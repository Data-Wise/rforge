"""
R ecosystem discovery.

Walks a directory tree looking for R `DESCRIPTION` files, parses them into
structured `Package` records, and classifies the result as a single package,
an ecosystem, or a hybrid layout.

Optionally enriches discovery from an *ecosystem manifest* (curation metadata:
role/repo/CRAN state). The manifest is located via a `manifest:` path in the
root `.rforge.yaml`, parsed by a vendored YAML-subset reader (`parse_manifest`),
matched to discovered packages by name, and any mismatch is reported as `drift`.
An absent/unreadable manifest leaves the zero-manifest behavior unchanged.

Pure Python — no R subprocess, no external deps beyond the stdlib (the manifest
reader is a hand-rolled YAML subset, not PyYAML). Ported
from `rforge-mcp/dist/tools/discovery/detect.js` (Path B Phase B.1).

Usage (CLI, from repo root):
    python3 -m lib.discovery --path . --format text
    python3 -m lib.discovery --path /path/to/eco --format json

Usage (Python API):
    from lib.discovery import detect_ecosystem
    eco = detect_ecosystem(".")
    print(eco.kind, [p.name for p in eco.packages])
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Optional


# ───────────────────────── Dataclasses ─────────────────────────


@dataclass
class Description:
    """Parsed contents of an R DESCRIPTION file."""

    package: str
    version: str
    title: Optional[str] = None
    description: Optional[str] = None
    license: Optional[str] = None
    depends: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    suggests: list[str] = field(default_factory=list)
    linking_to: list[str] = field(default_factory=list)
    url: Optional[str] = None


@dataclass
class ManifestEntry:
    """One package entry from an ecosystem manifest (curation metadata)."""

    name: str
    path: Optional[str] = None
    role: Optional[str] = None
    repo: Optional[str] = None
    cran: Optional[str] = None
    status_file: Optional[str] = None


@dataclass
class Manifest:
    """Parsed ecosystem manifest (e.g. ECOSYSTEM-MANIFEST.yaml).

    Curation metadata maintained by hand in a hub — what packages the ecosystem
    *should* contain, their roles, repos, and CRAN state. Distinct from on-disk
    discovery (`find_r_packages`), which is the source of truth for versions/deps.
    """

    ecosystem: Optional[str] = None
    updated: Optional[str] = None
    packages: list[ManifestEntry] = field(default_factory=list)


@dataclass
class Package:
    """An R package discovered on disk."""

    name: str
    version: str
    path: str
    category: Literal["active", "stable", "archived"] = "active"
    description: Optional[Description] = None
    manifest: Optional[ManifestEntry] = None  # curation metadata when a manifest matched


Kind = Literal["single", "ecosystem", "hybrid"]
Mode = Literal["minimal", "standard", "full"]


@dataclass
class Drift:
    """Mismatch between a manifest and what's on disk."""

    manifest_only: list[str] = field(default_factory=list)  # listed, not found on disk
    disk_only: list[str] = field(default_factory=list)  # found on disk, not in manifest


@dataclass
class Ecosystem:
    """Result of `detect_ecosystem()`."""

    root: str
    packages: list[Package]
    kind: Kind
    mode: Mode
    config_found: bool
    config_path: Optional[str] = None
    manifest_path: Optional[str] = None
    # Issue #20: the manifest's package names in *declared* order (empty in the
    # zero-manifest case), so consumers like `/rforge:status` can render in a
    # curated order rather than disk/alphabetical. Disk order stays in `packages`.
    manifest_order: list[str] = field(default_factory=list)
    drift: Drift = field(default_factory=Drift)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "kind": self.kind,
            "mode": self.mode,
            "config_found": self.config_found,
            "config_path": self.config_path,
            "manifest_path": self.manifest_path,
            "manifest_order": self.manifest_order,
            "drift": asdict(self.drift),
            "packages": [
                {**asdict(p), "description": asdict(p.description) if p.description else None}
                for p in self.packages
            ],
        }


# ───────────────────────── DESCRIPTION parser ─────────────────────────

_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9@]*)\s*:\s*(.*)$")
_DEP_NAME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9.]*)")


def _parse_dep_list(value: Optional[str]) -> list[str]:
    """Parse a comma-separated DESCRIPTION dep field, stripping version constraints.

    "dplyr (>= 1.0), ggplot2, R (>= 4.0)" → ["dplyr", "ggplot2"]
    (The R runtime itself is filtered out — it's not a CRAN package.)
    """
    if not value:
        return []
    out: list[str] = []
    for chunk in value.split(","):
        match = _DEP_NAME_RE.match(chunk.strip())
        if match:
            name = match.group(1)
            if name and name != "R":
                out.append(name)
    return out


def parse_description(content: str) -> Optional[Description]:
    """Parse the content of a DESCRIPTION file.

    DESCRIPTION uses an RFC-822-ish format: `Field: value` lines, with
    indented continuation lines belonging to the previous field.
    """
    fields: dict[str, str] = {}
    current_key = ""
    current_val = ""

    for raw_line in content.splitlines():
        # Walrus binds the match in one shot — no double regex eval, no
        # `assert` (which would be stripped under `python -O`).
        if raw_line and not raw_line[0].isspace() and (match := _FIELD_RE.match(raw_line)):
            if current_key:
                fields[current_key] = current_val.strip()
            current_key = match.group(1)
            current_val = match.group(2)
        elif raw_line.startswith((" ", "\t")) and current_key:
            current_val += " " + raw_line.strip()
    if current_key:
        fields[current_key] = current_val.strip()

    pkg = fields.get("Package", "")
    if not pkg:
        return None

    return Description(
        package=pkg,
        version=fields.get("Version", ""),
        title=fields.get("Title"),
        description=fields.get("Description"),
        license=fields.get("License"),
        depends=_parse_dep_list(fields.get("Depends")),
        imports=_parse_dep_list(fields.get("Imports")),
        suggests=_parse_dep_list(fields.get("Suggests")),
        linking_to=_parse_dep_list(fields.get("LinkingTo")),
        url=fields.get("URL"),
    )


def read_description(path: str | os.PathLike) -> Optional[Description]:
    """Read and parse a DESCRIPTION file. Returns None on any error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return parse_description(fh.read())
    except (OSError, UnicodeDecodeError):
        return None


# ───────────────────────── Manifest parser ─────────────────────────

# Keys recognized on a manifest package entry; anything else is ignored.
_MANIFEST_ENTRY_KEYS = {"name", "path", "role", "repo", "cran", "status_file"}


def _strip_inline_comment(value: str) -> str:
    """Drop a trailing ` # comment` from a scalar value.

    Splits on the first space-hash so a `#` that is part of the value (no
    preceding space) is preserved. The manifest schema uses no quoted strings,
    so this simple rule is sufficient.
    """
    idx = value.find(" #")
    if idx != -1:
        value = value[:idx]
    return value.strip()


def parse_manifest(content: str) -> Manifest:
    """Parse an ecosystem manifest from a strict YAML *subset*.

    Deliberately stdlib-only (no PyYAML). Supports exactly what the manifest
    schema uses: top-level scalars (`ecosystem`, `updated`, …) and a `packages:`
    list of flat maps. Blank lines and `#` comment lines are ignored. Anything
    fancier than this subset is silently skipped rather than raised — callers
    treat a sparse/empty Manifest as "no usable manifest".
    """
    manifest = Manifest()
    in_packages = False
    current: Optional[ManifestEntry] = None

    for raw in content.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        is_item = stripped.startswith("- ")
        body = stripped[2:].strip() if is_item else stripped
        if ":" not in body:
            continue
        key, _, value = body.partition(":")
        key = key.strip()
        value = _strip_inline_comment(value)
        indent = len(raw) - len(raw.lstrip())

        if indent == 0 and not is_item:
            if key == "packages":
                in_packages = True
                continue
            in_packages = False
            if key == "ecosystem":
                manifest.ecosystem = value or None
            elif key == "updated":
                manifest.updated = value or None
            continue

        if in_packages:
            if is_item:
                current = ManifestEntry(name="")
                manifest.packages.append(current)
            if current is not None and key in _MANIFEST_ENTRY_KEYS:
                setattr(current, key, value or None)

    return manifest


def read_manifest(path: str | os.PathLike) -> Optional[Manifest]:
    """Read and parse an ecosystem manifest. Returns None on any read error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return parse_manifest(fh.read())
    except (OSError, UnicodeDecodeError):
        return None


_CONFIG_MANIFEST_RE = re.compile(r"^manifest:\s*(.+)$", re.MULTILINE)


def _read_config_manifest_path(root: Path) -> Optional[str]:
    """Extract the optional `manifest:` path from `<root>/.rforge.yaml`."""
    try:
        text = (root / ".rforge.yaml").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _CONFIG_MANIFEST_RE.search(text)
    if not match:
        return None
    return _strip_inline_comment(match.group(1)) or None


def _read_site_allowlist(root: str | os.PathLike) -> tuple[list[str], bool]:
    """Read the optional `site.allowlist` list from `<root>/.rforge.yaml`.

    Parses the nested block form::

        site:
          allowlist:
            - PLAN-scratch.md
            - design-notes.md

    Returns ``(entries, malformed)``:

    - key absent (no `site:` or no `allowlist:` under it) → ``([], False)``
    - `allowlist:` present but **not** a block list (e.g. a scalar or empty) →
      ``([], True)`` so the caller can warn + fall back to the core allowlist.
    - `allowlist:` present as a list → ``([items], False)``.

    Stdlib-only (no PyYAML), matching this module's hand-rolled YAML subset.
    Never raises — an unreadable file degrades to ``([], False)``.
    """
    try:
        text = (Path(root) / ".rforge.yaml").read_text(
            encoding="utf-8", errors="replace")
    except OSError:
        return [], False

    in_site = False
    in_allowlist = False
    allowlist_seen = False
    allowlist_indent = -1
    inline_value = ""
    items: list[str] = []

    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()

        if indent == 0:
            # A new top-level key ends any site/allowlist context.
            in_site = stripped.startswith("site:")
            in_allowlist = False
            if in_site:
                # `site: something` inline would be malformed for our purposes,
                # but the block form `site:` is what we expect.
                pass
            continue

        if not in_site:
            continue

        if not in_allowlist:
            if stripped.startswith("allowlist:"):
                allowlist_seen = True
                in_allowlist = True
                allowlist_indent = indent
                inline_value = stripped[len("allowlist:"):].strip()
            # else: some other key under site: — ignore.
            continue

        # Inside allowlist: collect deeper-indented `- item` lines.
        if indent > allowlist_indent and stripped.startswith("- "):
            item = _strip_inline_comment(stripped[2:].strip())
            if item:
                items.append(item)
        elif indent <= allowlist_indent:
            in_allowlist = False
            # Re-evaluate this line as a potential sibling under site:.
            if indent > 0 and stripped.startswith("allowlist:"):
                allowlist_seen = True
                in_allowlist = True
                allowlist_indent = indent
                inline_value = stripped[len("allowlist:"):].strip()

    if not allowlist_seen:
        return [], False
    if items:
        return items, False
    # `allowlist:` was present but yielded no list items.
    # An inline scalar (`allowlist: foo`) is malformed; an empty block is also
    # treated as malformed so the caller warns + falls back to core.
    if inline_value:
        return [], True
    return [], True


def _enrich_packages(packages: list[Package], manifest: Manifest) -> Drift:
    """Attach manifest metadata to matching packages (by name, case-insensitive)
    and compute the drift between the manifest and what's on disk.
    """
    entries_by_name = {e.name.lower(): e for e in manifest.packages if e.name}
    for pkg in packages:
        entry = entries_by_name.get(pkg.name.lower())
        if entry is not None:
            pkg.manifest = entry
    disk_names = {p.name.lower() for p in packages}
    return Drift(
        manifest_only=sorted(
            e.name for e in manifest.packages if e.name and e.name.lower() not in disk_names
        ),
        disk_only=sorted(p.name for p in packages if p.name.lower() not in entries_by_name),
    )


# ───────────────────────── Filesystem scan ─────────────────────────


def _is_r_package(path: Path) -> bool:
    return (path / "DESCRIPTION").is_file()


def _infer_category(path: Path) -> Literal["active", "stable", "archived"]:
    lowered = str(path).lower()
    if "archived" in lowered or "deprecated" in lowered:
        return "archived"
    if "stable" in lowered or "cran" in lowered:
        return "stable"
    return "active"


def find_r_packages(root: str | os.PathLike, max_depth: int = 2) -> list[Package]:
    """Find all R packages under `root`, recursing at most `max_depth` levels.

    Mirrors the MCP server's traversal: if a directory is itself an R package,
    it's recorded and we don't descend into it. Hidden directories (`.git`,
    `.Rproj.user`, etc.) are skipped.
    """
    root_path = Path(root).resolve()
    found: list[Package] = []

    def scan(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if _is_r_package(path):
            desc = read_description(path / "DESCRIPTION")
            if desc:
                found.append(
                    Package(
                        name=desc.package,
                        version=desc.version,
                        path=str(path),
                        category=_infer_category(path),
                        description=desc,
                    )
                )
            return
        try:
            entries = sorted(path.iterdir())
        except (PermissionError, FileNotFoundError):
            return
        for entry in entries:
            if entry.is_dir() and not entry.name.startswith("."):
                scan(entry, depth + 1)

    scan(root_path, 0)
    return found


# ───────────────────────── Ecosystem classification ─────────────────────────


def _mcp_mode(package_count: int, current_is_package: bool, parent_count: int) -> Mode:
    """Replicate the MCP server's mode determination (minimal/standard/full).

    This preserves wire compatibility for side-by-side validation in Step 6 of
    the ORCHESTRATE plan.
    """
    if package_count == 0:
        if current_is_package and parent_count > 1:
            return "full" if parent_count >= 5 else "standard"
        return "minimal"
    if package_count == 1:
        return "minimal"
    if package_count < 5:
        return "standard"
    return "full"


_KIND_DECL_RE = re.compile(r"^kind:\s*hybrid\b", re.MULTILINE)


def _classify_kind(root: Path, packages: list[Package]) -> Kind:
    """Map filesystem state → user-facing 'single' / 'ecosystem' / 'hybrid'.

    Heuristic (strict):
      - 0-1 packages → 'single'
      - 2+ packages → 'ecosystem' by default
      - 'hybrid' only if `.rforge.yaml` explicitly declares `kind: hybrid`

    Rationale: filesystem-based hybrid detection is too fuzzy (a stray
    `docs/` sibling shouldn't change the classification). Users who run
    genuinely mixed layouts opt in via config.
    """
    if len(packages) <= 1:
        return "single"
    config = root / ".rforge.yaml"
    if config.is_file():
        try:
            if _KIND_DECL_RE.search(config.read_text(encoding="utf-8", errors="replace")):
                return "hybrid"
        except OSError:
            pass
    return "ecosystem"


def detect_ecosystem(path: str | os.PathLike = ".") -> Ecosystem:
    """Detect R ecosystem at `path`.

    Returns an `Ecosystem` describing the layout: the packages found, their
    classification (single / ecosystem / hybrid), the MCP-compatible mode
    (minimal / standard / full), and whether an `.rforge.yaml` config exists.

    Raises:
        FileNotFoundError: if `path` does not exist.
        NotADirectoryError: if `path` exists but is not a directory.
    """
    root = Path(path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"path does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"path is not a directory: {root}")
    config_path = root / ".rforge.yaml"
    config_found = config_path.is_file()

    packages = find_r_packages(root)

    # MCP mode (preserved for cross-validation)
    parent_pkgs: list[Package] = []
    current_is_pkg = _is_r_package(root)
    if not packages and current_is_pkg:
        parent_pkgs = find_r_packages(root.parent, max_depth=1)
    mode: Mode = _mcp_mode(len(packages), current_is_pkg, len(parent_pkgs))

    kind = _classify_kind(root, packages)

    # Optional manifest enrichment — keyed off `.rforge.yaml`'s `manifest:` path.
    # Degrades silently to the zero-manifest case on any miss; never raises.
    manifest_path: Optional[str] = None
    manifest_order: list[str] = []
    drift = Drift()
    if config_found:
        manifest_rel = _read_config_manifest_path(root)
        if manifest_rel:
            candidate = (root / manifest_rel).resolve()
            # Path-escape guard (issue #19): a `manifest:` resolving outside the
            # ecosystem root is ignored — never read arbitrary files off-tree.
            within_root = candidate == root or candidate.is_relative_to(root)
            if within_root and candidate.is_file():
                parsed = read_manifest(candidate)
                if parsed is not None:
                    manifest_path = str(candidate)
                    # Issue #20: preserve the manifest's declared package order.
                    manifest_order = [e.name for e in parsed.packages if e.name]
                    drift = _enrich_packages(packages, parsed)

    return Ecosystem(
        root=str(root),
        packages=packages,
        kind=kind,
        mode=mode,
        config_found=config_found,
        config_path=str(config_path) if config_found else None,
        manifest_path=manifest_path,
        manifest_order=manifest_order,
        drift=drift,
    )


# ───────────────────────── Formatters ─────────────────────────


def _truncate(text: str, limit: int) -> str:
    """Clip `text` to `limit` chars with an ellipsis when it overflows."""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_text(eco: Ecosystem) -> str:
    """Terminal-friendly rendering of an Ecosystem."""
    lines: list[str] = []
    icon = {"single": "📦", "ecosystem": "🏗️ ", "hybrid": "🧩"}[eco.kind]
    lines.append(f"{icon} {eco.kind.capitalize()}: {eco.root}")
    header = (f"   Packages: {len(eco.packages)} | mode: {eco.mode}"
              f" | config: {'found' if eco.config_found else 'not found'}")
    if eco.manifest_path:
        header += f" | manifest: {os.path.basename(eco.manifest_path)}"
    lines.append(header)
    if eco.packages:
        lines.append("")
        for pkg in eco.packages[:10]:
            tag = f" [{pkg.category}]" if pkg.category != "active" else ""
            role = ""
            if pkg.manifest and pkg.manifest.role:
                role = f" — {_truncate(pkg.manifest.role, 50)}"
            lines.append(f"   ├─ {pkg.name} {pkg.version}{tag}{role}")
        if len(eco.packages) > 10:
            lines.append(f"   └─ ... and {len(eco.packages) - 10} more")
    if eco.drift.manifest_only or eco.drift.disk_only:
        lines.append("")
        lines.append("⚠️  Manifest drift:")
        if eco.drift.manifest_only:
            lines.append(
                f"   in manifest, not on disk: {', '.join(eco.drift.manifest_only)}"
            )
        if eco.drift.disk_only:
            lines.append(
                f"   on disk, not in manifest: {', '.join(eco.drift.disk_only)}"
            )
    return "\n".join(lines)


def format_json(eco: Ecosystem) -> str:
    return json.dumps(eco.to_dict(), indent=2, sort_keys=True)


# ───────────────────────── CLI ─────────────────────────


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="discovery",
        description="Detect R package ecosystem structure.",
    )
    parser.add_argument("--path", default=".", help="Directory to scan (default: cwd)")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args(argv)

    try:
        eco = detect_ecosystem(args.path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(format_json(eco))
    else:
        print(format_text(eco))
    return 0


if __name__ == "__main__":
    sys.exit(_main())

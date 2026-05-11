"""
R ecosystem discovery.

Walks a directory tree looking for R `DESCRIPTION` files, parses them into
structured `Package` records, and classifies the result as a single package,
an ecosystem, or a hybrid layout.

Pure Python — no R subprocess, no external deps beyond the stdlib. Ported
from `rforge-mcp/dist/tools/discovery/detect.js` (Path B Phase B.1).

Usage (CLI):
    python3 lib/discovery.py --path . --format text
    python3 lib/discovery.py --path /path/to/eco --format json

Usage (Python API):
    from discovery import detect_ecosystem
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
class Package:
    """An R package discovered on disk."""

    name: str
    version: str
    path: str
    category: Literal["active", "stable", "archived"] = "active"
    description: Optional[Description] = None


Kind = Literal["single", "ecosystem", "hybrid"]
Mode = Literal["minimal", "standard", "full"]


@dataclass
class Ecosystem:
    """Result of `detect_ecosystem()`."""

    root: str
    packages: list[Package]
    kind: Kind
    mode: Mode
    config_found: bool
    config_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "kind": self.kind,
            "mode": self.mode,
            "config_found": self.config_found,
            "config_path": self.config_path,
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
        if raw_line and not raw_line[0].isspace() and _FIELD_RE.match(raw_line):
            if current_key:
                fields[current_key] = current_val.strip()
            match = _FIELD_RE.match(raw_line)
            assert match
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
    """
    root = Path(path).resolve()
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

    return Ecosystem(
        root=str(root),
        packages=packages,
        kind=kind,
        mode=mode,
        config_found=config_found,
        config_path=str(config_path) if config_found else None,
    )


# ───────────────────────── Formatters ─────────────────────────


def format_text(eco: Ecosystem) -> str:
    """Terminal-friendly rendering of an Ecosystem."""
    lines: list[str] = []
    icon = {"single": "📦", "ecosystem": "🏗️ ", "hybrid": "🧩"}[eco.kind]
    lines.append(f"{icon} {eco.kind.capitalize()}: {eco.root}")
    lines.append(f"   Packages: {len(eco.packages)} | mode: {eco.mode}"
                 f" | config: {'found' if eco.config_found else 'not found'}")
    if eco.packages:
        lines.append("")
        for pkg in eco.packages[:10]:
            tag = f" [{pkg.category}]" if pkg.category != "active" else ""
            lines.append(f"   ├─ {pkg.name} {pkg.version}{tag}")
        if len(eco.packages) > 10:
            lines.append(f"   └─ ... and {len(eco.packages) - 10} more")
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

    eco = detect_ecosystem(args.path)
    if args.format == "json":
        print(format_json(eco))
    else:
        print(format_text(eco))
    return 0


if __name__ == "__main__":
    sys.exit(_main())

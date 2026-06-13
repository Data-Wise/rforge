"""
Intra-package dependency reconciliation (`r:deps-sync`).

Scans a package's R sources for namespace usage and reconciles it against the
``Depends``/``Imports``/``Suggests`` fields of ``DESCRIPTION`` — surfacing
**missing**, **unused**, and **misclassified** dependencies plus a suggested
``DESCRIPTION`` patch. Report-only by default; ``--write`` applies the
unambiguous changes.

Pure Python — no R subprocess, no external deps beyond the stdlib. Reuses
``lib.discovery.read_description`` for the DCF parse. *Intra*-package — it
complements ``lib.deps`` (the *inter*-package ecosystem graph), which is a
different concern.

The **misclassified** finding (a ``Suggests`` package used *unconditionally* in
``R/``) is the static sibling of the cran-incoming noSuggests check
(``_R_CHECK_DEPENDS_ONLY_``): this catches it before R runs.

Usage (CLI, from repo root):
    python3 -m lib.deps_sync --path /path/to/pkg            # report (dry-run default)
    python3 -m lib.deps_sync --path /path/to/pkg --write    # apply unambiguous changes
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .discovery import read_description

__all__ = ["Usage", "scan_usage", "reconcile", "deps_sync"]

# R base-priority packages — always available, never need declaring. (Recommended
# packages like MASS/Matrix are NOT here: a package using them must still declare.)
_BASE_PKGS = frozenset({
    "base", "compiler", "datasets", "graphics", "grdevices", "grid", "methods",
    "parallel", "splines", "stats", "stats4", "tcltk", "tools", "utils",
})

# Usage patterns ──────────────────────────────────────────────────────────────
_NS_RE = re.compile(r"(?<![\w.])([a-zA-Z][a-zA-Z0-9.]*):{2,3}")           # pkg:: / pkg:::
_LIBRARY_RE = re.compile(r"\b(?:library|require)\(\s*['\"]?([a-zA-Z][a-zA-Z0-9.]*)")
_REQUIRENS_RE = re.compile(r"\brequireNamespace\(\s*['\"]([a-zA-Z][a-zA-Z0-9.]*)['\"]")
_LOADNS_RE = re.compile(r"\bloadNamespace\(\s*['\"]([a-zA-Z][a-zA-Z0-9.]*)['\"]")
_ROX_IMPORTFROM_RE = re.compile(r"^#'\s*@importFrom\s+([a-zA-Z][a-zA-Z0-9.]*)")
_ROX_IMPORT_RE = re.compile(r"^#'\s*@import\s+([a-zA-Z][a-zA-Z0-9.]*)\b")
_NS_IMPORTFROM_RE = re.compile(r"^\s*importFrom\(\s*([a-zA-Z][a-zA-Z0-9.]*)")
_NS_IMPORT_RE = re.compile(r"^\s*import\(\s*([a-zA-Z][a-zA-Z0-9.]*)\s*\)")
_DEP_NAME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9.]*)")  # strip "MASS (>= 1.0)" → "MASS"


@dataclass
class Usage:
    """Where and how one package is used across a package's sources.

    `in_r_unconditional` means it needs `Imports`; guarded / tests-only use is
    satisfied by `Suggests`.
    """

    name: str  # canonical (first-seen) spelling
    in_r_unconditional: bool = False  # pkg::, library(), @importFrom, NAMESPACE
    in_r_guarded: bool = False        # requireNamespace()/loadNamespace() in R/
    in_tests_or_vignettes: bool = False

    @property
    def needs_imports(self) -> bool:
        return self.in_r_unconditional

    @property
    def needs_suggests(self) -> bool:
        # used somewhere, but only in a Suggests-satisfiable position
        return not self.in_r_unconditional and (self.in_r_guarded or self.in_tests_or_vignettes)


def _envelope(status: str, findings: list, patch: dict, messages: list) -> dict:
    """House-style envelope, mirroring `lib.cranlint`/`lib.rcmd` keys."""
    return {
        "kind": "deps-sync",
        "status": status,
        "findings": findings,
        "patch": patch,
        "messages": messages,
        "engine_missing": [],
    }


def _iter_source_files(root: Path):
    """Yield (path, bucket) for scannable sources. bucket ∈ {'R','test_vig'}."""
    for sub, bucket in (("R", "R"), ("tests", "test_vig"), ("vignettes", "test_vig")):
        d = root / sub
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.suffix.lower() in (".r", ".rmd", ".qmd") and p.is_file():
                yield p, bucket


def _norm(name: str) -> str:
    return name.strip().lower()


def scan_usage(path: str | os.PathLike = ".") -> dict[str, Usage]:
    """Scan ``R/``, ``tests/``, ``vignettes/`` + ``NAMESPACE`` for package usage.

    Returns a map of lowercased package name → :class:`Usage`. Base-priority R
    packages are excluded (they never need declaring).
    """
    root = Path(path)
    usages: dict[str, Usage] = {}

    def mark(name: str, *, uncond=False, guarded=False, testvig=False) -> None:
        key = _norm(name)
        if not key or key in _BASE_PKGS or key == "r":
            return
        u = usages.get(key)
        if u is None:
            u = usages[key] = Usage(name=name)
        u.in_r_unconditional = u.in_r_unconditional or uncond
        u.in_r_guarded = u.in_r_guarded or guarded
        u.in_tests_or_vignettes = u.in_tests_or_vignettes or testvig

    for src, bucket in _iter_source_files(root):
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        in_r = bucket == "R"
        for line in text.splitlines():
            # guarded references first (so a guarded-only pkg isn't marked unconditional)
            guarded_here = set()
            for m in _REQUIRENS_RE.finditer(line):
                guarded_here.add(_norm(m.group(1)))
                mark(m.group(1), guarded=in_r, testvig=not in_r)
            for m in _LOADNS_RE.finditer(line):
                guarded_here.add(_norm(m.group(1)))
                mark(m.group(1), guarded=in_r, testvig=not in_r)
            # roxygen tags (R/ only) → declared Imports intent
            rox = _ROX_IMPORTFROM_RE.match(line) or _ROX_IMPORT_RE.match(line)
            if rox and in_r:
                mark(rox.group(1), uncond=True)
                continue
            # unconditional namespace/library use
            for m in _NS_RE.finditer(line):
                if _norm(m.group(1)) in guarded_here:
                    continue
                mark(m.group(1), uncond=in_r, testvig=not in_r)
            for m in _LIBRARY_RE.finditer(line):
                mark(m.group(1), uncond=in_r, testvig=not in_r)

    # NAMESPACE = the generated import truth (always Imports-level)
    ns = root / "NAMESPACE"
    if ns.is_file():
        try:
            for line in ns.read_text(encoding="utf-8", errors="replace").splitlines():
                m = _NS_IMPORTFROM_RE.match(line) or _NS_IMPORT_RE.match(line)
                if m:
                    mark(m.group(1), uncond=True)
        except OSError:
            pass

    return usages


def _declared(desc) -> tuple[set[str], set[str], dict[str, str]]:
    """Return (strong, suggests, display) name sets from a Description.

    `strong` = Depends ∪ Imports ∪ LinkingTo (all "must be present"); `suggests`
    = Suggests. `display` maps lowercased → original spelling for messages.
    """
    strong, suggests, display = set(), set(), {}

    def add(raw_list, target):
        for raw in raw_list:
            m = _DEP_NAME_RE.match(raw.strip())
            if not m:
                continue
            name = m.group(1)
            if _norm(name) == "r":
                continue
            display.setdefault(_norm(name), name)
            target.add(_norm(name))

    add(getattr(desc, "depends", []), strong)
    add(getattr(desc, "imports", []), strong)
    add(getattr(desc, "linking_to", []), strong)
    add(getattr(desc, "suggests", []), suggests)
    return strong, suggests, display


def reconcile(path: str | os.PathLike = ".") -> dict:
    """Reconcile a package's code usage against its DESCRIPTION dependencies.

    Emits findings (missing / missing-suggests / unused / misclassified) and a
    suggested patch. Never raises on a missing/unparseable DESCRIPTION — returns
    a ``warn`` envelope instead.
    """
    root = Path(path)
    desc_path = root / "DESCRIPTION" if root.is_dir() else root
    desc = read_description(desc_path)
    if desc is None:
        return _envelope("warn", [], {}, [
            f"No parseable DESCRIPTION at {desc_path} — is this an R package? "
            "Try /rforge:detect."
        ])

    strong, suggests, display = _declared(desc)
    usages = scan_usage(root)
    findings: list[dict] = []
    patch = {"add_imports": [], "add_suggests": [], "move_to_imports": [], "remove_candidates": []}

    used_keys = set(usages)
    for key, u in sorted(usages.items()):
        if u.needs_imports and key not in strong:
            if key in suggests:
                findings.append({"kind": "misclassified", "package": u.name,
                                 "detail": "in Suggests but used unconditionally in R/ → move to Imports"})
                patch["move_to_imports"].append(u.name)
            else:
                findings.append({"kind": "missing", "package": u.name,
                                 "detail": "used in R/ but not declared → add to Imports"})
                patch["add_imports"].append(u.name)
        elif u.needs_suggests and key not in strong and key not in suggests:
            findings.append({"kind": "missing_suggests", "package": u.name,
                             "detail": "used in tests/vignettes (or guarded) but not declared → add to Suggests"})
            patch["add_suggests"].append(u.name)

    # unused: declared but no usage found anywhere (advisory — may be dynamic)
    for key in sorted((strong | suggests) - used_keys):
        findings.append({"kind": "unused", "package": display.get(key, key),
                         "detail": "declared but no usage found (advisory — may be used dynamically)"})
        patch["remove_candidates"].append(display.get(key, key))

    status = "warn" if findings else "ok"
    msgs = []
    if any(f["kind"] == "misclassified" for f in findings):
        msgs.append("A Suggests package is used unconditionally in R/. Move it to Imports, or "
                    "guard with requireNamespace() in code AND skip_if_not_installed() in tests.")
    return _envelope(status, findings, patch, msgs)


def _read_field_specs(text: str, field_name: str) -> list[str]:
    """Extract the VERBATIM dependency specifiers from a DCF field's raw text.

    Unlike discovery's name-only parse, this preserves version constraints, e.g.
    ``"dplyr (>= 1.1.0)"`` stays intact. Returns the full spec strings in source
    order. Used so ``_apply_patch`` never drops constraints on untouched deps.
    """
    pat = re.compile(rf"^{re.escape(field_name)}:(.*?)(?=^\S|\Z)", re.MULTILINE | re.DOTALL)
    m = pat.search(text)
    if not m:
        return []
    specs: list[str] = []
    for part in m.group(1).split(","):
        spec = part.strip()
        if spec:
            specs.append(spec)
    return specs


def _apply_patch(desc_path: Path, patch: dict) -> list[str]:
    """Apply the *unambiguous* parts of a patch to DESCRIPTION's Imports/Suggests.

    Adds missing imports/suggests and moves misclassified packages to Imports.
    `remove_candidates` are advisory and never auto-removed. Returns a log of
    what changed. Best-effort DCF rewrite — normalizes the two fields it touches.

    Deps the patch does not modify keep their VERBATIM specifier (name +
    constraint) — the rewrite is built from the original field text, not from
    discovery's name-only parse, so ``(>= x.y.z)`` floors survive.
    """
    text = desc_path.read_text(encoding="utf-8", errors="replace")
    if not (re.search(r"^Imports:", text, re.MULTILINE) or
            re.search(r"^Suggests:", text, re.MULTILINE) or
            re.search(r"^Package:", text, re.MULTILINE)):
        return ["could not parse DESCRIPTION — no changes written"]

    # full spec strings (verbatim, with constraints) keyed by normalized name
    imports = _read_field_specs(text, "Imports")
    suggests = _read_field_specs(text, "Suggests")
    imp_keys = {_norm(_DEP_NAME_RE.match(d).group(1)) for d in imports if _DEP_NAME_RE.match(d)}
    sug_keys = {_norm(_DEP_NAME_RE.match(d).group(1)) for d in suggests if _DEP_NAME_RE.match(d)}
    log: list[str] = []

    for name in patch.get("add_imports", []):
        if _norm(name) not in imp_keys:
            imports.append(name); imp_keys.add(_norm(name)); log.append(f"+Imports: {name}")
    for name in patch.get("move_to_imports", []):
        suggests = [d for d in suggests
                    if not _DEP_NAME_RE.match(d) or _norm(_DEP_NAME_RE.match(d).group(1)) != _norm(name)]
        sug_keys.discard(_norm(name))
        if _norm(name) not in imp_keys:
            imports.append(name); imp_keys.add(_norm(name)); log.append(f"Suggests→Imports: {name}")
    for name in patch.get("add_suggests", []):
        if _norm(name) not in sug_keys and _norm(name) not in imp_keys:
            suggests.append(name); sug_keys.add(_norm(name)); log.append(f"+Suggests: {name}")

    if not log:
        return []
    new_text = _rewrite_field(text, "Imports", sorted(imports, key=str.lower))
    new_text = _rewrite_field(new_text, "Suggests", sorted(suggests, key=str.lower))
    desc_path.write_text(new_text, encoding="utf-8")
    return log


def _rewrite_field(text: str, field_name: str, values: list[str]) -> str:
    """Replace (or append) a comma-list DCF field with `values`, one per line."""
    if not values:
        return text
    block = f"{field_name}:\n" + ",\n".join(f"    {v}" for v in values) + "\n"
    # match "Field:" through the last continuation line
    pat = re.compile(rf"^{re.escape(field_name)}:.*?(?=^\S|\Z)", re.MULTILINE | re.DOTALL)
    if pat.search(text):
        return pat.sub(block, text, count=1)
    # append before trailing newline
    return text.rstrip("\n") + "\n" + block


def deps_sync(path: str | os.PathLike = ".", *, write: bool = False) -> dict:
    """Reconcile + (optionally) apply. Default is report-only (dry-run)."""
    env = reconcile(path)
    if write and env["status"] != "error" and env.get("patch"):
        root = Path(path)
        desc_path = root / "DESCRIPTION" if root.is_dir() else root
        if desc_path.is_file():
            applied = _apply_patch(desc_path, env["patch"])
            env["applied"] = applied
            env["messages"].append(
                f"--write applied {len(applied)} change(s)" if applied else "--write: nothing to apply"
            )
    else:
        env["applied"] = []
    return env


def format_text(env: dict) -> str:
    """Terminal-friendly rendering of a deps-sync envelope."""
    icon = {"ok": "✅", "warn": "⚠️ ", "error": "❌"}.get(env["status"], "•")
    lines = [f"{icon} deps-sync: {env['status']}"]
    groups: dict[str, list[str]] = {}
    for f in env.get("findings", []):
        groups.setdefault(f["kind"], []).append(f"{f['package']} — {f['detail']}")
    order = ["missing", "misclassified", "missing_suggests", "unused"]
    for kind in order:
        if kind in groups:
            lines.append(f"\n{kind} ({len(groups[kind])}):")
            lines += [f"  • {x}" for x in groups[kind]]
    if env.get("applied"):
        lines.append("\napplied:")
        lines += [f"  ✏️  {x}" for x in env["applied"]]
    for m in env.get("messages", []):
        lines.append(f"\n💡 {m}")
    return "\n".join(lines)


def _main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="lib.deps_sync", description=__doc__)
    ap.add_argument("--path", default=".")
    ap.add_argument("--write", action="store_true",
                    help="apply unambiguous Imports/Suggests changes to DESCRIPTION")
    ap.add_argument("--dry-run", action="store_true", help="report only (the default)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args(argv)
    env = deps_sync(ns.path, write=ns.write and not ns.dry_run)
    print(json.dumps(env, indent=2) if ns.format == "json" else format_text(env))
    return 0 if env["status"] in ("ok", "warn") else 1


if __name__ == "__main__":
    sys.exit(_main())

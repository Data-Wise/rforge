"""
pkgdown stray-file leak detector.

Pure-Python (stdlib + a `git` subprocess, **no R**) preflight that flags scratch
files which pkgdown would render and publish. pkgdown renders **every** top-level
``.md`` (not just ``README``/``NEWS``) plus non-``.Rd`` files in ``man/``. In
``vignettes/`` the scope is narrowed (USER DECISION — "aggressive in articles/
only"): every file under ``vignettes/articles/**`` is a candidate, but a
top-level rendered vignette (``.Rmd``/``.qmd``/``.Rnw``/``.Rmarkdown``) is
auto-trusted — only top-level NON-rendered files (``.md``/``.txt``/…) are
flagged. ``.Rbuildignore`` does **not** gate any of
this (it only affects ``R CMD build``). So a stray ``PLAN-*.md`` /
``ISSUE-*.md`` / ``NOTES.md`` leaks onto the published site — the failure mode
behind issue #52.

``check_site_leaks(path)`` lists candidate scratch files across that
pkgdown-rendered surface, minus an allowlist:

- **Core allowlist** (fixed, case-insensitive, with/without ``.md``):
  ``README``, ``NEWS``, ``LICENSE``/``LICENCE``, ``CHANGELOG``, ``index``,
  ``cran-comments``.
- **plus** the optional ``.rforge.yaml`` ``site.allowlist`` list (read via
  ``lib.discovery``). A malformed override (present but not a list) is ignored
  with a ``warn`` message — never a crash; the core set still applies.

Each hit is tagged ``tracked`` / ``untracked`` / ``modified`` from git
(``git ls-files`` for the tracked set, ``git status --porcelain`` for the
delta). If ``git`` is absent or the path is not a repo, the detector degrades:
``git_status`` is ``None`` and files are still flagged by filename.

Advisory only — emits the rforge house envelope
(``{kind, status, findings, messages, engine_missing: []}``), status is
``ok``/``warn`` (never ``blocked`` — that gate lives in the ``--deploy`` path),
and the CLI always exits 0.

Usage (CLI, from repo root):
    python3 -m lib.sitelint <package-dir>

Usage (Python API):
    from lib import sitelint
    env = sitelint.check_site_leaks(".")
    print(env["status"], [f["file"] for f in env["findings"]])
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import discovery

# ───────────────────────── allowlist ─────────────────────────

# Fixed core allowlist, compared after normalizing (lowercase, strip a single
# trailing ".md"). Covers case-insensitive LICENCE and with/without .md.
_CORE_ALLOWLIST = {
    "readme", "news", "license", "licence", "changelog", "index",
    "cran-comments",
}

# Legitimate (non-leak) extensions for man/ (only generated .Rd is trusted).
_MAN_DOC_EXT = {".rd"}

# Rendered vignette extensions: a TOP-LEVEL vignettes/<file> with one of these
# is a legit vignette and is AUTO-TRUSTED (never flagged). This trust applies
# ONLY one level deep in vignettes/ — vignettes/articles/** is web-only/
# scratch-prone and every file there is a candidate regardless of extension
# (USER DECISION: "aggressive in articles/ only"). Top-level NON-rendered files
# (e.g. .md, .txt) remain candidates subject to the allowlist.
_RENDERED_VIGNETTE_EXT = {".rmd", ".qmd", ".rnw", ".rmarkdown"}


def _normalize(name: str) -> str:
    """Lowercase and strip a single trailing ``.md`` for allowlist matching."""
    low = name.lower()
    if low.endswith(".md"):
        low = low[:-3]
    return low


# ───────────────────────── envelope helper ─────────────────────────


def _envelope(status: str, findings: list, messages: list) -> dict:
    """Build the house-style advisory envelope (mirrors lib/cranlint.py)."""
    return {
        "kind": "site-leaks",
        "status": status,
        "findings": findings,
        "messages": messages,
        "engine_missing": [],
    }


# ───────────────────────── git status ─────────────────────────


def _git_status_map(root: Path) -> Optional[dict[str, str]]:
    """Return ``{relpath: "tracked"|"untracked"|"modified"}`` for `root`.

    Tracked set comes from ``git ls-files`` (so a *clean committed* scratch file
    — the CI-leak case — is still labelled ``tracked``; it never appears in
    ``git status --porcelain``). The porcelain delta then promotes untracked
    (``??``) and modified (``M`` in either column) entries. Priority:
    modified > tracked > untracked.

    Returns ``None`` if git is unavailable or `root` is not a repo (caller
    degrades to filename-only linting).

    Decode-safe: the subprocess reads use ``errors="replace"`` and the except
    also catches ``ValueError`` (⊃ ``UnicodeDecodeError``) so a non-UTF-8
    tracked filename degrades gracefully instead of escaping the
    "never raises" contract (mirrors ``discovery._read_site_allowlist``).
    """
    try:
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root), capture_output=True, text=True,
            errors="replace",
        )
        if tracked.returncode != 0:
            return None
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True,
            errors="replace",
        )
        if porcelain.returncode != 0:
            return None
    except (FileNotFoundError, OSError, ValueError):
        return None

    status: dict[str, str] = {}
    for line in tracked.stdout.splitlines():
        rel = line.strip()
        if rel:
            status[rel] = "tracked"

    for line in porcelain.stdout.splitlines():
        if not line or len(line) < 4:
            continue
        xy = line[:2]
        rel = line[3:].strip()
        # Rename form "old -> new": take the new path.
        if " -> " in rel:
            rel = rel.split(" -> ", 1)[1].strip()
        if not rel:
            continue
        if xy == "??":
            status.setdefault(rel, "untracked")
        elif "M" in xy or "A" in xy or "R" in xy:
            status[rel] = "modified"
        else:
            status.setdefault(rel, "tracked")
    return status


# ───────────────────────── HEAD tree ─────────────────────────


def _head_paths(root: Path) -> list[str]:
    """Relpaths committed to ``HEAD`` (``git ls-tree -r --name-only HEAD``).

    Deploy publishes ``HEAD``, so a file committed but deleted from disk still
    leaks. Returns ``[]`` on any failure (not a repo, unborn HEAD, git absent,
    non-UTF-8 output) — the disk scan + git-absent degrade still cover those.
    """
    try:
        res = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD"],
            cwd=str(root), capture_output=True, text=True,
            errors="replace",
        )
    except (FileNotFoundError, OSError, ValueError):
        return []
    if res.returncode != 0:
        return []
    return [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]


# ───────────────────────── candidate collection ─────────────────────────
#
# Candidates are sourced from BOTH the working tree (disk) and ``HEAD`` (the
# deploy republishes HEAD), unioned per scope. A path in HEAD but deleted from
# disk is still a valid candidate (Finding A). Each scope yields relpaths.


def _scope_of(relpath: str, legit_man: set[str]) -> Optional[str]:
    """Classify a relpath into a pkgdown scope, or ``None`` if out of scope.

    Scope rules (mirror what pkgdown renders + publishes):

    - **root**: a single-component ``*.md`` (top-level markdown surface).
    - **man**: ``man/<file>`` (one level deep, NOT ``man/figures/...``) whose
      extension is not ``.Rd``. ``man/figures/*`` style noise stays out.
    - **vignettes**: ``vignettes/articles/**`` recursively (the web-only
      articles convention) is ALWAYS a candidate, regardless of extension.
      Directly under ``vignettes/`` (one level deep), a RENDERED vignette
      (.Rmd/.qmd/.Rnw/.Rmarkdown) is AUTO-TRUSTED (a legit vignette, never
      flagged); a NON-rendered file (.md/.txt/...) IS a candidate subject to
      the allowlist. (Accepted gap: a top-level scratch ``.Rmd`` is
      auto-trusted — it is indistinguishable from a real vignette by name.)
    """
    parts = relpath.split("/")
    suffix = Path(relpath).suffix.lower()

    if len(parts) == 1:
        if suffix == ".md":
            return "root"
        return None

    if parts[0] == "man":
        # man/<file> only — skip nested dirs (man/figures/...).
        if len(parts) == 2 and suffix not in legit_man:
            return "man"
        return None

    if parts[0] == "vignettes":
        # vignettes/articles/** → recursive candidates (every file).
        if len(parts) >= 3 and parts[1] == "articles":
            return "vignettes"
        # vignettes/<file> → one level deep. Rendered ext is auto-trusted
        # (legit vignette). Accepted gap: a top-level scratch .Rmd is
        # auto-trusted — indistinguishable from a real vignette by name.
        if len(parts) == 2 and suffix not in _RENDERED_VIGNETTE_EXT:
            return "vignettes"
        return None

    return None


def _disk_relpaths(root: Path) -> list[str]:
    """Relpaths on disk relevant to the three scopes.

    Walks: top level (``*.md``), ``man/`` (one level), ``vignettes/`` (one
    level + ``articles/`` recursive). Returns relpaths; scope/ext filtering is
    applied later by ``_scope_of``.
    """
    out: list[str] = []

    def _add_dir(d: Path, prefix: str, recurse: bool) -> None:
        if not d.is_dir():
            return
        try:
            for entry in sorted(d.iterdir()):
                rel = f"{prefix}/{entry.name}" if prefix else entry.name
                if entry.is_file():
                    out.append(rel)
                elif entry.is_dir() and recurse:
                    _add_dir(entry, rel, recurse)
        except OSError:
            pass

    # top-level files
    try:
        for entry in sorted(root.iterdir()):
            if entry.is_file():
                out.append(entry.name)
    except OSError:
        pass
    # man/ one level deep
    _add_dir(root / "man", "man", recurse=False)
    # vignettes/ one level deep, plus articles/ recursive
    _add_dir(root / "vignettes", "vignettes", recurse=False)
    _add_dir(root / "vignettes" / "articles", "vignettes/articles",
             recurse=True)
    return out


# ───────────────────────── main check ─────────────────────────


def check_site_leaks(path: str | os.PathLike = ".") -> dict:
    """Flag stray scratch files pkgdown would render + publish (issue #52).

    Scans the pkgdown-rendered surface of the package at `path`:

    - root ``*.md`` (the default surface),
    - non-``.Rd`` files directly in ``man/``,
    - non-vignette files directly in ``vignettes/``,

    minus the allowlist (fixed core set ∪ ``.rforge.yaml`` ``site.allowlist``).
    Each hit is tagged ``tracked`` / ``untracked`` / ``modified`` via git, or
    ``None`` when git is unavailable / not a repo.

    Advisory: degrades to ``warn`` (never raises, never ``blocked``). Returns the
    house envelope; each finding is
    ``{file, where, git_status, severity, message}`` where ``where`` is one of
    ``root`` / ``man`` / ``vignettes``.
    """
    root = Path(path)
    messages: list[str] = []

    if not root.is_dir():
        return _envelope(
            "warn", [],
            [f"Package directory not found: {root} — skipping site-leak scan."],
        )

    # — resolve allowlist —
    # Path-aware matching (Finding C):
    #   * core allowlist (README/NEWS/...)  → ROOT scope only.
    #   * a BARE `.rforge.yaml` entry (no "/") → ROOT scope only, so a root
    #     entry never silently clears a same-basename stray under man/ or
    #     vignettes/.
    #   * a path-qualified entry `dir/name` → that EXACT relpath.
    # Matching is normalized (lowercase, strip one trailing ".md") component-wise.
    allow_extra, malformed = discovery._read_site_allowlist(root)
    if malformed:
        messages.append(
            ".rforge.yaml site.allowlist is malformed (expected a list of "
            "filenames) — ignoring the override and using the core allowlist.")

    allow_root: set[str] = set(_CORE_ALLOWLIST)   # bare → root scope
    allow_relpath: set[str] = set()               # dir/name → exact relpath
    for entry in allow_extra:
        if "/" in entry:
            allow_relpath.add("/".join(_normalize(p) for p in entry.split("/")))
        else:
            allow_root.add(_normalize(entry))

    def _allowed(relpath: str) -> bool:
        parts = relpath.split("/")
        if len(parts) == 1:
            return _normalize(parts[0]) in allow_root
        return "/".join(_normalize(p) for p in parts) in allow_relpath

    # — git status (degrade to None) —
    status_map = _git_status_map(root)
    if status_map is None:
        messages.append(
            "git unavailable or not a repository — linting by filename only "
            "(no tracked/untracked/modified tags).")

    def _tag(relpath: str) -> Optional[str]:
        if status_map is None:
            return None
        # Tracked/untracked/modified files are explicitly in the map (from
        # ls-files + porcelain). A candidate not in the map is on disk but
        # neither tracked nor reported by porcelain → gitignored. Never call it
        # "tracked".
        return status_map.get(relpath, "ignored")

    # — collect candidates: union of disk + HEAD, classified per scope —
    candidate_rels: set[str] = set()
    for rel in _disk_relpaths(root):
        candidate_rels.add(rel)
    for rel in _head_paths(root):
        candidate_rels.add(rel)

    findings: list[dict] = []
    for relpath in sorted(candidate_rels):
        where = _scope_of(relpath, _MAN_DOC_EXT)
        if where is None:
            continue
        if _allowed(relpath):
            continue
        findings.append({
            "file": relpath,
            "where": where,
            "git_status": _tag(relpath),
            "severity": "advisory",
            "message": (
                f"'{relpath}' would be rendered + published by pkgdown "
                f"(every {where} file is part of the site surface). Move it "
                f"to a gitignored subdir, allowlist it via .rforge.yaml "
                f"site.allowlist, or remove it."),
        })

    status = "warn" if findings else "ok"
    if not findings and not messages:
        messages = ["No stray pkgdown-rendered files detected."]
    return _envelope(status, findings, messages)


# ───────────────────────── CLI ─────────────────────────


def _main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv and not argv[0].startswith("-") else "."
    print(json.dumps(check_site_leaks(path), indent=2))
    return 0  # advisory — always succeeds


if __name__ == "__main__":
    sys.exit(_main())

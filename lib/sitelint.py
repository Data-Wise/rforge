"""
pkgdown stray-file leak detector.

Pure-Python (stdlib + a `git` subprocess, **no R**) preflight that flags scratch
files which pkgdown would render and publish. pkgdown renders **every** top-level
``.md`` (not just ``README``/``NEWS``) plus non-``.Rd`` files in ``man/`` and
non-vignette files in ``vignettes/``; ``.Rbuildignore`` does **not** gate any of
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

# Legitimate (non-leak) extensions per scoped subdir.
_MAN_DOC_EXT = {".rd"}
_VIGNETTE_EXT = {".rmd", ".rnw", ".qmd", ".rmarkdown"}


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
    """
    try:
        tracked = subprocess.run(
            ["git", "ls-files"],
            cwd=str(root), capture_output=True, text=True,
        )
        if tracked.returncode != 0:
            return None
        porcelain = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root), capture_output=True, text=True,
        )
        if porcelain.returncode != 0:
            return None
    except (FileNotFoundError, OSError):
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


# ───────────────────────── candidate collection ─────────────────────────


def _root_candidates(root: Path) -> list[str]:
    """Top-level ``*.md`` files (the pkgdown default surface)."""
    out: list[str] = []
    try:
        for entry in sorted(root.iterdir()):
            if entry.is_file() and entry.suffix.lower() == ".md":
                out.append(entry.name)
    except OSError:
        pass
    return out


def _subdir_candidates(root: Path, sub: str, legit_ext: set[str]) -> list[str]:
    """Files directly under ``root/sub`` whose extension is NOT in `legit_ext`.

    Subdirectories (e.g. ``man/figures/``) are skipped — only top-level files in
    the scoped dir are considered, keeping the matcher conservative.
    """
    d = root / sub
    out: list[str] = []
    if not d.is_dir():
        return out
    try:
        for entry in sorted(d.iterdir()):
            if entry.is_file() and entry.suffix.lower() not in legit_ext:
                out.append(entry.name)
    except OSError:
        pass
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
    allow_extra, malformed = discovery._read_site_allowlist(root)
    if malformed:
        messages.append(
            ".rforge.yaml site.allowlist is malformed (expected a list of "
            "filenames) — ignoring the override and using the core allowlist.")
    extra_norm = {_normalize(a) for a in allow_extra}

    def _allowed(name: str) -> bool:
        n = _normalize(name)
        return n in _CORE_ALLOWLIST or n in extra_norm

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

    # — collect candidates per scope —
    scopes = [
        ("root", "", _root_candidates(root)),
        ("man", "man", _subdir_candidates(root, "man", _MAN_DOC_EXT)),
        ("vignettes", "vignettes",
         _subdir_candidates(root, "vignettes", _VIGNETTE_EXT)),
    ]

    findings: list[dict] = []
    for where, sub, names in scopes:
        for name in names:
            if _allowed(name):
                continue
            relpath = f"{sub}/{name}" if sub else name
            findings.append({
                "file": name,
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

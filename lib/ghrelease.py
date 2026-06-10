"""
GitHub release helpers for ``r:submit`` — construct the ``gh`` commands for a
CRAN pre-release and its promotion.

Pure Python (stdlib only); shells to nothing itself — it builds the argv lists
that the ``r:submit`` command runs via Bash, and reports ``gh`` availability.
The lifecycle (SPEC-r-submit-github-prerelease-2026-06-10):

  1. cut a GitHub **pre-release** of the submitted tarball  → ``prerelease_cmd()``
  2. hand off the CRAN submit step (no auto-submit)
  3. on CRAN acceptance, **promote in place**               → ``promote_cmd()``

Mechanism verified against the GitHub CLI docs::

    gh release create <tag> --prerelease --title ... --notes-file ... <asset>
    gh release edit   <tag> --prerelease=false --latest

Plain ``v<version>`` tags — the prerelease flag carries the "pending CRAN"
semantics, and promotion flips that flag in place (no ``-rc``/``-cran`` suffix
that would force a new tag on acceptance).
"""

from __future__ import annotations

import shutil
from typing import Optional

__all__ = ["gh_available", "submission_tag", "prerelease_cmd", "promote_cmd", "manual_recipe"]


def gh_available() -> bool:
    """True if the ``gh`` CLI is on PATH (auth is checked separately at runtime)."""
    return shutil.which("gh") is not None


def submission_tag(version: str) -> str:
    """Canonical pre-release tag for a submitted version: ``v<version>``."""
    return "v" + version.strip().lstrip("vV")


def prerelease_cmd(version: str, tarball: Optional[str] = None, *,
                   notes_file: Optional[str] = None, title: Optional[str] = None,
                   repo: Optional[str] = None) -> list[str]:
    """Build ``gh release create`` for a pre-release of the submitted tarball.

    `notes_file` is typically ``cran-comments.md`` (single source of truth for
    "what was submitted"); `tarball` is the built source artifact, attached as
    a release asset.
    """
    tag = submission_tag(version)
    cmd = ["gh", "release", "create", tag, "--prerelease",
           "--title", title or f"{tag} (submitted to CRAN)"]
    if notes_file:
        cmd += ["--notes-file", notes_file]
    else:
        cmd += ["--notes", f"{tag} — submitted to CRAN, pending review."]
    if repo:
        cmd += ["--repo", repo]
    if tarball:
        cmd.append(tarball)
    return cmd


def promote_cmd(version: str, *, repo: Optional[str] = None) -> list[str]:
    """Build ``gh release edit`` that promotes the pre-release to a full release."""
    tag = submission_tag(version)
    cmd = ["gh", "release", "edit", tag, "--prerelease=false", "--latest"]
    if repo:
        cmd += ["--repo", repo]
    return cmd


def manual_recipe(version: str, tarball: Optional[str] = None, *,
                  notes_file: Optional[str] = None) -> str:
    """Printed fallback when ``gh`` is unavailable/unauthed — the manual steps."""
    create = " ".join(prerelease_cmd(version, tarball, notes_file=notes_file))
    promote = " ".join(promote_cmd(version))
    return (
        "# gh CLI not available — run manually after `gh auth login`:\n"
        f"{create}\n"
        "# … submit to CRAN, then on acceptance:\n"
        f"{promote}"
    )

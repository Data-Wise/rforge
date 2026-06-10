"""Tests for lib/ghrelease.py — gh command construction for r:submit.

Covers SPEC-r-submit-github-prerelease-2026-06-10: pre-release create + promote
command shapes, tag normalization, and the gh-absent manual recipe. No GitHub
side effects — these are pure command builders.
"""

from __future__ import annotations

from lib import ghrelease


def test_submission_tag_normalizes():
    assert ghrelease.submission_tag("0.2.1") == "v0.2.1"
    assert ghrelease.submission_tag("v0.2.1") == "v0.2.1"
    assert ghrelease.submission_tag("  V1.0.0 ") == "v1.0.0"


def test_prerelease_cmd_shape():
    cmd = ghrelease.prerelease_cmd("0.2.1", "demo_0.2.1.tar.gz",
                                   notes_file="cran-comments.md")
    assert cmd[:4] == ["gh", "release", "create", "v0.2.1"]
    assert "--prerelease" in cmd
    assert "--notes-file" in cmd and "cran-comments.md" in cmd
    assert cmd[-1] == "demo_0.2.1.tar.gz"  # asset last
    # never promotes / marks latest at create time
    assert "--latest" not in cmd
    assert "--prerelease=false" not in cmd


def test_prerelease_cmd_without_notes_file_uses_inline_notes():
    cmd = ghrelease.prerelease_cmd("1.0.0")
    assert "--notes" in cmd
    assert "--notes-file" not in cmd


def test_promote_cmd_shape():
    cmd = ghrelease.promote_cmd("0.2.1")
    assert cmd == ["gh", "release", "edit", "v0.2.1", "--prerelease=false", "--latest"]


def test_repo_flag_threaded():
    assert "--repo" in ghrelease.prerelease_cmd("1.0.0", repo="Data-Wise/medfit")
    assert "Data-Wise/medfit" in ghrelease.promote_cmd("1.0.0", repo="Data-Wise/medfit")


def test_gh_available_returns_bool():
    assert isinstance(ghrelease.gh_available(), bool)


def test_manual_recipe_contains_both_steps():
    recipe = ghrelease.manual_recipe("0.2.1", "demo.tar.gz", notes_file="cran-comments.md")
    assert "gh release create v0.2.1 --prerelease" in recipe
    assert "gh release edit v0.2.1 --prerelease=false --latest" in recipe

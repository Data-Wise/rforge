"""Tests for lib.changed — git-diff-scoped check helpers.

git is mocked via subprocess so tests are hermetic (no real repo needed),
except the file→package mapping test, which builds a tmp fixture ecosystem.
"""
from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from lib import changed


# ───────── changed_files: git invocation ─────────

def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode,
                                       stdout=stdout, stderr="")


def test_changed_files_committed_diff_against_merge_base():
    """Default: diff merge-base(HEAD, base)..HEAD, name-only."""
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("/repo\n")            # is-inside-work-tree root
        if cmd[:2] == ["git", "merge-base"]:
            return _completed("abc123\n")
        if "diff" in cmd:
            return _completed("pkgA/R/x.R\npkgB/DESCRIPTION\n")
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        files = changed.changed_files(path="/repo", base="dev")

    assert files == ["pkgA/R/x.R", "pkgB/DESCRIPTION"]
    # the diff must be scoped to the merge-base, committed + uncommitted
    diff_cmd = next(c for c in calls if "diff" in c)
    assert "abc123" in diff_cmd            # merge-base sha, not raw base
    assert "--name-only" in diff_cmd


def test_changed_files_not_a_git_repo_returns_marker():
    """Outside a git repo: no raise; return None so callers can warn + fall back."""
    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("", returncode=128)   # fatal: not a git repository
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        assert changed.changed_files(path="/tmp/not-a-repo", base="dev") is None


def test_changed_files_no_merge_base_returns_marker():
    """Unrelated histories / bad base: merge-base fails → None (caller falls back)."""
    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("/repo\n")
        if cmd[:2] == ["git", "merge-base"]:
            return _completed("", returncode=1)
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        assert changed.changed_files(path="/repo", base="nonexistent") is None


def test_changed_files_empty_diff_returns_empty_list():
    """No changes is distinct from no-repo: empty list, not None."""
    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("/repo\n")
        if cmd[:2] == ["git", "merge-base"]:
            return _completed("abc\n")
        if "diff" in cmd:
            return _completed("")
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        assert changed.changed_files(path="/repo", base="dev") == []


def test_changed_files_git_missing_returns_marker():
    """git binary absent → None, never an exception."""
    with mock.patch.object(changed.subprocess, "run",
                           side_effect=FileNotFoundError("git")):
        assert changed.changed_files(path="/repo", base="dev") is None


# ───────── changed_packages: file → owning package ─────────

def _mk_pkg(root, name):
    d = root / name
    d.mkdir(parents=True)
    (d / "DESCRIPTION").write_text(
        f"Package: {name}\nVersion: 0.1.0\nTitle: T\n", encoding="utf-8")
    (d / "R").mkdir()
    return d


def test_changed_packages_maps_files_to_owning_packages(tmp_path):
    _mk_pkg(tmp_path, "pkgA")
    _mk_pkg(tmp_path, "pkgB")
    files = ["pkgA/R/x.R", "pkgA/tests/testthat/test-x.R", "pkgB/DESCRIPTION"]
    pkgs = changed.changed_packages(files, root=str(tmp_path))
    names = {p.name for p in pkgs}
    assert names == {"pkgA", "pkgB"}
    # each returned package carries its on-disk path (for rcmd --path)
    assert all(p.path for p in pkgs)


def test_changed_packages_ignores_files_outside_any_package(tmp_path):
    _mk_pkg(tmp_path, "pkgA")
    files = ["pkgA/R/x.R", "README.md", "docs/notes.md"]  # last two own no pkg
    pkgs = changed.changed_packages(files, root=str(tmp_path))
    assert {p.name for p in pkgs} == {"pkgA"}


def test_changed_packages_empty_when_no_files(tmp_path):
    _mk_pkg(tmp_path, "pkgA")
    assert changed.changed_packages([], root=str(tmp_path)) == []


def test_changed_packages_single_package_repo(tmp_path):
    """Single-package layout: root itself is the package; any R/ edit maps to it."""
    (tmp_path / "DESCRIPTION").write_text(
        "Package: solo\nVersion: 1.0.0\nTitle: T\n", encoding="utf-8")
    (tmp_path / "R").mkdir()
    pkgs = changed.changed_packages(["R/core.R"], root=str(tmp_path))
    assert {p.name for p in pkgs} == {"solo"}


# ───────── tag_findings: introduced vs pre-existing ─────────

def test_tag_findings_splits_introduced_and_pre_existing():
    head = ["NOTE: foo", "WARNING: bar", "NOTE: baz"]
    base = ["NOTE: baz"]  # baz pre-existed on the base
    tagged = changed.tag_findings(head_findings=head, base_findings=base)
    intro = [t["text"] for t in tagged if t["tag"] == "introduced"]
    pre = [t["text"] for t in tagged if t["tag"] == "pre-existing"]
    assert intro == ["NOTE: foo", "WARNING: bar"]
    assert pre == ["NOTE: baz"]


def test_tag_findings_all_pre_existing_when_base_equals_head():
    f = ["NOTE: foo", "WARNING: bar"]
    tagged = changed.tag_findings(head_findings=f, base_findings=list(f))
    assert all(t["tag"] == "pre-existing" for t in tagged)


def test_tag_findings_preserves_duplicates_by_count():
    """Two identical findings on HEAD, one on base → one introduced, one pre-existing."""
    head = ["NOTE: dup", "NOTE: dup"]
    base = ["NOTE: dup"]
    tags = sorted(t["tag"] for t in changed.tag_findings(head_findings=head,
                                                         base_findings=base))
    assert tags == ["introduced", "pre-existing"]


def test_tag_findings_empty_head_returns_empty():
    assert changed.tag_findings(head_findings=[], base_findings=["NOTE: x"]) == []

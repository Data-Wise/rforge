"""Tests for lib.changed — git-diff-scoped check helpers.

git is mocked via subprocess so tests are hermetic (no real repo needed),
except the file→package mapping test, which builds a tmp fixture ecosystem.

The merge_base / run_baseline / scope_check tests deliberately use a REAL
temporary git repo (commits made with subprocess git) — NOT mocked git. A
mocked baseline run is exactly what hid the v2.10.0 false-negative (compared
HEAD against HEAD), so these tests exercise genuine worktrees/checkouts.
"""
from __future__ import annotations

import os
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


# ───────── REAL-GIT fixtures for merge_base / run_baseline / scope_check ─────────


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          check=True)


def _init_repo(root):
    """A real git repo with a `dev` base commit and a `feature/x` branch commit.

    Returns (repo_path, base_sha). The repo contains one tracked file `f.txt`
    that differs between the base (on `dev`) and the branch tip (checked out).
    """
    _git(["init", "-q"], cwd=root)
    _git(["config", "user.email", "t@t.t"], cwd=root)
    _git(["config", "user.name", "T"], cwd=root)
    _git(["checkout", "-q", "-b", "dev"], cwd=root)
    (root / "f.txt").write_text("base\n", encoding="utf-8")
    _git(["add", "f.txt"], cwd=root)
    _git(["commit", "-q", "-m", "base"], cwd=root)
    base_sha = _git(["rev-parse", "HEAD"], cwd=root).stdout.strip()
    _git(["checkout", "-q", "-b", "feature/x"], cwd=root)
    (root / "f.txt").write_text("branch\n", encoding="utf-8")
    _git(["add", "f.txt"], cwd=root)
    _git(["commit", "-q", "-m", "branch"], cwd=root)
    return root, base_sha


# ───────── merge_base ─────────


def test_merge_base_resolves_fork_point(tmp_path):
    repo, base_sha = _init_repo(tmp_path)
    assert changed.merge_base(path=str(repo), base="dev") == base_sha


def test_merge_base_none_when_not_a_repo(tmp_path):
    assert changed.merge_base(path=str(tmp_path), base="dev") is None


def test_merge_base_none_for_unknown_base(tmp_path):
    repo, _ = _init_repo(tmp_path)
    assert changed.merge_base(path=str(repo), base="no-such-branch") is None


# ───────── run_baseline: detached worktree, guaranteed cleanup ─────────


def _wt_count(repo):
    out = _git(["worktree", "list"], cwd=repo).stdout
    return len([ln for ln in out.splitlines() if ln.strip()])


def test_run_baseline_runs_runner_at_base_sha_and_cleans_up(tmp_path):
    """Runner is invoked in a tree whose f.txt holds the BASE content, and no
    worktree is leaked afterward."""
    repo, base_sha = _init_repo(tmp_path)
    before = _wt_count(repo)
    seen = {}

    def runner(treedir):
        # Prove the baseline tree is genuinely the base commit, not HEAD.
        seen["content"] = (os.path.join(treedir, "f.txt"))
        with open(seen["content"], encoding="utf-8") as fh:
            seen["text"] = fh.read()
        return ["finding-from-base"]

    out = changed.run_baseline(path=str(repo), base_sha=base_sha, runner=runner)
    assert out == ["finding-from-base"]
    assert seen["text"] == "base\n"            # NOT "branch\n" — real checkout
    assert _wt_count(repo) == before           # no leaked worktree


def test_run_baseline_cleans_up_even_when_runner_raises(tmp_path):
    repo, base_sha = _init_repo(tmp_path)
    before = _wt_count(repo)

    def boom(treedir):
        raise RuntimeError("inner run failed")

    with pytest.raises(RuntimeError):
        changed.run_baseline(path=str(repo), base_sha=base_sha, runner=boom)
    assert _wt_count(repo) == before           # finally cleaned up despite raise


def test_run_baseline_none_when_worktree_add_fails(tmp_path):
    repo, _ = _init_repo(tmp_path)
    out = changed.run_baseline(path=str(repo), base_sha="deadbeef" * 5,
                               runner=lambda d: ["x"])
    assert out is None


# ───────── scope_check: full two-run tagging over a real repo ─────────


def test_scope_check_tags_introduced_and_pre_existing(tmp_path):
    """HEAD has two findings; base has one of them → one introduced, one pre-existing."""
    repo, _ = _init_repo(tmp_path)

    def run_check(treedir):
        with open(os.path.join(treedir, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        if txt == "branch":
            return ["NOTE: old", "NOTE: new"]   # HEAD findings
        return ["NOTE: old"]                    # base findings

    result = changed.scope_check(run_check, path=str(repo), base="dev")
    assert result is not None
    tags = {t["text"]: t["tag"] for t in result["findings"]}
    assert tags == {"NOTE: old": "pre-existing", "NOTE: new": "introduced"}
    assert result["introduced_count"] == 1
    assert result["merge_base"]


def test_scope_check_none_when_no_merge_base(tmp_path):
    """Falls back (None) when base does not resolve — caller goes scope-only."""
    repo, _ = _init_repo(tmp_path)
    assert changed.scope_check(lambda d: [], path=str(repo),
                               base="no-such-branch") is None

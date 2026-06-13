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


# ── IMPORTANT 4 regression: dict (lint) findings tagged by stable identity ──

def test_tag_findings_lint_line_shift_stays_pre_existing():
    """A pre-existing lint that moved (blank line inserted above) must NOT flip
    to [introduced]. Identity excludes the raw `line`."""
    base = [{"file": "R/a.R", "line": 10, "linter": "object_usage_linter",
             "message": "no visible binding for 'x'"}]
    # same lint on HEAD, but the line shifted 10 -> 11 (an unrelated edit above)
    head = [{"file": "R/a.R", "line": 11, "linter": "object_usage_linter",
             "message": "no visible binding for 'x'"}]
    tagged = changed.tag_findings(head_findings=head, base_findings=base)
    assert [t["tag"] for t in tagged] == ["pre-existing"]
    # the full finding (with its real, shifted line) is still carried for display
    assert tagged[0]["text"]["line"] == 11


def test_tag_findings_lint_genuinely_new_is_introduced():
    """A lint with a different message IS a new finding even if line/file match."""
    base = [{"file": "R/a.R", "line": 10, "linter": "object_usage_linter",
             "message": "no visible binding for 'x'"}]
    head = [{"file": "R/a.R", "line": 10, "linter": "object_usage_linter",
             "message": "no visible binding for 'x'"},
            {"file": "R/a.R", "line": 12, "linter": "seq_linter",
             "message": "use seq_len()"}]
    tagged = changed.tag_findings(head_findings=head, base_findings=base)
    tags = {t["text"]["message"]: t["tag"] for t in tagged}
    assert tags == {"no visible binding for 'x'": "pre-existing",
                    "use seq_len()": "introduced"}


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


def test_scope_check_line_shifted_lint_tagged_pre_existing(tmp_path):
    """End-to-end (IMPORTANT 4): a pre-existing lint whose line shifted on the
    branch must be tagged [pre-existing] through scope_check, not [introduced]."""
    repo, _ = _init_repo(tmp_path)

    def run_lint(treedir):
        with open(os.path.join(treedir, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        # The lint is the SAME content on both trees; only `line` differs (a
        # blank line was inserted above it on the branch).
        line = 11 if txt == "branch" else 10
        return [{"file": "R/a.R", "line": line, "linter": "object_usage_linter",
                 "message": "no visible binding for 'x'"}]

    result = changed.scope_check(run_lint, path=str(repo), base="dev")
    assert result is not None
    assert [t["tag"] for t in result["findings"]] == ["pre-existing"]
    assert result["introduced_count"] == 0


# ───────── uncommitted_files (v2.12.0): git status --porcelain ─────────


def test_uncommitted_files_reports_modified_staged_and_added(tmp_path):
    """Returns the working-tree-dirty paths: modified, staged, and new/added."""
    repo, _ = _init_repo(tmp_path)
    # tracked file modified but NOT committed
    (repo / "f.txt").write_text("dirty\n", encoding="utf-8")
    # a brand-new untracked file
    (repo / "new.R").write_text("x <- 1\n", encoding="utf-8")
    # a staged-but-uncommitted file
    (repo / "staged.R").write_text("y <- 2\n", encoding="utf-8")
    _git(["add", "staged.R"], cwd=repo)

    files = changed.uncommitted_files(path=str(repo))
    assert "f.txt" in files          # modified, unstaged
    assert "new.R" in files          # untracked/added
    assert "staged.R" in files       # staged


def test_uncommitted_files_handles_spaced_and_nonascii_paths(tmp_path):
    """MINOR (feature 2): `git status --porcelain` quotes paths with spaces /
    non-ASCII, leaving literal quotes that never exact-match. With `-z` the path
    is NUL-separated and never quoted, so it survives verbatim."""
    repo, _ = _init_repo(tmp_path)
    # Commit a file in R/ first so R/ is a tracked dir → git reports new files
    # under it individually (not as a single collapsed `R/` untracked entry).
    (repo / "R").mkdir()
    (repo / "R" / "keep.R").write_text("k <- 0\n", encoding="utf-8")
    _git(["add", "R/keep.R"], cwd=repo)
    _git(["commit", "-q", "-m", "seed R dir"], cwd=repo)
    spaced = repo / "R" / "my util.R"
    spaced.write_text("x <- 1\n", encoding="utf-8")
    nonascii = repo / "R" / "café.R"
    nonascii.write_text("y <- 2\n", encoding="utf-8")

    files = changed.uncommitted_files(path=str(repo))
    # Exact, unquoted, repo-relative — would be '"R/my util.R"' without -z.
    assert "R/my util.R" in files
    assert "R/café.R" in files


def test_uncommitted_files_empty_on_clean_tree(tmp_path):
    repo, _ = _init_repo(tmp_path)
    assert changed.uncommitted_files(path=str(repo)) == set()


def test_uncommitted_files_empty_on_non_repo_no_raise(tmp_path):
    """Advisory: a non-repo path → empty set, never an exception."""
    assert changed.uncommitted_files(path=str(tmp_path)) == set()


def test_uncommitted_files_empty_when_git_missing(tmp_path):
    with mock.patch.object(changed.subprocess, "run",
                           side_effect=FileNotFoundError("git")):
        assert changed.uncommitted_files(path=str(tmp_path)) == set()


# ───────── scope_check [uncommitted] refinement (v2.12.0, REAL git) ─────────


def test_scope_check_retags_introduced_in_uncommitted_file(tmp_path):
    """KEY e2e: an introduced finding in a COMMITTED file stays [introduced];
    an introduced finding in an UNCOMMITTED (dirty, not committed) file is
    re-tagged [uncommitted]; a pre-existing finding stays [pre-existing].
    No mocking of git — real repo + real `git status --porcelain`."""
    repo, _ = _init_repo(tmp_path)
    # On the branch: commit a finding-file (R/committed.R), then dirty another
    # file (R/dirty.R) WITHOUT committing it.
    (repo / "R").mkdir()
    (repo / "R" / "committed.R").write_text("a <- 1\n", encoding="utf-8")
    _git(["add", "R/committed.R"], cwd=repo)
    _git(["commit", "-q", "-m", "add committed finding file"], cwd=repo)
    # dirty file: present in the working tree, uncommitted
    (repo / "R" / "dirty.R").write_text("b <- 2\n", encoding="utf-8")

    def run_engine(treedir):
        with open(os.path.join(treedir, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        if txt == "branch":  # HEAD tree
            return [
                {"file": "R/committed.R", "line": 1, "linter": "L",
                 "message": "introduced-committed"},
                {"file": "R/dirty.R", "line": 1, "linter": "L",
                 "message": "introduced-uncommitted"},
                {"file": "R/old.R", "line": 1, "linter": "L",
                 "message": "preexisting"},
            ]
        # baseline tree: only the pre-existing finding
        return [{"file": "R/old.R", "line": 1, "linter": "L",
                 "message": "preexisting"}]

    result = changed.scope_check(run_engine, path=str(repo), base="dev")
    assert result is not None
    tags = {t["text"]["message"]: t["tag"] for t in result["findings"]}
    assert tags == {
        "introduced-committed": "introduced",
        "introduced-uncommitted": "uncommitted",
        "preexisting": "pre-existing",
    }
    # [uncommitted] counts as introduced for the introduced_count.
    assert result["introduced_count"] == 2


def test_scope_check_string_finding_never_uncommitted(tmp_path):
    """String findings (R CMD check, no file attribute) stay [introduced] even
    when the tree is dirty — no file to attribute to an uncommitted path."""
    repo, _ = _init_repo(tmp_path)
    (repo / "R").mkdir()
    (repo / "R" / "dirty.R").write_text("z <- 1\n", encoding="utf-8")  # dirty tree

    def run_check(treedir):
        with open(os.path.join(treedir, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        if txt == "branch":
            return ["NOTE: new string finding"]
        return []

    result = changed.scope_check(run_check, path=str(repo), base="dev")
    assert result is not None
    assert [t["tag"] for t in result["findings"]] == ["introduced"]


def test_scope_check_clean_tree_no_uncommitted_tags(tmp_path):
    """No v2.11 regression: a clean working tree yields zero [uncommitted] tags;
    an introduced finding stays [introduced]."""
    repo, _ = _init_repo(tmp_path)

    def run_engine(treedir):
        with open(os.path.join(treedir, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        if txt == "branch":
            return [{"file": "R/a.R", "line": 1, "linter": "L",
                     "message": "new"}]
        return []

    result = changed.scope_check(run_engine, path=str(repo), base="dev")
    assert result is not None
    tags = [t["tag"] for t in result["findings"]]
    assert "uncommitted" not in tags
    assert tags == ["introduced"]


# ───────── BLOCKER: cross-package basename collision (v2.12.0 fix) ─────────


def _write_pkg(root, name):
    """Minimal R package skeleton under root/<name> with R/ dir."""
    pkg = root / name
    (pkg / "R").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text(
        f"Package: {name}\nVersion: 0.0.1\n", encoding="utf-8")
    return pkg


def test_scope_check_no_cross_package_basename_collision(tmp_path):
    """REGRESSION (BLOCKER): two packages share a basename. pkgA/R/util.dat is
    dirty+uncommitted; pkgB/R/util.dat is committed clean. A pkgB finding must
    stay [introduced]; a pkgA finding must become [uncommitted]. The old
    basename/suffix match wrongly re-tagged the pkgB finding [uncommitted]
    because both files end in `util.dat` (same basename)."""
    repo, _ = _init_repo(tmp_path)
    # Two sibling packages, both with an R/util.dat.
    _write_pkg(repo, "pkgA")
    _write_pkg(repo, "pkgB")
    (repo / "pkgA" / "R" / "util.dat").write_text("a\n", encoding="utf-8")
    (repo / "pkgB" / "R" / "util.dat").write_text("b\n", encoding="utf-8")
    # Commit BOTH packages clean on the branch.
    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-q", "-m", "add two packages"], cwd=repo)
    # Now dirty ONLY pkgA/R/util.dat (uncommitted). pkgB stays committed clean.
    (repo / "pkgA" / "R" / "util.dat").write_text("a-dirty\n", encoding="utf-8")

    # rel package dirs as rcmd computes them, in discovery order.
    pkgs = changed.changed_packages(
        changed.changed_files(path=str(repo), base="dev") or [], root=str(repo))
    rel_pkgs = {p.name: str(p.path) for p in pkgs}

    def runner(tree_root):
        with open(os.path.join(tree_root, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        if txt != "branch":
            return []  # baseline: nothing → both findings are introduced
        # HEAD: one finding per package, BOTH named R/util.dat (package-relative).
        # Annotate the owning package's repo-relative dir so scope_check can
        # rebase to repo-relative coordinates and exact-match.
        return [
            {"file": "R/util.dat", "line": 1, "linter": "L",
             "message": "finding-in-pkgA", "pkg_dir": "pkgA"},
            {"file": "R/util.dat", "line": 1, "linter": "L",
             "message": "finding-in-pkgB", "pkg_dir": "pkgB"},
        ]

    result = changed.scope_check(runner, path=str(repo), base="dev")
    assert result is not None
    tags = {t["text"]["message"]: t["tag"] for t in result["findings"]}
    # pkgA's file is dirty → uncommitted. pkgB's identical-basename file is
    # committed clean → must NOT collide; stays introduced.
    assert tags["finding-in-pkgA"] == "uncommitted"
    assert tags["finding-in-pkgB"] == "introduced", (
        "cross-package basename collision: pkgB finding wrongly re-tagged")


# ───────── baseline caching (candidate A, v2.13.0) ─────────
#
# The baseline run is a pure function of (merge_base_sha, kind, package-set,
# kwargs). `scope_check` accepts an opaque `cache_key` (rcmd builds it from
# kind+pkgset+kwargs) and caches the baseline finding list under
# ~/.rforge/baseline-cache/<repo-id>/<sha>-<keyhash>.json. The tests below
# monkeypatch `_cache_root` so they never touch the real ~/.rforge.


@pytest.fixture()
def cache_root(tmp_path, monkeypatch):
    root = tmp_path / "bcache"
    monkeypatch.setattr(changed, "_cache_root", lambda: root)
    return root


def test_baseline_cache_write_then_read_roundtrip(tmp_path, cache_root):
    findings = ["NOTE: a", {"file": "R/x.R", "line": 3, "linter": "L",
                            "message": "m"}]
    changed.write_baseline_cache(str(tmp_path), "deadbeef", "check|.|{}", findings)
    got = changed.read_baseline_cache(str(tmp_path), "deadbeef", "check|.|{}")
    assert got == findings


def test_baseline_cache_miss_on_different_sha(tmp_path, cache_root):
    changed.write_baseline_cache(str(tmp_path), "sha1", "k", ["x"])
    assert changed.read_baseline_cache(str(tmp_path), "sha2", "k") is None


def test_baseline_cache_miss_on_different_key(tmp_path, cache_root):
    changed.write_baseline_cache(str(tmp_path), "sha1", "k1", ["x"])
    assert changed.read_baseline_cache(str(tmp_path), "sha1", "k2") is None


def test_baseline_cache_miss_when_absent(tmp_path, cache_root):
    assert changed.read_baseline_cache(str(tmp_path), "nope", "k") is None


def test_baseline_cache_corrupt_file_is_miss(tmp_path, cache_root):
    changed.write_baseline_cache(str(tmp_path), "sha1", "k", ["x"])
    # Corrupt the on-disk JSON.
    f = changed._cache_file(str(tmp_path), "sha1", "k")
    f.write_text("{not json", encoding="utf-8")
    assert changed.read_baseline_cache(str(tmp_path), "sha1", "k") is None


def test_baseline_cache_prune_keeps_newest(tmp_path, cache_root):
    import os as _os
    import time as _time
    # Write 5 distinct entries (same repo) with keep=3; the 2 oldest go.
    for i in range(5):
        changed.write_baseline_cache(str(tmp_path), f"sha{i}", "k", [i], keep=3)
        # Stagger mtimes so "newest" is well-defined.
        f = changed._cache_file(str(tmp_path), f"sha{i}", "k")
        _os.utime(f, (1_000 + i, 1_000 + i))
    # Re-prune to settle (last write used the staggered times above).
    changed.write_baseline_cache(str(tmp_path), "sha4", "k", [4], keep=3)
    repo_dir = changed._cache_file(str(tmp_path), "sha4", "k").parent
    remaining = sorted(p.name for p in repo_dir.glob("*.json"))
    assert len(remaining) == 3


def test_clear_baseline_cache_removes_and_counts(tmp_path, cache_root):
    changed.write_baseline_cache(str(tmp_path), "sha1", "k1", ["x"])
    changed.write_baseline_cache(str(tmp_path), "sha2", "k2", ["y"])
    n = changed.clear_baseline_cache(str(tmp_path))
    assert n == 2
    assert changed.read_baseline_cache(str(tmp_path), "sha1", "k1") is None


def test_repo_id_stable_and_distinct(tmp_path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    assert changed._repo_id(str(a)) == changed._repo_id(str(a))
    assert changed._repo_id(str(a)) != changed._repo_id(str(b))


def test_cached_baseline_partial_hit_runs_only_uncached(tmp_path, cache_root):
    """Per-package granularity (candidate-A step 2): caching pkgA's baseline, then
    requesting [pkgA, pkgB], reuses pkgA from cache and runs ONLY pkgB — the
    growing changed-set case that ecosystem cascade work hits."""
    repo, base_sha = _init_repo(tmp_path)
    ran = []

    def run_item(tree_root, rel):
        ran.append(rel)
        return [f"NOTE: {rel}"]

    def key_item(rel):
        return f"check|{rel}|{{}}"

    out1 = changed.cached_baseline(str(repo), base_sha, ["pkgA"], run_item, key_item)
    assert out1 == ["NOTE: pkgA"]
    assert ran == ["pkgA"]

    ran.clear()
    out2 = changed.cached_baseline(str(repo), base_sha, ["pkgA", "pkgB"],
                                   run_item, key_item)
    assert out2 == ["NOTE: pkgA", "NOTE: pkgB"]  # combined, in item order
    assert ran == ["pkgB"]  # pkgA reused from cache, NOT re-run


def test_cached_baseline_all_hits_skip_run(tmp_path, cache_root):
    """When every item is cached, run_item is never called (no worktree)."""
    repo, base_sha = _init_repo(tmp_path)
    ran = []

    def run_item(tree_root, rel):
        ran.append(rel)
        return [rel]

    key_item = lambda rel: f"k|{rel}"
    changed.cached_baseline(str(repo), base_sha, ["a", "b"], run_item, key_item)
    ran.clear()
    out = changed.cached_baseline(str(repo), base_sha, ["a", "b"], run_item, key_item)
    assert out == ["a", "b"]
    assert ran == []  # all cache hits → no run, no worktree


def test_cached_baseline_use_cache_false_never_caches(tmp_path, cache_root):
    repo, base_sha = _init_repo(tmp_path)
    ran = []

    def run_item(tree_root, rel):
        ran.append(rel)
        return [rel]

    key_item = lambda rel: f"k|{rel}"
    changed.cached_baseline(str(repo), base_sha, ["a"], run_item, key_item,
                            use_cache=False)
    changed.cached_baseline(str(repo), base_sha, ["a"], run_item, key_item,
                            use_cache=False)
    assert ran == ["a", "a"]  # ran both times, never cached
    assert changed.read_baseline_cache(str(repo), base_sha, "k|a") is None


def test_cached_baseline_none_when_worktree_add_fails(tmp_path, cache_root):
    """Not a git repo → worktree add fails → None (caller falls back), and
    run_item is never invoked."""
    ran = []

    def run_item(tree_root, rel):
        ran.append(rel)
        return [rel]

    out = changed.cached_baseline(str(tmp_path), "deadbeef", ["a"],
                                  run_item, lambda r: f"k|{r}")
    assert out is None
    assert ran == []


def test_scope_check_uses_injected_baseline(tmp_path, cache_root):
    """scope_check delegates baseline acquisition to the injected callable and
    tags the always-fresh HEAD run against whatever it returns."""
    repo, _ = _init_repo(tmp_path)
    res = changed.scope_check(
        lambda treedir: ["NOTE: old", "NOTE: new"],   # HEAD findings
        path=str(repo), base="dev",
        baseline=lambda p, sha: ["NOTE: old"],         # injected baseline
    )
    assert res is not None
    tags = {t["text"]: t["tag"] for t in res["findings"]}
    assert tags == {"NOTE: old": "pre-existing", "NOTE: new": "introduced"}


def test_scope_check_baseline_none_falls_back(tmp_path, cache_root):
    """A baseline callable returning None → scope_check returns None (caller falls
    back to scope-only), same as a failed worktree add."""
    repo, _ = _init_repo(tmp_path)
    res = changed.scope_check(lambda d: ["x"], path=str(repo), base="dev",
                              baseline=lambda p, sha: None)
    assert res is None


def test_scope_check_default_baseline_is_uncached(tmp_path, cache_root):
    """No baseline callable → scope_check uses run_baseline directly (uncached):
    the baseline runs on every call (no caching without an injected baseline)."""
    repo, _ = _init_repo(tmp_path)
    seen = []

    def runner(treedir):
        with open(os.path.join(treedir, "f.txt"), encoding="utf-8") as fh:
            txt = fh.read().strip()
        seen.append(txt)
        return ["NOTE: old"] if txt == "base" else ["NOTE: old", "NOTE: new"]

    changed.scope_check(runner, path=str(repo), base="dev")
    changed.scope_check(runner, path=str(repo), base="dev")
    assert seen.count("base") == 2  # baseline re-ran (uncached) both times


def test_changed_cli_clear_cache(tmp_path, cache_root, capsys):
    repo, _ = _init_repo(tmp_path)
    changed.write_baseline_cache(str(repo), "sha1", "k", ["x"])
    rc = changed._main(["--path", str(repo), "--clear-cache"])
    assert rc == 0
    assert changed.read_baseline_cache(str(repo), "sha1", "k") is None


def test_scope_check_dict_findings_hit_equals_miss(tmp_path, cache_root):
    """A per-package cache HIT must yield byte-for-byte the same tagging as a
    fresh MISS, including dict (lint) findings that round-trip through JSON.
    Guards hit/miss equivalence against future _finding_identity changes (the
    string-finding path is covered by the cached_baseline tests above)."""
    repo, _ = _init_repo(tmp_path)
    base = {"file": "R/a.R", "line": 5, "linter": "L",
            "message": "pre-existing", "pkg_dir": "."}

    def run_item(tree_root, rel):                  # baseline: one package "."
        return [base]

    def runner(treedir):                           # HEAD: shifted + new
        return [{**base, "line": 7},
                {"file": "R/a.R", "line": 9, "linter": "L",
                 "message": "introduced", "pkg_dir": "."}]

    def mk_baseline():
        return lambda p, sha: changed.cached_baseline(
            p, sha, ["."], run_item, lambda rel: "lint|.|{}")

    miss = changed.scope_check(runner, path=str(repo), base="dev",
                               baseline=mk_baseline())   # writes the baseline
    hit = changed.scope_check(runner, path=str(repo), base="dev",
                              baseline=mk_baseline())     # reads it back via JSON
    assert miss == hit  # JSON round-trip of the cached baseline is transparent
    tags = {t["text"]["message"]: t["tag"] for t in hit["findings"]}
    assert tags == {"pre-existing": "pre-existing", "introduced": "introduced"}
    assert hit["introduced_count"] == 1


def test_cache_never_raises_on_unresolvable_home(tmp_path, monkeypatch):
    """BLOCKER regression: Path.home() raises RuntimeError (a non-OSError) when
    HOME is unset AND the uid has no passwd entry (containers / scratch CI users).
    _cache_root must fall back to the temp dir, and no public cache op may raise —
    the advisory 'never raises' contract has to hold through the weird-HOME path
    (previously this aborted r:check --changed with a traceback)."""
    monkeypatch.delenv("HOME", raising=False)
    monkeypatch.setattr(os.path, "expanduser", lambda p: p)  # unresolvable → "~"
    monkeypatch.setattr(changed.tempfile, "gettempdir",
                        lambda: str(tmp_path / "fallback"))
    root = changed._cache_root()
    assert root == tmp_path / "fallback" / ".rforge" / "baseline-cache"
    # The three public ops must complete without raising (the regression).
    changed.write_baseline_cache(str(tmp_path), "sha", "k", ["x"])
    assert changed.read_baseline_cache(str(tmp_path), "sha", "k") == ["x"]
    assert changed.clear_baseline_cache(str(tmp_path)) >= 0

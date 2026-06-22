"""Tests for the clean-ref pkgdown deploy path (lib.rcmd._run_deploy, issue #52).

This path is MUTATING + NETWORK (pkgdown::deploy_to_branch pushes to gh-pages),
so the actual deploy is ALWAYS mocked at the `rcmd._invoke_r` boundary — exactly
how tests/test_rcmd_rhub.py mocks the R call. We never perform a real push.

The load-bearing assertion (the actual proof of #52) is the worktree one:
after the gate passes, the materialized detached-HEAD worktree contains the
committed scratch file but NOT the untracked one — i.e. untracked files are
structurally excluded. The worktree (vs `git archive`) is mandatory because
deploy_to_branch drives the package's own git repo+remote, which an archived
tempdir lacks.
"""
import subprocess
from pathlib import Path

import lib.rcmd as rcmd


# ───────────────────────── fixtures ─────────────────────────


def _run_git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def _make_pkg_repo(tmp_path, *, scratch_tracked=True, allowlist=None):
    """A real git repo R package: DESCRIPTION + README.md + (tracked) PLAN-scratch.md,
    plus an UNTRACKED NOTES.md. Returns the repo path."""
    repo = tmp_path / "pkg"
    repo.mkdir()
    (repo / "DESCRIPTION").write_text("Package: demo\nVersion: 0.0.1\n")
    (repo / "README.md").write_text("# demo\n")
    (repo / "PLAN-scratch.md").write_text("scratch plan\n")
    if allowlist is not None:
        lines = "\n".join(f"    - {a}" for a in allowlist)
        (repo / ".rforge.yaml").write_text(f"site:\n  allowlist:\n{lines}\n")
    _run_git(repo, "init", "-q")
    _run_git(repo, "config", "user.email", "t@t.io")
    _run_git(repo, "config", "user.name", "t")
    _run_git(repo, "add", "DESCRIPTION", "README.md")
    if scratch_tracked:
        _run_git(repo, "add", "PLAN-scratch.md")
    if allowlist is not None:
        _run_git(repo, "add", ".rforge.yaml")
    _run_git(repo, "commit", "-q", "-m", "init")
    # untracked file present in the working dir but never committed
    (repo / "NOTES.md").write_text("scratch notes\n")
    if not scratch_tracked:
        # leave PLAN-scratch.md untracked as well
        pass
    return repo


def _mock_deploy_ok(monkeypatch):
    """Mock the R deploy call; record whether it was invoked + the snippet seen."""
    calls = []

    def fake(snippet, *a, **k):
        calls.append(snippet)
        return ('{"deployed":true,"branch":"gh-pages"}', 0)

    monkeypatch.setattr(rcmd, "_invoke_r", fake)
    return calls


# ───────────────────────── gate: abort vs --force ─────────────────────────


def test_gate_blocks_on_tracked_scratch(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True)
    calls = _mock_deploy_ok(monkeypatch)
    env = rcmd.run("deploy", str(repo))
    assert env["status"] == "blocked"
    assert any("PLAN-scratch.md" in f["file"] for f in env["blockers"])
    # deploy must NOT have been attempted
    assert calls == []
    assert env["deployed"] is False


def test_force_downgrades_block_and_proceeds(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True)
    calls = _mock_deploy_ok(monkeypatch)
    env = rcmd.run("deploy", str(repo), force=True)
    # forced override → not blocked; deploy ran
    assert env["status"] == "warn"  # forced success surfaces as warn
    assert env["forced"] is True
    assert len(calls) == 1
    assert any("--force" in m for m in env["messages"])


def test_clean_repo_no_block_deploys(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True,
                          allowlist=["PLAN-scratch.md"])
    calls = _mock_deploy_ok(monkeypatch)
    env = rcmd.run("deploy", str(repo))
    # PLAN-scratch.md is allowlisted → no blocking finding → deploy runs
    assert env["status"] == "ok"
    assert env["deployed"] is True
    assert len(calls) == 1


def test_untracked_alone_does_not_block(tmp_path, monkeypatch):
    # PLAN-scratch.md untracked, README tracked; only untracked stray files exist.
    repo = _make_pkg_repo(tmp_path, scratch_tracked=False)
    calls = _mock_deploy_ok(monkeypatch)
    env = rcmd.run("deploy", str(repo))
    # untracked files cannot reach the archive → must NOT block
    assert env["status"] == "ok"
    assert env["blockers"] == []
    assert len(calls) == 1


# ─────────── worktree construction: the #52 structural proof ───────────


def test_worktree_excludes_untracked_includes_committed(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True,
                          allowlist=["PLAN-scratch.md"])
    captured = {}

    def fake(snippet, *a, **k):
        # capture the ref_dir contents WHILE the worktree is still live (the
        # try/finally in _run_deploy removes it before run() returns).
        captured["snippet"] = snippet
        return ('{"deployed":true,"branch":"gh-pages"}', 0)

    monkeypatch.setattr(rcmd, "_invoke_r", fake)

    seen = {}
    real_cleanup = rcmd._git_worktree_cleanup

    def spy_cleanup(r, dest):
        # snapshot the materialized tree before it is torn down
        seen["plan"] = (Path(dest) / "PLAN-scratch.md").is_file()
        seen["readme"] = (Path(dest) / "README.md").is_file()
        seen["notes"] = (Path(dest) / "NOTES.md").exists()
        return real_cleanup(r, dest)

    monkeypatch.setattr(rcmd, "_git_worktree_cleanup", spy_cleanup)
    env = rcmd.run("deploy", str(repo))
    ref_dir = env["ref_dir"]
    # committed files present in the clean HEAD worktree
    assert seen["plan"] is True
    assert seen["readme"] is True
    # untracked file structurally absent — the whole point of #52
    assert seen["notes"] is False
    # the snippet deploys from the clean HEAD worktree, not the working dir
    assert str(ref_dir) in captured["snippet"]
    assert str(repo) not in captured["snippet"]
    # the worktree is removed after the deploy (try/finally cleanup)
    assert not Path(ref_dir).exists()


# ───────────────────────── error envelopes ─────────────────────────


def test_git_worktree_failure_refuses_never_deploys_working_dir(tmp_path, monkeypatch):
    # a package dir that is NOT a git repo → git worktree add fails
    repo = tmp_path / "nogit"
    repo.mkdir()
    (repo / "DESCRIPTION").write_text("Package: demo\nVersion: 0.0.1\n")
    (repo / "README.md").write_text("# demo\n")
    calls = _mock_deploy_ok(monkeypatch)
    env = rcmd.run("deploy", str(repo))
    assert env["status"] == "warn"
    assert env["deployed"] is False
    # CRITICAL: deploy_to_branch never called → no working-dir publish
    assert calls == []
    assert any("refus" in m.lower() or "worktree" in m.lower()
               for m in env["messages"])


def test_pkgdown_missing_engine_missing_path(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True,
                          allowlist=["PLAN-scratch.md"])
    monkeypatch.setattr(
        rcmd, "_invoke_r",
        lambda s, *a, **k: ('{"engine_missing":["pkgdown"]}', 0))
    env = rcmd.run("deploy", str(repo))
    # OPTIONAL_ENGINES downgrade: error → warn, never crash
    assert env["status"] == "warn"
    assert "pkgdown" in env["engine_missing"]


def test_publish_preview_in_messages(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True,
                          allowlist=["PLAN-scratch.md"])
    _mock_deploy_ok(monkeypatch)
    env = rcmd.run("deploy", str(repo))
    assert any("publish" in m.lower() for m in env["messages"])


def test_custom_branch_threaded(tmp_path, monkeypatch):
    repo = _make_pkg_repo(tmp_path, scratch_tracked=True,
                          allowlist=["PLAN-scratch.md"])
    captured = {}
    monkeypatch.setattr(
        rcmd, "_invoke_r",
        lambda s, *a, **k: (captured.update(snippet=s)
                            or ('{"deployed":true,"branch":"docs"}', 0)))
    env = rcmd.run("deploy", str(repo), branch="docs")
    assert env["branch"] == "docs"
    assert '"docs"' in captured["snippet"]


# ───────────────────────── recommend-only / no auto-run ─────────────────────────


def test_orchestrator_never_lists_deploy_as_autorun():
    # There is no SAFE_AUTORUN code constant; recommend-only is enforced in the
    # orchestrator agent prose. Guard: the `r:site --deploy` surface must NEVER
    # appear in an auto-run / read-only-auto-run enumeration in the orchestrator.
    root = Path(__file__).resolve().parent.parent
    text = (root / "agents" / "orchestrator.md").read_text()
    # crude but effective: no line that both mentions auto-run AND --deploy
    for line in text.splitlines():
        low = line.lower()
        if "auto" in low and "run" in low and "--deploy" in low:
            raise AssertionError(
                f"orchestrator lists --deploy as auto-runnable: {line!r}")

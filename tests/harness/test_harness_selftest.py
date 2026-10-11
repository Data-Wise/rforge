"""Self-tests for the replay harness (tests/harness/replay.py).

The harness decides whether the audit is good enough to ship, so it is tested
against a stub audit on a synthetic git repo: it must go green when the stub finds
the planted defect and red (the mutation test) when the stub finds nothing."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
import replay  # noqa: E402

MANIFEST = HARNESS.parent / "fixtures" / "docaudit" / "defects.json"


def _git(repo: Path, *args: str) -> str:
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(repo), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """Two commits: the first has a defective vignette, the second fixes it. No NAMESPACE/man at all."""
    r = tmp_path / "pkg"
    (r / "vignettes").mkdir(parents=True)
    _git(r, "init", "-q", "-b", "main")
    (r / "DESCRIPTION").write_text("Package: demo\nVersion: 0.1.0\n")
    (r / "vignettes" / "a.qmd").write_text("calls BAD here\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "defect")
    bad = _git(r, "rev-parse", "HEAD")
    (r / "vignettes" / "a.qmd").write_text("calls good here\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "fix")
    return r, bad


def _manifest(bad: str, **over) -> dict:
    row = {"id": "demo-bad", "package": "demo", "ref": bad, "fix": None, "file": "vignettes/a.qmd",
           "check": "signature-names", "release": "A1", "expectation": "firm", "status": "pending", "reason": ""}
    row.update(over)
    return {"packages": {"demo": {"env": "RFORGE_DEMO_PATH"}}, "defects": [row]}


def stub_audit(tree: Path) -> list:
    text = (tree / "vignettes" / "a.qmd").read_text()
    return [{"check": "signature-names", "file": "vignettes/a.qmd", "function": "f", "arg": "x"}] if "BAD" in text else []


def run(manifest, repo_path, **kw):
    return replay.run_recall(manifest, overrides={"demo": str(repo_path)}, **kw)


def test_caught_when_stub_finds_planted_defect(repo):
    path, bad = repo
    s = run(_manifest(bad), path, audit=stub_audit)
    assert [r["outcome"] for r in s["rows"]] == ["caught"]
    assert s["firm_caught"] == 1 and s["firm_eligible"] == 1 and s["ok"]


def test_mutation_audit_that_finds_nothing_turns_firm_row_red(repo):
    path, bad = repo
    s = run(_manifest(bad), path, audit=lambda tree: [])
    assert s["rows"][0]["outcome"] == "missed"
    assert not s["ok"] and s["failures"] == ["demo-bad"]


def test_wrong_file_is_not_a_catch(repo):
    path, bad = repo
    s = run(_manifest(bad, file="vignettes/other.qmd"), path, audit=stub_audit)
    assert s["rows"][0]["outcome"] == "missed"


def test_unimplemented_check_is_pending_not_missed(repo):
    path, bad = repo
    s = run(_manifest(bad), path, audit=lambda tree: [], implemented=set())
    assert s["rows"][0]["outcome"] == "pending" and s["ok"]
    assert s["firm_pending"] == 1 and s["firm_eligible"] == 0


def test_audit_crash_is_red_not_pending(repo):
    path, bad = repo

    def boom(tree):
        raise replay.AuditCrashed("traceback")

    s = run(_manifest(bad), path, audit=boom)
    assert s["rows"][0]["outcome"] == "crashed" and not s["ok"]


def test_unknown_ref_is_reported_not_crashed(repo):
    path, _ = repo
    s = run(_manifest("0" * 40), path, audit=stub_audit)
    assert s["rows"][0]["outcome"] == "ref-not-found" and s["ok"]


def test_missing_checkout_is_unavailable_but_locked_row_fails(repo):
    _, bad = repo
    m = _manifest(bad)
    s = replay.run_recall(m, overrides={}, audit=stub_audit)
    assert s["rows"][0]["outcome"] == "unavailable" and s["ok"]
    m["defects"][0]["status"] = "firm"
    assert not replay.run_recall(m, overrides={}, audit=stub_audit)["ok"]


def test_row_without_ref_is_unavailable(repo):
    path, _ = repo
    s = run(_manifest(None, check="site-missing-page", release="A2"), path, audit=stub_audit)
    assert s["rows"][0]["outcome"] == "unavailable" and s["ok"]


def test_conditional_miss_does_not_fail_unless_locked(repo):
    path, bad = repo
    s = run(_manifest(bad, expectation="conditional"), path, audit=lambda tree: [])
    assert s["rows"][0]["outcome"] == "missed" and s["ok"] and s["conditional_total"] == 1
    s = run(_manifest(bad, expectation="conditional", status="firm"), path, audit=lambda tree: [])
    assert not s["ok"]


def test_scope_filters_rows(repo):
    path, bad = repo
    assert run(_manifest(bad), path, scope="signature", audit=stub_audit)["rows"]
    assert run(_manifest(bad), path, scope="a1", audit=stub_audit)["rows"]
    assert run(_manifest(bad, check="scannability"), path, scope="signature", audit=stub_audit)["rows"] == []
    assert run(_manifest(bad, release="A2"), path, scope="a1", audit=stub_audit)["rows"] == []


def test_extraction_tolerates_missing_paths_and_leaves_repo_untouched(repo):
    path, bad = repo  # no man/, NAMESPACE or README at this ref: `git archive` alone would abort
    before = (_git(path, "rev-parse", "HEAD"), _git(path, "status", "--porcelain"), _git(path, "worktree", "list"))
    run(_manifest(bad), path, audit=stub_audit)
    assert before == (_git(path, "rev-parse", "HEAD"), _git(path, "status", "--porcelain"), _git(path, "worktree", "list"))


def test_history_replay_dedupes_and_tags_first_seen(repo):
    path, bad = repo
    (path / "vignettes" / "a.qmd").write_text("calls BAD again\n")
    _git(path, "add", "-A"); _git(path, "commit", "-q", "-m", "regress")
    found = replay.run_history(path, n=10, audit=stub_audit)
    assert len(found) == 1 and found[0]["commits"] == 2
    assert found[0]["first_seen_in"] == _git(path, "rev-parse", "HEAD")
    assert replay.run_history(path, n=10, checks={"signature-arity"}, audit=stub_audit) == []


def test_history_replay_respects_n(repo):
    path, _ = repo
    assert replay.run_history(path, n=1, audit=stub_audit) == []  # only the fixed tip


# ───────────────────────── the committed manifest ─────────────────────────


def test_manifest_shape():
    m = json.loads(MANIFEST.read_text())
    rows = m["defects"]
    assert len(rows) == 18 and len({r["id"] for r in rows}) == 18
    assert {k for r in rows for k in r} == {"id", "package", "ref", "fix", "file", "check", "release",
                                            "expectation", "status", "reason"}
    assert {r["expectation"] for r in rows} <= {"firm", "conditional", "none"}
    assert {r["status"] for r in rows} <= {"pending", "firm"}
    assert sum(r["expectation"] == "firm" for r in rows) == 3
    assert sum(r["expectation"] == "conditional" for r in rows) == 3
    for r in rows:  # a row with a check has a release; a row without one is expectation none
        assert (r["check"] is None) == (r["release"] is None) == (r["expectation"] == "none")
        assert r["ref"] is None or len(r["ref"].rstrip("^")) == 7  # SHAs only, never content


def test_cli_recall_on_committed_manifest_never_fails_without_checkouts(monkeypatch, capsys):
    monkeypatch.delenv("RFORGE_MEDFIT_PATH", raising=False)
    assert replay.main(["recall", "--manifest", str(MANIFEST)]) == 0
    assert "firm" in capsys.readouterr().out

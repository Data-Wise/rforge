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
    required = {"id", "package", "ref", "fix", "file", "check", "release", "expectation", "status", "reason"}
    assert required <= {k for r in rows for k in r} <= required | {"function", "arg"}
    assert {r["expectation"] for r in rows} <= {"firm", "conditional", "none"}
    assert {r["status"] for r in rows} <= {"pending", "firm"}
    assert sum(r["expectation"] == "firm" for r in rows) == 3
    assert sum(r["expectation"] == "conditional" for r in rows) == 3
    for r in rows:  # a row with a check has a release; a row without one is expectation none
        assert (r["check"] is None) == (r["release"] is None) == (r["expectation"] == "none")
        assert r["ref"] is None or len(r["ref"].rstrip("^")) == 7  # SHAs only, never content


def test_cli_recall_on_committed_manifest_without_checkouts(monkeypatch, capsys):
    monkeypatch.delenv("RFORGE_MEDFIT_PATH", raising=False)
    # a regression-locked row cannot be verified without its checkout: red by default...
    assert replay.main(["recall", "--manifest", str(MANIFEST)]) == (1 if replay.docaudit_available() else 0)
    # ...and tolerated with --allow-unavailable (CI-style run)
    assert replay.main(["recall", "--manifest", str(MANIFEST), "--allow-unavailable"]) == 0
    assert "firm" in capsys.readouterr().out


# ───────────────────────── adversarial review #2 regressions ─────────────────────────


def test_broken_docaudit_import_is_red_not_pending(repo, monkeypatch):
    path, bad = repo

    def broken():
        raise replay.AuditCrashed("cannot import lib.docaudit")

    monkeypatch.setattr(replay, "docaudit_available", lambda: True)
    monkeypatch.setattr(replay, "implemented_checks", broken)
    s = replay.run_recall(_manifest(bad), overrides={"demo": str(path)})
    assert s["rows"][0]["outcome"] == "crashed" and not s["ok"]


def test_catch_requires_the_manifest_function_and_arg(repo):
    path, bad = repo
    other = lambda tree: [{"check": "signature-names", "file": "vignettes/a.qmd", "function": "other", "arg": "q"}]  # noqa: E731
    assert run(_manifest(bad, function="f"), path, audit=other)["rows"][0]["outcome"] == "missed"
    assert run(_manifest(bad), path, audit=other)["rows"][0]["outcome"] == "caught"  # no function pinned: file+check
    right = lambda tree: [{"check": "signature-names", "file": "vignettes/a.qmd", "function": "f", "arg": "x"}]  # noqa: E731
    assert run(_manifest(bad, function="f", arg="x"), path, audit=right)["rows"][0]["outcome"] == "caught"
    assert run(_manifest(bad, function="f", arg="y"), path, audit=right)["rows"][0]["outcome"] == "missed"


def test_allow_unavailable_does_not_forgive_a_bad_ref(repo):
    path, _ = repo
    m = _manifest("0" * 40, status="firm")
    assert not run(m, path, audit=stub_audit, allow_unavailable=True)["ok"]


def test_readme_qmd_is_extracted(tmp_path):
    r = tmp_path / "pkg"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "README.qmd").write_text("x\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "c")
    assert replay.extract_tree(r, "HEAD", tmp_path / "out") and (tmp_path / "out" / "README.qmd").exists()


def test_real_audit_path_catches_a_planted_defect_through_the_subprocess(tmp_path):
    """The stub tests prove the plumbing; this one runs the real `python -m lib.docaudit` gate."""
    r = tmp_path / "pkg"
    (r / "man").mkdir(parents=True)
    _git(r, "init", "-q", "-b", "main")
    (r / "DESCRIPTION").write_text("Package: demo\nVersion: 0.1.0\n")
    (r / "NAMESPACE").write_text("export(f)\n")
    (r / "man" / "f.Rd").write_bytes(b"\\name{f}\n\\usage{\nf(a, b)\n}\n")
    (r / "README.md").write_text("```r\nf(a = 1, zzz = 2)\n```\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "defect")
    bad = _git(r, "rev-parse", "HEAD")
    m = _manifest(bad, check="signature-named-arg", file="README.md", function="f", arg="zzz")
    s = replay.run_recall(m, overrides={"demo": str(r)})
    assert s["rows"][0]["outcome"] == "caught" and s["ok"]
    (r / "README.md").write_text("```r\nf(a = 1)\n```\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "fix")
    fixed = _git(r, "rev-parse", "HEAD")
    assert replay.run_recall(_manifest(fixed, check="signature-named-arg", file="README.md", function="f", arg="zzz"),
                             overrides={"demo": str(r)})["rows"][0]["outcome"] == "missed"


# ───────────────────────── Codex review #3: F2 (failed audits) and F3 (the lock) ─────────────────────────


@pytest.fixture
def fake_audit(tmp_path, monkeypatch):
    """Point `subprocess_audit` at a fake `lib.docaudit` that prints a chosen stdout and exit code."""
    root = tmp_path / "fakeroot"
    (root / "lib").mkdir(parents=True)
    (root / "lib" / "__init__.py").write_text("")

    def make(stdout: str, code: int = 0, sleep: float = 0):
        (root / "lib" / "docaudit.py").write_text(
            f"import sys, time\ntime.sleep({sleep})\nprint({stdout!r})\nsys.exit({code})\n")
        monkeypatch.setattr(replay, "REPO_ROOT", root)
        return tmp_path

    return make


@pytest.mark.parametrize("stdout,code", [
    ('{"findings": []}', 3),                                           # non-zero exit
    ("not json", 0),                                                   # malformed output
    ('{"status": "ok"}', 0),                                           # no findings key
    ('{"findings": [], "audit_failed": true, "messages": ["boom"]}', 0),  # the catch-all envelope
])
def test_subprocess_audit_raises_on_every_failed_audit_shape(fake_audit, stdout, code):
    tree = fake_audit(stdout, code)
    with pytest.raises(replay.AuditCrashed):
        replay.subprocess_audit(tree)


def test_subprocess_audit_accepts_a_real_empty_report(fake_audit):
    assert replay.subprocess_audit(fake_audit('{"findings": [], "status": "ok"}')) == []


def test_subprocess_audit_times_out(fake_audit):
    with pytest.raises(replay.AuditCrashed, match="timed out"):
        replay.subprocess_audit(fake_audit('{"findings": []}', sleep=5), timeout=1)


def test_history_replay_does_not_report_clean_for_a_failed_audit(repo, fake_audit):
    path, _ = repo
    fake_audit('{"findings": [], "audit_failed": true, "messages": ["boom"]}')
    with pytest.raises(replay.AuditCrashed):
        replay.run_history(path, n=2)


def test_audit_failure_envelope_is_marked(tmp_path, monkeypatch):
    from lib import docaudit

    (tmp_path / "DESCRIPTION").write_text("Package: p\nVersion: 1\n")
    monkeypatch.setattr(docaudit, "read_api", lambda root: (_ for _ in ()).throw(RuntimeError("boom")))
    r = docaudit.audit_package(tmp_path)
    assert r["audit_failed"] is True and r["findings"] == [] and "boom" in r["messages"][0]


def test_locked_row_cannot_go_pending_when_its_check_disappears(repo):
    path, bad = repo
    locked = _manifest(bad, status="firm")
    for implemented in (set(), {"some-other-check"}):  # removed, or the manifest check misnamed
        s = run(locked, path, audit=stub_audit, implemented=implemented)
        assert s["rows"][0]["outcome"] == "lost" and not s["ok"] and s["failures"] == ["demo-bad"]
    unlocked = run(_manifest(bad, status="pending"), path, audit=stub_audit, implemented=set())
    assert unlocked["rows"][0]["outcome"] == "pending" and unlocked["ok"]


def test_lock_survives_a_missing_module_on_the_committed_manifest(monkeypatch):
    monkeypatch.setattr(replay, "docaudit_available", lambda: False)
    s = replay.run_recall(json.loads(MANIFEST.read_text()), scope="signature")
    assert not s["ok"] and s["failures"] == ["refcard-joint-effects-args"]


def test_mutation_removing_a_check_from_implemented_checks_fails_recall(monkeypatch):
    monkeypatch.setattr(replay, "docaudit_available", lambda: True)
    monkeypatch.setattr(replay, "implemented_checks", lambda: set())
    assert not replay.run_recall(json.loads(MANIFEST.read_text()), scope="signature")["ok"]


# ───────────────────────── Codex re-review: G2 incomplete audits, G4 failed enumeration/extraction ─────────────────────────


def test_incomplete_audit_is_not_reported_as_clean(fake_audit):
    tree = fake_audit('{"findings": [], "incomplete": true, "messages": ["region at README.md:2 skipped"]}')
    with pytest.raises(replay.AuditCrashed, match="incomplete"):
        replay.subprocess_audit(tree)


def test_history_replay_on_a_missing_repository_is_an_error(tmp_path):
    with pytest.raises(replay.AuditCrashed, match="rev-list"):
        replay.run_history(tmp_path / "nope", n=3, audit=lambda tree: [])
    assert replay.main(["replay", "--repo", str(tmp_path / "nope"), "--n", "3"]) in (1, 2)


def test_failed_extraction_is_an_error_not_a_skip(repo, monkeypatch):
    path, _ = repo
    real = replay._git

    def failing(repo_, *args, **kw):
        if args and args[0] == "archive":
            return subprocess.CompletedProcess(args, 128, stdout=b"", stderr="fatal: boom")
        return real(repo_, *args, **kw)

    monkeypatch.setattr(replay, "_git", failing)
    with pytest.raises(replay.AuditCrashed, match="archive"):
        replay.run_history(path, n=2, audit=stub_audit)


def test_revisions_with_no_documentation_paths_are_counted_not_failed(tmp_path):
    r = tmp_path / "pkg"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "other.txt").write_text("x\n")
    _git(r, "add", "-A"); _git(r, "commit", "-q", "-m", "c")
    stats: dict = {}
    assert replay.run_history(r, n=5, audit=stub_audit, stats=stats) == []
    assert stats == {"revisions": 1, "audited": 0, "skipped_empty": 1}


def test_history_stats_count_audited_revisions(repo):
    path, _ = repo
    stats: dict = {}
    replay.run_history(path, n=10, audit=stub_audit, stats=stats)
    assert stats == {"revisions": 2, "audited": 2, "skipped_empty": 0}


# ───────────────────────── Codex re-review #2: the lock cannot be bypassed by a misspelled check or the scope filter ─────────────────────────


def test_misspelled_locked_check_fails_even_when_scope_would_filter_it_out():
    m = json.loads(MANIFEST.read_text())
    for r in m["defects"]:
        if r["id"] == "refcard-joint-effects-args":
            r["check"] = "sigature-names"
    s = replay.run_recall(m, scope="signature", allow_unavailable=True)
    assert not s["ok"] and any("sigature-names" in f for f in s["failures"])


def test_every_manifest_check_id_is_known():
    m = json.loads(MANIFEST.read_text())
    assert {r["check"] for r in m["defects"] if r["check"]} <= replay.KNOWN_CHECKS


def test_subprocess_audit_rejects_a_report_that_audited_nothing(fake_audit):
    tree = fake_audit('{"findings": [], "audited": false, "messages": ["not an R package (no DESCRIPTION at x)"]}')
    with pytest.raises(replay.AuditCrashed, match="nothing was audited"):
        replay.subprocess_audit(tree)


def test_subprocess_audit_rejects_a_report_for_a_different_package(fake_audit):
    tree = fake_audit('{"findings": [], "audited": true, "scope": {"root": "/somewhere/else"}}')
    with pytest.raises(replay.AuditCrashed, match="not the extracted tree"):
        replay.subprocess_audit(tree)

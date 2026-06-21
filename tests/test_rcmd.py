import json
import os
import subprocess
import textwrap
from pathlib import Path
import pytest
from lib import rcmd


def _write_desc(tmp_path: Path, name="foo", version="0.2.0"):
    (tmp_path / "DESCRIPTION").write_text(
        textwrap.dedent(f"Package: {name}\nVersion: {version}\nTitle: Test\n")
    )
    return tmp_path


def test_find_package_reads_description(tmp_path):
    _write_desc(tmp_path, "mypkg", "1.4.0")
    assert rcmd.find_package(str(tmp_path)) == {"package": "mypkg", "version": "1.4.0"}


def test_find_package_missing_returns_none(tmp_path):
    assert rcmd.find_package(str(tmp_path)) is None


def test_normalize_check_clean_ok():
    env = rcmd.normalize("check", {"errors": [], "warnings": [], "notes": []}, 0,
                         {"package": "foo", "version": "1.0"})
    assert env["status"] == "ok" and env["package"] == "foo"


def test_normalize_check_notes_warn():
    assert rcmd.normalize("check", {"notes": ["n"]}, 0, None)["status"] == "warn"


def test_normalize_check_errors_error():
    assert rcmd.normalize("check", {"errors": ["e"]}, 1, None)["status"] == "error"


def test_normalize_test_failures_error():
    env = rcmd.normalize("test", {"passed": 40, "failed": 2, "skipped": 1,
                                  "warnings": 0, "failing_files": ["t-a.R"]}, 1, None)
    assert env["status"] == "error" and env["tests"]["failing_files"] == ["t-a.R"]


def test_normalize_coverage_includes_untested():
    raw = {"total_pct": 80.0, "per_file": {"R/a.R": 50.0},
           "untested": [{"file": "R/a.R", "first_line": 3, "last_line": 7}]}
    env = rcmd.normalize("coverage", raw, 0, None)
    assert env["status"] == "ok"
    assert env["coverage"]["untested"][0]["first_line"] == 3


@pytest.mark.parametrize("kind,key", [("lint", "lints"), ("spell", "misspelled")])
def test_normalize_quality_warns_when_findings(kind, key):
    assert rcmd.normalize(kind, {key: [{"x": 1}]}, 0, None)["status"] == "warn"
    assert rcmd.normalize(kind, {key: []}, 0, None)["status"] == "ok"


def test_normalize_urlcheck_empty_is_ok():
    env = rcmd.normalize("urlcheck", {"broken": []}, 0, None)
    assert env["status"] == "ok"
    assert env["urlcheck"]["count"] == 0
    assert env["urlcheck"]["doi_blocked_count"] == 0


def test_normalize_style_ok_on_exit0():
    assert rcmd.normalize("style", {"changed_files": ["R/a.R"]}, 0, None)["status"] == "ok"


def test_normalize_engine_missing_error():
    env = rcmd.normalize("site", {"engine_missing": ["pkgdown"]}, 1, None)
    assert env["status"] == "error" and env["engine_missing"] == ["pkgdown"]


def test_console_fallback_testthat():
    raw = rcmd.console_fallback("test", "[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]\n")
    assert raw == {"failed": 2, "warnings": 0, "skipped": 1, "passed": 41}


def test_console_fallback_rcmdcheck():
    raw = rcmd.console_fallback("check", "0 errors v | 1 warning x | 2 notes x\n")
    assert len(raw["errors"]) == 0 and len(raw["warnings"]) == 1 and len(raw["notes"]) == 2


def test_console_fallback_unknown_returns_messages():
    assert "messages" in rcmd.console_fallback("test", "nothing here")


@pytest.mark.parametrize("kind,needle", [
    ("check", "rcmdcheck::rcmdcheck"), ("build", "pkgbuild::build"),
    ("document", "roxygen2::roxygenize"), ("test", "testthat::test_local"),
    ("coverage", "covr::package_coverage"), ("site", "pkgdown::build_site"),
    ("load", "pkgload::load_all"), ("lint", "lintr::lint_package"),
    ("spell", "spelling::spell_check_package"), ("urlcheck", "urlchecker::url_check"),
    ("style", "styler::style_pkg"),
])
def test_r_snippet_uses_lower_level_engine(kind, needle):
    src = rcmd.r_snippet(kind, "/tmp/foo")
    assert needle in src and "jsonlite::toJSON" in src and "devtools::" not in src


def test_r_snippet_check_as_cran():
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True)
    assert "--as-cran" in src and 'error_on = "never"' in src


def test_r_snippet_test_uses_load_package_source():
    assert 'load_package="source"' in rcmd.r_snippet("test", "/tmp/foo")


def test_r_snippet_coverage_uses_zero_coverage():
    assert "zero_coverage" in rcmd.r_snippet("coverage", "/tmp/foo")


def test_r_snippet_site_flags():
    assert "preview_site" in rcmd.r_snippet("site", "/tmp/f", preview=True)
    assert "preview_site" not in rcmd.r_snippet("site", "/tmp/f")
    assert "check_pkgdown" in rcmd.r_snippet("site", "/tmp/f", strict=True)
    assert "pkgdown_sitrep" in rcmd.r_snippet("site", "/tmp/f")  # default
    assert "build_articles" in rcmd.r_snippet("site", "/tmp/f", articles_only=True)


def test_run_check_happy(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.2.0")
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ('{"errors":[],"warnings":["W"],"notes":[]}', 0))
    env = rcmd.run("check", str(tmp_path))
    assert env["status"] == "warn" and env["package"] == "foo"
    assert env["check"]["warnings"] == ["W"]


def test_run_no_description_error(tmp_path):
    env = rcmd.run("check", str(tmp_path))
    assert env["status"] == "error" and "detect" in " ".join(env["messages"]).lower()


def test_run_falls_back_on_nonjson(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ("[ FAIL 1 | WARN 0 | SKIP 0 | PASS 9 ]", 1))
    env = rcmd.run("test", str(tmp_path))
    assert env["tests"]["failed"] == 1 and env["status"] == "error"


def test_run_optional_engine_missing_downgrades_to_warn(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"engine_missing":["pkgdown"]}', 0))
    env = rcmd.run("site", str(tmp_path))
    assert env["status"] == "warn"  # optional engine → warn, not error
    assert any("pkgdown" in m for m in env["messages"])


def test_cycle_stops_on_first_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    calls = []
    def fake_run(kind, path, **kw):
        calls.append(kind)
        return {"kind": kind, "status": "error" if kind == "test" else "ok",
                "engine_missing": [], "messages": []}
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cycle(str(tmp_path))
    assert env["failed_stage"] == "test" and calls == ["document", "test"]


def test_main_emits_json(tmp_path, monkeypatch, capsys):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"errors":[],"warnings":[],"notes":[]}', 0))
    rc = rcmd.main(["--kind", "check", "--path", str(tmp_path)])
    assert json.loads(capsys.readouterr().out)["status"] == "ok" and rc == 0


# --- Regression tests: bugs found in live R sanity check (2026-06-01) ---

def test_parse_json_tolerates_leading_progress_lines():
    # urlchecker prints "fetching [...]" and pkgdown prints a build log to stdout
    # before the JSON. _parse_json must recover the trailing JSON object.
    stdout = 'fetching [ 0 / 1 ]\n-- Building site --\n{"checked":true,"built":true,"problems":[]}'
    assert rcmd._parse_json(stdout) == {"checked": True, "built": True, "problems": []}


def test_parse_json_clean_single_line():
    assert rcmd._parse_json('{"errors":[],"warnings":[],"notes":[]}') == {
        "errors": [], "warnings": [], "notes": []}


def test_parse_json_empty_is_empty_dict():
    assert rcmd._parse_json("") == {}


def test_parse_json_no_json_returns_none():
    assert rcmd._parse_json("just logs\nno json here") is None


def test_as_list_wraps_scalars():
    # jsonlite auto_unbox collapses a length-1 vector to a scalar.
    assert rcmd._as_list("one warning") == ["one warning"]
    assert rcmd._as_list({"file": "R/a.R"}) == [{"file": "R/a.R"}]
    assert rcmd._as_list(None) == []
    assert rcmd._as_list(["a", "b"]) == ["a", "b"]


def test_normalize_check_unboxed_single_warning_becomes_list():
    # A single check warning arrives as a bare string; counts must still work.
    env = rcmd.normalize("check", {"errors": [], "warnings": "one WARNING", "notes": []},
                         0, None)
    assert env["check"]["warnings"] == ["one WARNING"]
    assert len(env["check"]["warnings"]) == 1
    assert env["status"] == "warn"


def test_normalize_lint_unboxed_single_lint_counts_one():
    env = rcmd.normalize("lint", {"lints": {"file": "R/a.R", "line": 3}}, 0, None)
    assert env["lint"]["count"] == 1 and len(env["lint"]["lints"]) == 1


def test_normalize_site_filters_empty_problems():
    # sitrep capture can yield [""]; that must not count as a problem (spurious warn).
    env = rcmd.normalize("site", {"checked": True, "built": True, "problems": [""]}, 0, None)
    assert env["site"]["problems"] == [] and env["status"] == "ok"


def test_run_site_recovers_from_build_log(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ('-- Building site --\nWriting 404.html\n'
                                   '{"checked":true,"built":true,"problems":[""]}', 0))
    env = rcmd.run("site", str(tmp_path))
    assert env["site"]["built"] is True and env["status"] == "ok"


# --- Task 1: dispatched status for async engines (winbuilder/rhub) ---

def test_status_dispatched_for_winbuilder_on_success():
    assert rcmd._status_for("winbuilder", {}, 0) == "dispatched"
    assert rcmd._status_for("rhub", {}, 0) == "dispatched"


def test_status_dispatched_engine_missing_is_error():
    # engine_missing takes precedence (downgraded later in run())
    assert rcmd._status_for("winbuilder", {"engine_missing": ["devtools"]}, 0) == "error"
    assert rcmd._status_for("rhub", {"engine_missing": ["rhub"]}, 0) == "error"


def test_main_dispatched_exits_zero(tmp_path, monkeypatch, capsys):
    _write_desc(tmp_path)
    # Pre-flight requires a committed rhub.yaml before any dispatch.
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
    )
    monkeypatch.setattr(rcmd, "_invoke_r", lambda *a, **k: ('{"run_url":"https://x"}', 0))
    monkeypatch.setattr(rcmd, "_rhub_actions_url", lambda p: "")  # no browser launch
    rc = rcmd.main(["--kind", "rhub", "--path", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "dispatched" and rc == 0


def test_classify_notes_spurious_vs_real():
    notes = ["New submission", "checking foo ... NOTE\n  undefined global bar"]
    out = rcmd._classify_notes(notes)
    assert out[0]["kind"] == "spurious" and out[0]["reason"]
    assert out[1]["kind"] == "real" and out[1]["reason"] is None


def test_normalize_check_includes_notes_classified():
    raw = {"errors": [], "warnings": [], "notes": ["New submission"]}
    env = rcmd.normalize("check", raw, 0, None)
    assert env["check"]["notes_classified"][0]["kind"] == "spurious"


# --- Task 3: r:revdep — reverse-dependency check (revdepcheck) ---

def test_r_snippet_revdep_uses_revdepcheck():
    src = rcmd.r_snippet("revdep", "/tmp/foo")
    assert "revdepcheck" in src and "jsonlite::toJSON" in src
    assert "devtools::" not in src

def test_normalize_revdep_broken_is_error():
    env = rcmd.normalize("revdep", {"broken": ["pkgA"], "new_problems": []}, 0, None)
    assert env["status"] == "error" and env["revdep"]["broken"] == ["pkgA"]

def test_normalize_revdep_clean_is_ok():
    env = rcmd.normalize("revdep", {"broken": [], "new_problems": []}, 0, None)
    assert env["status"] == "ok"

def test_normalize_revdep_new_problems_is_warn():
    env = rcmd.normalize("revdep", {"broken": [], "new_problems": ["pkgB"]}, 0, None)
    assert env["status"] == "warn"


# --- Task 4: r:goodpractice — advisory best-practice bundle (goodpractice) ---

def test_r_snippet_goodpractice_uses_gp():
    src = rcmd.r_snippet("goodpractice", "/tmp/foo")
    assert "goodpractice::gp" in src and "jsonlite::toJSON" in src
    assert "devtools::" not in src

def test_normalize_goodpractice_warns_with_items():
    env = rcmd.normalize("goodpractice", {"checks": ["avoid T/F"]}, 0, None)
    assert env["status"] == "warn" and env["goodpractice"]["count"] == 1

def test_normalize_goodpractice_clean_ok():
    assert rcmd.normalize("goodpractice", {"checks": []}, 0, None)["status"] == "ok"


# --- Task 5: r:winbuilder + r:rhub — multi-platform dispatch ---

def test_r_snippet_winbuilder_guards_devtools():
    src = rcmd.r_snippet("winbuilder", "/tmp/foo")
    assert "devtools::check_win_devel" in src and 'requireNamespace("devtools"' in src

def test_r_snippet_rhub_uses_rhub_check():
    src = rcmd.r_snippet("rhub", "/tmp/foo")
    assert "rhub::rhub_check" in src and 'requireNamespace("rhub"' in src

def test_run_winbuilder_missing_devtools_warns(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"engine_missing":["devtools"]}', 0))
    env = rcmd.run("winbuilder", str(tmp_path))
    assert env["status"] == "warn"  # optional engine downgrade
    assert any("devtools" in m for m in env["messages"])


# --- Task 6: render_cran_comments — pure markdown generator ---

def test_cran_comments_spurious_note_no_revdep():
    """revdep_env=None → 'no downstream dependencies'; spurious note is tagged 'expected'."""
    check_env = {"check": {"errors": [], "warnings": [], "notes": ["New submission"],
                 "notes_classified": [{"text": "New submission", "kind": "spurious",
                                       "reason": "expected on first submission"}]}}
    text = rcmd.render_cran_comments("foo", "0.2.0", check_env, None)
    assert "## R CMD check results" in text
    assert "0 errors | 0 warnings | 1 note" in text
    assert "New submission" in text and "expected on first submission" in text
    assert "[expected]" in text
    assert "## Reverse dependencies" in text
    assert "no downstream dependencies" in text.lower()


def test_cran_comments_spurious_note_clean_revdep():
    """revdep_env provided with no broken packages → 'All reverse dependencies passed'."""
    check_env = {"check": {"errors": [], "warnings": [], "notes": ["New submission"],
                 "notes_classified": [{"text": "New submission", "kind": "spurious",
                                       "reason": "expected on first submission"}]}}
    revdep_env = {"revdep": {"broken": [], "new_problems": []}}
    text = rcmd.render_cran_comments("foo", "0.2.0", check_env, revdep_env)
    assert "## R CMD check results" in text
    assert "0 errors | 0 warnings | 1 note" in text
    assert "New submission" in text and "expected on first submission" in text
    assert "## Reverse dependencies" in text
    assert "all reverse dependencies passed" in text.lower()


def test_cran_comments_flags_real_note_needs_review():
    check_env = {"check": {"errors": [], "warnings": [],
                 "notes_classified": [{"text": "undefined global foo", "kind": "real",
                                       "reason": None}]}}
    text = rcmd.render_cran_comments("foo", "1.0", check_env, None)
    assert "NEEDS REVIEW" in text and "undefined global foo" in text


def test_cran_comments_broken_revdep():
    """Broken packages are listed; empty check_env is handled without crash."""
    revdep_env = {"revdep": {"broken": ["pkgA", "pkgB"], "new_problems": []}}
    text = rcmd.render_cran_comments("foo", "0.2.0", {}, revdep_env)
    assert "Broke 2 package(s): pkgA, pkgB" in text
    assert "maintainers notified" in text


# --- Task 7: _run_cran_prep orchestrator ---

def test_cran_prep_stops_at_hard_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    calls = []
    def fake_run(kind, path, **kw):
        calls.append(kind)
        status = "error" if kind == "test" else "ok"
        return {"kind": kind, "status": status, "engine_missing": [], "messages": [],
                "check": {"errors": [], "warnings": [], "notes": [], "notes_classified": []}}
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path))
    assert env["status"] == "blocked" and env["failed_stage"] == "test"
    assert "check" not in calls  # stopped before the gate

def test_cran_prep_ready_when_clean(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.2.0")
    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok", "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [], "notes": [], "notes_classified": []}
        if kind == "revdep":
            base["revdep"] = {"broken": [], "new_problems": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=False)
    assert env["status"] == "ready"
    assert env["cran_comments_path"].endswith("cran-comments.md")

def test_cran_prep_warn_on_real_note(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok" if kind != "check" else "warn",
                "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [],
                             "notes": ["undefined global"],
                             "notes_classified": [{"text": "undefined global",
                                                   "kind": "real", "reason": None}]}
        if kind == "revdep":
            base["revdep"] = {"broken": [], "new_problems": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path))
    assert env["status"] == "warn"   # real NOTE → not "ready"
    assert any("real NOTE" in b or "real note" in b.lower() for b in env["blockers"])


def test_cran_prep_no_description_blocked(tmp_path):
    env = rcmd._run_cran_prep(str(tmp_path))
    assert env["status"] == "blocked" and "DESCRIPTION" in env["blockers"][0]
    assert env["stages"] == []


def test_cran_prep_check_error_blocked(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    def fake_run(kind, path, **kw):
        status = "error" if kind == "check" else "ok"
        base = {"kind": kind, "status": status, "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": ["E"], "warnings": [], "notes": [],
                             "notes_classified": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path))
    assert env["status"] == "blocked" and env["failed_stage"] == "check"


def test_cran_prep_revdep_error_adds_blocker(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    def fake_run(kind, path, **kw):
        status = "error" if kind == "revdep" else "ok"
        base = {"kind": kind, "status": status, "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [], "notes": [],
                             "notes_classified": []}
        if kind == "revdep":
            base["revdep"] = {"broken": ["pkgA"], "new_problems": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path))
    assert any("reverse" in b for b in env["blockers"])


def test_cran_prep_multi_platform_populates_dispatched(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.2.0")
    def fake_run(kind, path, **kw):
        status = "dispatched" if kind in ("winbuilder", "rhub") else "ok"
        base = {"kind": kind, "status": status, "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [], "notes": [],
                             "notes_classified": []}
        if kind == "revdep":
            base["revdep"] = {"broken": [], "new_problems": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path), multi_platform=True)
    assert env["dispatched"] == ["winbuilder", "rhub"]
    assert env["status"] == "ready"


# ───────── --changed (diff-aware) wiring ─────────

from unittest import mock

from lib import changed as changed_mod


def test_check_changed_scopes_to_changed_package(monkeypatch, tmp_path):
    """--changed restricts a multi-package run to the single changed package."""
    # One changed package, name 'pkgA' at tmp path.
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    seen_paths = []

    def fake_run(kind, path=".", **kw):
        seen_paths.append(path)
        return {"kind": "check", "status": "ok",
                "check": {"errors": [], "warnings": [], "notes": []}}

    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["changed"]["packages"] == ["pkgA"]
    assert str(tmp_path / "pkgA") in seen_paths


def test_check_changed_scope_only_fallback_surfaces_real_status(monkeypatch, tmp_path):
    """When tagging is unavailable (no merge-base — tmp_path is not a git repo),
    the scope-only fallback must surface the REAL status, never fold to ok. This is
    the regression guard for the v2.10.0 false-negative: the changed package
    reports a real WARNING; the result stays 'warn' with the scope-only message.
    """
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])

    def fake_run(kind, path=".", **kw):
        # changed package has a real, branch-introduced warning
        return {"kind": "check", "status": "warn",
                "check": {"errors": [], "warnings": ["W: introduced by branch"],
                          "notes": []}}

    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    # status is the REAL full status — not falsely folded to ok
    assert env["status"] == "warn"
    # the real finding is surfaced
    assert env["check"]["warnings"] == ["W: introduced by branch"]
    # no tagging block in the fallback
    assert "findings" not in env["changed"]
    assert "introduced_count" not in env["changed"]
    # scope-only fallback message present
    assert any("scope-only" in m for m in env.get("messages", []))


def test_check_changed_strict_is_noop_still_works(monkeypatch, tmp_path):
    """--changed-strict is a documented no-op: scope-only fallback, real status."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: {
        "kind": "check", "status": "error",
        "check": {"errors": ["E: boom"], "warnings": [], "notes": []}})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev",
                           changed_strict=True)
    assert env["status"] == "error"
    assert "introduced_count" not in env["changed"]


def test_check_changed_real_git_repo_tagging_e2e(monkeypatch, tmp_path):
    """END-TO-END through the REAL git + discovery + worktree path (only R `run`
    is faked). Drives `run_changed("check", ...)` against a throwaway git repo with
    one R package modified on a feature branch. `changed_files`, `changed_packages`,
    `merge_base`, `run_baseline` (a real `git worktree add --detach`), and
    `scope_check` all run for real.

    The faked R engine is PATH-SENSITIVE: it reports an ERROR only when the
    package's f.R contains the branch content ("2"), mimicking a real
    branch-introduced failure. The baseline detached worktree holds the base
    content ("1") → no error there → the finding tags [introduced] → status error.

    This is the test that would have caught the v2.10.0 false-negative: the old
    broken draft compared HEAD against HEAD and tagged the real error pre-existing.
    Here the baseline is a genuine checkout of the merge-base, so the diff is real.
    """
    import subprocess

    def git(*args):
        subprocess.run(["git", *args], cwd=str(tmp_path), check=True,
                       capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    git("checkout", "-q", "-b", "main")
    pkg_dir = tmp_path / "mypkg"
    (pkg_dir / "R").mkdir(parents=True)
    _write_desc(pkg_dir, "mypkg", "0.1.0")
    (pkg_dir / "R" / "f.R").write_text("f <- function() 1\n")
    git("add", "-A")
    git("commit", "-qm", "init")
    # feature branch with a real change to the package
    git("checkout", "-q", "-b", "feature/x")
    (pkg_dir / "R" / "f.R").write_text("f <- function() 2\n")
    git("add", "-A")
    git("commit", "-qm", "change f")

    # Path-sensitive faked engine: error iff f.R holds the branch content.
    def fake_run(kind, path=".", **kw):
        src = (Path(path) / "R" / "f.R").read_text()
        errs = ["E: real check failure"] if "2" in src else []
        status = "error" if errs else "ok"
        return {"kind": "check", "status": status,
                "check": {"errors": errs, "warnings": [], "notes": []}}

    monkeypatch.setattr(rcmd, "run", fake_run)

    env = rcmd.run_changed("check", root=str(tmp_path), base="main")
    # (a) scoped to the changed package, two-run tagging engaged
    assert env["changed"]["packages"] == ["mypkg"]
    assert env["changed"]["fell_back"] is False
    # (b) the error is genuinely NEW on the branch → tagged introduced
    tags = {f["text"]: f["tag"] for f in env["changed"]["findings"]}
    assert tags == {"E: real check failure": "introduced"}
    assert env["changed"]["introduced_count"] == 1
    # (c) default --fail-on introduced → status error
    assert env["status"] == "error"


def test_changed_no_git_falls_back_to_full(monkeypatch, tmp_path):
    """Not a git repo (changed_files None) → full run + warn message, status preserved."""
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: None)
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: {
        "kind": "check", "status": "ok",
        "check": {"errors": [], "warnings": [], "notes": []}})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["changed"]["fell_back"] is True
    assert any("git" in m.lower() for m in env.get("messages", []))


def test_changed_no_changes_is_noop_ok(monkeypatch, tmp_path):
    """Empty diff → nothing to check; status ok, packages empty."""
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: [])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [])
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["status"] == "ok"
    assert env["changed"]["packages"] == []
    assert any("no changes" in m.lower() for m in env.get("messages", []))


def test_test_kind_changed_no_merge_base_fallback_is_scope_only(monkeypatch, tmp_path):
    """r:test --changed on a tree with NO resolvable merge-base (tmp_path is not a
    git repo) falls back to scope-only: it scopes to the changed package but does
    NOT tag findings. (This exercises the fallback path, not the tagging path —
    the real tagging path is covered by the v2.11.0 tagging tests below and by
    the dict-finding tests in test_changed.py.)"""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    seen = []
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: seen.append((kind, path)) or {
        "kind": "test", "status": "ok", "tests": {"passed": 1, "failed": 0}})
    env = rcmd.run_changed("test", root=str(tmp_path), base="dev")
    assert ("test", str(tmp_path / "pkgA")) in seen
    assert "findings" not in env["changed"]   # fallback (no merge-base): no tagging


# ───────── --changed (diff-aware) TAGGING (v2.11.0) ─────────


def test_changed_tags_introduced_when_scope_check_succeeds(monkeypatch, tmp_path):
    """When merge-base/baseline resolve, findings are tagged and an introduced
    finding drives status=error (default --fail-on introduced)."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    # scope_check resolves and returns one introduced + one pre-existing finding.
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda runner, path, base, **kw: {
                            "base": base, "merge_base": "abc123",
                            "findings": [{"text": "E: new", "tag": "introduced"},
                                         {"text": "N: old", "tag": "pre-existing"}],
                            "introduced_count": 1})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["changed"]["fell_back"] is False
    assert env["changed"]["introduced_count"] == 1
    assert env["changed"]["merge_base"] == "abc123"
    tags = {f["text"]: f["tag"] for f in env["changed"]["findings"]}
    assert tags == {"E: new": "introduced", "N: old": "pre-existing"}
    # default --fail-on introduced → status error with >=1 introduced
    assert env["status"] == "error"
    # no stale "tagging deferred" wording
    assert not any("deferred" in m for m in env.get("messages", []))


def test_changed_no_introduced_findings_is_ok(monkeypatch, tmp_path):
    """All findings pre-existing → no introduced → status ok (nothing new on branch)."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda runner, path, base, **kw: {
                            "base": base, "merge_base": "abc",
                            "findings": [{"text": "N: old", "tag": "pre-existing"}],
                            "introduced_count": 0})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["status"] == "ok"
    assert env["changed"]["introduced_count"] == 0


def test_changed_fail_on_introduced_fails_on_only_uncommitted(monkeypatch, tmp_path):
    """[uncommitted] is a subset of introduced: --fail-on introduced (default) must
    STILL exit non-zero when the only findings are [uncommitted] (they're yours).
    scope_check folds [uncommitted] into introduced_count, so status=error."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda runner, path, base, **kw: {
                            "base": base, "merge_base": "abc",
                            "findings": [{"text": {"file": "R/x.R",
                                                   "message": "m"},
                                          "tag": "uncommitted"}],
                            "introduced_count": 1})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["status"] == "error"
    assert env["changed"]["introduced_count"] == 1


def test_changed_fail_on_none_never_errors_on_introduced(monkeypatch, tmp_path):
    """--fail-on none: introduced findings are reported but do not drive a nonzero
    status (advisory mode)."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda runner, path, base, **kw: {
                            "base": base, "merge_base": "abc",
                            "findings": [{"text": "E: new", "tag": "introduced"}],
                            "introduced_count": 1})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev", fail_on="none")
    assert env["status"] == "ok"
    assert env["changed"]["introduced_count"] == 1


def test_changed_falls_back_to_scope_only_when_scope_check_none(monkeypatch, tmp_path):
    """No regression of v2.10.0: when scope_check returns None (no merge-base /
    baseline add failed) the command stays scope-only and exits 0."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda runner, path, base, **kw: None)
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: {
        "kind": "check", "status": "ok",
        "check": {"errors": [], "warnings": [], "notes": []}})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["status"] == "ok"
    assert env["changed"]["fell_back"] is False
    assert "findings" not in env["changed"]   # scope-only fallback: no tagging
    assert any("scope-only" in m for m in env.get("messages", []))


def test_changed_runner_extracts_findings_per_kind(monkeypatch, tmp_path):
    """The runner closure handed to scope_check flattens each kind's envelope into
    a finding list (check: errors+warnings+notes; lint: lints; test: failing files)."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: {
        "kind": "check", "status": "error",
        "check": {"errors": ["E1"], "warnings": ["W1"], "notes": ["N1"]}})

    captured = {}

    def capture(runner, path, base, **kw):
        captured["findings"] = runner(str(tmp_path))
        return {"base": base, "merge_base": "x", "findings": [], "introduced_count": 0}

    monkeypatch.setattr(rcmd.changed, "scope_check", capture)
    rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert captured["findings"] == ["E1", "W1", "N1"]


# ───────────────────────── s7runtime engine (v2.11.0) ─────────────────────────
def test_r_snippet_s7runtime_loads_and_guards():
    """s7runtime: loads via pkgload, guards S7+jsonlite, emits JSON, never devtools.

    The introspection body (incl. pkgload::load_all) now ships in
    lib/r/s7runtime.R; the snippet source()s it. Assert load_all in the file,
    everything else in the snippet."""
    src = rcmd.r_snippet("s7runtime", "/tmp/foo")
    from pathlib import Path as _P
    script = (_P(rcmd.__file__).parent / "r" / "s7runtime.R").read_text()
    assert "pkgload::load_all" in script
    assert "jsonlite::toJSON" in src
    assert "auto_unbox" in src
    assert "devtools::" not in src
    assert "devtools::" not in script
    # the guard must check for the S7 engine package
    assert "S7" in src


def test_s7runtime_snippet_sources_script():
    src = rcmd.r_snippet("s7runtime", "/tmp/foo")
    assert "s7runtime.R" in src and "s7_runtime_report" in src
    assert 'requireNamespace("S7"' in src and "tryCatch" in src


def test_s7runtime_in_safe_autorun_taxonomy():
    """s7runtime must be classified read-only/safe-to-auto-run."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_check_agent_engines",
        str(Path(__file__).parent / "_check_agent_engines.py"))
    cae = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cae)
    assert "s7runtime" in cae.SAFE_AUTORUN


def test_normalize_s7runtime_warn_when_issues():
    raw = {"dead_generics": ["dead_gen"], "methods_on_missing_class": [],
           "nonenforcing_validators": ["Lax"]}
    env = rcmd.normalize("s7runtime", raw, 0, {"package": "foo", "version": "1.0"})
    assert env["status"] == "warn"
    assert env["s7runtime"]["dead_generics"] == ["dead_gen"]
    assert env["s7runtime"]["nonenforcing_validators"] == ["Lax"]


def test_normalize_s7runtime_warn_on_undeclared_dependency():
    """A non-empty methods_undeclared_dependency list alone flips status to warn
    and is surfaced in the normalized block."""
    raw = {"dead_generics": [], "methods_on_missing_class": [],
           "methods_undeclared_dependency": [
               {"generic": "speak", "class": "Widget", "package": "otherpkg"}],
           "nonenforcing_validators": []}
    env = rcmd.normalize("s7runtime", raw, 0, None)
    assert env["status"] == "warn"
    assert env["s7runtime"]["methods_undeclared_dependency"] == [
        {"generic": "speak", "class": "Widget", "package": "otherpkg"}]


def test_normalize_s7runtime_ok_when_clean():
    raw = {"dead_generics": [], "methods_on_missing_class": [],
           "nonenforcing_validators": []}
    env = rcmd.normalize("s7runtime", raw, 0, None)
    assert env["status"] == "ok"


def test_run_s7runtime_engine_missing_downgrades_to_warn(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.1.0")
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ('{"engine_missing":["S7"]}', 0))
    env = rcmd.run("s7runtime", str(tmp_path))
    # S7 is an optional engine → downgrade error→warn, never hard error
    assert env["status"] == "warn"
    assert "S7" in env["engine_missing"]


def test_main_accepts_s7runtime_kind(tmp_path, monkeypatch, capsys):
    _write_desc(tmp_path, "foo", "0.1.0")
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ('{"dead_generics":[],"methods_on_missing_class":[],'
                                   '"nonenforcing_validators":[]}', 0))
    rc = rcmd.main(["--kind", "s7runtime", "--path", str(tmp_path)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "s7runtime"


# ── opt-in real-R e2e ──
def _have_r_with_s7():
    import shutil
    import subprocess
    if shutil.which("Rscript") is None:
        return False
    try:
        out = subprocess.run(
            ["Rscript", "-e",
             'cat(requireNamespace("S7", quietly=TRUE) && '
             'requireNamespace("pkgload", quietly=TRUE) && '
             'requireNamespace("jsonlite", quietly=TRUE))'],
            capture_output=True, text=True, timeout=60)
        return out.stdout.strip() == "TRUE"
    except Exception:
        return False


@pytest.mark.skipif(not _have_r_with_s7(),
                    reason="R + S7 + pkgload + jsonlite not installed")
def test_s7runtime_e2e_detects_dead_generic_and_lax_validator(tmp_path):
    """Real-R e2e: a fixture package with (a) a generic that has NO method (dead)
    and (b) a class whose validator does not reject bad input → both fire."""
    pkg = tmp_path / "s7rt"
    (pkg / "R").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text(textwrap.dedent("""\
        Package: s7rt
        Version: 0.0.1
        Title: S7 runtime fixture
        Imports: S7
        Encoding: UTF-8
    """))
    (pkg / "NAMESPACE").write_text("import(S7)\n")
    (pkg / "R" / "classes.R").write_text(textwrap.dedent("""\
        # A generic with NO registered method anywhere -> dead generic
        dead_gen <- S7::new_generic("dead_gen", "x")

        # A class whose validator NEVER rejects (always passes) -> non-enforcing
        Lax <- S7::new_class("Lax",
          properties = list(x = S7::class_numeric),
          validator = function(self) NULL
        )

        # A well-behaved generic + method (must NOT be flagged dead)
        live_gen <- S7::new_generic("live_gen", "x")
        S7::method(live_gen, Lax) <- function(x, ...) x@x
    """))
    env = rcmd.run("s7runtime", str(pkg))
    assert env["kind"] == "s7runtime", env
    rt = env.get("s7runtime", {})
    assert "dead_gen" in rt.get("dead_generics", []), env
    assert "Lax" in rt.get("nonenforcing_validators", []), env
    # the well-behaved generic must not be flagged dead
    assert "live_gen" not in rt.get("dead_generics", []), env


@pytest.mark.skipif(not _have_r_with_s7(),
                    reason="R + S7 + pkgload + jsonlite not installed")
def test_s7runtime_e2e_on_committed_bad_fixture():
    """Real-R e2e (MINOR 9): the committed s7pkg.bad fixture must actually LOAD
    under S7 (Imports: S7 + import(S7)) so the runtime engine has real coverage —
    it populates dead_generics (ComputeEffect) and nonenforcing_validators
    (NonEnforcing), and does NOT flag the generic that has a method."""
    fixture = Path(__file__).parent / "fixtures" / "s7pkg.bad"
    env = rcmd.run("s7runtime", str(fixture))
    # If the fixture failed to load, messages carries the load error and the
    # lists stay empty — that is exactly the silent-degradation bug MINOR 9 fixes.
    msgs = env.get("messages", [])
    msg_text = msgs if isinstance(msgs, str) else " ".join(msgs)
    assert "failed" not in msg_text.lower(), f"fixture did not load cleanly: {env}"
    rt = env.get("s7runtime", {})
    assert "ComputeEffect" in rt.get("dead_generics", []), env
    assert "NonEnforcing" in rt.get("nonenforcing_validators", []), env
    # external_generic has a method -> must NOT be flagged dead
    assert "external_generic" not in rt.get("dead_generics", []), env


@pytest.mark.skipif(not _have_r_with_s7(),
                    reason="R + S7 + pkgload + jsonlite not installed")
def test_s7runtime_e2e_detects_method_on_missing_class(tmp_path):
    """Real-R e2e: a method registered on an inline, unbound class (nothing can ever
    construct it) is flagged in methods_on_missing_class; a method on a real bound
    class and a base-type method are NOT flagged."""
    pkg = tmp_path / "s7mm"
    (pkg / "R").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text(textwrap.dedent("""\
        Package: s7mm
        Version: 0.0.1
        Title: S7 missing-class fixture
        Imports: S7
        Encoding: UTF-8
    """))
    (pkg / "NAMESPACE").write_text("import(S7)\n")
    (pkg / "R" / "classes.R").write_text(textwrap.dedent("""\
        Real <- S7::new_class("Real")
        # binding name != @name — the idiomatic case that must NOT false-positive
        Aliased <- S7::new_class("DifferentName")
        speak <- S7::new_generic("speak", "x")
        # (ok) method on a real, namespace-bound class
        S7::method(speak, Real) <- function(x, ...) "real"
        # (ok) method on a class bound under a name != its @name
        S7::method(speak, Aliased) <- function(x, ...) "aliased"
        # (ok) method on a base type -> not an S7 class, must NOT be flagged
        S7::method(speak, S7::class_integer) <- function(x, ...) "int"
        # (BAD) method on an inline class with NO namespace binding -> unreachable
        S7::method(speak, S7::new_class("Ghost")) <- function(x, ...) "boo"
    """))
    env = rcmd.run("s7runtime", str(pkg))
    assert env["kind"] == "s7runtime", env
    msgs = env.get("messages", [])
    msg_text = msgs if isinstance(msgs, str) else " ".join(msgs)
    assert "failed" not in msg_text.lower(), f"fixture did not load: {env}"
    rt = env.get("s7runtime", {})
    missing = rt.get("methods_on_missing_class", [])
    classes = [m.get("class") if isinstance(m, dict) else str(m) for m in missing]
    assert "Ghost" in classes, env             # dangling method flagged
    assert "Real" not in classes, env          # real bound class NOT flagged
    # binding-name != @name must NOT false-positive (identity, not @name, resolution)
    assert "DifferentName" not in classes, env
    assert "integer" not in classes, env       # base type NOT flagged


@pytest.mark.skipif(not _have_r_with_s7(),
                    reason="R + S7 + pkgload + jsonlite not installed")
def test_s7runtime_e2e_detects_undeclared_dependency(tmp_path, monkeypatch):
    """Real-R e2e (v2.12.0): a method dispatching on an S7 class from a HELPER
    package that is installed-and-resolvable but NOT in the fixture's DESCRIPTION
    fires `methods_undeclared_dependency`; a method on a properly-`Imports`-declared
    class does NOT fire; a base-type (`methods`/`S7`) class does NOT fire.

    Construction approach: build two tiny installable helper packages — `s7udep`
    (provides `Widget`, left UNdeclared) and `s7dep` (provides `Gadget`, declared in
    Imports) — `R CMD INSTALL` both into a temp library, then a fixture package whose
    generic dispatches on both helper classes plus a base S7 type. The temp lib is
    put on R's path via `R_LIBS` so `load_all` + `asNamespace()` resolve the helpers
    while the fixture's DESCRIPTION deliberately omits `s7udep`.
    """
    libdir = tmp_path / "lib"
    libdir.mkdir()

    def _mk_helper(name, cls):
        src = tmp_path / name
        (src / "R").mkdir(parents=True)
        (src / "DESCRIPTION").write_text(textwrap.dedent(f"""\
            Package: {name}
            Version: 0.0.1
            Title: S7 helper
            Imports: S7
            Encoding: UTF-8
        """))
        (src / "NAMESPACE").write_text(f"import(S7)\nexport({cls})\n")
        (src / "R" / "cls.R").write_text(
            f'{cls} <- S7::new_class("{cls}", package = "{name}")\n')
        rc = subprocess.run(["R", "CMD", "INSTALL", f"--library={libdir}", str(src)],
                            capture_output=True, text=True)
        assert rc.returncode == 0, rc.stderr

    _mk_helper("s7udep", "Widget")   # left UNdeclared in the fixture
    _mk_helper("s7dep", "Gadget")    # declared in the fixture's Imports

    pkg = tmp_path / "s7main"
    (pkg / "R").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text(textwrap.dedent("""\
        Package: s7main
        Version: 0.0.1
        Title: S7 undeclared-dep fixture
        Imports: S7, s7dep
        Encoding: UTF-8
    """))
    (pkg / "NAMESPACE").write_text("import(S7)\n")
    (pkg / "R" / "methods.R").write_text(textwrap.dedent("""\
        speak <- S7::new_generic("speak", "x")
        # (BAD) dispatch on a class from an UNdeclared package -> flagged
        S7::method(speak, s7udep::Widget) <- function(x, ...) "widget"
        # (ok) dispatch on a class from a DECLARED (Imports) package -> not flagged
        S7::method(speak, s7dep::Gadget) <- function(x, ...) "gadget"
        # (ok) dispatch on a base S7 type -> not flagged
        S7::method(speak, S7::class_integer) <- function(x, ...) "int"
    """))

    # put the temp lib on R's search path so the engine resolves the helpers
    existing = os.environ.get("R_LIBS", "")
    monkeypatch.setenv("R_LIBS", f"{libdir}{os.pathsep}{existing}" if existing
                       else str(libdir))

    env = rcmd.run("s7runtime", str(pkg))
    assert env["kind"] == "s7runtime", env
    msgs = env.get("messages", [])
    msg_text = msgs if isinstance(msgs, str) else " ".join(msgs)
    assert "failed" not in msg_text.lower(), f"fixture did not load: {env}"
    rt = env.get("s7runtime", {})
    undecl = rt.get("methods_undeclared_dependency", [])
    by_class = {e.get("class"): e for e in undecl if isinstance(e, dict)}
    assert "Widget" in by_class, env               # undeclared dep flagged
    assert by_class["Widget"]["package"] == "s7udep", env
    assert "Gadget" not in by_class, env           # declared (Imports) NOT flagged
    assert "integer" not in by_class, env          # base type NOT flagged
    # and the undeclared class is NOT mis-reported as a missing class
    miss_classes = [m.get("class") if isinstance(m, dict) else str(m)
                    for m in rt.get("methods_on_missing_class", [])]
    assert "Widget" not in miss_classes, env


def test_run_rhub_rejects_injection_platform(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    # _invoke_r must NOT be reached — validation happens first.
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("R ran!")))
    env = rcmd._run_rhub(str(tmp_path), {"package": "foo", "version": "1.0"},
                         platforms=['x"); cat(1); ("'])
    assert env["status"] == "error"
    assert "Unknown platform" in " ".join(env["messages"])


def test_run_rhub_rejects_unknown_platform(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("R ran!")))
    env = rcmd._run_rhub(str(tmp_path), {"package": "foo"}, platforms=["linux", "nope"])
    assert env["status"] == "error" and "nope" in " ".join(env["messages"])


def test_allowed_platforms_covers_presets():
    # every token in every preset must be in the allow-list (internal consistency)
    for plats in rcmd._RHUB_PRESETS.values():
        for p in plats:
            assert p in rcmd.ALLOWED_RHUB_PLATFORMS


# ── Task 2 (P3): timeouts on the quick Rscript calls ──
import subprocess as _sp


def test_invoke_r_timeout_returns_124(monkeypatch):
    def boom(*a, **k):
        raise _sp.TimeoutExpired(cmd="Rscript", timeout=k.get("timeout", 1))
    monkeypatch.setattr(rcmd.shutil, "which", lambda x: "/usr/bin/Rscript")
    monkeypatch.setattr(rcmd.subprocess, "run", boom)
    out, code = rcmd._invoke_r("1+1", timeout=1)
    assert code == 124 and '"timed_out"' in out


def test_run_surfaces_timeout_as_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda *a, **k: ('{"timed_out": true}', 124))
    env = rcmd.run("check", str(tmp_path))
    assert env["status"] == "error"
    assert any("timed out" in m.lower() for m in env["messages"])

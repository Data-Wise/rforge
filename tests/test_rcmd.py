import json
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


@pytest.mark.parametrize("kind,key", [("lint", "lints"), ("spell", "misspelled"),
                                      ("urlcheck", "broken")])
def test_normalize_quality_warns_when_findings(kind, key):
    assert rcmd.normalize(kind, {key: [{"x": 1}]}, 0, None)["status"] == "warn"
    assert rcmd.normalize(kind, {key: []}, 0, None)["status"] == "ok"


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
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"run_url":"https://x"}', 0))
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
    assert "goodpractice::gp" in rcmd.r_snippet("goodpractice", "/tmp/foo")

def test_normalize_goodpractice_warns_with_items():
    env = rcmd.normalize("goodpractice", {"checks": ["avoid T/F"]}, 0, None)
    assert env["status"] == "warn" and env["goodpractice"]["count"] == 1

def test_normalize_goodpractice_clean_ok():
    assert rcmd.normalize("goodpractice", {"checks": []}, 0, None)["status"] == "ok"

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

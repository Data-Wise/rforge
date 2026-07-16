"""Tests for lib/tidyaudit.py — roxygen completeness + NEWS.md header checks (issue #65)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib import tidyaudit


# ── check_roxygen_completeness ──────────────────────────────────────────────

def _write_r_file(tmp_path, name, content):
    r_dir = tmp_path / "R"
    r_dir.mkdir(exist_ok=True)
    (r_dir / name).write_text(content)


def test_roxygen_no_r_dir_warns(tmp_path):
    env = tidyaudit.check_roxygen_completeness(str(tmp_path))
    assert env["status"] == "warn"
    assert env["findings"] == []


def test_roxygen_exported_function_missing_all_tags(tmp_path):
    _write_r_file(tmp_path, "foo.R",
                 "#' Do the thing\n"
                 "#' @export\n"
                 "do_thing <- function(x) x\n")
    env = tidyaudit.check_roxygen_completeness(str(tmp_path))
    assert env["status"] == "warn"
    assert len(env["findings"]) == 1
    f = env["findings"][0]
    assert f["function"] == "do_thing"
    assert set(f["missing_tags"]) == {"examples", "return", "family"}


def test_roxygen_exported_function_complete_no_finding(tmp_path):
    _write_r_file(tmp_path, "foo.R",
                 "#' Do the thing\n"
                 "#' @param x a thing\n"
                 "#' @return the thing\n"
                 "#' @family thing helpers\n"
                 "#' @examples\n"
                 "#' do_thing(1)\n"
                 "#' @export\n"
                 "do_thing <- function(x) x\n")
    env = tidyaudit.check_roxygen_completeness(str(tmp_path))
    assert env["status"] == "ok"
    assert env["findings"] == []


def test_roxygen_internal_function_not_exported_exempt(tmp_path):
    _write_r_file(tmp_path, "foo.R",
                 "#' Internal helper\n"
                 "helper <- function(x) x\n")
    env = tidyaudit.check_roxygen_completeness(str(tmp_path))
    assert env["findings"] == []


def test_roxygen_partial_missing_tags_lists_only_missing(tmp_path):
    _write_r_file(tmp_path, "foo.R",
                 "#' Do the thing\n"
                 "#' @return the thing\n"
                 "#' @export\n"
                 "do_thing <- function(x) x\n")
    env = tidyaudit.check_roxygen_completeness(str(tmp_path))
    f = env["findings"][0]
    assert set(f["missing_tags"]) == {"examples", "family"}
    assert "return" not in f["missing_tags"]


# ── check_news_header ───────────────────────────────────────────────────────

def _write_desc(tmp_path, version="1.2.3"):
    (tmp_path / "DESCRIPTION").write_text(
        f"Package: testpkg\nVersion: {version}\n")


def test_news_missing_file_warns(tmp_path):
    _write_desc(tmp_path)
    env = tidyaudit.check_news_header(str(tmp_path))
    assert env["status"] == "warn"
    assert env["findings"] == []  # advisory absence, not a finding


def test_news_header_matches_description_version_ok(tmp_path):
    _write_desc(tmp_path, version="1.2.3")
    (tmp_path / "NEWS.md").write_text("## testpkg 1.2.3\n\n* Initial release.\n")
    env = tidyaudit.check_news_header(str(tmp_path))
    assert env["status"] == "ok"
    assert env["findings"] == []


def test_news_header_version_mismatch(tmp_path):
    _write_desc(tmp_path, version="1.2.3")
    (tmp_path / "NEWS.md").write_text("## testpkg 1.2.0\n\n* Old entry.\n")
    env = tidyaudit.check_news_header(str(tmp_path))
    assert env["status"] == "warn"
    f = env["findings"][0]
    assert f["code"] == "news_header_version_mismatch"
    assert f["news_version"] == "1.2.0"
    assert f["description_version"] == "1.2.3"


def test_news_header_wrong_format(tmp_path):
    _write_desc(tmp_path, version="1.2.3")
    (tmp_path / "NEWS.md").write_text("Changes in this version:\n\n* Stuff.\n")
    env = tidyaudit.check_news_header(str(tmp_path))
    assert env["status"] == "warn"
    assert env["findings"][0]["code"] == "news_header_format"


# ── run_all ──────────────────────────────────────────────────────────────────

def test_run_all_aggregates_both_stages(tmp_path):
    _write_desc(tmp_path)
    env = tidyaudit.run_all(str(tmp_path))
    assert env["kind"] == "tidyaudit"
    assert len(env["stages"]) == 2
    assert {s["kind"] for s in env["stages"]} == {"roxygen_completeness", "news_header"}

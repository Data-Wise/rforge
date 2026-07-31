"""Tests for lib/rstatus.py — single R-package session-state reader/differ
(SPEC-restore-finish-commands-2026-07-31.md)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lib import rstatus


# ── parse_rstatus / read_rstatus ────────────────────────────────────────────

def test_parse_rstatus_all_known_fields():
    content = (
        "package: medfit\n"
        "updated: 2026-07-31\n"
        "status: Active\n"
        "version: 0.4.0\n"
        "cran_status: not-submitted\n"
        "last_check: 2026-07-28 PASS\n"
        "last_release: v0.4.0 shipped\n"
        "next: CRAN resubmission\n"
        "blockers: none\n"
    )
    r = rstatus.parse_rstatus(content)
    assert r.package == "medfit"
    assert r.updated == "2026-07-31"
    assert r.status == "Active"
    assert r.version == "0.4.0"
    assert r.cran_status == "not-submitted"
    assert r.last_check == "2026-07-28 PASS"
    assert r.last_release == "v0.4.0 shipped"
    assert r.next == "CRAN resubmission"
    assert r.blockers == "none"


def test_parse_rstatus_missing_fields_are_none():
    r = rstatus.parse_rstatus("package: medfit\n")
    assert r.package == "medfit"
    assert r.next is None
    assert r.blockers is None


def test_parse_rstatus_unknown_field_preserved_in_raw_only():
    r = rstatus.parse_rstatus("package: medfit\ncustom_field: hello\n")
    assert r.raw_fields["custom_field"] == "hello"
    assert not hasattr(r, "custom_field")


def test_parse_rstatus_does_not_match_emoji_box_format():
    """Regression guard for the exact bug found during implementation:
    lib.status.parse_status_file's emoji-box grammar returns empty/None
    against a key:value .STATUS. This module's own parser must actually
    extract fields from the real rforge/craft/savant convention."""
    content = "project: rforge\nupdated: 2026-07-16\nstatus: Active\n"
    r = rstatus.parse_rstatus(content)
    assert r.status == "Active"
    assert r.updated == "2026-07-16"


def test_read_rstatus_missing_file_returns_none(tmp_path):
    assert rstatus.read_rstatus(str(tmp_path)) is None


def test_read_rstatus_reads_real_file(tmp_path):
    (tmp_path / ".STATUS").write_text("package: medfit\nversion: 0.4.0\n")
    r = rstatus.read_rstatus(str(tmp_path))
    assert r is not None
    assert r.package == "medfit"
    assert r.version == "0.4.0"


# ── diff_rstatus (redundant-edit guard) ─────────────────────────────────────

def test_diff_rstatus_no_current_all_fields_are_changes():
    intended = rstatus.RStatus(package="medfit", version="0.4.0")
    changes = rstatus.diff_rstatus(None, intended)
    fields = {c[0] for c in changes}
    assert "package" in fields
    assert "version" in fields


def test_diff_rstatus_timestamp_only_change_is_filtered_out():
    current = rstatus.RStatus(package="medfit", updated="2026-07-16", version="0.4.0")
    intended = rstatus.RStatus(package="medfit", updated="2026-07-31", version="0.4.0")
    assert rstatus.diff_rstatus(current, intended) == []


def test_diff_rstatus_real_change_is_reported_alongside_timestamp():
    current = rstatus.RStatus(package="medfit", updated="2026-07-16", next="old task")
    intended = rstatus.RStatus(package="medfit", updated="2026-07-31", next="new task")
    changes = rstatus.diff_rstatus(current, intended)
    fields = {c[0]: c for c in changes}
    assert "next" in fields
    assert fields["next"] == ("next", "old task", "new task")
    assert "updated" in fields  # timestamp change surfaces too, just not alone


def test_diff_rstatus_no_change_at_all():
    current = rstatus.RStatus(package="medfit", version="0.4.0")
    intended = rstatus.RStatus(package="medfit", version="0.4.0")
    assert rstatus.diff_rstatus(current, intended) == []


# ── parse_news_header ───────────────────────────────────────────────────────

def test_parse_news_header_missing_file(tmp_path):
    result = rstatus.parse_news_header(str(tmp_path))
    assert result == {"found": False, "has_unreleased": False, "top_header": None, "entries": []}


def test_parse_news_header_unreleased_with_entries(tmp_path):
    (tmp_path / "NEWS.md").write_text(
        "# medfit (development version)\n\n"
        "## Unreleased\n\n"
        "- Added bootstrap intervals\n"
        "- Fixed a typo\n\n"
        "## medfit 0.3.0\n\n"
        "- Old entry\n"
    )
    result = rstatus.parse_news_header(str(tmp_path))
    assert result["found"] is True
    assert result["has_unreleased"] is False  # top header is "medfit (development version)"
    assert result["top_header"] == "medfit (development version)"


def test_parse_news_header_top_section_scope_only(tmp_path):
    (tmp_path / "NEWS.md").write_text(
        "## Unreleased\n\n"
        "- New thing\n\n"
        "## medfit 0.3.0\n\n"
        "- Old thing (must not appear in entries)\n"
    )
    result = rstatus.parse_news_header(str(tmp_path))
    assert result["has_unreleased"] is True
    assert result["entries"] == ["New thing"]


def test_parse_news_header_no_headers_at_all(tmp_path):
    (tmp_path / "NEWS.md").write_text("just some prose, no headers\n")
    result = rstatus.parse_news_header(str(tmp_path))
    assert result["found"] is True
    assert result["top_header"] is None
    assert result["entries"] == []


# ── git_snapshot ─────────────────────────────────────────────────────────────

def test_git_snapshot_not_a_repo(tmp_path):
    result = rstatus.git_snapshot(str(tmp_path))
    assert result == {"available": False}


def test_git_snapshot_real_repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True)
    (tmp_path / "README.md").write_text("hi\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(tmp_path), check=True)

    result = rstatus.git_snapshot(str(tmp_path))
    assert result["available"] is True
    assert result["dirty"] is False
    assert "init" in result["last_commit"]

    (tmp_path / "dirty.txt").write_text("x\n")
    result2 = rstatus.git_snapshot(str(tmp_path))
    assert result2["dirty"] is True


# ── build_recap / format_text ────────────────────────────────────────────────

def test_build_recap_not_an_r_package(tmp_path):
    recap = rstatus.build_recap(str(tmp_path))
    assert recap["is_r_package"] is False
    assert "Not an R package" in rstatus.format_text(recap)


def test_build_recap_full_r_package(tmp_path):
    (tmp_path / "DESCRIPTION").write_text(
        "Package: medfit\nVersion: 0.4.0\nTitle: Fit things\n"
    )
    (tmp_path / "NEWS.md").write_text("## Unreleased\n\n- did a thing\n")
    (tmp_path / ".STATUS").write_text("package: medfit\nversion: 0.4.0\nnext: ship it\n")

    recap = rstatus.build_recap(str(tmp_path))
    assert recap["is_r_package"] is True
    assert recap["description"]["version"] == "0.4.0"
    assert recap["news"]["has_unreleased"] is True
    assert recap["rstatus"]["next"] == "ship it"
    assert recap["version_drift"] is None

    text = rstatus.format_text(recap)
    assert "medfit" in text
    assert "ship it" in text


def test_build_recap_version_drift_detected(tmp_path):
    (tmp_path / "DESCRIPTION").write_text("Package: medfit\nVersion: 0.5.0\n")
    (tmp_path / ".STATUS").write_text("package: medfit\nversion: 0.4.0\n")

    recap = rstatus.build_recap(str(tmp_path))
    assert recap["version_drift"] == {"status_version": "0.4.0", "description_version": "0.5.0"}
    assert "drift" in rstatus.format_text(recap)


def test_format_json_round_trips(tmp_path):
    (tmp_path / "DESCRIPTION").write_text("Package: medfit\nVersion: 0.4.0\n")
    recap = rstatus.build_recap(str(tmp_path))
    import json
    parsed = json.loads(rstatus.format_json(recap))
    assert parsed["is_r_package"] is True

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


def test_parse_rstatus_only_unknown_fields_still_returns_object():
    r = rstatus.parse_rstatus("custom_a: x\ncustom_b: y\n")
    assert r.package is None
    assert r.next is None
    assert r.raw_fields == {"custom_a": "x", "custom_b": "y"}


def test_parse_rstatus_blank_line_resets_continuation_scope():
    """Regression guard: a blank line must end the previous field's
    continuation, so trailing freeform prose below a blank line isn't
    silently absorbed into whatever field happened to be last (caught by
    adversarial review — the parser used to never clear current_key)."""
    content = (
        "package: medfit\n"
        "next: ship it\n"
        "\n"
        "Some unrelated freeform notes a human appended below.\n"
        "More notes here.\n"
    )
    r = rstatus.parse_rstatus(content)
    assert r.next == "ship it"
    assert "Some unrelated freeform notes" not in r.raw_fields["next"]


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


def test_diff_rstatus_multiple_simultaneous_real_changes_all_surface():
    current = rstatus.RStatus(
        package="medfit", updated="2026-07-16", next="old next",
        blockers="old blocker", cran_status="not-submitted",
    )
    intended = rstatus.RStatus(
        package="medfit", updated="2026-07-31", next="new next",
        blockers="old blocker", cran_status="resubmission-pending",
    )
    changes = rstatus.diff_rstatus(current, intended)
    fields = {c[0] for c in changes}
    assert fields == {"updated", "next", "cran_status"}


def test_diff_rstatus_bare_construction_wipes_untouched_fields_regression_guard():
    """Documents the exact data-loss bug 3/4 adversarial-review agents caught:
    constructing `intended` as a bare RStatus(...) (what an earlier draft of
    commands/finish.md's own example did) leaves every unmentioned field at
    None, and diff_rstatus reports those as real changes — NOT caught by the
    redundant-edit guard, since other real fields also changed. This is why
    apply_updates() exists and commands/finish.md now mandates it."""
    current = rstatus.RStatus(
        package="medfit", updated="2026-07-16", version="0.4.0",
        cran_status="not-submitted", last_check="2026-07-28 PASS",
        last_release="v0.4.0 shipped", status="Active",
    )
    # The dangerous pattern: only updated/version set, everything else at None.
    intended_bare = rstatus.RStatus(package="medfit", updated="2026-07-31", version="0.4.0")
    changes = rstatus.diff_rstatus(current, intended_bare)
    fields = {c[0]: c for c in changes}
    # cran_status/last_check/last_release/status all silently "change" to None.
    assert fields["cran_status"] == ("cran_status", "not-submitted", None)
    assert fields["last_check"] == ("last_check", "2026-07-28 PASS", None)

    # The safe pattern: apply_updates carries everything forward.
    intended_safe = rstatus.apply_updates(current, updated="2026-07-31")
    assert rstatus.diff_rstatus(current, intended_safe) == []  # timestamp-only, filtered


# ── apply_updates (safe intended-state builder) ─────────────────────────────

def test_apply_updates_from_none_current_uses_only_overrides():
    intended = rstatus.apply_updates(None, package="medfit", version="0.4.0")
    assert intended.package == "medfit"
    assert intended.version == "0.4.0"
    assert intended.next is None


def test_apply_updates_carries_every_field_forward_except_overrides():
    current = rstatus.RStatus(
        package="medfit", updated="2026-07-16", version="0.4.0",
        cran_status="not-submitted", next="old next", blockers="none",
        last_check="2026-07-28 PASS", last_release="v0.4.0", status="Active",
    )
    intended = rstatus.apply_updates(current, updated="2026-07-31", next="new next")
    assert intended.updated == "2026-07-31"
    assert intended.next == "new next"
    # Everything else carried forward verbatim — not silently cleared.
    assert intended.cran_status == "not-submitted"
    assert intended.last_check == "2026-07-28 PASS"
    assert intended.last_release == "v0.4.0"
    assert intended.status == "Active"
    assert intended.blockers == "none"
    assert intended.package == "medfit"


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


def test_parse_news_header_bare_hash_with_no_title(tmp_path):
    """Regression guard: a bare `#` header line (no title text) must still
    match and be treated as a (empty-titled) header, not silently skipped —
    the original regex required >=1 char after the `#`, which dropped this
    case and everything under it from the top-section scope."""
    (tmp_path / "NEWS.md").write_text("#\n\n- an entry under a titleless header\n")
    result = rstatus.parse_news_header(str(tmp_path))
    assert result["found"] is True
    assert result["top_header"] == ""
    assert result["entries"] == ["an entry under a titleless header"]


def test_parse_news_header_present_with_empty_body(tmp_path):
    (tmp_path / "NEWS.md").write_text("## Unreleased\n\n")
    result = rstatus.parse_news_header(str(tmp_path))
    assert result["found"] is True
    assert result["has_unreleased"] is True
    assert result["entries"] == []


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


def test_build_recap_malformed_description_treated_as_not_a_package(tmp_path):
    """A DESCRIPTION file present but with no Package: field (garbage/empty)
    must degrade the same way as a missing DESCRIPTION — lib.discovery's
    parse_description already returns None in that case; build_recap must
    not crash or misreport is_r_package."""
    (tmp_path / "DESCRIPTION").write_text("not a real DCF file\njust prose\n")
    recap = rstatus.build_recap(str(tmp_path))
    assert recap["is_r_package"] is False
    assert recap["description"] is None


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
    (tmp_path / "NEWS.md").write_text("## Unreleased\n\n- did a thing\n")
    (tmp_path / ".STATUS").write_text("package: medfit\nversion: 0.4.0\nnext: ship it\n")

    recap = rstatus.build_recap(str(tmp_path))
    import json
    parsed = json.loads(rstatus.format_json(recap))
    # Assert nested values actually survive serialization, not just the
    # top-level flag — a format_json bug that dropped nested dicts would
    # still have passed the original single-assertion version of this test.
    assert parsed["is_r_package"] is True
    assert parsed["description"]["package"] == "medfit"
    assert parsed["description"]["version"] == "0.4.0"
    assert parsed["news"]["entries"] == ["did a thing"]
    assert parsed["rstatus"]["next"] == "ship it"

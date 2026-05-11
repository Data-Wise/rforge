"""Tests for lib/status.py."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta

import pytest

from lib.status import (
    EcosystemStatus,
    PackageStatus,
    StatusFileSummary,
    aggregate_status,
    calculate_health_score,
    format_json,
    format_text,
    parse_status_file,
)


# ───────────────────────── aggregate_status ─────────────────────────


def test_aggregate_status_empty_ecosystem(tmp_path):
    result = aggregate_status(tmp_path)
    assert isinstance(result, EcosystemStatus)
    assert result.packages == []
    assert result.health_score == 100  # convention: no packages → perfect
    # `None` (not `[]`) signals blocker-detection is not implemented yet
    # (deferred to v1.4.0). `[]` would mean "checked, found none".
    assert result.blocking_issues is None
    assert result.ecosystem == str(tmp_path.resolve())


def test_aggregate_status_with_packages_no_status_file(tmp_path, make_pkg):
    make_pkg("a")
    make_pkg("b")
    result = aggregate_status(tmp_path)
    assert len(result.packages) == 2
    for pkg in result.packages:
        assert pkg.check_status == "unknown"
        assert pkg.test_status == "unknown"
        assert pkg.status_file is None
        assert pkg.last_updated is None
    # Two unknowns each → score drops noticeably from 100
    assert result.health_score < 100


def test_aggregate_status_reads_status_file(tmp_path, make_pkg):
    pkg = make_pkg("solo")
    (pkg / ".STATUS").write_text(
        "🎯 CURRENT STATUS\nRefactor parser\n\n"
        "📊 PROGRESS\n42%\n"
    )
    result = aggregate_status(tmp_path)
    assert len(result.packages) == 1
    status = result.packages[0].status_file
    assert status is not None
    assert status.current_focus == "Refactor parser"
    assert status.progress == 42
    assert result.packages[0].last_updated is not None


def test_aggregate_status_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        aggregate_status(tmp_path / "nope")


# ───────────────────────── parse_status_file ─────────────────────────


def test_parse_status_file_extracts_focus_and_progress():
    content = (
        "🎯 CURRENT STATUS\n"
        "Wiring up the parser\n"
        "\n"
        "📊 PROGRESS\n"
        "30%\n"
        "\n"
        "Phase B.2: implementation\n"
        "\n"
        "✅ JUST COMPLETED\n"
        "- wrote dataclasses\n"
        "- ported regex extractors\n"
        "\n"
        "📋 NEXT ACTIONS\n"
        "1) write tests\n"
        "2) wire CLI\n"
        "\n"
        "⏰ LAST UPDATED 2026-05-09\n"
    )
    summary = parse_status_file(content)
    assert summary.current_focus == "Wiring up the parser"
    assert summary.progress == 30
    assert summary.phase == "B.2"
    assert "wrote dataclasses" in summary.just_completed
    assert "ported regex extractors" in summary.just_completed
    assert summary.next_actions == ["write tests", "wire CLI"]
    assert summary.last_updated == datetime(2026, 5, 9)


def test_parse_status_file_empty_returns_default_summary():
    summary = parse_status_file("")
    assert summary.current_focus is None
    assert summary.progress is None
    assert summary.phase is None
    assert summary.just_completed == []
    assert summary.next_actions == []
    assert summary.last_updated is None


def test_status_file_max_progress():
    """When multiple `\\d+%` appear, the parser keeps the largest."""
    content = "Random progress: 10%, 75%, then 33% later"
    summary = parse_status_file(content)
    assert summary.progress == 75


# ───────────────────────── calculate_health_score ─────────────────────────


def test_health_score_empty_packages_returns_100():
    assert calculate_health_score([]) == 100


def test_health_score_perfect_when_all_known():
    """If every package is known-passing on both axes, no deductions apply."""
    pkgs = [
        PackageStatus(name="a", version="1.0", path="/a",
                      check_status="passing", test_status="passing"),
        PackageStatus(name="b", version="1.0", path="/b",
                      check_status="passing", test_status="passing"),
    ]
    assert calculate_health_score(pkgs) == 100


def test_health_score_degrades_on_unknown():
    pkgs = [
        PackageStatus(name="a", version="1.0", path="/a"),
        PackageStatus(name="b", version="1.0", path="/b"),
    ]
    # Two unknowns × (0.15 + 0.10) × 50 = 25-point deduction
    assert calculate_health_score(pkgs) == 75


def test_health_score_degrades_on_staleness():
    stale_when = datetime.now() - timedelta(days=30)
    pkgs = [
        PackageStatus(
            name="a", version="1.0", path="/a",
            check_status="passing", test_status="passing",
            last_updated=stale_when,
        ),
    ]
    # Staleness only: 0.10 × 100 = 10 point deduction → 90
    assert calculate_health_score(pkgs) == 90


def test_health_score_floor_is_zero():
    pkgs = [
        PackageStatus(name="a", version="1.0", path="/a",
                      check_status="errors", test_status="failing"),
    ]
    score = calculate_health_score(pkgs)
    assert 0 <= score <= 100


# ───────────────────────── Formatters ─────────────────────────


def test_format_text_includes_health_score(tmp_path, make_pkg):
    make_pkg("solo")
    result = aggregate_status(tmp_path)
    rendered = format_text(result)
    assert "Health score:" in rendered
    assert "solo" in rendered
    assert "ECOSYSTEM STATUS" in rendered


def test_format_text_handles_empty_ecosystem(tmp_path):
    result = aggregate_status(tmp_path)
    rendered = format_text(result)
    assert "no packages discovered" in rendered
    assert "Health score: 100/100" in rendered


def test_format_json_round_trip(tmp_path, make_pkg):
    pkg = make_pkg("solo")
    (pkg / ".STATUS").write_text("🎯 CURRENT STATUS\nDoing stuff\n\n📊 50%\n")
    result = aggregate_status(tmp_path)
    payload = format_json(result)
    parsed = json.loads(payload)  # must not raise
    assert parsed["health_score"] == result.health_score
    assert parsed["ecosystem"] == result.ecosystem
    assert len(parsed["packages"]) == 1
    assert parsed["packages"][0]["status_file"]["progress"] == 50


def test_to_dict_methods_are_json_serializable(tmp_path, make_pkg):
    make_pkg("a")
    result = aggregate_status(tmp_path)
    # Round-trip via json with default=str (datetime → ISO string)
    payload = json.dumps(result.to_dict(), default=str)
    parsed = json.loads(payload)
    assert "packages" in parsed
    assert parsed["packages"][0]["check_status"] == "unknown"


# ───────────────────────── CLI ─────────────────────────


def test_status_cli_exits_1_on_missing_path(tmp_path):
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        ["python3", "-m", "lib.status",
         "--path", str(tmp_path / "nope"), "--format", "json"],
        cwd=repo_root, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr
    assert result.stdout == ""

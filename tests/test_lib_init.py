"""Tests for lib/init.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.init import (
    InitResult,
    _state_path_for,
    format_json,
    format_text,
    init_context,
)


# ───────────────────────── helpers ─────────────────────────


def _fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


# ───────────────────────── state file creation ─────────────────────────


def test_init_creates_state_file(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo", "1.0.0")

    result = init_context(path=pkg, home=str(home))

    assert result.was_initialized is False
    assert result.state_path == home / ".rforge" / "context.json"
    assert result.state_path.is_file()


def test_init_creates_rforge_directory(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo")

    assert not (home / ".rforge").exists()
    init_context(path=pkg, home=str(home))
    rforge_dir = home / ".rforge"
    assert rforge_dir.is_dir()
    # Mode bits (lower 9 bits) should include 0o755 for owner.
    # On macOS / Linux umask may strip group/other write — we only assert
    # owner rwx is present.
    assert (rforge_dir.stat().st_mode & 0o700) == 0o700


def test_init_idempotent_returns_already_initialized(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo", "2.0.0")

    first = init_context(path=pkg, home=str(home))
    second = init_context(path=pkg, home=str(home))

    assert first.was_initialized is False
    assert second.was_initialized is True
    assert "Already initialized" in second.message


def test_init_quick_mode_skips_already_initialized_guard(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo")

    init_context(path=pkg, home=str(home))
    quick_result = init_context(path=pkg, home=str(home), quick=True)

    # Quick re-runs always treat themselves as a fresh write.
    assert quick_result.was_initialized is False
    assert quick_result.quick_mode is True
    assert "Mode:    quick" in quick_result.message


# ───────────────────────── DESCRIPTION detection ─────────────────────────


def test_init_detects_package_from_description(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("medfit", "1.2.3")

    result = init_context(path=pkg, home=str(home))

    assert result.package_name == "medfit"
    assert result.package_version == "1.2.3"

    on_disk = json.loads(result.state_path.read_text())
    assert on_disk["package"] == "medfit"
    assert on_disk["version"] == "1.2.3"


def test_init_no_description_returns_none_package(tmp_path):
    home = _fake_home(tmp_path)
    empty = tmp_path / "empty"
    empty.mkdir()

    result = init_context(path=empty, home=str(home))

    assert result.package_name is None
    assert result.package_version is None
    # State file still written — context tracks the path even sans package.
    on_disk = json.loads(result.state_path.read_text())
    assert on_disk["package"] is None
    assert on_disk["path"] == str(empty.resolve())


def test_init_path_mismatch_overwrites(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg_a = make_pkg("pkgA")
    pkg_b = make_pkg("pkgB")

    init_context(path=pkg_a, home=str(home))
    result_b = init_context(path=pkg_b, home=str(home))

    # Per-cwd context: switching path → fresh detection, not "already init".
    assert result_b.was_initialized is False
    on_disk = json.loads(result_b.state_path.read_text())
    assert on_disk["path"] == str(pkg_b.resolve())
    assert on_disk["package"] == "pkgB"


# ───────────────────────── persistence schema ─────────────────────────


def test_state_file_is_valid_json(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo", "0.9.0")

    result = init_context(path=pkg, home=str(home))
    data = json.loads(result.state_path.read_text())

    # Required fields per MCP schema.
    for key in (
        "package",
        "version",
        "path",
        "detected_at",
        "initialized",
        "last_tool",
        "current_workflow",
        "last_plan",
    ):
        assert key in data, f"missing key: {key}"
    assert data["initialized"] is True
    assert data["last_tool"] == "init"


def test_init_via_env_home(tmp_path, make_pkg, monkeypatch):
    """When home=None, HOME env var drives the state path."""
    fake_home = _fake_home(tmp_path)
    monkeypatch.setenv("HOME", str(fake_home))
    pkg = make_pkg("foo")

    result = init_context(path=pkg)  # no explicit home
    assert result.state_path == _state_path_for(None)
    assert result.state_path.parent == fake_home / ".rforge"


def test_detected_at_preserved_across_reinit(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo")

    first = init_context(path=pkg, home=str(home), quick=True)
    first_detected = json.loads(first.state_path.read_text())["detected_at"]

    second = init_context(path=pkg, home=str(home), quick=True)
    second_detected = json.loads(second.state_path.read_text())["detected_at"]

    assert first_detected == second_detected


# ───────────────────────── formatters ─────────────────────────


def test_format_text_shows_package_and_path(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo", "1.0.0")
    result = init_context(path=pkg, home=str(home))

    text = format_text(result)
    assert "foo" in text
    assert "1.0.0" in text
    assert str(pkg.resolve()) in text
    assert "State:" in text


def test_format_json_round_trip(tmp_path, make_pkg):
    home = _fake_home(tmp_path)
    pkg = make_pkg("foo", "0.1.0")
    result = init_context(path=pkg, home=str(home))

    payload = format_json(result)
    parsed = json.loads(payload)
    assert parsed["package_name"] == "foo"
    assert parsed["package_version"] == "0.1.0"
    assert parsed["was_initialized"] is False
    assert parsed["state_path"] == str(result.state_path)

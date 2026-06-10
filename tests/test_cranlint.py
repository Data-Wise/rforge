"""Tests for lib/cranlint.py — pure-Python CRAN-incoming metadata + structure checks.

Covers Tier 4 of SPEC-cran-incoming-hardening-2026-06-10:
  4a  lint_description()       — DESCRIPTION incoming nits (RESEARCH §A.5)
  4b  check_build_hygiene()    — non-.Rbuildignore'd planning docs (RESEARCH §A.6)
  4c  check_planning_consistency() — advisory staleness / dangling-ref

All checks are advisory and must NEVER raise on missing/unparseable inputs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib import cranlint


# ───────────────────────── helpers ─────────────────────────


def _finding_codes(env: dict) -> set[str]:
    """Collect the `code` of every finding row in an envelope."""
    return {row.get("code") for row in env.get("findings", [])}


def _write_desc(tmp_path: Path, body: str) -> Path:
    (tmp_path / "DESCRIPTION").write_text(body, encoding="utf-8")
    return tmp_path


# ───────────────────────── 4a: lint_description ─────────────────────────


CLEAN_DESC = """\
Package: cleanpkg
Title: Robust Tools for Tidy Statistical Workflows
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides a small set of helpers for tidy statistical
    workflows, including summaries and plots. The helpers compose
    cleanly with the pipe.
License: MIT + file LICENSE
Encoding: UTF-8
"""


def test_clean_description_fires_no_advisories(tmp_path):
    _write_desc(tmp_path, CLEAN_DESC)
    env = cranlint.lint_description(tmp_path)
    assert env["kind"] == "description"
    assert env["status"] == "ok"
    assert env["findings"] == []
    assert env["engine_missing"] == []


def test_author_without_authors_at_r_fires(tmp_path):
    body = """\
Package: oldpkg
Title: Some Helpers for Data Work That Are Useful
Version: 0.1.0
Author: Ada Lovelace
Maintainer: Ada Lovelace <ada@example.com>
Description: Provides helpers for data work and related chores.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert env["status"] == "warn"
    assert "authors_at_r" in _finding_codes(env)


def test_description_without_trailing_period_fires(tmp_path):
    body = """\
Package: nodotpkg
Title: Robust Tools for Tidy Statistical Workflows
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides a set of helpers for tidy statistical workflows
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert env["status"] == "warn"
    assert "description_sentence" in _finding_codes(env)


def test_title_echoes_package_name_fires(tmp_path):
    body = """\
Package: echopkg
Title: echopkg
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides a set of helpers for tidy statistical workflows.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert env["status"] == "warn"
    assert "title_weak" in _finding_codes(env)


def test_missing_description_degrades_to_warn_no_exception(tmp_path):
    # No DESCRIPTION file at all.
    env = cranlint.lint_description(tmp_path)
    assert env["kind"] == "description"
    assert env["status"] == "warn"
    assert env["messages"]  # has a clear reason
    assert env["engine_missing"] == []


# ───────────────────────── 4b: check_build_hygiene ─────────────────────────


def _make_pkg(tmp_path: Path, rbuildignore: str | None) -> Path:
    (tmp_path / "DESCRIPTION").write_text("Package: hyg\nVersion: 0.1.0\n", encoding="utf-8")
    (tmp_path / "NAMESPACE").write_text("export(foo)\n", encoding="utf-8")
    (tmp_path / "R").mkdir()
    (tmp_path / "R" / "foo.R").write_text("foo <- function() 1\n", encoding="utf-8")
    (tmp_path / "specs").mkdir()
    (tmp_path / "specs" / "SPEC.md").write_text("# spec\n", encoding="utf-8")
    (tmp_path / "BRAINSTORM.md").write_text("# brainstorm\n", encoding="utf-8")
    (tmp_path / ".STATUS").write_text("status\n", encoding="utf-8")
    if rbuildignore is not None:
        (tmp_path / ".Rbuildignore").write_text(rbuildignore, encoding="utf-8")
    return tmp_path


def test_build_hygiene_flags_unignored_planning_docs(tmp_path):
    # .Rbuildignore covers only specs/ — BRAINSTORM.md and .STATUS remain.
    _make_pkg(tmp_path, rbuildignore="^specs$\n")
    env = cranlint.check_build_hygiene(tmp_path)
    assert env["kind"] == "build-hygiene"
    flagged = {row["entry"] for row in env["findings"]}
    assert "BRAINSTORM.md" in flagged
    assert ".STATUS" in flagged
    # specs/ is ignored → not flagged
    assert "specs" not in flagged
    # standard package entries are never flagged
    assert "R" not in flagged
    assert "DESCRIPTION" not in flagged
    assert "NAMESPACE" not in flagged
    assert env["status"] == "warn"


def test_build_hygiene_suggests_regex_for_each_flag(tmp_path):
    _make_pkg(tmp_path, rbuildignore="^specs$\n")
    env = cranlint.check_build_hygiene(tmp_path)
    by_entry = {row["entry"]: row for row in env["findings"]}
    # each flagged entry carries a suggested anchored regex
    assert by_entry["BRAINSTORM.md"]["suggest"].startswith("^")
    assert by_entry["BRAINSTORM.md"]["suggest"].endswith("$")
    assert "BRAINSTORM" in by_entry["BRAINSTORM.md"]["suggest"]


def test_build_hygiene_all_ignored_is_ok(tmp_path):
    _make_pkg(tmp_path, rbuildignore="^specs$\n^BRAINSTORM.*\\.md$\n^\\.STATUS$\n")
    env = cranlint.check_build_hygiene(tmp_path)
    assert env["findings"] == []
    assert env["status"] == "ok"


def test_build_hygiene_missing_rbuildignore_degrades_to_warn(tmp_path):
    _make_pkg(tmp_path, rbuildignore=None)
    env = cranlint.check_build_hygiene(tmp_path)
    # No .Rbuildignore → planning docs all flagged, but never an exception,
    # and the stage stays a warn (advisory).
    assert env["status"] == "warn"
    flagged = {row["entry"] for row in env["findings"]}
    assert "BRAINSTORM.md" in flagged


def test_build_hygiene_missing_package_dir_no_exception(tmp_path):
    missing = tmp_path / "nope"
    env = cranlint.check_build_hygiene(missing)
    assert env["kind"] == "build-hygiene"
    assert env["status"] == "warn"
    assert env["engine_missing"] == []


# ───────────────────────── 4c: planning consistency ─────────────────────────


def test_planning_consistency_never_blocks(tmp_path):
    (tmp_path / "DESCRIPTION").write_text("Package: p\nVersion: 0.1.0\n", encoding="utf-8")
    env = cranlint.check_planning_consistency(tmp_path)
    assert env["kind"] == "docs-consistency"
    assert env["status"] in ("ok", "warn")
    assert env["engine_missing"] == []


def test_planning_consistency_missing_dir_no_exception(tmp_path):
    env = cranlint.check_planning_consistency(tmp_path / "nope")
    assert env["status"] == "warn"


# ───────────────────────── CLI smoke ─────────────────────────


def test_cli_emits_json(tmp_path):
    _write_desc(tmp_path, CLEAN_DESC)
    proc = subprocess.run(
        [sys.executable, "-m", "lib.cranlint", "--path", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    # the CLI rolls the three Tier-4 stages into one object
    assert "stages" in payload or "kind" in payload

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


# ───────────────────────── 4b-ext: tarball inspection (v2.17.0) ─────────────────────────

def _make_tarball(tmp_path: Path, names: list[str]) -> Path:
    """Create a minimal gzipped tar archive with the given member names."""
    tarball = tmp_path / "pkg_1.0.tar.gz"
    import tarfile
    with tarfile.open(tarball, "w:gz") as tf:
        for name in names:
            # TarInfo with size 0, isfile.
            info = tarfile.TarInfo(name=name)
            tf.addfile(info, b"")
    return tarball


def test_build_hygiene_tarball_inspection_flags_quarto(tmp_path):
    _make_pkg(tmp_path, rbuildignore="^specs$\n^BRAINSTORM.*\\.md$\n^\\.STATUS$\n")
    tarball = _make_tarball(tmp_path, ["pkg/vignettes/.quarto/_freeze/index.qmd"])
    env = cranlint.check_build_hygiene(tmp_path, tarball_path=tarball)
    codes = _finding_codes(env)
    assert "tarball_build_artifact" in codes
    assert any(".quarto" in row["message"] for row in env["findings"])


def test_build_hygiene_tarball_inspection_flags_html(tmp_path):
    _make_pkg(tmp_path, rbuildignore="^specs$\n^BRAINSTORM.*\\.md$\n^\\.STATUS$\n")
    tarball = _make_tarball(tmp_path, ["pkg/vignettes/intro.html"])
    env = cranlint.check_build_hygiene(tmp_path, tarball_path=tarball)
    assert "tarball_build_artifact" in _finding_codes(env)


def test_build_hygiene_tarball_inspection_clean_is_ok(tmp_path):
    _make_pkg(tmp_path, rbuildignore="^specs$\n^BRAINSTORM.*\\.md$\n^\\.STATUS$\n")
    tarball = _make_tarball(tmp_path, ["pkg/DESCRIPTION", "pkg/R/foo.R"])
    env = cranlint.check_build_hygiene(tmp_path, tarball_path=tarball)
    assert env["status"] == "ok"


def test_build_hygiene_tarball_inspection_degrades_on_bad_tarball(tmp_path):
    _make_pkg(tmp_path, rbuildignore="^specs$\n^BRAINSTORM.*\\.md$\n^\\.STATUS$\n")
    bad = tmp_path / "not-a-tarball.tar.gz"
    bad.write_text("not gzipped tar data")
    env = cranlint.check_build_hygiene(tmp_path, tarball_path=bad)
    assert "tarball_unreadable" in _finding_codes(env)


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


# ───────────────────────── G2: Language field lint ─────────────────────────


def test_lint_description_language_missing(tmp_path):
    """DESCRIPTION without Language:, with vignettes/ → language_missing."""
    (tmp_path / "vignettes").mkdir()
    body = """\
Package: langpkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides helpers for statistical work. Very useful.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert env["status"] == "warn"
    assert "language_missing" in _finding_codes(env)


def test_lint_description_language_missing_no_docs_skip(tmp_path):
    """DESCRIPTION without Language:, no vignettes/ or man/ → no finding."""
    body = """\
Package: nodocspar
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides helpers for statistical work. Very useful.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "language_missing" not in _finding_codes(env)


def test_lint_description_language_present(tmp_path):
    """Language: en-US with docs dirs → no language_missing finding."""
    (tmp_path / "man").mkdir()
    body = """\
Package: langok
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides helpers for statistical work. Very useful.
License: MIT + file LICENSE
Language: en-US
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "language_missing" not in _finding_codes(env)


# ───────────────────────── G3: DOI format lint ─────────────────────────


def test_doi_format_bare_doi(tmp_path):
    """Description with bare doi:10.xxx → doi_format finding."""
    body = """\
Package: doipkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Based on methods by Smith (2020). See doi:10.1000/xyz for details.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "doi_format" in _finding_codes(env)


def test_doi_format_bare_url(tmp_path):
    """Description with bare https://doi.org/... → doi_format finding."""
    body = """\
Package: doiurlpkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: See https://doi.org/10.1000/xyz for details.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "doi_format" in _finding_codes(env)


def test_doi_format_wrapped_ok(tmp_path):
    """<doi:10.xxx> angle-bracket form → no doi_format finding."""
    body = """\
Package: doiwrappedpkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: See <doi:10.1000/xyz> for more details.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "doi_format" not in _finding_codes(env)


def test_doi_format_markdown_link_ok(tmp_path):
    """(https://doi.org/...) paren-wrapped form → no doi_format finding."""
    body = """\
Package: doimdpkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: See (https://doi.org/10.1000/xyz) for more details.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "doi_format" not in _finding_codes(env)


def test_doi_format_url_curly_ok(tmp_path):
    """\\url{https://doi.org/...} curly-brace Rd form → no doi_format finding."""
    body = r"""Package: doicurlypkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: See \url{https://doi.org/10.1000/xyz} for more details.
License: MIT + file LICENSE
"""
    _write_desc(tmp_path, body)
    env = cranlint.lint_description(tmp_path)
    assert "doi_format" not in _finding_codes(env)


# ───────────────────────── G5: testthat edition ─────────────────────────


def _write_desc_with_testthat(tmp_path: Path, extra_fields: str = "") -> Path:
    """Write a DESCRIPTION with a tests/testthat/ directory."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "testthat").mkdir()
    body = f"""\
Package: ttpkg
Title: Some Wonderful Tools for Statistical Work
Version: 0.1.0
Authors@R: person("Ada", "Lovelace", email = "ada@example.com",
    role = c("aut", "cre", "cph"))
Description: Provides helpers for statistical work. Very useful.
License: MIT + file LICENSE
{extra_fields}"""
    return _write_desc(tmp_path, body)


def test_check_test_config_missing(tmp_path):
    """No Config/testthat/edition → testthat_edition_missing."""
    _write_desc_with_testthat(tmp_path)
    env = cranlint.check_test_config(tmp_path)
    assert env["kind"] == "test_config"
    assert env["status"] == "warn"
    assert "testthat_edition_missing" in _finding_codes(env)


def test_check_test_config_edition2(tmp_path):
    """Config/testthat/edition: 2 → testthat_edition_outdated."""
    _write_desc_with_testthat(tmp_path, "Config/testthat/edition: 2")
    env = cranlint.check_test_config(tmp_path)
    assert env["status"] == "warn"
    assert "testthat_edition_outdated" in _finding_codes(env)


def test_check_test_config_edition3(tmp_path):
    """Config/testthat/edition: 3 → clean ok."""
    _write_desc_with_testthat(tmp_path, "Config/testthat/edition: 3")
    env = cranlint.check_test_config(tmp_path)
    assert env["status"] == "ok"
    assert env["findings"] == []


def test_check_test_config_no_description(tmp_path):
    """tests/testthat/ present but no DESCRIPTION → warn envelope, no raise."""
    (tmp_path / "tests" / "testthat").mkdir(parents=True)
    env = cranlint.check_test_config(tmp_path)
    assert env["kind"] == "test_config"
    assert env["status"] == "warn"
    assert env["engine_missing"] == []


def test_cranlint_cli_check_test_config(tmp_path):
    """Invoke python3 -m lib.cranlint check_test_config . via subprocess → valid JSON."""
    _write_desc_with_testthat(tmp_path)
    proc = subprocess.run(
        [sys.executable, "-m", "lib.cranlint", "check_test_config", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parent.parent),
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert "kind" in payload
    assert payload["kind"] == "test_config"

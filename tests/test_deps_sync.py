"""Tests for lib/deps_sync.py — intra-package DESCRIPTION↔usage reconciliation.

Covers SPEC-r-deps-sync-2026-06-10:
  - missing            (used in R/, undeclared → Imports)
  - misclassified      (Suggests used unconditionally in R/ → Imports)  ← the cran-incoming class
  - missing_suggests   (tests/vignettes-only usage, undeclared → Suggests)
  - unused             (declared, no usage → advisory)
  - guarded use is NOT flagged as misclassified
  - never raises on a missing/unparseable DESCRIPTION
  - --write applies unambiguous changes only
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import deps_sync


# ───────────────────────── helpers ─────────────────────────


def _codes(env: dict) -> set[str]:
    return {f["kind"] for f in env.get("findings", [])}


def _pkgs(env: dict, kind: str) -> set[str]:
    return {f["package"] for f in env.get("findings", []) if f["kind"] == kind}


def _mkpkg(tmp_path: Path, *, desc: str, r: dict | None = None,
           tests: dict | None = None, namespace: str | None = None) -> Path:
    (tmp_path / "DESCRIPTION").write_text(desc, encoding="utf-8")
    for sub, files in (("R", r or {}), ("tests/testthat", tests or {})):
        if files:
            d = tmp_path / sub
            d.mkdir(parents=True, exist_ok=True)
            for name, body in files.items():
                (d / name).write_text(body, encoding="utf-8")
    if namespace is not None:
        (tmp_path / "NAMESPACE").write_text(namespace, encoding="utf-8")
    return tmp_path


_DESC_BASE = """\
Package: demo
Title: A Demo Package
Version: 0.1.0
Imports:
    rlang
Suggests:
    testthat
"""


# ───────────────────────── findings ─────────────────────────


def test_missing_import(tmp_path):
    """A package used in R/ but declared nowhere → missing (add to Imports)."""
    pkg = _mkpkg(tmp_path, desc=_DESC_BASE,
                 r={"f.R": "f <- function(x) glue::glue('{x}')\n"})
    env = deps_sync.reconcile(pkg)
    assert "missing" in _codes(env)
    assert "glue" in _pkgs(env, "missing")
    assert "glue" in env["patch"]["add_imports"]


def test_misclassified_suggests_used_in_R(tmp_path):
    """The cran-incoming class: a Suggests pkg used unconditionally in R/ → Imports."""
    desc = _DESC_BASE.replace("    testthat\n", "    testthat,\n    MASS\n")
    pkg = _mkpkg(tmp_path, desc=desc,
                 r={"boot.R": "g <- function(n) MASS::mvrnorm(n, 0, 1)\n"})
    env = deps_sync.reconcile(pkg)
    assert "misclassified" in _codes(env)
    assert "MASS" in _pkgs(env, "misclassified")
    assert "MASS" in env["patch"]["move_to_imports"]
    assert any("Imports" in m for m in env["messages"])


def test_guarded_suggests_not_flagged(tmp_path):
    """A Suggests pkg used *guarded* (requireNamespace) in R/ is OK — not misclassified."""
    desc = _DESC_BASE.replace("    testthat\n", "    testthat,\n    MASS\n")
    pkg = _mkpkg(tmp_path, desc=desc, r={"boot.R": (
        "g <- function(n) {\n"
        "  if (requireNamespace('MASS', quietly = TRUE)) MASS::mvrnorm(n, 0, 1)\n"
        "}\n"
    )})
    env = deps_sync.reconcile(pkg)
    assert "MASS" not in _pkgs(env, "misclassified")


def test_missing_suggests_from_tests(tmp_path):
    """A pkg used only in tests/ → missing_suggests (add to Suggests, not Imports)."""
    pkg = _mkpkg(tmp_path, desc=_DESC_BASE,
                 r={"f.R": "f <- function(x) rlang::abort('no')\n"},
                 tests={"test-f.R": "withr::with_tempdir(testthat::test_that('x', {}))\n"})
    env = deps_sync.reconcile(pkg)
    assert "withr" in _pkgs(env, "missing_suggests")
    assert "withr" not in env["patch"]["add_imports"]


def test_unused_declared(tmp_path):
    """A declared dep with no usage → unused (advisory, in remove_candidates)."""
    desc = _DESC_BASE.replace("    rlang\n", "    rlang,\n    neverused\n")
    pkg = _mkpkg(tmp_path, desc=desc, r={"f.R": "f <- function(x) rlang::abort('no')\n"})
    env = deps_sync.reconcile(pkg)
    assert "neverused" in _pkgs(env, "unused")
    assert "neverused" in env["patch"]["remove_candidates"]


def test_base_packages_ignored(tmp_path):
    """Base-priority packages (stats, utils, …) are never flagged."""
    pkg = _mkpkg(tmp_path, desc=_DESC_BASE,
                 r={"f.R": "f <- function(x) stats::sd(utils::head(x))\n"})
    env = deps_sync.reconcile(pkg)
    assert "stats" not in {f["package"] for f in env["findings"]}
    assert "utils" not in {f["package"] for f in env["findings"]}


def test_clean_package_is_ok(tmp_path):
    """Everything used is declared and vice-versa → status ok, no findings."""
    pkg = _mkpkg(tmp_path, desc=_DESC_BASE,
                 r={"f.R": "f <- function(x) rlang::abort('no')\n"},
                 tests={"test-f.R": "testthat::test_that('x', {})\n"})
    env = deps_sync.reconcile(pkg)
    assert env["status"] == "ok"
    assert env["findings"] == []


def test_namespace_counts_as_imports(tmp_path):
    """NAMESPACE importFrom is the generated truth → Imports-level usage."""
    pkg = _mkpkg(tmp_path, desc=_DESC_BASE, r={"f.R": "f <- function(x) x\n"},
                 namespace="importFrom(cli, cli_alert)\nexport(f)\n")
    env = deps_sync.reconcile(pkg)
    assert "cli" in _pkgs(env, "missing")


# ───────────────────────── robustness ─────────────────────────


def test_no_description_warns_no_raise(tmp_path):
    env = deps_sync.reconcile(tmp_path)  # empty dir
    assert env["status"] == "warn"
    assert env["findings"] == []
    assert env["engine_missing"] == []


# ───────────────────────── --write ─────────────────────────


def test_write_applies_unambiguous_only(tmp_path):
    """--write adds the missing import + moves the misclassified; leaves unused alone."""
    desc = _DESC_BASE.replace("    testthat\n", "    testthat,\n    MASS,\n    neverused\n")
    pkg = _mkpkg(tmp_path, desc=desc,
                 r={"f.R": "f <- function(x) MASS::mvrnorm(x) + glue::glue('a')\n"})
    env = deps_sync.deps_sync(pkg, write=True)
    body = (tmp_path / "DESCRIPTION").read_text()
    # glue added to Imports; MASS moved Suggests→Imports
    assert "glue" in body
    imports_block = body.split("Imports:")[1].split("Suggests:")[0]
    assert "MASS" in imports_block and "glue" in imports_block
    # neverused (advisory removal) is NOT auto-removed
    assert "neverused" in body


def test_write_preserves_version_constraints(tmp_path):
    """--write must NOT silently drop (>= x.y.z) floors on untouched deps.

    Regression for the data-corruption bug: adding one dep rewrote the whole
    Imports/Suggests block from discovery's name-only parse, stripping every
    version constraint — including in fields the patch never targeted.
    """
    desc = """\
Package: demo
Title: A Demo Package
Version: 0.1.0
Imports:
    stats,
    dplyr (>= 1.1.0)
Suggests:
    testthat (>= 3.0.0)
"""
    # add one unrelated Imports dep (tibble) via usage scan
    pkg = _mkpkg(tmp_path, desc=desc,
                 r={"f.R": "f <- function(x) dplyr::filter(x) + tibble::tibble()\n"})
    deps_sync.deps_sync(pkg, write=True)
    body = (tmp_path / "DESCRIPTION").read_text()
    # the new dep landed
    assert "tibble" in body
    # both pre-existing constraints SURVIVE verbatim
    assert "dplyr (>= 1.1.0)" in body, body
    assert "testthat (>= 3.0.0)" in body, body


def test_dry_run_writes_nothing(tmp_path):
    desc = _DESC_BASE
    pkg = _mkpkg(tmp_path, desc=desc, r={"f.R": "f <- function() glue::glue('a')\n"})
    before = (tmp_path / "DESCRIPTION").read_text()
    deps_sync.deps_sync(pkg, write=False)
    assert (tmp_path / "DESCRIPTION").read_text() == before

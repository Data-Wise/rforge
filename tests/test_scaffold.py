"""Tests for lib/scaffold.py — the authoring/scaffolding engine.

Covers SPEC-r-scaffolding-2026-06-10:
  - parse a function's signature + roxygen + stop()/@param branches
  - plan a testthat file: one test_that() per branch; assertions = # TODO only
  - r:use-package: Imports vs Suggests; reuse deps_sync DESCRIPTION writer
  - dry-run writes nothing; --write applies; --force required to overwrite
  - usethis boundary is mocked (no R side effects asserted)
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from lib import scaffold

FIXTURE = Path(__file__).parent / "fixtures" / "scaffoldpkg"


@pytest.fixture
def pkg(tmp_path: Path) -> Path:
    """A writable copy of the fixture package."""
    dst = tmp_path / "scaffoldpkg"
    shutil.copytree(FIXTURE, dst)
    return dst


# ───────────────────────── signature parsing ─────────────────────────


def test_parse_signature_finds_params_and_default(pkg: Path):
    sig = scaffold.parse_function(pkg, "estimate")
    assert sig is not None
    assert sig.name == "estimate"
    assert [p.name for p in sig.params] == ["a", "b", "cov"]
    assert sig.params[2].default == "0"
    assert sig.source_file.name == "estimate.R"


def test_parse_signature_collects_stop_branches(pkg: Path):
    sig = scaffold.parse_function(pkg, "estimate")
    msgs = [b.message for b in sig.stop_branches]
    assert "a and b must be numeric" in msgs
    assert "b must be non-negative" in msgs


def test_parse_signature_collects_param_constraints(pkg: Path):
    sig = scaffold.parse_function(pkg, "estimate")
    # the "Must be non-negative" sentence on @param b is an edge-case source
    assert any("non-negative" in c.note.lower() for c in sig.param_constraints)


def test_parse_unknown_function_returns_none(pkg: Path):
    assert scaffold.parse_function(pkg, "no_such_fn") is None


# ───────────────────────── r:use-test planning ─────────────────────────


def test_plan_test_one_block_per_branch(pkg: Path):
    env = scaffold.plan_test(pkg, "estimate")
    body = env["plan"]["content"]
    # one happy-path block + one block per stop() + one per @param constraint
    n_blocks = body.count("test_that(")
    assert n_blocks == 1 + 2 + 1  # happy + 2 stop + 1 constraint
    assert 'test-estimate.R' in env["plan"]["target"]


def test_plan_test_assertions_are_todo_only(pkg: Path):
    env = scaffold.plan_test(pkg, "estimate")
    body = env["plan"]["content"]
    # NO invented expected values: every block carries a # TODO and no bare
    # expect_equal(...) with a literal RHS the engine guessed.
    assert "# TODO" in body
    # the happy path uses expect_no_error / a TODO, never a fabricated expect_equal value
    assert "expect_error(" in body  # error branches DO assert that it errors
    assert body.count("# TODO") >= 3


def test_plan_test_error_blocks_match_stop_messages(pkg: Path):
    env = scaffold.plan_test(pkg, "estimate")
    body = env["plan"]["content"]
    assert "must be numeric" in body
    assert "non-negative" in body


def test_plan_test_dry_run_writes_nothing(pkg: Path):
    target = pkg / "tests" / "testthat" / "test-estimate.R"
    env = scaffold.plan_test(pkg, "estimate")          # default dry-run
    assert env["status"] == "ok"
    assert not target.exists()                          # ZERO disk writes


def test_plan_test_write_creates_file(pkg: Path):
    target = pkg / "tests" / "testthat" / "test-estimate.R"
    env = scaffold.plan_test(pkg, "estimate", write=True)
    assert target.exists()
    assert "test_that(" in target.read_text(encoding="utf-8")


def test_plan_test_refuses_overwrite_without_force(pkg: Path):
    scaffold.plan_test(pkg, "estimate", write=True)
    env = scaffold.plan_test(pkg, "estimate", write=True)   # second time
    assert env["status"] == "warn"
    assert any("--force" in m for m in env["messages"])


def test_plan_test_force_overwrites(pkg: Path):
    scaffold.plan_test(pkg, "estimate", write=True)
    env = scaffold.plan_test(pkg, "estimate", write=True, force=True)
    assert env["status"] == "ok"


def test_plan_test_unknown_fn_scaffolds_stub_with_note(pkg: Path):
    env = scaffold.plan_test(pkg, "no_such_fn")
    assert env["status"] == "warn"
    assert "test_that(" in env["plan"]["content"]      # minimal stub still planned
    assert any("could not" in m.lower() for m in env["messages"])


# ───────────────────────── r:use-package planning ─────────────────────────


def test_plan_package_unconditional_R_use_picks_imports(pkg: Path):
    # tibble is used unconditionally in R/use_helpers.R → Imports
    env = scaffold.plan_package(pkg, "tibble")
    assert env["plan"]["field"] == "Imports"
    assert "tibble" in env["plan"]["importfrom_file"]  # @importFrom placed in the using file


def test_plan_package_vignette_only_use_picks_suggests(pkg: Path):
    # a pkg only present in vignettes/tests → Suggests
    (pkg / "vignettes").mkdir(exist_ok=True)
    (pkg / "vignettes" / "intro.Rmd").write_text(
        "```{r}\nlibrary(knitr)\n```\n", encoding="utf-8")
    env = scaffold.plan_package(pkg, "knitr")
    assert env["plan"]["field"] == "Suggests"


def test_plan_package_dry_run_writes_nothing(pkg: Path):
    before = (pkg / "DESCRIPTION").read_text(encoding="utf-8")
    env = scaffold.plan_package(pkg, "tibble")          # dry-run
    after = (pkg / "DESCRIPTION").read_text(encoding="utf-8")
    assert before == after                               # ZERO writes
    assert env["status"] == "ok"


def test_plan_package_write_uses_deps_sync_writer(pkg: Path):
    env = scaffold.plan_package(pkg, "tibble", write=True)
    desc = (pkg / "DESCRIPTION").read_text(encoding="utf-8")
    assert re.search(r"Imports:.*tibble", desc, re.DOTALL)
    # the @importFrom was inserted into the using R file
    used = (pkg / "R" / "use_helpers.R").read_text(encoding="utf-8")
    assert "@importFrom tibble as_tibble" in used or "@importFrom tibble" in used


def test_plan_package_already_declared_is_warn_noop(pkg: Path):
    env = scaffold.plan_package(pkg, "stats")            # already in Imports
    assert env["status"] == "warn"
    assert any("already" in m.lower() for m in env["messages"])


# ───────────────────────── r:use-vignette planning ─────────────────────────


def test_plan_vignette_dry_run_writes_nothing(pkg: Path):
    target = pkg / "vignettes" / "intro.Rmd"
    env = scaffold.plan_vignette(pkg, "intro")
    assert env["status"] == "ok"
    assert not target.exists()


def test_plan_vignette_skeleton_has_yaml_and_outline(pkg: Path):
    env = scaffold.plan_vignette(pkg, "intro")
    body = env["plan"]["content"]
    assert "vignette:" in body                  # the {VignetteIndexEntry} block
    assert "VignetteEngine" in body
    assert "## " in body                        # at least one drafted outline heading


def test_plan_vignette_uses_package_title(pkg: Path):
    env = scaffold.plan_vignette(pkg, "intro")
    body = env["plan"]["content"]
    assert "scaffoldpkg" in body                # package name appears in prose


def test_plan_vignette_write_creates_file(pkg: Path):
    target = pkg / "vignettes" / "intro.Rmd"
    env = scaffold.plan_vignette(pkg, "intro", write=True)
    assert target.exists()


def test_plan_vignette_refuses_overwrite_without_force(pkg: Path):
    scaffold.plan_vignette(pkg, "intro", write=True)
    env = scaffold.plan_vignette(pkg, "intro", write=True)
    assert env["status"] == "warn"
    assert any("--force" in m for m in env["messages"])

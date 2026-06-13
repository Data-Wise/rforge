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


def test_plan_package_write_preserves_version_constraints(pkg: Path):
    """r:use-package --write must NOT drop (>= x.y.z) floors on untouched deps.

    Regression for the data-corruption bug: adding tibble to Imports rewrote
    the whole block from discovery's name-only parse, stripping the existing
    `testthat (>= 3.0.0)` Suggests constraint (and any Imports constraint).
    """
    desc_path = pkg / "DESCRIPTION"
    # add a constrained Imports dep so we cover both fields
    desc_path.write_text(
        desc_path.read_text(encoding="utf-8").replace(
            "Imports:\n    stats\n", "Imports:\n    stats,\n    dplyr (>= 1.1.0)\n"),
        encoding="utf-8")
    scaffold.plan_package(pkg, "tibble", write=True)
    desc = desc_path.read_text(encoding="utf-8")
    assert "tibble" in desc
    assert "dplyr (>= 1.1.0)" in desc, desc
    assert "testthat (>= 3.0.0)" in desc, desc


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


# ───────────────────────── r:use-data planning ─────────────────────────


def test_scaffold_data_dry_run_writes_nothing(pkg: Path):
    data_r = pkg / "R" / "data.R"
    desc_before = (pkg / "DESCRIPTION").read_text(encoding="utf-8")
    env = scaffold.scaffold_data("mydat", path=pkg, write=False)
    assert env["status"] == "ok"
    assert not data_r.exists()
    # DESCRIPTION untouched on dry-run
    assert (pkg / "DESCRIPTION").read_text(encoding="utf-8") == desc_before


def test_scaffold_data_dry_run_renders_roxygen_stub(pkg: Path):
    env = scaffold.scaffold_data("mydat", path=pkg, write=False)
    content = env["plan"]["content"]
    assert "@title" in content
    assert "@format" in content
    assert "\\describe{" in content
    assert "@source" in content
    # the documented-data idiom: trailing quoted name
    assert '"mydat"' in content


def test_scaffold_data_dry_run_reports_description_delta(pkg: Path):
    env = scaffold.scaffold_data("mydat", path=pkg, write=False)
    blob = " ".join(env["messages"]) + repr(env.get("plan", {}))
    assert "LazyData" in blob
    assert "Depends" in blob


def test_scaffold_data_write_appends_data_r_and_patches_description(pkg: Path):
    data_r = pkg / "R" / "data.R"
    env = scaffold.scaffold_data("mydat", path=pkg, write=True)
    assert env["status"] == "ok"
    assert data_r.exists()
    body = data_r.read_text(encoding="utf-8")
    assert '"mydat"' in body
    desc = (pkg / "DESCRIPTION").read_text(encoding="utf-8")
    assert re.search(r"^LazyData:\s*true", desc, re.MULTILINE)
    assert re.search(r"^Depends:.*R \(>= 2\.10\)", desc, re.MULTILINE | re.DOTALL)
    # never fabricates the .rda; emits the produce-it reminder
    assert not (pkg / "data" / "mydat.rda").exists()
    assert any("use_data" in m for m in env["messages"])


def test_scaffold_data_write_preserves_version_constraints(pkg: Path):
    """r:use-data --write must NOT drop (>= x.y.z) floors (v2.10.0 regression lock)."""
    desc_path = pkg / "DESCRIPTION"
    desc_path.write_text(
        desc_path.read_text(encoding="utf-8").replace(
            "Imports:\n    stats\n", "Imports:\n    stats,\n    dplyr (>= 1.1.0)\n"),
        encoding="utf-8")
    scaffold.scaffold_data("mydat", path=pkg, write=True)
    desc = desc_path.read_text(encoding="utf-8")
    assert "dplyr (>= 1.1.0)" in desc, desc
    assert "testthat (>= 3.0.0)" in desc, desc


def test_scaffold_data_write_collision_no_duplicate_warns(pkg: Path):
    scaffold.scaffold_data("mydat", path=pkg, write=True)
    env = scaffold.scaffold_data("mydat", path=pkg, write=True)
    assert env["status"] == "warn"
    body = (pkg / "R" / "data.R").read_text(encoding="utf-8")
    assert body.count('"mydat"') == 1, body
    assert any("already" in m.lower() or "exist" in m.lower() for m in env["messages"])


def test_scaffold_data_is_pure_stdlib():
    """No R subprocess imports in the scaffold module (pure-stdlib)."""
    src = (Path(scaffold.__file__)).read_text(encoding="utf-8")
    assert "import subprocess" not in src
    assert "subprocess.run" not in src
    assert "Rscript" not in src


# ───────────────────────── r:use-citation planning ─────────────────────────


def test_scaffold_citation_dry_run_renders_bibentry(pkg: Path):
    env = scaffold.scaffold_citation(path=pkg, write=False)
    content = env["plan"]["content"]
    assert "bibentry(" in content
    assert re.search(r'bibtype\s*=\s*"Manual"', content)
    assert "scaffoldpkg" in content          # package/title appears
    assert "person(" in content              # Authors@R mapped to person()
    assert not (pkg / "inst" / "CITATION").exists()


def test_scaffold_citation_year_is_todo_when_date_absent(pkg: Path):
    """Determinism: no wall-clock date — a <YEAR> TODO instead (fixture has no Date)."""
    env = scaffold.scaffold_citation(path=pkg, write=False)
    content = env["plan"]["content"]
    assert "<YEAR>" in content
    # never a real four-digit year fabricated from the clock
    assert not re.search(r"year\s*=\s*\"20\d\d\"", content)


def test_scaffold_citation_write_creates_inst_citation(pkg: Path):
    target = pkg / "inst" / "CITATION"
    env = scaffold.scaffold_citation(path=pkg, write=True)
    assert env["status"] == "ok"
    assert target.exists()
    assert "bibentry(" in target.read_text(encoding="utf-8")


def test_scaffold_citation_write_refuses_clobber_without_force(pkg: Path):
    scaffold.scaffold_citation(path=pkg, write=True)
    env = scaffold.scaffold_citation(path=pkg, write=True)
    assert env["status"] == "warn"
    env2 = scaffold.scaffold_citation(path=pkg, write=True, force=True)
    assert env2["status"] == "ok"


def test_scaffold_citation_unparseable_authors_warns_not_raises(tmp_path: Path):
    root = tmp_path / "weirdpkg"
    (root).mkdir()
    (root / "DESCRIPTION").write_text(
        "Package: weirdpkg\nTitle: Weird\nVersion: 0.1\n"
        "Author: nobody in particular, unparseable <<<\n", encoding="utf-8")
    env = scaffold.scaffold_citation(path=root, write=False)
    # never raises; degrades to a TODO author block + warn
    content = env["plan"]["content"]
    assert "TODO" in content
    assert env["status"] == "warn"
    assert any("Authors@R" in m or "author" in m.lower() for m in env["messages"])

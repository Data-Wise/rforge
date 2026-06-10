"""E2E regression proof for the unconditional-Suggests bug class (medfit 0.2.1).

These tests shell out to the REAL R toolchain (rcmdcheck + MASS), so they are
opt-in: they run only when `RFORGE_E2E=1` is set AND Rscript + MASS are present.
The default `pytest tests/` run stays R-free (CI has no R) and skips them.

Run locally with:
    RFORGE_E2E=1 python3 -m pytest tests/test_regression_suggests_e2e.py -v
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

import lib.rcmd as rcmd

FIXTURES = Path(__file__).parent / "fixtures"


def _has_mass() -> bool:
    if not shutil.which("Rscript"):
        return False
    try:
        out = subprocess.run(
            ["Rscript", "-e", 'cat(requireNamespace("MASS", quietly=TRUE))'],
            capture_output=True, text=True, timeout=30)
        return out.stdout.strip() == "TRUE"
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not (os.environ.get("RFORGE_E2E") and _has_mass()),
    reason="set RFORGE_E2E=1 and install MASS to run the real-R regression proof")


def test_before_fixture_fails_nosuggests_pass():
    # MASS in Suggests, called unconditionally in an example → the noSuggests
    # flavor (_R_CHECK_DEPENDS_ONLY_=true) withholds MASS and the example errors.
    env = rcmd.run("check", str(FIXTURES / "suggestbug.before"),
                   as_cran=True, strict=True, flavor="depends")
    assert env["status"] == "error", "noSuggests pass should catch the medfit bug class"


def test_after_fixture_passes_nosuggests_pass():
    # MASS moved to Imports (the fix) → available under DEPENDS_ONLY → no error.
    env = rcmd.run("check", str(FIXTURES / "suggestbug.after"),
                   as_cran=True, strict=True, flavor="depends")
    assert env["status"] != "error", "the Imports fix should pass the noSuggests gate"
    assert not env.get("check", {}).get("errors")

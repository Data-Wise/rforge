"""Differential tests against pkgdown itself (#111). Non-gating: they live outside `tests/a2`, are not part of the
CI selection (`tests/a2 tests/harness tests/test_*.py`) and skip unless R, pkgdown 2.2.1, the R `quarto` package and
the Quarto CLI are all present. Run by hand: `python -m pytest tests/differential -q`."""
import json
import shutil
import subprocess

import pytest

PKGDOWN = "2.2.1"


def rscript(code, *args, timeout=120):
    run = subprocess.run(["Rscript", "--vanilla", "-e", code, *args], capture_output=True, text=True, timeout=timeout)
    if run.returncode:
        raise RuntimeError(run.stderr)
    return run.stdout


def _skip_reason():
    if shutil.which("Rscript") is None:
        return "Rscript not found"
    if shutil.which("quarto") is None:
        return "Quarto CLI not found"
    try:
        out = rscript('cat(as.character(packageVersion("pkgdown")), requireNamespace("quarto", quietly = TRUE))', timeout=60).split()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return f"R probe failed: {str(exc)[:80]}"
    if out[:1] != [PKGDOWN]:
        return f"pkgdown {PKGDOWN} required, found {out[:1]}"
    if out[1:] != ["TRUE"]:
        return "R package quarto not installed"
    return None


_REASON = _skip_reason()


@pytest.fixture(scope="session")
def pkgdown():
    if _REASON:
        pytest.skip(_REASON)
    return rscript


@pytest.fixture
def r_json(pkgdown):
    def run(code, *args):
        return json.loads(pkgdown("cat(jsonlite::toJSON(local({" + code + "}), auto_unbox = TRUE, null = 'null'))", *args))
    return run

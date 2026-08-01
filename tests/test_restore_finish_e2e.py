"""End-to-end tests for /rforge:restore and /rforge:finish (SPEC-restore-finish-
commands-2026-07-31.md). Real subprocess invocation of `python3 -m lib.rstatus`
against a real throwaway R package fixture (real git repo on disk) — not the
in-process unit tests in test_rstatus.py. Exercises exactly what the prompt-
commands actually shell out to."""
import json
import subprocess
import sys
import os

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")


def _run_recap(path, fmt="json"):
    result = subprocess.run(
        [sys.executable, "-m", "lib.rstatus", "recap", "--path", path, "--format", fmt],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=30,
    )
    return result


def _git_init(pkg_dir):
    subprocess.run(["git", "init", "-q"], cwd=pkg_dir, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=pkg_dir, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=pkg_dir, check=True)


def _make_r_package_fixture(tmp_path, with_status=True):
    (tmp_path / "DESCRIPTION").write_text(
        "Package: medfit\n"
        "Version: 0.4.0\n"
        "Title: Fit mediation models\n"
        "Imports: methods, stats\n"
    )
    # NOTE: lib.tidyaudit.check_news_header's regex
    # (`^#+\s*(\S+)\s+([\d.]+)\s*$`) requires a literal "PackageName X.Y.Z"
    # header and would flag "## Unreleased" as non-compliant advisory-only —
    # tidyaudit is a stricter CRAN-facing lint. "## Unreleased" is instead
    # the common keepachangelog-style dev-in-progress marker this module's
    # own parse_news_header deliberately recognizes (case-insensitive
    # substring match on the header text) as a MORE lenient convention than
    # tidyaudit's, not the same one — corrected after adversarial review
    # flagged the original comment here as claiming the opposite.
    (tmp_path / "NEWS.md").write_text(
        "## Unreleased\n\n"
        "- Added bootstrap intervals\n"
        "- Fixed a typo in vignette\n\n"
        "## medfit 0.3.0\n\n"
        "- Old entry\n"
    )
    if with_status:
        (tmp_path / ".STATUS").write_text(
            "package: medfit\n"
            "updated: 2026-07-16\n"
            "status: Active\n"
            "version: 0.4.0\n"
            "cran_status: not-submitted\n"
            "next: bootstrap CI review\n"
            "blockers: none\n"
        )
    _git_init(str(tmp_path))
    (tmp_path / "R").mkdir()
    (tmp_path / "R" / "fit.R").write_text("fit_model <- function(x) x\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=str(tmp_path), check=True)


# ── restore: real CLI invocation, with .STATUS ──────────────────────────────

def test_e2e_restore_recap_with_status(tmp_path):
    _make_r_package_fixture(tmp_path, with_status=True)

    result = _run_recap(str(tmp_path))
    assert result.returncode == 0, result.stderr

    recap = json.loads(result.stdout)
    assert recap["is_r_package"] is True
    assert recap["description"]["package"] == "medfit"
    assert recap["description"]["version"] == "0.4.0"
    assert recap["news"]["has_unreleased"] is True
    assert recap["rstatus"]["next"] == "bootstrap CI review"
    assert recap["git"]["available"] is True
    assert recap["git"]["dirty"] is False
    assert recap["version_drift"] is None


# ── restore: real CLI invocation, no .STATUS (most CRAN packages) ──────────

def test_e2e_restore_recap_without_status(tmp_path):
    _make_r_package_fixture(tmp_path, with_status=False)

    result = _run_recap(str(tmp_path), fmt="text")
    assert result.returncode == 0, result.stderr
    assert "medfit" in result.stdout
    assert ".STATUS: not found" in result.stdout


# ── restore: real CLI invocation, not an R package at all ──────────────────

def test_e2e_restore_recap_not_r_package(tmp_path):
    _git_init(str(tmp_path))
    (tmp_path / "README.md").write_text("just a repo\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(tmp_path), check=True)

    result = _run_recap(str(tmp_path), fmt="text")
    assert result.returncode == 0, result.stderr
    assert "Not an R package" in result.stdout


# ── restore: real CLI invocation, version drift between DESCRIPTION and .STATUS ─

def test_e2e_restore_detects_version_drift(tmp_path):
    _make_r_package_fixture(tmp_path, with_status=True)
    # Bump DESCRIPTION past what .STATUS still claims — simulates a real
    # release where DESCRIPTION was bumped but .STATUS wasn't synced yet.
    (tmp_path / "DESCRIPTION").write_text(
        "Package: medfit\nVersion: 0.5.0\nTitle: Fit mediation models\n"
    )

    result = _run_recap(str(tmp_path))
    assert result.returncode == 0, result.stderr
    recap = json.loads(result.stdout)
    assert recap["version_drift"] == {"status_version": "0.4.0", "description_version": "0.5.0"}


# ── finish: redundant-edit guard, exercised against real files on disk ─────

def test_e2e_finish_redundant_edit_guard_via_real_files(tmp_path):
    """Mirrors what /rforge:finish's flow actually does: read current .STATUS
    from a real file, compose an intended RStatus with only `updated` bumped,
    diff. A timestamp-only change must be filtered out (no false "changed")."""
    _make_r_package_fixture(tmp_path, with_status=True)

    sys.path.insert(0, REPO_ROOT)
    from lib.rstatus import read_rstatus, diff_rstatus, RStatus  # noqa: E402

    current = read_rstatus(str(tmp_path))
    assert current is not None

    # Intended: only the timestamp moves; nothing else changed this session.
    intended = RStatus(
        package=current.package, updated="2026-07-31", status=current.status,
        version=current.version, cran_status=current.cran_status,
        last_check=current.last_check, last_release=current.last_release,
        next=current.next, blockers=current.blockers,
    )
    assert diff_rstatus(current, intended) == []

    # Now a genuine change: next: field actually moved.
    intended.next = "CRAN resubmission after r-devel check"
    changes = diff_rstatus(current, intended)
    fields = {c[0] for c in changes}
    assert "next" in fields

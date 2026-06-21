"""Tests for r:rhub pre-flight checks and dispatch logic in lib/rcmd.py."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import lib.rcmd as rcmd
import lib.rhub as rhub


# ── _check_rhub_yaml tests ──────────────────────────────────────────────────

def test_rhub_yaml_missing_pak_version_fires(tmp_path):
    """setup-deps block without pak-version: stable → rhub_pak_devel_regression."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
        "          job-config: ${{ matrix.config.job-config }}\n"
    )
    findings = rhub._check_rhub_yaml(str(tmp_path))
    codes = {f["code"] for f in findings}
    assert "rhub_pak_devel_regression" in codes
    # Must use 'advisory' severity (not 'warn')
    pak_finding = next(f for f in findings if f["code"] == "rhub_pak_devel_regression")
    assert pak_finding["severity"] == "advisory"


def test_rhub_yaml_with_pak_stable_clean(tmp_path):
    """setup-deps block with pak-version: stable → no pak findings."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
        "          job-config: ${{ matrix.config.job-config }}\n"
    )
    findings = rhub._check_rhub_yaml(str(tmp_path))
    pak_findings = [f for f in findings if f["code"] == "rhub_pak_devel_regression"]
    assert pak_findings == []


def test_rhub_yaml_missing_entirely_no_findings(tmp_path):
    """No rhub.yaml → _check_rhub_yaml returns [] (preflight handles absence)."""
    findings = rhub._check_rhub_yaml(str(tmp_path))
    assert findings == []


def test_rhub_yaml_multiple_blocks_one_missing(tmp_path):
    """Two setup-deps blocks; second missing pak-version → finding for block 2 only."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          job-config: ${{ matrix.config.job-config }}\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
    )
    findings = rhub._check_rhub_yaml(str(tmp_path))
    pak_findings = [f for f in findings if f["code"] == "rhub_pak_devel_regression"]
    assert len(pak_findings) == 1
    assert pak_findings[0]["block"] == 2
    # Block 1 must NOT have a finding
    block_1_findings = [f for f in pak_findings if f.get("block") == 1]
    assert block_1_findings == []


def test_rhub_yaml_default_broken_platform_advisory(tmp_path):
    """default config field with 'macos' → rhub_yaml_default_broken_platform advisory."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "on:\n"
        "  workflow_dispatch:\n"
        "    inputs:\n"
        "      config:\n"
        "        default: 'linux,windows,macos'\n"
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
    )
    findings = rhub._check_rhub_yaml(str(tmp_path))
    codes = {f["code"] for f in findings}
    assert "rhub_yaml_default_broken_platform" in codes
    default_finding = next(
        f for f in findings if f["code"] == "rhub_yaml_default_broken_platform"
    )
    assert default_finding["severity"] == "advisory"
    assert "macos" in default_finding["platforms"]


# ── _rhub_preflight tests ───────────────────────────────────────────────────

def test_preflight_yaml_missing_hard_blocks(tmp_path):
    """No rhub.yaml → preflight returns error finding, hard-blocks."""
    findings = rhub._rhub_preflight(str(tmp_path), ["linux"])
    errors = [f for f in findings if f["severity"] == "error"]
    assert len(errors) == 1
    assert errors[0]["code"] == "rhub_yaml_missing"


def test_preflight_broken_platform_hard_blocks(tmp_path):
    """Requesting broken platform 'macos' → error finding."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
    )
    findings = rhub._rhub_preflight(str(tmp_path), ["linux", "macos"])
    errors = [f for f in findings if f["severity"] == "error"]
    codes = {f["code"] for f in errors}
    assert "rhub_broken_platform" in codes
    broken = next(f for f in errors if f["code"] == "rhub_broken_platform")
    assert broken["platform"] == "macos"


def test_preflight_clean_yaml_no_findings(tmp_path):
    """Clean rhub.yaml, no broken platforms → empty findings list."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
    )
    findings = rhub._rhub_preflight(str(tmp_path), ["linux", "windows", "macos-arm64"])
    assert findings == []


def test_preflight_advisory_does_not_block(tmp_path):
    """Advisory (pak_version missing) does not produce error severity."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
    )
    findings = rhub._rhub_preflight(str(tmp_path), ["linux"])
    errors = [f for f in findings if f["severity"] == "error"]
    advisories = [f for f in findings if f["severity"] == "advisory"]
    assert errors == []
    assert len(advisories) >= 1  # pak advisory present


# ── Preset resolution tests ─────────────────────────────────────────────────

def test_preset_cran_submission_includes_atlas():
    """cran-submission preset must include 'atlas' per Q6."""
    preset = rhub._RHUB_PRESETS["cran-submission"]
    assert "atlas" in preset
    assert "linux" in preset
    assert "windows" in preset
    assert "macos-arm64" in preset
    assert "macos" not in preset  # broken platform excluded


def test_preset_cran_submission_strict_includes_clang_asan():
    """cran-submission-strict adds clang-asan."""
    preset = rhub._RHUB_PRESETS["cran-submission-strict"]
    assert "clang-asan" in preset
    assert "atlas" in preset


def test_broken_platform_in_broken_dict():
    """'macos' is in _RHUB_BROKEN_PLATFORMS; 'macos-arm64' is not."""
    assert "macos" in rhub._RHUB_BROKEN_PLATFORMS
    assert "macos-arm64" not in rhub._RHUB_BROKEN_PLATFORMS


# ── Sequence ordering test ──────────────────────────────────────────────────

def test_preflight_yaml_missing_stops_before_broken_platform(tmp_path):
    """yaml_missing hard-stops immediately; broken_platform check never runs."""
    # No rhub.yaml at all
    findings = rhub._rhub_preflight(str(tmp_path), ["macos"])  # broken platform
    # Should only get yaml_missing, not rhub_broken_platform
    codes = {f["code"] for f in findings}
    assert "rhub_yaml_missing" in codes
    assert "rhub_broken_platform" not in codes


# ── rc_submit snippet test ──────────────────────────────────────────────────

def test_rc_submit_snippet_has_no_platforms():
    """r_snippet with rc_mode=True dispatches rc_submit() with no platforms= arg."""
    snippet = rcmd.r_snippet("rhub", ".", rc_mode=True)
    assert "rc_submit" in snippet
    assert "platforms=" not in snippet


# ── rhub_check snippet invariants ───────────────────────────────────────────

def test_rhub_check_snippet_explicit_platforms_no_setup():
    """rhub_check snippet passes platforms explicitly; never rhub_setup or NULL."""
    snippet = rcmd.r_snippet("rhub", ".", platforms=["linux", "windows"])
    assert "rhub_check" in snippet
    assert 'platforms=c("linux", "windows")' in snippet
    assert "rhub_setup" not in snippet  # would create a spurious commit
    assert "NULL" not in snippet         # would open an interactive menu / hang


def test_rhub_check_snippet_default_platforms_when_none():
    """No platforms → snippet falls back to the cran-submission preset list."""
    snippet = rcmd.r_snippet("rhub", ".")
    for plat in rhub._RHUB_PRESETS["cran-submission"]:
        assert f'"{plat}"' in snippet


# ── run() / _run_rhub wire-in ───────────────────────────────────────────────

def _write_desc(path):
    (path / "DESCRIPTION").write_text("Package: testpkg\nVersion: 0.1.0\n")


def test_run_unknown_preset_errors(tmp_path):
    """run(rhub, preset=bogus) → error envelope, no dispatch."""
    _write_desc(tmp_path)
    env = rcmd.run("rhub", str(tmp_path), preset="bogus")
    assert env["status"] == "error"
    assert "Unknown preset" in env["messages"][0]


def test_run_advisory_rides_along_into_findings(tmp_path, monkeypatch):
    """Advisory (missing pak-version) does not block dispatch; lands in findings."""
    _write_desc(tmp_path)
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
    )
    monkeypatch.setattr(rcmd, "_invoke_r", lambda *a, **k: ('{"submitted":true}', 0))
    monkeypatch.setattr(rhub, "_rhub_actions_url", lambda p: "")  # no browser launch
    env = rcmd.run("rhub", str(tmp_path), platforms=["linux"])
    assert env["status"] == "dispatched"
    codes = {f["code"] for f in env.get("findings", [])}
    assert "rhub_pak_devel_regression" in codes

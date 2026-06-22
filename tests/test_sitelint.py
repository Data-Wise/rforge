"""Tests for lib.sitelint — pkgdown stray-file leak detector (SPEC Phase 1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib import sitelint


# ───────────────────────── fixtures ─────────────────────────


def _run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=Test",
         *args],
        cwd=str(cwd), check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def pkg(tmp_path: Path) -> Path:
    """A git-init'd R package dir.

    Layout:
      DESCRIPTION       (committed)
      README.md         (committed, allowlisted)
      PLAN-scratch.md   (committed → tracked, non-allowlisted)
      NOTES.md          (untracked, non-allowlisted)
    """
    (tmp_path / "DESCRIPTION").write_text("Package: testpkg\nVersion: 0.0.1\n")
    (tmp_path / "README.md").write_text("# testpkg\n")
    (tmp_path / "PLAN-scratch.md").write_text("scratch\n")
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "add", "DESCRIPTION", "README.md", "PLAN-scratch.md")
    _run_git(tmp_path, "commit", "-m", "init")
    # untracked after the commit:
    (tmp_path / "NOTES.md").write_text("notes\n")
    return tmp_path


def _codes(env: dict) -> set[str]:
    return {f["file"] for f in env["findings"]}


def _by_file(env: dict, name: str) -> dict:
    for f in env["findings"]:
        if f["file"] == name:
            return f
    raise AssertionError(f"{name} not in findings: {env['findings']}")


# ───────────────────────── envelope shape ─────────────────────────


def test_envelope_shape(pkg: Path):
    env = sitelint.check_site_leaks(pkg)
    assert set(env) >= {"kind", "status", "findings", "messages", "engine_missing"}
    assert env["kind"] == "site-leaks"
    assert env["status"] in {"ok", "warn"}
    assert env["engine_missing"] == []


# ───────────────────────── core allowlist ─────────────────────────


def test_readme_allowlisted(pkg: Path):
    env = sitelint.check_site_leaks(pkg)
    assert "README.md" not in _codes(env)


def test_index_md_allowed(tmp_path: Path):
    (tmp_path / "index.md").write_text("# home\n")
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "init")
    env = sitelint.check_site_leaks(tmp_path)
    assert "index.md" not in _codes(env)


def test_case_insensitive_licence(tmp_path: Path):
    # LICENCE.md (British spelling, upper-case) must be allowlisted.
    (tmp_path / "LICENCE.md").write_text("MIT\n")
    (tmp_path / "STRAY.md").write_text("x\n")
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "init")
    env = sitelint.check_site_leaks(tmp_path)
    assert "LICENCE.md" not in _codes(env)
    assert "STRAY.md" in _codes(env)


# ───────────────────────── status tagging ─────────────────────────


def test_tracked_tag(pkg: Path):
    env = sitelint.check_site_leaks(pkg)
    plan = _by_file(env, "PLAN-scratch.md")
    assert plan["git_status"] == "tracked"


def test_untracked_tag(pkg: Path):
    env = sitelint.check_site_leaks(pkg)
    notes = _by_file(env, "NOTES.md")
    assert notes["git_status"] == "untracked"


def test_gitignored_not_tagged_tracked(pkg: Path):
    # A gitignored .md is on disk but neither tracked nor in porcelain —
    # it must NOT be mislabelled "tracked".
    (pkg / ".gitignore").write_text("IGNORED.md\n")
    (pkg / "IGNORED.md").write_text("ignored scratch\n")
    _run_git(pkg, "add", ".gitignore")
    _run_git(pkg, "commit", "-m", "add gitignore")
    env = sitelint.check_site_leaks(pkg)
    ignored = _by_file(env, "IGNORED.md")
    assert ignored["git_status"] == "ignored"


def test_modified_tag(pkg: Path):
    # Modify a tracked, non-allowlisted file → should tag "modified".
    (pkg / "PLAN-scratch.md").write_text("scratch CHANGED\n")
    env = sitelint.check_site_leaks(pkg)
    plan = _by_file(env, "PLAN-scratch.md")
    assert plan["git_status"] == "modified"


def test_both_non_allowlisted_flagged(pkg: Path):
    env = sitelint.check_site_leaks(pkg)
    assert {"PLAN-scratch.md", "NOTES.md"} <= _codes(env)
    assert env["status"] == "warn"


# ───────────────────────── scope: root + man + vignettes ─────────────────────────


def test_scope_man_non_rd(tmp_path: Path):
    man = tmp_path / "man"
    man.mkdir()
    (man / "foo.Rd").write_text("\\name{foo}\n")          # legit, skip
    (man / "SCRATCH.md").write_text("scratch\n")           # leak
    (man / "figures").mkdir()
    (man / "figures" / "logo.png").write_text("x")         # subdir → skip
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "init")
    env = sitelint.check_site_leaks(tmp_path)
    files = _codes(env)
    assert "SCRATCH.md" in files
    assert "foo.Rd" not in files
    assert "logo.png" not in files
    assert _by_file(env, "SCRATCH.md")["where"] == "man"


def test_scope_vignettes_non_vignette(tmp_path: Path):
    vig = tmp_path / "vignettes"
    vig.mkdir()
    (vig / "intro.Rmd").write_text("---\n")                # legit vignette, skip
    (vig / "guide.qmd").write_text("---\n")                # legit vignette, skip
    (vig / "DRAFT.md").write_text("draft\n")               # leak
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "init")
    env = sitelint.check_site_leaks(tmp_path)
    files = _codes(env)
    assert "DRAFT.md" in files
    assert "intro.Rmd" not in files
    assert "guide.qmd" not in files
    assert _by_file(env, "DRAFT.md")["where"] == "vignettes"


def test_root_where_tag(pkg: Path):
    env = sitelint.check_site_leaks(pkg)
    assert _by_file(env, "PLAN-scratch.md")["where"] == "root"


# ───────────────────────── .rforge.yaml override ─────────────────────────


def test_rforge_yaml_override_clears_tracked_hit(pkg: Path):
    (pkg / ".rforge.yaml").write_text(
        "site:\n  allowlist:\n    - PLAN-scratch.md\n")
    env = sitelint.check_site_leaks(pkg)
    assert "PLAN-scratch.md" not in _codes(env)
    # NOTES.md was not allowlisted → still flagged.
    assert "NOTES.md" in _codes(env)


def test_rforge_yaml_override_clears_vignettes_hit(tmp_path: Path):
    # Allowlist must apply across all scopes, not just root.
    vig = tmp_path / "vignettes"
    vig.mkdir()
    (vig / "intro.Rmd").write_text("---\n")
    (vig / "DRAFT.md").write_text("draft\n")
    (tmp_path / ".rforge.yaml").write_text(
        "site:\n  allowlist:\n    - DRAFT.md\n")
    _run_git(tmp_path, "init")
    _run_git(tmp_path, "add", ".")
    _run_git(tmp_path, "commit", "-m", "init")
    env = sitelint.check_site_leaks(tmp_path)
    assert "DRAFT.md" not in _codes(env)


def test_rforge_yaml_malformed_falls_back_to_core(pkg: Path):
    # allowlist as a scalar, not a list → malformed → warn + fall back to core.
    (pkg / ".rforge.yaml").write_text("site:\n  allowlist: PLAN-scratch.md\n")
    env = sitelint.check_site_leaks(pkg)
    # Core allowlist still applies (README excluded); PLAN still flagged.
    assert "PLAN-scratch.md" in _codes(env)
    assert "README.md" not in _codes(env)
    assert any("allowlist" in m.lower() for m in env["messages"])


# ───────────────────────── git-absent degrade ─────────────────────────


def test_git_absent_degrade(tmp_path: Path):
    # No git init → not a repo. Still lint by filename; git_status is None.
    (tmp_path / "DESCRIPTION").write_text("Package: t\nVersion: 0.0.1\n")
    (tmp_path / "README.md").write_text("# t\n")
    (tmp_path / "STRAY.md").write_text("x\n")
    env = sitelint.check_site_leaks(tmp_path)
    assert "STRAY.md" in _codes(env)
    assert "README.md" not in _codes(env)
    assert _by_file(env, "STRAY.md")["git_status"] is None


# ───────────────────────── CLI ─────────────────────────


def test_cli_emits_json_and_exits_zero(pkg: Path):
    proc = subprocess.run(
        [sys.executable, "-m", "lib.sitelint", str(pkg)],
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    env = json.loads(proc.stdout)
    assert env["kind"] == "site-leaks"
    assert "PLAN-scratch.md" in {f["file"] for f in env["findings"]}

"""Tier 4 (cranlint) integration into _run_cran_prep.

The pure-Python metadata/hygiene checks (description, build-hygiene,
docs-consistency) must surface as ADVISORY stage rows that never flip the
`ready` verdict on their own. R-calling stages are mocked so these tests run
without an R toolchain.
"""
import lib.rcmd as rcmd


def _ok(kind, path=".", **_):
    """Stand-in for run(): every R stage reports clean."""
    return {"kind": kind, "status": "ok", "check": {"notes_classified": []},
            "engine_missing": [], "messages": []}


def _make_pkg(tmp_path, *, rbuildignore="", extra_files=()):
    (tmp_path / "DESCRIPTION").write_text(
        "Package: demo\nVersion: 0.1.0\n"
        "Title: A Demo\nDescription: Does things.\nAuthor: A\nMaintainer: A <a@b.c>\n")
    (tmp_path / "NAMESPACE").write_text("")
    (tmp_path / "R").mkdir()
    if rbuildignore:
        (tmp_path / ".Rbuildignore").write_text(rbuildignore)
    for name in extra_files:
        (tmp_path / name).write_text("planning\n")
    return tmp_path


def test_cran_prep_includes_tier4_advisory_stages(tmp_path, monkeypatch):
    monkeypatch.setattr(rcmd, "run", _ok)
    pkg = _make_pkg(tmp_path, extra_files=("BRAINSTORM.md",))
    env = rcmd._run_cran_prep(str(pkg), no_revdep=True, strict=False)
    kinds = {s["kind"] for s in env["stages"]}
    assert {"description", "build-hygiene", "docs-consistency"} <= kinds


def test_tier4_advisory_never_blocks_ready(tmp_path, monkeypatch):
    # BRAINSTORM.md unignored => build-hygiene warns; DESCRIPTION has no
    # Authors@R => description warns. Neither may block `ready`.
    monkeypatch.setattr(rcmd, "run", _ok)
    pkg = _make_pkg(tmp_path, extra_files=("BRAINSTORM.md",))
    env = rcmd._run_cran_prep(str(pkg), no_revdep=True, strict=False)
    assert env["blockers"] == []
    assert env["status"] == "ready"


def test_tier4_missing_description_degrades_to_warn_not_exception(tmp_path, monkeypatch):
    # find_package needs Package+Version; give a minimal DESCRIPTION but make the
    # cranlint linters see a sparse file. They must degrade, never raise.
    monkeypatch.setattr(rcmd, "run", _ok)
    (tmp_path / "DESCRIPTION").write_text("Package: demo\nVersion: 0.1.0\n")
    (tmp_path / "R").mkdir()
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True, strict=False)
    # No exception, and the advisory stages still appear.
    kinds = {s["kind"] for s in env["stages"]}
    assert "description" in kinds

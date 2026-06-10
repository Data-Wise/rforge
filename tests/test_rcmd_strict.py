"""Strict CRAN-incoming check engine tests (feature/cran-incoming).

Covers the additions to lib/rcmd.py:
  - r_snippet(kind="check", flavor=..., incoming=...) env/args shaping
  - run("check", flavor=..., incoming=...) threading
  - _run_cran_prep strict-flavor loop (noSuggests / suggests-only) + blockers
  - --incoming bundle + argparse wiring

R is not available in this environment, so every test that would shell out
mocks at the _invoke_r / run boundary (matching tests/test_rcmd.py).
"""
import textwrap
from pathlib import Path

import pytest

from lib import rcmd


def _write_desc(tmp_path: Path, name="foo", version="0.2.0") -> Path:
    (tmp_path / "DESCRIPTION").write_text(
        textwrap.dedent(f"Package: {name}\nVersion: {version}\nTitle: Test\n")
    )
    return tmp_path


# --- Phase 1: r_snippet flavor + env shaping ---------------------------------

def test_r_snippet_check_depends_flavor_sets_env_and_donttest():
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True,
                         flavor="depends", strict=True)
    assert "--run-donttest" in src
    assert "_R_CHECK_DEPENDS_ONLY_" in src
    assert '"true"' in src  # the env value
    assert "env=" in src or "env =" in src


def test_r_snippet_check_suggests_flavor_sets_env_and_donttest():
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True,
                         flavor="suggests", strict=True)
    assert "--run-donttest" in src
    assert "_R_CHECK_SUGGESTS_ONLY_" in src
    assert "_R_CHECK_DEPENDS_ONLY_" not in src


def test_r_snippet_check_plain_is_unchanged():
    """Backward-compat lock: no flavor / no incoming → no env, no donttest."""
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True)
    assert "--run-donttest" not in src
    assert "_R_CHECK_DEPENDS_ONLY_" not in src
    assert "_R_CHECK_SUGGESTS_ONLY_" not in src
    assert "_R_CHECK_CRAN_INCOMING_" not in src
    # The whole call must be byte-identical to the pre-strict snippet.
    expected = rcmd._guard(
        "rcmdcheck",
        'r <- rcmdcheck::rcmdcheck("/tmp/foo", args=c("--as-cran"), '
        'quiet=TRUE, error_on = "never"); '
        'cat(jsonlite::toJSON(list(errors=r$errors, warnings=r$warnings, '
        'notes=r$notes), auto_unbox=TRUE, null="list"))')
    assert src == expected


def test_r_snippet_check_incoming_bundle():
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True, incoming=True)
    assert "_R_CHECK_CRAN_INCOMING_" in src
    assert "--run-donttest" in src  # incoming implies strict-grade run


# --- Phase 2: run() threading ------------------------------------------------

def test_run_check_threads_flavor(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    captured = {}

    def fake_invoke(snippet):
        captured["snippet"] = snippet
        return ('{"errors":[],"warnings":[],"notes":[]}', 0)

    monkeypatch.setattr(rcmd, "_invoke_r", fake_invoke)
    env = rcmd.run("check", str(tmp_path), as_cran=True, flavor="depends", strict=True)
    assert env["status"] == "ok"
    assert "_R_CHECK_DEPENDS_ONLY_" in captured["snippet"]
    assert "--run-donttest" in captured["snippet"]


def test_run_check_threads_incoming(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    captured = {}
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: (captured.setdefault("s", s),
                                   ('{"errors":[],"warnings":[],"notes":[]}', 0))[1])
    rcmd.run("check", str(tmp_path), as_cran=True, incoming=True)
    assert "_R_CHECK_CRAN_INCOMING_" in captured["s"]


# --- Phase 2: _run_cran_prep strict-flavor passes ----------------------------

def _fake_run_factory(flavor_status):
    """Build a fake run() where check status depends on the flavor kwarg.

    flavor_status maps a flavor value (None/'depends'/'suggests') to a status.
    """
    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok", "engine_missing": [], "messages": []}
        if kind == "check":
            base["status"] = flavor_status.get(kw.get("flavor"), "ok")
            base["check"] = {"errors": [], "warnings": [], "notes": [],
                             "notes_classified": []}
        if kind == "revdep":
            base["revdep"] = {"broken": [], "new_problems": []}
        return base
    return fake_run


def test_cran_prep_runs_strict_flavor_rows(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "run", _fake_run_factory({}))
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True)
    kinds = [s["kind"] for s in env["stages"]]
    assert "check (noSuggests)" in kinds
    assert "check (suggests-only)" in kinds


def test_cran_prep_depends_flavor_error_blocks_ready(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "run",
                        _fake_run_factory({"depends": "error"}))
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True)
    assert env["status"] != "ready"
    assert any("noSuggests" in b for b in env["blockers"])
    # the targeted hint must be surfaced somewhere
    blob = " ".join(env["blockers"]) + " ".join(env.get("messages", []))
    assert "requireNamespace" in blob


def test_cran_prep_suggests_flavor_error_blocks_ready(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "run",
                        _fake_run_factory({"suggests": "error"}))
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True)
    assert env["status"] != "ready"
    assert any("noSuggests" in b or "Suggests" in b for b in env["blockers"])


def test_cran_prep_clean_all_flavors_reaches_ready(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "run", _fake_run_factory({}))
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True)
    assert env["status"] == "ready"


def test_cran_prep_incoming_adds_row(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "run", _fake_run_factory({}))
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True, incoming=True)
    kinds = [s["kind"] for s in env["stages"]]
    assert "check (incoming)" in kinds


def test_cran_prep_no_incoming_omits_row(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "run", _fake_run_factory({}))
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True)
    kinds = [s["kind"] for s in env["stages"]]
    assert "check (incoming)" not in kinds


def test_cran_prep_incoming_error_blocks(tmp_path, monkeypatch):
    _write_desc(tmp_path)

    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok", "engine_missing": [], "messages": []}
        if kind == "check":
            base["status"] = "error" if kw.get("incoming") else "ok"
            base["check"] = {"errors": [], "warnings": [], "notes": [],
                             "notes_classified": []}
        return base

    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True, incoming=True)
    assert env["status"] != "ready"
    assert any("incoming" in b.lower() for b in env["blockers"])


# --- Phase 1b: manual-build warn (LaTeX absent) ------------------------------

def test_cran_prep_manual_latex_missing_is_warn_not_error(tmp_path, monkeypatch):
    """A missing-LaTeX manual signal must degrade to warn, never block ready."""
    _write_desc(tmp_path)
    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok", "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [], "notes": [],
                             "notes_classified": [],
                             "manual": {"built": False, "latex": False}}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=True)
    # latex-absent manual must not flip ready
    assert env["status"] == "ready"


# --- argparse wiring ---------------------------------------------------------

def test_main_incoming_flag_threads_into_cran_prep(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    seen = {}

    def fake_prep(path, **kw):
        seen.update(kw)
        return {"kind": "cran-prep", "status": "ready", "stages": [],
                "blockers": [], "dispatched": [], "engine_missing": [],
                "messages": []}

    monkeypatch.setattr(rcmd, "_run_cran_prep", fake_prep)
    rc = rcmd.main(["--kind", "cran-prep", "--path", str(tmp_path), "--incoming"])
    assert rc == 0
    assert seen.get("incoming") is True


def test_main_check_incoming_flag_threads_into_run(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    seen = {}

    def fake_run(kind, path, **kw):
        seen.update(kw)
        return {"kind": kind, "status": "ok", "engine_missing": [], "messages": [],
                "check": {"errors": [], "warnings": [], "notes": [],
                          "notes_classified": []}}

    monkeypatch.setattr(rcmd, "run", fake_run)
    rcmd.main(["--kind", "check", "--path", str(tmp_path), "--incoming"])
    assert seen.get("incoming") is True

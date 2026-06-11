"""Tests for lib/runiverse.py — R-universe early-access status (r:submit --universe).

Covers SPEC-r-submit-runiverse-early-access-2026-06-11:
  - remote_owner parses both https and ssh GitHub remotes (and tolerates non-GitHub)
  - api_url / install_snippet shapes
  - summarize: green / red / unknown classification
  - verify degradation paths (no DESCRIPTION, no remote, unregistered, offline)
    all return non-fatal `warn` and NEVER raise
  - verify green path → status ok
  - the envelope always matches the house shape (engine_missing == [])

No real network — fetch_status / remote_owner are monkeypatched, and the offline
test stubs urllib to raise (the hermetic-smoke guarantee).
"""

from __future__ import annotations

import types

import pytest

from lib import runiverse


# ───────────────────────── pure helpers ─────────────────────────


def test_api_url_and_install_snippet():
    assert runiverse.api_url("ropensci", "foo") == \
        "https://ropensci.r-universe.dev/api/packages/foo"
    assert runiverse.install_snippet("ropensci", "foo") == \
        'install.packages("foo", repos = "https://ropensci.r-universe.dev")'


def test_universe_name_is_lowercased():
    # R-universe subdomains are canonically lowercase: Data-Wise → data-wise.
    # The owner is lowercased; the package name keeps its (case-sensitive) case.
    assert runiverse.api_url("Data-Wise", "MyPkg") == \
        "https://data-wise.r-universe.dev/api/packages/MyPkg"
    assert runiverse.install_snippet("Data-Wise", "MyPkg") == \
        'install.packages("MyPkg", repos = "https://data-wise.r-universe.dev")'


def test_resolve_universe_lowercases(monkeypatch):
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: "Data-Wise")
    assert runiverse.resolve_universe(".") == "data-wise"          # from remote
    assert runiverse.resolve_universe(".", "@Data-Wise") == "data-wise"  # override


@pytest.mark.parametrize("url,owner", [
    ("https://github.com/Data-Wise/rforge.git", "Data-Wise"),
    ("git@github.com:Data-Wise/rforge.git", "Data-Wise"),
    ("https://github.com/ropensci/targets", "ropensci"),
    ("https://gitlab.com/foo/bar.git", None),  # non-GitHub → None
])
def test_remote_owner_parses_forms(monkeypatch, url, owner):
    def fake_run(*a, **k):
        return types.SimpleNamespace(returncode=0, stdout=url + "\n", stderr="")
    monkeypatch.setattr(runiverse.subprocess, "run", fake_run)
    assert runiverse.remote_owner(".") == owner


def test_remote_owner_no_remote(monkeypatch):
    def fake_run(*a, **k):
        return types.SimpleNamespace(returncode=2, stdout="", stderr="no origin")
    monkeypatch.setattr(runiverse.subprocess, "run", fake_run)
    assert runiverse.remote_owner(".") is None


def test_remote_owner_git_absent(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(runiverse.subprocess, "run", boom)
    assert runiverse.remote_owner(".") is None


def test_resolve_universe_override_wins(monkeypatch):
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: "from-remote")
    assert runiverse.resolve_universe(".", "@chosen") == "chosen"
    assert runiverse.resolve_universe(".", None) == "from-remote"


# ───────────────────────── summarize ─────────────────────────


def test_summarize_green():
    data = {"_status": "success", "_binaries": [
        {"os": "linux", "arch": "x86_64", "r": "4.4", "status": "success", "check": "OK"},
        {"os": "windows", "arch": "x86_64", "r": "4.4", "status": "success", "check": "OK"},
    ]}
    s = runiverse.summarize(data)
    assert s["green"] is True and s["known"] is True
    assert len(s["platforms"]) == 2 and all(p["ok"] for p in s["platforms"])


def test_summarize_real_shape_rmediation():
    """Live shape (data-wise.r-universe.dev/api/packages/RMediation): _binaries[]
    carries os/distro/r/status/check/buildurl and NO arch field."""
    data = {"_status": "success", "_binaries": [
        {"r": "4.7.0", "os": "linux", "version": "1.4.0", "distro": "noble",
         "commit": "42df74e", "status": "success", "check": "OK",
         "buildurl": "https://github.com/r-universe/data-wise/actions/runs/1"},
    ]}
    s = runiverse.summarize(data)
    assert s["green"] is True
    p = s["platforms"][0]
    assert p["platform"] == "linux" and p["distro"] == "noble" and p["arch"] == ""
    assert p["status"] == "success" and p["check"] == "OK" and p["ok"] is True


def test_summarize_built_but_check_warning_still_installable():
    """A binary that built but has a check WARNING is still installable → green;
    the check result is surfaced, not folded into green."""
    data = {"_status": "success", "_binaries": [
        {"os": "linux", "r": "4.4", "status": "success", "check": "WARNING"},
    ]}
    s = runiverse.summarize(data)
    assert s["green"] is True                      # built = installable
    assert s["platforms"][0]["check"] == "WARNING"  # surfaced as advisory
    assert s["platforms"][0]["ok"] is True


def test_summarize_red_when_one_fails():
    data = {"_status": "success", "_binaries": [
        {"os": "linux", "status": "success"},
        {"os": "macos", "status": "failure"},
    ]}
    s = runiverse.summarize(data)
    assert s["green"] is False
    assert [p["ok"] for p in s["platforms"]] == [True, False]


def test_summarize_red_when_top_status_fails():
    data = {"_status": "failure", "_binaries": [{"os": "linux", "status": "success"}]}
    assert runiverse.summarize(data)["green"] is False


def test_summarize_unknown_when_no_fields():
    s = runiverse.summarize({"Package": "foo", "Version": "1.0"})
    assert s["known"] is False and s["green"] is False and s["platforms"] == []


# ───────────────────────── verify: degradation paths ─────────────────────────


def _assert_envelope_shape(env):
    assert env["kind"] == "runiverse"
    assert env["status"] in ("ok", "warn", "error")
    assert env["engine_missing"] == []
    assert isinstance(env["findings"], list)
    assert isinstance(env["messages"], list)


def test_verify_no_description_warns(tmp_path):
    env = runiverse.verify(str(tmp_path))
    _assert_envelope_shape(env)
    assert env["status"] == "warn"
    assert any("DESCRIPTION" in m for m in env["messages"])


def test_verify_no_remote_warns(make_pkg, monkeypatch):
    pkg = make_pkg("foo")
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: None)
    env = runiverse.verify(str(pkg))
    _assert_envelope_shape(env)
    assert env["status"] == "warn"
    assert env["package"] == "foo"
    assert any("--universe" in m for m in env["messages"])


def test_verify_unregistered_gives_setup_guidance(make_pkg, monkeypatch):
    pkg = make_pkg("foo")
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: "someone")
    monkeypatch.setattr(runiverse, "fetch_status", lambda o, p, **k: ("not_found", None))
    env = runiverse.verify(str(pkg))
    _assert_envelope_shape(env)
    assert env["status"] == "warn"
    assert {f["kind"] for f in env["findings"]} == {"unregistered"}
    assert any("set-up.html" in m for m in env["messages"])


def test_verify_offline_warns_not_raises(make_pkg, monkeypatch):
    pkg = make_pkg("foo")
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: "someone")
    monkeypatch.setattr(runiverse, "fetch_status", lambda o, p, **k: ("network", None))
    env = runiverse.verify(str(pkg))
    _assert_envelope_shape(env)
    assert env["status"] == "warn"
    assert any("offline" in m.lower() or "could not reach" in m.lower() for m in env["messages"])


# ───────────────────────── verify: live-ish paths ─────────────────────────


def test_verify_green_is_ok(make_pkg, monkeypatch):
    pkg = make_pkg("foo")
    data = {"_status": "success", "_binaries": [{"os": "linux", "status": "success"}]}
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: "someone")
    monkeypatch.setattr(runiverse, "fetch_status", lambda o, p, **k: ("ok", data))
    env = runiverse.verify(str(pkg))
    _assert_envelope_shape(env)
    assert env["status"] == "ok"
    f = env["findings"][0]
    assert f["kind"] == "build_status" and f["green"] is True
    assert f["install"] == runiverse.install_snippet("someone", "foo")


def test_verify_red_is_warn(make_pkg, monkeypatch):
    pkg = make_pkg("foo")
    data = {"_status": "failure", "_binaries": [{"os": "macos", "status": "failure"}]}
    monkeypatch.setattr(runiverse, "remote_owner", lambda p: "someone")
    monkeypatch.setattr(runiverse, "fetch_status", lambda o, p, **k: ("ok", data))
    env = runiverse.verify(str(pkg))
    _assert_envelope_shape(env)
    assert env["status"] == "warn"
    assert env["findings"][0]["green"] is False
    assert any("macos" in m for m in env["messages"])


def test_fetch_status_offline_returns_network(monkeypatch):
    """The hermetic guarantee: a urllib failure becomes ('network', None), no raise."""
    import urllib.error

    def boom(*a, **k):
        raise urllib.error.URLError("no network")
    monkeypatch.setattr(runiverse.urllib.request, "urlopen", boom)
    assert runiverse.fetch_status("someone", "foo", timeout=0.1) == ("network", None)

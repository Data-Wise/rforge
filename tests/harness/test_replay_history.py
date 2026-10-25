"""History-replay tests: a planted bad commit on a synthetic repo, and (guarded) real packages."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS))
import replay  # noqa: E402

needs_audit = pytest.mark.skipif(not replay.docaudit_available(), reason="lib.docaudit not built yet")


def _git(repo, *args):
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "HOME": str(repo), "PATH": os.environ["PATH"]}
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env).stdout.strip()


def _history(tmp_path, bodies):
    r = tmp_path / "pkg"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    (r / "DESCRIPTION").write_text("Package: demo\nVersion: 0.1.0\n")
    (r / "NAMESPACE").write_text("export(f)\n")
    (r / "man").mkdir()
    (r / "man" / "f.Rd").write_bytes(b"\\name{f}\n\\usage{\nf(a, b)\n}\n")
    for i, body in enumerate(bodies):
        (r / "README.md").write_text(body + f"<!-- {i} -->\n")  # keep every commit non-empty
        _git(r, "add", "-A")
        _git(r, "commit", "-q", "-m", f"c{i}")
    return r


@needs_audit
def test_planted_bad_commit_is_found_once_with_first_seen(tmp_path):
    r = _history(tmp_path, ["```r\nf(a = 1)\n```\n", "```r\nf(zzz = 1)\n```\n", "```r\nf(zzz = 1)\n```\n", "```r\nf(a = 1)\n```\n"])
    found = replay.run_history(r, n=10, checks={"signature-named-arg"})
    assert [(f["arg"], f["commits"]) for f in found] == [("zzz", 2)]
    assert found[0]["first_seen_in"] == _git(r, "rev-parse", "HEAD~1")


@needs_audit
def test_clean_history_reports_nothing(tmp_path):
    r = _history(tmp_path, ["```r\nf(a = 1)\n```\n", "```r\nf(b = 2)\n```\n"])
    assert replay.run_history(r, n=10) == []


def test_cli_replay_exits_2_while_the_module_is_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(replay, "docaudit_available", lambda: False)
    assert replay.main(["replay", "--repo", str(tmp_path)]) == 2


@needs_audit
@pytest.mark.skipif(not os.environ.get("RFORGE_MEDFIT_PATH"), reason="RFORGE_MEDFIT_PATH not set")
def test_real_medfit_history_runs_without_crashing():
    found = replay.run_history(Path(os.environ["RFORGE_MEDFIT_PATH"]).expanduser(), n=5)
    assert isinstance(found, list)


@pytest.mark.skipif(not (os.environ.get("RFORGE_MEDFIT_PATH") and Path(os.environ["RFORGE_MEDFIT_PATH"]).is_dir()),
                    reason="RFORGE_MEDFIT_PATH not set")
def test_a2_stale_numeric_replay_on_real_medfit_history():
    """A2 catches medfit's documented stale NIE on the real pre-fix tree (README replay in R); the
    site row has no retained history and must stay pending, never reported caught."""
    import json
    manifest = json.loads((HARNESS.parent / "fixtures" / "docaudit" / "defects.json").read_text(encoding="utf-8"))
    summary = replay.run_recall(manifest, "a2", overrides={"medfit": os.environ["RFORGE_MEDFIT_PATH"]})
    outcomes = {row["id"]: row["outcome"] for row in summary["rows"]}
    assert outcomes["readme-nie-output"] == replay.CAUGHT
    assert outcomes["site-missing-models-page"] == replay.UNAVAILABLE

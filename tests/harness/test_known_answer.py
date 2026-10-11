"""Known-answer and planted-defect tests for `lib/docaudit.py`.

The plant tool itself is always tested. The audit assertions run once `lib.docaudit`
exists (they skip before that, so the suite stays green while the module is built)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parent
ROOT = HARNESS.parents[1]
FIX = ROOT / "tests" / "fixtures" / "docaudit"
sys.path.insert(0, str(HARNESS))
import plant  # noqa: E402
import replay  # noqa: E402

needs_audit = pytest.mark.skipif(not replay.docaudit_available(), reason="lib.docaudit not built yet")


def audit(path: Path, tmp_home: Path) -> dict:
    env = {**os.environ, "HOME": str(tmp_home)}
    proc = subprocess.run([sys.executable, "-m", "lib.docaudit", "--path", str(path), "--format", "json"],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _snapshot(d: Path) -> dict:
    return {str(p.relative_to(d)): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


# ───────────────────────── fixtures and the plant tool ─────────────────────────


def test_defect_and_clean_differ_only_in_the_refcard_row():
    a, b = _snapshot(FIX / "defect"), _snapshot(FIX / "clean")
    assert a.keys() == b.keys()
    assert [k for k in a if a[k] != b[k]] == ["vignettes/articles/refcard.qmd"]
    assert b"joint_effects(x, theta)" in a["vignettes/articles/refcard.qmd"]
    assert b"joint_effects(object, estimates)" in b["vignettes/articles/refcard.qmd"]


@pytest.mark.parametrize("kind", sorted(plant.PLANTS))
def test_plant_mutates_a_copy_only(tmp_path, kind):
    before = _snapshot(FIX / "clean")
    expected = plant.plant(FIX / "clean", tmp_path / "p", kind)
    assert _snapshot(FIX / "clean") == before
    assert plant.PLANTS[kind][0].encode() in (tmp_path / "p" / plant.FILE).read_bytes()
    assert expected["check"] == plant.PLANTS[kind][1]


# ───────────────────────── the audit ─────────────────────────


def _has(report: dict, check: str, **match) -> bool:
    return any(f["check"] == check and all(f.get(k) == v for k, v in match.items()) for f in report["findings"])


@needs_audit
def test_known_answer_defect_is_flagged(tmp_path):
    report = audit(FIX / "defect", tmp_path)
    assert _has(report, "signature-names", file="vignettes/articles/refcard.qmd", function="joint_effects")


@needs_audit
def test_known_answer_clean_has_no_error_and_no_joint_effects_flag(tmp_path):
    report = audit(FIX / "clean", tmp_path)
    assert not [f for f in report["findings"] if f["severity"] == "error"]
    assert not _has(report, "signature-names", function="joint_effects")
    assert not _has(report, "signature-names", function="bootstrap_mediation")  # `f, ...`: variadic, exempt


@needs_audit
def test_controls_produce_no_findings(tmp_path):
    assert audit(FIX / "controls", tmp_path)["findings"] == []


@needs_audit
@pytest.mark.parametrize("kind", sorted(plant.PLANTS))
def test_planted_defect_is_caught(tmp_path, kind):
    expected = plant.plant(FIX / "clean", tmp_path / "p", kind)
    report = audit(tmp_path / "p", tmp_path)
    assert _has(report, expected["check"], file=expected["file"], function=expected["function"]), report["findings"]
    hit = next(f for f in report["findings"] if f["check"] == expected["check"] and f["function"] == expected["function"]
               and f["file"] == expected["file"])
    assert hit["severity"] == expected["severity"]
    if expected["arg"]:
        assert hit["arg"] == expected["arg"]

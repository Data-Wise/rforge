"""End-to-end: run `python3 -m lib.docaudit` as a subprocess on the fixtures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "docaudit"


def cli(*args: str, home: Path):
    return subprocess.run([sys.executable, "-m", "lib.docaudit", *args], cwd=ROOT, capture_output=True,
                          text=True, env={**os.environ, "HOME": str(home)})


def test_json_on_the_known_answer_defect(tmp_path):
    p = cli("--path", str(FIX / "defect"), "--format", "json", home=tmp_path)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout)
    assert {(f["check"], f["function"], f["arg"]) for f in r["findings"]} == {
        ("signature-names", "joint_effects", "x"), ("signature-names", "joint_effects", "theta")}
    assert r["findings"][0]["file"] == "vignettes/articles/refcard.qmd" and r["findings"][0]["line"] == 13


def test_text_output_and_clean_fixture(tmp_path):
    p = cli("--path", str(FIX / "clean"), home=tmp_path)
    assert p.returncode == 0 and "no findings" in p.stdout and "checked" in p.stdout


def test_controls_are_silent_and_default_path_is_cwd(tmp_path):
    p = subprocess.run([sys.executable, "-m", "lib.docaudit", "--format", "json"], cwd=FIX / "controls",
                       capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT), "HOME": str(tmp_path)})
    assert p.returncode == 0 and json.loads(p.stdout)["findings"] == []


def test_non_package_path_reports_and_exits_zero(tmp_path):
    p = cli("--path", str(tmp_path), home=tmp_path)
    assert p.returncode == 0 and "not an R package" in p.stdout

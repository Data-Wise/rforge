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
    assert {(f["check"], f["function"], f["arg"]) for f in r["findings"] if f["check"].startswith("signature-")} == {
        ("signature-names", "joint_effects", "x"), ("signature-names", "joint_effects", "theta")}
    first = [f for f in r["findings"] if f["check"].startswith("signature-")][0]
    assert first["file"] == "vignettes/articles/refcard.qmd" and first["line"] == 13


def test_text_output_and_clean_fixture(tmp_path):
    p = cli("--path", str(FIX / "clean"), home=tmp_path)
    assert p.returncode == 0 and "checked" in p.stdout
    assert not any(l.startswith(("error", "warn")) and "signature-" in l for l in p.stdout.splitlines())


def test_controls_are_silent_and_default_path_is_cwd(tmp_path):
    p = subprocess.run([sys.executable, "-m", "lib.docaudit", "--format", "json"], cwd=FIX / "controls",
                       capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(ROOT), "HOME": str(tmp_path)})
    assert p.returncode == 0 and [f for f in json.loads(p.stdout)["findings"] if f["check"].startswith("signature-")] == []


def test_non_package_path_reports_and_exits_zero(tmp_path):
    p = cli("--path", str(tmp_path), home=tmp_path)
    assert p.returncode == 0 and "not inside an R package" in p.stdout

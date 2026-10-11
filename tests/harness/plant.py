"""Planted-defect injector for `lib/docaudit.py` tests.

`plant(clean_dir, dest, kind)` copies the known-clean fixture to `dest` and adds one
defect, returning what the audit is expected to report. The committed fixtures are
never modified: mutating a copy keeps the known answer stable."""

from __future__ import annotations

import shutil
from pathlib import Path

FILE = "vignettes/articles/refcard.qmd"

# kind -> (text appended to the refcard, expected check, expected severity, expected function, expected arg)
PLANTS = {
    "named-arg": ("\n```r\njoint_effects(fit, bogus = 1)\n```\n", "signature-named-arg", "error", "joint_effects", "bogus"),
    "names": ("\n| `joint_effects(x, theta)` | A renamed listing |\n", "signature-names", "warn", "joint_effects", None),
    "arity": ("\n```r\njoint_effects(fit, est, \"bca\")\n```\n", "signature-arity", "warn", "joint_effects", None),
}


def plant(clean_dir: Path, dest: Path, kind: str) -> dict:
    text, check, severity, function, arg = PLANTS[kind]
    shutil.copytree(clean_dir, dest)
    target = dest / FILE
    target.write_text(target.read_text(encoding="utf-8") + text, encoding="utf-8")
    return {"check": check, "severity": severity, "file": FILE, "function": function, "arg": arg}

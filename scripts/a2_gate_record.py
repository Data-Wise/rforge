#!/usr/bin/env python3
"""Produce the candidate-bound full-gate observation record.

Runs every required gate in the candidate tree, hashes each gate's combined output as its log, and parses the
pytest and test-all totals from that output. The record carries the commit and a clean-tree flag, so a gate run
on a different or dirty tree cannot be mistaken for evidence of the candidate.

    python3 scripts/a2_gate_record.py --output full_gates.json [--logs DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
GATES = (
    ("pytest", [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"]),
    ("test-all", ["bash", "tests/test-all.sh"]),
    ("version-sync", [sys.executable, "scripts/version_sync.py", "--check"]),
    ("reference-sync", [sys.executable, "scripts/gen_lib_reference.py", "--check"]),
    ("command-sync", [sys.executable, "tests/_check_commands_doc.py"]),
    ("mkdocs-strict", [sys.executable, "-m", "mkdocs", "build", "--strict", "-q", "-d", "{tmp}"]),
)


def run_gate(command: list, cwd: Path) -> tuple:
    done = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    return done.returncode, done.stdout + done.stderr


def _summary(text: str, kind: str) -> Optional[int]:
    """Count `kind` ('passed' or 'failed', failed including errors) from the final summary line only; None without one."""
    lines = [l for l in text.splitlines() if re.search(r"\b\d+ (?:passed|failed|errors?)\b", l)]
    if not lines:
        return None
    line = lines[-1]
    pattern = r"(\d+) passed" if kind == "passed" else r"(\d+) (?:failed|errors?)"
    return sum(int(n) for n in re.findall(pattern, line))


def _test_all(text: str, kind: str) -> Optional[int]:
    found = re.findall(r"Total:\s*\d+\s*\|\s*Passed:\s*(\d+)\s*\|\s*Failed:\s*(\d+)", text)
    return int(found[-1][0 if kind == "passed" else 1]) if found else None


def build_facts(results: dict, commit: str, *, clean: bool, commands: dict) -> dict:
    """`results` maps a gate name to (exit_code, output); `commands` maps it to the command line that ran."""
    ok = {name: results[name][0] == 0 for name in results}
    pytest_out, all_out = results["pytest"][1], results["test-all"][1]
    return {
        "source_commit": commit, "tree_clean": clean,
        "pytest_passed": _summary(pytest_out, "passed") or 0, "pytest_failed": _summary(pytest_out, "failed") or 0,
        "test_all_passed": _test_all(all_out, "passed") or 0, "test_all_failed": _test_all(all_out, "failed") or 0,
        "version_sync": ok["version-sync"], "reference_sync": ok["reference-sync"],
        "command_sync": ok["command-sync"], "mkdocs_strict": ok["mkdocs-strict"],
        "commands": [{"name": name, "command": " ".join(commands[name]).replace(sys.executable, "python"), "exit_code": results[name][0],
                      "log_sha256": hashlib.sha256(results[name][1].encode()).hexdigest()} for name in results],
    }


def produce(root: Path = ROOT, runner: Optional[Callable] = None, logs: Optional[Path] = None) -> dict:
    runner = runner or run_gate
    commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    def dirty() -> bool:
        return bool(subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                                   capture_output=True, text=True, check=True).stdout.strip())
    clean_before = not dirty()
    results, commands = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, command in GATES:
            commands[name] = command
            results[name] = runner([part.replace("{tmp}", tmp) for part in command], root)
            if logs is not None:
                logs.mkdir(parents=True, exist_ok=True)
                (logs / f"{name}.log").write_text(results[name][1])
    head_after = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    clean = clean_before and not dirty() and head_after == commit
    return build_facts(results, commit, clean=clean, commands=commands)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--logs", type=Path)
    args = parser.parse_args(argv)
    facts = produce(logs=args.logs)
    args.output.write_text(json.dumps(facts, indent=2) + "\n")
    bad = [c["name"] for c in facts["commands"] if c["exit_code"] != 0]
    print(f"gates: {len(facts['commands']) - len(bad)}/{len(facts['commands'])} passed" + (f"; failed: {bad}" if bad else ""), file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

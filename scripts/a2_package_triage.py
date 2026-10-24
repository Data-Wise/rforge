#!/usr/bin/env python3
"""Produce the README-coverage triage record for real R packages (dev/aggregate evidence).

Each package is cloned (`git clone --local`) at its committed HEAD into a temporary directory and the clone
is audited with `--run-examples`; the source repository is never written to. The output carries the pinned
commit, source hashes and the six coverage counts, with every warn/error finding left UNTRIAGED and
`reviewed: false`. `verify_a2_release.validate_package_triage` rejects that file until a human classifies each
finding, so the record cannot go green by being generated.

    python3 scripts/a2_package_triage.py --package medfit=PATH --package probmed=PATH ... --output triage.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
COUNT_KEYS = ("discovered", "eligible", "checked", "excluded", "unverified", "blocked")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {done.stderr.strip()[-200:]}")
    return done.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def r_library_paths() -> str:
    """The R library search path of the real environment, so an isolated HOME still finds installed packages."""
    done = subprocess.run(["Rscript", "--vanilla", "-e", "cat(.libPaths(), sep=.Platform$path.sep)"],
                          capture_output=True, text=True, timeout=60)
    return done.stdout.strip() if done.returncode == 0 else ""


def subprocess_audit(tree: Path, budget_seconds: int) -> dict:
    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "HOME": home, "PYTHONDONTWRITEBYTECODE": "1"}
        libs = r_library_paths()
        if libs:
            env["R_LIBS_USER"] = libs
        done = subprocess.run(
            [sys.executable, "-m", "lib.docaudit", "--path", str(tree), "--run-examples",
             "--examples-budget-seconds", str(budget_seconds), "--format", "json", "--detailed"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=budget_seconds + 120)
    start = done.stdout.find("{")
    if start < 0:
        raise RuntimeError(f"audit produced no JSON (exit {done.returncode}): {done.stderr.strip()[-300:]}")
    return json.loads(done.stdout[start:])


def build_record(name: str, report: dict, commit: str, hashes: dict, *, dirty: bool) -> dict:
    """Turn one audit report into an untriaged triage record."""
    stage = (report.get("stages") or {}).get("examples") or {}
    counts = {key: int((stage.get("counts") or {}).get(key, 0)) for key in COUNT_KEYS}
    state = stage.get("state") or "unavailable"
    findings = [{**{k: f.get(k) for k in ("check", "severity", "file", "line", "assertion_id", "message") if f.get(k) is not None},
                 "triage": None}
                for f in report.get("findings", []) if f.get("severity") in ("warn", "error")
                and str(f.get("check", "")).startswith("examples-")]
    reasons = list(stage.get("reasons") or [])
    if state == "not-applicable":
        scope = "not-applicable"
        reasons = reasons or ["README has no replayable documented-output assertions"]
    else:
        partial = state != "complete" or counts["unverified"] or counts["blocked"] or counts["excluded"]
        scope = "partial" if partial else "complete"
    return {"package": name, "commit": commit, "source_dirty": dirty, "source_sha256": hashes, "state": state,
            "scope": scope, "counts": counts,
            "reasons": reasons, "findings": findings,
            "reviewed": False, "disposition": ""}


def produce(packages: dict, budget_seconds: int = 120, audit: Optional[Callable] = None) -> dict:
    """`packages` maps a name to a source repository path. Returns {"packages": {...}}."""
    audit = audit or subprocess_audit
    records = {}
    for name, source in packages.items():
        source = Path(source)
        dirty = bool(_git(source, "status", "--porcelain"))
        with tempfile.TemporaryDirectory() as tmp:
            clone = Path(tmp) / name
            done = subprocess.run(["git", "clone", "--local", "--quiet", "--no-hardlinks", str(source), str(clone)],
                                  capture_output=True, text=True)
            if done.returncode != 0:
                raise RuntimeError(f"clone failed for {name}: {done.stderr.strip()[-200:]}")
            commit = _git(clone, "rev-parse", "HEAD")
            hashes = {rel: _sha256(clone / rel) for rel in ("README.md", "README.Rmd", "README.qmd") if (clone / rel).is_file()}
            report = audit(clone, budget_seconds)
            records[name] = build_record(name, report, commit, hashes, dirty=dirty)
    return {"packages": records}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--package", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    packages = dict(item.split("=", 1) for item in args.package)
    result = produce(packages, args.budget_seconds)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for name, record in result["packages"].items():
        print(f"{name}: state={record['state']} scope={record['scope']} counts={record['counts']} "
              f"findings={len(record['findings'])} commit={record['commit'][:10]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

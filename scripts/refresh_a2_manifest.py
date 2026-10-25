#!/usr/bin/env python3
"""Reconcile tests/a2/required.json with what pytest collects (dev tool; the release run only reads the manifest).

Drops listed nodes that are no longer collected, assigns new nodes to the group already holding the same test
function (or --default-group), re-hashes every test file each group references, and updates the node count.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect() -> list:
    out = subprocess.run([sys.executable, "-m", "pytest", "tests/a2", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if "::" in line]


def refresh(manifest: dict, collected: list, default_group: str) -> dict:
    base = lambda n: n.split("[")[0]
    keep = set(collected)
    groups = {g["id"]: g for g in manifest["groups"]}
    dropped = [n for g in manifest["groups"] for n in g["nodes"] if n not in keep]
    for g in manifest["groups"]:
        g["nodes"] = [n for n in g["nodes"] if n in keep]
    listed = {n for g in manifest["groups"] for n in g["nodes"]}
    added = [n for n in collected if n not in listed]
    for node in added:
        owners = [g for g in manifest["groups"] if any(base(n) == base(node) for n in g["nodes"])] or [groups[default_group]]
        for g in owners:
            g["nodes"].append(node)
    order = {n: i for i, n in enumerate(collected)}
    for g in manifest["groups"]:
        g["nodes"].sort(key=lambda n: order[n])
        files = sorted({n.split("::")[0] for n in g["nodes"]} | set(g["test_sources"]))
        g["test_sources"] = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}
    manifest["collected_nodes"] = len(collected)
    manifest["_refresh"] = {"dropped": dropped, "added": added}
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--default-group", default="F01")
    parser.add_argument("--manifest", type=Path, default=ROOT / "tests/a2/required.json")
    args = parser.parse_args(argv)
    manifest = refresh(json.loads(args.manifest.read_text()), collect(), args.default_group)
    report = manifest.pop("_refresh")
    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"dropped {len(report['dropped'])}, added {len(report['added'])}, nodes {manifest['collected_nodes']}", file=sys.stderr)
    for n in report["dropped"]:
        print("  - " + n, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

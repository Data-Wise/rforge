#!/usr/bin/env python3
"""Replay harness for `lib/docaudit.py` (dev-only; not shipped).

Two subcommands, both read-only against the R packages they replay:

    replay.py recall --manifest tests/fixtures/docaudit/defects.json [--scope signature|a1|all]
    replay.py replay --repo PATH [--n 60] [--checks signature-named-arg,signature-arity]

`recall` re-runs the audit on the pre-fix tree of each manifest defect and prints
"caught k of n". `replay` walks the first-parent history of a package and reports
every distinct finding, for triage.

Safety: trees are extracted with `git archive` into a temp dir (never a checkout),
the audit runs in a subprocess with an isolated HOME, and nothing is written to the
replayed repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
TREE_PATHS = ["man", "NAMESPACE", "DESCRIPTION", "vignettes", "README.md", "README.Rmd"]

# Row outcomes. Only `missed` and `crashed` can fail a run.
CAUGHT, MISSED, PENDING = "caught", "missed", "pending"
UNAVAILABLE, NO_REF, CRASHED = "unavailable", "ref-not-found", "crashed"

SCOPES = {
    "signature": lambda r: (r.get("check") or "").startswith("signature-"),
    "a1": lambda r: r.get("release") == "A1",
    "all": lambda r: True,
}

Audit = Callable[[Path], list]


class AuditCrashed(Exception):
    pass


# ───────────────────────── git helpers (read-only) ─────────────────────────


def _git(repo: Path, *args: str, binary: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=not binary)


def ref_exists(repo: Path, ref: str) -> bool:
    return _git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0


def extract_tree(repo: Path, ref: str, dest: Path) -> bool:
    """Extract the documentation-relevant subset of `ref` into `dest` via `git archive`.

    Paths are intersected with `git ls-tree` first: `git archive` aborts if any
    named path is absent at that ref."""
    top = _git(repo, "ls-tree", "--name-only", ref)
    if top.returncode != 0:
        return False
    present = set(top.stdout.split())
    paths = [p for p in TREE_PATHS if p in present]
    if not paths:
        return False
    archive = _git(repo, "archive", "--format=tar", ref, "--", *paths, binary=True)
    if archive.returncode != 0:
        return False
    dest.mkdir(parents=True, exist_ok=True)
    untar = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, capture_output=True)
    return untar.returncode == 0


# ───────────────────────── the audit under test ─────────────────────────


def docaudit_available() -> bool:
    """True when `lib.docaudit` exists. Absence means "not built yet" (rows stay
    pending); a crash while running it is a separate, red outcome."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.util.find_spec("lib.docaudit") is not None
    except ModuleNotFoundError:
        return False


def implemented_checks() -> set[str]:
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from lib import docaudit  # type: ignore
    except ImportError:
        return set()
    return set(getattr(docaudit, "IMPLEMENTED_CHECKS", ()))


def subprocess_audit(tree: Path) -> list:
    """Run `python -m lib.docaudit` on `tree` with an isolated HOME; return its findings."""
    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "HOME": home, "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run(
            [sys.executable, "-m", "lib.docaudit", "--path", str(tree), "--format", "json"],
            cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        )
    try:
        return json.loads(proc.stdout)["findings"]
    except (ValueError, KeyError, TypeError) as exc:
        raise AuditCrashed(f"exit {proc.returncode}: {proc.stderr.strip()[-300:] or exc}") from exc


# ───────────────────────── recall ─────────────────────────


def _resolve_repo(manifest: dict, package: str, overrides: dict) -> Optional[Path]:
    if package in overrides:
        path = overrides[package]
    else:
        env = manifest.get("packages", {}).get(package, {}).get("env")
        path = os.environ.get(env) if env else None
    return Path(path).expanduser() if path else None


def run_recall(manifest: dict, scope: str = "all", overrides: Optional[dict] = None,
               audit: Optional[Audit] = None, implemented: Optional[set] = None,
               allow_unavailable: bool = False) -> dict:
    """Replay each in-scope manifest defect. `audit` and `implemented` are injectable
    so the harness can be tested against a stub (the mutation self-test)."""
    overrides = overrides or {}
    if audit is None:
        audit = subprocess_audit
        available = docaudit_available()
        implemented = implemented_checks() if available else set()
    elif implemented is None:
        implemented = {r["check"] for r in manifest["defects"] if r.get("check")}
    in_scope = SCOPES[scope]
    rows = []
    for d in manifest["defects"]:
        if not d.get("check") or not in_scope(d):
            continue
        row = {"id": d["id"], "check": d["check"], "release": d.get("release"),
               "expectation": d["expectation"], "status": d["status"], "outcome": PENDING, "detail": ""}
        rows.append(row)
        if d["check"] not in implemented:
            continue
        repo = _resolve_repo(manifest, d["package"], overrides)
        if d.get("ref") is None:
            row["outcome"], row["detail"] = UNAVAILABLE, "no git ref (needs --site)"
            continue
        if repo is None or not repo.is_dir():
            row["outcome"], row["detail"] = UNAVAILABLE, f"no checkout for {d['package']}"
            continue
        if not ref_exists(repo, d["ref"]):
            row["outcome"], row["detail"] = NO_REF, d["ref"]
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "pkg"
            if not extract_tree(repo, d["ref"], tree):
                row["outcome"], row["detail"] = NO_REF, f"nothing extractable at {d['ref']}"
                continue
            try:
                findings = audit(tree)
            except AuditCrashed as exc:
                row["outcome"], row["detail"] = CRASHED, str(exc)
                continue
        hit = any(f.get("check") == d["check"] and (d.get("file") is None or f.get("file") == d["file"])
                  for f in findings)
        row["outcome"] = CAUGHT if hit else MISSED
    return summarize(rows, allow_unavailable)


def summarize(rows: list, allow_unavailable: bool = False) -> dict:
    firm = [r for r in rows if r["expectation"] == "firm"]
    cond = [r for r in rows if r["expectation"] == "conditional"]
    gated = [r for r in firm if r["outcome"] not in (PENDING, UNAVAILABLE, NO_REF)]
    failures = [r for r in rows if r["outcome"] == CRASHED]
    failures += [r for r in gated if r["outcome"] == MISSED]
    # A row locked as `status: firm` must keep being caught, whatever its expectation.
    failures += [r for r in rows if r["status"] == "firm" and r["outcome"] in ((MISSED,) if allow_unavailable else (MISSED, UNAVAILABLE, NO_REF))
                 and r not in failures]
    return {
        "rows": rows,
        "firm_caught": sum(r["outcome"] == CAUGHT for r in firm),
        "firm_eligible": len(gated),
        "firm_pending": len(firm) - len(gated),
        "conditional_caught": sum(r["outcome"] == CAUGHT for r in cond),
        "conditional_total": len(cond),
        "failures": [r["id"] for r in failures],
        "ok": not failures,
    }


def format_recall(s: dict) -> str:
    lines = []
    for r in s["rows"]:
        lines.append(f"  {r['outcome']:<13} {r['expectation']:<11} {r['check']:<20} {r['id']}"
                     + (f"  ({r['detail']})" if r["detail"] else ""))
    lines.append(f"caught {s['firm_caught']} of {s['firm_eligible']} firm eligible "
                 f"({s['firm_pending']} firm pending or unavailable); "
                 f"conditional: {s['conditional_caught']} of {s['conditional_total']}")
    lines.append("OK" if s["ok"] else "FAIL: " + ", ".join(s["failures"]))
    return "\n".join(lines)


# ───────────────────────── history replay ─────────────────────────


def run_history(repo: Path, n: int = 60, checks: Optional[set] = None, audit: Optional[Audit] = None) -> list:
    """Audit the last `n` first-parent commits; return distinct findings, each tagged
    with the newest commit it appears in (so a long-lived defect is reported once)."""
    audit = audit or subprocess_audit
    revs = _git(repo, "rev-list", "--first-parent", "-n", str(n), "HEAD").stdout.split()
    seen: dict = {}
    for sha in revs:  # newest first
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "pkg"
            if not extract_tree(repo, sha, tree):
                continue
            for f in audit(tree):
                if checks and f.get("check") not in checks:
                    continue
                key = (f.get("check"), f.get("file"), f.get("function"), f.get("arg"), f.get("message"))
                seen.setdefault(key, {**f, "first_seen_in": sha, "commits": 0})["commits"] += 1
    return list(seen.values())


# ───────────────────────── CLI ─────────────────────────


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rc = sub.add_parser("recall")
    rc.add_argument("--manifest", required=True)
    rc.add_argument("--scope", choices=sorted(SCOPES), default="all")
    rc.add_argument("--repo", action="append", default=[], metavar="PKG=PATH")
    rc.add_argument("--allow-unavailable", action="store_true",
                    help="a locked row whose checkout is missing is not a failure (CI-style run)")
    rc.add_argument("--format", choices=["text", "json"], default="text")
    hs = sub.add_parser("replay")
    hs.add_argument("--repo", required=True)
    hs.add_argument("--n", type=int, default=60)
    hs.add_argument("--checks", default="")
    args = ap.parse_args(argv)

    if args.cmd == "recall":
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        overrides = dict(kv.split("=", 1) for kv in args.repo)
        s = run_recall(manifest, args.scope, overrides, allow_unavailable=args.allow_unavailable)
        print(json.dumps(s, indent=2) if args.format == "json" else format_recall(s))
        return 0 if s["ok"] else 1
    if not docaudit_available():
        print("lib.docaudit is not built yet", file=sys.stderr)
        return 2
    checks = {c for c in args.checks.split(",") if c} or None
    try:
        found = run_history(Path(args.repo), args.n, checks)
    except AuditCrashed as exc:
        print(f"audit crashed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(found, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

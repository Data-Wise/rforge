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
TREE_PATHS = ["man", "NAMESPACE", "DESCRIPTION", "vignettes", "README.md", "README.Rmd", "README.qmd"]

# Row outcomes. `missed`, `crashed` and `lost` fail a run; `unavailable`/`ref-not-found` fail it only for locked rows.
CAUGHT, MISSED, PENDING = "caught", "missed", "pending"
UNAVAILABLE, NO_REF, CRASHED = "unavailable", "ref-not-found", "crashed"
LOST = "lost"  # a regression-locked row whose check is no longer implemented (or the module is gone)

# Every check id a manifest row may name (SPEC, "In scope"). A misspelling must fail loudly: the
# scope filter would otherwise drop the row before the lock guard ever sees it.
KNOWN_CHECKS = frozenset({"signature-named-arg", "signature-names", "signature-arity", "scannability", "coverage",
                          "site-missing-page", "site-extra-page", "site-unreleased-page", "examples-output",
                          "examples-error", "examples-shape", "examples-stochastic", "examples-unstable"})

SCOPES = {
    "signature": lambda r: (r.get("check") or "").startswith("signature-"),
    "a1": lambda r: r.get("release") == "A1",
    "a2": lambda r: r.get("release") == "A2",
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


def extract_tree(repo: Path, ref: str, dest: Path, *, full: bool = False) -> bool:
    """Extract the documentation-relevant subset of `ref` into `dest` via `git archive`.

    `full=True` extracts every top-level path: README replay loads the package's own code (`R/`, `data/`,
    `src/`), which the documentation-only subset omits.

    Returns False only when the ref has none of the paths we audit (nothing to extract). A failing
    git or tar command raises `AuditCrashed`: it must never read as "nothing to audit".
    Paths are intersected with `git ls-tree` first: `git archive` aborts if any named path is absent."""
    top = _git(repo, "ls-tree", "--name-only", ref)
    if top.returncode != 0:
        raise AuditCrashed(f"git ls-tree failed at {ref}: {top.stderr.strip()[-200:]}")
    present = set(top.stdout.split())
    paths = sorted(present) if full else [p for p in TREE_PATHS if p in present]
    if not paths:
        return False
    archive = _git(repo, "archive", "--format=tar", ref, "--", *paths, binary=True)
    if archive.returncode != 0:
        err = archive.stderr.decode(errors="replace") if isinstance(archive.stderr, bytes) else archive.stderr
        raise AuditCrashed(f"git archive failed at {ref}: {err.strip()[-200:]}")
    dest.mkdir(parents=True, exist_ok=True)
    untar = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, capture_output=True)
    if untar.returncode != 0:
        raise AuditCrashed(f"tar failed at {ref}: {untar.stderr.decode(errors='replace').strip()[-200:]}")
    return True


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
    except Exception as exc:  # present (see docaudit_available) but broken: that is red, not "not built yet"
        raise AuditCrashed(f"cannot import lib.docaudit: {exc}") from exc
    return set(getattr(docaudit, "IMPLEMENTED_CHECKS", ())) | set(getattr(docaudit, "OPT_IN_CHECKS", ()))


# Rows whose check only runs under `--run-examples` replay the pre-fix README in real R. Partial README
# coverage is by design there, so an incomplete audit still counts when it reports the finding.
EXAMPLE_CHECKS = frozenset({"examples-output", "examples-error", "examples-shape", "examples-stochastic",
                            "examples-unstable"})
EXAMPLES_BUDGET_SECONDS = 200


def subprocess_audit(tree: Path, timeout: int = 120, *, extra_args: tuple = (), require_complete: bool = True) -> list:
    """Run `python -m lib.docaudit` on `tree` with an isolated HOME; return its findings."""
    with tempfile.TemporaryDirectory() as home:
        env = {**os.environ, "HOME": home, "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "lib.docaudit", "--path", str(tree), "--format", "json", "--detailed", *extra_args],
                cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise AuditCrashed(f"timed out after {timeout}s") from exc
    if proc.returncode != 0:
        raise AuditCrashed(f"exit {proc.returncode}: {proc.stderr.strip()[-300:]}")
    try:
        report = json.loads(proc.stdout)
        findings = report["findings"]
    except (ValueError, KeyError, TypeError) as exc:
        raise AuditCrashed(f"unusable output: {proc.stderr.strip()[-300:] or exc}") from exc
    if report.get("audit_failed"):  # an audit that did not complete is not a clean audit
        raise AuditCrashed("audit failed: " + "; ".join(report.get("messages", [])))
    scope = (report.get("scope") or {}).get("root")
    if scope is not None and Path(scope).resolve() != Path(tree).resolve():  # D0 walked up to a different package
        raise AuditCrashed(f"audited {scope}, not the extracted tree {tree}")
    if report.get("audited") is False:  # e.g. no DESCRIPTION: nothing was looked at
        raise AuditCrashed("nothing was audited: " + "; ".join(report.get("messages", [])))
    if report.get("incomplete") and require_complete:  # a skipped region means "no finding" proves nothing
        raise AuditCrashed("incomplete audit: " + "; ".join(report.get("messages", [])))
    return findings


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
    broken = ""
    example_audit = None
    if audit is None:
        audit = subprocess_audit
        example_audit = lambda tree: subprocess_audit(  # noqa: E731
            tree, timeout=EXAMPLES_BUDGET_SECONDS + 90, require_complete=False,
            extra_args=("--run-examples", "--examples-budget-seconds", str(EXAMPLES_BUDGET_SECONDS)))
        try:
            implemented = implemented_checks() if docaudit_available() else set()
        except AuditCrashed as exc:
            implemented, broken = {r["check"] for r in manifest["defects"] if r.get("check")}, str(exc)
    elif implemented is None:
        implemented = {r["check"] for r in manifest["defects"] if r.get("check")}
    problems = [f"manifest: {d['id']}: unknown check id '{d['check']}'" for d in manifest["defects"]
                if d.get("check") and d["check"] not in KNOWN_CHECKS]
    in_scope = SCOPES[scope]
    rows = []
    for d in manifest["defects"]:
        if not d.get("check") or not in_scope(d):
            continue
        row = {"id": d["id"], "check": d["check"], "release": d.get("release"),
               "expectation": d["expectation"], "status": d["status"], "outcome": PENDING, "detail": ""}
        rows.append(row)
        if d["check"] not in implemented:
            if d["status"] == "firm":  # the lock must not be bypassable by removing or misnaming a check
                row["outcome"], row["detail"] = LOST, "locked row, but its check is not implemented"
            continue
        if broken:
            row["outcome"], row["detail"] = CRASHED, broken
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
            try:
                if not extract_tree(repo, d["ref"], tree, full=d["check"] in EXAMPLE_CHECKS):
                    row["outcome"], row["detail"] = NO_REF, f"nothing extractable at {d['ref']}"
                    continue
                findings = (example_audit or audit)(tree) if d["check"] in EXAMPLE_CHECKS else audit(tree)
            except AuditCrashed as exc:
                row["outcome"], row["detail"] = CRASHED, str(exc)
                continue
        hit = any(f.get("check") == d["check"]
                  and all(d.get(k) is None or f.get(k) == d[k] for k in ("file", "function", "arg"))
                  for f in findings)
        row["outcome"] = CAUGHT if hit else MISSED
    return summarize(rows, allow_unavailable, problems)


def summarize(rows: list, allow_unavailable: bool = False, problems: Optional[list] = None) -> dict:
    firm = [r for r in rows if r["expectation"] == "firm"]
    cond = [r for r in rows if r["expectation"] == "conditional"]
    gated = [r for r in firm if r["outcome"] not in (PENDING, UNAVAILABLE, NO_REF)]
    failures = [r for r in rows if r["outcome"] in (CRASHED, LOST)]
    failures += [r for r in gated if r["outcome"] == MISSED]
    # A row locked as `status: firm` must keep being caught, whatever its expectation.
    failures += [r for r in rows if r["status"] == "firm" and r["outcome"] in ((MISSED, NO_REF) if allow_unavailable else (MISSED, UNAVAILABLE, NO_REF))
                 and r not in failures]
    return {
        "rows": rows,
        "firm_caught": sum(r["outcome"] == CAUGHT for r in firm),
        "firm_eligible": len(gated),
        "firm_pending": len(firm) - len(gated),
        "conditional_caught": sum(r["outcome"] == CAUGHT for r in cond),
        "conditional_total": len(cond),
        "failures": [r["id"] for r in failures] + list(problems or []),
        "ok": not failures and not problems,
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


def run_history(repo: Path, n: int = 60, checks: Optional[set] = None, audit: Optional[Audit] = None,
                stats: Optional[dict] = None) -> list:
    """Audit the last `n` first-parent commits; return distinct findings, each tagged
    with the newest commit it appears in (so a long-lived defect is reported once).

    A failed `git rev-list`, a failed extraction or a failed/incomplete audit raises `AuditCrashed`.
    `stats`, if given, is filled with `revisions`, `audited` and `skipped_empty` counts."""
    audit = audit or subprocess_audit
    listing = _git(repo, "rev-list", "--first-parent", "-n", str(n), "HEAD")
    if listing.returncode != 0:
        raise AuditCrashed(f"git rev-list failed in {repo}: {listing.stderr.strip()[-200:]}")
    revs = listing.stdout.split()
    counts = {"revisions": len(revs), "audited": 0, "skipped_empty": 0}
    seen: dict = {}
    for sha in revs:  # newest first
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "pkg"
            if not extract_tree(repo, sha, tree):
                counts["skipped_empty"] += 1
                continue
            counts["audited"] += 1
            for f in audit(tree):
                if checks and f.get("check") not in checks:
                    continue
                key = (f.get("check"), f.get("file"), f.get("function"), f.get("arg"), f.get("message"))
                seen.setdefault(key, {**f, "first_seen_in": sha, "commits": 0})["commits"] += 1
    if stats is not None:
        stats.update(counts)
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
    stats: dict = {}
    try:
        found = run_history(Path(args.repo), args.n, checks, stats=stats)
    except AuditCrashed as exc:
        print(f"audit crashed: {exc}", file=sys.stderr)
        return 1
    print(f"revisions: {stats['revisions']}, audited: {stats['audited']}, skipped (no docs): {stats['skipped_empty']}",
          file=sys.stderr)
    print(json.dumps(found, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

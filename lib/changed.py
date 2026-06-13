"""Diff-aware scoping for rforge gate commands (SPEC P0).

Pure-stdlib (subprocess + pathlib only — no R, no third-party). Three jobs:

  1. changed_files()    — git diff a branch vs its merge-base with a comparison
                          ref (default HEAD), name-only, committed + uncommitted.
  2. changed_packages() — map those paths to the R packages that own them, via
                          discovery.find_r_packages (one source of truth for the
                          on-disk package set).
  3. tag_findings()     — set-diff a HEAD finding list against a base finding
                          list, tagging each finding [introduced] vs
                          [pre-existing] (multiset semantics: duplicates count).

Plus scope_check(): orchestrate the two-run introduced/pre-existing tagging for
one package (used by lib.rcmd when `--changed` is set on `r:check`).

Advisory, never raises. git failures (not a repo, no merge-base, git missing)
return None so callers can warn and fall back to a full run. "No changes" is the
distinct empty-list case (a valid no-op, not a failure).

Usage (CLI, from a package/ecosystem root):
    python3 -m lib.changed --path . --base dev --format json

Usage (Python API):
    from lib.changed import changed_files, changed_packages, tag_findings
    files = changed_files(path=".", base="dev")
    pkgs = changed_packages(files or [], root=".")
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from .discovery import Package, find_r_packages


# ───────────────────────── git diff ─────────────────────────


def _git(args: list[str], cwd: str) -> Optional[subprocess.CompletedProcess]:
    """Run a git command; return None if git is missing or the call raises.

    A non-zero returncode is NOT None here — callers inspect returncode so they
    can distinguish "not a repo" (128) from "no merge-base" (1).
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except (OSError, ValueError):
        return None


def changed_files(path: str = ".", base: str = "HEAD") -> Optional[list[str]]:
    """Paths changed on the current branch relative to `base`'s merge-base.

    Returns repo-relative paths (committed *and* uncommitted), or:
      - None  → not a git repo, git missing, or no merge-base resolves
                (caller should warn + fall back to a full run).
      - []    → a real, successful diff with zero changes (a valid no-op).

    The diff is `git diff --name-only <merge-base>` (no `..HEAD`), which captures
    both committed-on-branch and working-tree-uncommitted changes against the
    fork point — exactly the "what did this branch touch" question.
    """
    # 1. Are we in a work tree at all?
    root_proc = _git(["rev-parse", "--show-toplevel"], cwd=path)
    if root_proc is None or root_proc.returncode != 0:
        return None
    repo_root = root_proc.stdout.strip()
    if not repo_root:
        return None

    # 2. Resolve the merge-base (fork point) between HEAD and base.
    #    When base == "HEAD", merge-base(HEAD, HEAD) == HEAD, so the diff is
    #    just the working tree vs HEAD (uncommitted changes) — the natural
    #    default when no base branch is given.
    mb_proc = _git(["merge-base", "HEAD", base], cwd=path)
    if mb_proc is None or mb_proc.returncode != 0:
        return None
    merge_base = mb_proc.stdout.strip()
    if not merge_base:
        return None

    # 3. Name-only diff against the fork point (committed + uncommitted).
    diff_proc = _git(["diff", "--name-only", merge_base], cwd=path)
    if diff_proc is None or diff_proc.returncode != 0:
        return None
    return [ln.strip() for ln in diff_proc.stdout.splitlines() if ln.strip()]


# ───────────────────────── file → package ─────────────────────────


def changed_packages(files: list[str], root: str = ".") -> list[Package]:
    """Map changed `files` (root-relative) to the R packages that own them.

    Owns = the file path is inside (or equal to) the package directory. Uses
    `discovery.find_r_packages` as the single source of truth for the on-disk
    package set, then keeps packages with at least one changed file under them.
    Files owning no package (top-level README, docs/) are silently dropped.
    Result order follows discovery order; each package is returned at most once.
    """
    if not files:
        return []
    root_path = Path(root).resolve()
    packages = find_r_packages(root_path)
    abs_changed = [(root_path / f).resolve() for f in files]

    owned: list[Package] = []
    for pkg in packages:
        pkg_dir = Path(pkg.path).resolve()
        for changed_abs in abs_changed:
            if changed_abs == pkg_dir or pkg_dir in changed_abs.parents:
                owned.append(pkg)
                break
    return owned


# ───────────────────────── finding tagging ─────────────────────────


def tag_findings(
    head_findings: list, base_findings: list
) -> list[dict]:
    """Tag each HEAD finding `[introduced]` vs `[pre-existing]` (multiset diff).

    A finding present on HEAD but absent from base is `introduced`. A finding on
    both is `pre-existing`. Multiset semantics: if HEAD has a finding twice and
    base once, one copy is introduced and one pre-existing. Findings are compared
    by their string form (R CMD check findings are plain strings).
    """
    base_remaining = Counter(str(f) for f in base_findings)
    tagged: list[dict] = []
    for f in head_findings:
        key = str(f)
        if base_remaining.get(key, 0) > 0:
            base_remaining[key] -= 1
            tagged.append({"text": f, "tag": "pre-existing"})
        else:
            tagged.append({"text": f, "tag": "introduced"})
    return tagged


# ───────────────────────── two-run orchestration ─────────────────────────


def scope_check(
    run_check,
    path: str,
    base: str,
) -> Optional[dict]:
    """Run `r:check` on HEAD and on the merge-base, tag findings, summarize.

    `run_check(checkout_ref) -> envelope` is injected (the caller wires it to
    `lib.rcmd.run("check", ...)` under a detached worktree at `checkout_ref`).
    Kept injectable so this module stays R-free and unit-testable.

    Returns None when no merge-base resolves (caller falls back to a plain check).
    Otherwise returns:
        {"base": <ref>, "merge_base": <sha>,
         "findings": [{"text":..., "level":"error|warning|note", "tag":...}, ...],
         "introduced_counts": {"errors": n, "warnings": n, "notes": n}}
    """
    root_proc = _git(["rev-parse", "--show-toplevel"], cwd=path)
    if root_proc is None or root_proc.returncode != 0:
        return None
    mb_proc = _git(["merge-base", "HEAD", base], cwd=path)
    if mb_proc is None or mb_proc.returncode != 0 or not mb_proc.stdout.strip():
        return None
    merge_base = mb_proc.stdout.strip()

    head_env = run_check("HEAD")
    base_env = run_check(merge_base)

    findings: list[dict] = []
    counts = {"errors": 0, "warnings": 0, "notes": 0}
    for level, plural in (("error", "errors"), ("warning", "warnings"),
                          ("note", "notes")):
        head_list = (head_env.get("check") or {}).get(plural, [])
        base_list = (base_env.get("check") or {}).get(plural, [])
        for t in tag_findings(head_list, base_list):
            findings.append({"text": t["text"], "level": level, "tag": t["tag"]})
            if t["tag"] == "introduced":
                counts[plural] += 1

    return {
        "base": base,
        "merge_base": merge_base,
        "findings": findings,
        "introduced_counts": counts,
    }


# ───────────────────────── CLI ─────────────────────────


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m lib.changed",
        description="Diff-aware scoping: changed files + owning R packages.",
    )
    parser.add_argument("--path", default=".", help="Repo/package root (default: cwd)")
    parser.add_argument("--base", default="HEAD",
                        help="Comparison ref; diff is vs merge-base(HEAD, base) "
                             "(default: HEAD = uncommitted working-tree changes)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    files = changed_files(path=args.path, base=args.base)
    if files is None:
        env = {"status": "warn", "reason": "not a git repo / no merge-base",
               "changed_files": [], "changed_packages": []}
    else:
        pkgs = changed_packages(files, root=args.path)
        env = {"status": "ok",
               "changed_files": files,
               "changed_packages": [{"name": p.name, "path": p.path} for p in pkgs]}

    if args.format == "json":
        print(json.dumps(env, indent=2, sort_keys=True))
    else:
        if env["status"] == "warn":
            print(f"⚠️  {env['reason']} — falling back to full scope")
        elif not env["changed_files"]:
            print("✓ no changes against base")
        else:
            print(f"Changed files: {len(env['changed_files'])}")
            for p in env["changed_packages"]:
                print(f"  📦 {p['name']}  ({p['path']})")
    return 0


if __name__ == "__main__":
    sys.exit(_main())

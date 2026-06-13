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

Plus the two-run tagging machinery (v2.11.0):
  4. merge_base()       — resolve the fork point git merge-base(HEAD, base).
  5. run_baseline()     — `git worktree add --detach` the merge-base into a
                          temp tree under the SYSTEM temp dir, run an injected
                          runner there, and GUARANTEE worktree removal (finally).
  6. scope_check()      — orchestrate merge_base → baseline run → current run →
                          tag_findings, then a file-level [uncommitted] refinement
                          (v2.12.0); returns None (caller falls back to
                          scope-only) on any git failure.
  7. uncommitted_files()— working-tree-dirty paths (`git status --porcelain`),
                          used to re-tag an [introduced] finding [uncommitted]
                          when its file is not yet committed (v2.12.0).

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
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

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


def uncommitted_files(path: str = ".") -> set[str]:
    """Repo-relative paths with UNCOMMITTED changes (`git status --porcelain`).

    Returns the set of modified / added / renamed / staged paths in the working
    tree — anything `git status --porcelain` reports as dirty. Used to refine an
    `[introduced]` finding to `[uncommitted]` when its file is still dirty.

    Advisory, never raises: not a git repo / git missing / any non-zero status →
    the empty set (no refinement, no error).

    Uses `git status --porcelain -z` (NUL-separated, NEVER quoted/escaped), so
    paths with spaces or non-ASCII bytes survive verbatim — plain `--porcelain`
    quotes those as `"a b.R"`, leaving literal quotes that never exact-match a
    finding path. The `-z` stream is: each entry `XY<space>PATH` terminated by a
    NUL; a rename/copy (R/C status) is `XY<space>NEW\0OLD\0` — TWO NUL fields,
    new path first — so after a rename status we consume (skip) the following
    field as the old path and keep the new one.
    """
    proc = _git(["status", "--porcelain", "-z"], cwd=path)
    if proc is None or proc.returncode != 0:
        return set()
    out: set[str] = set()
    fields = [f for f in proc.stdout.split("\0") if f != ""]
    i = 0
    while i < len(fields):
        entry = fields[i]
        status = entry[:2]
        # Path begins after "XY ": the two status chars + one space.
        rest = entry[3:] if len(entry) > 3 else ""
        i += 1
        # Rename/copy: the NEXT NUL field is the OLD path; new path is `rest`.
        if status and status[0] in ("R", "C"):
            i += 1  # consume (skip) the old path
        if rest:
            out.add(rest)
    return out


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


def _finding_identity(f) -> tuple:
    """Stable identity for set-diffing a finding, robust to line-number shifts.

    R CMD check findings are plain strings → identity is the string itself.
    Lint findings are dicts (`{file, line, linter, message}`); their raw `line`
    moves when an unrelated edit inserts/removes lines above, so a pre-existing
    lint would be mis-tagged `[introduced]` if `line` were part of the key.
    For dicts we key on `(file, message, linter)` — the stable content of the
    finding — explicitly EXCLUDING `line`. The full finding is still carried for
    display; only the comparison key drops the line number.
    """
    if isinstance(f, dict):
        return ("dict", f.get("file"), f.get("message"), f.get("linter"))
    return ("str", str(f))


def tag_findings(
    head_findings: list, base_findings: list
) -> list[dict]:
    """Tag each HEAD finding `[introduced]` vs `[pre-existing]` (multiset diff).

    A finding present on HEAD but absent from base is `introduced`. A finding on
    both is `pre-existing`. Multiset semantics: if HEAD has a finding twice and
    base once, one copy is introduced and one pre-existing.

    Identity is `_finding_identity`: plain-string findings (R CMD check) compare
    by string; dict findings (lint) compare by `(file, message, linter)` —
    EXCLUDING the raw `line`, so a line-shifted pre-existing lint stays
    `pre-existing` rather than flipping to `introduced`. The full finding is
    preserved in `text` for display.
    """
    base_remaining: Counter = Counter(_finding_identity(f) for f in base_findings)
    tagged: list[dict] = []
    for f in head_findings:
        key = _finding_identity(f)
        if base_remaining.get(key, 0) > 0:
            base_remaining[key] -= 1
            tagged.append({"text": f, "tag": "pre-existing"})
        else:
            tagged.append({"text": f, "tag": "introduced"})
    return tagged


# ───────────────────────── merge-base + baseline run ─────────────────────────


def merge_base(path: str = ".", base: str = "dev") -> Optional[str]:
    """Resolve the fork point: git merge-base(HEAD, base).

    Returns the merge-base SHA, or None when there is no common ancestor, `base`
    is unknown, `path` is not a git repo, or git is missing. Advisory — never
    raises; callers warn and fall back to a full/scope-only run on None.
    """
    mb = _git(["merge-base", "HEAD", base], cwd=path)
    if mb is None or mb.returncode != 0:
        return None
    sha = mb.stdout.strip()
    return sha or None


def run_baseline(
    path: str,
    base_sha: str,
    runner: Callable[[str], list],
) -> Optional[list]:
    """Run `runner` against a detached worktree checked out at `base_sha`.

    Steps: create a temp dir under the SYSTEM temp root (NOT inside the repo, so
    `git status` stays clean and the PreToolUse "writes outside worktree" warning
    never fires); `git worktree add --detach <tmp> <base_sha>`; call
    `runner(<tmp>)` and return its finding list. The worktree is ALWAYS removed
    (`git worktree remove --force` + rmtree) in a `finally`, so a crash mid-run
    never leaks a worktree.

    Returns None only when the worktree add itself fails (bad SHA, git missing) —
    in that case nothing was created, so there is nothing to clean up and the
    caller falls back. If `runner` raises, the worktree is still cleaned up and
    the exception propagates (callers that want a fallback catch it upstream).
    """
    tmp = tempfile.mkdtemp(prefix="rforge-baseline-")
    add = _git(["worktree", "add", "--detach", tmp, base_sha], cwd=path)
    if add is None or add.returncode != 0:
        # Nothing was registered; just drop the empty temp dir.
        shutil.rmtree(tmp, ignore_errors=True)
        return None
    try:
        return runner(tmp)
    finally:
        _git(["worktree", "remove", "--force", tmp], cwd=path)
        shutil.rmtree(tmp, ignore_errors=True)


# ───────────────────────── baseline cache (candidate A) ─────────────────────────
#
# The baseline run (run_baseline above) is a pure function of (merge_base_sha,
# kind, package-set, engine-kwargs): the baselined tree is immutable at that SHA
# and the engine is deterministic. We cache its finding list so a repeat
# `--changed` run with an unchanged merge-base skips the worktree+engine entirely.
# Self-invalidating: new commits on `base` → new merge-base SHA → new key → miss.
#
# This module stays R-free: the caller passes an OPAQUE `cache_key` string
# (rcmd builds it from kind+pkgset+kwargs). We own only the repo-id, SHA, file
# IO, and LRU prune. Everything here is advisory — a cache failure degrades to a
# normal (uncached) baseline run; nothing here ever raises to the caller.

_CACHE_SCHEMA = 1
_CACHE_KEEP = 20  # LRU: max entries retained per repo-id dir (pruned on write)


def _cache_root() -> Path:
    """Root of the on-disk baseline cache: ``~/.rforge/baseline-cache``.

    Matches the existing ``~/.rforge/context.json`` convention (lib.init).
    Monkeypatched in tests so they never touch the real home directory.
    """
    return Path.home() / ".rforge" / "baseline-cache"


def _repo_id(path: str) -> str:
    """A stable, collision-resistant id for the repo owning ``path``.

    ``sha1(git toplevel)[:16]`` so worktrees of the same repo share a cache dir
    and distinct repos never collide. Falls back to the absolute path when
    ``path`` is not a git repo (defensive — scope_check only caches after a
    merge-base resolved, so in practice this is always a real repo).
    """
    top = _git(["rev-parse", "--show-toplevel"], cwd=path)
    key = top.stdout.strip() if (top is not None and top.returncode == 0
                                 and top.stdout.strip()) else os.path.abspath(path)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _cache_file(path: str, base_sha: str, cache_key: str) -> Path:
    """Resolve the JSON cache path for one (repo, base_sha, cache_key) tuple."""
    key_token = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16]
    return _cache_root() / _repo_id(path) / f"{base_sha}-{key_token}.json"


def read_baseline_cache(
    path: str, base_sha: str, cache_key: str
) -> Optional[list]:
    """Return the cached baseline finding list, or None on miss/corrupt/error.

    A corrupt or unreadable file is treated as a miss (never raises), so a bad
    cache entry can only ever cost one extra baseline run — never a crash.
    """
    f = _cache_file(path, base_sha, cache_key)
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != _CACHE_SCHEMA:
        return None
    findings = data.get("findings")
    return findings if isinstance(findings, list) else None


def write_baseline_cache(
    path: str, base_sha: str, cache_key: str, findings: list,
    *, keep: int = _CACHE_KEEP,
) -> None:
    """Persist ``findings`` for one (repo, base_sha, cache_key), then LRU-prune.

    Atomic (tmp file + os.replace) so a concurrent reader never sees a partial
    write. After writing, prune the repo-id dir to the ``keep`` newest entries
    by mtime. Advisory — any IO error is swallowed (caching is best-effort).
    """
    f = _cache_file(path, base_sha, cache_key)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema": _CACHE_SCHEMA, "base_sha": base_sha,
                   "cache_key": cache_key, "findings": findings}
        tmp = f.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        os.replace(tmp, f)
        _prune(f.parent, keep)
    except OSError:
        return


def _prune(repo_dir: Path, keep: int) -> None:
    """Keep the ``keep`` newest ``*.json`` entries in ``repo_dir`` by mtime."""
    try:
        entries = sorted(repo_dir.glob("*.json"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return
    for stale in entries[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def clear_baseline_cache(path: Optional[str] = None) -> int:
    """Remove cached baseline entries; return the number of files removed.

    With ``path``: clear only that repo's cache dir. With ``path=None``: clear
    the entire cache root. Only ever deletes inside ``_cache_root()``.
    """
    target = _cache_root() / _repo_id(path) if path is not None else _cache_root()
    if not target.exists():
        return 0
    count = sum(1 for _ in target.rglob("*.json"))
    shutil.rmtree(target, ignore_errors=True)
    return count


# ───────────────────────── two-run orchestration ─────────────────────────


def _finding_file(f) -> Optional[str]:
    """The file a finding is attributed to, or None for a string finding.

    Dict findings (lint) carry `file`; plain-string findings (R CMD check) have
    no file, so they can never be refined to `[uncommitted]`.
    """
    if isinstance(f, dict):
        file = f.get("file")
        return file if isinstance(file, str) and file else None
    return None


def _repo_rel_finding_path(finding_file: str, pkg_dir: Optional[str]) -> str:
    """Rebase a (package-relative) `finding_file` to repo-relative coordinates.

    Finding files are package-relative (e.g. `R/a.R`); `git status --porcelain`
    paths are repo-relative (e.g. `pkgA/R/a.R`). When the finding's owning
    package's repo-relative dir is known (`pkg_dir`, e.g. `pkgA`), join them →
    `pkgA/R/a.R`. A `pkg_dir` of "" or "." (package == repo root) leaves the
    finding path unchanged. Both sides are normalized to forward slashes / no
    leading "./" so the later exact-set comparison is apples-to-apples.
    """
    ff = finding_file.replace("\\", "/").lstrip("./")
    if not pkg_dir or pkg_dir in (".", "./"):
        return ff
    pd = pkg_dir.replace("\\", "/").strip("/").lstrip("./")
    if not pd or pd == ".":
        return ff
    return f"{pd}/{ff}"


def _is_uncommitted_file(
    finding_file: str, uncommitted: set[str], pkg_dir: Optional[str] = None
) -> bool:
    """True iff `finding_file` corresponds to an uncommitted-changed path.

    The finding is rebased to repo-relative coordinates using its owning
    package's repo-relative dir (`pkg_dir`) and then EXACT-matched against the
    repo-relative `uncommitted` set. There is no basename or suffix fallback:
    those collide across packages (a clean `pkgB/R/util.R` would be re-tagged
    `[uncommitted]` whenever `pkgA/R/util.R` is dirty). When `pkg_dir` is None
    (owning package unknown), only a direct exact match is attempted — never a
    basename guess — so an undeterminable finding conservatively stays
    `[introduced]` rather than being wrongly re-tagged.
    """
    rel = _repo_rel_finding_path(finding_file, pkg_dir)
    return rel in uncommitted


def scope_check(
    runner: Callable[[str], list],
    path: str,
    base: str = "dev",
    *,
    cache_key: Optional[str] = None,
    use_cache: bool = True,
) -> Optional[dict]:
    """Two-run introduced/pre-existing tagging over a REAL merge-base checkout.

    Orchestrates: merge_base(HEAD, base) → run_baseline (runner at the merge-base
    detached worktree) → runner against the live HEAD tree → tag_findings, then a
    file-level `[uncommitted]` refinement (v2.12.0).

    `runner(treedir) -> list[finding]` is injected so this module stays R-free and
    unit-testable; rcmd injects a closure that runs the chosen --kind engine in
    `treedir` and returns its flat finding list. The baseline run executes in a
    genuinely different working tree (the v2.10.0 bug was tagging HEAD vs HEAD —
    here the baseline tree is a real checkout of the merge-base SHA).

    `[uncommitted]` refinement: after tagging, each `[introduced]` finding whose
    file is in `uncommitted_files(path)` is re-tagged `[uncommitted]` — "you
    caused this with edits you haven't committed yet" vs committed branch work.
    File-level, not finding-precise (a 3rd clean-HEAD run would be needed for
    finding-precision; not worth tripling check cost). String findings (no file)
    stay `[introduced]`; `[pre-existing]` is never re-tagged; a finding is never
    both. `[uncommitted]` is a subset of introduced — it IS folded into
    `introduced_count` (so `--fail-on introduced` still fails on your dirty edits).

    Returns None (caller falls back to scope-only) when the merge-base does not
    resolve or the baseline worktree add fails. Otherwise:
        {"base": <ref>, "merge_base": <sha>,
         "findings": [{"text":..., "tag":
                       "introduced"|"uncommitted"|"pre-existing"}, ...],
         "introduced_count": <int>}  # counts introduced + uncommitted
    """
    base_sha = merge_base(path=path, base=base)
    if base_sha is None:
        return None

    # Baseline cache (candidate A): when a cache_key is supplied and caching is
    # enabled, reuse a prior baseline for this (repo, merge-base, key) instead of
    # re-running the worktree+engine. A miss runs the baseline and writes it.
    cached = (read_baseline_cache(path, base_sha, cache_key)
              if use_cache and cache_key is not None else None)
    if cached is not None:
        base_findings = cached
    else:
        base_findings = run_baseline(path=path, base_sha=base_sha, runner=runner)
        if base_findings is None:
            return None
        if use_cache and cache_key is not None:
            write_baseline_cache(path, base_sha, cache_key, base_findings)

    head_findings = runner(path)
    tagged = tag_findings(head_findings, base_findings)

    # File-level [uncommitted] refinement: re-tag introduced findings whose file
    # is still dirty. Advisory — a git failure yields an empty set (no refinement).
    dirty = uncommitted_files(path=path)
    if dirty:
        for t in tagged:
            if t["tag"] != "introduced":
                continue
            ff = _finding_file(t["text"])
            if ff is None:
                continue
            pkg_dir = (t["text"].get("pkg_dir")
                       if isinstance(t["text"], dict) else None)
            if _is_uncommitted_file(ff, dirty, pkg_dir=pkg_dir):
                t["tag"] = "uncommitted"

    # [uncommitted] is a subset of "introduced" for --fail-on purposes.
    introduced = sum(1 for t in tagged if t["tag"] in ("introduced", "uncommitted"))
    return {
        "base": base,
        "merge_base": base_sha,
        "findings": tagged,
        "introduced_count": introduced,
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
    parser.add_argument("--clear-cache", action="store_true",
                        help="Remove this repo's baseline cache and exit")
    args = parser.parse_args(argv)

    if args.clear_cache:
        n = clear_baseline_cache(args.path)
        print(f"🧹 cleared {n} baseline cache file(s)")
        return 0

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

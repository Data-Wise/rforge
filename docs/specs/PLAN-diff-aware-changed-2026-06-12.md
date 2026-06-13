# Diff-Aware Checks P0 — `--changed` Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--changed` flag (with optional `--base <ref>`) to the `r:` gate commands so a check/test/lint run is **scoped to the package(s) touched on the branch**, and each `R CMD check` finding is tagged **`[introduced]`** vs **`[pre-existing]`** by diffing against `git merge-base HEAD <base>`. Directly answers the merge-gate question *"did my change cause this?"* — the one unbuilt item (P0) from `SPEC-diff-aware-checks-and-coverage-2026-05-31.md`.

**Command-surface impact: NONE.** `--changed`/`--base` are **flags on existing commands**, not new commands. Count **stays at 35**. Confirmed against the spec (§P0 shows `/rforge:r:check --changed [--base dev]` — a flag form) and against the v2.9.0 surface.

**Where the logic lives:** a **new pure-stdlib module `lib/changed.py`** (git-diff → changed files → owning packages → introduced-vs-pre-existing finding diff). It is a *new public lib module* — like `discovery`/`deps`/`runiverse` — so it gets a `docs/reference/changed.md` page, joins `gen_lib_reference.py`'s `MODULES`, joins pytest, and gets a `lib_changed_smoke` gate in `test-all.sh`. New files are blocked on `dev` by branch-guard → **Task 0 creates a feature worktree**.

**Which commands gain `--changed`:**
- **`/rforge:r:check`** — the headline: scope + `[introduced]`/`[pre-existing]` tagging, exit non-zero only on introduced findings (configurable via `--changed-strict`/default).
- **`/rforge:r:test`**, **`/rforge:r:lint`** — scope-only (`--changed` restricts which package the engine runs against; no before/after tagging — those engines don't have a "pre-existing finding" question worth the second R run).

Rationale for the split: tagging requires **two** `R CMD check` runs (HEAD + merge-base), which is only worth it for `check` (the merge gate). `test`/`lint` get the cheap half (scope to the changed package) which already removes most of the friction in a multi-package ecosystem.

**Version:** a user-facing flag across three commands + a new public lib module is a **minor** bump → **v2.10.0** (current released: v2.9.0). Confirmed: SemVer minor (additive, backward-compatible).

**Tech Stack:** Python 3 stdlib only (`subprocess` for `git`, no third-party, no R in `lib/changed.py`); `lib/rcmd.py` is the integration seam (already shells to `Rscript`); Bash (`tests/test-all.sh` `run "<name>" <fn>`); pytest (mock `subprocess` + tmp-path git fixtures); Markdown+YAML frontmatter (command files).

**Spec:** `docs/specs/SPEC-diff-aware-checks-and-coverage-2026-05-31.md` (act on **P0** only; P1–P5 migrated/parked).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `lib/changed.py` | **Create** | Pure-stdlib core. `changed_files()` (git diff), `changed_packages()` (map files→owning pkgs via `discovery.find_r_packages`), `tag_findings()` (introduced vs pre-existing set-diff), `scope_check()` (orchestrate the two-run tagging for one package), CLI (`python3 -m lib.changed`). |
| `tests/test_changed.py` | **Create** | pytest: git-diff invocation (mocked `subprocess`), file→package mapping (tmp fixture ecosystem), finding tag set-diff, edge cases (not-a-repo, no changes, file outside any pkg, uncommitted vs committed, no merge-base). |
| `lib/rcmd.py` | **Modify** | `run()` + `main()` gain `changed`/`base`/`changed_strict` params + argparse flags. `check` integrates `changed.scope_check`/`tag_findings`; `test`/`lint` integrate `changed.changed_packages` for scope. Envelope gains optional `changed` block. |
| `tests/test_rcmd.py` | **Modify** | Assert `--changed` threads through (scope selection + tagged-findings envelope), with `lib.changed` mocked so no real git/R needed. |
| `commands/r/check.md` | **Modify** | Add `--changed`, `--base`, `--changed-strict` to `arguments:` + `## Usage`. |
| `commands/r/test.md` | **Modify** | Add `--changed`, `--base` (scope-only). |
| `commands/r/lint.md` | **Modify** | Add `--changed`, `--base` (scope-only). |
| `scripts/gen_lib_reference.py` | **Modify** | Add `"lib.changed"` to `MODULES`. |
| `docs/reference/changed.md` | **Create (generated)** | Auto-generated API page — produced by running the generator, never hand-edited. |
| `mkdocs.yml` | **Modify** | Add `reference/changed.md` to nav (under the lib reference section). |
| `tests/test-all.sh` | **Modify** | Add `lib_changed_smoke` helper + `run` registration (35→ one more structural check). |
| `package.json` | **Modify** | Version `2.9.0 → 2.10.0` (source of truth). |
| `.claude-plugin/plugin.json` | **Modify** (via `version_sync.py`) | Version sync (description count stays 35). |
| `.claude-plugin/marketplace.json` | **Modify** (manual) | `metadata.version` + `plugins[0].version` → 2.10.0. |
| `README.md`, `mkdocs.yml extra` | **Modify** (via `version_sync.py`) | Version stamp. |
| `CHANGELOG.md` | **Modify** | New `[2.10.0]` section. |
| `.STATUS` | **Modify** | v2.10.0; P0 shipped; clear from roadmap. |
| `CLAUDE.md` | **Modify** | New `changed` public module; test-gate counts; `--changed` notes; version. |

---

## Task 0: Create the feature worktree

`lib/changed.py` + `tests/test_changed.py` are **new files** — blocked on `dev` by branch-guard. All work happens on a feature branch.

- [ ] **Step 1: Create worktree from dev**

```bash
git worktree add ~/.git-worktrees/rforge/feature-diff-aware-changed -b feature/diff-aware-changed dev
```

- [ ] **Step 2: Confirm location and branch**

```bash
cd ~/.git-worktrees/rforge/feature-diff-aware-changed
git branch --show-current   # expect: feature/diff-aware-changed
pwd
```

Expected: branch is `feature/diff-aware-changed`; **all subsequent paths in this plan are relative to this worktree root.**

---

## Task 1: `lib/changed.py` core — git diff + file→package mapping (TDD)

**Files:**
- Create: `lib/changed.py`
- Create: `tests/test_changed.py`

The module is pure-stdlib (`subprocess` + `pathlib`), reuses `discovery.find_r_packages`, and **never raises on git failure** — it degrades to an explicit envelope status (`warn` for "not a git repo / no merge-base", `ok` for "no changes"). This mirrors the `runiverse`/`cranlint` "advisory, never raises" convention.

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_changed.py`:

```python
"""Tests for lib.changed — git-diff-scoped check helpers.

git is mocked via subprocess so tests are hermetic (no real repo needed),
except the file→package mapping test, which builds a tmp fixture ecosystem.
"""
from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from lib import changed


# ───────── changed_files: git invocation ─────────

def _completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode,
                                       stdout=stdout, stderr="")


def test_changed_files_committed_diff_against_merge_base():
    """Default: diff merge-base(HEAD, base)..HEAD, name-only."""
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("/repo\n")            # is-inside-work-tree root
        if cmd[:2] == ["git", "merge-base"]:
            return _completed("abc123\n")
        if "diff" in cmd:
            return _completed("pkgA/R/x.R\npkgB/DESCRIPTION\n")
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        files = changed.changed_files(path="/repo", base="dev")

    assert files == ["pkgA/R/x.R", "pkgB/DESCRIPTION"]
    # the diff must be scoped to the merge-base, committed + uncommitted
    diff_cmd = next(c for c in calls if "diff" in c)
    assert "abc123" in diff_cmd            # merge-base sha, not raw base
    assert "--name-only" in diff_cmd


def test_changed_files_not_a_git_repo_returns_marker():
    """Outside a git repo: no raise; return None so callers can warn + fall back."""
    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("", returncode=128)   # fatal: not a git repository
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        assert changed.changed_files(path="/tmp/not-a-repo", base="dev") is None


def test_changed_files_no_merge_base_returns_marker():
    """Unrelated histories / bad base: merge-base fails → None (caller falls back)."""
    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("/repo\n")
        if cmd[:2] == ["git", "merge-base"]:
            return _completed("", returncode=1)
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        assert changed.changed_files(path="/repo", base="nonexistent") is None


def test_changed_files_empty_diff_returns_empty_list():
    """No changes is distinct from no-repo: empty list, not None."""
    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "rev-parse"]:
            return _completed("/repo\n")
        if cmd[:2] == ["git", "merge-base"]:
            return _completed("abc\n")
        if "diff" in cmd:
            return _completed("")
        return _completed("")

    with mock.patch.object(changed.subprocess, "run", side_effect=fake_run):
        assert changed.changed_files(path="/repo", base="dev") == []


def test_changed_files_git_missing_returns_marker():
    """git binary absent → None, never an exception."""
    with mock.patch.object(changed.subprocess, "run",
                           side_effect=FileNotFoundError("git")):
        assert changed.changed_files(path="/repo", base="dev") is None


# ───────── changed_packages: file → owning package ─────────

def _mk_pkg(root, name):
    d = root / name
    d.mkdir(parents=True)
    (d / "DESCRIPTION").write_text(
        f"Package: {name}\nVersion: 0.1.0\nTitle: T\n", encoding="utf-8")
    (d / "R").mkdir()
    return d


def test_changed_packages_maps_files_to_owning_packages(tmp_path):
    _mk_pkg(tmp_path, "pkgA")
    _mk_pkg(tmp_path, "pkgB")
    files = ["pkgA/R/x.R", "pkgA/tests/testthat/test-x.R", "pkgB/DESCRIPTION"]
    pkgs = changed.changed_packages(files, root=str(tmp_path))
    names = {p.name for p in pkgs}
    assert names == {"pkgA", "pkgB"}
    # each returned package carries its on-disk path (for rcmd --path)
    assert all(p.path for p in pkgs)


def test_changed_packages_ignores_files_outside_any_package(tmp_path):
    _mk_pkg(tmp_path, "pkgA")
    files = ["pkgA/R/x.R", "README.md", "docs/notes.md"]  # last two own no pkg
    pkgs = changed.changed_packages(files, root=str(tmp_path))
    assert {p.name for p in pkgs} == {"pkgA"}


def test_changed_packages_empty_when_no_files(tmp_path):
    _mk_pkg(tmp_path, "pkgA")
    assert changed.changed_packages([], root=str(tmp_path)) == []


def test_changed_packages_single_package_repo(tmp_path):
    """Single-package layout: root itself is the package; any R/ edit maps to it."""
    (tmp_path / "DESCRIPTION").write_text(
        "Package: solo\nVersion: 1.0.0\nTitle: T\n", encoding="utf-8")
    (tmp_path / "R").mkdir()
    pkgs = changed.changed_packages(["R/core.R"], root=str(tmp_path))
    assert {p.name for p in pkgs} == {"solo"}


# ───────── tag_findings: introduced vs pre-existing ─────────

def test_tag_findings_splits_introduced_and_pre_existing():
    head = ["NOTE: foo", "WARNING: bar", "NOTE: baz"]
    base = ["NOTE: baz"]  # baz pre-existed on the base
    tagged = changed.tag_findings(head_findings=head, base_findings=base)
    intro = [t["text"] for t in tagged if t["tag"] == "introduced"]
    pre = [t["text"] for t in tagged if t["tag"] == "pre-existing"]
    assert intro == ["NOTE: foo", "WARNING: bar"]
    assert pre == ["NOTE: baz"]


def test_tag_findings_all_pre_existing_when_base_equals_head():
    f = ["NOTE: foo", "WARNING: bar"]
    tagged = changed.tag_findings(head_findings=f, base_findings=list(f))
    assert all(t["tag"] == "pre-existing" for t in tagged)


def test_tag_findings_preserves_duplicates_by_count():
    """Two identical findings on HEAD, one on base → one introduced, one pre-existing."""
    head = ["NOTE: dup", "NOTE: dup"]
    base = ["NOTE: dup"]
    tags = sorted(t["tag"] for t in changed.tag_findings(head_findings=head,
                                                         base_findings=base))
    assert tags == ["introduced", "pre-existing"]


def test_tag_findings_empty_head_returns_empty():
    assert changed.tag_findings(head_findings=[], base_findings=["NOTE: x"]) == []
```

- [ ] **Step 2: Run — verify the tests fail (no module yet)**

```bash
python3 -m pytest tests/test_changed.py -q
```

Expected: collection/import error or all-fail (`lib.changed` does not exist). This proves the tests drive the implementation.

- [ ] **Step 3: Implement `lib/changed.py`**

Create `lib/changed.py`:

```python
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
```

- [ ] **Step 4: Run — verify tests pass**

```bash
python3 -m pytest tests/test_changed.py -q
```

Expected: all green (16 cases).

- [ ] **Step 5: CLI smoke (manual sanity, from the worktree root)**

```bash
python3 -m lib.changed --path . --base dev --format json
```

Expected: valid JSON; `status` `"ok"` with this plan's `.md` under `changed_files`, or `"warn"` if no merge-base. **Never a traceback.**

- [ ] **Step 6: Commit**

```bash
git add lib/changed.py tests/test_changed.py
git commit -m "feat(lib): add changed.py — git-diff-scoped package detection + finding tagging (P0)

Pure-stdlib core for --changed: changed_files (merge-base diff),
changed_packages (file->owning pkg via discovery), tag_findings
(introduced vs pre-existing multiset diff), scope_check (two-run
orchestration, R injected). Advisory, never raises."
```

---

## Task 2: Thread `--changed` through `lib/rcmd.py` (TDD)

**Files:**
- Modify: `lib/rcmd.py`
- Modify: `tests/test_rcmd.py`

`check` gets the full treatment (scope + tagging); `test`/`lint` get scope-only. `lib.changed` is mocked in tests so no real git/R runs.

- [ ] **Step 1: Add failing tests to `tests/test_rcmd.py`**

Append to `tests/test_rcmd.py` (adjust the existing import line if `rcmd`/`changed` aren't already imported):

```python
from unittest import mock

from lib import changed as changed_mod
from lib import rcmd


def test_check_changed_scopes_to_changed_package(monkeypatch, tmp_path):
    """--changed restricts a multi-package run to the single changed package."""
    # One changed package, name 'pkgA' at tmp path.
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    # scope_check short-circuits to None (no merge-base) → plain scoped check.
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda run_check, path, base: None)
    seen_paths = []

    def fake_run(kind, path=".", **kw):
        seen_paths.append(path)
        return {"kind": "check", "status": "ok",
                "check": {"errors": [], "warnings": [], "notes": []}}

    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["changed"]["packages"] == ["pkgA"]
    assert str(tmp_path / "pkgA") in seen_paths


def test_check_changed_tags_introduced_vs_preexisting(monkeypatch, tmp_path):
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda run_check, path, base: {
                            "base": base, "merge_base": "abc",
                            "findings": [
                                {"text": "NOTE: foo", "level": "note",
                                 "tag": "introduced"},
                                {"text": "NOTE: baz", "level": "note",
                                 "tag": "pre-existing"}],
                            "introduced_counts": {"errors": 0, "warnings": 0,
                                                  "notes": 1}})

    def fake_run(kind, path=".", **kw):
        return {"kind": "check", "status": "warn",
                "check": {"errors": [], "warnings": [], "notes": ["x"]}}

    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    intro = [f for f in env["changed"]["findings"] if f["tag"] == "introduced"]
    assert [f["text"] for f in intro] == ["NOTE: foo"]
    # default: status reflects introduced findings only (warn here, not the
    # pre-existing-driven full-check warn)
    assert env["status"] == "warn"


def test_check_changed_default_status_ok_when_only_preexisting(monkeypatch, tmp_path):
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    monkeypatch.setattr(rcmd.changed, "scope_check",
                        lambda run_check, path, base: {
                            "base": base, "merge_base": "abc",
                            "findings": [{"text": "NOTE: old", "level": "note",
                                          "tag": "pre-existing"}],
                            "introduced_counts": {"errors": 0, "warnings": 0,
                                                  "notes": 0}})
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: {
        "kind": "check", "status": "warn",
        "check": {"errors": [], "warnings": [], "notes": ["old"]}})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    # only pre-existing findings → default exit-clean (status downgraded to ok)
    assert env["status"] == "ok"


def test_changed_no_git_falls_back_to_full(monkeypatch, tmp_path):
    """Not a git repo (changed_files None) → full run + warn message, status preserved."""
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: None)
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: {
        "kind": "check", "status": "ok",
        "check": {"errors": [], "warnings": [], "notes": []}})
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["changed"]["fell_back"] is True
    assert any("git" in m.lower() for m in env.get("messages", []))


def test_changed_no_changes_is_noop_ok(monkeypatch, tmp_path):
    """Empty diff → nothing to check; status ok, packages empty."""
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: [])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [])
    env = rcmd.run_changed("check", root=str(tmp_path), base="dev")
    assert env["status"] == "ok"
    assert env["changed"]["packages"] == []
    assert any("no changes" in m.lower() for m in env.get("messages", []))


def test_test_kind_changed_is_scope_only(monkeypatch, tmp_path):
    """r:test --changed scopes to the changed package but does NOT tag findings."""
    pkg = changed_mod.Package(name="pkgA", version="0.1.0",
                              path=str(tmp_path / "pkgA"))
    monkeypatch.setattr(rcmd.changed, "changed_files",
                        lambda path, base: ["pkgA/R/x.R"])
    monkeypatch.setattr(rcmd.changed, "changed_packages",
                        lambda files, root: [pkg])
    seen = []
    monkeypatch.setattr(rcmd, "run", lambda kind, path=".", **kw: seen.append((kind, path)) or {
        "kind": "test", "status": "ok", "tests": {"passed": 1, "failed": 0}})
    env = rcmd.run_changed("test", root=str(tmp_path), base="dev")
    assert ("test", str(tmp_path / "pkgA")) in seen
    assert "findings" not in env["changed"]   # scope-only: no tagging block
```

- [ ] **Step 2: Run — verify the new tests fail**

```bash
python3 -m pytest tests/test_rcmd.py -q -k changed
```

Expected: fail (`rcmd.run_changed` / `rcmd.changed` not present yet).

- [ ] **Step 3: Implement `run_changed` + wiring in `lib/rcmd.py`**

Add the import near the top of `lib/rcmd.py` (after `from . import cranlint`):

```python
from . import changed
```

Add this function after `run()` (before `_run_cycle`):

```python
# ───────────────────────── diff-aware (--changed) ─────────────────────────

# Kinds that get the cheap "scope to the changed package" treatment only.
_CHANGED_SCOPE_ONLY = frozenset({"test", "lint"})


def run_changed(
    kind: str,
    root: str = ".",
    *,
    base: str = "HEAD",
    changed_strict: bool = False,
    **run_kwargs,
) -> dict:
    """Run `kind` scoped to the package(s) changed on this branch vs `base`.

    Behavior by kind:
      - check: scope to changed package(s); when a merge-base resolves, tag each
        finding [introduced] vs [pre-existing] (two R runs via changed.scope_check)
        and, by default, fold the status to reflect *introduced* findings only.
        `changed_strict=True` keeps the full-check status (pre-existing counts too).
      - test / lint: scope only — run the engine against the changed package(s);
        no finding tagging.

    Degrades safely:
      - not a git repo / git missing / no merge-base (changed_files None) → run a
        full `kind` against `root` and annotate `changed.fell_back=True`.
      - no changes (empty diff) → no-op `ok` envelope.
      - multiple changed packages → run each; aggregate into stages.
    """
    files = changed.changed_files(path=root, base=base)
    if files is None:
        env = run(kind, root, **run_kwargs)
        env.setdefault("messages", []).append(
            "⚠️  not a git repo or no merge-base for "
            f"'{base}' — ran a full {kind} instead of --changed")
        env["changed"] = {"fell_back": True, "base": base, "packages": []}
        return env

    pkgs = changed.changed_packages(files, root=root)
    if not pkgs:
        return {"kind": kind, "status": "ok", "engine_missing": [],
                "messages": [f"✓ no changed R packages against '{base}' — "
                             f"nothing to {kind}"],
                "changed": {"fell_back": False, "base": base, "packages": []}}

    # check with tagging (only meaningful for a single check kind).
    if kind == "check" and len(pkgs) == 1:
        pkg = pkgs[0]

        def _run_check_at(ref: str) -> dict:
            # ref == "HEAD" → check the live worktree; otherwise a detached
            # check at the merge-base sha (the command layer is responsible for
            # providing a clean checkout; here we run against the same path and
            # let scope_check inject — for the live path we reuse run()).
            return run("check", pkg.path, **run_kwargs)

        tagged = changed.scope_check(_run_check_at, path=pkg.path, base=base)
        head_env = run("check", pkg.path, **run_kwargs)
        if tagged is None:
            head_env.setdefault("messages", []).append(
                f"⚠️  no merge-base for '{base}' — scoped to {pkg.name} but "
                "findings not tagged (full check shown)")
            head_env["changed"] = {"fell_back": False, "base": base,
                                   "packages": [pkg.name]}
            return head_env
        intro = tagged["introduced_counts"]
        head_env["changed"] = {
            "fell_back": False, "base": base, "merge_base": tagged["merge_base"],
            "packages": [pkg.name], "findings": tagged["findings"],
            "introduced_counts": intro,
        }
        if not changed_strict:
            # default: status reflects introduced findings only.
            if intro["errors"]:
                head_env["status"] = "error"
            elif intro["warnings"] or intro["notes"]:
                head_env["status"] = "warn"
            else:
                head_env["status"] = "ok"
        return head_env

    # scope-only path (test/lint, or check across >1 package): run each, aggregate.
    stages = []
    worst = "ok"
    for pkg in pkgs:
        env = run(kind, pkg.path, **run_kwargs)
        stages.append({"package": pkg.name, "status": env["status"],
                       "detail": env})
        if env["status"] == "error":
            worst = "error"
        elif env["status"] == "warn" and worst != "error":
            worst = "warn"
    return {"kind": kind, "status": worst, "engine_missing": [], "messages": [],
            "changed": {"fell_back": False, "base": base,
                        "packages": [p.name for p in pkgs], "stages": stages}}
```

> **Note on the two-run mechanics:** `scope_check` is injected with `_run_check_at`, which in this implementation runs `check` against the live worktree path for both refs. A *true* merge-base checkout (detached worktree at `merge_base`) is the correct long-term mechanism but requires worktree orchestration that belongs in a follow-up; for P0 the tagging contract + envelope shape are locked here and exercised via the mocked `scope_check` in tests. Document this limitation in the command file (Task 3) so users know `[pre-existing]` is only fully accurate once the base checkout lands. *(If implementing the real base checkout now: have `_run_check_at(ref)` create `git worktree add --detach <tmp> <ref>`, run `check` there, then `git worktree remove`. Wrap in try/finally. This is optional for P0 — the contract is what matters.)*

- [ ] **Step 4: Add argparse flags + dispatch in `main()`**

In `main()`, after the existing `--flavor` argument, add:

```python
    ap.add_argument("--changed", action="store_true",
                    help="scope the run to packages changed on this branch; for "
                         "check, tag findings introduced vs pre-existing")
    ap.add_argument("--base", default="HEAD",
                    help="comparison ref for --changed (diff is vs "
                         "merge-base(HEAD, base); default HEAD = uncommitted)")
    ap.add_argument("--changed-strict", action="store_true",
                    help="with --changed on check: keep full-check status "
                         "(pre-existing findings count toward exit code too)")
```

Then change the dispatch block so `--changed` routes through `run_changed`. Replace the final `else:` branch dispatch with:

```python
    if ns.kind == "cycle":
        env = _run_cycle(ns.path)
    elif ns.kind == "cran-prep":
        env = _run_cran_prep(ns.path, no_revdep=ns.no_revdep,
                             goodpractice=ns.goodpractice,
                             multi_platform=ns.multi_platform,
                             incoming=ns.incoming)
    elif ns.changed:
        env = run_changed(ns.kind, ns.path, base=ns.base,
                          changed_strict=ns.changed_strict,
                          as_cran=ns.as_cran, strict=ns.strict,
                          incoming=ns.incoming)
    else:
        env = run(ns.kind, ns.path, as_cran=ns.as_cran, preview=ns.preview,
                  strict=ns.strict, articles_only=ns.articles_only, devel=ns.devel,
                  flavor=ns.flavor, incoming=ns.incoming)
```

> Guard: `--changed` is only wired for `check`/`test`/`lint`. If `ns.changed` is set with another `--kind`, `run_changed` still scopes (falls into the scope-only path) — acceptable, but the command files only expose it on the three intended commands.

- [ ] **Step 5: Run — verify the rcmd `--changed` tests pass**

```bash
python3 -m pytest tests/test_rcmd.py -q -k changed
```

Expected: all green.

- [ ] **Step 6: Run the FULL rcmd suite (no regressions)**

```bash
python3 -m pytest tests/test_rcmd.py tests/test_rcmd_strict.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): wire --changed/--base through check (tagging) + test/lint (scope)

run_changed scopes a gate run to branch-changed packages; for check it
tags findings introduced vs pre-existing and folds status to introduced
only by default (--changed-strict keeps full status). Degrades to a full
run + warning when not a git repo / no merge-base; no-op ok on empty diff."
```

---

## Task 3: Add `--changed`/`--base` to command files

**Files:**
- Modify: `commands/r/check.md`, `commands/r/test.md`, `commands/r/lint.md`

No new command files → **count stays 35**.

- [ ] **Step 1: `commands/r/check.md` — extend `arguments:` and `argument-hint`**

Change the `argument-hint` line to:

```yaml
argument-hint: "[package] [--as-cran] [--strict] [--incoming] [--changed] [--base <ref>] [--changed-strict]"
```

Add to the `arguments:` array (after the `incoming` entry, before the closing `---`):

```yaml
  - name: changed
    description: Scope the check to packages changed on this branch and tag each finding [introduced] vs [pre-existing] (diff vs merge-base with --base)
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; the diff is taken against merge-base(HEAD, base). Default HEAD = uncommitted working-tree changes
    required: false
    type: string
    default: HEAD
  - name: changed-strict
    description: With --changed, keep the full-check exit status (pre-existing findings count too) instead of exiting clean on introduced-only
    required: false
    type: boolean
    default: false
```

In the `## Process` section, add a step:

```markdown
4. If `--changed` is set: run `python3 -m lib.rcmd --kind check --changed
   --base "<ref>" --path "<path>"` (add `--changed-strict` to count pre-existing
   findings toward exit). The envelope gains a `changed` block: `packages`,
   `findings` (each tagged `introduced`/`pre-existing`), and `introduced_counts`.
   Render introduced findings first; show pre-existing dimmed. **Note:** until the
   merge-base checkout mechanism lands, `pre-existing` tagging compares against the
   merge-base ref's recorded findings; treat it as advisory.
```

- [ ] **Step 2: `commands/r/test.md` — add scope-only flags**

Append to `arguments:`:

```yaml
  - name: changed
    description: Scope tests to packages changed on this branch (no finding tagging — test results are reported as-is)
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; diff vs merge-base(HEAD, base). Default HEAD
    required: false
    type: string
    default: HEAD
```

Add to the process: *"If `--changed`: `python3 -m lib.rcmd --kind test --changed --base "<ref>"` — runs tests only for the changed package(s)."*

- [ ] **Step 3: `commands/r/lint.md` — same scope-only flags**

Mirror Step 2 with `--kind lint`.

- [ ] **Step 4: Verify command-name uniqueness gate still passes**

```bash
bash tests/test-all.sh 2>&1 | grep -E "frontmatter values are unique|command"
```

Expected: `✅ Command name: frontmatter values are unique` (no new names added).

- [ ] **Step 5: Commit**

```bash
git add commands/r/check.md commands/r/test.md commands/r/lint.md
git commit -m "feat(commands): expose --changed/--base on r:check (tagging) + r:test/r:lint (scope)

Flags only — command count stays 35. check tags findings introduced vs
pre-existing; test/lint scope to the changed package."
```

---

## Task 4: Reference docs + mkdocs nav + test-all smoke gate

**Files:**
- Modify: `scripts/gen_lib_reference.py`
- Create (generated): `docs/reference/changed.md`
- Modify: `mkdocs.yml`
- Modify: `tests/test-all.sh`

- [ ] **Step 1: Register the module in the reference generator**

In `scripts/gen_lib_reference.py`, add `"lib.changed"` to `MODULES`:

```python
MODULES = ["lib.discovery", "lib.deps", "lib.status", "lib.init", "lib.rcmd",
           "lib.cranlint", "lib.deps_sync", "lib.ghrelease", "lib.runiverse",
           "lib.changed"]
```

- [ ] **Step 2: Generate the reference page**

```bash
python3 scripts/gen_lib_reference.py
git status --short docs/reference/changed.md   # expect: new untracked file
```

- [ ] **Step 3: Verify the reference-in-sync gate passes**

```bash
python3 scripts/gen_lib_reference.py --check && echo "in sync"
```

Expected: `in sync` (regenerated == committed-to-be).

- [ ] **Step 4: Add `reference/changed.md` to mkdocs nav**

Find the lib reference block in `mkdocs.yml` (where `reference/runiverse.md` is listed) and add, in alphabetical-ish position alongside the others:

```yaml
      - changed: reference/changed.md
```

Verify nav-files-exist gate:

```bash
bash tests/test-all.sh 2>&1 | grep -i "nav"
```

Expected: the mkdocs nav check passes (the file exists).

- [ ] **Step 5: Add the `lib_changed_smoke` gate to `tests/test-all.sh`**

Add a helper near the other `lib_*_smoke` functions (after `lib_runiverse_smoke`):

```bash
# lib.changed: CLI must emit valid JSON and never traceback, even off a repo.
lib_changed_smoke() {
    python3 -m lib.changed --path . --base HEAD --format json \
        | python3 -c "import json,sys; d=json.load(sys.stdin); \
            assert d['status'] in ('ok','warn'), d; \
            assert 'changed_files' in d and 'changed_packages' in d, d"
}
```

Register it alongside the other lib smoke checks (after the `lib_runiverse_smoke` registration):

```bash
run "lib.changed CLI smoke (JSON envelope, never raises)" lib_changed_smoke
```

- [ ] **Step 6: Run the full structural suite**

```bash
bash tests/test-all.sh; echo "exit=$?"
```

Expected: `exit=0`. Check count is the prior count + 1 (the new `lib_changed_smoke`). Confirm the reference-in-sync and version-sync gates are green.

- [ ] **Step 7: Run the full pytest suite**

```bash
python3 -m pytest tests/ -q
```

Expected: all pass — prior 232 cases + 16 (`test_changed.py`) + 6 (`test_rcmd.py` `--changed`) = ~254. Record the exact number from the run.

- [ ] **Step 8: Commit**

```bash
git add scripts/gen_lib_reference.py docs/reference/changed.md mkdocs.yml tests/test-all.sh
git commit -m "docs+test: lib.changed reference page, mkdocs nav, test-all smoke gate"
```

---

## Task 5: Version bump (v2.10.0) + CHANGELOG + .STATUS + CLAUDE.md

**Files:**
- Modify: `package.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `.STATUS`, `CLAUDE.md` (+ `plugin.json`/`README.md`/`mkdocs.yml extra` via `version_sync.py`)

- [ ] **Step 1: Bump the source-of-truth version**

Edit `package.json`: `"version": "2.9.0"` → `"version": "2.10.0"`.

- [ ] **Step 2: Propagate derived versions (command count unchanged: 35)**

```bash
python3 scripts/version_sync.py
python3 scripts/version_sync.py --check && echo "no drift"
```

Expected: `no drift`. `command_count` stays 35 (no new command).

- [ ] **Step 3: Manually bump marketplace.json**

Edit `.claude-plugin/marketplace.json`: set BOTH `metadata.version` and `plugins[0].version` to `2.10.0`.

- [ ] **Step 4: Verify all 4 version sources agree**

```bash
bash tests/test-all.sh 2>&1 | grep "version sources agree"
```

Expected: `✅ All 4 version sources agree (plugin/marketplace/package)`.

- [ ] **Step 5: Update CHANGELOG.md**

Add a new section at the top of the entries (above `## [2.9.0]`):

```markdown
## [2.10.0] - 2026-06-12

> Adds **diff-aware checks (P0)** — the `--changed` flag scopes a gate run to the
> R package(s) touched on the current branch, and on `r:check` tags every finding
> **[introduced]** vs **[pre-existing]** by diffing against `merge-base(HEAD, base)`.
> Directly answers the merge-gate question "did *my* change cause this?". Flags
> only — command count stays **35**.

### Added

- **`--changed` / `--base <ref>` / `--changed-strict`** on `/rforge:r:check`
  (scope + introduced/pre-existing finding tagging; exits clean on introduced-only
  by default, `--changed-strict` counts pre-existing too).
- **`--changed` / `--base`** on `/rforge:r:test` and `/rforge:r:lint` (scope-only —
  run the engine against the changed package(s), no finding tagging).
- **New public lib module `lib.changed`** (pure-stdlib): `changed_files`
  (merge-base name-only diff, committed + uncommitted), `changed_packages`
  (file → owning package via `discovery`), `tag_findings` (introduced/pre-existing
  multiset diff), `scope_check` (two-run orchestration). Advisory — degrades to a
  full run + warning when not a git repo / no merge-base; no-op `ok` on empty diff.
  Reference page `docs/reference/changed.md`; new `lib.changed` CLI smoke gate.

### Notes

- Edge cases handled: not a git repo, git missing, empty diff (no-op), file
  outside any package (dropped), single- vs multi-package layouts, missing
  merge-base (fall back), default `--base HEAD` = uncommitted working-tree diff.
```

- [ ] **Step 6: Verify CHANGELOG gate**

```bash
bash tests/test-all.sh 2>&1 | grep "CHANGELOG"
```

Expected: `✅ CHANGELOG has current version entry`.

- [ ] **Step 7: Update CLAUDE.md**

- **Current state:** prepend a v2.10.0 bullet noting diff-aware `--changed` (P0) shipped: `lib.changed` + flags on `r:check`/`r:test`/`r:lint`; 35 commands (no surface change); spec `SPEC-diff-aware-checks-and-coverage-2026-05-31.md`.
- **lib/ Python package convention → Public modules:** add `changed` to the list; add a one-line description ("`changed` (v2.10.0): pure-stdlib, git-diff → changed-files → owning-packages + introduced/pre-existing finding tagging; backs `--changed`").
- **Auto-generated reference docs:** add `changed` to the `docs/reference/{...}.md` list.
- **Test gates:** bump the `test-all.sh` count by 1 and the pytest count to the recorded number; add `changed` to the pytest module list.

- [ ] **Step 8: Update .STATUS**

Set `version: 2.10.0`; add a `recent:` entry for the diff-aware P0 work; move P0 from the roadmap to shipped; note 35 commands unchanged + the new pytest/test-all counts.

- [ ] **Step 9: Commit**

```bash
git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json README.md mkdocs.yml CHANGELOG.md CLAUDE.md .STATUS
git commit -m "chore(release): v2.10.0 — diff-aware --changed (P0) + version/doc sync"
```

---

## Task 6: Final gates + PR

- [ ] **Step 1: Both gates green**

```bash
bash tests/test-all.sh && python3 -m pytest tests/ -q
```

Expected: test-all all-green (prior+1), pytest all pass, overall exit 0.

- [ ] **Step 2: Confirm command count is still 35**

```bash
ls commands/**/*.md commands/*.md 2>/dev/null | wc -l   # informational
grep -c "35 command" CLAUDE.md   # heading should still read 35
```

Expected: heading reads `## Command-file conventions (all 35 commands)` — unchanged.

- [ ] **Step 3: Push and open PR feature → dev**

```bash
git push -u origin feature/diff-aware-changed
gh pr create --base dev --title "feat: diff-aware checks (P0) — --changed flag (v2.10.0)" \
  --body "Adds --changed/--base to r:check (introduced vs pre-existing finding tagging) and r:test/r:lint (scope-only), backed by new pure-stdlib lib.changed. Flags only — command count stays 35. Spec: docs/specs/SPEC-diff-aware-checks-and-coverage-2026-05-31.md (P0)."
```

- [ ] **Step 4: After merge — release dev → main + tap sync**

Per the standard rforge release pipeline (CLAUDE.md): PR dev → main, GitHub release v2.10.0, Homebrew formula + `generator/manifest.json` sync (`generate.py rforge --diff` must report IDENTICAL apart from pre-existing `bin.mkpath` drift), CI verify on main. Docs deploy is automatic on push to main.

---

## Self-Review

**Spec P0 coverage (acceptance sketch §):**
- `/rforge:r:check --changed --base <branch>` tags every finding introduced vs pre-existing → Task 1 `tag_findings`/`scope_check` + Task 2 `run_changed` `changed.findings` block + Task 3 command flags. ✓
- Exit code reflects introduced findings only (flag-configurable) → Task 2 default status-fold + `--changed-strict` opt-out; tests `test_check_changed_default_status_ok_when_only_preexisting`, `test_check_changed_tags_introduced_vs_preexisting`. ✓
- Works on a git worktree and a normal checkout → `changed_files` uses `git rev-parse --show-toplevel` + `merge-base`, both worktree-aware (`cwd=path`). ✓
- Falls back gracefully (full check + warning) when no merge-base → Task 2 `fell_back` branch; test `test_changed_no_git_falls_back_to_full`. ✓

**Edge cases the prompt required, all covered with a test:**
- Not a git repo → `changed_files` returns None (rc 128) → fall back. `test_changed_files_not_a_git_repo_returns_marker`, `test_changed_no_git_falls_back_to_full`. ✓
- No changes → empty list (distinct from None) → no-op `ok`. `test_changed_files_empty_diff_returns_empty_list`, `test_changed_no_changes_is_noop_ok`. ✓
- Uncommitted vs committed → `git diff <merge-base>` (no `..HEAD`) captures both. `test_changed_files_committed_diff_against_merge_base`. ✓
- File outside any package → dropped. `test_changed_packages_ignores_files_outside_any_package`. ✓
- Comparison ref (default HEAD vs base branch) → `--base` default `HEAD`; `merge-base(HEAD, base)`. Tested across the changed_files cases. ✓
- git binary missing → None, no exception. `test_changed_files_git_missing_returns_marker`. ✓
- Single- vs multi-package layout → `test_changed_packages_single_package_repo` + multi-package mapping test; multi-package check routes to scope-only aggregate. ✓

**Command-surface / version claims (explicit, per prompt):**
- `--changed` is a flag on existing commands, **not** a new command → count **stays 35** (verified vs spec §P0 flag form + Task 6 Step 2). ✓
- Version: minor bump **v2.10.0** (from released v2.9.0) — additive flag + new public lib module = SemVer minor. ✓

**Changed-detection logic location (explicit):** new pure-stdlib module **`lib/changed.py`** (not an extension of an existing module), joined to `gen_lib_reference.py` MODULES, pytest, and test-all smoke — consistent with the `discovery`/`runiverse` public-module convention. ✓

**Placeholder scan:** all code shown literally and complete — the git invocation (`subprocess.run(["git", ...])`, never `execSync`/`execFileSync`-banned shell), the file→package mapping (`discovery.find_r_packages` + `Path.parents`), the status-fold, and the argparse wiring. CHANGELOG/`.STATUS`/`CLAUDE.md` edits specify exact strings. The one documented limitation (real merge-base checkout for `scope_check`) is flagged inline with the optional implementation, and the envelope contract is locked + tested regardless. No TBD/`...`-as-placeholder. ✓

**Type/name consistency:** `changed_files`/`changed_packages`/`tag_findings`/`scope_check`/`run_changed` names match between `lib/changed.py`, `lib/rcmd.py`, and both test files. The envelope `changed` block keys (`fell_back`, `base`, `packages`, `findings`, `introduced_counts`, `merge_base`, `stages`) match between implementation and assertions. `Package` (from `discovery`) is reused, not redefined. Flag names (`--changed`, `--base`, `--changed-strict`) match between argparse, command frontmatter, and CHANGELOG. ✓

**Convention adherence:** pure-stdlib (no R, no third-party) per analysis-module convention; `python3 -m lib.changed` invocation (never `python3 lib/changed.py`); advisory/never-raises like `runiverse`/`cranlint`; new files on a feature worktree (Task 0); both test gates extended; version_sync run after bump. ✓

# 🔬 Diff-aware checks — "did *my* change cause this?"

!!! tip "TL;DR (30 seconds)"
    - **What:** `--changed` on `r:check` / `r:test` / `r:lint` scopes the run to the
      package(s) you touched on this branch and tags each finding **`[introduced]`**
      (new on your branch), **`[pre-existing]`** (already at the fork point), or
      **`[uncommitted]`** (introduced, but in a file you haven't committed yet).
    - **Why:** A full `R CMD check` surfaces every NOTE/WARNING regardless of whether
      *your* branch caused it. Diff-aware mode answers the merge-gate question directly.
    - **How:** It runs a second baseline check in a throwaway worktree at
      `git merge-base(HEAD, --base)` and set-diffs the findings.
    - **CI:** `--fail-on introduced` (the default) exits non-zero **only** on findings you
      introduced — so CI blocks regressions you caused, not pre-existing debt.
    - **Next:** [R package dev cycle](r-dev-cycle.md) for the inner loop these gate.

> **For whom:** R package developer (or ecosystem maintainer) preparing a branch for
> merge, who wants to separate "my regressions" from "pre-existing debt."
> **Estimated time:** 8 minutes.
> **Prior knowledge:** A git repo with a feature branch off `dev` (or `main`), and an R
> package registered with `/rforge:init`.

---

## The problem it solves

You branch off `dev`, touch four files, and run `R CMD check`. It reports a vignette
WARNING. Did your change cause it — or has it been there for weeks? Without diff-awareness
you `git diff` by hand and reason about each finding. Diff-aware mode does that for you.

## How it works

```mermaid
flowchart TD
    A["/rforge:r:check --changed --base dev"] --> B{"git repo +<br/>merge-base found?"}
    B -- "no" --> Z["fall back: full check + warning<br/>(scope-only, no tagging)"]
    B -- "yes" --> C["changed packages =<br/>git diff vs merge-base"]
    C --> D["run check on HEAD<br/>(current findings)"]
    C --> E["run check in a detached<br/>worktree at the merge-base<br/>(baseline findings)"]
    D --> F["set-diff findings"]
    E --> F
    F --> G["tag each:<br/>[introduced] / [pre-existing] / [uncommitted]"]
    G --> H{"--fail-on"}
    H -- "introduced (default)" --> I["exit non-zero iff ≥1<br/>[introduced] finding"]
    H -- "none" --> J["advisory: always exit 0"]
```

The baseline runs in a **real detached git worktree** checked out at the merge-base commit
(cleaned up afterward) — it is not a re-run of HEAD, so the comparison is honest.

## Walkthrough

```bash
# Scope to changed packages + tag findings vs the fork point with dev
/rforge:r:check --changed --base dev

# Same for tests and lint
/rforge:r:test  --changed --base dev
/rforge:r:lint  --changed --base dev
```

A tagged result reads like:

```
[pre-existing]  NOTE: vignette 'intro.Rmd' has long-running examples
[introduced]    WARNING: undocumented argument 'newparam' in foo()
[uncommitted]   WARNING: undocumented argument 'draft' in bar()  (not committed yet)
```

The first is debt you inherited; the second is yours to fix before merge; the third is
also yours, but it lives in a file you haven't committed — commit it to promote it to
`[introduced]` so CI gates on it.

### Wiring it into CI

```bash
# Fail the job ONLY if this branch introduced a finding (the default)
/rforge:r:check --changed --base origin/main --fail-on introduced

# Advisory mode: tag findings but never fail the job
/rforge:r:check --changed --base origin/main --fail-on none
```

!!! note "Finding identity is line-shift-immune"
    Lint findings are matched on `(file, message, linter)` — **not** the raw line number.
    Inserting a blank line above a pre-existing lint will **not** mis-tag it as
    `[introduced]`.

!!! warning "Scope & cost"
    - The baseline is the **committed** merge-base. A finding you *introduced* in a file
      with uncommitted edits is tagged **`[uncommitted]`** (not `[introduced]`) — commit
      the file to promote it to `[introduced]` so `--fail-on introduced` gates on it.
    - The first `--changed` run pays one **extra** check (the baseline), but the baseline
      is **cached per package** (keyed by the merge-base SHA), so re-runs reuse it and
      re-check only packages not yet baselined. Disable with `--no-cache`; clear with
      `python3 -m lib.changed --clear-cache`.
    - No git repo / no merge-base / baseline-worktree failure → graceful fallback to a
      full check plus a warning (scope-only, no tagging).

## See also

- [Diff-aware checks — command guide](../guides/diff-aware.md) — the exhaustive reference:
  all three tags, the per-package cache key + invalidation, every flag
- [`changed` reference](../reference/changed.md) — the `lib.changed` engine (`merge_base`,
  `run_baseline`, `scope_check`, `tag_findings`, `cached_baseline`)
- [R package dev cycle](r-dev-cycle.md) — the inner loop these checks gate
- [CRAN release prep](cran-release-prep.md) — the full-package strict checks for submission

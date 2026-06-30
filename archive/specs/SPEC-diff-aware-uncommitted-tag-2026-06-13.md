# SPEC: diff-aware `[uncommitted]` tag

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved (bundle build)
**Parent:** `SPEC-diff-aware-tagging-2026-06-13.md` (Out of scope → now addressed)
**Target:** v2.12.0 bundle (2 of 3)

---

## Summary

v2.11.0 diff-aware `--changed` tags findings `[introduced]` (new on this branch vs the
merge-base) and `[pre-existing]`. It explicitly deferred *uncommitted-change* tagging:
"dirty working-tree findings count as HEAD's." This refines that — an `[introduced]`
finding whose file has **uncommitted changes** is re-tagged **`[uncommitted]`**, so a user
can tell "I caused this with edits I haven't committed yet" from "this is committed branch
work."

## Why the cheap (file-level) approach

A *finding-precise* version would need a **third** check run (a clean worktree at committed
HEAD) to set-diff working-tree findings from committed ones — tripling the check cost. The
value (telling committed-branch from uncommitted) does not justify a 3rd full `R CMD check`.

Instead: **file-level refinement, no extra run.** After tagging, an `[introduced]` finding
whose `file` is in the set of uncommitted-changed paths (`git status --porcelain` →
modified/added, staged or not) is re-tagged `[uncommitted]`. Zero extra check runs; reuses
the runs `--changed` already does.

## Design

In `lib/changed.py`:

- New `uncommitted_files(path) -> set[str]` — `git status --porcelain`, returning the
  modified/added/renamed paths (package-relative). Advisory: git failure → empty set
  (no refinement, no error).
- In `scope_check` (after `tag_findings`): for each finding tagged `[introduced]` whose
  finding-file ∈ `uncommitted_files`, change its tag to `[uncommitted]`. String findings
  (no file) are never refined (stay `[introduced]`).
- `[uncommitted]` is a **subset of introduced** for `--fail-on` purposes: `--fail-on
  introduced` (default) still fails on `[uncommitted]` findings (they're yours). A finding
  is never both.

## Scope decisions / caveats

- **File-level, not finding-level.** If a file has *both* a committed-branch finding and an
  uncommitted edit, all that file's introduced findings tag `[uncommitted]` (can't tell
  which without the 3rd run). Documented in the command help + this spec.
- **String findings** (whole-package `R CMD check` messages with no file) stay
  `[introduced]` — no file to attribute.
- No new flag; the refinement is automatic when `--changed` runs in a dirty tree. Pre-existing
  findings are never re-tagged.

## Tests (gates)

- Real-git e2e: branch with one **committed** introduced finding + one in an
  **uncommitted** file → assert the former tags `[introduced]`, the latter `[uncommitted]`,
  a pre-existing one stays `[pre-existing]`. No mocking of git.
- `uncommitted_files` unit: returns modified+staged+added paths; empty on non-repo (no raise).
- `--fail-on introduced` still exits non-zero when only `[uncommitted]` findings exist.
- Clean tree (no uncommitted changes) → no `[uncommitted]` tags (no regression of v2.11).
- Command frontmatter/`Usage` + `docs/commands.md` + `changed` reference updated; CHANGELOG.

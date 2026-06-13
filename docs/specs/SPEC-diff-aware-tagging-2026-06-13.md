# SPEC: Diff-aware `[introduced]` / `[pre-existing]` tagging (P0 completion)

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved
**Parent:** `SPEC-diff-aware-checks-and-coverage-2026-05-31.md` (P0 steps 2–4)
**Target:** v2.11.0 bundle (feature 1 of 3)

---

## Summary

The v2.10.0 `--changed` flag is **honest scope-only**: it runs the full check on the
changed packages and reports the real status, with a "tagging deferred" message. The
deferred half — tagging each finding `[introduced]` (your branch caused it) vs
`[pre-existing]` (already on base) — is what this spec completes.

The set-diff logic already exists (`lib.changed.tag_findings`, multiset semantics). The
**only** missing piece is producing the *baseline* finding list: a check run against
`git merge-base HEAD <base>`. That requires a checkout of the base commit, which the
DORMANT `lib.changed.scope_check` helper is already written to consume.

## Why it was deferred (the bug the pre-release review caught)

The first v2.10.0 draft tried two runs in one tree and tagged via a `_run_check_at(ref)`
that **ignored its `ref` argument** — so it compared HEAD against HEAD and silently
reported `ok` while real ERRORs existed. A mocked test hid it. Lesson: the baseline run
must execute in a *genuinely different working tree* at the merge-base commit, and the
test must use a real git repo (no mocking the diff).

## Design

### Mechanism — detached worktree at the merge-base

```
1. base_sha   = git merge-base HEAD <base>        (base defaults to "dev", --base override)
2. tmp        = git worktree add --detach <tmpdir> <base_sha>
3. baseline   = run the SAME check (--kind) in tmp        → base finding list
4. current    = run the check on the live tree (HEAD)     → HEAD finding list
5. tagged     = tag_findings(current, baseline)           → [introduced]/[pre-existing]
6. git worktree remove --force <tmp>                       (ALWAYS, in finally)
7. exit non-zero only on findings tagged [introduced]      (--fail-on, default "introduced")
```

### Where it lands

- **`lib/changed.py`** — new `merge_base(path, base) -> Optional[str]` and
  `run_baseline(path, base_sha, kind) -> Optional[list[Finding]]` (does the worktree
  add / run / **guaranteed** remove). Wake the DORMANT `scope_check()` to orchestrate
  steps 1–7. Still advisory: any git failure (no merge-base, detached-add fails, git
  missing) returns `None` → caller warns and falls back to the existing scope-only path.
- **`lib/rcmd.py` `run_changed`** — gains the real two-run tagging it currently stubs.
  Replace the "tagging deferred" message with tagged findings when `scope_check`
  succeeds; keep the scope-only fallback when it returns `None`.
- **Command frontmatter** — `commands/r/check.md` (and `test`/`lint`) `--changed`
  description updated from "scope-only" back to describing tagging; add `--base` and
  `--fail-on` to the `arguments:` array.

### Finding identity

`tag_findings` keys each finding via `changed._finding_identity` with multiset
(Counter) semantics so duplicate findings count correctly:

- **String findings** (R CMD check errors/warnings/notes) → keyed by the string itself.
- **Dict findings** (lint: `{file, line, linter, message}`) → keyed by
  `(file, message, linter)`, **EXCLUDING the raw `line`**. A pre-existing lint
  whose line shifted because an unrelated edit inserted/removed lines above it
  therefore stays `[pre-existing]` instead of mis-flipping to `[introduced]`. The
  full finding (with its real line) is preserved in `text` for display.

(The earlier draft of this spec claimed a `(file, normalized-line, message)`
key; no line-normalization step ever existed — excluding `line` for dict findings
is the actual, simpler implementation, regression-tested in
`tests/test_changed.py::test_tag_findings_lint_line_shift_stays_pre_existing` and
`::test_scope_check_line_shifted_lint_tagged_pre_existing`.)

### Safety / cleanup

- Worktree removal is in a `finally` — a crash mid-run never leaks a worktree.
- The temp dir is created under the system temp root, not inside the repo (avoids the
  PreToolUse "writes outside active worktree" warning and keeps `git status` clean).
- Read-only with respect to the user's tree: the baseline runs in an isolated detached
  worktree; the live tree is never checked out or mutated.

## Out of scope (deferred again)

- **Uncommitted changes in the baseline** — baseline is the committed merge-base only.
  Tagging reflects committed HEAD vs base; dirty working-tree findings count as HEAD's.
- **Caching baseline runs** across invocations (the parent spec's "reuse a cached run").
  Each `--changed --fail-on` invocation pays one extra check. Note this in the command help.

## Tests (gates)

- **Real-git e2e** (extends the existing honest one): build a temp repo, commit a clean
  base, branch, introduce a *real* lint/check finding, assert it tags `[introduced]` and
  that a pre-existing finding tags `[pre-existing]`. **No mocking of git or the diff.**
- Worktree cleanup assertion: after the run, `git worktree list` shows no leftover temp
  worktree (even on a forced check failure).
- `--fail-on introduced` exit-code test: non-zero iff ≥1 introduced finding.
- Fallback test: when `merge_base` returns `None`, the command still runs scope-only and
  exits 0 with the warning (no regression of the v2.10.0 behavior).

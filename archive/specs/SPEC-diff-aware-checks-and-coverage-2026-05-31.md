# SPEC / Feature Request: Diff-Aware Checks, Coverage, and Ecosystem NOTE Classification

**Date:** 2026-05-31
**Author:** Davood Tofighi (with Claude Code)
**Status:** Draft — **refocused to P0** (2026-06-10); P1–P5 migrated (see below)
**Origin:** Friction encountered using rforge (`/rforge:r:check`, `/rforge:docs:check`) across a
3-package ecosystem change (RMediation + medfit covariance work) under the workflow
"address all issues and errors before merging."

---

## Status & refocus (2026-06-10)

This started as a 6-item wishlist; events have since absorbed most of it. **The live scope of
this spec is now P0 only** — `--changed` diff-aware checks, the one high-value item still
unbuilt. The rest are migrated:

| Item | Disposition |
|---|---|
| **P0** `--changed` diff-aware check | **LIVE — the focus of this spec.** Still unbuilt. Candidate target: post-v2.6.0 (unscheduled). |
| P1 `r:coverage` (package_coverage) | ✅ base **shipped v2.1.0**; the `--changed` slice folds into P0's diff-aware mode. |
| P2 auto-handle missing `Suggests` (`_R_CHECK_FORCE_SUGGESTS_`) | → **`SPEC-cran-incoming-hardening`** (v2.3.0), which owns the `_R_CHECK_*` flavor surface. |
| P3 ecosystem-aware NOTE classification | partly done by the v2.2.0 NOTE classifier; the ecosystem-metadata half → **`SPEC-ecosystem-manifest-discovery`** (v2.4.0). |
| P4 `r:test-gen` scaffold | → the deferred **scaffolding theme** (`r:use-test`), its own future spec. |
| P5 worktree-collision guard | minor; keep as a parked note under P0. |

Everything below P0 is retained for historical context only; act on **P0**.

---

## Summary

rforge's check/test/docs commands answer *"is this package healthy right now?"* well. But real PR
work keeps asking a different question: *"did **my change** introduce this, and is it actionable?"*
— and that is currently a manual, error-prone chore. This proposes five enhancements, ranked by the
time they would have saved this session.

---

## P0 — `--changed` / diff-aware mode for `/rforge:r:check`

**Problem.** `R CMD check` runs on the whole package, so every NOTE/WARNING surfaces regardless of
whether the branch caused it. I repeatedly ran `git diff <base>..HEAD --name-only` and reasoned by
hand about whether each finding was *mine* or *pre-existing*. Example: a medfit vignette WARNING
looked like a blocker until I confirmed it pre-existed on `dev` (the branch touched 4 unrelated
files).

**Request.**

```
/rforge:r:check --changed [--base dev]
```

1. Run the check (or reuse a cached run).
2. Diff findings against a check of `git merge-base HEAD <base>`.
3. Tag each NOTE/WARNING/ERROR **`[introduced]`** vs **`[pre-existing]`**.
4. Exit non-zero only on *introduced* findings (configurable).

**Impact.** Highest-value item — directly answers the merge-gate question.

---

## P1 — `/rforge:r:coverage` using `package_coverage()` correctly

**Problem.** `covr::file_coverage("R/x.R", "tests/.../test-x.R")` **fails**: it sources the test file
in isolation without testthat's harness, so `skip_if_not_installed()`, `test_that()`, etc. throw
"could not find function" and the result reads as 0%/uncovered — a misleading false signal.

**Request.** A coverage command that:
1. Uses `covr::package_coverage()` (loads package + full test infra), not `file_coverage()`.
2. Supports `--changed` to report coverage only for functions/lines modified on the branch
   (git-diff-scoped), per-function.
3. Surfaces the `file_coverage` helper-loading pitfall if a user asks for single-file coverage.

```
/rforge:r:coverage --changed --base dev
# R/ci_medfit.R: ci_mediation_data 100%, ci_serial_mediation_data 96%, .resolve_path_indices 100%
```

---

## P2 — Auto-handle missing `Suggests` packages

**Problem.** An uninstalled `Suggests` dep (e.g. `OpenMx`) makes `R CMD check` emit a hard **ERROR**
(`Package suggested but not available`), masking true health. I set `_R_CHECK_FORCE_SUGGESTS_=false`
on every invocation by hand.

**Request.** `/rforge:r:check` should detect uninstalled `Suggests`, then either auto-set
`_R_CHECK_FORCE_SUGGESTS_=false` (noting it in output) or offer to install — and report which
suggest-gated checks were skipped, so reduced coverage is explicit rather than read as breakage.

---

## P3 — Ecosystem-aware NOTE classification

**Problem.** RMediation's only remaining NOTE was `Unknown field 'Remotes'` + `Suggests not in
mainstream repositories: medfit`. Correct and expected for an ecosystem package depending on a
sibling not yet on CRAN — but a naive reading treats it as actionable, risking a "fix" that deletes
`Remotes:` and breaks pre-CRAN install.

**Request.** rforge already models the ecosystem (`/rforge:deps`, `/rforge:status`). Classify such
NOTEs from that manifest:

```
NOTE: Remotes / medfit not in mainstream repositories
  -> [ecosystem-expected] medfit is a GitHub-only sibling pending CRAN.
     Clears automatically when medfit is published. Do NOT remove Remotes:.
```

---

## P4 — Test-authoring scaffold (`/rforge:r:test-gen`)

**Problem.** rforge runs/validates tests but cannot *author* them. After changing a function I
hand-wrote fixtures (S7 constructors with every required slot) and risked gaps. (`craft:test:gen`
exists but is not R/testthat/S7-aware.)

**Request.** Given a changed exported function, scaffold a `tests/testthat/test-<fn>.R` that:
1. Reads signature + roxygen `@examples` + the S7/S4 classes of its arguments.
2. Emits a fixture builder (from the class definition's required properties) and stub `test_that()`
   blocks for: happy path, each documented `stop()`, and `@param`-constraint edge cases.
3. Leaves assertions as `# TODO` — does **not** guess expected values.

> Explicitly a *scaffold*, not an oracle. A real bug this session — a test asserting the naive
> product `a*b` for a delta-method estimate that is actually bias-corrected to `a*b + cov(a,b)` —
> shows generated **assertions** must not be trusted; the human/agent supplies expected values.

---

## P5 (minor) — Worktree-collision guard

**Problem.** Running `/rforge:r:check` on a worktree while a background agent edits files there can
race. **Request:** detect a concurrent writer and warn, or offer a read-only snapshot check.

---

## Prioritization

| # | Feature | Effort | Value |
|---|---------|--------|-------|
| P0 | `--changed` diff-aware check | Medium | ⭐⭐⭐⭐⭐ |
| P1 | `/rforge:r:coverage` (package_coverage, diff-scoped) | Medium | ⭐⭐⭐⭐ |
| P2 | Auto-handle missing Suggests | Low | ⭐⭐⭐⭐ |
| P3 | Ecosystem-aware NOTE classification | Low–Med | ⭐⭐⭐ |
| P4 | Test-authoring scaffold | High | ⭐⭐⭐ |
| P5 | Worktree-collision guard | Low | ⭐⭐ |

**Recommended first cut:** P0 + P2 — cheapest high-value pair, directly serving the
"address all issues before merging" workflow.

---

## Acceptance sketch (P0)

- [ ] `/rforge:r:check --changed --base <branch>` tags every finding introduced vs pre-existing.
- [ ] Exit code reflects introduced findings only (flag-configurable).
- [ ] Works on a git worktree and a normal checkout.
- [ ] Falls back gracefully (full check + warning) when no merge-base resolves.

---
name: rforge:r:check
description: Run R CMD check with smart parsing — NOTEs classified as spurious or real
argument-hint: "[package] [--as-cran] [--strict] [--incoming] [--changed] [--base <ref>] [--fail-on introduced|none] [--no-cache]"
arguments:
  - name: package
    description: Package path to check (defaults to current directory)
    required: false
    type: string
  - name: as-cran
    description: Run with --as-cran flag (stricter CRAN-compliance checks)
    required: false
    type: boolean
    default: false
  - name: strict
    description: Run both Suggests-withholding flavor passes (noSuggests + suggests-only), each with --run-donttest, as two distinct stage rows
    required: false
    type: boolean
    default: false
  - name: incoming
    description: "Implies --strict; adds a third check (incoming) pass using the CRAN-incoming _R_CHECK_* env switches. Runs two sequential rcmdcheck passes (_R_CHECK_DEPENDS_ONLY_ + _R_CHECK_SUGGESTS_ONLY_) — expect ≈3× check time."
    required: false
    type: boolean
    default: false
  - name: changed
    description: Run the check on the package(s) changed on this branch (vs --base) and tag each finding [introduced] (new on your branch) vs [pre-existing] (already on base) via a two-run merge-base baseline.
    required: false
    type: boolean
    default: false
  - name: base
    description: Comparison ref for --changed; the diff + baseline run are taken against merge-base(HEAD, base). Default dev.
    required: false
    type: string
    default: dev
  - name: fail-on
    description: "--changed exit policy: introduced (default) exits non-zero iff >=1 introduced finding; none reports findings but never folds the status (advisory)."
    required: false
    type: string
    default: introduced
  - name: no-cache
    description: "--changed: bypass the baseline cache — force a fresh merge-base baseline run and skip writing it. Use after upgrading an R engine (e.g. lintr) that could change the immutable-tree baseline."
    required: false
    type: boolean
    default: false
---

# R Package Check

Run `R CMD check` (via `rcmdcheck`) and report structured results.

## Process

1. Resolve package path from `$ARGUMENTS` (default: current dir).
2. `python3 -m lib.rcmd --kind check --path "<path>"` (add `--as-cran`, `--strict`,
   and/or `--incoming` if requested).
3. Render the JSON envelope below. Do not re-run R yourself.
4. If `--changed` is set: run `python3 -m lib.rcmd --kind check --changed
   --base "<ref>" [--fail-on introduced|none] [--no-cache] --path "<path>"`. The envelope gains
   a `changed` block with `packages` (the changed package(s)), `merge_base` (the
   fork-point SHA), `introduced_count`, and `findings` — each finding tagged
   `introduced` (new on this branch), `uncommitted` (an introduced finding whose
   file still has uncommitted changes), or `pre-existing` (already on `base`). The
   tagging is honest: a baseline run executes the SAME check in a detached worktree
   checked out at `merge-base(HEAD, base)`. `uncommitted` counts as introduced for
   `--fail-on`. With `--fail-on introduced` (default)
   the status is `error` iff ≥1 introduced finding (incl. `uncommitted`). Render the
   tagged findings, grouping by tag. If the `changed` block instead has `fell_back`/scope-only
   wording (no merge-base / baseline worktree unavailable), render the full check
   result as usual.

## Usage

```bash
/rforge:r:check                    # single --as-cran pass (default; unchanged)
/rforge:r:check --as-cran          # explicit --as-cran pass
/rforge:r:check --strict           # two extra flavor passes (see below)
/rforge:r:check --incoming         # --strict + a third CRAN-incoming pass
/rforge:r:check --changed                # tag findings vs merge-base(HEAD, dev)
/rforge:r:check --changed --base main    # compare against main instead of dev
/rforge:r:check --changed --fail-on none # tag findings but never fail (advisory)
/rforge:r:check --changed --no-cache     # force a fresh baseline (skip the cache)
```

- **`--changed`** — runs the check on the R package(s) touched on this branch
  (diff vs `merge-base(HEAD, --base)`; `--base` defaults to `dev`) and tags each
  finding **`[introduced]`** (new on your branch) vs **`[pre-existing]`** (already
  present at the fork point). The tag is computed honestly: a second baseline run
  executes the same check in a detached worktree checked out at the merge-base SHA,
  and the two finding lists are set-diffed. An `[introduced]` finding whose file
  still has **uncommitted** changes is further refined to **`[uncommitted]`** (you
  caused it with edits you haven't committed yet) — a file-level refinement with no
  third check run, so all introduced findings in a dirty file tag `[uncommitted]`;
  string findings (R CMD check messages with no file) stay `[introduced]`.
  **`--fail-on introduced`** (default)
  exits non-zero iff ≥1 introduced finding (`[uncommitted]` counts as introduced),
  so CI fails only on regressions you
  caused — not pre-existing debt; **`--fail-on none`** is advisory. Degrades
  gracefully: not a git repo / no merge-base / baseline worktree unavailable →
  scope-only (real status on the changed package(s), no tagging) + a warning; no
  changes → a clean no-op.

!!! note "Cost — `--changed` runs the check twice (baseline is cached)"
    Tagging pays one extra check run (the merge-base baseline). That baseline is
    **cached per package** under `~/.rforge/baseline-cache/`, keyed by
    `(repo, merge-base SHA, kind, package, engine flags)`, so a repeat `--changed`
    run with an unchanged merge-base reuses each already-baselined package and
    re-runs only the uncached ones — when the whole changed set is cached, the
    second pass is skipped entirely. The cache is **self-invalidating**: new
    commits on `--base` move the merge-base SHA → new key → automatic miss. Pass
    **`--no-cache`** to force a fresh baseline (and skip writing one) — useful after
    upgrading an R engine that
    could change the immutable-tree baseline. Clear it with
    `python3 -m lib.changed --clear-cache`. For a quick scoped run without any
    baseline pass, omit `--changed` and pass the package path directly.

- **Plain `r:check` (no flag)** — unchanged: one `--as-cran` pass, one `check` stage row.
- **`--strict`** — runs **both** Suggests-withholding flavor passes as two distinct
  stage rows, each with `--run-donttest` (so `\donttest{}` examples actually run):
  - `check (noSuggests)` — `_R_CHECK_DEPENDS_ONLY_=true`: withholds every `Suggests`
    package, so a `Suggests` dependency used unconditionally **fails here** (the class CRAN's
    post-acceptance flavor catches but plain `--as-cran` misses).
  - `check (suggests-only)` — `_R_CHECK_SUGGESTS_ONLY_=true`: catches undeclared-package use.
- **`--incoming`** — **implies `--strict`** and adds a third `check (incoming)` row using the
  CRAN-incoming env switches (`_R_CHECK_CRAN_INCOMING_`, `_R_CHECK_CRAN_INCOMING_REMOTE_`).
  `--as-cran` already enables the incoming block, so this bundle is intentionally small.

These are the same strict passes `/rforge:r:cran-prep` runs **by default** — one mental
model across both commands. Mechanism: `rcmdcheck`'s `env=` named vector; no `devtools`,
no subprocess-layer change.

!!! warning "Behavior change — a package green under `--as-cran` can turn red under `--strict`"
    A package that passes plain `r:check`/`--as-cran` can fail the `check (noSuggests)` pass
    once it detects a `Suggests` package used unconditionally. This is intended.

    **Fix:** A `Suggests` package is used unconditionally. Move it to `Imports`, or guard with
    `requireNamespace()` in code **and** `skip_if_not_installed()` in tests.

!!! note "Cost"
    `--strict` runs ≈ 2× the work of a plain check (two extra passes). `--incoming` implies
    `--strict` and adds a third CRAN-incoming pass — expect **≈3× check time** vs. a plain
    `r:check`. Acceptable for a pre-submission gate; run it once, not in CI.

## Output Format

```markdown
## Package Check: {package} v{version}
### Status: {🟢 ok / 🟡 warn / 🔴 error}
### R CMD Check
- Errors: {len check.errors}
- Warnings: {len check.warnings}
- Notes: {len check.notes}
{list each message as a bullet, if any}
{If check.notes_classified is non-empty:}
### NOTE classification
{For each check.notes_classified: "🟢 expected — {text}" (kind=spurious) or
 "🔴 needs attention — {text}" (kind=real)}
### Recommended Actions
{1-3 steps, or "None — package is clean ✅"}
```

If `engine_missing` is non-empty, report 🔴 with the install hint from `messages`.

## Related Commands
- `/rforge:r:cycle` — document → test → check in one pass
- `/rforge:thorough` — **ecosystem** rollup incl. R CMD check (this is **single-package**)
- `/rforge:docs:check` — documentation drift (complements R CMD check)

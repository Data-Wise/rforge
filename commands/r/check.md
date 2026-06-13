---
name: rforge:r:check
description: Run R CMD check with smart parsing — NOTEs classified as spurious or real
argument-hint: "[package] [--as-cran] [--strict] [--incoming] [--changed] [--base <ref>] [--fail-on introduced|none]"
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
    description: Implies --strict; adds a third check (incoming) pass using the CRAN-incoming _R_CHECK_* env switches
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
---

# R Package Check

Run `R CMD check` (via `rcmdcheck`) and report structured results.

## Process

1. Resolve package path from `$ARGUMENTS` (default: current dir).
2. `python3 -m lib.rcmd --kind check --path "<path>"` (add `--as-cran`, `--strict`,
   and/or `--incoming` if requested).
3. Render the JSON envelope below. Do not re-run R yourself.
4. If `--changed` is set: run `python3 -m lib.rcmd --kind check --changed
   --base "<ref>" [--fail-on introduced|none] --path "<path>"`. The envelope gains
   a `changed` block with `packages` (the changed package(s)), `merge_base` (the
   fork-point SHA), `introduced_count`, and `findings` — each finding tagged
   `introduced` (new on this branch) or `pre-existing` (already on `base`). The
   tagging is honest: a baseline run executes the SAME check in a detached worktree
   checked out at `merge-base(HEAD, base)`. With `--fail-on introduced` (default)
   the status is `error` iff ≥1 introduced finding. Render the tagged findings,
   grouping by tag. If the `changed` block instead has `fell_back`/scope-only
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
```

- **`--changed`** — runs the check on the R package(s) touched on this branch
  (diff vs `merge-base(HEAD, --base)`; `--base` defaults to `dev`) and tags each
  finding **`[introduced]`** (new on your branch) vs **`[pre-existing]`** (already
  present at the fork point). The tag is computed honestly: a second baseline run
  executes the same check in a detached worktree checked out at the merge-base SHA,
  and the two finding lists are set-diffed. **`--fail-on introduced`** (default)
  exits non-zero iff ≥1 introduced finding, so CI fails only on regressions you
  caused — not pre-existing debt; **`--fail-on none`** is advisory. Degrades
  gracefully: not a git repo / no merge-base / baseline worktree unavailable →
  scope-only (real status on the changed package(s), no tagging) + a warning; no
  changes → a clean no-op.

!!! note "Cost — `--changed` runs the check twice"
    Tagging pays one extra check run (the merge-base baseline). Baseline results are
    not cached across invocations. For a quick scoped run without the second pass,
    omit `--changed` and pass the package path directly.

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
    `--strict` runs ≈ 2× the work of a plain check (two extra passes); `--incoming` adds a
    third. Acceptable for a pre-submission gate.

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

---
name: rforge:r:check
description: Run R CMD check with smart parsing — NOTEs classified as spurious or real
argument-hint: "[package] [--as-cran] [--strict] [--incoming]"
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
---

# R Package Check

Run `R CMD check` (via `rcmdcheck`) and report structured results.

## Process

1. Resolve package path from `$ARGUMENTS` (default: current dir).
2. `python3 -m lib.rcmd --kind check --path "<path>"` (add `--as-cran`, `--strict`,
   and/or `--incoming` if requested).
3. Render the JSON envelope below. Do not re-run R yourself.

## Usage

```bash
/rforge:r:check                    # single --as-cran pass (default; unchanged)
/rforge:r:check --as-cran          # explicit --as-cran pass
/rforge:r:check --strict           # two extra flavor passes (see below)
/rforge:r:check --incoming         # --strict + a third CRAN-incoming pass
```

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

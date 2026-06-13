---
name: rforge:r:use-test
description: Scaffold a testthat file and draft test_that() blocks for a function (assertions left as TODO)
argument-hint: "<function> [--write] [--force]"
arguments:
  - name: function
    description: The exported function to scaffold tests for (one per call)
    required: true
    type: string
  - name: write
    description: Apply the plan (create the file). Default is dry-run (prints the plan, writes nothing).
    required: false
    type: boolean
    default: false
  - name: force
    description: Overwrite an existing test file (diff shown first)
    required: false
    type: boolean
    default: false
---

# R Use Test

Scaffold `tests/testthat/test-<function>.R` for an **existing** function and draft a
`test_that()` block per branch — happy path, one per `stop()`, one per constrained `@param`.

**Dry-run by default.** `--write` creates the file; `--force` is required to overwrite.
**No oracle:** assertions are emitted as `# TODO` — the engine never invents expected values
(a delta-method estimate may be `a*b + cov(a,b)`, not `a*b`).

## Usage

```bash
# Dry-run: print the planned file, write nothing (default)
python3 -m lib.scaffold test --fn "<function>" --path "<path>" 

# Apply: create the file (sets up testthat 3e infra if absent)
python3 -m lib.scaffold test --fn "<function>" --path "<path>" --write

# Overwrite an existing file
python3 -m lib.scaffold test --fn "<function>" --path "<path>" --write --force
```

On `--write`, if `tests/testthat/` infra is missing, run the guarded usethis setup first:

```bash
python3 -m lib.usethis_infra testthat --path "<path>"
```

(If `usethis` is absent, a manual `usethis::use_testthat(3)` recipe is printed — non-fatal.)

## What you do after the plan

The drafted blocks are *structure*. Read `R/<function>.R`, then **fill each `# TODO`** with a
real expected value. Do not trust generated assertions — verify against the documented behavior.

## Related Commands

- `/rforge:r:test` — run the tests you just wrote
- `/rforge:r:coverage` — confirm the new file lifts coverage
- `/rforge:r:document` — regenerate docs if you edited roxygen while writing tests

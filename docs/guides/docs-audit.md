# Docs audit (`/rforge:docs:check`)

!!! tip "TL;DR (30 seconds)"
    - **What:** checks that the calls and signatures in your `README` and `vignettes/` still match what the package exports. Static, read-only, no R.
    - **Run:** `/rforge:docs:check` in a package (or `--eco` for every package under the ecosystem root).
    - **Read:** `error` = a call that would fail as written; `warn` = a candidate to check by hand; the `checked N of M` line says how much it could see.

## What it checks

| Check | Severity | Fires when |
|---|---|---|
| `signature-named-arg` | error | A documented call names an argument that is not a formal of the exported function. R's partial matching is applied, so `f(conf = .9)` is fine for `conf.level`. |
| `signature-names` | warn | A signature listing (a backticked call that is the whole first cell of a table row, as in a reference card) names a non-formal. |
| `signature-arity` | warn | A call passes more positional arguments than the function has formals. |
| `scannability` | info | A paragraph over 110 words, an H2 section over 800 words with fewer than 3 H3, or a "Next Steps" heading that is not last. Shown with `--detailed`. |
| `coverage` | warn | With `--since <tag>` only: an export added since the tag that no README or vignette mentions. |

Functions with a `...` formal are exempt from the three signature checks, because any name or count is valid there.
Code in an unlabeled fence downgrades `error` to `warn` (it may be console output).

## Reading a report

```text
scope: package medfit at /path/to/medfit
error signature-named-arg  vignettes/intro.qmd:154  `BootstrapResult()` has no argument `converged` (formals: ...)
checked 18 of 22 exported functions (3 no-usage, 1 variadic not checked)
```

1. **The first line is the scope.** "Audited `medfit`" is not "audited the ecosystem".
2. **Read `checked N of M`.** An export with no `\usage` in its Rd, a method behind a generic, or a re-export cannot be checked; a clean report on `checked 1 of 22` proves little.
3. **`INCOMPLETE` or `NOT AUDITED` at the end means the result is not clean**, whatever `status` says: a file was unreadable, a region was too large to scan, or no package was found.
4. **Findings are candidates.** A flagged call may be intentional pseudo-code; check the call before changing the docs.

## Scope

Without an argument it audits the package you are in (walking up to the nearest `DESCRIPTION`). Outside a package it
sweeps the ecosystem only if a `.rforge.yaml` manifest exists or you pass `--eco`; otherwise it says so and exits 0.
A `kind: hybrid` root audits the root package and its nested packages.

## Suppressing a finding

```yaml
# .rforge.yaml (package root)
docs:
  allowlist:
    - vignettes/articles/methods.qmd::scannability   # one check in one file
    - NEWS-draft.md                                    # everything in a file
```

A malformed block is ignored with a message; the suppressed count appears in the summary.

## In a release gate

`--fail-on error` (or `warn`) sets the exit code only; the report is the same. The default is `none` (always exits 0).

## What it does not check

NEWS completeness (see the `description-sync` skill), whether examples run (`/rforge:r:check`), live-site pages,
prose claims, wrong default values, reordered arguments, and S3/S4/S7 method signatures behind a generic.

!!! warning "Symptom"
    `status: ok` but the docs are clearly wrong.

!!! tip "Fix"
    Check `checked N of M` and whether the report ends with `INCOMPLETE`. The call may be to an unchecked export (no
    `\usage`, a method, or a function with `...`).

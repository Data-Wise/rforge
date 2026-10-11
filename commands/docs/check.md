---
name: rforge:docs:check
description: Audit documentation content against the package API — calls and signatures in README/vignettes that no longer match the exports
argument-hint: "[package] [--detailed] [--eco] [--since <tag>] [--fail-on none|warn|error]"
arguments:
  - name: package
    description: Package path or name. Omitted, the package you are in (walks up to the nearest DESCRIPTION); outside a package it audits the ecosystem only when a .rforge.yaml manifest exists or --eco is passed.
    required: false
    type: string
  - name: detailed
    description: Also print info findings (scannability) in the report.
    required: false
    type: boolean
    default: false
  - name: eco
    description: Force the ecosystem sweep (every package found under the ecosystem root).
    required: false
    type: boolean
    default: false
  - name: since
    description: Tag or ref. Adds the coverage report, limited to exports added since it (exports no README/vignette mentions).
    required: false
    type: string
  - name: fail-on
    description: "Exit-code threshold: none (default, always 0), warn or error. Does not change the report."
    required: false
    type: string
    default: none
---

# /rforge:docs:check - Documentation Content Audit

Checks what the docs *say* against what the package *exports*. Static and read-only: no R, no network, no
writes. It reads `man/*.Rd` usage, `NAMESPACE`, and the R code and inline calls in `README` and `vignettes/`.

## Process

```bash
python3 -m lib.docaudit --path "<package-or-dir>" --format json
```

Map the flags straight through: `--detailed` → `--detailed`, `--eco` → `--eco`, `--since <tag>` → `--since <tag>`,
`--fail-on <level>` → `--fail-on <level>`. Omit `--path` to use the current directory. Read the JSON; render the
text form with `python3 -m lib.docaudit ...` (no `--format`) when the user wants the plain report.

The first line of the text report is the **resolved scope** (which package, or which ecosystem, was audited).
State it before any finding: "audited `medfit`" is not "audited the ecosystem".

## Checks

| Check | Severity | Flags |
|---|---|---|
| `signature-named-arg` | error | A named argument in a documented call that is not a formal of the exported function (`f(arg = ...)`). R's partial matching is applied. |
| `signature-names` | warn | A signature listing (backticked call that is the whole first cell of a table row) names an argument that is not a formal. |
| `signature-arity` | warn | A call passes more positional arguments than the function has formals. |
| `scannability` | info (`--detailed`) | Paragraph over 110 words; H2 section over 800 words with fewer than 3 H3; "Next Steps" not last. |
| `coverage` | warn (`--since` only) | An export added since the tag that no README or vignette mentions. |

Functions with a `...` formal are exempt from the three signature checks. Unlabeled code fences downgrade
`error` to `warn` (they may be console output). The summary line states `checked N of M exported functions`
with the unchecked ones named by reason (no usage, method, re-export, variadic) — read it: a clean report on
`checked 1 of 22` proves little.

## Reading the result

- `status`: `ok`, or `warn` when any `warn`/`error` finding exists. `max_severity` shows an `error` inside a `warn`
  envelope. Info findings never change `status`.
- `incomplete: true` means a file was unreadable or a region too large to scan (named in `messages`): **do not report
  "no findings" as clean**.
- `audited: false` means nothing was audited (no package found): report the message, not "clean".
- Findings are candidates, not verdicts: a flagged call may be intentional pseudo-code. Check the call before
  telling the user to change the docs.

## Suppressing a finding

Add `docs.allowlist` to the package's `.rforge.yaml` (entries `<relpath>` or `<relpath>::<check-id>`):

```yaml
docs:
  allowlist:
    - vignettes/articles/methods.qmd::scannability
```

## Usage

```bash
# Audit the package you are in
/rforge:docs:check

# A specific package, including info findings
/rforge:docs:check medfit --detailed

# Every package under the ecosystem root
/rforge:docs:check --eco

# Which exports added since v2.0.0 are not mentioned in any doc
/rforge:docs:check --since v2.0.0

# Use in a release gate: exit 1 on any error
/rforge:docs:check --fail-on error
```

## What it does not check

NEWS completeness, whether examples run, live-site pages, prose claims, wrong default values, reordered
arguments, and S3/S4/S7 method signatures behind a generic. Those need other commands or a read of the docs.

## Related Commands

- `/rforge:r:check` - R CMD check (runs examples)
- `/rforge:r:site --check-leaks` - pkgdown render-surface leak scan
- `/rforge:status` - Overall health

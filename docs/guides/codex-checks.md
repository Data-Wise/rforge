# 🤖 Rforge checks in Codex

⏱️ **6 minutes** • 🟡 Intermediate • ✓ 4 steps

!!! tip "TL;DR (30 seconds)"
    - **What:** Three source skills (`$rforge-check`, `$rforge-docs-check`, `$rforge-lint`) that run Rforge's static engines from Codex.
    - **Why:** Get the same package, docs and lint evidence in Codex without importing the full Claude command catalog.
    - **How:** Register the checkout's `openai` directory, install `rforge-openai`, restart, then run `$rforge-docs-check Audit /absolute/path/to/package`.
    - **Next:** Read [Check evidence and approval decisions](evidence-and-approval.md) to keep check outcomes separate from owner authorization.

!!! tip "Personal pilot"
    Three focused source skills reuse the local Rforge checkout. The full Claude
    command catalog and its hooks are not imported.

## The three skills

| Skill | Runs | Reports |
| --- | --- | --- |
| `$rforge-check` | `lib.rcmd` with `--as-cran` by default | Errors, warnings and NOTEs |
| `$rforge-docs-check` | Static `lib.docaudit` | Resolved scope, export coverage, incomplete scans |
| `$rforge-lint` | Separate R process, no preloaded development code | Lint findings and CI parity |

## Package checks

Ask `$rforge-check` to check an absolute package path. It runs `lib.rcmd` from
Rforge's checkout with `--as-cran` by default and explains errors, warnings,
and NOTEs.

!!! warning "Before you run it"
    R and the check engine's dependencies must already be available. Checks can
    execute package code and produce build/check files; they do not authorize
    submissions.

### Strict checks

- Requested strict checks run the two existing flavor passes (`depends`, `suggests`).
- Incoming adds the engine's incoming bundle. Each result is reported separately.
- Raw CLI `--strict` alone is only one pass with donttest examples.
- The pilot does not support advanced `--changed` baseline tagging.

### What counts as a completed check

- Structured JSON with `incomplete: false`.
- Zero for every inner R check exit status in `check.exit_status`.
- Real `00check.log` files, reported in `check.log_paths`. The engine retains them.
- Empty log paths mean log evidence is unavailable, never an invented path.

## Documentation checks

Ask `$rforge-docs-check` to audit an absolute package path. It runs the static
`lib.docaudit` engine, reports the resolved scope and export coverage, and
explains incomplete scans.

- It uses `--package-only` to prevent implicit hybrid or ecosystem expansion.
  An explicit ecosystem request uses `--eco` instead.
- New-export coverage requires `--since REF`. Without a chosen comparison ref,
  that component is omitted and must be reported separately from signature coverage.
- It does not execute examples or build a site.

## Package lint and CI parity

Ask `$rforge-lint` to lint an absolute package path. It uses a separate R process
without preloading development code or attaching testthat.

1. Inspect the lint CI workflow and startup files.
2. Match its linters, R/lintr versions and library.
3. If CI installs the current package, require an install receipt tied to the
   source ref. Matching version strings alone cannot establish the installed source.

Outcomes to report:

- Missing prerequisites mean unavailable.
- Unknown provenance means local findings with CI parity unverified.
- Installation requires separate authorization.

Helpers outside `test_that()` should qualify assertions such as
`testthat::expect_true(...)`. A loaded development session can hide this missing
name, while an old installed namespace can create unrelated diagnostics.
Read the lint findings and missing-engine/messages fields, not only exit zero.
See [quality commands](quality.md#match-the-ci-environment) for the shared guidance.
The new skill's installation and fresh-session invocation remain separate gates.

## Setup and first use

1. Use a reviewed checkout containing the desired adapter. Review all skill instructions.
2. In Codex's local marketplace controls, register the checkout's `openai`
   directory (the catalog file is `openai/.agents/plugins/marketplace.json`).
3. Install and enable `rforge-openai`, then start a fresh Codex session.
4. Confirm `$rforge-check`, `$rforge-docs-check` and `$rforge-lint` are discoverable. Run the
   static audit first, then explicitly request the package check.

### Where things live

- The source package is `openai/rforge-openai`; the personal catalog is
  `openai/.agents/plugins/marketplace.json`.
- The default engine checkout is `/Users/davood/projects/dev-tools/rforge`;
  point the workflow to another Rforge checkout if needed. Use Python 3.10+.
- The personal local catalog source is `/Users/davood/projects/dev-tools/rforge/openai`.

### Versions

Version 0.1.1 requires the repaired engines: check envelopes with
`output_format`, `incomplete`, `check.exit_status`, and `check.log_paths`,
plus docaudit's `--package-only`. These engines and the adapter are integrated
on `dev` through [PR #92](https://github.com/Data-Wise/rforge/pull/92). Use the
durable checkout containing that integration, rather than a retired verification
worktree. See the
[adapter source on dev](https://github.com/Data-Wise/rforge/tree/dev/openai/rforge-openai).

- Report the installed adapter version and engine Git ref separately.
- The new source adapter is 0.2.0; editing source does not refresh installed 0.1.1.

### First run

Start with `$rforge-docs-check Audit /absolute/path/to/package`.
Confirm its resolved package and checked-versus-total coverage, then try
`$rforge-check Check /absolute/path/to/package`. Missing prerequisites must
produce an unavailable result, never a clean check.

This is a prepared personal adapter, not a published release. Installation,
post-restart skill discovery, and actual Codex invocation are separate gates.

## Verified behavior and remaining gaps

### medfit exercise

Both installed skills were discovered in a fresh Codex session and exercised on
isolated medfit copies.

- The v0.12.0 audit found no static issues in its covered signatures; comparison
  with v0.11.1 found the new `compare_lr()` export covered.
- Eleven variadic signatures were outside the static checker.
- A default package check exposed medfit's undeclared `rlang` import; after the
  isolated import fix, the rerun completed with zero check errors, warnings, or NOTEs.
- Unit-test warnings and skips are recorded separately from package-check status.

The import fix is integrated into medfit dev (#296). A separate pkgdown audit
found the generated 404 page's invalid `/medfit/NA` MathJax script source; its
repair is integrated into medfit dev (#297). The scoped main promotion
[medfit PR #298](https://github.com/Data-Wise/medfit/pull/298) merged as
`100cca7b` after review and CI. Live deployment is verified separately from
a successful local build.

### Site audits

Use [web-write](https://data-wise.github.io/codex-config/guides/web-write/) for
explicitly requested documentation/site audits and repairs. Its isolated pkgdown
checks covered a full build, examples, 106 HTML pages, 8,268 local references,
and representative desktop/mobile output. This complements the static Rforge
skills; it does not expand their contract or introduce a new Rforge command.

### Fresh-session checks

Two fresh read-only sessions verified that both installed 0.1.1 skills report
unavailable for a missing explicit engine and for the actual v2.21.0 engine
without the required interfaces. Neither ran a package check or unguarded docs
audit, substituted another engine, or reported passing results. This used a
synthetic package; it does not add package-check coverage.

Fresh sessions also verified engine/package paths containing spaces: static
audit completed with zero findings and 1/1 exports checked; the default
`--as-cran` check completed with zero errors/warnings and one new-submission
NOTE. Both skills rejected Python 3.9 when it was the fixture's sole permitted
interpreter; this does not claim supported Python is absent from the host.

### Remaining gaps

- Unchecked variadic signatures.
- An unexplained check termination during CRAN incoming checks in the earlier
  network-restricted session. The successful network-enabled rerun does not prove
  the earlier failure's cause.
- Separately unexercised missing-interpreter/invalid-package fresh-session cases.
- Full external-resource/accessibility coverage and standalone Quarto remain unverified.
- Article, tutorial, cookbook and refcard generation remain deferred.

## Common requests

```text
$rforge-docs-check Audit /absolute/path/to/package and explain unchecked exports.
$rforge-docs-check Check new-export documentation in /absolute/path/to/package since v0.11.1.
$rforge-check Check /absolute/path/to/package and summarize errors, warnings and NOTEs.
```

Replace the sample path and comparison ref with the requested package and its
actual baseline. New-export coverage requires an established ref; a general
static audit may proceed without it and must report coverage as not run.
For a requested strict check, the skill runs both labeled dependency flavors;
incoming adds its own bundle. It does not automatically install dependencies,
change source, submit packages or deploy sites. Missing dependencies or malformed
results are unavailable/incomplete, never passing results.

## Next steps

- [Check evidence and approval decisions](evidence-and-approval.md): report what the checks establish and what stays with the owner.
- [Quality commands](quality.md): the lint, spell, style and URL commands behind `$rforge-lint`.
- [Docs audit](docs-audit.md): the full `/rforge:docs:check` behavior the static docs skill mirrors.

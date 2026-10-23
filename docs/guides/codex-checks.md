# Rforge checks in Codex

!!! tip "Personal pilot"
    Two focused skills reuse the local Rforge checkout. The full Claude command
    catalog and its hooks are not imported.

## Package checks

Ask `$rforge-check` to check an absolute package path. It runs `lib.rcmd` from
Rforge's checkout with `--as-cran` by default and explains errors, warnings,
and NOTEs. R and the check
engine's dependencies must already be available. Checks can execute package
code and produce build/check files; they do not authorize submissions.

Requested strict checks run the two existing flavor passes (`depends`,
`suggests`); incoming adds the engine's incoming bundle. Each result is reported
separately. Raw CLI `--strict` alone is only one pass with donttest examples.
The pilot does not support advanced `--changed` baseline tagging.

A completed package check requires structured JSON, `incomplete: false`,
and zero for every inner R check exit status in `check.exit_status`.
The engine retains real `00check.log` files and reports `check.log_paths`.
Empty log paths mean log evidence is unavailable, never an invented path.

## Documentation checks

Ask `$rforge-docs-check` to audit an absolute package path. It runs the static
`lib.docaudit` engine, reports the resolved scope and export coverage, and
explains incomplete scans. It uses `--package-only` to prevent implicit hybrid
or ecosystem expansion; an explicit ecosystem request uses `--eco` instead.
New-export coverage requires `--since REF`; without a chosen comparison ref,
that component is omitted and must be reported separately from signature coverage.
It does not execute examples or build a site.

## Setup and first use

The source package is `openai/rforge-openai`; the personal catalog is
`openai/.agents/plugins/marketplace.json`. Review the two skill instructions,
register the local catalog in Codex, install `rforge-openai`, and restart.
The default engine checkout is `/Users/davood/projects/dev-tools/rforge`;
point the workflow to another Rforge checkout if needed. Use Python 3.10+.

Version 0.1.1 requires the repaired engines: check envelopes with
`output_format`, `incomplete`, `check.exit_status`, and `check.log_paths`,
plus docaudit's
`--package-only`. These engines and the adapter are integrated on `dev` through
[PR #92](https://github.com/Data-Wise/rforge/pull/92). Use the durable checkout
containing that integration, rather than a retired verification worktree. See the
[adapter source on dev](https://github.com/Data-Wise/rforge/tree/dev/openai/rforge-openai). The
personal local catalog source is `/Users/davood/projects/dev-tools/rforge/openai`.
Installed adapter 0.1.1 and the engine's Git ref should be reported separately.

Start with `$rforge-docs-check Audit /absolute/path/to/package`.
Confirm its resolved package and checked-versus-total coverage, then try
`$rforge-check Check /absolute/path/to/package`. Missing prerequisites must
produce an unavailable result, never a clean check.

This is a prepared personal adapter, not a published release. Installation,
post-restart skill discovery, and actual Codex invocation are separate gates.

## Verified behavior and remaining gaps

Both installed skills were discovered in a fresh Codex session and exercised on
isolated medfit copies. The v0.12.0 audit found no static issues in its covered
signatures; comparison with v0.11.1 found the new `compare_lr()` export covered.
Eleven variadic signatures were outside the static checker. A default package
check exposed medfit's undeclared `rlang` import; after the isolated import fix,
the rerun completed with zero check errors, warnings, or NOTEs. Unit-test warnings
and skips are recorded separately from package-check status.

The import fix is integrated into medfit dev (#296). A separate pkgdown audit
found the generated 404 page's invalid `/medfit/NA` MathJax script source; its
repair is integrated into medfit dev (#297). Main promotion/deployment is tracked
in [medfit PR #298](https://github.com/Data-Wise/medfit/pull/298), not inferred
from a successful local build.

Use [web-write](https://data-wise.github.io/codex-config/guides/web-write/) for
explicitly requested documentation/site audits and repairs. Its isolated pkgdown
checks covered a full build, examples, 106 HTML pages, 8,268 local references,
and representative desktop/mobile output. This complements the static Rforge
skills; it does not expand their contract or introduce a new Rforge command.

Still unverified: fresh-session missing/older-engine handling, unchecked variadic
signatures, full external-resource/accessibility coverage, and standalone Quarto.
Article, tutorial, cookbook and refcard generation remain deferred.

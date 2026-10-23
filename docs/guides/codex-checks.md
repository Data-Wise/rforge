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
`--package-only`. While these changes remain on a feature branch, explicitly
supply that worktree as the engine checkout. An older default checkout is
reported as unavailable for this pilot; refresh the installed instructions
after changes.

Start with `$rforge-docs-check Audit /absolute/path/to/package`.
Confirm its resolved package and checked-versus-total coverage, then try
`$rforge-check Check /absolute/path/to/package`. Missing prerequisites must
produce an unavailable result, never a clean check.

This is a prepared personal adapter, not a published release. Installation,
post-restart skill discovery, and actual Codex invocation are separate gates.

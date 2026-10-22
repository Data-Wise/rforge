# Rforge checks in Codex

!!! tip "Personal pilot"
    Two focused skills reuse the local Rforge checkout. The full Claude command
    catalog and its hooks are not imported.

## Package checks

Ask `$rforge-check` to check an absolute package path. It runs `lib.rcmd` from
Rforge's checkout and explains errors, warnings, and NOTEs. R and the check
engine's dependencies must already be available. Checks can execute package
code and produce build/check files; they do not authorize submissions.

## Documentation checks

Ask `$rforge-docs-check` to audit an absolute package path. It runs the static
`lib.docaudit` engine, reports the resolved scope and export coverage, and
explains incomplete scans. It does not execute examples or build a site.

## Setup and first use

The source package is `openai/rforge-openai`; the personal catalog is
`openai/.agents/plugins/marketplace.json`. Review the two skill instructions,
register the local catalog in Codex, install `rforge-openai`, and restart.
The default engine checkout is `/Users/davood/projects/dev-tools/rforge`;
point the workflow to another Rforge checkout if needed. Use Python 3.10+.

Start with `$rforge-docs-check Audit /absolute/path/to/package`.
Confirm its resolved package and checked-versus-total coverage, then try
`$rforge-check Check /absolute/path/to/package`. Missing prerequisites must
produce an unavailable result, never a clean check.

This is a prepared personal adapter, not a published release. Installation,
post-restart skill discovery, and actual Codex invocation are separate gates.

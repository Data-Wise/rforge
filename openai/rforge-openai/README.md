# Rforge for Codex — personal pilot

Two skills reuse the existing Rforge engines:

- `$rforge-check`: R package validation through `lib.rcmd`.
- `$rforge-docs-check`: static API-content audit through `lib.docaudit`.

The adapter version is independent of the Claude plugin version. This package
contains instructions only and requires a local Rforge checkout with Python
3.10+; package checks additionally require R and the engine's R dependencies.
The personal default source path is `/Users/davood/projects/dev-tools/rforge`.
Version 0.1.1 requires check output provenance/log fields and docaudit's
`--package-only`; older engines are unavailable for this pilot. Before
integration, explicitly supply the repaired feature worktree as the checkout.
It works from another package directory because each skill resolves that
package first and runs its engine from the Rforge checkout.

Default checks use `--as-cran`. Strict requests run both flavor calls;
incoming adds the incoming bundle. Advanced `--changed` is outside the pilot.
Docs audits stay within one package; new-export coverage needs `--since REF`.

## First use

After reviewing and installing the local package, restart Codex and ask:

```text
$rforge-docs-check Audit /absolute/path/to/package and explain the coverage.
$rforge-check Check /absolute/path/to/package and summarize failures.
```

Verify both skill names are discoverable in the new session. Test the static
check first, then run a package check on a package you choose. Missing engines
must be reported as unavailable, never as passing results.

## Local installation

The local catalog is `openai/.agents/plugins/marketplace.json`. Register it using
Codex's plugin marketplace controls, then select `rforge-openai`. Installation
and registration change personal configuration and are separate from preparing
these files. No hooks, Claude command migration, background jobs, or automatic
submissions are included. Refresh the package after editing skill instructions;
engine changes are read directly from the local checkout.

# Rforge for Codex — personal pilot

Three skills reuse the existing Rforge engines:

- `$rforge-check`: R package validation through `lib.rcmd`.
- `$rforge-docs-check`: static API-content audit through `lib.docaudit`.
- `$rforge-lint`: fresh-process package lint through `lib.rcmd`, with explicit
  evidence for the installed package/library used by CI.

The adapter version is independent of the Claude plugin version. This package
contains instructions only and requires a local Rforge checkout with Python
3.10+; package checks additionally require R and the engine's R dependencies.
The personal default source path is `/Users/davood/projects/dev-tools/rforge`.
Since 0.1.1, the adapter requires check output provenance/log fields and docaudit's
`--package-only`; older engines are unavailable for this pilot. The original
adapter and repaired engines are integrated on `dev` through PR #92. Use the
durable checkout containing that integration; retired pilot worktrees are not
required. Report the engine Git ref separately from adapter 0.2.0.
It works from another package directory because each skill resolves that
package first and runs its engine from the Rforge checkout.

Default checks use `--as-cran`. Strict requests run both flavor calls;
incoming adds the incoming bundle. Advanced `--changed` is outside the pilot.
Docs audits stay within one package; new-export coverage needs `--since REF`.

## Why lint reuses the engine

The adapter adds instructions around `lib.rcmd`, rather than maintaining another
R lint implementation. This preserves the engine's configured linters and JSON
report. It does not make the local environment identical to CI: the workflow
records installed-source and library evidence separately. Automatically loading
development code or suppressing missing-name diagnostics was rejected because
the regression fixture shows that attaching testthat hides the helper defect.
The fixture prepends its package library while retaining dependency libraries;
it covers both the default environment and dependencies found via `R_LIBS_USER`.

## First use

After reviewing and installing the local package, restart Codex and ask:

```text
$rforge-docs-check Audit /absolute/path/to/package and explain the coverage.
$rforge-check Check /absolute/path/to/package and summarize failures.
$rforge-lint Lint /absolute/path/to/package and assess CI parity.
```

Verify all three skill names are discoverable in the new session. Test the static
check first, then run a package check on a package you choose. Missing engines
must be reported as unavailable, never as passing results.

## Local installation

The local catalog is `openai/.agents/plugins/marketplace.json`. Register it using
Codex's plugin marketplace controls, then select `rforge-openai`. Installation
and registration change personal configuration and are separate from preparing
these files. No hooks, Claude command migration, background jobs, or automatic
submissions are included. Refresh the package after editing skill instructions;
engine changes are read directly from the local checkout.

## Verification boundary

Fresh-session discovery and isolated medfit package/docs checks passed. Static
checks leave variadic signatures unchecked. Installed 0.1.1 missing/older-engine
rejection was verified separately; 0.2.0 lint discovery/invocation has not been
verified in a fresh Codex session. Local engine smoke tests are separate evidence.
Site builds, runnable examples and live resources need separate verification.
See the repository website's
[Codex guide](https://data-wise.github.io/rforge/guides/codex-checks/).

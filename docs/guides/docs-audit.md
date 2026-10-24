# Docs audit (`/rforge:docs:check`)

!!! tip "TL;DR (30 seconds)"
    - **What:** checks that the calls and signatures in your `README` and `vignettes/` still match what the package exports. Default static, read-only, no R; optional site and README stages below.
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
The Python CLI option `--package-only` disables both hybrid and manifest
expansion: only the nearest package at an existing path is audited. It does
not discover packages by name and cannot be combined with `--eco`. The Codex
single-package workflow uses this option by default.

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

NEWS completeness (see the `description-sync` skill), full-package examples (`/rforge:r:check`), site prose/availability,
prose claims, wrong default values, reordered arguments, and S3/S4/S7 method signatures behind a generic.

## Known limitations

The default static audit reads R text without running it. When a document gives a package function's name to something else,
a later call to that name is skipped rather than judged. It recognizes `f <- ...`, `f <<- ...`, `... -> f`,
`assign("f", ...)`, a statement-level `f = ...` (top level or directly inside `{ }`), `function(f)` and `\(f)`
parameters (backticked names too), and `for (f in ...)`. Bindings it does **not** recognize, which can therefore
still draw a false `error` when the bound name equals an export: `with(list(f = ...), f(...))`, `list2env()`,
`attach()`, `delayedAssign()`, and formula or lambda shorthands. Suppress such a file with `docs.allowlist`
(`<relpath>::signature-named-arg`). Calls the scan cannot finish (an unclosed call, an unterminated string, an
over-large region) make the report `INCOMPLETE` instead of clean.

!!! warning "Symptom"
    `status: ok` but the docs are clearly wrong.

!!! tip "Fix"
    Check `checked N of M` and whether the report ends with `INCOMPLETE`. The call may be to an unchecked export (no
    `\usage`, a method, or a function with `...`).

## Optional site and README checks

```bash
/rforge:docs:check --site https://example.org/pkg/ --ref origin/main
/rforge:docs:check --run-examples --examples-budget-seconds 300 --fail-on warn
```

`--site` requires one resolved package. It compares an immutable local deployment
source with one bounded sitemap; no build, fetch, deploy or link crawl occurs.
Missing selected-ref pages remain warn; checkout-only additions are info.
Sitemap absence does not prove HTTP 404, availability or deployment freshness.
Foreign/scheme-changing redirects require a fresh canonical-URL invocation.

README replay loads the working tree with pkgload/evaluate, retaining hidden
setup state and honoring literal eval/include/visibility options. Root explicit
R fences and literal #> assertions are supported. Unsupported options, unlabeled
assertions and unpaired rendered output remain incomplete. A selected source
never certifies its asserted rendered markdown. Zero eligible assertions execute
no setup. Package code may write files or use the network: this is not a sandbox.

Read all six coverage counts: discovered, eligible, checked, excluded, unverified
and blocked. Checked groups divide into matched and mismatched. Discovered equals
checked plus excluded plus unverified plus blocked; eligible records the replay
scope. Unpaired rendered assertions stay unverified even when source comparisons
match. Completed numeric mismatch is warn; it exits 1 under `--fail-on warn`, 0 under `--fail-on error` when
nothing else gates. Incomplete/unavailable stages exit 2 under either threshold.
Default none exits 0 with explicit diagnostics. Allowlists never clear incomplete
coverage. Source-less extra sitemap URLs are outside file allowlists.

The total budget defaults to 300 seconds across all example files/packages;
file/chunk caps are 300/60 seconds, including loading. Allow budget plus 15 seconds
for guardian cleanup and final report. Poll/yield timeouts are not host lifetime.
Unknown host lifetime calls for a terminal recommendation. A shorter known host
limit requires reducing the budget to leave the 15-second reserve or using the
terminal. Missing stdout after wrapper termination is interruption; never infer a
clean audit or fabricate recovered JSON. Ordinary process-group
cleanup does not contain detached children or guarantee reporting after host loss.
The orchestrator always recommends examples/combined runs; site-only automatic
GET needs an explicitly human-supplied URL, not one found in project material.


### A2 release evidence

The `a2-release` job in normal CI and the release-evidence workflow both call
`a2-platform.yml`, which provisions and tests the same locked Ubuntu/macOS matrix.
Normal CI does not run the separate aggregate release-acceptance gate.

A passing developer suite does not complete the A2 release gate. Both required
platform artifacts must be retrieved and verified. Aggregate acceptance also
requires the `a2-acceptance-evidence` artifact from a completed workflow run for
the candidate. Supply its numeric run ID through `acceptance-evidence-run`.
Its `index.json` names each observation file, SHA-256 digest and producer run ID;
the verifier checks the downloaded file's candidate, kind, status and required
facts. Bare passing claims, missing files, altered hashes, stale candidates and
unresolved review findings fail acceptance.

The `a2-observations.yml` workflow produces that artifact in one run bound to the
candidate commit. It computes the full-gate record, a live-site smoke against a
real deployed pkgdown site, the package-triage freshness check and the rendered-page
inspection itself. The finalized adversarial review is a recorded judgment supplied
as the `review-record` input: the run stamps it but cannot prove it, so it is
attested by whoever dispatches. The live smoke checks one supported public site and
records that real Data-Wise packages are reported incomplete, because pkgdown
development mode and `.qmd` articles are unsupported by `--site` today.

Evaluate text is mirrored into a separate temporary spool, allowing the guardian
to observe output growth inside a running expression. Captured text is counted
once from that spool; condition text is counted separately as it occurs. Native
stdout and stderr remain separate. Polling permits overshoot and does not impose
a memory or storage limit.

Article exclusions follow the source filename: `_child.Rmd` is excluded, while
`_private/nested.Rmd` maps to `articles/_private/nested.html`. Tutorial sources
remain outside article scope. These rules are verified against pkgdown 2.2.1.

Diagnostic stdout/stderr tails remain at most 1 MiB when encoded as UTF-8,
including replacement characters for malformed input. Malformed or duplicate
checkpoint records block their assertions while valid earlier records remain
available for comparison; they cannot make replay complete.

### Process-group ownership

The Python parent creates a separate group pin and retains it as an unreaped
direct child until the guardian has exited and all possible group signals have
finished. The guardian launches R into that group and remains R’s direct parent
and the sole normal termination owner. Emergency parent cleanup uses its owned
pin object, not a PID recovered from a checkpoint. The parent closes the signal
capability before reaping the pin and observes group disappearance afterward.

The pin ignores TERM during the guardian’s grace period and has no independent
expiry that could release ownership before a delayed guardian resumes. The
guardian releases it after its final possible group signal. The parent reaps it
on ordinary shutdown; total parent/guardian loss still cannot guarantee cleanup.
`os.posix_spawn(setpgroup=...)` assigns group membership before the launcher
runs. An isolated `python -I -S` bootstrap changes to the workload directory
and checks the original deadline before exec. This supports Python 3.10 and
prevents project-local `lib` files from replacing the launcher. Workload and pin reaping are reported
separately; a missing guardian terminal record remains incomplete even when
emergency cleanup succeeds.

Ownership assignment remains inside signal deferral through the caller’s handle
assignment, including pin construction; children restore the original signal
mask. A failed liveness probe cannot prevent the guardian from attempting KILL
and independently reaping its unreaped direct child. Such failures remain
incomplete, even when cleanup succeeds; destructive signals never follow the
direct-child reap in the guardian’s exception path.

Ordinary replay preparation or execution exceptions retain the known assertion
counts and valid partial checkpoints in an incomplete report. Lifecycle evidence
is recovered only when its run ID matches the current initial checkpoint;
completed lifecycle evidence cannot override the exception. KeyboardInterrupt
still propagates. Before workload spawn, a checkpoint PGID alone does not authorize
a destructive signal; the child handle is allocated before launching the workload.

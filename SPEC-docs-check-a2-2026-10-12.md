# docs:check A2 — live-site and README example audit

Date: 2026-10-12. Revision: 8 (Python policy amendment, 2026-10-23).
Status: revision 7 approved and implementation authorized on 2026-10-12; user authorized removing the Python 3.12 pin on 2026-10-23. All other acceptance requirements remain unchanged.
Target: next minor release (provisionally 2.22.0); 44 commands remain.

## Objective and recommendation

Extend the existing `/rforge:docs:check` with opt-in `--site URL` and
`--run-examples`. Preserve the default static, offline audit. Keep site inspection
and example execution independently testable and independently reportable.
Recommended build order: shared stage reporting → site → examples → integration.
The user approved this specification and requested implementation planning only.
Implementation and release remain separate authorized tasks. Material scope limitation: source/render
pairing is deferred, so source-based READMEs with asserted rendered output
remain incomplete even when their source assertions replay successfully.

## Design review and owning sources

- `archive/specs/SPEC-docs-check-content-audit-2026-10-11.md`, A2 contracts:
  deploy-ref expectations, fresh ordered README sessions, working-tree package
  loading, output normalization, skip markers, and real integration smoke tests.
- `lib/docaudit.py#_envelope`, `audit_package`, `audit`, `main`: the shipped
  envelope uses `kind: docaudit`, `max_severity`, `audited`, `incomplete`, and
  `engine_missing`. With a threshold enabled, incomplete audits already exit 2.
  Ecosystem aggregation currently initializes `engine_missing` to an empty list;
  A2 must aggregate stage failures rather than lose them.
- `commands/docs/check.md` and `docs/guides/docs-audit.md`: current public contract
  is static and read-only. Execution changes that contract only when requested.
- `lib/docaudit.py#extract_regions`: static extraction is not yet a complete
  executable-chunk parser. Do not use A1 region extraction to select executable chunks.

Retain the archived decisions, with explicit refinements below. In particular,
being ahead of a deployment ref must not downgrade a page missing from that ref.
Unreleased source pages and missing deployed-source pages are separate results.

## Command contract

```bash
python3 -m lib.docaudit --path /path/to/package --site https://example.org/pkg/
python3 -m lib.docaudit --path /path/to/package --site https://example.org/pkg/ --ref origin/main
python3 -m lib.docaudit --path /path/to/package --run-examples --format json
python3 -m lib.docaudit --path /path/to/package --site https://example.org/pkg/ --run-examples --fail-on warn
```

Slash-command equivalents map these flags directly. `--ref` requires `--site`.
An explicit site URL requires exactly one resolved package; ambiguous ecosystem
scope is a CLI error, not reuse of one URL for every package. `--run-examples`
may sweep packages, sequentially. No dependency installation, fetch, build,
deployment, or source edits occur automatically.

Each requested stage reports state (`complete`, `incomplete`, `unavailable`,
`not-applicable`), counts, provenance, and reasons. Unrequested stages are absent.
Static findings remain available even when an optional stage fails. Missing
engines propagate through package and ecosystem reports. A requested unavailable
or incomplete stage sets overall `incomplete`; no assertions anywhere in the
README surface is `not-applicable`. Assertions present but outside supported
comparison scope make the stage incomplete, with explicit unverified counts.
An excluded-only stage is also `not-applicable`, with exclusion reasons/counts.
`--detailed` may hide info findings but never stage states or coverage counts.
Default `--fail-on none` remains exit 0; enabled thresholds retain exit 2 for
incomplete/failed audits, exit 1 for complete threshold findings, else exit 0.
CLI misuse exits 2 independently of `--fail-on`.
Buffer the final report until execution completes or the runner deadline fires.
Keep the existing scope as the first text line. Immediately afterward in that report, print
requested stage states and diagnostic reasons; unavailable/incomplete stages also
emit a concise stderr notice, including in JSON mode. JSON stdout remains one
valid document. Preserve the final INCOMPLETE marker and prohibit “no findings”
as a clean conclusion for such runs. No-output stages never execute setup alone.
The single-package site restriction is a proposed A2 scope choice, not removal
of a shipped feature; ecosystem URL configuration is deferred.

## Site stage

1. Accept an explicit HTTP(S) base URL without credentials, query, or fragment.
   Normalize its path and retrieve its `sitemap.xml` using stdlib `urllib`.
   Bound time and response size (proposed 10 seconds, 5 MiB). Handle malformed
   XML, offline responses, redirects, and sitemap indexes explicitly. A2 supports
   a single URL-set sitemap; an index is incomplete, not an empty site.
2. Resolve `--ref` locally to a commit. Otherwise infer one unambiguous pkgdown
   deployment branch from recognized workflow configuration, falling back to
   locally available `origin/main`, then `main`, with provenance. Ambiguous
   triggers, dynamic workflows, missing refs, or missing git make the stage
   incomplete. Do not fetch. Branch inference is evidence of intended source,
   not proof of the commit currently deployed.
3. Inspect the immutable commit tree, including pkgdown configuration. Derive
   supported article and Rd routes; retain internal Rd topics. Honor recognized
   exclusions and article naming rules. Never silently apply naive filename
   mapping to an unsupported custom layout: report affected scope as incomplete.
   Keep source path → expected URL attribution. No generated index, authors,
   news, or 404 pages are mandatory expectations.
4. Compare normalized same-site paths, preserving case and base-path boundaries.
   Missing expected routes emit `site-missing-page` (warn), phrased as absent
   from the sitemap, not a proven HTTP 404. Sitemap coverage is not availability.
   Extra routes emit info only within the supported article/reference surface;
   generated pages are not stale-page findings.
5. Separately report pages added in the checkout relative to the selected ref
   as unreleased info. Dirty-tree additions must be identified as such. Missing
   pages from the selected ref stay warn even when the checkout is ahead.

Site checks do not inspect prose, render pages, crawl links, or verify deployment
freshness. Network errors are stage diagnostics, not missing-page findings.
Read-only site GETs are orchestrator auto-run only for an explicitly supplied
URL, following the archived decision; do not discover arbitrary sites to probe.

### Normative site rules

The requested URL establishes the comparison origin and base path. Accept a
maximum of three same-origin redirects; reject HTTPS downgrade and cross-origin
redirects as incomplete with the final target shown. Do not silently alias
custom domains, www/apex hosts, or HTTP/HTTPS. If source `url:` disagrees with
the requested base, stop comparison as incomplete and ask the caller to select
the canonical URL. A non-empty sitemap with no entries within that base is
incomplete, never mass missing-page findings. Mixed foreign entries are counted
and excluded with a message. Preserve escaped separators and path case; drop
fragments, normalize default ports, and do not collapse distinct routes.

| Source input | Supported derivation or explicit limitation |
|---|---|
| Deployment workflow | Literal `on.push.branches` containing exactly one branch in a workflow with a literal pkgdown build/deploy command; no alternate checkout ref. Resolve `origin/<branch>`, then local branch. Multiple candidates, globs, expressions, alternate checkout refs and reusable workflows require explicit `--ref`. |
| No deployment candidate | Fall back to local `origin/main`, then `main`; label this a fallback assumption. Never fall back after detecting an ambiguous candidate. |
| Ref provenance | Report selected ref, resolved SHA, commit timestamp, selection reason and observed local-ref status. Timestamp is not evidence that a remote-tracking ref is current. No deployment-SHA freshness claim. |
| Standard `man/*.Rd` | `reference/<Rd basename>.html`, including internal topics; index selection does not remove pages. |
| Standard Rmd articles | Output is always under `articles/`: `vignettes/foo.Rmd` → `articles/foo.html`; `vignettes/articles/foo.Rmd` → `articles/foo.html`; `vignettes/pizza/slice.Rmd` → `articles/pizza/slice.html`. Exclude underscore-prefixed child files; tutorial sources are outside article scope and explicitly counted. A pinned pkgdown fixture for all three mappings is a hard release gate; route collisions make derivation incomplete. |
| `articles`, `reference`, `navbar` configuration | Index/navigation organization alone is not a page exclusion or rename. External articles are links, not required local routes. |
| Quarto, custom extensions, `as_is`, build overrides, configuration overlays | Affected routes are unsupported/incomplete until committed fixtures establish their exact mapping; never invent `.html` routes. |
| `url:` | Canonical base validation only; never permission to silently rewrite origins. |

Parse recognized YAML data without evaluating expressions. If the optional YAML
reader is unavailable and relevant configuration exists, mark inference incomplete
(or require an explicit ref for workflow inference); do not add a mandatory Python
dependency. An explicit ref bypasses branch inference, not route uncertainty.
Unsupported route scope retains checked routes and reports excluded counts.
When source `url:` is absent, use the explicit requested base for comparison;
a missing sitemap is incomplete, not evidence that source pages are missing.
The strict same-origin policy intentionally rejects HTTP→HTTPS redirects: show
the canonical target and require a fresh invocation with it. This is a scope
choice, not a claimed live-site defect.

Primary rule references: [pkgdown articles](https://pkgdown.r-lib.org/reference/build_articles.html)
and [reference pages](https://pkgdown.r-lib.org/reference/build_reference.html).
Pin fixture provenance to the supported pkgdown release during implementation;
latest online documentation alone is not a versioned compatibility promise.

[pkgdown build_site](https://pkgdown.r-lib.org/reference/build_site.html) distinguishes
local destination from development-site subdirectories. Support default/explicit
release mode initially. Non-default development mode, development.destination,
or workflow PKGDOWN_DEV_MODE overrides make the site stage incomplete before
comparison until versioned fixtures establish their mapping. Top-level destination
is a local build path, never an automatic public-URL suffix. Publication transforms
remain unsupported. Add explicit fixtures for these configurations.

## Example stage

Scope: explicit R fences/chunks in root `README.md`, `README.Rmd`, and
`README.qmd`. Each eligible execution document uses a fresh `Rscript --vanilla`
session, subject to the source-selection rules below. Vignettes, unlabeled
fences, Python, plots, and semantic prose claims
are outside A2.

### README source selection and setup

If exactly one README source (`README.Rmd` or `README.qmd`) coexists with
`README.md`, prefer that source and do not independently replay the rendered md.
A2 compares only literal `#>` assertions already in the selected source; it does
not knit or pair source chunks with rendered output. Count rendered `#>` assertion
groups as unverified whenever md is not executed: source assertions cannot verify
rendered counterparts without pairing. Any such count makes the stage incomplete,
including when the source has no assertions. With no assertions in either file,
the stage is not-applicable and setup does not execute. Two coexisting sources are ambiguous:
mark the stage incomplete and execute neither. With only md present, execute it
as a standalone transcript and state that omitted setup cannot be reconstructed.
An object-not-found failure without source evidence is an incomplete replay
(`examples-error` candidate), not proof that the published example is broken.

Report `rendered-unpaired` whenever rendered assertions remain unverified.
A source with no eligible assertions plus asserted rendered output executes no
R and exits 2 under either enabled threshold. A source with eligible assertions
may execute them, but cannot clear that incompleteness. This is an explicit
partial-coverage limitation, not an info-only finding; neither an allowlist nor
`--fail-on error` bypasses it. Source/render pairing remains a future scope change.

This deliberately narrows the archived per-file execution contract rather than
introducing a fragile source/render pairing system. Add a source/md fixture with
hidden state creation: selected-source execution must retain that state, rendered
md must not be executed a second time, and source-without-assertions must report
unsupported comparison coverage rather than clean examples.
Global `knitr::opts_chunk$set()` and Quarto execute defaults affecting eval/include
must be resolved as supported literal values before execution. Dynamic defaults,
child documents, option templates and unsupported visibility/output overrides
make the file incomplete; do not infer effective options solely from each header.
Body options override header options, consistent with knitr; repeated conflicting
values at the same precedence are unsupported. Setup requiring knitr adds it to
the file's dependency preflight, never automatic installation.

Reference: [knitr chunk options](https://yihui.org/knitr/options/) establishes that
include=false still evaluates code while omitting it from output, and that body
options override headers. A2's conservative subset is not a full knitr renderer.

Load the working tree with `pkgload::load_all()`; verify package path/version in
the report. Evaluate eligible chunks in document order, preserving setup state.
Use `evaluate` and shipped `lib/r/docexamples.R`; missing Rscript, pkgload,
evaluate, or required package dependencies is unavailable/incomplete. Do not
substitute an installed package. Do not install dependencies.

Honor `eval: false`/`eval=FALSE` as non-execution. `include: false`/`include=FALSE`
executes setup but supplies no visible output assertions; this intentionally
refines the archived instruction to skip hidden chunks, which would lose state.
Recognize `# docs-check: skip`, preceding `<!-- docs-check: skip -->`, and
`#| docs-check: skip`. Skip installation chunks; this is a convenience filter,
not a security sandbox. Unknown dynamic chunk options are explicitly unsupported.

Use a dedicated executable-chunk extractor returning file/line spans, engine,
literal options, skip reason, expressions and associated `#>` output lines.
Support closed backtick/tilde fences labeled `r` or `{r ...}` only. Support literal
boolean eval/include options from the Rmd header and Quarto `#|` lines under the
precedence rules above; unsupported dynamic values prevent execution. A preceding
HTML skip marker must be the immediately preceding nonblank line. Unterminated
R fences are incomplete and never executed. Installation detection must inspect
code tokens rather than comments/strings; it is not a sandbox guarantee.

### Literal options

Support eval/include/echo/warning/message as literal booleans, results as markup
or hide, collapse as a literal boolean, comment as literal `#>`, and error=FALSE
with stop-on-error semantics. Source echo controls display only. Include/results/
warning/message control eligible channels; hidden assertions are counted as
explicitly excluded. Unassociated output is incomplete. Plain chunk labels and
engine identifiers are metadata. Every other execution/rendering option, literal
or dynamic, is unsupported/incomplete before execution, including error=TRUE,
numeric error options and figure options. List unsupported options; never mistake
an intentional error example for a broken example by silently ignoring error=TRUE.
The same subset applies to effective global defaults. This conservative subset
is a proposed scope choice grounded in knitr's documented visibility semantics.

### Output comparison

Only line-leading `#>` comments represent pasted output. Parse expression/output
association conservatively; compare an ordered documented subsequence without
reusing actual output tokens. Ambiguous alignment emits `examples-shape` (warn),
not a numeric error. Capture stdout, conditions, and output separately. Force
UTF-8 and width 80; report R/package versions and normalization policy.

Normalize whitespace. Numeric comparison uses one unit in the last documented
digit, including scientific notation; preserve signs, percentages, NA/NaN/Inf,
inequality direction, and labels. Do not normalize unrelated numbers into a
match. Formatting/token-shape differences remain warn. `examples-output` is
warn in the initial A2 release, subject to the promotion gate below.
RNG calls without an earlier explicit seed make comparisons info; absence of
recognized RNG calls is not proof of determinism. Package-internal randomness
and unstable output must be triaged before an error gate is claimed reliable.

Alignment requires the same expression, an identical nonnumeric skeleton and
equal numeric-token count (except the explicitly supported inequality form).
Subsequence matching may omit undocumented expressions, never labels or values
within a documented assertion. Warnings/messages are separate assertions;
timestamps, versions and unstable format fields are not numeric error candidates.
There is no automatic proof of determinism. A2 initially emits `examples-output`
as warn; promoting it to error requires a separately approved revision after
hold-out/replay validation. This explicitly revises the archived D7 error default;
no per-package severity configuration is added in A2.
Use decimal-string arithmetic with an inclusive tolerance: a documented decimal
with k fractional digits and exponent e has tolerance 10^(e-k), with e=0 when
absent. Thus 1e-04 has tolerance 0.0001, while 1.00e-04 has tolerance 0.000001.
Apply tolerance only to equality assertions; inequalities use the literal strict
or non-strict bound without rounding tolerance. This policy measures agreement
with displayed precision, not full numerical accuracy.

| Documented | Actual (same labeled assertion) | Verdict |
|---|---|---|
| `0.19` | `0.1900` | match |
| `0.19` | `0.20` | match at inclusive 0.01 boundary |
| `0.19` | `0.2001` | examples-output warn |
| `0.164` | `0.1648` | match within 0.001 |
| `0.19` | `0.164` | examples-output warn |
| `1e-04` | `0.0001` | match |
| `p < 0.001` | `p = 2.2e-16` | match by explicit p-value inequality rule |
| `p < 0.001` | `p = 0.002` | examples-output warn |
| `55%` | `36 %` | examples-output warn (percent unit preserved) |
| `55%` | `0.55` | examples-shape warn; no implicit percent conversion |
| `1,234` | `1234` | examples-shape warn; no guessed grouping convention |
| `NA` | `NA` | match; NA, NaN and signed Inf otherwise require exact token identity |

Unseeded/uncertain stochastic assertions remain info and count as unverified,
not matched. Output mismatch is a completed comparison; lost output, ambiguous
expression association or blocked execution makes the stage incomplete.

For the same labeled assertion, `p < 0.001` versus `p < 2e-16` matches because the
actual upper bound implies the documented bound. Weaker or opposite inequality
bounds are unverified/shape-warn and incomplete, not guessed contradictions.
Bare `<2e-16` without the matching label is outside alignment.

### Coverage accounting

Coverage counts partition discovered assertion groups into checked, explicitly
excluded, unverified and blocked groups; matched/mismatched are subdivisions of
checked. Literal visibility exclusions, eval=false and explicit skip markers
are excluded with reasons, not verified. Excluded-only documents are
not-applicable with counts; mixed checked/excluded coverage may complete.
Unsupported options, uncertain assertions and unexecuted rendered assertions
are unverified and make the stage incomplete. Execution failure makes affected
groups blocked and the stage incomplete. No eligible assertions means setup
does not execute. Report the selected-source and rendered counts separately.
Skip markers and eval/visibility rules define execution/comparison exclusions,
not `docs.allowlist` suppression. No minimum checked fraction is imposed: complete
means the declared eligible scope finished, not that every published assertion
was verified. Always show all four partition counts in the stage headline and
JSON, including under `--detailed`; never describe excluded groups as passed.
Test a one-checked/many-excluded fixture and an excluded-only fixture. Fixture
release gates require nonzero checked assertions for their clean/planted cases,
independently of this user-document exclusion policy.

### Execution limits and reporting

On execution failure emit one `examples-error` (warn), stop the file, and mark
remaining chunks blocked with counts. Do not generate downstream failure spam.
Timeout terminates the file session and marks it incomplete. Proposed limits:
60 seconds per chunk and 300 seconds per file, with external process termination
as the hard backstop. A blocking native call must not evade the file deadline.
Add `--examples-budget-seconds` (positive integer, default 300; requires
`--run-examples`) as the total example-stage deadline across all packages/files,
including engine startup and loading. Use the minimum of remaining global,
file and chunk limits. Terminate the owned process group on timeout (POSIX),
with a tested Windows process-tree strategy or explicit unavailable diagnostic.
Do not reuse `_invoke_r` unchanged: its timeout does not guarantee descendant
cleanup or partial output recovery. Completed chunk results are checkpointed
in temporary structured files and included in the final report; no stdout JSON
streaming. Remaining packages/files are explicitly budget-blocked. The command
host must allow this deadline plus cleanup/report overhead; shorter host limits
require a smaller flag value or a supported background invocation, never a
claim of complete results after host termination.
Before loading and before every chunk, the R runner atomically writes a
sequence-numbered phase-start checkpoint identifying the file/chunk. The parent
obtains the guardian's armed deadline/start timestamp and acknowledges each
checkpoint before the runner may enter that phase; sequence numbers prevent
overwritten or stale acknowledgements. Do not restart timing on parent receipt.
Poll every 100 ms while active; report observed enforcement delay rather than
promise a scheduler-independent 100 ms maximum.
The parent enforces the 60-second chunk limit by requesting guardian termination,
including for blocked native calls. Loading is a separate phase covered by the
file/global deadline. Completion checkpoints are atomic; malformed/partial or
missing checkpoints mean incomplete and never successful comparison.

The slash-command wrapper must configure a process lifetime longer than the
requested budget plus cleanup/report overhead, or pass a smaller budget with
at least 15 seconds reserved for cleanup/reporting. A host's poll/yield interval
is not a process timeout. If lifetime support is unknown, recommend the terminal
invocation instead of launching execution with an assumed safe deadline. Keep
300 seconds as the standalone CLI default. Before launching R, stderr announces
the scope,
budget and started stage; flush phase/coverage progress there without contaminating
JSON stdout. Controlled timeout returns the complete partial-result envelope.
External host kill cannot guarantee a final report: report it as interrupted,
never interpret missing stdout as clean or claim checkpoint recovery succeeded.

Run from a temporary working directory, preserve access to package data, and
clean temporary artifacts. This reduces accidental writes but is not isolation:
arbitrary R/package code can write elsewhere or use the network. The command
must describe execution clearly. Orchestrator execution remains recommend-only;
explicit user invocation authorizes it. Never claim this stage is read-only.

### Process supervision and stdio

The existing `lib/rcmd.py#_invoke_r` uses subprocess.run/communicate; it does not
itself exhibit the proposed polling-loop undrained-pipe bug. A2 must use separate
temporary stdout/stderr files and distinct structured evaluate checkpoints.
Retain at most 1 MiB of diagnostics per stream; abort as incomplete when combined
captured textual output exceeds the 10 MiB threshold defined below (report
observed polling overshoot).
Test native/child output over 64 KiB that bypasses evaluate; child output never
contaminates JSON stdout.

Use an independent Python stdlib guardian outside the R process group. It
launches and reaps its direct R child; the parent reaps the guardian on normal
completion. Observe group disappearance separately; do not claim to reap
grandchildren. Cleanup is successful only when observed. Normal shutdown closes
handles; guardian failure or unverifiable termination is incomplete.

Process-group termination covers cooperating descendants remaining in that
group. Detached sessions/groups are outside this guarantee; this is not process
containment. If the host kills both parent and guardian, no cleanup guarantee
remains. A killed process cannot report completion: the wrapper labels missing
completion as interrupted. Print the temporary run-directory/run ID at startup;
keep an atomic lifecycle marker there (started/completed/interrupted and last
phase) for inspection while it survives. Total host termination cannot guarantee
marker updates or temporary-file cleanup. Do not add automatic stale PID killing
or claim that a later invocation reconstructs the lost report.

Test parent termination while the guardian survives, ordinary child cleanup,
guardian failure, large-output handling and the documented detached-process
limit. The acceptance fixture must clean up its own deliberately detached child.
These are required implementation tests, not outcomes verified in this session.

The 10 MiB output threshold is one shared total of stdout bytes, stderr bytes
and UTF-8 structured evaluate text payload bytes. It is detected by polling,
not a hard storage limit. Count each captured payload once across cumulative
checkpoints, excluding serialization metadata; do not echo evaluate output to
the native capture files. If a mirror is nevertheless captured, its bytes also
count. For example 1 MiB stdout + 2 MiB stderr + 3 MiB evaluate text totals
6 MiB, not three independent allowances. It does not bound
arbitrary package filesystem writes, plots or memory. Report truncation and
observed overshoot; exceeding the cap remains incomplete.

### Guardian protocol and deadline ownership

The guardian is the sole normal termination owner and direct
R parent. The Python parent handles reports and phase requests. Only observed
guardian failure permits emergency parent-owned group termination; report that
run incomplete even if cleanup succeeds. Parent-first termination with a later
guardian deadline is rejected because it adds a second kill authority and shifts
the advertised global deadline.

Parent and guardian use Python `time.monotonic_ns()` on the same host with Python
3.10 or newer; record `get_clock_info('monotonic')`. Python documents a shared clock
across processes, including macOS from 3.10. Budgets measure that clock, not a
wall-time promise across machine suspend. A heartbeat lapse can classify a host
stall as interruption; it must not emit a package-output defect.

Use atomic run-ID/sequence-numbered files in the private run directory for
parent heartbeat (updated at least once per second), phase arm/ack, termination
requests and guardian status. The guardian measures heartbeat age from the last
new sequence it observes; stale timestamps cannot refresh it. No heartbeat
for 5 seconds, or the absolute global deadline, triggers termination, whichever
comes first. Neither event resets the deadline. Retain final complete checkpoints
until report assembly; guardian shutdown must not delete them before the parent
reads them. Partial/malformed records never verify an assertion.

| State/event | Required action/evidence |
|---|---|
| Startup | Establish global deadline before engine preflight/startup; arm guardian before R runs package code. Expired budget means no launch. |
| Loading/chunk arm | Parent sends file/phase identity and remaining limits. Guardian records effective absolute deadline = minimum of global, file and (for chunks) its phase start + 60 seconds; guardian acknowledges, then parent releases R. No acknowledgement means no phase execution. |
| Deadline/request/output excess | Guardian records a termination ID, reason, phase and observed monotonic time before TERM; duplicate requests are idempotent. Parent may request but never independently signal a healthy guardian's group. |
| Terminating | TERM immediately when the triggering event is observed; KILL after at most 2 seconds if necessary, then wait at most 5 seconds for direct-child exit/group disappearance. Record actual delay and cleanup observations. |
| Completion/deadline collision | Guardian processes expired effective deadlines before accepting success. Completion accepted before the deadline retains its results; completion at/after it cannot certify the phase. Record which event won rather than infer from R's signal/exit code. |
| Finalization | Parent reads guardian terminal status and valid checkpoints, marks remaining assertions blocked and assembles one partial envelope. Missing/failed terminal status is incomplete. Reap guardian; bounded report assembly has a 5-second allowance. |

The wrapper's 15-second reserve covers 2 seconds termination grace, 5 seconds
cleanup, 5 seconds report assembly and overhead. Failure to assemble in that
allowance is interrupted/incomplete; a killed host cannot guarantee a report.
Guardian also monitors capture sizes and checkpoint text totals; parent loss
cannot disable output-threshold detection while the guardian survives. Polling
and scheduling delay is measured, never represented as a hard storage or
scheduler-independent execution bound. Detached-process and total-host-kill
limitations remain unchanged. Deadline-collision, heartbeat-lapse, lost-ack,
rapid-transition, checkpoint-retention and guardian-failure cases are mandatory
manifest tests, including tests of reason attribution.

Reference: [Python monotonic clock](https://docs.python.org/3/library/time.html#time.monotonic).

## Architecture and suppression

Keep `lib.docaudit` as the public facade; place site and execution internals in
separate private modules if that avoids expanding its existing scanner. Keep
R code in `lib/r/docexamples.R`, using existing runner conventions and bounded
subprocess calls. No new public module or mandatory Python dependency.

Preserve existing finding keys and add stage metadata, rather than replacing
the A1 schema. Reuse `docs.allowlist` source-relative suppression for attributable
findings; suppression never authorizes execution or conceals incomplete stages.
Site-only extra URLs have no source file: report them as stage info outside the
file allowlist. Document that exception explicitly.

Package engine_missing lists are sorted unique engine identifiers; ecosystem
engine_missing is their sorted union. Preserve each package's list and stage
reasons in package entries. Add mixed-package missing-engine aggregation tests:
the existing `lib/docaudit.py#audit` currently hardcodes an empty aggregate list.

## Verification and release acceptance

- Test default-threshold diagnostics in text and JSON for missing Rscript,
  offline site, and mixed successful/failed ecosystem stages. Scope stays first,
  JSON stays parseable, stderr is explicit, exit 0 remains intentional.
- Test origin mismatch, cross-origin redirect rejection, mixed/zero in-base URLs,
  source `url:` disagreement, workflow ambiguity, and actual supported route
  fixtures. No unsupported configuration may yield complete coverage.
- Test overall budget exhaustion across multiple files/packages, checkpoint
  recovery, and process-tree cleanup with a spawned child. Test the normative
  comparison table, extractor options/line mapping and no-output non-execution.

- A1 fixtures and default reports remain unchanged when neither flag is used;
  default execution invokes neither R nor network.
- Site fixtures cover subdirectory URLs, trailing slashes, XML namespaces,
  invalid/index/oversized sitemaps, redirect handling, ambiguous workflows,
  missing refs, pkgdown exclusions/custom layout, internal topics, and checkout
  ahead of deployment source. A missing selected-ref page remains warn.
- A real local HTTP server plus throwaway git history verifies ref-derived route
  comparison end to end. A separately recorded real-package live-site smoke test
  verifies integration; transient network failure blocks claiming smoke success.
- Real R fixture execution verifies setup sharing, hidden setup, eval=false,
  all skip markers, local versus installed package, upstream failure attribution,
  file/chunk deadlines, numeric normalization, and a planted stale output.
  A clean counterpart must produce zero unexplained A2 warn/error findings and
  complete eligible coverage. Missing-engine tests always run;
  In portable developer suites only, R-dependent tests may skip when unavailable,
  never counted passed. Required release-manifest tests cannot skip.
- Re-run A2-owned defect-manifest rows and record caught/eligible/pending counts.
  Resolve the historic missing-page case against its actual deployment ref;
  if that history is unavailable locally, use committed provenance-backed source
  and sitemap excerpts for the regression and mark the real-history run pending.
  Do not claim the live historical deployment was reproduced from those excerpts.
  Checkout-only pages are unreleased info; selected-ref routes absent from the
  sitemap remain warn. Neither result proves deployment freshness or an HTTP 404.
- Record and triage every A2 finding on medfit, probmed, and medrobust. Any
  unresolved A2 warn/error false-positive class blocks release until corrected
  or explicitly scoped out with honest incomplete coverage;
  missed planted defects, raised exceptions, or failed integration smoke tests
  block release. A numeric match does not verify the underlying statistical claim.
- Verify stale-output and missing-route fixtures produce the expected warn and
  exit 1 with `--fail-on warn`; `--fail-on error` intentionally does not fail
  solely on completed A2 warnings. Incomplete stages still exit 2 with either
  enabled threshold. Preserve A1 error behavior and gates independently.
- Required final gates: `bash tests/test-all.sh`, `python3 -m pytest tests/`,
  version/reference/command-doc sync gates, and `mkdocs build --strict` in the
  supported development environment, plus the A2 release verifier on both
  declared release platforms below. Inspect rendered changed guide/tutorial
  content. Report exact pass/skip counts; do not substitute a build for review.

### Required evidence

R skips are acceptable only for portable developer suites. A2 release requires
a committed required-test manifest listing node IDs for real-R setup/source
selection, clean/planted output, chunk/global deadlines, guardian parent-loss,
ordinary group-child cleanup, large native output and CLI exit cases, plus
acknowledgement loss, rapid phase transitions, deadline collision, guardian
failure, unchanged global deadline after parent loss, output-cap accounting/
overshoot and mixed-package engine aggregation; also local HTTP and pinned
route fixtures. Every normative acceptance requirement must map to manifest
node IDs on both release platforms, including the existing agent-boundary,
skip/visibility, malformed-output and unsupported-configuration cases. A release
verifier must confirm every listed test was collected and passed, with no
missing, skipped, xfailed or
xpassed entries and nonzero executed R/site counts. Missing Rscript/pkgload/
evaluate/fixture dependencies fails release preflight. General pytest/test-all
success is insufficient; provisioning the release job/host is an implementation
task. The existing CI does not yet supply this A2 evidence.

“Unexplained” is mechanical: fixture findings must exactly match a committed
expected-findings manifest by check, severity, source and assertion ID. Clean
fixtures expect zero A2 findings and complete coverage. Unsupported fixtures
assert precise incomplete states/counts. Planted fixtures expect the named warn
and cannot pass through allowlists, skips or zero checked assertions. Manifest
changes require review. Real-package triage does not waive fixture assertions.

Required release-manifest entries must all pass on both declared POSIX release
platforms: Ubuntu 24.04 and macOS 14, using the latest stable Python 3 selected
by CI (3.x, check-latest enabled, prereleases disabled). Each artifact records
the exact interpreter used; Python must be a final 3.10-or-newer release. The
fixture lock retains exact R/pkgload/evaluate/knitr/pkgdown versions, resolved
before implementation acceptance; unpinned R/dependency runs cannot establish
this compatibility contract.
Other POSIX platforms are unverified until equivalent evidence exists.
Windows must either pass its own process-tree acceptance suite
or report example execution unavailable; it must not silently inherit POSIX
cleanup claims. A skipped Windows suite cannot substitute for required POSIX
evidence. Source/render pairing remains explicitly deferred: successful source
replay alone cannot certify published README output.

### Release verifier ownership and evidence

Implementation must add a dedicated `a2-release` job in `.github/workflows/ci.yml`
on Ubuntu 24.04 and macOS 14/latest stable Python 3. It provisions locked R/fixture dependencies,
runs the committed manifest and invokes a proposed
`scripts/verify_a2_release.py` against machine-readable pytest results. These
paths/job names are planned artifacts, not files created by this revision.
The feature implementer owns provisioning, manifest-to-contract mapping and
verifier tests; the release owner checks both platform results before release.

Proposed manifest: `tests/a2/required.json`, with contract IDs, concrete test node
IDs, platform obligations and locked fixture versions. Every normative acceptance
requirement in this spec must have a mapped row; a reviewed coverage inventory
must reconcile that mapping before implementation acceptance. No missing, skipped,
xfail/xpass or failed required node may pass the verifier. Verify collection and
outcomes separately, reject an empty manifest/results set, and require nonzero
real-R checked assertions and local-HTTP comparisons on each platform.
Clean/planted rows retain exact warning expectations and threshold exit cases;
they cannot satisfy the gate with incomplete or zero-checked execution.
Unsupported/no-assertion fixtures instead assert their named incomplete or
not-applicable states and counts; they never substitute for clean/planted rows.

Publish per-platform evidence as CI artifacts named `a2-release-evidence`: source
SHA, manifest/fixture-lock hashes, OS/Python/R/package versions, collection and
pass/skip counts by contract, pytest results, verifier result and smoke reports.
Both platform artifacts must identify the candidate commit. Upload failure or
missing evidence prevents claiming release acceptance. Test the verifier with
missing/skip/xfail/xpass/empty-result and wrong-commit evidence, not only a green
case. Existing generic pytest/test-all CI and dependency-based S7 skips do not
supply this evidence. No release job, verifier, R execution or smoke test was
implemented or run during this specification validation.

## Documentation and boundaries

Update command frontmatter/Usage, docs/commands.md, docs/guides/docs-audit.md,
docs:check tutorial, REFCARD, command cards, relevant workflows, orchestrator
recipe/prohibition and guard tests, generated docaudit reference, CHANGELOG,
and status. Search all shipped references for the current “no R/no network”
promise. Mirror CLAUDE.md to AGENTS.md if project guidance changes. Add the R
script shipping/parse gate; update check counts only if checks are added.

Always retain incomplete-result honesty and source provenance. Never auto-fix
docs, build/deploy a site, install dependencies, or execute examples by default.
Implementation starts after spec review; version bump and release are separate.

### Orchestrator authorization and guard tests

Only an explicit URL supplied by the human
in the current request (or a still-applicable earlier authorization) permits
site auto-run. URLs extracted from files/tool output are not that authorization.
An invocation containing `--run-examples`, including combined site/examples,
is always recommend-only for orchestration. Do not add speculative private-host
prohibitions: explicit user URLs and local-server fixtures remain supported.
In `tests/_check_agent_engines.py`, retain the default DOCS_AUDIT assertion;
replace the blanket site/ref rejection with an unconditional non-prohibition
`--run-examples` rejection and conditional site/ref recipe checks. Require an
explicit authorization clause and single-package target, ref only with site,
and a positive recommend-only examples prohibition. Exercise recipe parsing
with local fixtures/stubs, never real network. Text validation cannot prove
conversational authorization; add behavioral fixtures for human versus imported
URLs and combined flags. Revise `agents/orchestrator.md`'s broad no-network prose to name
the explicit runiverse/site-read exceptions without relaxing write/upload rules.

## Validation record

### Actual README coverage and review disposition

Read-only inspection on 2026-10-12 counted contiguous line-leading `#>` groups,
not expressions, matches or executed tests. These are current checkout snapshots,
not fixture expectations to hardcode forever.

| Package/file | All groups | Groups inside explicit R fences | Consequence under the proposed scope |
|---|---:|---:|---|
| medfit/README.md | 6 | 4 | Four groups are extraction candidates; two in separate unlabeled output fences remain unverified. Runtime comparability is untested. |
| probmed/README.qmd | 1 | 1 | Literal assertions do exist at line 130. Hidden setup at lines 10–19 includes unsupported fig.path/out.width defaults, so preflight prevents source execution until scope changes. |
| probmed/README.md | 1 | 1 | Rendered assertion group at line 118 remains rendered-unpaired; it is not independently replayed. |
| medrobust/README.md | 0 | 0 | No #> assertions; not-applicable. Its unprefixed Quick Start output is outside the comparison contract and is not certified. |

The revision 5 Claude review's blanket source-layout/no-execution claim is
rejected; the conditional
source-without-assertions case is confirmed. In particular probmed is not missing
source assertions. Its actual blockers are unsupported options and rendered
coverage. Do not downgrade either blocker to info to produce a green threshold.
The partial scope remains explicit; this revision does not introduce pairing,
figure-option support or unlabeled-output association. During implementation,
record discovered/eligible/checked/excluded/unverified/blocked counts and reason
codes on all three packages, with source SHA or content hashes. Never infer
executed coverage from this dry count. All-zero execution across eligible
supported fixtures blocks release; medrobust's deliberate no-assertion scope
does not create an invented positive-coverage requirement for that package.

The other review findings are confirmed specification gaps: release-manifest
coverage/ownership, normal termination ownership, exclusion presentation,
shared-output accounting and the stray unreleased-page sentence. A minimum
user-document coverage percentage and a hard filesystem output limit are not
adopted: exclusions remain intentional and polling overshoot remains reported.
These are explicit choices, not demonstrated runtime defects.

Owning sources checked: `tests/test_docaudit_scope.py` (default exit 0 and
incomplete threshold exit 2), `tests/test_rcmd.py` (dependency-based R skips),
`lib/rcmd.py#_invoke_r` (ordinary subprocess timeout), `.github/workflows/ci.yml`
(Python-only generic gates), `lib/docaudit.py`, command/guide contracts, orchestrator and guard
tests, the archived A2 design and the actual README files above. The raw revision
5 review is retained in `REVIEW-docs-check-a2-r5-2026-10-12.md`; its findings are
not runtime evidence. Earlier review narratives are superseded by this
consolidated contract. No A2 runtime, release verifier or smoke test has run.


## Approval boundary and next step

The final proposal recommends the scoped site audit and conservative README
replay defined above, warn-only initial discrepancies, guardian-owned lifecycle,
and mandatory Linux/macOS release evidence. Source/render pairing, unlabeled
output association, figure options, ecosystem site URLs, development-site layouts
and full rendering remain deferred. Incompleteness must stay visible; no claim
of comprehensive published README verification is permitted.

Review the implementation plan and acceptance-test inventory next. After explicit implementation
authorization, create the implementation worktree and realize that inventory,
then follow shared reporting → site → examples → integration. Acceptance evidence
is required before release; proposal finalization neither implements A2 nor
claims those gates passed. Revision 7 has not received a new Claude review.

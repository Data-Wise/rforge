---
name: rforge:docs:check
description: Audit documentation content against the package API — calls and signatures in README/vignettes that no longer match the exports
argument-hint: "[package] [--detailed] [--eco] [--since <tag>] [--fail-on none|warn|error] [--site URL] [--ref REF] [--run-examples] [--examples-budget-seconds N]"
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
  - name: site
    description: Explicit single-package HTTP(S) base URL; compare sitemap with local deployment-source ref.
    required: false
    type: string
  - name: ref
    description: Local deployment-source ref; requires --site. Never fetches.
    required: false
    type: string
  - name: run-examples
    description: Opt in to supervised working-tree R replay of supported root README transcripts.
    required: false
    type: boolean
    default: false
  - name: examples-budget-seconds
    description: Positive total example-stage budget; requires --run-examples.
    required: false
    type: string
    default: 300

---

# /rforge:docs:check - Documentation Content Audit

Checks what the docs *say* against what the package *exports*. The default is static and read-only: no R, network or source writes.
Opt-in site checks read a sitemap; example replay executes package/README code
in supervised temporary sessions. Replay is not a security sandbox. It reads `man/*.Rd` usage, `NAMESPACE`, and the R code and inline calls in `README` and `vignettes/`.

## Process

```bash
python3 -m lib.docaudit --path "<package-or-dir>" --format json
```

Map the flags straight through: `--detailed` → `--detailed`, `--eco` → `--eco`, `--since <tag>` → `--since <tag>`,
`--fail-on <level>` → `--fail-on <level>`, `--site URL` → `--site URL`,
`--ref REF` → `--ref REF`, `--run-examples` → `--run-examples`,
`--examples-budget-seconds N` → `--examples-budget-seconds N`. Omit `--path` to use the current directory (the module itself must be run from the plugin/repo root, so pass `--path` unless you are already there). Read the JSON; render the
text form with `python3 -m lib.docaudit ...` (no `--format`) when the user wants the plain report.

For a strictly single-package Python invocation, add `--package-only`: it
prevents hybrid/manifest expansion and conflicts with `--eco`. The existing
Claude command's default scope semantics are unchanged.

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
- The text report ends with `NOT AUDITED` or `INCOMPLETE` in those two cases instead of `no findings`; the JSON
  carries `audited` and `incomplete`. `status: ok` does not mean clean when either is set.
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

## Optional site and README stages

```bash
/rforge:docs:check --site https://example.org/pkg/ --ref origin/main
/rforge:docs:check --run-examples --examples-budget-seconds 300 --fail-on warn
```

The site URL requires one package; --ref requires --site. Only bounded sitemap
GETs and local immutable-ref inspection occur: no fetch, crawl, build or deploy.
Missing selected-ref routes are warn even when the checkout is ahead; unreleased
checkout routes are info. Missing from a sitemap does not establish HTTP 404 or
current deployment SHA. Cross-origin and HTTP-to-HTTPS redirects require a new
invocation with the caller-selected canonical URL.

Example replay loads the working tree using pkgload/evaluate. Closed explicit R
README fences execute in document order with hidden setup retained; eval=false,
skip markers and installation chunks do not execute. Unsupported options stop
preflight. Source/render pairing, figures and unlabeled output are outside scope.
Asserted rendered markdown remains unverified when a source is selected, even
when source replay succeeds. No eligible assertions means no setup execution.

Read each stage's discovered/eligible/checked/excluded/unverified/blocked counts.
Completed stale numeric output is warn: --fail-on warn exits 1; --fail-on error
alone does not gate that warning. Any incomplete stage exits 2 with either
threshold. Default none remains diagnostic exit 0 with explicit INCOMPLETE/stderr
notices. Allowlists suppress findings, never incomplete coverage or execution
restrictions. Source-less sitemap extras are outside file allowlists.

Replay has a total default 300-second budget across packages, a 300-second file
cap and a 60-second chunk cap. An independent guardian owns ordinary process-group
termination; detached children and total host loss remain outside containment.
The host must allow budget plus 15 seconds for cleanup/reporting. If host lifetime
is unknown, recommend a terminal invocation. With a shorter known host limit,
reduce the requested budget to leave the 15-second reserve or recommend the
terminal. Poll/yield timeouts are not host lifetime limits. Missing stdout after
a killed wrapper means interruption, never a clean audit or recovered JSON.
Any examples/combined invocation
is recommend-only for the orchestrator. Site-only auto-run needs a current or
still-applicable human-supplied URL; URLs discovered in files/tools are not permission.

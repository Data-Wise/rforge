# Check evidence and approval decisions

!!! tip "TL;DR (30 seconds)"
    A successful check supports a bounded technical claim. It does not prove
    scientific assumptions, recover missing historical evidence, or authorize
    release, deployment, submission or merge. Track evidence and decisions separately.

## Three questions to answer separately

| Question | Record | Who can resolve it? |
| --- | --- | --- |
| What was verified? | Source, checks, coverage and logs | Evidence reviewer |
| What remains unknown? | Evidence gaps and unchecked claims | Evidence owner |
| What is approved? | Decision, date and conditions | Authorized owner |

Accepting a disclosed limitation is a scope decision. It does not turn an
unverified assumption or missing record into a verified fact. Use wording such
as **"accepted as bounded scope; still unverified"** when that is the decision.

## What Rforge checks establish

### Package checks

A completed package check requires the structured result and actual inner check
statuses. Report errors, warnings and NOTEs with the retained logs, rather than
using the outer process exit alone. See [Codex checks](codex-checks.md) and the
[check engine reference](../reference/rcmd.md) for the supported contracts.

A successful check establishes the outcome of the checks that ran on that
source and environment. It does not independently establish statistical
calibration, estimator correctness outside tested cases, or publication readiness.
Warnings and skipped tests need their own disposition; they are not silently
cleared by an otherwise successful command.

### Documentation checks

A static documentation audit covers the selected scope and the signatures it
can inspect. Report checked-versus-total coverage and any incomplete status.
New-export coverage requires an explicit comparison reference. A clean static
audit does not mean examples ran, a website built, or rendered pages were read.
See the [documentation audit guide](docs-audit.md).

### Builds, CI and deployed pages

Associate CI with its exact head and run. Passing checks on a preceding commit
do not certify later commits. Identify pending jobs separately from completed
ones, and distinguish configured checks from checks actually required by branch
protection.

A local site build supports a build claim. A successful deployment supports a
deployment claim. Inspect the served page before claiming its visible content
is correct. Report local, pushed, merged, deployed and visually inspected states
separately; none implies all the others. See the [website guide](website.md).

## Scientific and historical evidence

For statistical software, separate software-check results from the evidence
needed for a scientific claim. For example:

- A conditional theorem can be correct while its assumptions remain unverified
  for the procedure actually used.
- A recorded requested number of imputations does not establish the effective
  count if an error path can return fewer completed datasets.
- Finite estimates and convergence flags do not establish that a fallback was
  absent. Missing fallback records establish neither occurrence nor absence.
- A retrospective transformation can be algebraically exact under stated
  prerequisites while historical records leave those prerequisites unverified.

These are examples of reasoning boundaries, not additional checks implemented
by Rforge. Do not rerun studies, rewrite historical results or add provenance
fields retrospectively just to make a status report look complete.

## A closeout record reviewers can assess

Keep one owning status register and link to supporting receipts. A concise
entry can use the following structure:

```text
Verified: source <commit>, checks <commands>, scope <coverage>, logs <paths>.
Unverified: <specific scientific assumption or historical evidence gap>.
Owner decision: <pending, or named acceptance with date and conditions>.
Evidence status after acceptance: still unverified unless new evidence supplied.
Editorial approval: <revision reviewed>; factual declarations reconfirmed <date>.
External action: <separate authorization and current exact-head checks>.
```

Historical approvals remain historical evidence. They do not establish that
time-sensitive declarations are still true, or approve later revisions. An
owner should confirm current facts separately from approving the prose that
states them.

## Reviewing an automated or model-generated assessment

Read its coverage and skipped files before adopting findings. A reviewer that
stopped before an approval-history entry cannot establish that approval never
occurred. A skipped source or numerical trace is a coverage limit, not proof
that its claims are wrong.

Preserve the raw assessment and record which findings were confirmed,
qualified or dismissed, with source anchors. Do not automatically resume a
review or broaden its scope to manufacture a clean verdict.

For session status updates, use the [session boundary guide](session-boundary.md).
This guide adds reporting guidance; it adds no new command, automatic gate,
scientific certification or authorization workflow.

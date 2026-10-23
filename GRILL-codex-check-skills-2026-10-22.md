# Grill: personal Codex check pilot

Status: all six findings repaired in adapter 0.1.1 and shared engines.
Local regression and real fixture verification pass; fresh-session acceptance
remains.

## Review and contract

Used agent-skills doubt-driven-development: a fresh-context agent review,
then the user-approved Codex CLI review. The CLI used gpt-5.6-sol, an ephemeral
session, and a read-only sandbox. Its input contained the adversarial prompt,
contract, spec, and two skills, without prior findings or session reasoning.
Gemini was unavailable in PATH. The first outer-sandbox startup failed; the
same approved invocation completed outside that sandbox, retaining the inner
read-only sandbox. Existing login and environment were unchanged.

Contract: a small personal adapter in the existing Rforge repo, reusing local
engines, preserving package scope, and distinguishing implementation from
runtime
acceptance. No second GitHub repo, duplicate engines, new hooks, or full
command port.

## Reconciled findings

All six initial findings were valid and actionable. The descriptions below
record the pre-repair evidence; their current dispositions follow. Engine
behavior was inspected directly;
review severity labels are not treated as proof. No finding was dismissed as
noise.

1. **Blocker: false-clean package output.** `lib/rcmd.py` parses unrecognized
   R output through `console_fallback`, then normalizes it without preserving
   structured-output provenance. A mocked R invocation returning unrecognized
   text and exit zero produced `status: ok` with empty check findings. The
   same happened for valid empty JSON findings. This establishes an engine
   limitation, not a real R-package check. Instruction-only changes cannot
   reliably recover lost provenance. A small existing-engine fix is needed;
   do not certify package-check success before it is addressed.
2. **Missing check logs.** `lib/rsnippets.py` emits check errors/warnings/notes;
   `lib/rcmd.py:normalize` exposes no check-log location. The skill/spec promise
   exceeds the current engine. Preserve and expose a real log when available,
   or explicitly report unavailable log evidence. An adapter JSON report must
   not be represented as the R check log.
3. **Default check differs from Claude.** `commands/r/check.md` defines the
   ordinary workflow as an `--as-cran` pass. The Codex skill's default omits
   that flag, and the Python CLI defaults it off. Align the skill's ordinary
   check with the documented Rforge default; honor an explicit plain-check
   request.
4. **Strict orchestration is missing.** Passing `--strict` to `lib.rcmd` adds
   `--run-donttest` to one check; it does not orchestrate the documented
   Suggests-withholding flavor passes. Spell out the existing flavor calls
   and incoming behavior in the skill, with separate results and run cost.
   Do not describe raw flag pass-through as full workflow parity.
5. **Docs scope can expand.** `lib.docaudit.resolve_scope` expands hybrid roots
   and manifest directories without `--eco`. Preflight the actual resolver
   before auditing; require explicit broader scope or report the unsupported
   single-package case. Reporting expansion afterward is insufficient.
6. **New-export coverage requires a ref.** `audit_package` computes coverage
   only with `--since REF`. A natural-language new-export request needs a
   supplied or established comparison ref; otherwise report coverage omitted.
   Checked-versus-total signature coverage is a different measurement.

## Smallest repair plan

Keep the same-repo architecture. First fix lost package-output provenance in
`lib.rcmd` with a focused regression test; decide actual log availability from
`rcmdcheck` before promising a path. Then correct the two skills' default,
strict orchestration, scope preflight, and comparison-ref instructions. Reuse
existing engines and flavor selectors; do not add a wrapper or new service.

This proposes a narrow exception to the original unchanged-engine constraint:
existing-engine safety/evidence repairs, not a replacement engine. The user
authorized and implementation completed this narrow exception.
A fresh repair review and local tests completed first. The delayed user
selection then authorized the additional CLI second opinion recorded below.

## Repair dispositions and verification

1. Structured JSON provenance and schema are required; outer and inner check
   failures cannot pass. Null fields, empty output, and missing incoming slots
   found by the repair review are now rejected with regression coverage.
2. Explicit persistent check directories retain actual logs; emitted paths are
   verified against existing completed `00check.log` files.
3. Skill default now includes `--as-cran`.
4. Skill orchestrates labeled depends/suggests passes and incoming when
requested.
5. New opt-in `--package-only` guards scope before discovery; legacy defaults
stay.
6. Skill requires an established coverage ref and distinguishes signature
counts.

Final checks: 920 pytest passed, 4 skipped; 47/47 repository gates; strict
MkDocs,
frontmatter validation, and changed Markdown lint passed. Real isolated R
fixtures completed ordinary, both strict, and incoming checks with five retained
logs, zero errors/warnings, and expected new-submission NOTEs. Clean and
deliberately
broken docs fixtures produced the expected scope/counts/findings; details in
spec.

Installed 0.1.1 matches source in all four files. Both skill names appear in
this
session's catalog, but fresh-session 0.1.1 loading and a real user package
remain
unverified. The unused standalone scaffold remains inactive and unregistered.
Retain the worktree-backed catalog until integration and durable registration.
No push, PR, merge, release, or website deployment occurred.

## Additional approved CLI review (2026-10-22)

The user selected the delayed optional second opinion and confirmed the exact
command. Codex CLI 0.163.0 used the configured gpt-5.6-sol model, ephemeral
session, and read-only sandbox. Its prompt contained only the adversarial review
instructions, contract, committed engine/test diff, spec, and two skills.
Outer-sandbox initialization failed; the same approved command ran with that
outer restriction lifted, retaining the reviewer's read-only sandbox.
Local connector warnings occurred, but the CLI completed its source inspection
and mocked-output probes. This was not another real R package run.

Three findings were reconciled against the actual artifact:

1. **Missing logs accepted as complete — contract misread.** The review prompt
   overstated mandatory log availability. The installed skill explicitly says
   to verify reported paths and report an empty/missing log as unavailable.
   Check completion and log availability are separate: no file may be invented
   or described as retained without inspection. Preserve this small design;
   do not introduce filesystem log validation into every mocked engine result.
   The earlier five real completed logs remain direct retention evidence.
2. **Outer process failure with incomplete false — valid/actionable, repaired.**
   The probe reproduced valid arrays and inner status zero with outer exit 1:
   status error but incomplete false. Include the outer code in incomplete and
   strengthen the regression assertion. This was already a failure result;
   the repair makes its completeness signal consistent.
3. **Unintended tarball-check change — valid/actionable, repaired.** Restrict
   the new nonzero/inner-status rule to kind check. Preserve the preexisting
   tarball timeout rule and other tarball behavior; tarball hardening is outside
   this pilot and has not been certified here.

Reconciliation uses local regression tests, not a claim that the CLI reviewed
its own subsequent repairs. No further external review invocation is implied.

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

## Medfit installed-skill verification (2026-10-22)

Fresh ephemeral Codex session discovered and followed both installed 0.1.1
skills using this pilot engine. Target: medfit checkout dd42073d18bc0463f31a1a0e1d469117689b5b28,
DESCRIPTION version 0.10.0. Read-only session completed the docs audit but
blocked R temporary-file creation. Authorized rerun with temporary-file access
completed the default --as-cran check: status ok, structured JSON,
incomplete false, inner exit 0, zero errors/warnings/NOTEs. Retained actual
00check.log ended with * DONE and Status: OK; tests and PDF manual passed.

Latest published non-draft/non-prerelease release verified via GitHub:
v0.12.0 (local ref e89428295af0abe8dcf41642696c65097dcd1f09).
Static audit used --package-only --since v0.12.0: audited true,
incomplete false, zero findings, checked 11/22 exports; 11 variadic exports
unchecked. New-export set is empty, so there were no new exports to assess.
This older checkout result does not certify the current release or exercise
positive new-export detection; the earlier defect fixture covers that behavior.

Evidence: /private/tmp/medfit-rforge-fresh-session.md,
/private/tmp/medfit-rforge-temp-access-check.json,
/private/tmp/medfit-rforge-release-coverage.json. Actual R log:
/var/folders/xn/dn01tdjd78q6mxfmq6c4_jqc0000gn/T/rforge-check-17587fe276d5/medfit.Rcheck/00check.log.
No package source changes; two preexisting untracked plan files preserved.
Remaining: fresh-session older/missing-engine handling remains unverified;
11 variadic signatures remain outside the audit. Integration and durable
engine/catalog relocation remain pending. No push, merge, or release performed.

## Latest-release isolated verification (2026-10-22)

Verified published release v0.12.0 and checked out exact commit
`e89428295af0abe8dcf41642696c65097dcd1f09` in detached isolated worktree
`/private/tmp/medfit-rforge-release-v0.12.0`. DESCRIPTION confirms 0.12.0.
Followed both installed 0.1.1 skill instructions with the repaired pilot engine.
This direct rerun complements the earlier fresh-session discovery evidence;
it is not a second fresh-session invocation. Both source checkouts stayed clean
apart from the original checkout's two preexisting untracked plan files.

Docs: package-only, audited true, incomplete false, no findings, checked 12/23;
11 variadic exports unchecked. Comparison against v0.12.0 itself correctly has
no new exports. Additional comparison against previous release v0.11.1 exercises
positive coverage: compare_lr is mentioned in README.md and three vignette
articles. Mention coverage does not establish example correctness.

Package check: one default --as-cran invocation, medfit 0.12.0, structured JSON,
incomplete false, inner exit 0, zero errors, one warning, zero NOTEs.
Warning: '::' or ':::' import not declared from rlang. Tests, examples including
donttest, and manuals completed. Real retained 00check.log contains * DONE and
Status: 1 WARNING. Skill reports warning honestly; package is not warning-free.

Evidence: /private/tmp/medfit-v0120-check.json,
/private/tmp/medfit-v0120-docaudit.json,
/private/tmp/medfit-v0120-previous-release-docaudit.json. Log:
/var/folders/xn/dn01tdjd78q6mxfmq6c4_jqc0000gn/T/rforge-check-65272589ca7e/medfit.Rcheck/00check.log.

Remaining gaps: medfit's undeclared rlang import; 11 variadic signatures outside
the static audit; fresh-session missing/older-engine handling unverified.
Strict/incoming flavors were verified on synthetic fixtures, not this release.
No URL/site/reverse-dependency or platform certification is implied.
Integration and durable catalog/engine relocation remain pending. Retain the
isolated checkout and logs for inspection. No source fixes or external actions.

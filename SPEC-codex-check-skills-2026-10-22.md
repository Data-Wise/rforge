# Spec: Rforge checks in Codex

Date: 2026-10-22. Status: six repairs implemented; local verification passed.
Fresh-session acceptance and integration remain pending.

## Purpose and packaging

Support Davood's frequent package and documentation checks with a small Codex
plugin inside the existing Rforge repository: `openai/rforge-openai`.
The two skills are the initial slice, not a limit or full Claude command parity.
Reuse `lib.rcmd` and `lib.docaudit`; no separate repository, wrapper, service,
or imported Claude hooks. Savant is a separate follow-up.

## Implemented (adapter 0.1.1)

- `rforge-check`: default `--as-cran`; strict requests run the existing depends
  and suggests flavors separately; incoming adds the two-pass incoming call.
  Report every pass, errors/warnings/classified NOTEs, and retained real logs.
- Check evidence includes structured-output provenance, completeness, and R's
  inner check exit statuses. Missing/malformed evidence or an unsuccessful
  subprocess cannot pass; outer failure also marks the result incomplete.
  Incoming requires exactly two integer statuses.
- `rforge-docs-check`: default `--package-only` prevents hybrid/manifest
  expansion. Ecosystem scope requires an explicit request. New-export coverage
  requires an established `--since REF`; otherwise state coverage was omitted.
  Report audited/incomplete state and checked-versus-total signatures separately.

Resolve the requested package to an existing absolute path, honor its instructions
and holds, and require Python 3.10+. Package checks also need R and engine packages.
Missing prerequisites remain unavailable; no dependency installation is implied.
Checks execute package code and retain temporary artifacts. Docs audits are static.
Neither skill authorizes submission, release, deployment, or unrelated edits.
Advanced `--changed` baseline tagging is outside this pilot.

## Verified locally

Engine: feature checkout `/Users/davood/projects/dev-tools/_worktrees/rforge-codex-checks`
on `codex/rforge-check-skills`. The default durable checkout does not yet contain
these repairs; select this pilot checkout explicitly until integration.

- Full Python suite: **920 passed, 4 skipped**. Repository gates: **47/47**.
- Both skills pass frontmatter validation and changed Markdown lint; strict
  MkDocs build passes. Generated references use Python 3.12 to avoid unrelated
  Python 3.15 signature rendering changes.
- Fresh-context review findings (null arrays, blank-output provenance, missing
  incoming status slots) repaired and covered by regression tests.
- Real synthetic R package `rforgepilot` 0.0.1 at
  `/private/tmp/rforge pilot verification/clean package`: default as-cran,
  both strict flavors, and incoming completed with inner statuses zero.
  Each pass had zero errors/warnings and one expected new-submission NOTE.
  All five real `00check.log` files survived R exit and contained `* DONE`.
- Clean docs fixture: audited true, incomplete false, checked 1/1, no findings.
  Defect fixture at `/private/tmp/rforge pilot verification/coverage package`,
  `--since HEAD`: stale `add_one(nope=1)` error and missing `new_thing` coverage
  warning, checked 2/2. Both fixture paths contain spaces.
- Scope/missing-path regressions prevent discovery sweeps. Malformed output,
  outer/inner failures, and missing/extra/null status slots cannot pass.
- Both skill names are discoverable in this session's catalog. Local plugin
  refreshed to 0.1.1; all four installed package files match source.

These are direct engine/fixture observations following the skill contracts,
not proof that a fresh Codex session loads and follows cached 0.1.1 instructions.

Log availability is reported separately from check completion. Verify every
reported file before citing it; absent logs mean unavailable log evidence.
Additional approved CLI review found one contract ambiguity and two small
implementation issues; their dispositions and repairs are recorded in the grill.
Tarball behavior is preserved and remains outside this pilot's acceptance.

## Remaining runtime acceptance

- [x] Fresh session loads both skills; R execution verified by authorized rerun.
- [x] Verified medfit checkout, honoring holds; see version limitation below.
- [x] Confirm missing/older engine is reported unavailable in fresh sessions;
      see the negative-preflight record below.

The original worktree-retention requirement is superseded by the durable
registration checkpoint below. Earlier execution records remain historical.

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

## Isolated medfit import repair verification (2026-10-22)

Branch codex/fix-rlang-import at /private/tmp/medfit-rforge-rlang-fix, based on
v0.12.0. Declared existing rlang runtime use in DESCRIPTION Imports and recorded
it in NEWS. No R function, NAMESPACE, release tag, or original checkout changed.
Default Rforge --as-cran rerun: structured JSON, incomplete false, inner exit 0,
zero check errors/warnings/NOTEs. Retained log ended * DONE / Status: OK.
Test runner separately reports FAIL 0, WARN 1, SKIP 98, PASS 5993; this is not
an assertion that every test executed warning-free. Evidence:
/private/tmp/medfit-rlang-fixed-check.json and
/var/folders/xn/dn01tdjd78q6mxfmq6c4_jqc0000gn/T/rforge-check-a78b1b0771e8/medfit.Rcheck/00check.log.

The undeclared import gap is resolved locally, not in the published release.
Other previously recorded audit/runtime limits remain. No push or merge.


## Durable integration checkpoint — 2026-10-22

PR #92 merged to dev as `fe8c8ef`. The active catalog source is the durable
`/Users/davood/projects/dev-tools/rforge/openai`; installed adapter 0.1.1 uses
that repository's engines. Pilot worktree paths in earlier evidence are history,
not current setup instructions. No adapter release/tag is implied by dev merge.
Fresh-session discovery and medfit invocation passed; missing/older-engine
fresh-session behavior and uninspected variadic signatures remain unverified.
Rforge static docs audits do not verify pkgdown, examples, or deployed resources;
web-write has separate evidence for those checks. Writing formats stay deferred.

## Missing/older-engine fresh-session verification — 2026-10-22

Two independent ephemeral, read-only Codex sessions read both installed 0.1.1
skills and used an explicitly supplied engine with a synthetic DESCRIPTION package.
All four outcomes were unavailable, never passing:

| Engine case | rforge-check | rforge-docs-check |
| --- | --- | --- |
| Missing checkout | Unavailable; no check | Unavailable; no audit |
| v2.21.0 lib archive | Fields absent; no check | Flag absent; no audit |

Older ref: `7387a05fd01b55a27a37871cab0902b2778b75ce`. Required check
fields and the docs `--package-only` flag were absent.

The older case used Python 3.13.17 for definitive help checks. The missing case
also reported default Python 3.9.6; this does not independently establish a
Python-only failure or prove no supported interpreter was installed. Neither
session substituted the default engine, installed anything, executed R, ran an
unguarded audit, or invented passing results/logs. Command transcripts were
inspected, not just final summaries. DESCRIPTION and archived engine sources
matched their originals afterward; hook `.remember` files and interpreter caches
are outside that preservation claim. Startup reported skill-context budget
warnings, but both sessions explicitly read both installed skill files.

Evidence: `/private/tmp/rforge-unavailable-verification/` contains
`missing-prompt.md`, `older-prompt.md`, both `*-events.jsonl` command transcripts
and `*-result.md` reports. Temporary evidence is local and not a durable artifact.
Session IDs: missing `01a1673a-2215-7623-aa6a-a211f6233a4d`;
older `01a1673a-4b47-7361-aca3-54a64288721a`.
This closes missing/older-engine acceptance only; paths containing spaces and
Python-only unavailability remain unverified. Static variadic-signature limits
remain. Writing formats remain deferred.

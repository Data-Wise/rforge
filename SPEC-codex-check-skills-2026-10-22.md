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
- [ ] Confirm missing/older engine is reported unavailable in that fresh session.

Retain this feature worktree: the installed local catalog points into it.
Integration and durable catalog relocation require their own authorized workflow.
No push, PR, merge, release, or live deployment is claimed.

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

---
name: review-fix-loop
description: Run an adversarial review after a phase of work, triage each finding against the source, plan the fixes, implement them, and verify the result. Use whenever the user asks for an adversarial or Codex review of a phase or commit range, says to "review and fix", "run the review loop", or wants findings checked, planned and implemented before moving on. Also use for follow-up keywords such as "re-review", "next phase review", "check the review findings", "fix the review findings". Not for ordinary single edits.
---

# Review-fix loop

This skill is its own orchestrator for one workflow: **review a phase, triage, plan, implement, verify**. It is
deliberately narrow. It is not an entry point for other work, and it adds no gate on unrelated requests.
It composes three agents under `.claude/agents/`: `adversarial-reviewer`, `fix-implementer`, `gate-verifier`.
Execution mode: subagents, run sequentially (the roles do not need to talk to each other mid-task).

## Phase 0: Intake
1. Name the phase: repository or worktree path, the commit or range under review, and the contract it must
   satisfy (spec, acceptance row, docs).
2. Do not review a moving target. If CI is running on the ref, wait; do not dispatch a new run over it.
3. Create a scratch directory and keep it for the reviewer's `TMPDIR`.

## Phase 1: Review (`adversarial-reviewer`)
Spawn it read-only with the phase, the contract files, and the scratch directory. Require executed test counts;
a review that ran nothing is recorded as **static**, and is never filed as an executed review.

## Phase 2: Triage (you, not an agent)
Check every finding against the source yourself before acting. For each, record a disposition:
- **Confirmed** — reproduced or shown from the code; goes on the fix list.
- **Rejected** — the premise is wrong, or the proposed fix does not work. Record why (for example, a
  suggested reordering that the platform makes impossible). Rejection needs evidence, not a hunch.
- **Deferred** — real but out of scope; name where it will be tracked.
Do not act on a finding because the reviewer ranked it highly, and do not drop one because it is inconvenient.

## Phase 3: Plan the fixes
Turn the confirmed findings into a short ordered list: finding, file, intended change, the test that proves it
(one that fails before the fix and passes after). Show the list to the user when a fix changes a lock, a
contract, a public behavior, or anything the user said to retain.

## Phase 4: Implement (`fix-implementer`)
Spawn it with the approved list. It edits, tests, refreshes any recorded hashes, and commits locally. It never
pushes, dispatches CI, or writes outside the repository.

## Phase 5: Verify (`gate-verifier`)
Spawn it with the commit. Local gates first. For CI evidence, read the log artifact, not the job status
(a `tee` pipe without `pipefail` reports success over failing tests). Evidence is bound to the commit SHA.

## Phase 6: Record and hand off
Record the review, each disposition, the fixes, and the gate results in the project's coverage or status
document, once, on the surface it belongs to. Then ask the user before any outward-facing step: push, CI
dispatch, PR, merge, release.

## Rules learned the hard way
- A review is evidence only for what it executed. Label static reviews as static.
- A passing job status proves nothing until you have read what it ran.
- Do not re-dispatch CI over an in-progress run on the same ref; it cancels the run.
- Scan a branch diff for secrets and personal data before the first push.
- A denied action is a stop. Report it and let the user decide; do not rephrase the same action.
- Do not weaken a test to make it pass. A test that was wrong gets a documented reason for the change.

## Error handling
If a reviewer or implementer fails, retry once with a narrower scope; then proceed without it and note the
omission. Never delete a conflicting finding; record it with its source and disposition.

## Test scenarios
- **Normal:** a phase diff with two real findings and one wrong premise: two fixes land with failing-first
  tests, the third is recorded as rejected with its reason, gates pass.
- **Reviewer cannot run tests:** the report is recorded as static and the gap is carried into the next phase.
- **Gate failure after a fix:** the failing assertion is reported; the fix is revised, not the test weakened.

# Task list — docs:check A2 revision 8

Plan: [PLAN-docs-check-a2-2026-10-12.md](PLAN-docs-check-a2-2026-10-12.md). Acceptance inventory: [ACCEPTANCE-docs-check-a2-2026-10-12.md](ACCEPTANCE-docs-check-a2-2026-10-12.md).
Status: updated 2026-10-24; T01-T07, T09-T17, T19-T21 implemented and mapped (both-platform smoke 582/582); T08 (G08 process review), T18 (D04 rendered inspection), T22 (H01/H02 candidate-bound runs) and T23 (F01/F02 final records) remain open; implementation in progress; revision 8 removes the Python pin per user authorization. This is the authoritative
checklist target under the repository's root-plan convention. Completing a task
requires its plan acceptance and verification, not merely writing its proposed tests.

- [x] T00: Prepare the implementation worktree. Dependencies: None.
- [x] T01: Establish the acceptance harness. Dependencies: 00.
- [x] T02: Preserve A1 and expose optional-stage reporting. Dependencies: 01.
- [x] T03: Resolve immutable deployment sources. Dependencies: 02.
- [x] T04: Derive fixture-proven site routes. Dependencies: 03.
- [x] T05: Read bounded canonical sitemaps. Dependencies: 02.
- [x] T06: Deliver the site CLI path. Dependencies: 03,04,05.
- [x] T07: Build the guardian handshake protocol. Dependencies: 01,02.
- [ ] T08: Enforce deadlines and observed cleanup. Dependencies: 07.
- [x] T09: Capture bounded text and durable checkpoints. Dependencies: 07,08.
- [x] T10: Select README sources and extract chunks. Dependencies: 02.
- [x] T11: Resolve literal options and preflight coverage. Dependencies: 10.
- [x] T12: Compare documented assertion output. Dependencies: 10,11.
- [x] T13: Replay a working-tree package in real R. Dependencies: 07,08,09,10,11,12.
- [x] T14: Deliver example CLI budgets and partial results. Dependencies: 13.
- [x] T15: Reconcile orchestrator boundaries. Dependencies: 06,14.
- [x] T16: Verify the shipped runtime surface. Dependencies: 13,14.
- [x] T17: Update command and generated reference contracts. Dependencies: 06,14,15.
- [ ] T18: Update tutorials and user-facing site material. Dependencies: 17.
- [x] T19: Record feature state and mirrored guidance. Dependencies: 15,16,17,18.
- [x] T20: Make the required-test verifier non-vacuous. Dependencies: 01,06,14,15,16,19.
- [x] T21: Provision both required release platforms. Dependencies: 20,16.
- [ ] T22: Run recall, package triage and site smoke. Dependencies: 06,14,20,21.
- [ ] T23: Reconcile final gates and prepare review delivery. Dependencies: 15,16,17,18,19,20,21,22.

## Checkpoints

- [ ] Reporting compatibility (T02).
- [ ] Supported site CLI end to end (T06).
- [ ] Guardian/process faults on both platforms (T09).
- [ ] Real-R replay and partial CLI envelopes (T14).
- [ ] Shipping/agent/command/rendered-doc alignment (T19).
- [ ] Required manifest, both platform artifacts, smoke/triage, full gates and review (T23).

Implementation is in progress in `codex/docs-check-a2`. The optional engines,
guardian, acceptance tests, runtime lock, release verifier and CI workflow exist.
Contract mapping review is complete: 118 spec entries, 87 groups and 435 expanded nodes.
6 groups retain explicit coverage gaps; see [coverage audit](COVERAGE-docs-check-a2-2026-10-12.md).
Actual Ubuntu/macOS release artifacts remain pending.
Unchecked tasks have not yet satisfied their complete plan acceptance.
External PR/merge/release/deployment actions are separate.

## 2026-10-23 review checkpoint

- [x] Run focused Claude adversarial review of 7eb8a40 and validate follow-up concerns: no confirmed issue; 126 focused native-process tests passed.
- [x] Replace A2 Python 3.12 pin with latest-stable selection and exact runtime provenance; update spec/ledger without removing requirements.
- [ ] Close G08, D04, H01, H02, F01 and F02 (D05 local coverage complete); see the plan for ordered actions and owners.
- [ ] Obtain actual Ubuntu/macOS acceptance artifacts and final observations after separate authorization for external actions.

Existing unchecked tasks remain unchecked because their full acceptance criteria have not been demonstrated.

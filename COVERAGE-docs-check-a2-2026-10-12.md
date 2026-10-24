# A2 contract-to-test mapping audit

Spec revision 8 applies the user-authorized 2026-10-23 Python policy amendment; all other obligations remain. Mapping review is complete; release coverage is not complete.

Mapped 118 unchanged paragraphs/table rows to 87 inventory groups and 435 actual expanded nodes. All collected A2 nodes have one semantic inventory owner; no duplicated or unowned nodes. 6 groups retain explicit gaps. Neither filename similarity nor local test success closes these gaps.

The immutable requirement ledger records exact source text/hash/anchor/ordinal plus inventory ownership. Test source hashes bind this review snapshot. Header, historical validation and approval paragraphs are contextual documentation obligations, not invented runtime tests. Actual external evidence is separate from portable validators.

## Remaining coverage work

### G08 / T08

Mapped: `tests/a2/test_group_pin.py::test_pin_holds_identity_after_workload_reap`, `tests/a2/test_group_pin.py::test_pin_retains_exited_child_without_poll`, `tests/a2/test_group_pin.py::test_guardian_crash_uses_owned_pin[False]`, `tests/a2/test_group_pin.py::test_guardian_crash_uses_owned_pin[True]`, `tests/a2/test_group_pin.py::test_pin_ignores_term_during_guardian_grace`, `tests/a2/test_group_pin.py::test_pin_stays_armed_past_deadline_until_owner_releases`, `tests/a2/test_guardian.py::test_guardian_failure_emergency_cleanup`, `tests/a2/test_guardian.py::test_no_exception_signal_after_direct_child_reap`, `tests/a2/test_guardian.py::test_live_guardian_death_emergency_owner`, `tests/a2/test_guardian.py::test_guardian_crash_after_reap_keeps_pin_owned[False]`, `tests/a2/test_guardian.py::test_guardian_crash_after_reap_keeps_pin_owned[True]`, `tests/a2/test_guardian.py::test_join_launcher_ignores_decoy_lib_in_workload_cwd`, `tests/a2/test_guardian.py::test_deadline_before_join_never_executes_workload`, `tests/a2/test_guardian.py::test_interrupt_after_launch_tracks_and_reaps_child[pin]`, `tests/a2/test_guardian.py::test_interrupt_after_launch_tracks_and_reaps_child[guardian]`.

- Parent-owned group pin integrated; native guardian death after workload reap, corrupt checkpoint PID, and parent-loss tests pass locally. Independent ownership review and both-platform execution remain pending; no actual PID-wrap reproduction is claimed.

### D04 / T18

Mapped: `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/guides/docs-audit.md-terms0]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/tutorials/fix-a-docs-check-finding.md-terms1]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/workflows/index.md-terms2]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/quickstart.md-terms3]`.

- Guide/tutorial/workflows/quickstart text checks exist; REFCARD/cards and all changed rendered-content observations remain aggregate work.

### D05 / T19

Closed locally: version/mirror gate plus `test_status_guidance_count_sync` and seven `test_agent_boundary_prohibitions` cases. Actual runner check count, active command count excluding rename stubs, unchanged feature version, current pending-group count and release hold are asserted. Both-platform acceptance remains pending.

### H01 / T22

Mapped: `tests/a2/test_evidence.py::test_committed_defect_replay`.

- Generated known-finding regressions pass; caught/eligible/pending historical replay and provenance-backed historical source/sitemap substitute not yet recorded.

### H02 / T22

Mapped: `tests/a2/test_evidence.py::test_package_coverage_triage`.

- Controlled triage file facts checked; exact all-six-count/reason/source-hash triage schema needs strengthening and candidate-bound actual dogfood refresh.

### F01 / T23

Mapped: `tests/a2/test_final_gates.py::test_gate_record_validation[missing-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[missing-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[missing-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[missing-requirement_mapping]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-requirement_mapping]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-requirement_mapping]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-requirement_mapping]`.

- Artifact hashes and minimum facts checked; actual full-gate logs/check names/source binding are not yet inspected by aggregate producer.

### F02 / T23

Mapped: `tests/a2/test_final_gates.py::test_review_record_validation`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[bare-claim]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[missing-file]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[wrong-hash]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[escaping-path]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[wrong-candidate]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[wrong-producer]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[empty-facts]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[unresolved-review]`.

- Unresolved review rejected; real finalized review coverage, complete mapping, both retrieved platform artifacts and observation producers pending.

## Execution dependency

Close the listed fixture/validator gaps and review their oracles before making required.json ready. Reconcile the independent ledger with the unchanged approved spec. Then commit a stable candidate, run the actual locked acceptance collection on Ubuntu 24.04 and macOS 14, retrieve both artifacts, and produce candidate/run-bound live, triage, full-gate, rendered-review and finalized adversarial-review observations. Only then can the aggregate gate certify acceptance. No CI dispatch, source publication, or release has occurred.


## Group-pin review disposition

Raw read-only Claude review: `REVIEW-docs-check-a2-group-pin-2026-10-12.json`,
job `1ef64607-b22b-47ab-8c5c-ec667d20501d`, against the initial pin integration.
The reviewer inspected helper/guardian bodies and searched tests; broader
contracts, inventory and complete test bodies were outside that review scope.
The result includes conflicting budget flags between the tool envelope and
reviewer's structured report; it is not a clean final acceptance review.

- Confirmed: workload-cwd `lib` shadowing executed the decoy module in the native
  red regression. Production now uses an isolated stdlib-only `-I -S` bootstrap.
- Confirmed: delaying child-side group join allowed workload execution after the
  deadline. Production now assigns membership in `os.posix_spawn(setpgroup=...)`
  before any bootstrap instruction; the bootstrap also checks the original
  absolute deadline before exec. Native delayed-bootstrap regression passes.
- Addressed locally: SIGINT between process creation and handle assignment could
  lose ownership. Launch masks defer delivery until assignment; native pin and
  guardian interruptions verify tracked children are reaped and no workload runs.
- Parent-loss ownership proof remains a review obligation. Native tests exercise
  original deadlines and missing startup release, not actual PID wrap or complete
  simultaneous owner loss. The pin must not expire while a guardian can signal.

G08 and F02 remain pending final independent review and both-platform evidence.
No acceptance requirement or approved product-spec text was relaxed.

Local post-fix verification: full pytest 1302 passed / 4 existing skipped;
focused mapping/guardian/pin 65 passed; launcher/interruption regression subset
4 passed; test-all 47/47; mkdocs strict passed. The unchanged approved spec hash
is `b202409f690b478fcb3fe6473afb4021930a1e271e8ae2a90ec0370bebe65b51`.
These local checks do not replace the seven pending acceptance groups.


## Supplemental Python 3.15 compatibility

The new local development interpreter does not replace the approved Python 3.12
acceptance pin or either required platform artifact. The reference generator now
uses public `dataclasses.MISSING` identity, preserving byte-identical generated
references across 3.12 and 3.15. Fault-injection fixtures now use the production
atomic spawn rather than the retired delayed-join launcher, and observe orphan
workload death within a bound instead of assuming instantaneous SIGKILL delivery.
The test-source hashes were refreshed; all 403 concrete node IDs are unchanged.
Python 3.12 focused lifecycle/mapping checks: 65 passed. Python 3.15 repository
gates: 47/47; strict docs build passed with Homebrew Cairo available.

Final Python 3.15 full-suite result: 1302 passed / 4 existing skipped.

## Final ownership review validation

G08 adds four concrete nodes (407 total): repeated probe failure with the parent absent, pending SIGINT at workload handoff, interruption after pin construction, and NUL-command rejection before bootstrap. The first three failed on the reviewed candidate and are repaired. The fourth already returned guardian-failure. Source hashes refreshed; seven coverage groups remain pending, including independent repair review and both-platform execution. Spec revision 7 is unchanged.

## Confirmed-gap acceptance regressions

The inventory now maps 419 unique expanded nodes across the same 87 groups.
Two guardian regressions cover a real SIGINT after pin reap, with no destructive
group signal, and handle allocation failure before spawn. Ten replay regressions
cover partial checkpoints and severity gates, preparation failure, stale lifecycle
rejection, completed lifecycle evidence plus boundary failure, and propagated
KeyboardInterrupt. Source hashes refreshed; seven pending coverage groups and
both-platform release requirements remain pending. Revision 7 and Python 3.12
acceptance pins are unchanged.

Final local Python 3.12.15 verification: 1318 passed / 4 existing skipped,
repository gates 47/47, strict docs build passed, five updated validation probes
passed. These local results do not supply either required platform artifact.

## 2026-10-23 checkpoint

Focused review of 7eb8a40 reported no material finding; 126 native-process regressions passed on Python 3.12.15. See REVIEW-docs-check-a2-7eb8a40-2026-10-23.md for coverage limits. G08/F02 remain open for broader final review and actual platform evidence. Python policy is now latest stable, with exact interpreter recorded; eight runtime evidence regressions bring the uniquely mapped inventory to 427. No group was closed by this policy change. Historical revision-7 hashes and Python 3.12 observations below remain historical records.

## D05 local coverage — 2026-10-23

Added eight expanded nodes: current status/count/version/release-hold assertion and seven agent prohibition cases. Focused docs/agent tests pass 35/35 on Python 3.15.0; full suite 1334 passed/4 existing skipped, repository gates 47/47 and strict MkDocs passed. Inventory now owns 435 unique nodes; D05 has no remaining local coverage gap. Six groups remain pending: G08, D04, H01, H02, F01, F02. The spec, latest-stable policy and external acceptance requirements are unchanged. Earlier seven-group/427-node entries are historical.

## Phase 2 Codex review disposition (2026-10-24, HEAD 146e670)

Read-only Codex adversarial review of D04 docs and a broad G08 ownership read.

- Confirmed and fixed: REFCARD/cards omitted the spec's `origin/main`, then `main` fallback when no deployment candidate exists (ambiguous candidates stay incomplete); `docs/lib-modules.md` still promised "no R" for `docaudit`. Both corrected; new nodes cover the fallback term and both lib-modules phrases (manifest hashes and D04 node list refreshed).
- Rejected as stated: moving the final PGID probe before pin release. An unreaped zombie pin keeps the group present (EPERM on macOS), so disappearance cannot be observed before the reap. A PGID reused after the reap can only turn success into `cleanup-unverified` (fails closed); no destructive signal follows pin release. Rationale recorded as a comment in `lib/_docguardian.py`. Linux behavior of the zombie-group probe is not yet observed; it falls under the Ubuntu platform run.
- The reviewer's test run could not execute (no writable temp dir in its sandbox); local runs: full suite 1362 passed / 4 skipped, test-all 47/47, strict docs build passed, Python 3.15.
- G08 remains pending: both-platform process tests and a review that actually executes them. D04 rendered inspection remains aggregate.

## Phase 3 review disposition (static review: no tests executed by the reviewer)

- Confirmed and fixed: install-chunk detection ran a regex after string removal, so dispatch (`do.call`, `match.fun`, `getExportedValue`), shell (`system2`) and attached-installer forms slipped through; `is_installation` now inspects token- and string-preserving views, with look-alike negatives pinned.
- Confirmed and fixed: tibble type rows (`<chr>`, `<dbl[2]>`) compared as bare inequality bounds; type rows now require exact equality while numeric bounds such as `<2e-16` stay `shape`.
- Confirmed, partly fixed: the triage validator accepted unknown keys, findings without `check`/`severity`, extra packages and non-README hash keys; it is now an exact-key schema. Limit: a well-formed but fabricated commit or hash cannot be detected by the validator; authenticity rests on the producer run ID plus the artifact hash.
- Manifest refreshed: 537 collected nodes (36 added), source hashes recomputed. Local gates: full pytest 1460 passed / 5 skipped, `test-all.sh` 47/47, reference generator check clean.

## Phase 4 review disposition (executed review: 101 tests passed)

- Confirmed and fixed: bool/float/string values satisfied count and exit-code checks (`exit_code: False`, `pytest_passed: True`, `47.0`) and a non-numeric value raised a raw TypeError; all counts now require a real int. Review evidence of one character passed; it now needs a written string of at least 10 characters.
- Confirmed and fixed: gate commands were not compared with the canonical commands (`true` passed); each gate's command is pinned and its flag must agree with its exit code.
- Confirmed and fixed: the producer checked cleanliness only before the gates and parsed the last match anywhere in the output; it now rechecks status and HEAD after the run and reads only the final summary line (errors count as failures, no summary is not a pass).
- Limit, not fixed: the gate and review records remain self-attested. The validator cannot re-derive counts from logs; authenticity rests on the producer run ID plus the artifact hash. Shipping and re-hashing the logs is a design change deferred to the aggregate stage.
- Deferred: mkdocs strict output directory is not retained as evidence.

## D04 rendered-site inspection (dev-time, commit-unbound)

Built with `mkdocs build --strict` on the A2 branch (strict build clean) and inspected the rendered `<article>` HTML of the eight A2-touched pages: docs-audit guide, fix-a-docs-check-finding tutorial, REFCARD, command-cards, commands, reference/docaudit, workflows, quickstart. Every expected term (`--site`, `--run-examples`, `unverified`, `sandbox`, `--fail-on error`, `INCOMPLETE`, `figure`) is present in the rendered text, no raw Markdown or admonition syntax leaked, and no internal link is broken; the tutorial renders six admonitions and five code blocks. This is a development-time inspection: the candidate-bound `rendered_review` observation (page hashes on the final commit, produced by the aggregate run) remains open.

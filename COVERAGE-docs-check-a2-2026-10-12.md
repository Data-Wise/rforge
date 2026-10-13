# A2 contract-to-test mapping audit

Approved spec revision 7 remains unchanged. Mapping review is complete; release coverage is not complete.

Mapped 118 unchanged paragraphs/table rows to 87 inventory groups and 386 actual expanded nodes. All collected A2 nodes have one semantic inventory owner; no duplicated or unowned nodes. 7 groups retain explicit gaps. Neither filename similarity nor local test success closes these gaps.

The immutable requirement ledger records exact source text/hash/anchor/ordinal plus inventory ownership. Test source hashes bind this review snapshot. Header, historical validation and approval paragraphs are contextual documentation obligations, not invented runtime tests. Actual external evidence is separate from portable validators.

## Remaining coverage work

### G08 / T08

Mapped: `tests/a2/test_guardian.py::test_guardian_failure_emergency_cleanup`, `tests/a2/test_guardian.py::test_no_exception_signal_after_direct_child_reap`, `tests/a2/test_guardian.py::test_live_guardian_death_emergency_owner`.

- Live guardian death and emergency group ownership are now reproduced; PID reuse safety remains unresolved.

### D04 / T18

Mapped: `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/guides/docs-audit.md-terms0]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/tutorials/fix-a-docs-check-finding.md-terms1]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/workflows/index.md-terms2]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/quickstart.md-terms3]`.

- Guide/tutorial/workflows/quickstart and REFCARD/cards text checks pass; changed rendered-content inspection records remain aggregate work.

### D05 / T19

Mapped: `tests/a2/test_docs.py::test_version_and_agent_mirror`.

- Version and mirror gates covered; status/count accuracy and boundary prohibitions need explicit assertions.

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

## Local checkpoint and focused review

386 expanded nodes. Full suite: 1285 passed, four existing skips; repository checks: 47/47; strict docs build passed. After strengthening UTF-8 tail-content assertions, the focused stdio/CI suite passed 27 cases. No production code changed after the full suite.

Claude job b17e1ee1-8dcb-40a8-aa07-7a2796d49377 completed: one high unresolved guardian ownership finding and two low findings. The UTF-8 oracle finding is addressed by suffix and valid-encoding assertions. CI matrix execution on normal pushes/PRs implements the approved ci.yml contract; the live main protection API reports no required status checks, so no existing check-name binding needs migration. The guardian signal path is confirmed from source; actual PID reuse has not been reproduced. Proposed remediation is a parent-owned process-group pin, with Python >=3.10 compatibility, guardian-death, parent-loss, and bounded cleanup tests required before adoption. Start-time comparison alone is rejected as incomplete because it leaves a check-to-signal race.

The raw review records skipped checkpoint implementation and planning/evidence files, medium uncertainty, Sonnet request/effective claude-sonnet-5-5, 9 turns, 203563 tokens, $0.2086217, 65697ms, and no cost/turn/Evidence Lease exhaustion. It is not final A2 acceptance. No automatic resume, model chain, or budget expansion occurred.

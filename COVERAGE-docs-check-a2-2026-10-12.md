# A2 contract-to-test mapping audit

Approved spec revision 7 remains unchanged. Mapping review is complete; release coverage is not complete.

Mapped 118 unchanged paragraphs/table rows to 87 inventory groups and 382 actual expanded nodes. All collected A2 nodes have one semantic inventory owner; no duplicated or unowned nodes. 10 groups retain explicit gaps. Neither filename similarity nor local test success closes these gaps.

The immutable requirement ledger records exact source text/hash/anchor/ordinal plus inventory ownership. Test source hashes bind this review snapshot. Header, historical validation and approval paragraphs are contextual documentation obligations, not invented runtime tests. Actual external evidence is separate from portable validators.

## Remaining coverage work

### G08 / T08

Mapped: `tests/a2/test_guardian.py::test_guardian_failure_emergency_cleanup`, `tests/a2/test_guardian.py::test_no_exception_signal_after_direct_child_reap`, `tests/a2/test_guardian.py::test_live_guardian_death_emergency_owner`.

- Live guardian death and emergency group ownership are now reproduced; PID reuse safety remains unresolved.

### I01 / T09

Mapped: `tests/a2/test_stdio.py::test_native_output_does_not_deadlock`, `tests/a2/test_stdio.py::test_public_diagnostics_bounded_and_json_isolated`.

- Public JSON isolation and ASCII diagnostic tails are covered; multibyte UTF-8 tail byte bounds remain unverified.

### I04 / T09

Mapped: `tests/a2/test_stdio.py::test_checkpoint_and_marker_integrity`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[None]`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[{]`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[[]]`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[[{}]]`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[{"records":[{}]}]`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[{"records":{}}]`, `tests/a2/test_stdio.py::test_invalid_checkpoint_cannot_match[{"records":[{"id":"README.md:3","text":[1]}]}]`.

- Malformed/partial/missing checkpoint no-match regressions pass; mixed valid/malformed and duplicate-record preservation need direct cases.

### D04 / T18

Mapped: `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/guides/docs-audit.md-terms0]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/tutorials/fix-a-docs-check-finding.md-terms1]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/workflows/index.md-terms2]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/quickstart.md-terms3]`.

- Guide/tutorial/workflows/quickstart text checks exist; REFCARD/cards and all changed rendered-content observations remain aggregate work.

### D05 / T19

Mapped: `tests/a2/test_docs.py::test_version_and_agent_mirror`.

- Version and mirror gates covered; status/count accuracy and boundary prohibitions need explicit assertions.

### V05 / T21

Mapped: `tests/a2/test_release_ci.py::test_both_platforms_locked_runtime`.

- Dedicated workflow_dispatch matrix exists, but approved spec additionally names a2-release under ci.yml; CI integration not realized.

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

## Consolidated local validation

382 expanded A2 nodes collected. Full repository suite: 1281 passed, four existing skips. Repository gate: 47/47. Strict documentation build passed. The live guardian-death case exercises emergency cleanup but does not prove PID-reuse safety. Malformed checkpoint input no longer raises KeyError; mixed-record preservation and UTF-8 tail byte bounds remain explicit gaps. No release readiness, platform CI, finalized review, or rendered visual inspection is claimed.

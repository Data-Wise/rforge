# A2 implementation: second Claude review

Candidate: `b881812`; base: `74824acf4a1b63d2477c342645b988018d0eedca`.

The authorized standard read-only review completed as job `2ea63ebe-6cf9-44d1-9d77-5a6de19528be`. Raw findings, coverage, session, requested/effective model and usage are preserved in `tests/a2/evidence/claude-implementation-review-2.json`. Effective model: claude-sonnet-5-5; 18 turns; 332,608 tokens; $0.2958915; 83,533 ms. No cost, turn or Evidence Lease exhaustion was reported. No automatic follow-up or resume was started.

## Validation and disposition

- **Confirmed, high: aggregate evidence authentication.** `scripts/verify_a2_release.py:90-92` accepts any truthy provenance string with a passing status/candidate. `scripts/verify_a2_aggregate.py` revalidates platform artifacts, but does not retrieve or inspect supporting files for the six external observations. The workflow accepts operator JSON as data; avoiding script injection and candidate self-reference does not authenticate evidence. The gate must verify actual supporting artifacts and their contents before acceptance; pending manifests currently prevent a release run but do not repair this latent defect.
- **Confirmed, medium: buffered output is invisible during a segment.** `lib/r/docexamples.R:58-79` obtains all evaluate results before updating payload.json. The guardian polls that file, so one long-running print loop does not expose its captured bytes until evaluation returns. SPEC lines 395-402 explicitly permit polling overshoot and exclude a memory/storage guarantee: Claude's proposed address-space guarantee is outside the approved scope. Nevertheless, incremental textual payload accounting is needed to make the shared output threshold observable during execution. Add a native print-loop regression before changing the worker; preserve event ordering, condition visibility, once-only byte counting and earlier valid checkpoints.
- **Unverified, low: emergency PGID reuse.** `lib/_docguardian.py:216-237` authenticates the current run marker, but a UUID does not establish OS process identity after guardian failure/reparenting. The review inferred this race and supplied no reproduction. SPEC lines 407-409 authorize emergency parent cleanup only after guardian failure. Investigate process-start identity and a native guardian-failure regression before claiming the risk resolved; do not introduce a historical PID killer.

Claude found no confirmed defect in the nested-package git path handling, normal leader retention through signalling, startup heartbeat, or aggregate candidate binding in the portions read. This is limited evidence, not exhaustive approval.

## Coverage and current gates

Read: guardian, R worker, verifier/aggregate/runner, CI, expected-findings manifest and part of site source selection. Skipped: README parser, facade, independent oracle producer, acceptance/requirement manifests, native tests, evidence, spec/plan/docs/commands/agent changes. No runtime tests were executed by Claude. Overall uncertainty: high.

Local full suite after the wrapper regression: **1,151 passed, 4 existing skipped**, 84.87 seconds. This is not the locked no-skip release gate. Earlier 251-node locked run and 47 repository checks remain historical evidence; current A2 collection has 252 nodes. Requirement mapping, the confirmed gate/output issues, emergency identity investigation and both actual platform artifact runs remain pending. No publication or release has occurred.

Next: fix the confirmed aggregate artifact validation and incremental captured-text accounting, add meaningful negative/native tests, then finish contract mapping and run the two-platform acceptance workflow after publication authorization.

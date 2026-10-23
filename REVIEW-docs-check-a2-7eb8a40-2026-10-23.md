# A2 repair review — 2026-10-23

Candidate: `7eb8a404d3e9fc12958a2155b0a9904c4ce23e3e`.
Scope: commit 7eb8a40 against its parent; pre-existing dirty .STATUS excluded by focus.
Raw result: [Claude review](REVIEW-docs-check-a2-7eb8a40-2026-10-23.json).

## Outcome and validation

Claude reported no findings and no material ship blocker. This is a narrow implementation review, not final A2 release approval. It examined lib/_docexamples.py, lib/_docgroup_pin.py and lib/_docguardian.py; skipped the changed tests, docs, inventory and status; ran no tests. Uncertainty: medium.

Codex independently inspected the changed tests and existing pin/reporting regressions. Python 3.12.15 native-process checks passed: guardian/replay 65/65 and group-pin/reporting 61/61 (126 total; no skips). The initial restricted run failed 40/65 because process inspection/signaling was blocked; a direct probe reported "[Errno 1] Operation not permitted: 'ps'". Required process access resolved those failures without code changes.

- Spawn/interruption follow-up: test_pending_workload_sigint_retains_direct_child_handle injects SIGINT after real posix_spawn returns and verifies the guardian retains/reaps its direct child. Allocation failure is tested before spawn. Existing constructor/guardian interruption tests also passed.
- Sparse lifecycle follow-up: replay boundary tests cover preparation failures and stale/missing terminal evidence while retaining known blocked counts. Reporting tests accept incomplete stages without complete lifecycle fields; no direct consumer failure was reproduced.
- KeyboardInterrupt: explicit regression requires propagation. The reviewer called loss of partial evidence a minor observability concern, not an actionable finding. No requirement change or catch-BaseException repair is justified by this review.

No confirmed issue requires an implementation fix. No tests, requirement ledger, acceptance inventory, runtime lock, workflows or approved specification changed. Approved spec SHA-256: b202409f690b478fcb3fe6473afb4021930a1e271e8ae2a90ec0370bebe65b51.

## Review provenance and limits

Job: e3646895-1416-4234-b475-e516ed31ef1f. Requested model: sonnet; effective model: claude-sonnet-5-5. Profile standard, effort medium. Duration 47.332s; 13 reported turns; 264300 total tokens (including cached input), 5525 output tokens; cost $0.2244203. Cost budget exhausted: false; turn limit reached: false; Evidence Lease: none, exhausted false. Budget: 12 configured maximum turns, finalize at 9, $1, 240s. Reported turn count exceeds configured maximum, but tool flags indicate no exhaustion; raw metadata retained without reinterpretation.
Session: a33155e7-8342-4961-a04c-11d4bde81308. Resume hint: claude --resume a33155e7-8342-4961-a04c-11d4bde81308. No resume or second review dispatched.

Claude recommended a quick focused follow-up on signal fault coverage, interrupt evidence and sparse lifecycle consumers. Existing tests address those checks as described above. Broader final review, seven coverage groups and actual Ubuntu 24.04/macOS 14 locked acceptance artifacts remain pending. Local focused tests do not establish either platform's release acceptance. No fresh full-suite or site build was run for this documentation-only review record. No push, CI dispatch, deployment or release.

## Subsequent user-authorized change

After this review completed, the user authorized removing the Python pin. Spec revision 8, workflow selectors, verifier checks and associated tests were subsequently updated. The Claude verdict applies only to 7eb8a40 and does not review that later policy change. Revision-7 hashes and unchanged-file statements above describe the review checkpoint before the amendment.

## Runtime amendment verification — 2026-10-23

Python 3.15.0 full suite: 1326 passed, 4 existing skips (148.10s). Repository
gates: 47/47. Strict MkDocs build passed with the installed Homebrew Cairo
library exposed through DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib. Rendered
contributor policy was inspected in site/contributing/index.html (57165 bytes);
the build contains 66 HTML pages. Targeted runtime/workflow checks: 41 passed.
All 118 obligations, 87 groups, 427 unique collected nodes and source hashes
were reconciled; required manifest remains pending. No requirement outside the
user-authorized Python policy changed. No external execution or publication.

Current Python release source: [Python 3.15.0 final announcement](https://blog.python.org/2026/10/python-3150-final-is-here/).

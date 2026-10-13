# Final A2 ownership adversarial review

Date: 2026-10-12. Reviewed candidate: `ba161ad`; base: `702f28b`.
Job: `d153322a-d03d-488f-a1b9-34855adc4230`.
Verdict: **needs-attention**. This is an inspection review, not validated findings or release acceptance.
Raw result: [complete review and usage](REVIEW-docs-check-a2-final-ownership-2026-10-12.json).

## Reported findings

1. **High — ps failure can skip emergency group kill after parent loss.** `lib/_docguardian.py:176-188`: the exception handler calls the failed liveness probe again, so group kill and child wait can be skipped before pin release.
2. **Medium — workload handle assignment is outside signal deferral.** `lib/_docgroup_pin.py:71-80`: restoring a pending SIGINT can interrupt before the helper returns its handle to the guardian; fallback group kill does not establish direct-child reap.
3. **Low — pin leak between constructor return and cleanup try.** `lib/_docguardian.py:233-241`: a narrow interruption window leaves a pin owned by a still-live parent without cleanup.
4. **Low — parent loss plus pin death leaves identity/proof gaps.** `lib/_docguardian.py:178-204`: destructive signals rely on the ownership assumption; early pin release can leave unverified survivors. Needs contract validation, including whether the failure combination is within the guarantee and whether proposed liveness checks prove identity.
5. **Low — non-OSError launch failures may look completed.** `lib/_docgroup_pin.py:32-43`: exceptions such as ValueError lack launch-error metadata. Needs reproduction at the actual spawn/bootstrap boundary; a NUL may be rejected by posix_spawn before the bootstrap runs.

No finding has been reproduced or resolved in this review turn. Severity and confidence are Claude's, not independent confirmation.

## Sound elements and limits

Claude judged the ownership design sound for in-guarantee cases and found no demonstrated parent-loss or deadline bypass. Atomic group assignment, isolated bootstrap, normal guardian ownership and parent handle assignment are the reviewed mechanisms. Simultaneous parent/guardian loss is documented outside the cleanup guarantee. This is not both-platform release acceptance.

Read: full `lib/_docguardian.py` and `lib/_docgroup_pin.py`; grep of test names in guardian/pin tests.
Skipped: approved spec revision 7, full test bodies, stdio tests, examples integration, coverage disposition, prior raw review, CI and docs.
Nothing executed. Uncertainty: medium. The requested contract/test-body scope was not completed; G08/F02 stay pending.

## Review provenance

Requested model: sonnet; effective: claude-sonnet-5-5; standard profile, medium effort.
9 turns; 213495 total tokens; 14207 output tokens; 108234 ms elapsed (107411 ms API); cost USD 0.2985635.
Evidence Lease: null; lease exhausted: false; cost budget exhausted: false; turn limit reached: false; reviewer budget_exhausted: false.
Budget: 12 turns, finalization turn 9, USD 1 soft/hard budget, 240000 ms timeout.
Session: `4654f07b-41c3-4ac4-a752-4f92dd80167b`; resume hint: `claude --resume 4654f07b-41c3-4ac4-a752-4f92dd80167b`.
Claude recommended a deep focused follow-up on ps failure, SIGINT at context exit, macOS zombie-group behavior and full fault-test bodies. No automatic resume, second review, budget expansion or fallback occurred.

Next: validate these findings against revision-7 contracts and native fault injection before deciding fixes; obtain actual both-platform evidence before acceptance.

# A2 ownership repairs: Claude adversarial review

Date: 2026-10-12. Candidate: `a41fd4a`; base: `00870da`.
Job: `d96b54e9-d020-4c89-9209-2250d153936d`.
Verdict: **needs-attention**. Static inspection only; new findings are not independently validated.
Raw result and full provenance: [REVIEW-docs-check-a2-ownership-repairs-2026-10-12.json](REVIEW-docs-check-a2-ownership-repairs-2026-10-12.json).

## Result

a41fd4a resolves the three reproduced defects on the paths I traced: parent-loss cleanup under ps failure (lib/_docguardian.py:182-194 now SIGKILLs unconditionally while the direct child is unreaped), pending SIGINT handoff (outer defer spans spawn/pin construction, handles assigned before unblock, pin construction moved inside try at :240), and original signal mask through nested deferral (explicit signal_mask threaded to GroupPin and spawn_in_group). No destructive group signal follows pin-release or direct-child reap on the traced paths. One conditional gap remains: the pre-spawn exception path SIGKILLs a PGID with no ownership anchor, so parent loss plus pin exit can hit a reused PGID. Minor gaps: post-reap probe failure, deadline overrun in cleanup, and no structured handling at the _docexamples boundary. Evidence is local macOS/static only; no both-platform acceptance and SPEC rev 7 and test_group_pin.py were not read. Conclusions are from static reading and no tests were run.

## Findings

- **medium — Pre-spawn exception path can SIGKILL a reused PGID after parent loss and pin exit** (`lib/_docguardian.py:179-181`, confidence 0.55). When process is None the handler does os.killpg(pgid, SIGKILL) with no ownership anchor. The pin exits by itself on parent loss when no startup-release exists (_docgroup_pin.py:156-159) and init then reaps it, freeing the PGID once the group is empty. A guardian exception in that window (read/atomic/ps/MemoryError) signals a PGID that may belong to an unrelated group. This is the previously unconfirmed parent-loss plus independent pin death/reuse concern; it holds only on this pre-spawn branch, since the post-spawn branch is anchored by the unreaped workload child. Inferred from code, not reproduced; narrow window. Suggested repair: Drop the pre-spawn killpg (no workload exists before startup-release) or verify the pin is still a live/zombie unreaped child before signalling. Add a test for a pre-spawn exception with the pin already gone.
- **low — Post-reap probe failure leaves no group cleanup when parent is also gone** (`lib/_docguardian.py:164-182`, confidence 0.45). A ps failure at :165 after direct_child_reaped is True goes to the handler, which skips the kill because the child is reaped. A straggler that joined the group between the :152 check and the reap survives if the parent is gone; the parent-side pin SIGKILL at :281-285 only helps while the parent lives. Terminal state is reported as guardian-failure/cleanup-unverified, so it is not silent. Suggested repair: Issue the group SIGKILL before the direct-child reap decision, or keep the pin-anchored kill before release regardless of the reaped flag. Test a single post-reap probe failure.
- **low — Cleanup waits can overrun the absolute deadline; SIGINT blocked during pin-ready poll** (`lib/_docgroup_pin.py:96-141`, confidence 0.4). The pin readiness loop runs inside run()'s outer defer so SIGINT/SIGTERM stay blocked up to 5s (bounded by ready_deadline). On timeout finish() adds up to 3s and the handler's process.wait(5) adds more; the deadline is only checked at loop heads. Bounded but nonzero overrun. SPEC rev 7 tolerance not verified. Suggested repair: Confirm against SPEC rev 7 deadline contract; narrow the blocked region to Popen only and cap cleanup waits to the remaining budget.
- **low — No structured handling of guardian.run exceptions at the production boundary** (`lib/_docexamples.py:228-233`, confidence 0.4). guardian.run is called without try/except. Launcher, atomic or KeyboardInterrupt exceptions propagate after run()'s finally cleanup, but the TemporaryDirectory removes terminal.json including cleanup_error/cleanup-unverified evidence. Cleanup claim holds; observability is lost. Suggested repair: Catch Exception around guardian.run, record a guardian-failure lifecycle in stage provenance, and re-raise KeyboardInterrupt after recording.
- **low — Test coverage gaps for new repairs** (`tests/a2/test_guardian.py:459-520`, confidence 0.6). The probe-failure test makes every ps call fail so it never exercises a single post-reap failure. The pending-SIGINT test is in-process with parent_pid=getppid(), so it does not cover real parent loss with pending SIGINT. No test covers pre-spawn killpg reuse or independent pin death. Evidence is Darwin ps path only; the waitid branch and Linux/Python 3.15 CI are not exercised locally. Suggested repair: Add tests for the pin-gone pre-spawn exception and single post-reap probe failure, and obtain Linux and macOS CI acceptance.

## Coverage and limits

Examined: lib/_docguardian.py; lib/_docgroup_pin.py; lib/_docexamples.py (lines 215-264); tests/a2/test_guardian.py (lines 455-535).
Skipped: SPEC-docs-check-a2-2026-10-12.md; tests/a2/test_group_pin.py; tests/a2/test_guardian.py (other bodies); REVIEW-docs-check-a2-final-ownership-validation-2026-10-12.md; COVERAGE-docs-check-a2-2026-10-12.md; docs/guides/docs-audit.md; CHANGELOG.md; .STATUS; tests/a2/required.json.
No tests executed. Requested spec and full native-body coverage were not completed. Uncertainty: medium. This does not clear G08/F02 or actual both-platform acceptance. The previous local 1306-pass result is separate evidence and was not rerun in this review.

## Provenance

Usage: tokens=315751 output=12487 turns=12 duration_ms=97215 api_ms=96537 cost_usd=0.2942763
Requested model: sonnet; effective: claude-sonnet-5-5; profile: standard; effort: medium.
Budget: {"max_turns": 12, "finalize_at_turn": 9, "soft_budget_usd": 1, "max_budget_usd": 1, "timeout_ms": 240000}.
Evidence Lease: null; evidence_lease_exhausted=False; cost_budget_exhausted=False; turn_limit_reached=False; reviewer budget_exhausted=False.
Session: `9d8448c7-04e0-4519-a485-e879f68ad145`; resume hint: `claude --resume 9d8448c7-04e0-4519-a485-e879f68ad145`.
Focused follow-up recommendation: {"profile": "standard", "focus": ["Pre-spawn killpg PGID reuse after parent loss and pin exit", "SPEC rev 7 deadline/lifecycle conformance", "test_group_pin.py bodies", "Linux/macOS CI acceptance"], "reason": "The medium finding and the unverified SPEC contracts and both-platform behavior warrant a focused follow-up."}.
No automatic resume, chained review, expanded budget or fallback occurred.

Next: validate the five findings against revision-7 lifecycle/deadline contracts and native fault tests, starting with pre-spawn signaling when no workload exists. Obtain actual Ubuntu/macOS evidence before acceptance. No implementation changes or release authorization follows from this report.

Validated follow-up: [contract disposition and reproducible probes](REVIEW-docs-check-a2-ownership-repairs-validation-2026-10-12.md). Original review findings are preserved above.

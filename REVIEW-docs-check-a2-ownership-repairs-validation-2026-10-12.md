# A2 ownership-repair review: validated disposition

Date: 2026-10-12. Candidate: `a41fd4a`; review-record HEAD: `95992f1`.
Review: [Claude report](REVIEW-docs-check-a2-ownership-repairs-2026-10-12.md).
No production implementation, approved spec, acceptance inventory, runtime pin or CI changes in this validation pass.

## 1. Confirmed unsafe signaling request; PID-reuse damage remains conditional

`lib/_docguardian.py:179-181` issues SIGKILL from `initial.group_pgid` when `process is None`. The native pin test `test_parent_loss_before_startup_release_has_no_orphan_pin` confirms the pin automatically exits after parent loss with no startup release. No independent pin-kill fault is needed for that loss of reservation.

The validation probe creates and reaps a real pin, supplies its expired numeric PGID as the guardian's initial value, and queues real SIGINT during the pre-release heartbeat read. The production exception handler requests `(old_pgid, SIGKILL)` despite having no workload child handle or live pin reservation. Signals are intercepted: no possibly unrelated group is killed. This proves the missing ownership guard, not actual PID wrap/reuse, a victim, or the complete concurrent parent-loss/reuse interleaving.

Claude's generic read-OSError example is weaker: `read()` already catches OSError. The decisive probe uses native SIGINT, which the guardian catches as BaseException. Revision 7 (`373-391`) forbids stale PID killing. Priority: fix the ownershipless pre-release branch. Do not use a numeric liveness probe as an identity capability. Preserve cleanup for a launch that may have created a child before a handle-construction exception; removing every pre-spawn cleanup request without distinguishing that case requires additional proof.

## 2. Post-reap survivor claim not reproduced

A real child completes in a pinned group. The first actual membership probe is false; the second actual probe is also false but is made to raise one CalledProcessError. The guardian records guardian-failure, keeps direct-child-reaped true, emits no destructive group signal and leaves no live workload member. The existing `test_no_exception_signal_after_direct_child_reap` checks the related no-late-signal rule.

Claude's claimed straggler additionally requires a membership observation that misses an in-group survivor or an external joining race. No such survivor was reproduced from a single post-reap probe failure. This is unconfirmed, not a proof that all ps snapshot races are impossible. Adding a post-reap numeric kill indiscriminately would weaken identity safety. Keep the proof gap explicit; do not mark G08 ready.

## 3. Deadline-overrun violation rejected; interruption latency characterized

Revision 7 (`319-353`, `428-450`) expressly distinguishes the execution deadline from cleanup/report overhead: two seconds TERM grace, five seconds cleanup, five seconds assembly and a 15-second wrapper reserve. Deadline crossing during bounded cleanup does not extend allowed package execution. The existing native tests cover original deadline preservation, completion collisions, parent loss, blocked children and delayed polling.

A native SIGINT queued during pin construction with a deliberately hidden ready acknowledgement is deferred until the 0.3-second startup deadline. The child is reaped and no workload starts. This verifies deferred but bounded interruption; it does not establish a hard 100-ms response promise. The code's five-second readiness cap is a possible latency tradeoff, not a demonstrated contract violation. Capping cleanup to an already exhausted execution budget would conflict with the separate cleanup allowance.

## 4. Confirmed loss of counts/lifecycle; uncaught ordinary exception claim narrowed

`lib/docaudit.py:1037-1042` already catches ordinary replay exceptions and returns an unavailable stage. The report remains incomplete and both warn/error gates return 2. Thus an ordinary exception does not escape the public audit or produce a clean release result.

The production-boundary probe starts with one known eligible assertion, writes a cleanup-unverified terminal with cleanup_error, then raises OSError from guardian.run. The public result has `counts={}` and no lifecycle provenance, and TemporaryDirectory removes the terminal. This is a concrete loss of known scope/cleanup evidence. Revision 7 (`295-307`, `373-377`, `435-441`) requires partition counts, blocked execution failures and partial/incomplete reporting. Preserve known counts and available valid lifecycle/checkpoint data before directory teardown when repairing this boundary.

KeyboardInterrupt does propagate and remove the directory; the probe confirms that behavior. The spec does not promise a recovered final report after arbitrary host/interruption loss. Preserve interruption safety without inventing successful report recovery or suppressing KeyboardInterrupt.

## 5. Coverage finding partially confirmed

Existing tests cover guardian crash, corrupt checkpoint PID, retained zombie pin ownership, native parent loss, startup pin exit, atomic workload membership, pending SIGINT assignment, post-constructor interruption, deadline enforcement and severity gates. Claude skipped most of that evidence.

There were no committed acceptance nodes for the new pre-release expired-PGID request or replay-boundary evidence loss. The accompanying probes characterize them but are not accepted regression or platform evidence. The post-reap single-failure case is now locally characterized without a survivor.

Actual Linux/Ubuntu 24.04 and macOS 14 acceptance artifacts remain absent. `.github/workflows/a2-platform.yml` is pinned to Python 3.12 on both requested platforms. `.github/workflows/ci.yml` separately includes Python 3.15; that supplemental matrix row does not change the approved acceptance pin. A combined real parent-loss plus pending-SIGINT test and actual PID-wrap scenario remain unexecuted; the absence of those combinations alone is not a new explicit normative requirement.

## Verification and reproducibility

- Python 3.12.15, local macOS: five characterization probes passed (`0.61s`). These intentionally assert current defective behavior in findings 1 and 4; passing does not mean the defects are fixed.
- Existing guardian, pin and reporting tests: 96 passed (`39.31s`), no skips.
- Approved spec SHA-256 unchanged: `b202409f690b478fcb3fe6473afb4021930a1e271e8ae2a90ec0370bebe65b51`.
- Acceptance inventory remains 407 nodes, 87 groups and seven coverage gaps. No full-suite, release-acceptance, Ubuntu execution or publication claimed in this validation pass.

Probe source: [characterization probes](REVIEW-docs-check-a2-ownership-repairs-validation-probes-2026-10-12.py).
Run from the active worktree:

```sh
PYTHONPATH="$PWD" .venv/bin/python -m pytest REVIEW-docs-check-a2-ownership-repairs-validation-probes-2026-10-12.py -q
.venv/bin/python -m pytest tests/a2/test_guardian.py tests/a2/test_group_pin.py tests/a2/test_reporting.py -q
```

Next: repair the confirmed pre-release ownership guard and replay-boundary evidence/count loss, convert the characterization cases into acceptance regression tests, then review the repaired diff and obtain both-platform evidence. The post-reap race concern stays unconfirmed.

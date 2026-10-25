# Plan: complete the personal Codex check pilot

## Decision and scope

Keep `openai/rforge-openai` in the existing Rforge repository. Reuse
`lib.rcmd` and `lib.docaudit`. The two skills are the first useful slice;
more workflows may follow. Do not create a second GitHub repository.

Current checkpoint: integrated to dev via PR #92 (`fe8c8ef`); installed 0.1.1
uses the durable Rforge checkout/catalog. Fresh-session medfit discovery and
real checks passed. Fresh sessions verified missing/older-engine rejection,
space-containing engine/package paths and controlled Python 3.9 rejection.

The skills, catalog, installation, and spec already exist. This plan records
remaining work; it does not present completed implementation as future work.
Tasks and acceptance criteria: [task list](TASKS-codex-check-
skills-2026-10-22.md).

## Sequence

1. Grill the spec and packaging decision using a fresh-context reviewer.
   Record actionable findings, accepted trade-offs, and unresolved questions.
2. Repair the six reconciled findings in the grill. Start with the smallest
   existing-engine provenance/log-evidence fix, then correct skill orchestration
   and docs scope/ref instructions. The user authorized narrow existing-engine
   repairs; no wrapper or new
   service. Refresh installed instructions after focused validation and review.
3. After a Codex restart, verify both skills on a selected R package. Capture
   invocation, package path, result, coverage/logs, and prerequisite failures.
4. If runtime acceptance passes and publishing is authorized, use feature-to-dev
   integration. Move the local catalog registration to a durable Rforge checkout
   only after the package files exist there. Verify cache/source parity before
   removing this feature worktree.

Review outcome: same-repo packaging stands. All six gaps are repaired;
920 tests and 47 gates pass. Real isolated fixtures verified both engine
contracts; installed 0.1.1 matches source. Fresh-session medfit acceptance
and durable registration passed; see the spec for the remaining boundary.

## Checkpoints

- Review: no unresolved blocking finding; existing architecture remains small.
- Runtime: every unchecked spec acceptance item has observed evidence. Missing
  prerequisites are reported as unavailable, not silently installed or passed.
- Integration: explicit push/PR/merge authorization and live checks govern each
  external step. Local success does not grant publication authority.

## Risks and constraints

- Mutable local engines can drift from cached instructions: report the source
  checkout/ref during runtime verification and recheck changed contracts.
- A worktree-backed catalog breaks if removed prematurely: keep it until a
  verified replacement exists; do not copy engines to solve this.
- Python selection matters: system Python may be too old. Resolve a supported
  interpreter explicitly; do not assume `python3` satisfies 3.10+.
- Docs checks do not prove complete API coverage or site freshness.
- Package checks execute package code; honor project holds and existing jobs.

## Open input

Missing/older-engine rejection is verified in two fresh read-only sessions; see
the spec negative-preflight and paths/Python records. Paths and controlled
Python-version rejection are verified. Static variadic limits and an unexplained
restricted-session check termination remain; missing-interpreter and invalid
package fresh-session cases were not separately exercised. Existing medfit
evidence and durable registration supersede the original planning gaps.
No new service, hook layer, distribution framework, or full command port.

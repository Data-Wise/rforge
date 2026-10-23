# Tasks: personal Codex check pilot

## 1. Review scope and contracts

Dependencies: none. Scope: spec, plan, review record.

- [x] Fresh reviewer checks the same-repo decision and skill contracts.
- [x] Findings are reconciled; six actionable repairs are recorded in the grill.

Verification: record file-specific findings and dispositions in the grill.

## 2. Close evidenced contract gaps

Dependencies: task 1. Scope: two skills, affected documentation, and an
authorized
narrow existing-engine safety/evidence repair. No replacement engine or wrapper.

- [x] Preserve structured-output provenance; regression-test malformed R output.
- [x] Establish real log availability and align the log-evidence contract.
- [x] Align default and strict check orchestration with existing Rforge
semantics.
- [x] Preflight docs scope and establish the ref for new-export coverage.
- [x] Review repaired contracts without introducing new engines or hooks.
- [x] Skills validate and changed Markdown lints; update spec/status if needed.

Verification: focused validators plus relevant existing checks. Repeat the full
suite only when behavior changes justify it. Refresh changed installed skills
and verify file parity; do not infer runtime success from a file comparison.

## 3. Runtime acceptance

Dependencies: task 2 and a restarted Codex session. Scope: acceptance evidence.
Repairs and isolated real engine fixtures pass; installation is not fresh-
session acceptance.

- [ ] Both skills discover and invoke on a selected R package, including paths
      containing spaces; recorded behavior satisfies the spec checklist.
- [ ] Docs coverage/incomplete results and real package-check logs are honest;
      invalid package and unavailable engine cases do not produce success.

Verification: record actual invocation/output and package/ref. Existing upstream
unit tests do not replace these observations.

## 4. Authorized integration and durable registration

Dependencies: task 3 and instance-specific external-action authorization.
Scope: integration state and local catalog registration.

- [x] Integrate through the repository's feature-to-dev PR workflow with live
      CI and review. No merge or release is authorized by this checklist.
- [x] Register the catalog from a durable checkout only once files exist there,
      verify enabled installation/cache parity, then assess worktree cleanup.

Verification: live integration ref and catalog location; preserve unrelated
work.

Latest-release verification: both installed skill contracts followed on isolated
v0.12.0; see spec/grill. Fresh-session discovery was verified earlier. Remaining
acceptance: missing/older engine in fresh session; package warning and static
variadic limits are explicit. Integration was subsequently authorized and completed; see the checkpoint.


## Reconciled checkpoint — 2026-10-22

PR #92 is merged to dev at `fe8c8ef`; durable registration points to
`rforge/openai`, and the installed adapter is 0.1.1. Fresh-session discovery and
isolated medfit docs/package checks passed. The import repair is integrated to
medfit dev (#296); website repair is integrated there (#297), with scoped main
promotion #298 awaiting its final CI checks. Paths-with-spaces and fresh-session
missing/older-engine acceptance are not promoted to verified by these results.
The earlier unchecked runtime group remains partial for those cases.

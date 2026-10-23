# Tasks: personal Codex check pilot

## 1. Review scope and contracts

Dependencies: none. Scope: spec, plan, review record.

- [x] Fresh reviewer checks the same-repo decision and skill contracts.
- [x] Findings are reconciled; six actionable repairs are recorded in the grill.

Verification: record file-specific findings and dispositions in the grill.

## 2. Close evidenced contract gaps

Dependencies: task 1. Scope: two skills, affected documentation, and a proposed
narrow existing-engine safety/evidence repair. No replacement engine or wrapper.

- [ ] Preserve structured-output provenance; regression-test malformed R output.
- [ ] Establish real log availability and align the log-evidence contract.
- [ ] Align default and strict check orchestration with existing Rforge semantics.
- [ ] Preflight docs scope and establish the ref for new-export coverage.
- [ ] Review repaired contracts without introducing new engines or hooks.
- [ ] Skills validate and changed Markdown lints; update spec/status if needed.

Verification: focused validators plus relevant existing checks. Repeat the full
suite only when behavior changes justify it. Refresh changed installed skills
and verify file parity; do not infer runtime success from a file comparison.

## 3. Runtime acceptance

Dependencies: task 2 and a restarted Codex session. Scope: acceptance evidence.
Blocked by the unresolved review findings; installation is not runtime acceptance.

- [ ] Both skills discover and invoke on a selected R package, including paths
      containing spaces; recorded behavior satisfies the spec checklist.
- [ ] Docs coverage/incomplete results and real package-check logs are honest;
      invalid package and unavailable engine cases do not produce success.

Verification: record actual invocation/output and package/ref. Existing upstream
unit tests do not replace these observations.

## 4. Authorized integration and durable registration

Dependencies: task 3 and instance-specific external-action authorization.
Scope: integration state and local catalog registration.

- [ ] Integrate through the repository's feature-to-dev PR workflow with live
      CI and review. No merge or release is authorized by this checklist.
- [ ] Register the catalog from a durable checkout only once files exist there,
      verify enabled installation/cache parity, then assess worktree cleanup.

Verification: live integration ref and catalog location; preserve unrelated work.

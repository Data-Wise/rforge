# Todo: docs:check content audit (release A1)

> Source of truth for task detail (acceptance criteria, files, verification): [`plan.md`](plan.md). Tick boxes here as work lands.
> Rule: no task past **Checkpoint B (the gate)** starts until the gate passes.

## Phase 0 — Foundation and harness

- [x] T1 [S] `discovery` allowlist helper refactor — direct tests first; own commit
- [x] T2 [M] Defect manifest (18 real medfit defects) + recall runner, red-first, with mutation self-test
- [x] T3 [M] Planted-defect injector + committed known-answer pair (Rd fixtures via Bash/`git show`)
- [x] T4 [S] History replayer (`replay.py replay`, read-only `git archive`, HOME isolated)

### Checkpoint A — harness live

- [ ] `pytest tests/harness -q` green
- [ ] `replay.py recall` shows every row `pending` and counts none as missed
- [ ] Mutation self-test proves the harness goes red when the audit finds nothing

## Phase 1 — First vertical slices

- [x] T5 [M] A wrong named argument is flagged, end to end (`signature-named-arg`, parsers, CLI, envelope)
- [x] T6 [M] A refcard listing with non-formal names or bad arity is flagged (`signature-names`, `signature-arity`)

### Checkpoint B — THE GATE (human; hard stop)

- [ ] Adversarial review #2 on the signature logic (multi-agent, read-only)
- [ ] History replay: ≥60 commits × medfit / medrobust / probmed; hits triaged
- [ ] `replay.py recall --scope signature` catches every eligible signature row (scannability/site rows not yet eligible)
- [ ] Planted defects in a scratch copy of the hold-out docs are caught
- [ ] Hold-out triage by the maintainer (true / false / won't-fix); precision recorded in the SPEC appendix
- [ ] No `error`-severity false positive (else demote `signature-named-arg` to `warn`, D7)

## Phase 2 — Remaining checks (parallel-safe after the gate)

- [ ] T7 [S] Scannability findings (`info`, configurable thresholds)
- [ ] T8 [M] Coverage report and `--since` (no engine enumeration)
- [ ] T9 [S] `docs.allowlist` suppression end to end (needs T1)

### Checkpoint C

- [ ] All A1 checks green; `replay.py recall --scope a1` catches every `release: A1` row (A2 rows excluded)
- [ ] `pytest tests/ -q` green

## Phase 3 — User-facing surface

- [ ] T10 [M] CLI complete and scope-correct (D0, `max_severity`, `--fail-on`, `audit_ecosystem`, formatters)
- [ ] T11 [M] `/rforge:docs:check` rewrite + `commands.md` + orchestrator row and assertion

### Checkpoint D — live exercise

- [ ] `/rforge:docs:check` run against the defect and clean fixture packages; transcript quoted for the PR body

## Phase 4 — Ship

- [ ] T12 [S] Registration gates for the new public module (`MODULES`, mkdocs nav, `lib-modules.md`, `PUBLIC_MODULES`, reference page)
- [ ] T13 [S] `test-all.sh` lines + exact check count in `CLAUDE.md`, `AGENTS.md`, `docs/contributing.md`; `lib_pytest` list
- [ ] T14 [S] Docs sweep A — stale "clean docs:check" meaning (5 files)
- [ ] T15 [S] Docs sweep B — tutorials, `commands/complete.md`, `description-sync.md`
- [ ] T16 [M] Guide, remove the unbacked `claude_md_budget` claim, "Validates" list, CHANGELOG `[Unreleased]`

### Checkpoint E — release gates

- [ ] `pytest tests/ -q`; `bash tests/test-all.sh` (exact count); `gen_lib_reference.py --check`; `version_sync.py --check`; `mkdocs build --strict`
- [ ] Harness recall report archived in the PR body
- [ ] ORCHESTRATE file and `tasks/` removed from the branch before the merge to `dev`

- [ ] T17a [M] Version bump to 2.21.0 and PRs (user-gated)
- [ ] T17b [S] Tag, GitHub release, tap sync (user-gated; ask permission for each write to the tap repo)

## Checkpoint B fixes (Codex review #3; plan: `tasks/plan-checkpoint-b-fixes.md`)

- [ ] F1 R argument matching: exact names first, then partials among remaining formals
- [ ] F4 linear paren matching, per-region work budget, replay subprocess timeout
- [ ] F2 failed audits (non-zero exit, bad JSON, `audit_failed`) raise `AuditCrashed`
- [ ] F3 a `status: firm` row whose check is missing/unimplemented fails (`lost`), never `pending`
- [ ] Gates, evidence rerun, triage sheet refresh, Codex re-review clean


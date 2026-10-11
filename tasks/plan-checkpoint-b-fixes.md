# Plan: verify and fix the Codex review #3 findings (Checkpoint B blockers)

Source: Codex adversarial review of `TRIAGE-docaudit-signature-gate-2026-10-11.md` (2026-10-11, verdict `needs-attention`, four medium findings).
Branch: `feature/docs-check-content-audit` (worktree `~/.git-worktrees/rforge/feature-docs-check-content-audit`). Nothing past Checkpoint B starts until this plan's exit criteria hold.

Rules for every task: **verify first** (reproduce the claim, record the output; if it does not reproduce, say so and stop), **red test next**,
then the smallest fix, then the focused suite. One commit per finding. Reviewers so far could only read code, so each claim is reproduced here by running it.

## Findings at a glance

| ID | Finding | Where | Severity | Why it blocks |
|---|---|---|---|---|
| F1 | Partial matching checks each named arg against all formals; R matches exact names first, then partials among the *remaining* formals | `lib/docaudit.py` `_partial_ok` / `check_region` | medium, **error-level false positive** | An unresolved false-positive class on the `error` check (D7) |
| F2 | `subprocess_audit` keeps only `findings`, so an `audit failed` envelope, a non-zero exit or a malformed envelope reads as "clean" | `tests/harness/replay.py` | medium | Replay evidence can say "0 defects" for revisions whose audit never ran |
| F3 | A `status: firm` row becomes `pending` (and recall `ok`) when its check is not implemented or the module is absent | `tests/harness/replay.py` `run_recall` | medium | The regression lock can be bypassed by removing or misnaming a check |
| F4 | The 200,000-char guard leaves quadratic scans below it (`_balanced_close` per call; `split_args` per nested call); replay subprocess has no timeout | `lib/docaudit.py`, `tests/harness/replay.py` | medium | Malformed historical docs can stall the gate |

## Dependency order

```text
F2 ──┐                      (harness: independent of the docaudit changes)
F3 ──┼──► Task 5 gates ──► Task 6 reruns + triage refresh ──► Task 7 re-review
F1 ──┤
F4 ──┘   (F4 touches the same functions as F1: do F1 first, then F4)
```

F2 and F3 are independent of F1/F4 and of each other. Do F1 before F4 (both edit `check_region` / `_calls`).

## Task 1 — F1: R argument matching [S]

**Verify.** Build a throwaway package (scratchpad) with `\usage{ f(alpha, alpine) }`, `export(f)`, `README.md` containing `f(alpha = 1, al = 2)`;
run `python3 -m lib.docaudit --path <dir> --format json`. Expected today: one `signature-named-arg` error for `al`. Also try the reversed order `f(al = 2, alpha = 1)`.

**Red tests** (`tests/test_docaudit.py`): both orders above must produce no finding; `f(al = 1)` alone stays flagged (ambiguous prefix); two args partial-matching the same formal
(`f(alp = 1, alp = 2)` and `f(alph = 1, alpha = 2)`, the second being an exact + partial on the same formal) are flagged; a partial that matches only an already-exact formal is flagged.

**Fix.** Replace the per-argument `_partial_ok` with `_unmatched_named(names, formals)` implementing R's order: (1) exact matches across the whole call;
(2) each remaining name must be a prefix of exactly one *still-unmatched* formal, which it then consumes; (3) anything else is returned as unmatched.
Only the unmatched names become findings. `...` functions stay exempt (partial matching stops at `...`, but we skip those functions entirely).

**Acceptance.** New tests green; existing partial-matching tests unchanged; `pytest tests/test_docaudit.py` green.

## Task 2 — F4: linear scans and a work budget [M]

**Verify.** Time three inputs on a one-function package: (a) a fence of `f(` repeated to 199,000 chars; (b) `f(` x 50,000 then `)` x 50,000 (deeply nested, balanced);
(c) a long argument list. Record seconds for each; today (a) is expected to exceed 5 s (Codex's probe).

**Red tests.** Each input above completes in under 2 s (use `time.perf_counter`, generous bound), and the result is still correct on small versions of the same shapes
(unclosed call ignored; nested balanced call still reports a bad named arg at the right line).

**Fix.**

1. One linear pass per region builds a `paren match` map (stack); `_calls` and `parse_rd_usage` use it instead of `_balanced_close`. Unbalanced `(` map to -1.
2. `split_args` on nested calls is O(n x depth): add a per-region **work budget** (total characters passed to `split_args`, default 2,000,000). When exceeded, stop checking that region and
   record one `info`-free message in the envelope (`messages`: "region at `file:line` skipped: too large to scan") so a skip is visible, never silent.
3. Keep the 200,000-char guard as the cheap first cut.
4. `tests/harness/replay.py` `subprocess_audit`: `timeout=120` on `subprocess.run`; a timeout raises `AuditCrashed("timed out ...")`.

**Acceptance.** The three timing inputs finish quickly; a skipped region shows up in `messages`; the harness timeout test passes with a stub that sleeps.

## Task 3 — F2: failed audits must not read as clean [S]

**Verify.** Force `read_api` to raise (monkeypatch in a scratch run of `audit_package`) and confirm the envelope is `status: warn`, an "audit failed" message, `findings: []`;
then run `replay.run_history` with an audit that returns that envelope's findings and confirm it reports `[]` and exit 0.

**Red tests** (`tests/harness/`): `subprocess_audit` (real subprocess, with `lib.docaudit.read_api` made to fail via an env-triggered hook or a package fixture that makes it raise)
raises `AuditCrashed`; a non-zero exit raises; non-JSON stdout raises; a JSON object without `findings` raises; `run_history` and `run_recall` propagate it
(`recall` row `crashed`; `replay` exits 1 with the message).

**Fix.** `audit_package` adds `"audit_failed": true` to the failure envelope (and `summary` stays `{}`); `subprocess_audit` raises `AuditCrashed` on: non-zero exit, invalid JSON,
missing `findings`, or `audit_failed`. For the failure-injection test use a package that triggers the catch-all deterministically (for example a monkeypatched `docaudit.read_api` in an in-process test, plus a subprocess test using a crafted `NAMESPACE`/`man` combination only if one genuinely raises; otherwise test the envelope parsing with a fake `lib.docaudit` stub script on `PYTHONPATH`).

**Acceptance.** No input path yields an empty findings list for an audit that did not complete.

## Task 4 — F3: locked rows cannot go pending [S]

**Verify.** `run_recall(manifest, implemented=set(), audit=stub)` on the committed manifest: confirm `ok=True`, `firm_eligible=0` (Codex's claim). Also confirm module-absent behaves the same.

**Red tests.** With `implemented=set()` or a missing module, a row with `status: firm` yields outcome `lost` and `ok=False`; a row with `status: pending` still yields `pending`;
the mutation test: remove `signature-names` from `IMPLEMENTED_CHECKS` (monkeypatch) and `recall` on a synthetic locked row fails; a misnamed check in the manifest (`signature-nmaes`) fails.

**Fix.** In `run_recall`, a row whose `status` is `firm` and whose check is not in `implemented` (or when the module is absent) gets outcome `lost` (new, counts as a failure) instead of `pending`.
`summarize` treats `lost` like `missed`. Document `lost` in the module docstring and the sheet.

**Acceptance.** The lock cannot be bypassed by removing/misnaming a check or the module; never-locked rows still read `pending` (T7's rows stay pending until their check ships).

## Task 5 — gates [S]

`pytest tests -q`; with `RFORGE_MEDFIT_PATH` set, `pytest tests/harness -q`; `bash tests/test-all.sh` (45/45 expected); `python3 scripts/gen_lib_reference.py --check`.
All with the Python 3.12 venv (system `python3` is 3.9).

## Task 6 — rerun the evidence and refresh the sheet [S]

1. `replay.py recall --scope signature` (expect caught 1 of 1; lock now fails if the check disappears).
2. History replay, 60 commits x 7 packages and 200 for medfit; expect the same findings (medfit refcard, medrobust `check_compatibility`, medsim x7) and **no audit failures**.
3. `HEAD` hold-out across the 7 packages; expect the same findings as before F1 (partial-match fix can only remove findings: diff the before/after and list any that disappeared).
4. Refresh `TRIAGE-docaudit-signature-gate-2026-10-11.md`: new section for review #3 (F1-F4: verified yes/no, fix, test), updated counts, gate boxes.
5. Update `tasks/todo.md` and the SPEC review log (findings 30-33).

## Task 7 — re-review [S]

Run `/codex:adversarial-review` again on the branch (Codex has a shell, so it can reproduce rather than read). If it is clean, Checkpoint B is ready for your triage ticks.
If it reports new `error`-level false positives, repeat this plan's loop for them; do not start T7-T9 of the main plan.

## Exit criteria

- [ ] F1-F4 each reproduced (or recorded as not reproducing) with the command and output in the sheet
- [ ] Each has a red-then-green regression test; mutation checks for F3 (removed/misnamed check) and F2 (failure envelope) go red without the fix
- [ ] `pytest tests` green, `test-all.sh` 45/45, `gen_lib_reference.py --check` clean
- [ ] Recall, history replay and hold-out rerun; differences from the previous run explained
- [ ] Codex re-review has no `error`-level false-positive or gate-bypass finding
- [ ] Triage sheet refreshed; you tick H2, R3, R4

## Risks

| Risk | Mitigation |
|---|---|
| The F1 fix hides a real bad name by consuming a formal twice | Tests for double partial-match and exact+partial on one formal |
| A work budget makes the audit silently miss defects in big docs | A skipped region is reported in `messages`; replay treats skips as visible, not as clean |
| `lost` outcome breaks an in-progress T7 that adds a locked row before its check ships | Rows are only locked (`status: firm`) when their check is implemented; T7 flips the row after the check lands |
| Real-subprocess failure injection is hard to trigger deterministically | Use a fake `lib.docaudit` stub on `PYTHONPATH` in a temp dir to emit each bad envelope shape |

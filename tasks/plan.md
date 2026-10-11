# Implementation Plan: docs:check content audit (release A1) — vertical slices, harness first

> **Spec:** `SPEC-docs-check-content-audit-2026-10-11.md` · **Branch:** `feature/docs-check-content-audit` · **Base:** `dev` · **Target:** v2.21.0

## Overview

SPEC v2 (`SPEC-docs-check-content-audit-2026-10-11.md`, decisions D0/D6/D7 confirmed) and the committed ORCHESTRATE file
(`ORCHESTRATE-docs-check-content-audit.md`, 9 horizontal phases) already define *what* A1 builds. This plan re-slices that
work **vertically** (each task is one complete user-visible path that leaves the system working) and adds the one thing the
review found missing: a **replay harness** that makes the audit's recall and precision *measurable and reproducible* instead
of asserted. Harness-first is red-first at project level: every later slice turns manifest rows from "pending" to "firm".

**Files:** this plan lives in the feature worktree `~/.git-worktrees/rforge/feature-docs-check-content-audit` (branch `feature/docs-check-content-audit`). `tasks/todo.md` is the live checklist.
`ORCHESTRATE-docs-check-content-audit.md` keeps the objective, acceptance criteria and friction notes; **this file supersedes its horizontal Phase Overview.** Delete both from the branch before merging to `dev`.

## Architecture decisions

- **Harness is dev-only under `tests/harness/`** (not `scripts/`): `package.json` `files` ships `scripts/` but not `tests/`, and the
  harness needs fixtures, a defect manifest and local checkouts. No `tests/__init__.py` exists, so file basenames must be
  unique across `tests/` subdirectories.
- **Read-only against other repos:** extraction via `git archive <ref> man NAMESPACE DESCRIPTION vignettes README.md | tar -x -C <tmp>`
  (or `git ls-tree` + `git show`); never a checkout; output only to `tmp_path`/scratchpad. HOME isolated (`lib.changed` writes
  `~/.rforge/baseline-cache/`).
- **CI-safe vs local:** committed fixtures (3 small excerpts) run under `pytest tests/`; real-history rows are guarded by
  `pytest.mark.skipif` on `RFORGE_MEDFIT_PATH` / `RFORGE_PROBMED_PATH` / `RFORGE_MEDROBUST_PATH` (the `RFORGE_E2E` pattern at
  `tests/test_regression_suggests_e2e.py:34-36`).
- **Manifest-driven expectations:** `tests/fixtures/docaudit/defects.json` rows carry `expectation: firm|conditional|none`,
  `status: pending|firm`. A `firm` row that stops firing fails CI — recall can only go up, never silently down.
- **The harness is itself tested** (mutation self-test: with the audit stubbed to return nothing, firm rows must report red).
- **Reuse, don't rewrite:** `lib/s7review.py` `_mask_strings_and_comments` (~line 80), `tests/conftest.py` `make_pkg`, the
  `copytree` copy-then-mutate pattern (`tests/test_scaffold.py:22,44`), `tests/fixtures/suggestbug.before|after` as the
  before/after template, `lib/sitelint._envelope` for the house envelope shape.

## Dependency graph

```text
T1 allowlist helper ───────────────────────────────┐
T2 manifest + recall runner ─┬─ T3 plant + known-answer fixtures ─┐
                             └─ T4 history replay                  │
                                                                   ▼
        T5 named-arg slice ── T6 listing/arity slice ══ GATE (human) ══╗
                                                                       ▼
                         T7 scannability ∥ T8 coverage+since ∥ T9 allowlist suppression (needs T1)
                                                                       ▼
                         T10 CLI/D0/envelope ── T11 docs:check rewrite
                                                                       ▼
        T12 registration gates ── T13 test-all+counts ── T14/T15/T16 docs sweeps ── T17 release (user-gated)
```

Parallel-safe: T1 ∥ T2; T7 ∥ T8 ∥ T9; T14 ∥ T15 ∥ T16. Must be sequential: T5→T6→GATE; T10→T11; T12→T13; release last.

## Task list

### Phase 0 — Foundation and harness

- [ ] **T1 [S] `discovery` allowlist helper refactor.** *Files:* `lib/discovery.py`, `tests/test_lib_discovery.py`. *AC:* direct tests
  for absent key, scalar/empty (malformed), block list, inline comments, CRLF, sibling `docs:` key; helper takes a section name,
  `_read_site_allowlist` stays a thin wrapper with identical `(items, malformed)`; sitelint and rcmd_deploy tests untouched and green.
  *Verify:* `pytest tests/test_lib_discovery.py tests/test_sitelint.py tests/test_rcmd_deploy.py -q`. *Deps:* none.
- [ ] **T2 [M] Defect manifest + recall runner (red-first).** *Files:* `tests/harness/replay.py`, `tests/fixtures/docaudit/defects.json`,
  `tests/harness/test_harness_selftest.py`. *AC:* manifest has the 18 real medfit defects (id, package, class, fix sha, pre-fix ref,
  file, owning `check`, `release` (A1|A2), `expectation`, `status`, reason — SHAs and paths only, no content); `replay.py recall --scope signature|a1|all` (default `all`) reports eligible rows only, extracts each pre-fix tree read-only,
  calls `python3 -m lib.docaudit --path <tmp> --format json`, prints "caught k of n eligible (m pending, A2)" (module absent → rows `pending`; `release: A2` rows never count toward A1); exit code
  fails when an eligible `firm` row stops firing; self-test on a synthetic tmp git repo, including the **mutation test** (stubbed audit →
  firm rows red). *Verify:* `pytest tests/harness -q`; `python3 tests/harness/replay.py recall --manifest tests/fixtures/docaudit/defects.json`.
  *Deps:* none.
- [ ] **T3 [M] Planted-defect injector + committed known-answer pair.** *Files:* `tests/harness/plant.py`, `tests/harness/test_known_answer.py`,
  `tests/fixtures/docaudit/{defect,clean}/` (+ provenance `README.md`). *AC:* fixtures are verbatim excerpts of medfit `17d976d^` /
  `17d976d` (refcard table, `joint_effects.Rd` usage, DESCRIPTION, NAMESPACE) — **Rd files created via Bash/`git show`** (the
  PreToolUse hook blocks Write/Edit on `man/*.Rd`); injector mutates a `copytree` of the clean fixture (wrong named arg,
  renamed formal in a listing, extra positional); known-answer test is red until T5/T6. *Verify:* `pytest tests/harness -q`
  (known-answer tests marked expected-pending in the manifest). *Deps:* T2.
- [ ] **T4 [S] History replayer.** *Files:* `tests/harness/replay.py`, `tests/harness/test_replay_history.py`. *AC:* `replay.py replay
  --repo <path> --n 60 --checks named-arg,arity` walks `git rev-list --first-parent -n N`, extracts per commit, dedupes hits by
  (file, call, arg), emits JSON for triage; tested on a synthetic tmp git history with one planted bad commit; local-repo test
  skipif-guarded; HOME isolated. *Verify:* `pytest tests/harness -q`. *Deps:* T2.

**Checkpoint A — harness live (human glance):** `pytest tests/harness -q` green; `replay.py recall` prints every row as
`pending` and counts none as missed; the mutation self-test proves the harness goes red when it should; nothing under `lib/docaudit.py` yet.

### Phase 1 — First vertical slices

- [ ] **T5 [M] "A wrong named argument is flagged, end to end."** *Files:* `lib/docaudit.py` (NEW), `tests/test_docaudit.py`,
  `tests/test_docaudit_e2e.py`. *AC:* Rd `\usage` parser (defaults, multiline, `\dots`→`...`, backticks), `NAMESPACE` exports
  (comma lists; `exportPattern` → message), masking reused from `s7review`, doc surface (fenced `r`/unlabeled blocks + backticked
  spans); `signature-named-arg` (error) skips `...` functions and accepts unique-prefix partial matching; minimal house envelope;
  `python3 -m lib.docaudit --path P --format json`; e2e subprocess flags a planted wrong arg on the T3 clean fixture; manifest
  named-arg rows flip `pending→firm`; local replay reproduces medfit `b40444e` and medrobust `96d97b4`. *Verify:*
  `pytest tests/test_docaudit.py tests/test_docaudit_e2e.py tests/harness -q`. *Deps:* T3 (T1 not needed).
- [ ] **T6 [M] "A refcard listing with non-formal names or bad arity is flagged."** *Files:* `lib/docaudit.py`, `tests/test_docaudit.py`,
  `tests/test_docaudit_e2e.py`. *AC:* `signature-names` (warn; backticked span that is the whole first cell of a table row; `...` functions exempt) and
  `signature-arity` (warn; positionals > formals, **only for functions with no `...`** — variadic functions exempt, positive control: `f(x, ...)` called as `f(1, 2, 3)` is not flagged); unchecked-reason accounting (`no-usage`, `method`, `re-export`)
  and the `checked N of M` summary line; defect fixture flags `joint_effects(x, theta)`, clean fixture has 0 `error`, the fixed
  refcard does **not** flag `bootstrap_mediation(f, …)`; known-answer test green; manifest `joint_effects` row `firm`. *Verify:* same
  command as T5. *Deps:* T5.

**Checkpoint B — THE GATE (human; hard stop).** Adversarial review #2 on the signature logic (multi-agent, read-only);
history replay ≥60 commits × medfit/medrobust/probmed (`replay.py replay`); `replay.py recall --scope signature` caught-k-of-n matching the signature rows of the SPEC claim (scannability and site rows are not eligible yet);
planted defects in a scratch copy of the hold-out docs; hold-out triage by you (true/false/won't-fix), precision recorded in the SPEC
appendix. **Blocked by:** red fixture or missed planted defect; any raised exception; any unresolved false-positive class; any
`error`-severity false positive (→ demote `signature-named-arg` to `warn`, D7). No later slice starts until this passes.

### Phase 2 — Remaining checks (parallel-safe after the gate)

- [x] **T7 [S] "Scannability findings appear."** *Files:* `lib/docaudit.py`, `tests/test_docaudit.py`. *AC:* paragraph >110 words, H2 >800
  words with <3 H3, "Next Steps" not last; `info`, configurable; the `extraction.qmd` Next-Steps row flips `firm`; `methods.qmd`-style
  permanent flag documented as allowlist-able. *Deps:* T6.
- [x] **T8 [M] "Coverage report and `--since`."** *Files:* `lib/docaudit.py`, `tests/test_docaudit.py`. *AC:* export × doc matrix (`info`;
  `warn` only when an export appears in no doc); `--since TAG` restricts to exports/Rd added since the tag via
  `git diff --name-status TAG..HEAD` on `NAMESPACE`/`man/`; unknown tag → message, no crash; **no engine enumeration**. *Deps:* T6.
- [x] **T9 [S] "A finding can be suppressed via `.rforge.yaml`."** *Files:* `lib/docaudit.py`, `tests/test_docaudit.py`. *AC:* `docs.allowlist`
  entries `<relpath>` and `<relpath>::<check-id>` read from the **package root** via T1's helper; malformed → ignore + message.
  *Deps:* T1, T6.

**Checkpoint C:** all A1 checks green; `replay.py recall --scope a1` catches every `release: A1` row (now including `scannability`); `release: A2` rows stay `pending` and are excluded;
`pytest tests/ -q` green.

### Phase 3 — User-facing surface

- [x] **T10 [M] "CLI is complete and scope-correct."** *Files:* `lib/docaudit.py`, `tests/test_docaudit.py`, `tests/test_docaudit_e2e.py`.
  *AC:* `max_severity`, `status` = `warn` for any warn/error, `--fail-on none|warn|error` (exit code only), `info` hidden unless
  `--detailed`, D0 scope (walk up to `DESCRIPTION`; manifest-or-`--eco` for sweeps; hybrid audits nested; resolved scope is the
  first output line; subdirectory, one-package-ecosystem-root and no-manifest cases tested), `audit_ecosystem`, `format_text`/`format_json`.
  *Deps:* T7, T8, T9.
- [ ] **T11 [M] "`/rforge:docs:check` runs the audit."** *Files:* `commands/docs/check.md`, `docs/commands.md`, `agents/orchestrator.md`,
  `tests/_check_agent_engines.py`. *AC:* keeps `name: rforge:docs:check`; hyphenated `arguments:` (`package` positional, `detailed`,
  `eco`, `since`, `fail-on`); every flag appears literally in the `docs/commands.md` section; orchestrator read-only recipe row for the default
  invocation plus a positive assertion modeled on `_check_agent_engines.py:100-115`; (`--run-examples` prohibition and Step 3 wording
  are A2). *Verify:* `python3 tests/_check_commands_doc.py && python3 tests/_check_agent_engines.py`. *Deps:* T10.

**Checkpoint D — live exercise (e2e-before-pr rule):** run `/rforge:docs:check` in a real session against the defect and clean
fixture packages and quote the transcript (a run that can fail); record it for the PR body.

### Phase 4 — Ship

- [ ] **T12 [S] Registration gates for the new public module.** *Files:* `scripts/gen_lib_reference.py` (`MODULES`), `mkdocs.yml` (nav), `docs/lib-modules.md`,
  `tests/cli/automated-tests.sh` (`PUBLIC_MODULES`), `docs/reference/docaudit.md` (generated). *Verify:* `python3 scripts/gen_lib_reference.py --check`.
- [ ] **T13 [S] Test-all, counts and mirror.** *Files:* `tests/test-all.sh` (CLI smoke + harness smoke `run` lines; add `test_docaudit.py` to `lib_pytest`),
  `CLAUDE.md` (check count at :136 and public-modules list at :101), `AGENTS.md` (mirror), `docs/contributing.md:94`. *AC:* the exact new
  check count is stated and identical in all three places. *Verify:* `bash tests/test-all.sh`; `version_sync.py --check`. *Deps:* T12.
- [ ] **T14 [S] Docs sweep A — stale "clean docs:check" meaning (1).** *Files:* `docs/command-cards.md:86`, `docs/REFCARD.md:41,380`, `docs/quickstart.md:357`,
  `docs/architecture.md:226,257,273,281`, `docs/workflows/index.md:137`.
- [ ] **T15 [S] Docs sweep B — stale meaning (2).** *Files:* `docs/tutorials/cran-release-prep.md:7,28,48,259`, `docs/tutorials/rforge-in-the-r-lifecycle.md:63`,
  `commands/complete.md:127`, `.claude-plugin/skills/validation/description-sync.md:112`.
- [ ] **T16 [M] Guide, config claim, CHANGELOG.** *Files:* relevant `docs/guides/*` page, `docs/configuration.md:132` (remove the unbacked `claude_md_budget` claim),
  `docs/commands.md:490-515` ("Validates" list), `CHANGELOG.md` `[Unreleased]` (behavior change + dropped promises). *AC:* `mkdocs build --strict` clean.

**Checkpoint E — release gates:** `pytest tests/ -q`; `bash tests/test-all.sh` (exact count); `gen_lib_reference.py --check`; `version_sync.py --check`; `mkdocs build --strict`;
harness recall report archived in the PR body; ORCHESTRATE file removed from the branch before merge to `dev`.

- [ ] **T17a [M] Version bump and PRs (user-gated).** 4 version sources → 2.21.0, `version_sync.py`, grep for the old version string, PR `feature→dev` (squash), then `dev→main` release PR.
- [ ] **T17b [S] Tag, release, tap (user-gated).** Tag + GitHub release after CI is green on `main`; tap formula + `generator/manifest.json` sync with `generate.py rforge --diff` IDENTICAL —
  **writes to another repo: ask for explicit permission for each write.**

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Manifest rots if medfit history is rewritten | Med | Manifest holds SHAs only; `replay.py` reports "ref not found" as a distinct status, never as "not caught" |
| Harness grows larger than the check it verifies | Med | Three subcommands only (`recall`, `replay`, plant); self-test with a mutation case; no plugin system |
| Harness gives false assurance | High | Mutation self-test (stub audit → red); `firm` rows are regression-locked; the gate still needs human triage |
| `git archive` extraction cost over 60×3 commits | Low | Extract only `man/ NAMESPACE DESCRIPTION vignettes/ README*`; cache per sha in `tmp_path` |
| PreToolUse hook blocks Rd fixture writes | Low | Create Rd via Bash/`git show`; noted in T3 |
| Hard-coded check count drifts in 3 places | Med | T13 owns all three; verify by grep for the old number |
| Python 3.9 system env fails 3 of 45 checks | Low | Use the ≥3.10 venv recipe from ORCHESTRATE Verification |
| Human gate stalls the build | Med | Schedule the triage session at the start; slices T7–T9 are queued behind it |

## Verification (definition of done for A1)

```bash
cd ~/.git-worktrees/rforge/feature-docs-check-content-audit
export PATH="$HOME/.venvs/rforge-dev/bin:$PATH"        # Python >=3.10 + pytest, pyyaml, mkdocs-material (recipe in ORCHESTRATE)
python -m pytest tests/ -q                              # incl. tests/harness; baseline 615 passed / 2 skipped on `dev` after #85/#86 (merged into this branch 2026-10-11)
bash tests/test-all.sh                                  # baseline 45 checks; exact new count stated in the PR
python3 scripts/gen_lib_reference.py --check && python3 scripts/version_sync.py --check
python3 tests/harness/replay.py recall --manifest tests/fixtures/docaudit/defects.json
RFORGE_MEDFIT_PATH=~/projects/r-packages/active/medfit python -m pytest tests/harness -q   # local real-history rows
```

Definition of done also requires: every `release: A1` firm row caught by `replay.py recall --scope a1` (A2 rows excluded); every `error` finding free of false positives on the
hold-out (else demoted, D7); the Checkpoint D transcript quoted in the PR.

## Open questions

1. Hold-out triage session: when? (It gates T7–T17.)
2. T17b tap sync needs your explicit permission at release time.
3. A2 (`--site`, `--run-examples`) gets its own plan after A1 ships; the harness manifest already carries its rows as `conditional`.

# docs:check content audit (release A1) — Orchestration Plan

> **Branch:** `feature/docs-check-content-audit`
> **Base:** `dev`
> **Worktree:** `~/.git-worktrees/rforge/feature-docs-check-content-audit`
> **Spec:** `SPEC-docs-check-content-audit-2026-10-11.md` (v2, decisions D0/D6/D7 confirmed)
> **Decision ledger:** `GRILL-docs-content-skills-2026-10-11.md` · **Brainstorm:** `BRAINSTORM-docs-content-skills-2026-10-11.md`
> **Target version:** v2.21.0 (minor; command count stays 44)
> **Scope:** A1 only — static checks + the `docs:check` rewrite. **A2** (`--site`, `--run-examples`) is a separate, later plan.
> **Task order:** superseded by `tasks/plan.md` (vertical slices, replay harness first); `tasks/todo.md` is the live checklist. This file keeps the objective, acceptance criteria and friction prevention; its Phase Overview below is historical.

## Objective

Give `/rforge:docs:check` deterministic backing via a new pure-stdlib `lib/docaudit.py` (signature, arity, coverage and
scannability checks, `--since`, `docs.allowlist`, D0 scope resolution), rewrite the command to delegate to it, and ship
v2.21.0. The tool is a candidate generator with 3 firm + 3 conditional hits of 18 real medfit defects; never claim more.

## Phase Overview

| Phase | Increment | Priority | Effort | Status |
|---|---|---|---|---|
| 1 | `discovery` allowlist refactor (own commit, direct tests first) | P0 | Low | ⏳ |
| 2 | Parsers: Rd `\usage`, `NAMESPACE`, doc surface, masking reuse | P0 | Med | ⏳ |
| 3 | `signature-named-arg` / `signature-names` / `signature-arity` + fixtures + e2e planted control | P0 | High | ⏳ |
| 4 | **Gate** — adversarial review #2, history + recall replay, planted defects, hold-out triage (needs you) | P0 | Med | ⏳ |
| 5 | `coverage` (+ `--since`) and `scannability` | P1 | Med | ⏳ |
| 6 | CLI, envelope + `max_severity`, summary line, `--fail-on`, D0 scope, `audit_ecosystem` | P1 | Med | ⏳ |
| 7 | `docs:check` rewrite + `commands.md` + orchestrator row | P1 | Med | ⏳ |
| 8 | Mechanical gates + docs (full list below) | P1 | Med | ⏳ |
| 9 | A1 release (v2.21.0) — user-gated | P2 | High | ⏳ |

Phase 4 is a **hard stop**: the maintainer triages findings, so it cannot run unattended. Phases 5–9 do not start until
Phase 4's blocking criteria pass.

## Phase 1: `discovery` allowlist refactor

**Scope:** generalize `lib/discovery.py` `_read_site_allowlist` (lines ~308-394, a hand-rolled state machine hard-wired to
`site:`/`allowlist:`) into a section-name helper; keep `_read_site_allowlist` as a thin wrapper. It has only indirect
tests today (`tests/test_sitelint.py:192-258`, `tests/test_rcmd_deploy.py`), so **write direct unit tests first**.

- [ ] 1.1 Direct unit tests for `_read_site_allowlist`: absent key, scalar/empty (malformed), block list, inline comments, CRLF, `docs:` sibling key does not collide
- [ ] 1.2 Generalize to a section-name helper (`docs.allowlist` readable from the **package root**); wrapper keeps `(items, malformed)`
- [ ] 1.3 Existing sitelint + rcmd_deploy tests stay green untouched

**Key files:** `lib/discovery.py` (update), `tests/test_lib_discovery.py` (update)

## Phase 2: Parsers

**Scope:** shared static parsers. **Reuse `lib/s7review.py` `_mask_strings_and_comments`** (line ~80) — v2.10.0 added it for
exactly this bug class (no comment/string masking); do not write a second masker. Decide import-vs-extract here; do not
change `s7review` behavior.

- [ ] 2.1 `man/*.Rd` `\usage{}` parser: defaults, multiline, `\dots`/`\ldots` → `...`, backticked names; `\method{}`/`\S4method{}` recorded as unchecked (reason `method`), no usage = unchecked (`no-usage`), re-export = unchecked (`re-export`)
- [ ] 2.2 `NAMESPACE` exports: `export(a, b)` comma lists; `exportPattern` → message, not a guess; restrict all checks to exports
- [ ] 2.3 Doc-surface extractor: `README.md`, `README.qmd`/`README.Rmd`, `vignettes/**/*.{qmd,Rmd}`; fenced blocks only when labeled `r` or unlabeled; backticked `fn(…)` spans outside fences
- [ ] 2.4 Argument splitter that blanks comments and string contents first (both reviewer toy cases as tests)

**Key files:** `lib/docaudit.py` (NEW), `tests/test_docaudit.py` (NEW)

## Phase 3: Signature checks

**Scope:** the three checks and the fixtures that prove they can fail.

- [ ] 3.1 `signature-named-arg` (error): named arg not among formals, exported function **without `...`**; unique-prefix partial matching is valid
- [ ] 3.2 `signature-names` (warn): bare-identifier arg in any backticked `fn(…)` span outside fences, function **without `...`** (the `...` exemption is part of the rule — the first prototype hid it)
- [ ] 3.3 `signature-arity` (warn): positionals exceed the non-`...` formals; no "ordered subset" rule
- [ ] 3.4 Fixtures under `tests/fixtures/docaudit/` with a provenance README: `17d976d^` refcard table + `joint_effects.Rd` usage (defect), `17d976d` (clean). **Create Rd fixtures via Bash or `git show` — the PreToolUse hook blocks Write/Edit on `man/*.Rd`**
- [ ] 3.5 e2e (`tests/test_docaudit_e2e.py`): real `python3 -m lib.docaudit` subprocess on the fixture package; defect → `signature-names`; clean → 0 `error`; **planted defect** (synthetic wrong named arg) is caught

**Key files:** `lib/docaudit.py` (update), `tests/test_docaudit_e2e.py` (NEW), `tests/fixtures/docaudit/` (NEW)

## Phase 4: Gate (adversarial review #2 + replays + triage) — STOP for the maintainer

**Scope:** precision-critical logic is reviewed before more is built, so a forced fix cannot invalidate later phases.

- [ ] 4.1 Adversarial review of the signature logic (multi-agent, read-only; focus: false positives on real docs)
- [ ] 4.2 **History replay:** named-arg + arity over ≥60 commits each of medfit, medrobust, probmed via `git show` (read-only); record hits, triage each
- [ ] 4.3 **Recall replay:** re-run the 18-defect table from the SPEC; state "caught k of n"; it must match the SPEC's Motivation claim
- [ ] 4.4 **Planted defects in a scratch copy** of the hold-out docs (copied to the scratchpad, never edited in place)
- [ ] 4.5 Hold-out triage on current probmed (63 Rd) and medrobust (55): the maintainer labels every finding true / false / won't-fix; precision recorded in the SPEC appendix
- [ ] 4.6 D7 check: any `error`-severity false positive → demote `signature-named-arg` to `warn` before continuing

**Blocking criteria:** red fixture or missed planted defect; any raised exception; any unresolved false-positive class;
any `error` false positive (→ demote, per D7).

## Phase 5: `coverage` and `scannability`

- [ ] 5.1 `coverage` matrix (export × doc): `info`, `warn` only when an export appears in no doc; a report, **no engine enumeration in v1**
- [ ] 5.2 `--since TAG`: restrict to exports/Rd added since the tag (`git diff --name-status TAG..HEAD` on `NAMESPACE`, `man/`); unknown tag → message
- [ ] 5.3 `scannability` (`info`, configurable): paragraph over 110 words; H2 over 800 words with fewer than 3 H3; "Next Steps" not last

**Key files:** `lib/docaudit.py` (update), `tests/test_docaudit.py` (update)

## Phase 6: CLI, envelope, scope

- [ ] 6.1 House envelope `{kind: "docs-audit", status, findings, messages, engine_missing}` + `max_severity`; `status` is `warn` for any warn/error finding
- [ ] 6.2 Summary line `checked N of M exported functions` with unchecked reasons; `info` hidden by default, shown with `--detailed`
- [ ] 6.3 `--fail-on none|warn|error` sets only the exit code (default `none`); do not claim `lib.rcmd` precedent
- [ ] 6.4 **D0 scope:** walk up to nearest `DESCRIPTION`; at a non-package root sweep only with a manifest or `--eco`, else print a hint and exit 0; hybrid roots audit nested packages; the resolved scope is the **first output line**
- [ ] 6.5 `audit_ecosystem` via `lib.discovery.detect_ecosystem` (note: `Kind` is `single` for 0–1 packages — use `_is_r_package`, wrapped publicly if needed)
- [ ] 6.6 `format_text` / `format_json`; `python3 -m lib.docaudit` CLI (run as a package, never `python3 lib/docaudit.py`)

## Phase 7: Command rewrite

- [ ] 7.1 Rewrite `commands/docs/check.md`; keep `name: rforge:docs:check` (rename stubs assert it). A1 `arguments:` are **hyphenated**: `package` (positional), `detailed`, `eco`, `since`, `fail-on`
- [ ] 7.2 `docs/commands.md` section shows every flag literally (`_check_commands_doc.py` requires `--<name>`)
- [ ] 7.3 `agents/orchestrator.md`: add a `docs-audit` row to the read-only recipe table (default invocation); extend `tests/_check_agent_engines.py` with a positive assertion modeled on the deploy-only one (`:100-115`). The `--run-examples` prohibition line and the Step 3 wording reconciliation belong to **A2**
- [ ] 7.4 Behavior-change text for the CHANGELOG: improvised prompt → deterministic checks; dropped promises (NEWS completeness, cross-package contracts, vignette cross-references, default example checking); `--detailed` narrows; D0 default scope

## Phase 8: Mechanical gates and docs

- [ ] 8.1 `scripts/gen_lib_reference.py:36` `MODULES` += `lib.docaudit`; regenerate `docs/reference/docaudit.md`
- [ ] 8.2 `mkdocs.yml` nav entry (~line 152, beside `sitelint`/`tidyaudit`); `docs/lib-modules.md` (header line 4 + a row near line 51); `tests/cli/automated-tests.sh:108` `PUBLIC_MODULES`
- [ ] 8.3 `CLAUDE.md:101` public-modules list → copy to `AGENTS.md`; `version_sync.py --check` stays green
- [ ] 8.4 `test-all.sh`: CLI smoke `run` line; add `tests/test_docaudit.py` to the `lib_pytest` named list (~line 415); update the hard-coded check count in `CLAUDE.md:136`, `AGENTS.md:137`, `docs/contributing.md:94` (45 → the exact new number)
- [ ] 8.5 Docs asserting the old meaning of a clean `docs:check`: `docs/command-cards.md:86`; `docs/REFCARD.md:41,380`; `docs/quickstart.md:357`; `docs/architecture.md:226,257,273,281`; `docs/workflows/index.md:137`; `docs/tutorials/cran-release-prep.md:7,28,48,259`; `docs/tutorials/rforge-in-the-r-lifecycle.md:63`; `commands/complete.md:127`; `.claude-plugin/skills/validation/description-sync.md:112`; `docs/commands.md:490-515`
- [ ] 8.6 Remove the unbacked `claude_md_budget` claim at `docs/configuration.md:132`
- [ ] 8.7 Guide + REFCARD entries + CHANGELOG `[Unreleased]` (behavior change from 7.4)

## Phase 9: A1 release (user-gated)

- [ ] 9.1 Version bump to 2.21.0 across the 4 sources, then `python3 scripts/version_sync.py`; grep the repo for the old version string
- [ ] 9.2 Full gates green; PR `feature/* → dev`, then `dev → main` release PR; tag; GitHub release; CI verify on `main`
- [ ] 9.3 Homebrew formula + `generator/manifest.json` sync (`generate.py rforge --diff` → IDENTICAL). **Writes to another repo: ask for explicit permission for each write**

## Friction Prevention

- **Context first:** verify CWD, branch and worktree with `pwd`, `git branch --show-current`, `git worktree list` before any git operation; this worktree is `feature-docs-check-content-audit` (a second one, `feature-rstatus-version-drift`, belongs to PR #85 — do not touch it).
- **Python ≥3.10 needed:** system `python3` is 3.9 and fails 3 of 45 `test-all.sh` checks from environment alone. Use a venv (see Verification).
- **Never Write/Edit `man/*.Rd`** (PreToolUse hook rule 1). Fixtures: Bash heredoc or `git show`.
- **Run modules as packages** (`python3 -m lib.docaudit`); never `python3 lib/docaudit.py`.
- **No unrequested cross-repo writes.** medfit, probmed and medrobust are read-only (`git show`, `ls`, `cat`); scratch copies go in the session scratchpad, never inside those repos.
- **Do not overclaim.** Recall is 3 firm + 3 conditional of 18; `coverage` is a report; `signature-names` cannot tell a stale name from a placeholder.
- **Commits:** conventional; a pre-commit hook fix means re-stage and make a NEW commit, never amend.
- **No autonomous starts past Phase 4;** test per phase; never skip the Phase 4 stop.
- **ORCHESTRATE cleanup:** delete this file from the branch as part of the merge to `dev` (working artifact, not for `dev`).

## Acceptance Criteria

- [ ] Fixtures green incl. the planted-defect control (SPEC acceptance 1)
- [ ] History replay: ≥60 commits × 3 packages, hits triaged (2)
- [ ] Recall replay states "caught k of n" and matches the SPEC (3)
- [ ] Planted defects in a scratch copy of the hold-out docs are caught (4)
- [ ] Hold-out triage done; precision recorded in the SPEC appendix (5)
- [ ] No `error`-severity false positive (else `signature-named-arg` demoted to `warn`, D7)
- [ ] `docs:check` rewritten; frontmatter hyphenated; commands count still 44
- [ ] All mechanical gates updated (Phase 8); `test-all.sh` and `pytest tests/` green with the exact new check count stated
- [ ] CHANGELOG states the behavior change and the dropped promises

## Commit Strategy

Conventional commits, one per logical step; Phase 1 is its own `refactor(discovery): …` commit. Suggested scopes:
`refactor(discovery)`, `feat(docaudit)`, `test(docaudit)`, `feat(docs-check)`, `docs`, `chore: bump version to v2.21.0`.

## Verification

Test command (auto-detected from `CLAUDE.md` "Test gates"; run from the worktree path in a Python ≥3.10 environment):

```bash
# one-time: a Python >=3.10 environment with the dev dependencies
uv venv ~/.venvs/rforge-dev --python 3.12
uv pip install --python ~/.venvs/rforge-dev/bin/python pytest pyyaml mkdocs-material mkdocs-macros-plugin pillow cairosvg

cd ~/.git-worktrees/rforge/feature-docs-check-content-audit
export PATH="$HOME/.venvs/rforge-dev/bin:$PATH"
python -m pytest tests/ -q          # baseline before this plan: 610 passed / 2 skipped on the PR #85 branch
bash tests/test-all.sh              # baseline: 45 checks
python3 scripts/gen_lib_reference.py --check
python3 scripts/version_sync.py --check
```

## Test plan (TDD) — red-first

Tier selection (auto): new parser/script → **unit**; changed command frontmatter/flags → **e2e + dogfood**; cross-command
data flow → **integration** only at the orchestrator row; external dependency → **N/A for A1** (static; no network, no R —
that is A2); new command/skill/agent → **count-cascade N/A** (no new command, count stays 44). Write each stub failing first;
each carries `# TODO(author): delete if not contract-bearing` until the contract is confirmed.

### unit (`tests/test_docaudit.py`, `tests/test_lib_discovery.py`)

- [ ] **test_read_site_allowlist_direct_cases** (Phase 1)
- [ ] **test_rd_usage_parse** — defaults, multiline, `\dots`, backticked names (Phase 2)
- [ ] **test_namespace_comma_lists_and_exportpattern** (Phase 2)
- [ ] **test_splitter_blanks_comments_and_strings** — both reviewer toy cases (Phase 2)
- [ ] **test_named_arg_skips_dots_functions** and **test_unique_prefix_is_valid** (Phase 3)
- [ ] **test_signature_names_skips_dots_functions_placeholder** — `bootstrap_mediation(f, …)` not flagged (Phase 3)
- [ ] **test_signature_names_any_backticked_span** — table cell, list item, heading, prose; not inside a plantuml fence (Phase 3)
- [ ] **test_arity_positionals_exceed_formals** (Phase 3)
- [ ] **test_since_restricts_coverage**, **test_unchecked_reasons_accounting** (Phase 5)
- [ ] **test_scannability_defaults_and_allowlist** (Phase 5)
- [ ] **test_scope_walk_up_subdir**, **test_scope_hybrid_nested**, **test_scope_one_package_ecosystem_root**, **test_scope_no_manifest_needs_eco** (Phase 6)
- [ ] **test_envelope_max_severity_and_status** (Phase 6)

### e2e + dogfood (`tests/test_docaudit_e2e.py`, `tests/test-all.sh`)

- [ ] **test_known_defect_fixture_flags_signature_names** and **test_clean_fixture_zero_errors** (Phase 3)
- [ ] **test_planted_defect_caught** — the control proving the check can fail (Phase 3)
- [ ] **commands.md gate covers every hyphenated flag**; `AGENTS.md` mirror; `lib_pytest` list includes the new file; CLI smoke (Phase 7–8)
- [ ] **test_local_known_answer_pair** — `pytest.mark.skipif` unless `RFORGE_MEDFIT_PATH` is set; `git show` only (Phase 4)

## Documentation & Discoverability

Scored with craft's doc-impact rubric (cheap ≥3; heavy ≥5 or a new user-facing surface). Inputs: 1 new module, a config key
(`docs.allowlist`), flags on an existing command; no new command or surface.

- [x] Guide — extend the relevant `docs/guides/*` page (score 4)
- [x] Refcard — `docs:check` flags (score 4)
- [x] Demo — audit on the defect fixture (score 3)
- [x] API reference — `docs/reference/docaudit.md` (rubric 3 → N/A by score, **required** by the public-module convention and `gen_lib_reference.py --check`)
- [x] `docs/commands.md`, CHANGELOG `[Unreleased]`, and the stale-meaning docs listed in Phase 8.5
- N/A Mermaid (2), Tutorial (4), Cookbook (4), Architecture note (2) — below threshold

Count-cascade exclusion: version and command-count lines stay with `scripts/version_sync.py`.

## Session Instructions

```bash
cd ~/.git-worktrees/rforge/feature-docs-check-content-audit && claude
> "Read ORCHESTRATE-docs-check-content-audit.md and start Phase 1."
```

(Desktop app, no persistent shell: `EnterWorktree({ path: "/Users/davood/.git-worktrees/rforge/feature-docs-check-content-audit" })`
switches the session's cwd directly; the worktree is already in `git worktree list`.)

## Next steps

1. Start Phase 1 (the `discovery` refactor) — smallest, own commit, direct tests first.
2. Hold Phase 4 as a hard stop and schedule the triage session with the maintainer.
3. A2 (`--site`, `--run-examples`) gets its own ORCHESTRATE after A1 ships.

**Total estimate:** 9 phases; Phases 1–2 Low–Med, 3 High, 4 Med (human-gated), 5–8 Med, 9 High (release, user-gated).

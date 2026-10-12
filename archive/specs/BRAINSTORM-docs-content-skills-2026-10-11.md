# BRAINSTORM: rforge docs-content skills/commands — stale-content audit, new-feature docs, cookbooks, articles

> **Status (2026-10-11):** superseded in part. The grill and SPEC v2 corrected several recommendations here: impact folded into `--since`; `docs:check` rewritten instead of a new `docs:audit`; deploy-commit-message detection replaced by sitemap comparison; "a seventh class" moved out of v1. Kept as the divergent record; release B items stay parked. Current source of truth: `SPEC-docs-check-content-audit-2026-10-11.md`.

**Date:** 2026-10-11
**Depth:** default · **Focus:** feat
**Categories:** req, users, scope, success
**Decisions (from the session):** all four capabilities are in scope; form is **hybrid** (`lib/` + commands for deterministic checks, skills for judgment-heavy authoring).
**Assumption:** "stake contents" in the request was read as "stale contents."

## Context — what medfit's site shows (read-only, 2026-10-11)

Live site `https://data-wise.github.io/medfit/`: 67 pages (36 reference, 27 articles, news, home). New sections: Models menu (14 `model-*` pages), 4 Guides (changes, glossary, intervals, troubleshooting), cookbook, refcard, 4-step Getting Started.

medfit ran **five doc audits by hand in one day** (`.STATUS`: `readme_audit`, `stale_content_check`, `docs_audit`, `scannability_audit`, `website_review`). Each is a repeatable recipe; none is encoded anywhere reusable. The defects they found are exactly the class a tool should catch:

| Defect (real, medfit 2026-10-10) | Class |
|---|---|
| Introduction: "a seventh class" — 8 classes exported | prose count vs code |
| Refcard: `joint_effects(x, theta)` — real args `(object, estimates)` | documented signature vs `man/*.Rd` |
| README bootstrap block: `NIE = 0.19 [0.08, 0.32]` — real `0.164 [0.0867, 0.256]` | documented output vs a real run |
| Getting Started lacked the cluster and native engines; `?extract_mediation` omitted `SEMFit` | export/engine coverage gap |
| `extraction.qmd`: 942 lines, no route chooser, 113–124 word paragraphs | scannability |
| HC3 offered as survey-weight inference (it ignores clusters/strata) | semantic claim — needs a reader, not a regex |
| Live site was the 0.7.0 `main` build; `/articles/models.html` returned 404 until a manual `gh workflow run pkgdown.yaml --ref dev` | deployed-ref drift |

## What already exists in rforge (overlap check)

| Existing | Covers | Gap vs this brainstorm |
|---|---|---|
| `r:site` (`--strict`, `--check-leaks`, `--deploy`) | build health, leak guard, deploy | not content truth |
| `lib/sitelint.py`, `lib/tidyaudit.py`, `lib/cranlint.py` | leaks, NEWS header, DESCRIPTION lints | no claim-vs-code checks |
| `r:use-vignette`, `lib/scaffold.py` | vignette scaffold, dry-run + `--write` | no recipe/outline/grounding |
| `r:urlcheck`, `r:spell` | links, spelling | — |
| **`docs:check`** | promises "outdated examples", "API contracts" | **prompt-only: no `lib/` or R backing** (verified: no `lib.`/`python3`/`Rscript` in the file) |

**Overlap decision (recommended):** do not ship a parallel command that leaves `docs:check` making unbacked promises. Ship `/rforge:docs:audit` with real backing, then re-point `docs:check` at `lib.docaudit --eco` in a follow-up patch.

## Users

The maintainer of the MediationVerse R packages (medfit, probmed, medrobust, …), working inside one package repo, sometimes sweeping the ecosystem via the `.rforge.yaml` manifest.

## Proposed surface

| Capability | Form | Name | Default mode |
|---|---|---|---|
| Stale-content audit | `lib/docaudit.py` + command | `/rforge:docs:audit [pkg] [--site] [--run-examples] [--fail-on]` | read-only, advisory |
| New-feature docs | `lib/docimpact.py` + command | `/rforge:docs:impact [pkg] [--since TAG]` | read-only checklist |
| Cookbook builder | command + skill | `/rforge:docs:cookbook add\|verify` | dry-run, `--write` applies |
| Article authoring | command + skill | `/rforge:docs:article <topic> --outline\|--draft` | dry-run; unrun values stay placeholders |

Skills (new — rforge has only `skills/validation` today): `rforge-docs-authoring` (cookbook + article procedure) and `rforge-docs-adversarial-review` (the judgment tier below; opt-in, never in CI).

### Audit check catalog

| Tier | Check | Deterministic? | Reuses |
|---|---|---|---|
| A site-vs-source | deployed ref vs branch HEAD; sitemap vs `_pkgdown.yml` | yes (network, degrades to `warn`) | `runiverse` degrade pattern, `r:site --strict` |
| B claim-vs-code | documented call signatures vs `man/*.Rd` `\usage{}` | yes (static parse) | `discovery` |
| B | prose counts near nouns ("seventh class") vs exports | candidates only | `s7review` class list |
| B | README/vignette output vs a real run | opt-in `--run-examples`; numeric tolerance + seed | `rcmd` Rscript runner |
| B | stale numbers ("1,900+ tests") and versions | candidates | `rstatus`, `version_sync` idea |
| C coverage | export/engine × doc matrix (which article mentions which engine) | yes | `deps_sync.scan_usage` idea |
| D scannability | headings/paragraph length/section order per article | yes, advisory, configurable | — |
| E semantic | claims a regex can't judge (HC3 as survey inference) | no → skill | adversarial workflow pattern |

Finding shape: `{tier, check, severity, file, line, claim, evidence, suggestion}`. Allowlist via `.rforge.yaml` (as `site.allowlist`). Suggestions never say "edit `man/*.Rd`" — the PreToolUse hook blocks that; they say "run `document()`."

### Impact (new-feature docs)

Input: NEWS `(development version)` bullets + `NAMESPACE` diff + new `man/*.Rd` since `--since` (default last tag). Output: per new surface, the doc targets to touch — `_pkgdown.yml` reference index (a missing export fails `check_pkgdown`), Rd, refcard, cookbook, Getting Started, a model/guide article. Report-only in v1; NEWS prose stays the author's.

### Cookbook and article contracts

- **Recipe contract:** runs after the setup chunk alone, on bundled example data, with an asserted output. A `verify` mode runs every recipe plus a planted-defect control (medfit PR #129 did this — **study its mechanism before copying**).
- **Article contract:** every number or output comes from a run; unrun values stay `[RUN?]` placeholders (same grounding rule as `/rforge:finish` step 2 and savant's no-fabrication rule); length/heading budget comes from audit Tier D; finish by running the audit.

## Sequencing (recommended)

| Release | Bundle | Why |
|---|---|---|
| **A** | audit + impact (`docaudit`, `docimpact`, shared Rd/NAMESPACE parsers) | deterministic, read-only, highest reuse; medfit supplies known-answer fixtures |
| **B** | cookbook + article (skills + scaffold commands) | judgment-heavy; article uses the audit as its gate, so it must come after |

rforge precedent bundles related features (v2.11, v2.14). Cadence: spec → TDD → adversarial review (mandatory — these include skills and agent-prompt changes) → end-to-end smoke test for the network path → release.

## Risks

| Risk | Mitigation |
|---|---|
| False positives from number-near-noun heuristics | emit as `candidate`, never `error`; allowlist; `--fail-on` opt-in |
| `--run-examples` executes package code | opt-in; same posture as `r:test`/`r:check`; report diffs, never rewrite |
| Deployed-ref drift is *expected* in dev→main repos (site deploys from `main`) | severity `info` with the commits behind, not an alarm |
| Fabricated prose in `--draft` | placeholders + grounding rule + audit gate |
| Quarto vs Rmd article handling (medfit uses `.qmd` under `vignettes/articles/`) | parse both; open question on pkgdown's Quarto grouping limits |
| Skills are new to rforge (only `validation` exists) | adversarial Workflow review; `test-all.sh` skill-validity check |

## Success criteria — a known-answer pair from real history

`17d976d` is the commit that fixed the stale-content findings (touches `introduction.qmd`, `refcard.qmd`, NEWS). That gives a real before/after pair, readable without any write via `git show <sha>:<path>`:

- **Known-defect fixture** (`17d976d^`): audit must flag "seventh class" and `joint_effects(x, theta)` → both found, 0 false negatives.
- **Known-clean control** (`17d976d` or current HEAD, which `docs_audit` found healthy): audit reports 0 errors; any candidates are reviewed and either allowlisted or counted as false positives (target: ≤3).
- Same pair for the README bootstrap defect via `--run-examples` (fixture = `b1f307b^`).

## Test plan (TDD) — red-first

Tier selection (auto): new parser/script → **unit**; cross-command data flow (audit → impact → article gate) → **integration**; external deps (`gh-pages` fetch, `Rscript`, knitr/pkgdown) → **dependency**; new command/skill → **count-cascade dogfood**; flags/frontmatter → **e2e + dogfood**.

### unit (`tests/test_docaudit.py`, `tests/test_docimpact.py`)
- [ ] **test_rd_usage_parse** — `\usage{}` → arg names; positional vs named; `# TODO(author): delete if not contract-bearing`
- [ ] **test_signature_mismatch_flagged** — `joint_effects(x, theta)` vs `(object, estimates)` → one `error`
- [ ] **test_prose_count_candidate** — "seventh class" with 8 exports → `candidate`, not `error`
- [ ] **test_namespace_diff_new_export** — new export absent from `_pkgdown.yml` reference → impact item

### integration (`tests/test_docs_pipeline.py`)
- [ ] **test_audit_findings_feed_impact_envelope** — shared envelope keys survive the hand-off
- [ ] **test_article_gate_blocks_on_audit_error**

### dependency
- [ ] **test_site_fetch_offline_degrades_to_warn** — no network → `warn` envelope, never raises (as `runiverse`)
- [ ] **test_run_examples_engine_missing** — no `Rscript` → `engine_missing` envelope (as `rcmd`)

### e2e + dogfood (`tests/test_docs_e2e.py`) — must be able to fail
- [ ] **test_known_defect_fixture_flagged** — real `17d976d^` content extracted to a tmp dir via `git show`; asserts both defects found
- [ ] **test_known_clean_control_zero_errors** — `17d976d` content → 0 errors
- [ ] **test_planted_defect_in_recipe_caught** — cookbook `verify` fails on a planted bad recipe
- [ ] **test_dry_run_writes_nothing** — `cookbook add`/`article --draft` without `--write` leaves the tree untouched

### count-cascade dogfood
- [ ] **new commands have `arguments:` frontmatter matching `## Usage`**, appear in `docs/commands.md` (`_check_commands_doc.py`), `mkdocs.yml` nav, and `version_sync.py` count (44 → 48); `AGENTS.md` mirror still matches `CLAUDE.md`

Plus smoke test: a real run of `docs:audit --site` against the live medfit site (read-only) before release.

## Documentation & Discoverability

Scored with craft's doc-impact rubric (cheap types ≥3; heavy types ≥5 or a new user-facing surface). Inputs: 4 new commands, 2 new modules, multi-step workflow, config change (`.rforge.yaml` keys), user-facing CLI, new user-facing surface.

- [x] Guide — `docs/guides/docs-content.md` (score 13)
- [x] Refcard — REFCARD entries (9)
- [x] Demo — terminal recording of audit on the known-defect fixture (9)
- [x] Mermaid — audit → impact → cookbook → article pipeline (6)
- [x] Tutorial — "keep a package site honest" walkthrough, medfit as the example (15)
- [x] API reference — `docs/reference/{docaudit,docimpact}.md` via `gen_lib_reference.py` (7)
- [x] Cookbook — recipes for the audit/impact flags (14)
- [x] Architecture note — where the audit sits vs `r:site`/`sitelint`/`docs:check` (7)
- [x] CHANGELOG `[Unreleased]` mirror; `docs/commands.md` entries

Count-cascade exclusion: version and command-count lines stay with `scripts/version_sync.py`; this section never edits them.

## Open questions / to verify before the SPEC

1. pkgdown's `deploy_to_branch` commit message (believed `Built site for <pkg>: <version>@<sha>`) — **verify** before relying on it for deployed-ref detection.
2. medfit PR #129's cookbook test mechanism — read before designing `cookbook verify`.
3. medfit `model_pages` note: pkgdown groups Quarto articles only under some condition (text truncated here) — read `planning/specs/GAP-docs-model-pages-2026-10-10.md`.
4. Should `docs:check` be re-pointed at `lib.docaudit --eco` (recommended) or retired with a rename stub?
5. Ecosystem sweep (`--eco`) in v1, or single-package first? (Recommended: single-package first.)

## Recommended Next Step

→ Turn this into a SPEC (`SPEC-docs-audit-2026-10-11.md`) for **release A only** (audit + impact), after resolving open questions 1–3 by reading, then grill it before TDD. Cookbook and article stay as a parked second bundle.

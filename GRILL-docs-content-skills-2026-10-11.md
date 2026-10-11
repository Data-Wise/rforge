# GRILL: rforge docs-content skills/commands

**Date:** 2026-10-11
**Target:** [BRAINSTORM-docs-content-skills-2026-10-11.md](BRAINSTORM-docs-content-skills-2026-10-11.md) (scope: release A, audit + impact)
**Mode:** interactive, one question per branch; recommended answer first.

## Pre-answered by reading (2026-10-11)

- Known-defect fixtures verified: `17d976d^` has `introduction.qmd:35` "A seventh class" and `refcard.qmd:72` `joint_effects(x, theta)`; fixed at `17d976d`. README `NIE = 0.19` at `b1f307b^:151`.
- `man/joint_effects.Rd` usage is `joint_effects(object, estimates = object@estimates)`; the refcard documents `(object, estimates)`, so a signature matcher must allow omitted defaulted args (documented names must be a subset of formals, in order).
- **Brainstorm correction:** medfit's `gh-pages` commits read `Deploying to gh-pages from @ Data-Wise/medfit@<sha>` (GitHub Action), not pkgdown's `Built site for ...`. The format depends on the deploy mechanism.
- Cookbook test mechanism (medfit PR #129, `tests/testthat/test-cookbook-consistency.R`): package-resident testthat file; splits `.qmd` on `## ` headings and r-chunks, runs each recipe in a fresh env after the setup chunk, skips when vignettes are absent, synthetic planted-defect control; recipes 9-11 excluded as slow.
- Quarto grouping: GAP note called it unverified, but shipped `_pkgdown.yml` has grouped `articles:` (lines 232-272).
- rforge has no standard plugin skills: one flat `.claude-plugin/skills/validation/description-sync.md`, no `SKILL.md`, none declared in `plugin.json`. Release A ships none; resolve for release B.


## Decision Ledger

| # | Branch | Decision |
|---|---|---|
| 1 | Prose-count claims ("a seventh class") in v1 scope? | A: out of v1. Deterministic tier = Rd-signature drift, README/example run diffs, coverage, scannability; prose counts go to the later adversarial skill. Success criterion shrinks: the audit deterministically catches 1 of the 3 PR #133 findings (the refcard signature). |
| 2 | Impact: separate command/module or audit mode? | A: fold into the audit as `--since <tag>` (restricts the Tier C coverage matrix to exports/engines/NEWS items new since the tag). No lib/docimpact; the check_pkgdown overlap is wrapped, not rebuilt. Release A = 1 module + 1 command. |
| 3 | Where does the audit command live? | A: rewrite `/rforge:docs:check` to delegate to `python3 -m lib.docaudit`; keep `[package] [--detailed]`, add `--since`, `--run-examples`, `--site`, `--fail-on`. No new command: count stays 44, no count cascade. Reverses the brainstorm's `docs:audit` plan; CHANGELOG must state the behavior change (improvised prompt -> deterministic checks). |
| 4 | How to detect a stale deployed site? | A: opt-in `--site <url>` compares expected pages (vignettes/articles/*.qmd, man/*.Rd minus internal topics) to the live sitemap.xml; degrades to a warn envelope offline. Commit-sha parsing dropped (deploy-mechanism-dependent). Adds a NETWORK class: mandatory smoke test against the live medfit site (read-only GET) before release. Evidence: medfit man/ = 36 Rd files, live sitemap = 36 reference pages. |
| 5 | Acceptance gate for release A | A: known-answer fixtures (17d976d^/17d976d signature defect; b1f307b^ README via --run-examples) PLUS a read-only hold-out run on current probmed and medrobust (man/ 63 and 55 Rd files), every finding triaged by the maintainer, precision recorded in the SPEC. No numeric precision gate (sample too small). Hold-out reads other repos: state it up front per no-cross-repo-work rule. |
| 6 | (Release B) Where do rforge's authoring skills live? | A: standard root `skills/<name>/SKILL.md` (auto-discovered, as craft; craft's plugin.json declares none). Plumbing required: add `skills/` to package.json `files` (currently commands/, agents/, lib/, docs/, .claude-plugin/, scripts/ - a new dir would miss an npm-packaged install; Homebrew formula installs everything), add a test-all gate (every SKILL.md has frontmatter and ships), verify with `claude plugin validate`. Existing .claude-plugin/skills/validation/description-sync.md is a hot-reload validation script, not a standard skill. |
| 7 | (Release B) Where does cookbook recipe verification live? | A: `cookbook add --with-test` scaffolds a generic package-resident testthat harness (tests/testthat/test-cookbook-recipes.R): chunk extractor, fresh-env runner after the setup chunk, planted-defect control, skip when vignettes absent, NO hardcoded recipe count. `cookbook verify` runs it via the existing rcmd test path. Reason: medfit's test-cookbook-consistency.R hardcodes eleven recipes (## 1. to ## 11.), so any appended recipe would turn its CI red; slow recipes need a time budget/skip tag (medfit excludes 9-11). |
| 8 | (Release B) How do article drafts guarantee no fabricated numbers? | A: drafts express every result via inline R or an executed chunk; unrun values stay `[RUN?]` placeholders; the audit adds a prose-literal lint (estimate-like literals such as `NIE = 0.19`, `[0.08, 0.32]` flagged as candidates, allowlist for legitimate n/tolerances). Reason: executed Quarto chunks cannot go stale, so the exposure is literal numerals in prose and pasted README output. |

## Locked scope (what the SPEC should say)

**Release A: one module, one command, no new command name**

- `lib/docaudit.py` (new public module, pure-stdlib except opt-in `--run-examples`/`--site`) backs a **rewritten `/rforge:docs:check`** (keeps `[package] [--detailed]`; adds `--since <tag>`, `--run-examples`, `--site <url>`, `--fail-on`). Command count stays 44.
- Deterministic checks: documented call signatures vs `man/*.Rd` `\usage{}` (documented arg names must be an ordered subset of formals, so omitted defaults are fine); README/example output vs a real run (opt-in); export/engine x doc coverage matrix, restricted to items new since a tag with `--since`; scannability (advisory); sitemap-vs-source page set (opt-in, NETWORK, degrades to `warn`).
- **Out of v1:** prose-count/ordinal claims ("a seventh class"); commit-sha detection of the deployed site; a separate impact module.
- **Success criterion (rewritten):** the audit deterministically flags the refcard `joint_effects(x, theta)` defect at `17d976d^` and reports 0 errors at `17d976d`; flags the README `NIE = 0.19` block at `b1f307b^` under `--run-examples`; plus a read-only hold-out run on current probmed and medrobust with every finding triaged and precision recorded.

**Release B: authoring (parked behind A)**

- Standard root `skills/<name>/SKILL.md` (+ `package.json` `files` entry + test-all gate + `claude plugin validate`).
- `cookbook add --with-test` scaffolds a generic, count-agnostic testthat harness; `cookbook verify` runs it via rcmd.
- `article` drafts only via inline R/executed chunks, unrun values as `[RUN?]`; the audit's prose-literal lint is the gate.

## Corrections to the brainstorm

| Brainstorm said | Now |
|---|---|
| New `/rforge:docs:audit` + `/rforge:docs:impact` (+2 commands) | Rewrite `docs:check`; impact folds into it as `--since`; command count stays 44 |
| Both known defects found deterministically | Only the refcard signature defect; "seventh class" is out of v1 |
| Deployed-ref via pkgdown commit message | Wrong assumption (medfit uses a GitHub Action message); replaced by sitemap-vs-source |
| "Skills are new to rforge (only skills/validation)" | rforge has no standard skills; plumbing (`files`, gate, validate) is part of release B |

## Open Questions (carry into the SPEC)

1. **`docs:check` default scope.** It is ecosystem-wide today (no `package` arg = whole ecosystem via the manifest). Rewriting it forces a choice: keep an `--eco` sweep as the default, or switch to single-package and document the behavior change. Unresolved; the brainstorm's "single package first" leans the second way.
2. `--run-examples`: numeric tolerance, seed handling and `#>` output normalization when diffing README output vs a real run; execution safety (same posture as `r:test`/`r:check`).
3. Rd-signature matcher scope: S3/S4/S7 methods (`\method{}`, `\S4method{}`), `...`, operators, and extracting calls from `.qmd` code spans vs chunks.
4. `--site` expected-page derivation: `\keyword{internal}`, `@noRd`, pkgdown `reference:` excludes, `.Rmd` vs `.qmd` article naming, redirects.
5. Release B: skill names/triggers; slow-recipe tagging (medfit excludes recipes 9-11 for time); whether `claude plugin validate` actually exercises a root `skills/` dir (verify on the first skill).
6. Hold-out logistics: triage session scheduling; reads probmed/medrobust read-only (state it, no writes).

## Test plan (TDD) — release A, red-first

Tier selection (auto): new parser/script -> **unit**; external dependency (`gh-pages`/site fetch, `Rscript`) -> **dependency + smoke**; changed command frontmatter/flags -> **e2e + dogfood**. count-cascade N/A for A (no new command); release B adds a skills gate.

### unit (tests/test_docaudit.py)
- [ ] **test_rd_usage_parse** — `\usage{}` -> formals incl. defaults  `# TODO(author): delete if not contract-bearing`
- [ ] **test_signature_subset_rule** — `(object, estimates)` vs `(object, estimates = object@estimates)` -> no finding; `(x, theta)` -> `error`
- [ ] **test_since_restricts_coverage** — only items new since the tag appear
- [ ] **test_expected_pages_skip_internal_topics**

### dependency / smoke
- [ ] **test_site_offline_degrades_to_warn** — never raises (as `runiverse`)
- [ ] **test_run_examples_engine_missing** — `engine_missing` envelope (as `rcmd`)
- [ ] **smoke (manual, pre-release):** `docs:check --site https://data-wise.github.io/medfit/` against the live site, read-only GET

### e2e + dogfood (tests/test_docaudit_e2e.py) — must be able to fail
- [ ] **test_known_defect_fixture_flagged** — content of `17d976d^` extracted via `git show` into a tmp dir -> `joint_effects(x, theta)` flagged
- [ ] **test_known_clean_control_zero_errors** — `17d976d` -> 0 errors
- [ ] **test_planted_defect_caught** — a synthetic wrong signature in a fixture is caught (positive control)
- [ ] **test_docs_check_frontmatter_matches_usage** — `arguments:` equals `## Usage`; `_check_commands_doc.py` and `AGENTS.md` mirror still pass

## Documentation & Discoverability — release A (rubric: cheap >=3, heavy >=5 or new surface)

Inputs: 1 new module, config change (`.rforge.yaml` allowlist keys), user-facing CLI flags on an existing command (no new command, no new surface).

- [x] Guide: extend the relevant `docs/guides/*` page (score 4)
- [x] Refcard: `docs:check` flags (score 4)
- [x] Demo: audit on the `17d976d^` fixture (score 3)
- [x] API reference: `docs/reference/docaudit.md` — N/A by the rubric (score 3) but **required** by rforge's public-module convention and the `gen_lib_reference.py --check` gate
- [x] CHANGELOG `[Unreleased]` + `docs/commands.md` — must state the `docs:check` behavior change
- N/A Mermaid (2), Tutorial (4), Cookbook (4), Architecture note (2) — below threshold, no new user-facing surface

Count-cascade exclusion: version and command-count lines stay with `scripts/version_sync.py`.

## Post-grill note (2026-10-11)

A 4-reviewer adversarial pass revised the SPEC to v2 (`SPEC-docs-check-content-audit-2026-10-11.md`, review log at its end).
Grill decisions 1-8 stand. Refinements: decision 4 now derives expected pages from the **deploy ref**, not the working tree;
decision 5 gains a history replay, recall replay, planted defects and explicit blocking criteria. New decisions awaiting
confirmation: D0 (scope rule), D6 (split release A into A1 static + rewrite and A2 `--run-examples`/`--site`), D7
(`signature-named-arg` stays `error`, auto-demoted on any false positive).

## Confirmation round (2026-10-11) — the four open SPEC v2 decisions

| # | Branch | Decision |
|---|---|---|
| C1 | D0: default scope of `docs:check` | A: walk up to the nearest `DESCRIPTION`; at a non-package root sweep only if a manifest exists or `--eco` is passed, else print a hint; hybrid roots audit nested packages too; the resolved scope is the first output line. CHANGELOG must state the change from "ecosystem-wide by default". |
| C2 | D6: one release or split? | A: split. **A1 (v2.21.0)** = static checks (`signature-named-arg`, `signature-names`, `signature-arity`, `coverage`, `scannability`) + `docs:check` rewrite + `--since` + `docs.allowlist` + mechanical gates. **A2 (v2.22.0)** = `--site` (then smoke test) followed by `--run-examples` + `lib/r/docexamples.R`. Moves grill decisions 4 and the examples check one release later; reverses neither. |
| C3 | D7: severity of `signature-named-arg` | A: `error`, auto-demoted to `warn` before release if the history replay or hold-out shows any `error`-severity false positive. Evidence: 0 false positives over 337 named args at HEAD; 20,468 args replayed over 120 commits gave 5 hits, all real. The envelope never blocks, so `error` only affects the exit code under `--fail-on`. |
| C4 | Orchestrator auto-run of `docs:check --site` | A: auto-run, read-only, following the `lib.runiverse` precedent (`agents/orchestrator.md:69-71`). The Step 3 wording "network -> recommend" is reconciled to "network writes -> recommend" in the same change; a positive assertion is added in `tests/_check_agent_engines.py`. `--run-examples` stays recommend-only (executes package code). |

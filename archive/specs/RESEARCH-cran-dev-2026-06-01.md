# RESEARCH: CRAN submission + modern R dev practices (2026) vs rforge v2.1.0

> **⚠️ SUPERSEDED — historical record (banner added 2026-06-20).** The CRAN suite
> this research informed SHIPPED across rforge v2.2.0–v2.14.0 (see CHANGELOG). Kept
> for history only — NOT action-guidance.

> **Type:** Research + recommendations (no code, no spec). Informs planning for the deferred `r:cran-prep` orchestrator and improvements to the v2.1.0 `r:` command surface.
> **Date:** 2026-06-01
> **Scope:** rforge is an R-package *ecosystem orchestrator* (Claude Code plugin). It develops OTHER R packages and has no DESCRIPTION of its own. Commands referenced are the v2.1.0 28-command surface, especially `r:load/document/test/check/coverage/build/install/site/cycle/lint/spell/urlcheck/style`.

---

## PART A — Current (2026) state of CRAN + R dev

### A.1 CRAN submission requirements

**Repository Policy highlights** ([CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html), [Submission checklist](https://cran.r-project.org/web/packages/submission_checklist.html))

- Packages **must pass `R CMD check --as-cran`** under current **R-devel** (R-patched if devel unavailable) **without warnings or significant notes**. ERRORs are unacceptable; WARNINGs and significant NOTEs must be eliminated or explained in `cran-comments.md`.
- **"0/0/0" expectation:** the practical bar (per r-pkgs.org) is *zero errors, zero warnings, zero notes — not almost zero*. ([r-pkgs 22 Releasing to CRAN](https://r-pkgs.org/release.html))
- **Version increment:** every submission (even a rejected resubmission) must bump the version. Increasing it each round is preferred to reduce confusion.
- **Submission frequency:** once established, updates "no more than every 1–2 months." Wait 48h+ after publication before submitting a correction.
- **Size limits:** source tarball ≤ ~10 MB (higher by request); data + docs combined ≤ 5 MB; reasonable compression mandatory.
- **URL/DOI:** DESCRIPTION references use author-year with `<doi:...>`/`<arXiv:...>`/`<https:...>` in angle brackets, year in parens. URLs must be valid, redirect-free where possible, and use verified SSL; avoid rate-limit (HTTP 429/403) endpoints. `--as-cran` runs URL checks.
- **Reverse-dependency obligation:** for API-changing updates the maintainer must check downstream packages still pass, contact affected maintainers **≥ 2 weeks ahead**, and mention this in the submission email.

**Common unavoidable / spurious NOTEs** (list and explain in `cran-comments.md`) ([r-pkg-devel](https://stat.ethz.ch/pipermail/r-package-devel/2020q1/005200.html), [r-pkgs release](https://r-pkgs.org/release.html))

- `New submission` — automatic on first submission; expected, no action.
- `Possibly misspelled words in DESCRIPTION` — CRAN's own spell-checker (not the `spelling` pkg); proper nouns/technical terms are flagged. Explain as intentional.
- `checking CRAN incoming feasibility ... Maintainer: ...` — informational, appears only on incoming checks.
- `Days since last update: <N>` — appears if resubmitting too soon; respect the 1–2 month cadence.
- `installed size is N Mb` / `sub-directories ... large` — for data/doc-heavy packages; explain if irreducible.

**`cran-comments.md`** ([r-pkgs](https://r-pkgs.org/release.html)) — two sections: (1) **R CMD check results** (state error/warning/note counts; list each remaining NOTE with a one-line justification); (2) **Reverse dependencies** (paste `revdep/cran.md`, or state "There are currently no downstream dependencies"). Create with `usethis::use_cran_comments()`. On resubmission, prepend a `## Resubmission` section describing changes.

**revdepcheck** ([r-pkgs](https://r-pkgs.org/release.html), [revdepcheck](https://r-lib.github.io/revdepcheck/)) — one-time `usethis::use_revdep()`; run `revdepcheck::revdep_check(num_workers = 4)`. Outputs in `revdep/`: `README.md`, `problems.md`, `failures.md`, `cran.md`. Helpers `revdep_maintainers()` / `revdep_email()` for mass notification. Note: revdepcheck (the standalone tool) is the modern replacement for `tools::check_packages_in_dir()`.

**Multi-platform pre-submission flow:**

- **win-builder** — `devtools::check_win_devel()` (also `_release`, `_oldrelease`). Builds + checks on Windows R-devel; results emailed. Still the canonical Windows-without-Windows path. ([r-pkgs](https://r-pkgs.org/release.html))
- **macOS builder** — `devtools::check_mac_release()`.
- **R-hub v2** — **v1 (`rhub::check_for_cran()`) is deprecated/defunct.** v2 is GitHub-Actions-based: `rhub::rhub_setup()` writes `.github/workflows/rhub.yaml`, `rhub::rhub_doctor()` validates config, `rhub::rhub_check()` selects from 20+ specialized platforms (clang/gcc/intel R-devel, valgrind, ASAN, macOS-arm64, etc.). Results land in the repo's Actions tab — **no console output, no emails.** For non-GitHub packages, `rhub::rc_submit()` uses shared R-Consortium runners (slower, public). ([R-hub v2 blog](https://blog.r-hub.io/2024/04/11/rhub2/), [rhub reference](https://r-hub.github.io/rhub/reference/rhubv2.html))

**Submission / resubmission etiquette:** use `usethis::use_release_issue()` for a checklist; `devtools::submit_cran()` (or `release()`) uploads; confirm via the emailed link. On rejection: fix, bump patch, add `## Resubmission` to `cran-comments.md`, resubmit. Don't email CRAN maintainers directly except as instructed. Post-acceptance: `usethis::use_github_release()` then `usethis::use_dev_version()`.

### A.2 Modern R package dev practices

- **testthat 3rd edition** ([3e article](https://testthat.r-lib.org/articles/third-edition.html), [3.3.0](https://www.tidyverse.org/blog/2025/11/testthat-3-3-0/)) — opt in via `usethis::use_testthat(3)` (sets `Config/testthat/edition: 3` in DESCRIPTION). Key behaviors: messages bubble to results; `expect_warning()`/`expect_error()` capture **one** condition; `local_reproducible_output()` auto-applied (width 80, no color/unicode); **snapshot tests** (`expect_snapshot()`, `_value()`) record human-readable output in `_snaps/`. 3.3.0: `expect_snapshot()` **fails when creating a new snapshot on CI** (prevents accidental baseline capture), `snapshot_reject()`.
- **lintr + styler** ([goodpractice](https://ropensci-review-tools.github.io/goodpractice/), [styler NEWS](https://github.com/r-lib/styler/blob/main/NEWS.md)) — `lintr` flags style + correctness issues (configurable via `.lintr`); `styler` auto-reformats to tidyverse style. Common CI pattern: lintr as a check, styler as a pre-commit fixer (not a CI gate, since it rewrites).
- **roxygen2 / Rd** — inline `@`-tags compile to `man/*.Rd` + NAMESPACE. CRAN initial-submission expectations: every exported function needs `@returns` (or `\value`) and `@examples`; `@family` builds "See also" cross-links surfaced on pkgdown.
- **pkgdown** — `usethis::use_pkgdown_github_pages()` wires site + GH Actions + Pages. Articles = long-form vignettes; `_pkgdown.yml` controls reference index and article nav.
- **Coverage norms** — `covr` for line coverage; codecov/Coveralls badges; no hard CRAN threshold, but tidyverse/rOpenSci norms target high coverage (often ≥ 90% aspirational, with untested lines justified).
- **CI matrices** — `usethis::use_github_action("check-standard")` produces the r-lib matrix: R-release/-devel/-oldrel × {ubuntu, macOS, windows}. Companion actions: `pkgdown`, `test-coverage`, `lint`.
- **goodpractice** ([goodpractice](https://ropensci-review-tools.github.io/goodpractice/)) — `goodpractice::gp()` bundles R CMD check + lintr + covr + cyclomatic complexity + a curated rule set into one advisory report. Maintained under rOpenSci-review-tools.
- **rOpenSci dev guide** ([devguide](https://devguide.ropensci.org/pkg_building.html)) — canonical aggregator of the above for peer-reviewed packages.

---

## PART B — Gap analysis vs rforge v2.1.0

Coverage of each CRAN / dev-practice requirement by the current command surface. ✅ covered · ⚠️ partial · ❌ missing.

| # | Requirement / practice | rforge command(s) | Status | Notes |
|---|---|---|---|---|
| 1 | `R CMD check --as-cran` (0/0/0) | `r:check`, `r:cycle`, `thorough` | ⚠️ | `r:check` runs rcmdcheck; **need to confirm `--as-cran` / `args=c("--as-cran")` is passed**, not a plain check. `thorough` orchestrates but is single-pkg-shallow on as-cran. |
| 2 | Spell check (`spelling` pkg) | `r:spell` | ✅ | Covers `spelling::spell_check_package()`. Does NOT replicate CRAN's own DESCRIPTION spell-checker (different word list) — acceptable. |
| 3 | URL validity (`urlchecker`) | `r:urlcheck` | ✅ | `urlchecker::url_check()`. Good. Could add redirect-fix mode. |
| 4 | DOI / `<doi:>` formatting in DESCRIPTION | — | ❌ | No DOI-format linting. `--as-cran` catches some; rforge surfaces nothing. |
| 5 | Lint (`lintr`) | `r:lint` | ✅ | |
| 6 | Style (`styler`) | `r:style` | ✅ | |
| 7 | Roxygen regen + NAMESPACE | `r:document`, `r:cycle` | ✅ | Backed by roxygen2. PreToolUse hook blocks hand-edits to `man/*.Rd`. |
| 8 | testthat 3e tests | `r:test` | ⚠️ | Runs testthat; **edition-agnostic** — doesn't detect/warn if pkg is on 2e, nor surface snapshot-on-CI failures distinctly. |
| 9 | Coverage (`covr`) | `r:coverage` | ✅ | Total + per-file + untested lines. No threshold gate. |
| 10 | pkgdown site / articles | `r:site` | ✅ | Builds pkgdown. |
| 11 | Build tarball | `r:build` | ✅ | pkgbuild. |
| 12 | Local install | `r:install` | ✅ | |
| 13 | Version increment + SemVer | `pretooluse.py` hook, `description-sync` skill | ⚠️ | Hook warns on bad SemVer; skill checks DESCRIPTION↔NEWS. No automated `use_version()` bump. |
| 14 | `cran-comments.md` generation | — | ❌ | Not generated or templated. Major gap for `r:cran-prep`. |
| 15 | revdepcheck | — | ❌ | No `r:revdep`. `release`/`deps` model *internal* ecosystem deps, NOT CRAN downstream revdeps. |
| 16 | win-builder submission | — | ❌ | No `r:winbuilder` / `check_win_devel()` wrapper. |
| 17 | R-hub v2 | — | ❌ | No `r:rhub`. GitHub-Actions-based; could be setup + dispatch. |
| 18 | macOS builder | — | ❌ | No wrapper (lower priority). |
| 19 | goodpractice bundle | — | ❌ | No `r:goodpractice`. Overlaps lint+coverage+check but adds complexity/rules. |
| 20 | CI matrix scaffolding | — | ❌ | No `use_github_action`-style scaffolder (overlaps craft's `ci:generate`). |
| 21 | Submission orchestration | `release` (plan only) | ⚠️ | `release` plans *ecosystem submission ordering* by internal deps; does NOT run the per-package CRAN gate sequence. This is exactly the `r:cran-prep` gap. |
| 22 | NEWS.md polish / changelog | `docs:check`, `complete` (cascade) | ⚠️ | Drift checks + cascade exist; no NEWS-for-release formatting. |
| 23 | Initial-submission doc checks (`@returns`/`@examples`, `cph` role) | — | ❌ | No "first CRAN submission" linter (extrachecks-style). |

**Summary:** Strong on the *local dev cycle* (items 1–12 mostly ✅). The **CRAN-submission "last mile" is almost entirely missing**: cran-comments (#14), revdepcheck (#15), win-builder/R-hub (#16–18), `--as-cran` confirmation (#1), and an orchestrator to sequence them (#21). `release` covers *cross-package ordering* but not the *per-package gate*.

---

## PART C — Prioritized recommendations

### Quick wins (< 1 day each)

1. **Confirm/guarantee `--as-cran` in `r:check`.** Verify `lib.rcmd` passes `args = "--as-cran"` to `rcmdcheck::rcmdcheck()`; add an explicit `--as-cran` flag (default on for release context) and surface the as-cran-only NOTEs (incoming feasibility, misspelled DESCRIPTION) distinctly so users know which are expected. *Rationale:* item #1 is the single most important CRAN gate; a plain check silently under-tests.
2. **testthat-edition awareness in `r:test`.** Read `Config/testthat/edition` from DESCRIPTION; warn if not `3`; on CI surface the 3.3.0 "new snapshot created" failure as actionable, not a flaky fail. *Cheap, high signal.*
3. **`r:urlcheck` redirect-fix hint.** `urlchecker::url_update()` can auto-fix redirects; expose a `--fix` flag. Reduces the most common avoidable URL NOTE.
4. **DOI/DESCRIPTION-format lint inside `r:check` output parsing.** Pattern-match the as-cran NOTE text and give a one-line "format DOIs as `<doi:...>`" remediation. No new engine needed.

### Medium (1–3 days)

5. **`r:revdep` — NEW command (BUILD).** Wrap `revdepcheck::revdep_check()` + emit a `revdep/`-summary envelope. *Rationale:* hard CRAN obligation (#15, A.1) with **no overlap** — rforge's existing `deps`/`release` model *internal* ecosystem edges, which is orthogonal to CRAN downstream reverse-deps. Genuinely missing. Gate behind "has reverse deps on CRAN" detection to avoid noise for new packages.
6. **`cran-comments.md` generator (fold into `r:cran-prep`, or standalone helper).** Template the two-section file, auto-fill check-result counts from the `r:check --as-cran` envelope, paste `revdep/cran.md`, and pre-list the known-spurious NOTEs with stub justifications. *Rationale:* item #14, pure text generation, big time-saver.
7. **`r:goodpractice` — NEW command (BUILD, thin).** Wrap `goodpractice::gp()`. *Rationale:* one advisory call surfacing cyclomatic complexity + rule set beyond what lint/coverage/check give. **Overlap caveat:** it re-runs check+lint+covr, so make it opt-in (release context only) and dedupe — don't run it inside `r:cycle`.

### Long-term

8. **`r:cran-prep` — the deferred orchestrator (BUILD).** Sequence (stop at first hard failure; collect soft NOTEs):

   ```
   r:cran-prep  (single package)
     1. r:document          # ensure Rd/NAMESPACE current
     2. r:style (check-only) + r:lint        # style/quality gate (advisory)
     3. r:spell             # spelling pkg
     4. r:urlcheck          # + offer url_update() fix
     5. r:test              # testthat 3e, snapshots clean
     6. r:coverage          # report (advisory threshold)
     7. r:check --as-cran   # THE gate: 0/0/0; classify NOTEs (spurious vs real)
     8. r:revdep            # only if CRAN downstream deps exist
     9. [optional] r:goodpractice   # advisory bundle
    10. multi-platform: dispatch r:winbuilder + r:rhub (async; remind to check results)
    11. generate/refresh cran-comments.md (counts + revdep/cran.md + NOTE justifications)
    12. version bump check (description-sync skill; suggest use_version level)
     ──────────── HANDOFF ────────────
    → /rforge:release   # ecosystem-level: orders THIS pkg's submission
                        #   relative to dependent packages, plans the
                        #   submission wave. cran-prep = per-package gate;
                        #   release = cross-package sequencing.
   ```

   **Hand-off contract:** `r:cran-prep` certifies a *single* package is CRAN-ready and emits a machine-readable "ready/blocked + open NOTEs" envelope; `release` consumes those per-package verdicts to order the multi-package submission wave by internal dependency topology. They compose; neither duplicates the other.

9. **`r:winbuilder` + `r:rhub` — NEW commands (BUILD; pair them).** `r:winbuilder` wraps `devtools::check_win_devel()` (fire-and-remind: results are emailed). `r:rhub` wraps the v2 flow — `rhub_setup()` (idempotent, writes the GH Actions workflow) / `rhub_doctor()` / `rhub_check()`; results land in the Actions tab, so the command should *dispatch + link to the run*, not block on output. *Rationale:* multi-platform testing is expected for non-trivial CRAN submissions (#16–17). **Build** — no overlap with local `r:check`. Note R-hub v2's GitHub-Actions dependency: rforge already assumes packages live in GitHub repos, so this fits.

10. **SKIP / defer:**
    - **`r:macbuilder`** — *skip for now.* `check_win_devel()` + R-hub v2 macOS-arm64 platform cover the gap; standalone mac-builder wrapper is marginal.
    - **CI-matrix scaffolder** — *skip / delegate.* Overlaps craft's `ci:generate`/`ci:detect`. Recommend documenting "use `usethis::use_github_action('check-standard')` or craft's CI commands" rather than reimplementing.
    - **NEWS-polish command** — *defer.* `docs:check` + `complete` cascade partially cover; a dedicated formatter is low ROI vs. the submission-gate gaps.

### Ranked improvement list (highest impact first)

1. **`r:check --as-cran` confirmation + NOTE classification** (quick win #1) — fixes the core gate.
2. **`r:cran-prep` orchestrator** (long-term #8) — the headline deferred feature; ties everything together.
3. **`r:revdep`** (medium #5) — hard CRAN obligation, genuinely missing, no overlap.
4. **`cran-comments.md` generator** (medium #6) — removes manual, error-prone step.
5. **`r:winbuilder` + `r:rhub`** (long-term #9) — expected multi-platform coverage; R-hub v2 fits rforge's GitHub assumption.

*(Runners-up: testthat-3e awareness #2, `r:goodpractice` #7, urlcheck `--fix` #3.)*

---

## Sources

- [CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html)
- [Checklist for CRAN submissions](https://cran.r-project.org/web/packages/submission_checklist.html)
- [r-pkgs.org (2e) — 22 Releasing to CRAN](https://r-pkgs.org/release.html)
- [r-pkgs.org (2e) — 11 Dependencies in practice](https://r-pkgs.org/dependencies-in-practice.html)
- [R-hub v2 blog post](https://blog.r-hub.io/2024/04/11/rhub2/)
- [rhub v2 reference (rhubv2)](https://r-hub.github.io/rhub/reference/rhubv2.html)
- [rhub package site](https://r-hub.github.io/rhub/)
- [revdepcheck](https://r-lib.github.io/revdepcheck/)
- [testthat 3e article](https://testthat.r-lib.org/articles/third-edition.html)
- [testthat snapshotting](https://testthat.r-lib.org/articles/snapshotting.html)
- [testthat 3.3.0 release](https://www.tidyverse.org/blog/2025/11/testthat-3-3-0/)
- [goodpractice (rOpenSci review tools)](https://ropensci-review-tools.github.io/goodpractice/)
- [rOpenSci dev guide — pkg building](https://devguide.ropensci.org/pkg_building.html)
- [styler NEWS](https://github.com/r-lib/styler/blob/main/NEWS.md)
- [DavisVaughan/extrachecks](https://github.com/DavisVaughan/extrachecks)
- [ThinkR prepare-for-cran](https://github.com/ThinkR-open/prepare-for-cran)
- [R-package-devel: misspelled words thread](https://stat.ethz.ch/pipermail/r-package-devel/2020q1/005200.html)

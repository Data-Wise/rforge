# BRAINSTORM: rforge command expansion — beyond the dev cycle

- **Date:** 2026-05-31
- **Context:** The `r:` dev-cycle spec (load/document/test/check/coverage/build/install/site/cycle) is done. This explores *what else* is worth adding. Ideation only — no spec yet.
- **Research:** two parallel agents (usethis/scaffolding + quality/CRAN-release tooling).

## The decisive lens: AI value vs mechanical

A command earns its place only if it adds **parsing or judgement** over just running the R function:

- ✅ **Parseable output** → ADHD report (lint/spell/urlcheck results are structured).
- ✅ **Judgement** → Imports-vs-Suggests, real-typo-vs-WORDLIST, test design.
- ❌ **Pure template** (use_news_md, licenses, canned GH Actions YAML) → just shell out; not command-worthy.

---

## ⚡ Quick wins (cheap — reuse the `lib/rcmd.py` envelope we're already building)

These four are *quality* checks with structured output. Same architecture as `r:check`/`r:test`: R emits JSON → normalize → ADHD report. Marginal cost is tiny once `lib/rcmd.py` exists.

| Command | Engine | Returns | Why |
|---|---|---|---|
| `r:lint` | `lintr::lint_package()` | structured: file/line/col/linter/message | **Best easy win.** Group by file/severity, top offenders. Read-only. |
| `r:spell` | `spelling::spell_check_package()` | data frame: word + locations | AI triages real typos vs add-to-WORDLIST. Common CRAN NOTE. |
| `r:urlcheck` | `urlchecker::url_check()` | data frame: broken/redirected URLs + suggested fix | Frequent CRAN rejection; can auto-fix redirects. |
| `r:style` | `styler::style_pkg()` | side-effect (rewrites files) + changed-file tibble | Auto-format. **Mutates source** → gate behind confirmation; summarize diff. |

> All four are also `flow-cli r` parity-ish (`r spell` exists; lint/style/urlcheck don't even in the dispatcher → net-new capability).

---

## 🔨 Medium effort (real AI judgement — more design needed)

| Command | Engine | Why it's judgement-bearing |
|---|---|---|
| `r:deps-sync` ⭐ | `attachment::att_amend_desc()` + `desc` | **Flagship.** Scan `R/`, tests, vignettes for `library()`/`::`/`@importFrom`; reconcile DESCRIPTION. AI decides Imports vs Suggests, version floors, Remotes for GitHub-only deps. Pairs with existing `deps`/`impact`. |
| `r:create` | `usethis::create_package()` / `create_tidy_package()` | AI fills Title/Description/Authors/License from a one-line intent; picks tidy vs base skeleton. Blank-form chore → one prompt. |
| `r:use-package` | `use_package()` / `use_import_from()` | Add a dep + roxygen `@importFrom` in the right file; AI picks Imports vs Suggests. |
| `r:use-test` | `use_test()` | Scaffold the test file **and draft testthat cases** from the function's signature/branches. |

---

## 🏔️ Long-term (orchestration / heavier)

| Command | What | Notes |
|---|---|---|
| `r:cran-prep` ⭐ | Orchestrator: spell → urlcheck → check → (win/rhub dispatch) → revdep → cran-comments scaffold → version-bump prompt | Single-package pre-submission prep. **Hands off to** `/rforge:release` (which owns ecosystem sequencing). Stops short of actual submit. |
| `r:use-vignette` | `use_vignette()`/`use_article()` + draft prose | Real authorship payoff; bigger AI surface. |
| `r:goodpractice` | `goodpractice::gp()` (~250 checks) | **Overlaps** `r:check` + `r:coverage` (gp runs rcmdcheck + covr internally). Scope down or skip. |
| `r:revdep` | `revdepcheck::revdep_check()` | Only for packages with downstream deps; long-running. Better folded into `/rforge:release`. |
| `r:winbuilder` / `r:rhub` | `check_win_devel()` / `rhub_check()` v2 | Async/email/GitHub-Actions — AI can launch but **can't parse results**. Make them optional steps inside `r:cran-prep`, not standalone. |

---

## 🚫 Skip (documented shell-outs, no AI value)

`use_news_md`, license helpers, `use_cran_comments`, canned `use_github_action("check-standard"/...)`, bare `use_r()`. A docs snippet ("run `usethis::use_news_md()`") beats a command wrapper. CI YAML → defer to craft's `ci:generate`.

---

## Overlap guardrails (don't re-spec existing capability)

- `r:check` already = `R CMD check`; `r:cran-prep` should **call** it, not reimplement.
- `r:coverage` already = covr; `r:goodpractice` would double it.
- `/rforge:release` owns **ecosystem** submission sequencing; `r:cran-prep` is **single-package** local prep. Complementary.

---

## 🎯 Recommended path

1. **Bundle the 4 quality commands** (`r:lint`, `r:spell`, `r:urlcheck`, `r:style`) **into the existing v2.1.0 `r:` feature.** They share `lib/rcmd.py` — adding them now is far cheaper than a second feature later. (`r:style` needs a confirm-gate since it mutates files.)
   - → Bumps the dev-cycle feature from 8 → ~12 new commands.
2. **Then `r:deps-sync`** as its own small spec — the flagship judgement command, naturally extends rforge's dependency theme.
3. **Then a `scaffolding` theme** (`r:create`, `r:use-test`, `r:use-package`, `r:use-vignette`) as a separate spec — different shape (writes files, drafts content) from the run-and-parse commands.
4. **`r:cran-prep`** last — it depends on `r:spell`/`r:urlcheck` existing and on the `/rforge:release` handoff being defined.

**Why this order:** quality commands are the highest value-per-effort (infra already in flight), `deps-sync` is the highest *absolute* value, scaffolding is a coherent separate chunk, and `cran-prep` is the capstone that ties the quality commands + release together.

---

## Open questions

- **Fold the 4 quality commands into v2.1.0, or ship them as v2.2.0?** Folding is cheaper but widens the current PR.
- **`r:style` confirm-gate:** auto-run and show diff, or require `--write` flag (dry-run by default)?
- **Scaffolding scope:** is creating *new* packages (`r:create`) in rforge's mission, or is rforge for *existing* ecosystems only? (Current commands assume existing packages.)

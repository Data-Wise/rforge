# 🚀 CRAN submission with rforge

!!! tip "TL;DR (30 seconds)"
    - **What:** Full per-package CRAN-readiness gate using `r:cran-prep`, then hand off to `/rforge:release`.
    - **Why:** One command sequences document→lint→spell→urlcheck→test→coverage→check(--as-cran)→revdep and writes `cran-comments.md`.
    - **How:** `/rforge:r:cran-prep` → fix blockers → re-run → `--multi-platform` → review `cran-comments.md` → `/rforge:release`.
    - **Next:** [CRAN release prep](cran-release-prep.md) for the ecosystem-level submission order.

> **For whom:** Maintainer preparing a CRAN submission for a single package.
> **Estimated time:** 15 minutes to read; the actual gate takes longer because `R CMD check --as-cran` and `revdepcheck` can take minutes.
> **Prior knowledge:** You have a package that passes basic `r:cycle` checks and want to submit it to CRAN.

## Before you start

You need:

- `r:cycle` passing (document → test → check) — if not, fix those first
- The R packages for each stage installed (rforge reports 🟡 + install hint if anything is missing):
  - `rcmdcheck`, `revdepcheck`, `lintr`, `spelling`, `urlchecker`, `covr`
  - Optional: `goodpractice`, `devtools`, `rhub`

## Step 1: Run the full CRAN-prep gate

```bash
/rforge:r:cran-prep
```

This runs the full sequence in order:

| Stage | Tool | What it checks |
|-------|------|----------------|
| `document` | `roxygen2::roxygenize()` | Rd files + NAMESPACE up to date |
| `lint` | `lintr::lint_package()` | Style and code-quality issues |
| `spell` | `spelling::spell_check_package()` | Typos in documentation |
| `urlcheck` | `urlchecker::url_check()` | Broken or redirected URLs |
| `test` | `testthat::test_local()` | Tests pass with no failures |
| `coverage` | `covr::package_coverage()` | Coverage baseline |
| `check` | `rcmdcheck::rcmdcheck(--as-cran)` | R CMD check with CRAN flags + NOTE classifier |
| `revdep` | `revdepcheck::revdep_check()` | CRAN downstream packages not broken |

**Output — what to look for:**

```markdown
## CRAN-Prep: medfit v2.2.0
### Status: 🔴 blocked

| Stage      | Result |
|------------|--------|
| document   | 🟢 ok  |
| lint       | 🟡 warn — 3 style issues |
| spell      | 🟢 ok  |
| urlcheck   | 🟢 ok  |
| test       | 🟢 ok  |
| coverage   | 🟡 warn — 72% (below 80%) |
| check      | 🔴 error — 1 ERROR |
| revdep     | skipped (check blocked) |

### Blockers
- check: ERROR — R CMD check returned an error

### Next
Fix blockers and re-run `/rforge:r:cran-prep`.
```

## Step 2: Read the blockers and fix them

A **blocked** (🔴) verdict means there are hard errors — CRAN will reject the submission. Fix each blocker before continuing.

!!! warning "Blockers vs. warns"
    - **Blocked (🔴):** Errors or check failures. CRAN will reject. Must fix.
    - **Warn (🟡):** Notes, style issues, low coverage. CRAN may accept but you should review. Fixing is strongly recommended.
    - **Ready (🟢):** All stages pass. You can proceed to submission.

**Common blockers and fixes:**

| Blocker | Likely cause | Fix |
|---------|-------------|-----|
| `check: ERROR` | Code errors surfaced by `--as-cran` | Read the check output, fix code |
| `test: failures` | Tests broken | `r:test` for details, fix test/code |
| `document: error` | Roxygen parsing error | `r:document` for details |
| `revdep: broken` | Downstream packages break | Contact maintainers; document in `cran-comments.md` |

**Common warns (review but not always blockers):**

| Warn | Fix |
|------|-----|
| `lint: style issues` | Run `/rforge:r:style` for auto-fixes, then `/rforge:r:lint` to verify |
| `spell: unknown words` | Add technical terms to `inst/WORDLIST` |
| `urlcheck: redirects` | Update URLs to their final destination |
| `coverage: low` | Add tests for uncovered paths |
| `check: NOTEs (spurious)` | Notes classified as `spurious` by `notes_classified` — expected on first CRAN submission; document in `cran-comments.md` |
| `check: NOTEs (real)` | Notes classified as `real` — address before submitting |

## Step 3: Re-run after fixing

After fixing blockers:

```bash
/rforge:r:cran-prep
```

Iterate until you reach **🟢 ready** or **🟡 warn** (with only acceptable notes).

!!! note "Expected behavior on first CRAN submission"
    First-time CRAN submissions typically get a NOTE like `New submission` — this is classified as `spurious` by the NOTE classifier and is expected. It will appear in `cran-comments.md` with context.

## Step 4: Multi-platform checks (recommended)

Once the local gate is green, optionally dispatch to win-builder and R-hub:

```bash
/rforge:r:cran-prep --multi-platform
```

Or run them individually:

```bash
# Dispatch to win-builder (async — results emailed to DESCRIPTION Maintainer in ~30 min)
/rforge:r:winbuilder

# Dispatch to R-hub v2 (async — results in repo Actions tab)
/rforge:r:rhub
```

!!! note "These are async"
    Both win-builder and R-hub dispatch immediately and return a `🚀 dispatched` status. Results are delivered out-of-band — check your inbox (win-builder) or the repo's Actions tab (R-hub). You do not need to wait for results before proceeding to submission if the local gate is already green.

## Step 5: Review `cran-comments.md`

After a green gate, `cran-comments.md` is generated at the package root. Review it before submitting:

```bash
cat cran-comments.md
```

The file captures:
- The R CMD check result (errors, warnings, notes)
- NOTE classifications (spurious vs. real)
- Reverse-dependency check outcome
- Platform results (if `--multi-platform` was used)

Edit it to add any context that CRAN reviewers need (e.g., explaining a NOTE, or noting that you contacted affected maintainers ahead of an API-breaking change).

## Step 6: Add the advisory goodpractice pass (optional)

For a deeper advisory check beyond the gate, add `--goodpractice`:

```bash
/rforge:r:cran-prep --goodpractice
```

`goodpractice::gp()` re-runs check/lint/coverage plus additional checks (cyclomatic complexity, TODO/FIXME scan, DESCRIPTION completeness). Its findings are advisory — they do not affect the `ready`/`warn`/`blocked` verdict, but surface useful improvements before submission.

## Step 7: Hand off to /rforge:release

With a green gate and reviewed `cran-comments.md`, hand off to the ecosystem-level release planner:

```bash
/rforge:release
```

`/rforge:release` handles cross-package submission ordering — if you have multiple packages, it determines which order to submit them (dependencies first) and estimates the timeline.

!!! abstract "Division of responsibility"
    - `/rforge:r:cran-prep` = single-package gate (runs R, generates `cran-comments.md`)
    - `/rforge:release` = ecosystem ordering (reads `.STATUS`, plans the multi-package sequence)

---

## Full workflow at a glance

```text
1. /rforge:r:cran-prep              # Run the gate
   → 🔴 blocked?  Fix blockers, go to step 1
   → 🟡 warn?     Review notes, fix if real, go to step 2
   → 🟢 ready?    Proceed

2. /rforge:r:cran-prep --multi-platform   # Optional: win-builder + R-hub
   → Check inbox (win-builder) + Actions tab (R-hub) for results

3. Review cran-comments.md         # Edit if needed

4. /rforge:release                 # Plan submission order

5. Submit via CRAN web form        # rforge doesn't upload — you do
```

---

## Related commands

- `/rforge:r:cran-prep` — the full gate (this tutorial)
- `/rforge:r:revdep` — reverse-dependency check only
- `/rforge:r:goodpractice` — advisory best-practice bundle only
- `/rforge:r:winbuilder` — win-builder dispatch only
- `/rforge:r:rhub` — R-hub dispatch only
- `/rforge:release` — ecosystem submission ordering
- `/rforge:r:cycle` — quick dev loop (document → test → check); use before cran-prep
- [CRAN release prep](cran-release-prep.md) — the broader ecosystem release workflow

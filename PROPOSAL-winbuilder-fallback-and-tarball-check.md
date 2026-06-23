# PROPOSAL: winbuilder fallback + tarball-level CRAN check

**Date:** 2026-06-22  
**Source:** medrobust v0.4.0 CRAN-prep debugging session  
**Priority:** High — both issues blocked submission and required manual recovery

---

## Issue 1 — `rforge:r:winbuilder`: broken implementation layer

### What happened

`/rforge:r:winbuilder` calls `python3 -m lib.rcmd --kind winbuilder --path "<path>"`.
That module does not exist on the user's machine → `ModuleNotFoundError`. The skill
produced no useful output and silently failed. Manual recovery required two attempts
because `devtools::check_win_*()` also rejects a `.tar.gz` path (it needs a **package
directory**).

### Root causes

1. `lib.rcmd` is not installed or not on `PYTHONPATH` — the skill has no fallback.
2. The fallback the skill implies ("use devtools") fails if given a tarball path.

### Proposed fix

**A. Add a `devtools` fallback in the skill's `## Process` section:**

```markdown
## Process

Primary (when lib.rcmd is available):
```bash
python3 -m lib.rcmd --kind winbuilder --path "<path>"
```

Fallback (when lib.rcmd is missing — use devtools from the package directory):
```r
pkg_dir <- "<package-directory>"   # NOT a .tar.gz path
devtools::check_win_devel(pkg_dir)
devtools::check_win_release(pkg_dir)
devtools::check_win_oldrelease(pkg_dir)
```
```

**B. In the fallback, make clear the argument must be a directory.** The `argument-hint`
already says `[package]` but the description says "Package path" — add: *(must be a
directory, not a tarball)*.

**C. Detect `lib.rcmd` availability before attempting it:**

```bash
python3 -c "import lib.rcmd" 2>/dev/null && USE_LIB=1 || USE_LIB=0
```

If `USE_LIB=0`, emit a `🟡` warning and fall through to the devtools path automatically
rather than erroring out.

---

## Issue 2 — `rforge:r:cran-prep`: source-tree check misses tarball-level failures

### What happened

`/rforge:r:cran-prep` (and the local strict check invoked manually as
`rcmdcheck::rcmdcheck(args = c("--as-cran", "--run-donttest"))` from the source
directory) returned **0E/0W/1N**. win-builder returned **4 NOTEs** from the same
codebase because it checks the submitted tarball, not the source tree.

The divergence: `devtools::check()` / `rcmdcheck()` on a source directory builds
vignettes into a temp `inst/doc/` before running R CMD check, so CRAN's vignette
scanner sees pre-built outputs. Checking the tarball directly (what win-builder and CRAN
do) skips that step — if `vignettes/` contains sources with no `VignetteBuilder` wired
up and no pre-built `inst/doc/` in the tarball, the scanner fires WARNING + 2 NOTEs.

### Root cause

The `build-hygiene` Tier 4 stage checks for stray files in the **source tree**.
It does NOT:
1. Build a tarball
2. Inspect the tarball contents
3. Run `rcmdcheck` against the tarball

So a package can pass every gate stage and still fail on win-builder/CRAN.

### Proposed fix: add a `tarball-check` stage to `cran-prep`

Between the existing `check` stage and `description`/`build-hygiene`, add:

| Stage | What it does | Blocks `ready`? |
|-------|--------------|-----------------|
| `tarball-check` | `devtools::build()` → `tar -tzf` to inspect contents → `rcmdcheck(tarball, args="--as-cran")` | **yes** (errors/warnings/unexpected NOTEs) |

Implementation sketch:

```r
tarball <- devtools::build(pkg_path, quiet = TRUE)
# Inspect for common leaks
contents <- system2("tar", c("-tzf", tarball), stdout = TRUE)
suspicious <- grep("(\\.quarto|_freeze|\\.html$|_files/)", contents, value = TRUE)
if (length(suspicious) > 0) warn("Tarball contains build artifacts: ", suspicious)

# Check the tarball itself
result <- rcmdcheck::rcmdcheck(tarball, args = c("--as-cran", "--run-donttest"), error_on = "never")
```

**Why this catches what source-tree check misses:**
- Vignette artifact leaks (`.quarto/`, `_freeze/`, pre-built `.html`) that slip past
  `.Rbuildignore` 
- VignetteBuilder misconfiguration (sources in tarball, no `inst/doc/`)
- Non-portable paths from build artifacts

**Output addition:**

```markdown
| tarball-check | 🟢 0E/0W/1N (tarball: medrobust_0.4.0.tar.gz) |
```

or on failure:

```markdown
| tarball-check | 🔴 Tarball check: 1W/2N — vignettes/ in tarball but no inst/doc/ |
```

### Also: add tarball inspection to `build-hygiene` Tier 4

Even if `tarball-check` isn't blocking, `build-hygiene` should optionally build a
tarball and report what's in `vignettes/` vs. what `.Rbuildignore` actually excludes.
This surfaces the delta between "what the dev thinks is excluded" and "what actually
ships."

---

## Summary of changes requested

| Skill | Change | Effort |
|-------|--------|--------|
| `rforge:r:winbuilder` | Add `lib.rcmd` availability check + devtools fallback + clarify arg must be directory | Small |
| `rforge:r:cran-prep` | Add `tarball-check` blocking stage: build → inspect → rcmdcheck(tarball) | Medium |
| `rforge:r:cran-prep` `build-hygiene` | Optionally report tarball contents vs. `.Rbuildignore` diff | Small |

---

## Real-world validation

All three fixes would have caught the medrobust issue without the multi-session
debugging loop:
- `winbuilder` fallback: session would have dispatched on first try
- `tarball-check`: would have flagged `vignettes/.quarto` and missing `inst/doc/`
  before win-builder, saving two PR cycles (PR #25, PR #26)

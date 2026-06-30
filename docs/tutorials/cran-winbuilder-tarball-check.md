# CRAN win-builder + tarball-check walkthrough

> **For whom:** You are preparing an R package for CRAN and want to catch the
> failures that CRAN's incoming checks and win-builder see, *before* you submit.
> **Estimated time:** 10 minutes.
> **Prerequisites:** A working R package with `devtools` installed.

## The problem

Running `devtools::check()` from your source tree can hide real CRAN failures:

- Vignettes are pre-built into `inst/doc/` before R CMD check runs, so missing
  `VignetteBuilder` entries or stray `.quarto/` / `_freeze/` / `.html` artifacts
  are silently present in the built tarball but absent from your clean tree.
- Win-builder uses a different environment; if the plugin's `lib/` directory is
  not on `PYTHONPATH`, the previous `r:winbuilder` implementation failed with a
  bare `ModuleNotFoundError`.

v2.17.0 adds two fixes: a **tarball-check** stage in `r:cran-prep` and a
**WinBuilder fallback** in `r:winbuilder`.

---

## Step 1: Run `r:cran-prep` with the tarball-check stage

From inside your R package directory:

```text
/rforge:r:cran-prep
```

The default stage sequence now includes `tarball-check` between the strict
incoming checks and the Tier-4 advisory stages:

```text
document → lint → spell → urlcheck → test → coverage →
check (as-cran) → check (noSuggests) → check (suggests-only) →
revdep → tarball-check → description / build-hygiene / docs-consistency
```

`tarball-check` does three things:

1. `devtools::build()` produces the source tarball you would actually submit.
2. `tar -tzf` inspects the tarball for files that should have been excluded
   by `.Rbuildignore` (`.quarto/`, `_freeze/`, `.html`, `*_files/`).
3. `rcmdcheck::rcmdcheck(tarball, --as-cran, --run-donttest)` runs R CMD check
   on the tarball itself.

If the tarball contains stray artifacts, you'll see advisory findings like:

```text
🟡 tarball_build_artifact: pkg/vignettes/.quarto/_freeze/index.qmd
```

If the tarball check produces an ERROR, WARNING, or real NOTE, it **blocks**
`r:cran-prep` from returning `ready`.

---

## Step 2: Fix the usual tarball leaks

Most leaks are fixed by adding lines to `.Rbuildignore`:

```gitignore
^\.quarto$
^_freeze$
^docs\/
^README\.html$
^vignettes/.*_files\/
```

After editing `.Rbuildignore`, re-run `r:cran-prep` to confirm `tarball-check`
is clean.

---

## Step 3: Send to Win-builder

Once `r:cran-prep` reports `ready`, submit to win-builder for Windows checking:

```text
/rforge:r:winbuilder
```

`r:winbuilder` normally delegates to `lib/rcmd.py`. If the plugin's `lib/`
folder is not on `PYTHONPATH` (common when you invoke it from inside an R
package directory), v2.17.0 detects this and falls back to calling
`devtools::check_win_devel()` / `check_win_release()` / `check_win_oldrelease()`
directly in R, printing a 🟡 warning that the fallback path was used.

You can also pick a platform:

```text
/rforge:r:winbuilder --platform devel
/rforge:r:winbuilder --platform release
/rforge:r:winbuilder --platform oldrelease
/rforge:r:winbuilder --platform all
```

---

## Step 4: Read the results

Win-builder emails a link when the check finishes. Back in rforge, you can
continue CRAN prep with:

```text
/rforge:r:cran-prep --incoming
```

This adds an additional `check (incoming)` pass that emulates CRAN's post-
acceptance environment.

---

## What changed in v2.17.0

| Before | After |
|--------|-------|
| `r:winbuilder` silently failed with `ModuleNotFoundError` if `lib/` wasn't on `PYTHONPATH` | Falls back to `devtools::check_win_*()` with a clear warning |
| `r:cran-prep` only checked the source tree | New `tarball-check` stage builds + inspects the tarball and runs `rcmdcheck` on it |
| `check_build_hygiene` only scanned the source tree | Now also scans the built tarball for artifact leaks |

---

## Next steps

- **Full CRAN gate:** [CRAN release prep tutorial](cran-release-prep.md)
- **Submission workflow:** [CRAN submission with rforge](cran-submission-with-rforge.md)
- **Command reference:** [CRAN submission guide](../guides/cran-submission.md)

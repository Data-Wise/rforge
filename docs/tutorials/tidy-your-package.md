# Tidy a package with r:tidy

!!! tip "TL;DR (30 seconds)"
    - **What:** run `/rforge:r:tidy` for a "how tidy am I?" report, apply the safe fixes with `--fix`, then fix the rest by hand until every stage is `ok`.
    - **Time:** about 10 minutes.
    - **You need:** an R package. The roxygen and `NEWS.md` stages are static and need no R; the lint, `DESCRIPTION` and style stages use `lintr`, `usethis` and `styler` through R.

`r:tidy` checks a package against tidyverse conventions. **Every stage is advisory and never blocks**, unlike
[`r:cran-prep`](cran-submission-with-rforge.md), which gates a CRAN submission. Without `--fix` it writes nothing to
your package.

The examples below come from a real run on a small demo package with deliberately planted defects, so you can
see what each finding looks like and what clears it.

## Step 1: Run the audit (read-only)

```text
/rforge:r:tidy
```

Or, from a terminal, `python3 -m lib.rcmd --kind tidy --path <package>`. On the demo package the result was
(condensed from the JSON envelope the command returns; the messages are verbatim):

```text
status: warn    package: demopkg 0.2.0    applied: false

lint (tidy)           ok
tidydesc              warn
roxygen_completeness  warn
news_header           warn

[tidydesc] DESCRIPTION would normalize (use_tidy_description()).
[roxygen_completeness] funs.R:11 `scale_it()` is @export'd but missing roxygen tag(s): @examples, @return, @family.
[news_header] Top NEWS.md entry is version 0.1.0, but DESCRIPTION is 0.2.0 — NEWS.md may not have been updated for the current release.
```

`applied: false` confirms nothing was written. `engine_missing` lists any R engine the audit could not find; it was
empty here.

## Step 2: Read the four stages

| Stage | What it checks | `--fix` can repair it? |
|-------|----------------|------------------------|
| `lint (tidy)` | the tidyverse `lintr` preset, grouped by file | no (`r:style` handles formatting) |
| `tidydesc` | whether `usethis::use_tidy_description()` would change `DESCRIPTION` | **yes** |
| `roxygen_completeness` | exported functions missing `@examples`, `@return` or `@family` | no |
| `news_header` | the top `NEWS.md` entry exists and matches the `DESCRIPTION` version | no |

Only `tidydesc` and the `style` stage (added by `--fix`) are safe to automate. A missing `@examples` block or a stale
`NEWS.md` needs a person.

!!! warning "Symptom"
    A large count from `lint (tidy)` on argument names such as `mu.x` or `se.y`.

!!! tip "Fix"
    These are legacy dot.case public arguments. Renaming them is a breaking change, so treat the count as a phased
    migration candidate, not a to-fix-now list.

## Step 3: Apply the safe fixes

`--fix` is **mutating**: it runs `styler` on the package and rewrites `DESCRIPTION` in place. Commit first so that
`git diff` shows exactly what changed.

```text
/rforge:r:tidy --fix
```

On a copy of the demo package this reported `applied: true`, added a `style` stage (`ok`), and changed `DESCRIPTION`
only:

```text
5a6,7
> Imports:
>     stats
7d8
< Imports: stats
```

The roxygen and `NEWS.md` findings were still reported, unchanged. `--fix` does not touch them.

## Step 4: Fix the rest by hand

For the roxygen finding, give the exported function the missing tags:

```r
#' Scale a vector
#'
#' @param x A numeric vector.
#' @return The standardized vector.
#' @examples
#' scale_it(c(1, 2, 3))
#' @family arithmetic
#' @export
scale_it <- function(x) (x - mean(x)) / sd(x)
```

For `news_header`, add an entry for the current version at the top of `NEWS.md`:

```text
# demopkg 0.2.0

* Added scale_it().

# demopkg 0.1.0

* First release.
```

## Step 5: Re-run until it is clean

```text
status: ok    package: demopkg 0.2.0    applied: false

lint (tidy)           ok
tidydesc              ok
roxygen_completeness  ok
news_header           ok
```

No messages and `status: ok` is the goal. Remember to regenerate `man/*.Rd` (`/rforge:r:document`) after editing
roxygen tags, so the help pages match.

## Where it fits

- Run `r:tidy` while developing, before you open a PR. It is a conventions report, not a correctness gate.
- Run [`r:cran-prep`](cran-release-prep.md) when you are preparing a submission. That one blocks.
- To run a single stage on its own, use `/rforge:r:lint --tidy` or `/rforge:r:style`.

## What next

- [R package dev cycle](r-dev-cycle.md): the daily `r:` commands around `r:tidy`.
- [Quality guide](../guides/quality.md): lint, style and spell checks in depth.
- [tidyaudit reference](../reference/tidyaudit.md): the module behind the static stages.

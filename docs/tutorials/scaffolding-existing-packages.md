# 🏗️ Scaffolding for existing packages

!!! tip "TL;DR (30 seconds)"
    - **What:** Three `r:use-*` commands that scaffold a test file, a dependency, and a vignette into an **existing** package.
    - **Why:** Less boilerplate, fewer forgotten steps (NAMESPACE, VignetteBuilder, testthat infra) — and rforge picks `Imports` vs `Suggests` for you.
    - **How:** Everything is **dry-run by default**. Read the plan, then re-run with `--write`.
    - **Safety:** No oracle — generated assertions and prose are `# TODO`. The engine never invents expected values.
    - **Next:** [R package dev cycle](r-dev-cycle.md) to run what you scaffolded.

> **For whom:** R package developer adding a test, a dependency, or a vignette to a
> package that already exists.
> **Estimated time:** 10 minutes.
> **Prior knowledge:** You have an R package (a directory with a `DESCRIPTION` file)
> registered with `/rforge:init`. These commands **do not create packages** — they
> add into one you already have.

## The shared contract

All three commands behave the same way:

| Behavior | Default | Flag |
|----------|---------|------|
| Print the plan, write nothing | ✅ dry-run | — |
| Apply the change | — | `--write` |
| Overwrite an existing target | — | `--force` (diff shown first) |

So the loop is always: **run → read the plan → run again with `--write`**.

---

## Part 1: Author a test — `r:use-test`

Scaffold `tests/testthat/test-<function>.R` for an existing exported function. rforge
drafts a `test_that()` block per branch: the happy path, one per `stop()`, and one per
constrained `@param`.

```bash
# Dry-run: see the planned file
/rforge:r:use-test estimate_effect

# Apply: create the file (sets up testthat 3e infra if absent)
/rforge:r:use-test estimate_effect --write
```

!!! warning "No oracle"
    Assertions are emitted as `# TODO` comments. The engine never invents expected
    values — a delta-method estimate may be `a*b + cov(a,b)`, not `a*b`. After
    `--write`, open `R/estimate_effect.R`, then fill each `# TODO` with a real expected
    value verified against the documented behavior.

Then run the tests you just wrote:

```bash
/rforge:r:test
/rforge:r:coverage   # confirm the new file lifts coverage
```

---

## Part 2: Add a dependency — `r:use-package`

Declare a single dependency. rforge reuses `r:deps-sync`'s usage scan to pick the field:
unconditional use in `R/` → **Imports**; tests/vignettes-only or `requireNamespace()`-guarded
→ **Suggests**. For an `Imports` dep it also inserts an `#' @importFrom <pkg> <symbol>`.

```bash
# Dry-run: see the field decision + reason, plus the planned edits
/rforge:r:use-package rlang

# Apply: write DESCRIPTION (deps_sync writer) + insert @importFrom
/rforge:r:use-package rlang --write
```

The recommendation **and its reason** are always surfaced, so you can override it (e.g.
re-run intending `Suggests` if the package is test-only). After `--write` on an `Imports`
dep, regenerate `NAMESPACE`:

```bash
/rforge:r:document
```

!!! note "Imports vs Suggests, at a glance"
    | Usage detected | Field |
    |---|---|
    | `pkg::` / `library()` / `@importFrom` in `R/` | **Imports** |
    | only in `tests/` or `vignettes/`, or `requireNamespace()`-guarded | **Suggests** |
    | not used yet | **Imports** (default) |

To reconcile **all** dependencies at once instead of adding one named dep, use
[`/rforge:r:deps-sync`](../commands.md#rforgerdeps-sync).

---

## Part 3: Author a vignette — `r:use-vignette`

Scaffold `vignettes/<name>.Rmd`: a knitr skeleton (YAML index entry + engine) plus an
outline seeded from the package Title/Description. Section bodies are `# TODO`.

```bash
# Dry-run: see the planned .Rmd
/rforge:r:use-vignette intro

# Apply: write the .Rmd + register the VignetteBuilder (usethis)
/rforge:r:use-vignette intro --write

# Or create a pkgdown-only article (not built/installed)
/rforge:r:use-vignette advanced --article --write
```

If `usethis` is absent, a manual `usethis::use_vignette()` recipe is printed — non-fatal;
the `.Rmd` is still written. Once you've filled the outline, build the site:

```bash
/rforge:r:site
/rforge:r:check   # confirm the vignette builds under R CMD check
```

---

## Putting it together

A realistic "add a feature, document it" pass:

```bash
/rforge:r:use-package rlang --write     # 1. declare the dep
/rforge:r:document                      # 2. regenerate NAMESPACE
/rforge:r:use-test my_new_function --write   # 3. scaffold tests, then fill the TODOs
/rforge:r:test                          # 4. run them
/rforge:r:use-vignette intro --write    # 5. scaffold a vignette, then expand it
/rforge:r:site                          # 6. build the site
```

## See also

- [`scaffold` reference](../reference/scaffold.md) — the `lib.scaffold` engine behind these commands
- [R package dev cycle](r-dev-cycle.md) — run document/test/check after scaffolding
- [`/rforge:r:deps-sync`](../commands.md#rforgerdeps-sync) — reconcile all deps at once

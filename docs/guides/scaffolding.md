# 🏗️ Scaffolding commands

!!! tip "TL;DR (30 seconds)"
    - **What:** Five `r:use-*` commands that add one piece of structure to an
      **existing** package — a test file, a declared dependency, a vignette, a
      documented dataset, or a citation.
    - **Why:** They handle the boilerplate you forget (NAMESPACE `@importFrom`,
      `VignetteBuilder`, testthat 3e infra, `LazyData`/`Depends`, `inst/CITATION`)
      and pick `Imports` vs `Suggests` for you.
    - **The commands:** `r:use-test` · `r:use-package` · `r:use-vignette` ·
      `r:use-data` · `r:use-citation`.
    - **Dry-run is the default.** Every command prints a plan and writes nothing
      until you re-run with `--write`.
    - **Next:** the task walkthrough — [Scaffolding for existing
      packages](../tutorials/scaffolding-existing-packages.md).

---

## What this family covers

These five commands **add structure into a package you already have** — they are
not `usethis::create_package`. Each one plans a single artifact, prints it for
review, and applies it only on `--write`. The engine emits verifiable *structure*
only: generated test assertions and vignette prose are left as `# TODO`, so no
expected values are ever invented. Content drafting is your job after the plan.

| Command | Scaffolds | `--write` applies |
|---|---|---|
| `r:use-test` | `tests/testthat/test-<fn>.R` — one `test_that()` per branch | Creates the file (+ testthat 3e infra if absent) |
| `r:use-package` | An `Imports`/`Suggests` dep + `@importFrom` | Edits `DESCRIPTION` + inserts the `@importFrom` tag |
| `r:use-vignette` | `vignettes/<name>.Rmd` skeleton + outline | Writes the `.Rmd` + registers the `VignetteBuilder` |
| `r:use-data` | `R/data.R` roxygen stub + `DESCRIPTION` patch | Appends the doc block + patches `LazyData`/`Depends` |
| `r:use-citation` | `inst/CITATION` from `DESCRIPTION` metadata | Writes `inst/CITATION` (creates `inst/` if absent) |

!!! warning "Dry-run is the default — `--write` applies the change"
    Running any `r:use-*` command **without** `--write` only prints the plan; it
    touches no files. Re-run the exact command with `--write` to apply it. For the
    three commands that target a single file (`use-test`, `use-vignette`,
    `use-citation`), `--force` is additionally required to overwrite an existing
    target — the diff is shown first. The loop is always: **run → read the plan →
    run again with `--write`**.

---

## `r:use-test` — draft a testthat file

Scaffold `tests/testthat/test-<function>.R` for an existing exported function.
rforge parses the function and drafts one `test_that()` block per branch: a happy
path, one `expect_error` per `stop()` message, and one skipped edge-case stub per
constrained `@param`.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `<function>` | string | *(required)* | The exported function to scaffold tests for (one per call) |
| `--write` | boolean | `false` | Apply the plan — create the file |
| `--force` | boolean | `false` | Overwrite an existing test file (diff shown first) |

```bash
# Dry-run: print the planned file, write nothing
/rforge:r:use-test estimate_effect

# Apply: create the file (sets up testthat 3e infra if absent)
/rforge:r:use-test estimate_effect --write
```

**Output:** the planned file path plus the drafted `test_that()` blocks. If the
function's definition cannot be located, a minimal stub plus a note is emitted
(never an invented signature).

!!! warning "No oracle — assertions are `# TODO`"
    The engine never invents expected values — a delta-method estimate may be
    `a*b + cov(a,b)`, not `a*b`. After `--write`, open `R/<function>.R` and fill
    each `# TODO` with a real expected value verified against the documented
    behavior.

---

## `r:use-package` — declare one dependency

Add a single dependency to `DESCRIPTION`. The `Imports`-vs-`Suggests` decision
reuses `r:deps-sync`'s usage scan; for an `Imports` dep it also inserts an
`#' @importFrom <pkg> <symbol>` in the file that uses it. The same DCF writer as
`r:deps-sync` performs the `DESCRIPTION` edit.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `<package>` | string | *(required)* | The dependency to declare (one per call) |
| `--write` | boolean | `false` | Apply the change to `DESCRIPTION` + the `@importFrom` |
| `--force` | boolean | `false` | Reserved for symmetry with the other `use-*` commands |

```bash
# Dry-run: show the field decision + reason, plus the planned edits
/rforge:r:use-package rlang

# Apply: write DESCRIPTION (deps_sync writer) + insert @importFrom
/rforge:r:use-package rlang --write
```

**Output:** the field decision (`Imports` or `Suggests`) **with its reason**, so
you can override it (re-run intending `Suggests` if the package is test-only).
After `--write` on an `Imports` dep, run `/rforge:r:document` to regenerate
`NAMESPACE`.

!!! note "Imports vs Suggests, at a glance"
    | Usage detected | Field |
    |---|---|
    | `pkg::` / `library()` / `@importFrom` in `R/` | **Imports** (runtime) |
    | only in `tests/` or `vignettes/`, or `requireNamespace()`-guarded | **Suggests** (optional) |
    | not used yet | **Imports** (default) |

!!! tip "One dep here, all deps in `deps-sync`"
    `r:use-package` adds **one named** dependency. To reconcile **every**
    declared dep against actual usage at once, use
    [`/rforge:r:deps-sync`](../tutorials/dependency-reconciliation.md).

---

## `r:use-vignette` — scaffold a vignette or article

Scaffold `vignettes/<name>.Rmd`: a knitr skeleton (YAML index entry + engine)
plus an outline seeded from the package Title/Description. Section bodies are
`# TODO`. The skeleton mirrors what `usethis::use_vignette` writes; the infra
(the `vignettes/` dir + the `VignetteBuilder` field) is applied separately on
`--write`.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `<name>` | string | *(required)* | The vignette file name (becomes `vignettes/<name>.Rmd`) |
| `--article` | boolean | `false` | Create a pkgdown-only article (not built/installed) instead of a vignette |
| `--write` | boolean | `false` | Apply the plan — write the `.Rmd` + register the `VignetteBuilder` |
| `--force` | boolean | `false` | Overwrite an existing vignette file (diff shown first) |

```bash
# Dry-run: print the planned .Rmd, write nothing
/rforge:r:use-vignette intro

# Apply: write the .Rmd + register the VignetteBuilder (usethis)
/rforge:r:use-vignette intro --write

# Create a pkgdown-only article instead of a built vignette
/rforge:r:use-vignette advanced --article --write
```

**Output:** the planned `.Rmd` (front-matter + outline). If `usethis` is absent,
a manual `usethis::use_vignette("<name>")` recipe is printed — **non-fatal**; the
`.Rmd` is still written. Once you fill the outline, run `/rforge:r:site` to build
and `/rforge:r:check` to confirm it builds under `R CMD check`.

---

## `r:use-data` — document a dataset

Document a package dataset: append a roxygen stub to `R/data.R` (`@title`, a
`@format \describe{}` skeleton, `@source`, and the trailing `"<name>"`
documented-data idiom) and patch `DESCRIPTION` (`LazyData: true` /
`Depends: R (>= 2.10)`).

| Flag | Type | Default | Effect |
|---|---|---|---|
| `<name>` | string | *(required)* | The dataset/object name to document (one per call) |
| `--write` | boolean | `false` | Apply the plan — append to `R/data.R` + patch `DESCRIPTION` |

```bash
# Dry-run: print the roxygen stub + the DESCRIPTION delta
/rforge:r:use-data starwars

# Apply: append to R/data.R (creates it if absent) + patch DESCRIPTION
/rforge:r:use-data starwars --write
```

**Output:** the planned roxygen block plus the `DESCRIPTION` delta. A collision
guard skips the append (and warns) if `R/data.R` already documents the same
`\name`. Note there is **no `--force`** flag on this command.

!!! warning "It documents — it never fabricates the data"
    `r:use-data` does **not** create `data/<name>.rda`. The dataset is yours; the
    command prints the exact `usethis::use_data(<name>)` reminder to produce it.

!!! note "Expected behavior — constraints are preserved"
    The `DESCRIPTION` patch goes through the same constraint-preserving DCF writer
    as `r:use-package` / `r:deps-sync`, so existing version floors like
    `dplyr (>= 1.1.0)` survive untouched.

---

## `r:use-citation` — generate `inst/CITATION`

Scaffold `inst/CITATION` from `DESCRIPTION`. It parses `Title`, `Authors@R` (or a
fallback `Author`), and `Version`, and renders a
`bibentry(bibtype = "Manual", ...)` re-emitting the package's own `person()`
calls **verbatim**.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--write` | boolean | `false` | Apply the plan — write `inst/CITATION` (creates `inst/` if absent) |
| `--force` | boolean | `false` | Overwrite an existing `inst/CITATION` (refused without this flag) |

```bash
# Dry-run: print the planned inst/CITATION
/rforge:r:use-citation

# Apply: write inst/CITATION (refuses to clobber an existing one)
/rforge:r:use-citation --write

# Overwrite an existing inst/CITATION
/rforge:r:use-citation --write --force
```

**Output:** the rendered `bibentry`. Unparseable `Authors@R` degrades to a
`# TODO` author block plus a warning (it never raises).

!!! note "Expected behavior — deterministic, no wall-clock date"
    The year comes from the `DESCRIPTION` `Date:` field if present, else a
    `<YEAR>` TODO placeholder — the output **never** embeds the current date, so
    re-running is reproducible. Replace any `<YEAR>` by hand (or add a `Date:`).

---

## See also

- [Command reference (`commands.md`)](../commands.md) — the terse one-line entry
  for every `r:use-*` command.
- [`scaffold` reference](../reference/scaffold.md) — the `lib.scaffold` engine
  behind these commands (`plan_test`, `plan_package`, `plan_vignette`,
  `scaffold_data`, `scaffold_citation`).
- [Scaffolding for existing packages](../tutorials/scaffolding-existing-packages.md)
  — the task walkthrough that strings these into a real "add a feature, document
  it, ship the data + citation" pass.
- [`/rforge:r:deps-sync`](../tutorials/dependency-reconciliation.md) —
  `r:use-package` declares **one** dep; `r:deps-sync` reconciles **all** of them.

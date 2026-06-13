---
name: rforge:r:use-data
description: Scaffold roxygen docs for a package dataset (R/data.R) and patch DESCRIPTION (LazyData/Depends)
argument-hint: "<name> [--write]"
arguments:
  - name: name
    description: The dataset/object name to document (one per call)
    required: true
    type: string
  - name: write
    description: Apply the plan (append to R/data.R + patch DESCRIPTION). Default is dry-run (prints the plan, writes nothing).
    required: false
    type: boolean
    default: false
---

# R Use Data

Document a package dataset named `<name>` for an **existing** R package. Appends a roxygen
doc stub to `R/data.R` (`@title`, `@format` with a `\describe{}` skeleton, `@source`, and the
trailing `"<name>"` documented-data idiom) and patches `DESCRIPTION` (`LazyData: true` /
`Depends: R (>= 2.10)`).

**Dry-run by default.** `--write` appends the doc and patches DESCRIPTION.
**Never fabricates the data:** the `.rda` is yours — the command emits the exact
`usethis::use_data(<name>)` command to produce it.

`DESCRIPTION` edits go through the shared constraint-preserving writer — existing version
floors (e.g. `dplyr (>= 1.1.0)`) survive.

## Usage

```bash
# Dry-run: print the planned roxygen block + DESCRIPTION delta, write nothing (default)
python3 -m lib.scaffold data --name "<name>" --path "<path>"

# Apply: append to R/data.R (create if absent) + patch DESCRIPTION
python3 -m lib.scaffold data --name "<name>" --path "<path>" --write
```

A collision guard skips appending if `R/data.R` already documents the same `\name` (no
duplicate; warns instead).

## What you do after the plan

1. Generate the data and save it: `usethis::use_data(<name>)` (creates `data/<name>.rda`).
2. Fill each `# TODO` in the roxygen block (title, `\describe{}` variables, source).
3. Run `/rforge:r:document` to regenerate `man/<name>.Rd`.

## Related Commands

- `/rforge:r:document` — regenerate the Rd file from the new roxygen
- `/rforge:r:check` — confirm the data + docs pass R CMD check
- `/rforge:r:deps-sync` — reconcile DESCRIPTION after edits

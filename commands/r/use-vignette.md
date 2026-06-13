---
name: rforge:r:use-vignette
description: Scaffold a vignette skeleton (usethis infra) and draft an outline from the package purpose
argument-hint: "<name> [--article] [--write] [--force]"
arguments:
  - name: name
    description: The vignette file name (becomes vignettes/<name>.Rmd)
    required: true
    type: string
  - name: article
    description: Create an article (pkgdown-only, not built/installed) instead of a vignette
    required: false
    type: boolean
    default: false
  - name: write
    description: Apply the plan (write the .Rmd + register the VignetteBuilder). Default is dry-run.
    required: false
    type: boolean
    default: false
  - name: force
    description: Overwrite an existing vignette file (diff shown first)
    required: false
    type: boolean
    default: false
---

# R Use Vignette

Scaffold `vignettes/<name>.Rmd` for an **existing** package: a knitr skeleton (YAML index entry +
engine) plus a drafted outline seeded from the package Title/Description. Section bodies are
`# TODO` for you to expand.

**Dry-run by default.** `--write` writes the file and registers the `VignetteBuilder` via guarded
`usethis`; `--force` overwrites. `--article` creates a pkgdown-only article instead.

## Usage

```bash
# Dry-run: print the planned .Rmd, write nothing (default)
python3 -m lib.scaffold vignette --name "<name>" --path "<path>"

# Apply: write the .Rmd, then register the builder (usethis infra)
python3 -m lib.scaffold vignette --name "<name>" --path "<path>" --write
python3 -m lib.usethis_infra vignette --name "<name>" --path "<path>"

# Create a pkgdown-only article instead of a built vignette
python3 -m lib.scaffold vignette --name "<name>" --path "<path>" --article --write

# Overwrite an existing vignette
python3 -m lib.scaffold vignette --name "<name>" --path "<path>" --write --force
```

If `usethis` is absent, the infra step prints a manual `usethis::use_vignette("<name>")` recipe —
**non-fatal**; the `.Rmd` is still written.

## Related Commands

- `/rforge:r:site` — build the pkgdown site (vignettes → articles) once you've filled the outline
- `/rforge:r:check` — confirm the vignette builds under `R CMD check`

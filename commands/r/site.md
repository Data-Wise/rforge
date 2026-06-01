---
name: rforge:r:site
description: Build the pkgdown website (vignettes→articles); optional preview
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: preview
    description: Open the built site (pkgdown::preview_site)
    required: false
    type: boolean
    default: false
  - name: strict
    description: Fail-fast config check (check_pkgdown) for CI
    required: false
    type: boolean
    default: false
  - name: articles-only
    description: Build only articles/vignettes (reinstalls first)
    required: false
    type: boolean
    default: false
  - name: devel
    description: Fast in-process build via load_all (lower fidelity)
    required: false
    type: boolean
    default: false
---

# R Package Website

Validate (`pkgdown_sitrep`, or `check_pkgdown` with `--strict`) then build the site.
`pkgdown` is optional — if `engine_missing` includes `pkgdown`, report 🟡 + hint.
Needs `pandoc` to render vignettes; if absent, report 🟡 with the pandoc hint.

## Process
```bash
python3 -m lib.rcmd --kind site --path "<path>"   # + --preview / --strict / --articles-only / --devel
```

## Output Format
```markdown
## Website: {package} v{version}
### Status: {🟢 built clean / 🟡 built with problems / 🔴 build failed}
- Checked: {site.checked} · Built: {site.built}
{If status 🔴: "### Vignette/render errors" — point at the failing .Rmd from messages}
{If site.problems: "### Config/index problems" — list each (url, un-indexed topics)}
### Recommended Actions
{Fix problems, or "Site built to docs/ ✅"}
```

## Related Commands
- `/rforge:r:document` — ensure Rd docs exist before building the site

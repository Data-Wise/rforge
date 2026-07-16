---
name: rforge:r:tidy
description: Tidyverse-conventions audit — lint preset + DESCRIPTION normalization preview + roxygen completeness + NEWS.md header (advisory, never blocks)
argument-hint: "[package] [--fix]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: fix
    description: Auto-fix what's safe — runs styler on the package and applies the DESCRIPTION normalization to the real file instead of previewing it. MUTATING.
    required: false
    type: boolean
    default: false
---

# R Package Tidyverse-Conventions Audit

A "how tidy am I?" report — **all four stages are advisory and never block**,
unlike `/rforge:r:cran-prep`. Read-safe by default: without `--fix`, nothing
on disk is touched.

## Process
```bash
python3 -m lib.rcmd --kind tidy --path "<path>"

# Auto-fix what's safe (styler + DESCRIPTION normalization, MUTATING)
python3 -m lib.rcmd --kind tidy --path "<path>" --fix
```

## Stages

| Stage | What it does | Writes files? |
|-------|--------------|----------------|
| `lint (tidy)` | tidyverse lintr preset (`--tidy` on `r:lint`) — additions grouped by file | no |
| `tidydesc` | `usethis::use_tidy_description()` preview (scratch-dir diff) — or applied with `--fix` | only with `--fix` |
| `style` | **only with `--fix`** — `styler::style_pkg()` | only with `--fix` |
| `roxygen_completeness` | exported (`@export`) functions missing `@examples`/`@return`/`@family` | no |
| `news_header` | top `NEWS.md` entry matches `## Package X.Y.Z` and its version matches DESCRIPTION | no |

Without `--fix`, `tidydesc` runs against a **scratch copy** of DESCRIPTION
only — the real file is never touched, and the envelope reports whether it
*would* change (`tidydesc.changed`). `--fix` applies it for real, in place,
and also runs `style` (both are real writes at that point).

`roxygen_completeness` and `news_header` are pure static analysis (no R
required, no `--fix` behavior — there's no safe auto-fix for a missing
`@examples` block or a stale NEWS.md entry; those need a human).

!!! note "Legacy dot.case API arguments"
    `object_name_linter` findings on public-API arguments (e.g. `mu.x`, `se.y`)
    can't be renamed without a breaking release. The `lint (tidy)` stage
    surfaces these as a per-file count, not raw hit-by-hit noise — treat a
    large count here as a phased-migration candidate, not a to-fix-now list.

## Output Format
```markdown
## Tidy: {package} v{version}
### Status: {🟢 ok / 🟡 warn}
| Stage | Result |
|-------|--------|
{one row per stages[] with its status dot}
{messages[], one bullet each, prefixed [stage-name]}
### Next
{If --fix was NOT used and tidydesc.changed or lint.tidy.count>0: "→ re-run with --fix to apply the safe fixes"}
{roxygen_completeness / news_header findings always need manual attention — never auto-fixed}
```

## Related Commands
- `/rforge:r:lint --tidy` — just the lint-preset stage, on its own
- `/rforge:r:style` — just the styler stage, on its own
- `/rforge:r:cran-prep` — the CRAN-readiness gate (blocking); `r:tidy` is advisory-only and separate

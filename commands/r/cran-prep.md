---
name: rforge:r:cran-prep
description: Per-package CRAN gate — document→lint→spell→urlcheck→test→coverage→check (+strict noSuggests/suggests-only passes)→Tier 4 advisory→revdep, writes cran-comments.md
argument-hint: "[package] [--goodpractice] [--multi-platform] [--no-revdep] [--incoming]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: goodpractice
    description: Also run the advisory goodpractice bundle
    required: false
    type: boolean
    default: false
  - name: multi-platform
    description: Dispatch win-builder + R-hub (async)
    required: false
    type: boolean
    default: false
  - name: no-revdep
    description: Skip the reverse-dependency check
    required: false
    type: boolean
    default: false
  - name: incoming
    description: Add the opt-in CRAN-incoming check pass (check (incoming)) on top of the default strict flavor passes
    required: false
    type: boolean
    default: false
---

# R Package CRAN-Prep Gate

Run the full per-package CRAN-readiness sequence and generate `cran-comments.md`.
Composes with `/rforge:release` (this = single-package gate; release = cross-package
submission ordering).

## Process
```bash
python3 -m lib.rcmd --kind cran-prep --path "<path>"   # + --goodpractice / --multi-platform / --no-revdep / --incoming
```

## Stage sequence

By default the gate runs (in order):

| Stage | What it does | Blocks `ready`? |
|-------|--------------|-----------------|
| `document` → `lint` → `spell` → `urlcheck` → `test` → `coverage` | dev-cycle + quality stages | per their existing semantics |
| `check` | `R CMD check --as-cran` + NOTE classifier | yes (errors / real NOTEs) |
| `check (noSuggests)` | strict flavor pass — `_R_CHECK_DEPENDS_ONLY_=true` + `--run-donttest` | **yes** |
| `check (suggests-only)` | strict flavor pass — `_R_CHECK_SUGGESTS_ONLY_=true` + `--run-donttest` | **yes** |
| `check (incoming)` | **opt-in (`--incoming`)** — CRAN-incoming `_R_CHECK_*` bundle | yes (only when requested) |
| `description` | Tier 4 — DESCRIPTION incoming nits (non-`Authors@R`/no `cph`, weak/echoed `Title`, `Description` not a complete sentence, stale `Date`) | **no — advisory** |
| `build-hygiene` | Tier 4 — planning/dev docs that would ship in the tarball; emits the exact `.Rbuildignore` regex to add | **no — advisory** |
| `docs-consistency` | Tier 4 — lightweight advisory staleness/dangling-ref check | **no — advisory** |
| `revdep` | reverse-dependency check (skip with `--no-revdep`) | yes |

Also runs by default: **Tier 1b** — verify the PDF reference manual builds; `warn` (never
block) if no LaTeX is available.

**Strict passes (Tier 2) run BY DEFAULT.** A strict-pass **ERROR blocks the `ready`
verdict** and appends the blocker `noSuggests/donttest check failed (Suggests used
unconditionally?)`. Mechanism: `rcmdcheck`'s `env=` named vector — no `devtools`, no
subprocess-layer change. These are the same passes `/rforge:r:check --strict` runs.

**Tier 4 stages (`description`, `build-hygiene`, `docs-consistency`) are pure-Python,
advisory, and NEVER block `ready`** — they surface as `warn` only. (A build-hygiene finding
can still block *indirectly* once R's own "non-standard top-level files" NOTE fires in the
`check` stage.) Backed by the pure-stdlib `lib/cranlint.py` module.

!!! warning "Behavior change — a package that is `ready` today can turn `blocked`"
    Because the strict flavor passes now run by default, a package that reports 🟢 `ready`
    under `--as-cran` alone can turn 🔴 once the `check (noSuggests)` pass detects a
    `Suggests` package used unconditionally. This is intended.

    **Fix:** A `Suggests` package is used unconditionally. Move it to `Imports`, or guard with
    `requireNamespace()` in code **and** `skip_if_not_installed()` in tests.

`--incoming` adds the opt-in `check (incoming)` row on top of the default strict passes.

## Output Format
```markdown
## CRAN-Prep: {package} v{version}
### Status: {🟢 ready / 🟡 warn (open notes) / 🔴 blocked}
| Stage | Result |
|-------|--------|
{one row per stages[] with its status dot}
{If blockers: "### Blockers" list}
{If dispatched: "### Dispatched (async)" — winbuilder/rhub + where to check}
- cran-comments.md: {cran_comments_path}
### Next
{If ready: "→ hand off to /rforge:release for submission ordering"}
{else: fix blockers and re-run}
```

## Related Commands
- `/rforge:release` — ecosystem-level submission ordering (consumes this verdict)
- `/rforge:r:revdep`, `/rforge:r:check`, `/rforge:r:winbuilder`, `/rforge:r:rhub` — individual stages
- `/rforge:r:cycle` — quick dev loop (doc→test→check); cran-prep is the submission gate

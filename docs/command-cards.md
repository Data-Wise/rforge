# Command Quick-Reference Cards

Handy one-line descriptions grouped by purpose.

## Health & onboarding

| Command | What it does |
|---------|-------------|
| `/rforge:init` | Register an R package as the active context |
| `/rforge:status` | Health snapshot of your R package ecosystem |
| `/rforge:detect` | Discover R packages in a directory tree |
| `/rforge:next` | Suggest the next most useful action |
| `/rforge:capture` | Capture a task or idea into `.STATUS` |
| `/rforge:complete` | Mark a task complete and cascade doc updates |
| `/rforge:restore` | Recap a single R package's state (read-only) |
| `/rforge:finish` | Sync `.STATUS` from current state (dry-run by default) |

## Analysis

| Command | What it does |
|---------|-------------|
| `/rforge:quick` | Fast 10-second ecosystem sanity check |
| `/rforge:thorough` | Deep multi-package assessment (~2 min) |
| `/rforge:analyze` | Analyze a specific change or area |
| `/rforge:impact` | Assess blast radius of a planned change |
| `/rforge:health` | Health metrics across the ecosystem |

## Orchestration

| Command | What it does |
|---------|-------------|
| `/rforge:deps` | Map the dependency graph of your ecosystem |
| `/rforge:cascade` | Plan a multi-package rollout in topological order |
| `/rforge:release` | Generate a CRAN submission order for the ecosystem |

## R package dev cycle

| Command | What it does |
|---------|-------------|
| `/rforge:r:cycle` | Run the dev cycle: document → test → check |
| `/rforge:r:check` | Run R CMD check (with --as-cran / --strict) |
| `/rforge:r:test` | Run testthat suite |
| `/rforge:r:document` | Regenerate documentation via roxygen2 |
| `/rforge:r:load` | Load the package via pkgload |
| `/rforge:r:build` | Build the package binary |
| `/rforge:r:install` | Install the package locally and report the version |

## Quality

| Command | What it does |
|---------|-------------|
| `/rforge:r:lint` | Run lintr on R/ and tests/ |
| `/rforge:r:spell` | Run spelling check |
| `/rforge:r:style` | Auto-format code via styler |
| `/rforge:r:urlcheck` | Check URLs in documentation |
| `/rforge:r:coverage` | Calculate test coverage |
| `/rforge:r:goodpractice` | Advisory best-practices check |
| `/rforge:r:tidy` | Tidyverse-conventions audit (advisory, never blocks) |

## CRAN submission

| Command | What it does |
|---------|-------------|
| `/rforge:r:cran-prep` | Multi-stage CRAN readiness gate |
| `/rforge:r:winbuilder` | Dispatch async Windows check |
| `/rforge:r:rhub` | Dispatch multi-platform check |
| `/rforge:r:revdep` | Run reverse-dependency checks |
| `/rforge:r:submit` | GitHub pre-release + CRAN handoff |

## S7 review

| Command | What it does |
|---------|-------------|
| `/rforge:r:s7-review` | Check S7 OOP conventions (static) |
| `--eco` | Cross-package contract checking |
| `--runtime` | Runtime dispatch checks |

## Diff-aware

| Command | What it does |
|---------|-------------|
| `/rforge:r:check --changed` | Check only changed packages |
| `/rforge:r:test --changed` | Test only changed packages |
| `/rforge:r:lint --changed` | Lint only changed packages |

## Documentation & site

| Command | What it does |
|---------|-------------|
| `/rforge:docs:check` | Audit README/vignette calls and signatures against the exports |
| `/rforge:r:site` | Build the pkgdown site; `--check-leaks` lints the render surface, `--deploy` is recommend-only |

## Ecosystem

| Command | What it does |
|---------|-------------|
| `/rforge:r:deps-sync` | Reconcile DESCRIPTION vs usage (dry run; `--write` applies) |
| `/rforge:deps` | Visualize the dependency graph |
| `/rforge:r:submit --universe` | Check R-universe early-access build status |

## Scaffolding

| Command | What it does |
|---------|-------------|
| `/rforge:r:use-test` | Draft a test file |
| `/rforge:r:use-package` | Add a dependency to DESCRIPTION |
| `/rforge:r:use-vignette` | Scaffold a vignette |
| `/rforge:r:use-data` | Document a dataset |
| `/rforge:r:use-citation` | Scaffold a CITATION file |

→ See the [full Reference Card](REFCARD.md) for detailed descriptions and flags.

Optional docs audit: `--site URL` plus optional local `--ref REF`;
`--run-examples --examples-budget-seconds N` for supervised root README replay.
Default remains static. Inspect stage coverage; unpaired rendered assertions and
unsupported options are incomplete. Complete A2 warnings gate warn, incomplete
stages gate warn/error. No site build/deploy/fetch; example replay is opt-in.

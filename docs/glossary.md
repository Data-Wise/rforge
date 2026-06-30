# Glossary

Terms used across the rforge documentation and plugin output.

## A–C

**advisory**
:   A finding or stage that is surfaced for awareness but never blocks a `ready`
    verdict. Examples: Tier 4 `cran-prep` stages, S7 review findings, build-hygiene
    notes. Contrast with **blocking**.

**blast radius**
:   The set of packages that depend on a changed package. Calculated by
    `lib.deps` from the ecosystem manifest and `DESCRIPTION` `Imports`/`Suggests`.

**blocking**
:   An error or finding that prevents a `ready` verdict. In `r:cran-prep`,
    `ERROR`s and `WARNING`s (and real `NOTE`s under `--strict`) are blocking.
    Contrast with **advisory**.

**cascade**
:   A planned multi-package rollout in topological order — update a leaf package
    first, then propagate changes up the dependency chain.

**changed scope**
:   A mode that restricts commands (`r:check`, `r:test`, `r:lint`) to packages
    that differ between `HEAD` and a merge-base (typically `dev`). Tags findings
    `[introduced]` / `[pre-existing]` / `[uncommitted]`.

**cran-prep**
:   The `r:cran-prep` command — a multi-stage gate that runs the full dev cycle,
    strict checks, incoming checks, and blocking Tier 4 stages before reporting
    `ready` / `warn` / `blocked`.

## D–F

**diff-aware**
:   The per-package baseline caching system (`lib.changed`) that compares current
    results against a merge-base baseline to distinguish findings you introduced
    from pre-existing debt.

**discovery**
:   The `lib.discovery` module that detects R packages in a workspace via
    `DESCRIPTION` files and builds an ecosystem map.

**ecosystem**
:   A set of related R packages under a common manifest (`.rforge.yaml`). The
    manifest defines the root path, package directories, and optional config
    (CRAN mirror, R version pin).

**envelope**
:   The uniform JSON output format used by all `lib/` modules. Contains a
    `verdict` (`ok` / `warn` / `error`), a list of findings, and metadata.
    Normalized by the `formatters` module for CLI display.

**goodpractice**
:   An advisory `r:goodpractice` run using the `goodpractice` R package. Reports
    best-practice suggestions; does not affect `cran-prep` `ready` verdict.

## G–L

**gate**
:   A structured sequence of stages with a pass/fail/warn verdict. `r:cran-prep`
    is the primary gate; each stage can be blocking or advisory.

**guard (branch)**
:   A local git hook (`branch-guard.sh`) that enforces branch policies —
    no code commits on `main` or `dev`, no force-pushes to protected branches,
    no destructive commands in commit messages.

**guard (site leak)**
:   The site-leak guard in `lib.sitelint` that scans a pkgdown render surface for
    untracked artifacts (stale `.html`, leaked `_freeze/` directories).

**impact**
:   The `rforge:impact` command that assesses the blast radius of a planned change
    — which packages break, and severity.

## M–O

**manifest**
:   The `.rforge.yaml` file at the ecosystem root. Defines the discovery path,
    package list, CRAN mirror, R version pin, and site-leak allowlist.

**MCP (Model Context Protocol)**
:   The protocol rforge used before v1.3.0. Replaced by pure-Python `lib/` modules;
    no MCP server is needed or supported.

**merge-base baseline**
:   A per-package cached checkpoint of check/test/lint results at the merge-base
    commit (`dev`). Used by the diff-aware system to classify findings.

**orchestrator**
:   The agent that accepts goals (e.g. "is this CRAN-ready?") instead of specific
    commands. Runs read-only analyses in parallel, then synthesizes one summary.

## P–R

**package context**
:   State stored in `~/.rforge/context.json` — the active package path, version,
    and status. Set by `r:init`, read by most `r:` commands.

**pkgdown deploy guard**
:   A feature of `r:site --deploy` that builds the site in a temporary worktree
    (excluding untracked files), then pushes only the `gh-pages` branch.
    See `lib.sitelint`.

**preset (R-hub)**
:   A named group of R-hub platforms defined in `lib/rhub.py`. Override via
    `--preset`; list presets with `_RHUB_PRESETS`.

**rcmd**
:   The `lib.rcmd` module that shells out to R engines (`rcmdcheck`, `pkgbuild`,
    `testthat`, `lintr`, etc.) and normalizes results into envelopes.

**revdep**
:   Reverse-dependency check (`r:revdep`). Runs `R CMD check` on packages that
    depend on yours — a CRAN requirement before submission.

**R-universe**
:   A CRAN-like build service at <https://r-universe.dev>. `r:submit --universe`
    checks your package's R-universe build status (read-only; never uploads).

## S–Z

**S7 review**
:   The `r:s7-review` command that checks S7 OOP conventions — naming, validators,
    method signatures, legacy S3 compatibility, documentation. Supports `--eco`
    (cross-package) and `--runtime` (needs R) modes.

**snippet (R)**
:   A helper function in `lib/rsnippets.py` that generates R code as a string for
    `lib.rcmd` to execute. Not used externally.

**stage**
:   A single step within a gate (e.g., `document`, `lint`, `check`, `revdep`).
    Each stage produces an envelope; the gate rolls them up.

**tarball check**
:   A `cran-prep` stage that builds a source tarball via `devtools::build()`,
    inspects it for leaked artifacts, then runs `rcmdcheck` on the tarball
    (not the source tree). Catches build leaks that a source-tree check masks.

**Tier 4 stage**
:   Advisory stages in `cran-prep`: `description`, `build-hygiene`,
    `docs-consistency`. Pure-Python, no R needed, never block `ready`.

**verdict**
:   The overall outcome of an envelope: `ok` (green), `warn` (yellow), or
    `error` (red). Rolled up by gates from individual stage verdicts.

**win-builder**
:   CRAN's Windows build service. `r:winbuilder` dispatches a check to
    win-builder and emails results (via the R `devtools::check_win_*()` path).

# SPEC: Scaffolding theme — `r:use-test` / `r:use-package` / `r:use-vignette`

- **Status:** Draft — awaiting user review
- **Target version:** unscheduled candidate (post-v2.6.0; builds on `r:deps-sync` v2.5.0 — see Dependencies)
- **Date:** 2026-06-10
- **Author:** brainstormed with Claude, grounded in `BRAINSTORM-r-command-expansion-2026-05-31.md`
- **Related:** [SPEC-r-deps-sync-2026-06-10.md](SPEC-r-deps-sync-2026-06-10.md),
  [SPEC-diff-aware-checks-and-coverage-2026-05-31.md](SPEC-diff-aware-checks-and-coverage-2026-05-31.md) (P4 origin),
  `lib/rcmd.py`, `lib/deps_sync.py` (planned)

## Summary

A coherent **authoring** theme: three commands that *scaffold + draft* package artifacts for an
**existing** package — `r:use-test` (a `testthat` file + drafted cases), `r:use-package` (add a
declared dependency + `@importFrom`), and `r:use-vignette` (a vignette skeleton + drafted prose).
They share one shape distinct from the run-and-parse `r:` commands: they **write files**, so they
are **dry-run by default** and apply only with `--write`. Engine is **hybrid** — `usethis::` for the
infra it does correctly (testthat edition, vignette builder), pure-Python + AI for simple file
creation and content drafting. Commands 33 → **36** (+3).

## Motivation

rforge runs and validates the dev cycle but can't *author* the artifacts that cycle checks. Per the
2026-05-31 brainstorm (and the diff-aware spec's P4), after changing a function a maintainer
hand-writes the test file and fixtures, hand-edits `DESCRIPTION` + roxygen to add a dep, and
hand-starts vignettes — mechanical chores with real AI value in the *content* (drafting `testthat`
cases from a signature, picking `Imports` vs `Suggests`, outlining vignette prose). `craft:test:gen`
exists but is not R/`testthat`/S7-aware. These three commands fill that gap while staying within
rforge's mission of serving **existing** ecosystems (no package *creation* — `r:create` is out, see
Non-goals).

## Goals

- `r:use-test <fn>` — ensure `testthat` infra, create `tests/testthat/test-<fn>.R`, and **draft**
  `test_that()` blocks (happy path, each documented `stop()`, `@param`-constraint edge cases) from
  the function's signature + roxygen + argument classes (S7/S4).
- `r:use-package <pkg>` — add `<pkg>` to `DESCRIPTION` (AI picks `Imports` vs `Suggests`) and insert
  the roxygen `@importFrom` in the right `R/` file.
- `r:use-vignette <name>` — scaffold the vignette (`usethis` infra) and **draft** an outline/prose
  from the package's purpose.
- All three: **dry-run by default**, apply with `--write`; never overwrite an existing file without
  `--force`.

## Non-goals

- **No `r:create`.** Creating *new* packages is out of scope — rforge serves existing ecosystems
  (decided 2026-06-10). Revisit only if rforge's mission changes.
- **No oracle.** `r:use-test` drafts *structure*, not expected values — assertions are emitted as
  `# TODO`. (A real bug: a test asserting the naive `a*b` for a delta-method estimate that is
  actually `a*b + cov(a,b)` — generated assertions must not be trusted.)
- **No reconcile-everything.** `r:use-package` adds *one named* dep; scanning + reconciling *all*
  usage is `r:deps-sync`'s job. Complementary, not overlapping.
- **No auto-write by default**, no interactive prompts (dry-run + `--write`, agent/TTY-safe).

## Scope

### In scope (decided)

| Command | usethis (infra) | Python + AI (content) | Writes |
|---|---|---|---|
| `r:use-test <fn>` | `use_testthat(3)` if testthat absent | draft `test_that()` blocks from signature/roxygen/arg-classes; assertions = `# TODO` | `tests/testthat/test-<fn>.R` |
| `r:use-package <pkg>` | — (pure-Python via shared writer) | pick `Imports`/`Suggests`; choose the `R/` file for `@importFrom` | `DESCRIPTION` + one `R/*.R` roxygen block |
| `r:use-vignette <name>` | `use_vignette()`/`use_article()` (builder config, skeleton) | draft outline/prose from package purpose | `vignettes/<name>.Rmd` + `DESCRIPTION` VignetteBuilder |

All accept `--write` (apply; default dry-run) and `--force` (overwrite existing).

### Out of scope (YAGNI / deferred)

- `r:create` / `r:use-data` / `r:use-r` (bare file creation with no AI value — a docs snippet beats a wrapper).
- Rewriting/regenerating `man/*.Rd` — that's `r:document`'s job (and the hook blocks hand-edits).
- Multi-function test generation in one call — one `<fn>` per `r:use-test`.

## Architecture

These are command prompts (like all rforge commands) orchestrating a **hybrid** backend:

- **Infra via `usethis` (guarded R engine).** Only the bits `usethis` does correctly: `use_testthat(3)`
  (sets `Config/testthat/edition`), `use_vignette()`/`use_article()` (creates `vignettes/`, sets
  `VignetteBuilder`, writes the skeleton). Shelled via a thin `lib/rcmd.py`-style snippet wrapped in
  `_guard("usethis", …)`; if `usethis` is absent, degrade to a printed manual recipe (mirrors
  `r:winbuilder`). **`usethis` is a scoped *authoring* engine, not a gate** — the "no devtools/usethis
  for gate commands" rule is unaffected.
- **Content via Python + AI.** The command prompt reads `R/<fn>.R` (signature, roxygen `@examples`,
  `@param`, and the S7/S4 classes of arguments) and drafts the test/vignette content. Simple file
  creation (the test file, the roxygen insertion) is pure-Python.
- **`r:use-package` reuses `lib/deps_sync.py`.** The `DESCRIPTION`-patch writer built for `r:deps-sync`
  (v2.5.0) does the `Imports`/`Suggests` edit here too — one DCF-editing implementation, two commands.
  This is why scaffolding sequences **after** deps-sync.
- **Dry-run/`--write`.** Default renders the planned files + diffs without touching disk; `--write`
  applies; `--force` is required to overwrite an existing target.

## Dependencies

- **`usethis`** — new **optional, guarded** R engine for infra (mainly `use-vignette`; `use_testthat`
  setup). Manual-recipe fallback when absent. Scoped to authoring commands only.
- **`lib/deps_sync.py`** (v2.5.0) — reused `DESCRIPTION`-patch writer for `r:use-package`. **Hard
  sequencing dependency:** this theme builds on deps-sync.
- Otherwise pure-Python stdlib + AI drafting in the prompt. No `devtools`.

## Error handling

- Target file already exists → refuse without `--force`; `--write --force` overwrites (diff shown first).
- `usethis` absent (for `use-vignette`) → print the manual `usethis::use_vignette()` recipe; do not fail.
- `r:use-test` on a function with no resolvable signature/roxygen → scaffold a minimal stub + a note
  that cases couldn't be drafted (never invent assertions).
- `r:use-package` with an ambiguous `Imports`-vs-`Suggests` call → state the recommendation + reason,
  apply on `--write`, but surface the judgement so the user can override.

## Testing

Both gates must pass (`python3 -m pytest tests/` and `bash tests/test-all.sh`). Mock the `usethis`
boundary; assert generated *text*, not R side effects:

- `r:use-test` — fixture function with two `stop()` calls + an `@param` constraint → drafted file has
  a `test_that()` per branch and **all assertions are `# TODO`** (no invented expected values).
- `r:use-package` — `<pkg>` used in `R/` → recommends `Imports`; used only in a vignette → `Suggests`;
  dry-run writes nothing, `--write` applies the DESCRIPTION diff + the `@importFrom`.
- `r:use-vignette` — `usethis`-absent → manual recipe printed, non-fatal; present → skeleton + drafted
  outline planned.
- **Dry-run safety** — default mode performs zero disk writes for all three (asserted).
- New command frontmatter + name-uniqueness covered by `test-all.sh`.

## Documentation impact

**Frontmatter:** `commands/r/use-test.md`, `commands/r/use-package.md`, `commands/r/use-vignette.md`
(`arguments:` for `--write`/`--force`).

**Help / hub:** `docs/commands.md` (a new "Scaffolding / authoring" section), `docs/REFCARD.md`,
`docs/index.md` + `docs/README.md` (counts 33→36, tree diagrams), root `README.md`,
`docs/lib-modules.md` (note the `deps_sync` reuse + `usethis` engine), a scaffolding tutorial.

**Trackers:** `CHANGELOG.md` (`[Unreleased]`), `.STATUS`. Version sync at release.

## Implementation order

1. *(docs — this spec, on `dev`)* — DONE on write.
2. **Prereq:** `r:deps-sync` (v2.5.0) landed — its `DESCRIPTION`-patch writer is reused by `use-package`.
3. *(code — feature worktree)* `r:use-package` (reuse deps_sync writer + `@importFrom` insertion).
4. `r:use-test` (Python file creation + AI case drafting; `use_testthat` infra via guarded usethis).
5. `r:use-vignette` (usethis infra + AI outline) — heaviest; can be a phase-2 if scope needs trimming.
6. Tests (both gates) with the `usethis` boundary mocked.
7. Full doc sweep (help/hub) + CHANGELOG/.STATUS + version sync.

> **Branch note:** steps 3–7 are code → a `feature/r-scaffolding` worktree off `dev`, fresh session.

## Open questions / risks

- **Version slot.** Unscheduled; competes with Phase 4 for post-v2.6.0. *Resolution:* sequence on the
  roadmap once v2.5.0/v2.6.0 are underway.
- **`use-vignette` phase.** Heaviest (usethis infra + largest AI prose surface; the brainstorm filed it
  "long-term"). *Proposed:* ship `use-test` + `use-package` first, `use-vignette` as phase 2.
- **S7/S4 fixture drafting fidelity.** Building a fixture from a class's required properties is the
  hardest part of `use-test`; mis-built fixtures waste time. *Mitigation:* scaffold the fixture
  skeleton with `# TODO` slots rather than guessing property values.
- **`@importFrom` placement.** Which `R/` file gets the roxygen tag (the using file vs a central
  `pkg-package.R`)? *Proposed:* the file where the symbol is used; fall back to a package-doc file.

## Sources

- [r-pkgs §"Testing basics" / testthat](https://r-pkgs.org/testing-basics.html) — `use_test()`, testthat 3e, file layout.
- [r-pkgs §"Dependencies"](https://r-pkgs.org/dependencies-mindset-background.html) — `use_package()`, Imports vs Suggests, `@importFrom`.
- [r-pkgs §"Vignettes"](https://r-pkgs.org/vignettes.html) and [Writing R Extensions §"Writing package vignettes"](https://cran.r-project.org/doc/manuals/r-release/R-exts.html) — `use_vignette()`, `VignetteBuilder`.
- rforge: `BRAINSTORM-r-command-expansion-2026-05-31.md` (origin + AI-value lens), `SPEC-r-deps-sync-2026-06-10.md` (reused patch writer), `SPEC-diff-aware-checks-and-coverage-2026-05-31.md` (P4 `r:test-gen` origin + the no-oracle lesson).

# Changelog - RForge Plugin

All notable changes to the RForge plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.7.0] - 2026-06-11

> Adds an **R-universe early-access tier** to `r:submit` — verify your package's
> fast-channel build is green while CRAN's slower review runs. CRAN submission
> stays explicit and never automatic.

### Added

- **`r:submit --universe`** (`lib/runiverse.py`) — new opt-in flag that verifies the package's
  [R-universe](https://r-universe.dev) early-access build. R-universe rebuilds from your GitHub
  repo within minutes and serves CRAN-like binaries, so users can install the new version
  (`install.packages("<pkg>", repos = "https://<owner>.r-universe.dev")`) while CRAN review runs
  in parallel. The flag auto-detects the universe from the git `origin` remote (override with
  `--universe-name <owner>`), reads the public R-universe API, and reports per-platform build
  status. **Read-only** — R-universe builds on `git push`, so it never uploads; and the R-universe
  status appears as an **advisory** line in the CRAN checklist that never blocks the (still manual)
  CRAN handoff. New public, pure-stdlib module `lib/runiverse.py` (`urllib`-only; no `gh`/R).
  Degrades to a `warn` envelope when offline or unregistered (prints one-time setup guidance);
  never raises. See `docs/specs/SPEC-r-submit-runiverse-early-access-2026-06-11.md`. Command count
  unchanged at 35 (a flag, not a new command).

---

## [2.6.0] - 2026-06-10

> Collapses four roadmapped minors into one release — cran-incoming hardening,
> ecosystem-manifest discovery, `r:deps-sync`, and `r:submit` — that accumulated
> on `dev` since v2.2.0.

### Added

- **Ecosystem manifest discovery** (`lib/discovery.py`): `detect_ecosystem()` optionally reads an ecosystem manifest (e.g. `ECOSYSTEM-MANIFEST.yaml`) located via a new `manifest:` key in the root `.rforge.yaml`, and enriches discovered packages with curated metadata (`role`, `repo`, `cran`, `status_file`). Matching is by package name (case-insensitive). Mismatches surface as `Ecosystem.drift` (`manifest_only` / `disk_only`). New public API: `Manifest`, `ManifestEntry`, `Drift`, `parse_manifest()`, `read_manifest()`.
- **Vendored YAML-subset parser** — `parse_manifest()` reads top-level scalars + a `packages:` list of flat maps with inline-comment stripping, keeping `discovery.py` stdlib-only (no PyYAML). See `docs/specs/SPEC-ecosystem-manifest-discovery-2026-06-10.md`.
- **Manifest surfaced in output**: `/rforge:detect` text output shows a `manifest:` header field, an inline `role` per package, and a `⚠️  Manifest drift` block. `/rforge:status` adds a (conditional) `Role` column and the same drift block. Both render the extra detail only when a manifest is configured — zero-manifest output is byte-for-byte unchanged.
- **`r:deps-sync`** (`lib/deps_sync.py`) — new pure-Python per-package command that reconciles `DESCRIPTION` against actual code usage. Scans `R/`/`tests/`/`vignettes/` + `NAMESPACE` for namespace usage (`pkg::`, `library()`, `@importFrom`, …) and reports **missing** (used, undeclared → Imports), **misclassified** (in Suggests but used unconditionally in `R/` → Imports — the static sibling of `r:check --strict`'s noSuggests pass), **missing_suggests** (tests/vignettes-only), and **unused** findings, plus a suggested patch. Report-only by default; `--write` applies the unambiguous changes. Commands 33 → 34.
- **`r:submit`** (`lib/ghrelease.py`) — new per-package command wrapping the moment of CRAN submission: gate on `cran-prep` `ready` → build the tarball → cut a GitHub **pre-release** (not "Latest") of it + `cran-comments.md` → print the CRAN submit checklist (**never auto-submits**). `r:submit --promote` flips the pre-release to a full release on acceptance (`gh release edit --prerelease=false --latest`). Plain `v<version>` tags promoted in place; `gh` is a soft dependency with a printed manual-recipe fallback. Sidesteps the r-pkgs anti-pattern of tagging a final release pre-acceptance. Commands 34 → 35.

### Changed

- `Ecosystem` gains `manifest_path` and `drift` fields (both default to the empty/zero-manifest case); `Package` gains an optional `manifest` field. `Ecosystem.to_dict()` includes both. Zero behavior change when no manifest is configured.
- `lib/status.py`: `PackageStatus` gains `role`; `EcosystemStatus` gains `drift`; both `to_dict()`s include the new fields. `aggregate_status()` passes manifest role + drift through from discovery.

---

## [2.3.0] - 2026-06-10

> ⚠️ **Behavior change.** `r:cran-prep` now runs two strict Suggests-withholding
> check passes **by default** and **blocks the `ready` verdict** when they fail.
> A package that reports 🟢 `ready` today under `--as-cran` alone can turn 🔴 if
> it uses a `Suggests` package unconditionally (the medfit 0.2.1 class). This is
> intended — CRAN's post-acceptance noSuggests flavor would bounce it anyway —
> but it is not patch-safe, hence the minor bump.

### Added

- **CRAN-incoming strict check passes** (`lib/rcmd.py`): `r:check --strict` runs
  both Suggests-withholding flavors as distinct stage rows — `check (noSuggests)`
  (`_R_CHECK_DEPENDS_ONLY_=true`) and `check (suggests-only)`
  (`_R_CHECK_SUGGESTS_ONLY_=true`) — each with `--run-donttest` (runs
  `\donttest{}` examples). `r:check --incoming` implies `--strict` and adds a
  third `check (incoming)` row (`_R_CHECK_CRAN_INCOMING_*`, confirmed against R
  Internals §8). Mechanism: `rcmdcheck(args=, env=)` — no `devtools`, no
  subprocess-layer change.
- **`lib/cranlint.py`** — new pure-stdlib (no R) analysis module with three
  advisory checks wired into `r:cran-prep`: `lint_description` (DESCRIPTION
  incoming nits — non-`Authors@R`/no `cph`, weak `Title`, `Description` prose,
  stale `Date`), `check_build_hygiene` (planning/dev docs that would ship in the
  tarball, each with the exact `.Rbuildignore` regex to add), and
  `check_planning_consistency`. These surface as the `description`,
  `build-hygiene`, and `docs-consistency` stages and **never block** `ready`.
- **Tier 1b manual-build check** — `r:cran-prep` verifies the PDF reference
  manual builds; emits a `warn` (never a blocker) when LaTeX is absent.
- **Failure hint** on a strict-pass error: move the package to `Imports`, or
  guard with `requireNamespace()` in code AND `skip_if_not_installed()` in tests.
- **E2E regression proof** — `tests/fixtures/suggestbug.{before,after}` +
  `tests/test_regression_suggests_e2e.py` (opt-in via `RFORGE_E2E`) prove the
  noSuggests pass catches the medfit bug class with the real R toolchain.

### Changed

- `r:cran-prep` default sequence now includes `check (noSuggests)`,
  `check (suggests-only)`, `description`, `build-hygiene`, and `docs-consistency`
  (plus opt-in `check (incoming)` via `--incoming`).
- `r_snippet`/`run("check", …)` gained internal `flavor`/`incoming` selectors;
  `lib.rcmd` argparse gained `--incoming`.

---

## [2.2.0] - 2026-06-02

### Added

- **5 new `r:` CRAN-submission commands**: `r:revdep` (reverse-dependency check via `revdepcheck`), `r:goodpractice` (advisory best-practice bundle), `r:winbuilder` (async dispatch to win-builder via `devtools`), `r:rhub` (async dispatch to R-hub v2 via `rhub`), `r:cran-prep` (full CRAN-readiness gate: document→lint→spell→urlcheck→test→coverage→check(--as-cran)→revdep + generates `cran-comments.md` with a `ready`/`warn`/`blocked` verdict).
- **`r:check` NOTE classifier**: each R CMD check NOTE is now classified as `spurious` (expected on first CRAN submission) or `real` (needs attention) in the `notes_classified` field of the envelope.
- **`render_cran_comments`** pure-Python function in `lib/rcmd.py` generates `cran-comments.md` from check + revdep envelopes.
- **28 → 33 commands** total.
- **Tutorial**: `docs/tutorials/cran-submission-with-rforge.md` — per-package CRAN gate walkthrough.

### Changed

- `r:check`: envelope now includes `check.notes_classified` (list of `{text, kind, reason}` dicts).
- `lib/rcmd.py`: new CRAN-submission engine kinds (`revdep`, `goodpractice`, `winbuilder`, `rhub`, `cran-prep`); `OPTIONAL_ENGINES` and `INSTALL_HINT` extended; `_status_for` + `normalize` updated; `dispatched` status added for async kinds.

---

## [2.1.0] - 2026-05-31

### Added

- **`lib/rcmd.py`** — new pure-Python module that runs lower-level R engines (`rcmdcheck`, `pkgbuild`, `roxygen2`, `testthat`, `pkgload`, `covr`, `pkgdown`, `lintr`, `spelling`, `urlchecker`, `styler`) and normalizes JSON output to a common envelope. CLI: `python3 -m lib.rcmd --kind <kind> --path <path>`. Never uses `devtools`.
- **12 new `r:` commands** (`r:load`, `r:document`, `r:test`, `r:coverage`, `r:build`, `r:install`, `r:site`, `r:cycle`, `r:lint`, `r:spell`, `r:urlcheck`, `r:style`) — total 16 → **28** commands.
- **`r:cycle`** — orchestrates `document → test → check` in sequence, stopping at the first hard error.
- **`r:site`** flags: `--preview`, `--strict`, `--articles-only`, `--devel`.
- **`docs/reference/rcmd.md`** — auto-generated API reference for `lib/rcmd.py`.

### Changed

- **`r:check`** — retrofitted to drive its report from `python3 -m lib.rcmd --kind check`. No longer calls `R CMD check` directly.

---

## [2.0.0] - 2026-05-12

> **Breaking change:** 3 of 16 commands renamed to align with craft's hybrid
> namespacing. The other 13 commands are unchanged. See
> [`docs/migration/v2.0.0-rename.md`](docs/migration/v2.0.0-rename.md) for
> the full mapping table and a `sed` recipe to update local scripts.

### Changed (BREAKING)

- `/rforge:doc-check` → `/rforge:docs:check` — aligns with craft's `docs:` namespace.
- `/rforge:ecosystem-health` → `/rforge:health` — shorter daily-use name; no sub-namespace needed for a single command.
- `/rforge:rpkg-check` → `/rforge:r:check` — R-specific commands get an `r:` prefix.

### Added

- **`docs/migration/v2.0.0-rename.md`** — single-page migration tutorial with mapping table and POSIX `sed` recipes for macOS + Linux.
- **Rename-error stubs** at the 3 old filenames (`commands/doc-check.md`, `commands/ecosystem-health.md`, `commands/rpkg-check.md`). Typing an old name in Claude Code produces a verbatim error message pointing at the new name plus a link to the migration tutorial. Stubs ship through the v2.x line; slated for removal in v3.0.0.
- **`rename_stubs_present` test** in `tests/test-all.sh` — asserts each stub exists, retains its old slash-command name in frontmatter, contains a `RENAMED` marker, and references its new name. Wording-tolerant (key-string match, not exact prose).

### Internal

- New `commands/docs/` and `commands/r/` subdirectories for the renamed commands; explicit `name:` frontmatter added to the two files that lacked it (`commands/health.md` and `commands/r/check.md`) so the colon-namespaced names resolve.
- Cross-reference sweep across `docs/commands.md`, `docs/quickstart.md`, `docs/configuration.md`, the `description-sync` skill, `commands/complete.md`, and `commands/impact.md`.

---

## [1.3.0] - 2026-05-11

> **Path B complete** — `rforge-mcp` is fully absorbed into the plugin via
> pure-Python `lib/` ports. With this release, the plugin no longer has any
> runtime dependency on the MCP server. The `data-wise/rforge-mcp` repo will
> be archived separately post-merge per `docs/migration/v1.3.0-post-merge-checklist.md`.

### Added — Path B Phase B.1: discovery + deps ported to `lib/`

- **`lib/discovery.py`** — pure-Python R ecosystem detector. Walks the filesystem
  for `DESCRIPTION` files, classifies layouts as `single | ecosystem | hybrid`,
  preserves MCP-compatible `mode` field (`minimal | standard | full`) for
  side-by-side validation. Exposes `detect_ecosystem()` API and an
  `argparse` CLI (`python3 -m lib.discovery --path . --format {text,json}`).
- **`lib/deps.py`** — dependency-graph + impact analysis, ported from
  `rforge-mcp` `tools/deps/{deps,impact}.js`. Builds DAG from
  `Imports`/`Depends`/`Suggests`/`LinkingTo`, computes topological layers
  (leaves first), detects cycles, identifies blockers. `analyze_impact()`
  estimates direct/indirect dependents, risk level, work hours, and
  generates change-type-aware recommendations. CLI subcommands:
  `python3 -m lib.deps [--path .] [--format {text,json}] [graph|impact ...]`.
- **`tests/test_lib_discovery.py` + `tests/test_lib_deps.py`** — 32 pytest cases
  covering DESCRIPTION parsing edge cases (continuation lines, version
  constraints, `R` filtering), FS traversal (hidden-dir handling, no descent
  into packages), classification rules, graph construction, cycle detection,
  impact heuristics, and blockers.

### Added — Path B Phases B.2 + B.3: status + init ported to `lib/`

- **`lib/status.py`** — pure-Python port of `rforge-mcp`'s `status` tool. Reads
  `DESCRIPTION` + `.STATUS` files and computes ecosystem health score.
  Faithful port: same algorithm, same field names, no R subprocess. CLI:
  `python3 -m lib.status [--path .] [--format text|json]`. (B.2)
- **`lib/init.py`** — pure-Python port of `rforge-mcp`'s `init` tool. Writes
  `~/.rforge/context.json` (global per-user state, matches MCP). Idempotent.
  CLI: `python3 -m lib.init [--path .] [--quick] [--format text|json]`. (B.3)
- **`commands/init.md`** — first-class `/rforge:init` command (B.3 makes init
  a real, addressable tool).
- **`docs/reference/{status,init}.md`** — auto-generated API reference from
  module introspection; kept in sync by `scripts/gen_lib_reference.py --check`.

### Changed

- **`commands/detect.md`, `commands/deps.md`, `commands/impact.md`** — invoke
  the new `lib/` Python modules via Bash instead of the `rforge_*` MCP tools.
  Both subprocess CLI usage and Python API documented.
- **`commands/{status,quick,thorough}.md`** now dispatch
  `python3 -m lib.status` instead of the MCP tool. `thorough.md` simplified
  to point users at `R CMD check` / `devtools::test()` / `covr` directly.
- **`commands/analyze.md`** — last two inline `rforge_status` / `rforge_detect`
  references swapped for the `lib/` CLIs.
- **`scripts/gen_lib_reference.py`** now generates references for `lib.status`
  and `lib.init` alongside `lib.discovery` and `lib.deps`.
- **`tests/test-all.sh`**: `lib_pytest` and `lib_cli_smoke` runners now
  exercise all four `lib/` modules (discovery + deps + status + init). Total
  checks remain 23 — coverage grew within existing runners.

### Scope notes

- **Status port is faithful, not aspirational.** The original SPEC called for
  a 4-mode (default/debug/optimize/release) status contract with R subprocess
  support. Wave 1 research surfaced that the MCP server's `status` tool had
  no modes and ran no R subprocess — it's a `.STATUS` file reader with a
  health-score heuristic. The 4-mode design is descoped to v1.4.0 pending
  real-user input on what depth is wanted.
- **`mcpServers.rforge` cleanup.** Users with `~/.claude/settings.json`
  referencing the now-archived `rforge-mcp` binary should remove that entry
  manually. We don't auto-edit user settings.

### Removed

- N/A — the plugin no longer depends on `rforge-mcp` at runtime, but no
  rforge-side files are deleted in v1.3.0. (The `data-wise/rforge-mcp` repo
  itself is archived separately after this PR merges.)

### Notes

- Non-breaking: existing users with `rforge-mcp` installed keep working; new
  users get pure-Python analysis with no peer dependency.
- B.1 was validated side-by-side against MCP server output on the
  mediationverse ecosystem (5 packages); algorithmic parity confirmed.

---

## [1.2.0] - 2026-05-09

> **Note:** v1.2.0 was developed across multiple sessions on `dev`. The list
> below captures the full scope of the upcoming release, including post-merge
> polish (rename-debt cleanup, MCP decoupling, version-sync hardening). Tagged
> release date will reflect the final ship date.

### Changed — MCP server is now optional (decoupling)

- **`package.json`** — removed `peerDependencies.rforge-mcp`. The plugin no
  longer requires `rforge-mcp` to be installed. Existing users with the MCP
  server keep all functionality; new users can install plugin standalone via
  marketplace, npm, or Homebrew without hitting the long-standing 404 from
  `rforge-mcp` not being on the npm registry.
- **`README.md`** — "Part 1: Install RForge MCP Server" reframed as optional.
- Plugin commands work via Claude Code's built-in tools (Read, Bash, etc.).
  MCP integration provides typed I/O for users who want it; not required for
  core functionality.

### Changed — Rename debt cleanup (post-extraction)

- All user-facing install instructions now use the `rforge` formula and plugin
  name (was `rforge-orchestrator`, the pre-extraction monorepo name).
- All `Data-Wise/claude-plugins` URLs in current-install contexts replaced
  with `Data-Wise/rforge`.
- Plugin install path: `~/.claude/plugins/rforge` (was `rforge-orchestrator`).
- Migration section in `README.md` and `MCP-MIGRATION.md` retain the old name
  intentionally (documents the rename for users on the old install).
- `scripts/install.sh` + `scripts/uninstall.sh`: `PLUGIN_NAME` now `rforge`.
  Comments document the legacy `rforge-orchestrator` cleanup path.

### Changed — Version-sync hardening

- **`tests/test-all.sh`** — the `versions_match` test now asserts all 4 version
  sources agree: `plugin.json`, `marketplace.json/metadata`,
  `marketplace.json/plugins[0]`, `package.json`. Previously only the first two
  were compared; `package.json` drifted from 1.1.0 → 1.2.0 unnoticed in the
  initial PR. Negative-tested by injecting a fake mismatch.

### Fixed — broken internal links

- 9 broken internal links in `docs/` and `README.md` from the monorepo
  extraction (paths like `../../docs/MODE-USAGE-GUIDE.md`,
  `../../KNOWLEDGE.md`) removed. Documents that survived the extraction now
  link to surviving siblings only.

### Added — Craft-Parity Foundations (Phases 1 + 2)

Brings rforge's plugin architecture to parity with craft for the
foundation layers — installable via the Claude Code marketplace, hook-aware
on every Write/Edit, and shipping its first autonomous validation skill.

#### Marketplace + Config

- **`.claude-plugin/marketplace.json`** — enables one-shot install via
  `/plugin marketplace add Data-Wise/rforge`. Mirrors craft's structure.
- **`.claude-plugin/config.json`** — user-configurable options stub with
  R-specific defaults: `cran_mirror` (cloud.r-project.org), `vignette_engine`
  (knitr::rmarkdown), `r_version_pin` (>= 4.1.0), `claude_md_budget` (600).

#### R-Aware Hooks

- **`.claude-plugin/hooks/pretooluse.py`** — PreToolUse hook with four rules:
  - **Block** edits to roxygen-generated `man/*.Rd` files (exit 2).
  - **Warn** on `R/*.R` edits — reminder to keep NAMESPACE/DESCRIPTION in sync.
  - **Warn** when `DESCRIPTION` `Version:` isn't SemVer-compatible.
  - **Warn** on writes outside the current worktree (port of craft's rule).
- **`.claude-plugin/hooks/README.md`** — wiring + testing reference.

#### Skills Layer

- **`.claude-plugin/skills/validation/description-sync.md`** — first
  autonomous validator. Checks that `DESCRIPTION` `Version:` matches the
  top entry of `NEWS.md` / `CHANGELOG.md` and flags non-SemVer bumps.
  Pure shell — no R or devtools required.

### Changed

- **`plugin.json`** — version 1.1.0 → 1.2.0; description tightened.
- **`README.md`** — adds a marketplace install section.

### Notes

- Phase 3 (command namespacing, breaking) and Phase 4 (discovery engine)
  remain in separate worktrees.
- Pre-existing blocker `npm install` failing on `rforge-mcp@>=0.1.0` (404)
  is unrelated to this release and tracked separately.

---

## [1.1.0] - 2025-12-26

### Added - R Package Commands

Migrated R-specific commands from user commands into the plugin:

#### New Commands (2 total)
- **`/rforge:rpkg-check`** - Run R CMD check on package with smart output parsing
- **`/rforge:ecosystem-health`** - Check health across R package ecosystem

### Changed
- **Total commands:** 13 → 15
- **Plugin installed via symlink** for easier development

---

## [1.0.0] - 2024-12-23

### Added - Initial Release

#### Commands (13 total)
- **`/rforge:analyze`** - Quick analysis with auto-delegation (< 30 seconds)
- **`/rforge:quick`** - Ultra-fast analysis using only quick tools (< 10 seconds)
- **`/rforge:thorough`** - Comprehensive analysis with background R processes (2-5 minutes)
- **`/rforge:detect`** - Auto-detect R package project structure
- **`/rforge:deps`** - Build and visualize dependency graph
- **`/rforge:impact`** - Analyze change impact across ecosystem
- **`/rforge:cascade`** - Plan coordinated updates across packages
- **`/rforge:doc-check`** - Check documentation drift and inconsistencies
- **`/rforge:release`** - Plan CRAN submission sequence
- **`/rforge:capture`** - Quick capture ideas and tasks
- **`/rforge:complete`** - Mark tasks complete with documentation cascade
- **`/rforge:next`** - Get ecosystem-aware next task recommendation
- **`/rforge:status`** - Ecosystem-wide status dashboard

#### Agents
- **orchestrator** - Auto-delegation for RForge MCP tools

#### Features
- Auto-delegation to RForge MCP tools
- Parallel execution of multiple MCP calls
- Live progress updates
- Smart result synthesis
- ADHD-friendly output

---

## Version History Summary

| Version | Date | Major Changes |
|---------|------|---------------|
| **1.2.0** | 2026-05-09 | Marketplace install, R-aware PreToolUse hook, first validation skill |
| **1.1.0** | 2025-12-26 | Added rpkg-check and ecosystem-health commands |
| **1.0.0** | 2024-12-23 | Initial release: 13 commands, 1 agent |

---

**Last Updated:** 2026-05-09
**Maintained By:** Data-Wise
**License:** MIT

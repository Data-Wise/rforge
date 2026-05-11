# Changelog - RForge Plugin

All notable changes to the RForge plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
- **`tests/test-all.sh`** — adds two checks (`Lib: pytest suite`,
  `Lib: CLI smoke`); total now 22.

### Changed

- **`commands/detect.md`, `commands/deps.md`, `commands/impact.md`** — invoke
  the new `lib/` Python modules via Bash instead of the `rforge_*` MCP tools.
  Both subprocess CLI usage and Python API documented.

### Notes

- Non-breaking: existing users with `rforge-mcp` installed keep working; new
  users get pure-Python analysis with no peer dependency.
- Validated side-by-side against MCP server output on the mediationverse
  ecosystem (5 packages); algorithmic parity confirmed (both treat `.Rcheck`
  duplicates equivalently).

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

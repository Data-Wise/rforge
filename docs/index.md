# RForge Plugin

[![Version](https://img.shields.io/github/package-json/v/Data-Wise/rforge?label=version&color=blue)](https://github.com/Data-Wise/rforge/releases)
[![npm](https://img.shields.io/npm/v/@data-wise/rforge-plugin?label=npm&color=red)](https://www.npmjs.com/package/@data-wise/rforge-plugin)
[![License: MIT](https://img.shields.io/github/license/Data-Wise/rforge?color=green)](https://github.com/Data-Wise/rforge/blob/main/LICENSE)
[![CI](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml)

**R package ecosystem orchestrator for Claude Code — 16 commands, R-aware hooks, validation skills.**

!!! tip "TL;DR (30 seconds)"
    - **What:** R package *ecosystem* analysis from inside Claude Code. 16 slash commands.
    - **Why:** Fast feedback on multi-package R repos — discovery, dependencies, change impact, CRAN cascade planning.
    - **How:** `brew install data-wise/tap/rforge`, then `/rforge:analyze "<what changed>"`.
    - **Next:** [Quick Start](QUICK-START.md) (3 min) → [Where to start](#where-to-start) below.

Self-contained R package analysis for Claude Code. Since v1.3.0 the plugin is fully self-sufficient — pure-Python `lib/` modules handle discovery, dependencies, status, and init. **No MCP server, no Node.js, no R subprocess** for the fast commands (only `/rforge:r:check` and `/rforge:thorough` shell out to R).

## What rforge is — and isn't

!!! abstract "rforge orchestrates an ecosystem; it does not build packages"
    rforge sits **alongside** the standard R toolchain, it doesn't replace it.

    - **`usethis` / `devtools`** scaffold, document, test, and build a *single* package.
    - **rforge** answers cross-cutting questions: *Which packages exist here? What depends on what? If I change `medfit`, what breaks downstream? In what order do I submit to CRAN?*

    If you're looking for `create_package()` or `document()`, that's `usethis`/`devtools`. rforge picks up where they leave off — see **[rforge in the R package lifecycle](tutorials/rforge-in-the-r-lifecycle.md)** for exactly where each tool plugs in.

## Where to start

| If you're… | Go to | Time |
|---|---|---|
| Brand new — just want it working | [Quick Start](QUICK-START.md) | 3 min |
| New to rforge, have an R package to try | [Getting started tutorial](tutorials/getting-started.md) | 10 min |
| Wondering how rforge fits with devtools/usethis | [rforge in the R package lifecycle](tutorials/rforge-in-the-r-lifecycle.md) | 12 min |
| Managing several inter-dependent packages | [Ecosystem orchestration](tutorials/ecosystem-orchestration.md) | 15 min |
| Preparing a CRAN submission | [CRAN release prep](tutorials/cran-release-prep.md) | 15 min |
| Looking up a command's syntax | [Reference Card](REFCARD.md) | <1 min |

## The 3 headline commands

Most daily work runs through these. The other 13 commands are specialized — see the [Reference Card](REFCARD.md).

```bash
# Ultra-fast snapshot (< 10 seconds) — pre-commit
/rforge:quick

# Balanced analysis with impact + recommendations (~30 seconds) — after changes
/rforge:analyze "Update RMediation bootstrap algorithm"

# Comprehensive validation incl. R CMD check (2-5 minutes) — before CRAN
/rforge:thorough "Prepare for CRAN release"
```

## What's new in v2.0.0 (BREAKING)

- 🔀 **3 commands renamed** for cleaner namespacing — `/rforge:doc-check` → `/rforge:docs:check`, `/rforge:ecosystem-health` → `/rforge:health`, `/rforge:rpkg-check` → `/rforge:r:check`. The other 13 commands are unchanged. Typing an old name produces a helpful rename-error pointing at the new name — no silent failures. See the [v2.0.0 migration tutorial](migration/v2.0.0-rename.md) for the full mapping table and a `sed` recipe to mass-update local scripts.

## What's new in v1.3.0

- 🎯 **MCP absorption complete** — the prior `rforge-mcp` prototype was absorbed into the plugin. All capabilities now ship as pure-Python `lib/` modules. See the [migration guide](migration/rforge-mcp-deprecation.md).
- 🐍 **`lib/status.py`** — ecosystem health snapshot (`DESCRIPTION` + `.STATUS` parsing): `python3 -m lib.status`.
- 🌱 **`lib/init.py`** — `~/.rforge/context.json` initializer behind the new `/rforge:init` command.
- 📦 **No runtime dependencies beyond Python 3.10+**.

Full release notes: [CHANGELOG.md](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md).

## How it works

```text
You invoke /rforge:<command>
    ↓
Claude reads commands/<name>.md as its prompt
    ↓
Claude orchestrates pure-Python lib/ modules + Bash tools as needed
    ├── python3 -m lib.discovery   (ecosystem + package detection)
    ├── python3 -m lib.deps        (dependency graph + change impact)
    ├── python3 -m lib.status      (health snapshot)
    └── python3 -m lib.init        (~/.rforge/context.json setup)
    ↓
PreToolUse hook diagnoses risky Write/Edit ops (blocks man/*.Rd edits, etc.)
    ↓
Validation skills run autonomously (description-sync, etc.)
    ↓
Results synthesized into an actionable summary
```

## Requirements

| Requirement | Needed for |
|---|---|
| **Claude Code CLI** | everything (this is a Claude Code plugin) |
| **Python 3.10+** on PATH | the `lib/` modules (`discovery`, `deps`, `status`, `init`) |
| **R 4.0+** (+ optional `devtools`, `testthat`, `covr`) | only `/rforge:r:check` and `/rforge:thorough` |

## Installation

```text
/plugin marketplace add Data-Wise/rforge
/plugin install rforge
```

Restart Claude Code so the commands register, then verify with `/help` (look for `/rforge:` entries). Homebrew, npm, and from-source options are in [Installation](installation.md).

> **Migrating from v1.2.x?** If `~/.claude/settings.json` still has an `mcpServers.rforge` entry, it's no longer needed — remove it. See the [migration guide](migration/rforge-mcp-deprecation.md).

## Design principles (ADHD-friendly)

1. **Fast feedback** — `/rforge:quick` returns in seconds, not minutes.
2. **Clear structure** — consistent, scannable output across commands.
3. **Visual progress** — you see what's happening as it happens.
4. **Always actionable** — every result ends with next steps.
5. **Interruptible & incremental** — results stream as they complete.

## More documentation

- **[Reference Card](REFCARD.md)** — all 16 commands on one page
- **[Commands](commands.md)** — full per-command reference
- **[Architecture](architecture.md)** — how the `lib/` modules fit together
- **[Hooks & Skills](hooks-and-skills.md)** — the R-aware `PreToolUse` hook
- **[Configuration](configuration.md)** — CRAN mirror, vignette engine, R version pin, CLAUDE.md budget
- **[Troubleshooting](troubleshooting.md)** — when commands misbehave

## License

MIT. Source: <https://github.com/Data-Wise/rforge>

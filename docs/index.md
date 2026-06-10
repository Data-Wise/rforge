# RForge Plugin

[![Version](https://img.shields.io/github/package-json/v/Data-Wise/rforge?label=version&color=blue)](https://github.com/Data-Wise/rforge/releases)
[![npm](https://img.shields.io/npm/v/@data-wise/rforge-plugin?label=npm&color=red)](https://www.npmjs.com/package/@data-wise/rforge-plugin)
[![License: MIT](https://img.shields.io/github/license/Data-Wise/rforge?color=green)](https://github.com/Data-Wise/rforge/blob/main/LICENSE)
[![CI](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml)

**R package ecosystem orchestrator for Claude Code — 33 commands, R-aware hooks, validation skills.**

!!! tip "TL;DR (30 seconds)"
    - **What:** R package *ecosystem* analysis from inside Claude Code. 33 slash commands.
    - **Why:** Fast feedback on multi-package R repos — discovery, dependencies, change impact, CRAN cascade planning.
    - **How:** `brew install data-wise/tap/rforge`, then `/rforge:analyze "<what changed>"`.
    - **Next:** [Quick Start](QUICK-START.md) (3 min) → [Where to start](#where-to-start) below.

Self-contained R package analysis for Claude Code. Since v1.3.0 the plugin is fully self-sufficient — pure-Python `lib/` modules handle discovery, dependencies, status, and init. **No MCP server, no Node.js** at runtime. The fast ecosystem commands (analysis, deps, status) are pure Python; the `r:*` dev-cycle commands and `/rforge:thorough` shell out to R via `lib/rcmd.py`.

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

Most daily work runs through these. The other 30 commands are specialized — see the [Reference Card](REFCARD.md).

```bash
# Ultra-fast snapshot (< 10 seconds) — pre-commit
/rforge:quick

# Balanced analysis with impact + recommendations (~30 seconds) — after changes
/rforge:analyze "Update RMediation bootstrap algorithm"

# Per-package CRAN gate (v2.2.0+) — document→strict check→Tier 4→revdep, writes cran-comments.md
/rforge:r:cran-prep

# Ecosystem rollup (2-5 minutes) — cross-package validation + submission order
/rforge:thorough "Prepare for CRAN release"
```

## What's new in v2.3.0

- **CRAN-incoming hardening for `r:check` + `r:cran-prep`** — the submission gate now emulates CRAN's *incoming* and post-acceptance flavors. `r:check --strict` runs **both** Suggests-withholding passes (`check (noSuggests)` + `check (suggests-only)`, each with `--run-donttest`); `--incoming` adds the opt-in `check (incoming)` env-var bundle. `r:cran-prep` runs the strict passes **by default**, and a strict ERROR **blocks** the `ready` verdict.
- **Tier 4 advisory checks (new `lib/cranlint.py`, pure stdlib, no R)** — three `cran-prep` stages that never block `ready`: `description` (DESCRIPTION incoming nits — non-`Authors@R`, weak `Title`, `Description` prose, stale `Date`), `build-hygiene` (planning/dev docs that would ship in the tarball, with the exact `.Rbuildignore` regex to add), and `docs-consistency`.

!!! warning "Behavior change in v2.3.0"
    A package that reports 🟢 `ready` today under `--as-cran` can turn 🔴 once the noSuggests pass catches a `Suggests` package used unconditionally (the medfit 0.2.1 class). This is intended — CRAN would bounce such a package post-acceptance. Move the dependency to `Imports`, or guard it with `requireNamespace()` + `skip_if_not_installed()`.

## What's new in v2.2.0

- **5 new `r:` CRAN-submission commands**: `r:revdep`, `r:goodpractice`, `r:winbuilder`, `r:rhub`, `r:cran-prep` — full pre-submission gate that runs document→lint→spell→urlcheck→test→coverage→check(--as-cran)→revdep, generates `cran-comments.md`, and returns a `ready`/`warn`/`blocked` verdict.
- **`r:check` NOTE classifier**: notes are now classified as `spurious` (expected on CRAN submission) or `real` (needs attention) using `notes_classified` in the envelope.
- **Total: 28 → 33 commands.**

## What's new in v2.1.0

- 🔬 **12 new `r:` commands** (`r:load`, `r:document`, `r:test`, `r:coverage`, `r:build`, `r:install`, `r:site`, `r:cycle`, `r:lint`, `r:spell`, `r:urlcheck`, `r:style`) — full R package dev cycle + quality layer.
- 🐍 **`lib/rcmd.py`** — new module running lower-level R engines (`rcmdcheck`, `pkgbuild`, `roxygen2`, `testthat`, `pkgload`, `covr`, `pkgdown`, `lintr`, `spelling`, `urlchecker`, `styler`); structured JSON output; optional engines degrade gracefully.
- **Total: 16 → 28 commands.**

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
| **R 4.0+** (+ optional engines via `lib.rcmd`) | all `r:*` commands and `/rforge:thorough` |

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

- **[Reference Card](REFCARD.md)** — all 33 commands on one page
- **[Commands](commands.md)** — full per-command reference
- **[Architecture](architecture.md)** — how the `lib/` modules fit together
- **[Hooks & Skills](hooks-and-skills.md)** — the R-aware `PreToolUse` hook
- **[Configuration](configuration.md)** — CRAN mirror, vignette engine, R version pin, CLAUDE.md budget
- **[Troubleshooting](troubleshooting.md)** — when commands misbehave

## License

MIT. Source: <https://github.com/Data-Wise/rforge>

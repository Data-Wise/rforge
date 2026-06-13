# RForge Plugin

[![Version](https://img.shields.io/github/package-json/v/Data-Wise/rforge?label=version&color=blue)](https://github.com/Data-Wise/rforge/releases)
[![npm](https://img.shields.io/npm/v/@data-wise/rforge-plugin?label=npm&color=red)](https://www.npmjs.com/package/@data-wise/rforge-plugin)
[![License: MIT](https://img.shields.io/github/license/Data-Wise/rforge?color=green)](https://github.com/Data-Wise/rforge/blob/main/LICENSE)
[![CI](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml)

**R package ecosystem orchestrator for Claude Code — {{ rforge.command_count }} commands, R-aware hooks, validation skills.**

!!! tip "TL;DR (30 seconds)"
    - **What:** R package *ecosystem* analysis from inside Claude Code. {{ rforge.command_count }} slash commands.
    - **Why:** Fast feedback on multi-package R repos — discovery, dependencies, change impact, CRAN cascade planning.
    - **How:** `brew install data-wise/tap/rforge`, then `/rforge:analyze "<what changed>"`.
    - **Next:** [Quick Start](QUICK-START.md) (3 min) → [Where to start](#where-to-start) below.

Self-contained R package analysis for Claude Code. Since v1.3.0 the plugin is fully self-sufficient — pure-Python `lib/` modules handle discovery, dependencies, status, and init. **No MCP server, no Node.js** at runtime. The fast ecosystem commands (analysis, deps, status) are pure Python; the `r:*` dev-cycle commands and `/rforge:thorough` shell out to R via `lib/rcmd.py`.

## Where rforge fits

```mermaid
flowchart LR
    A["usethis<br/>scaffold"] --> B["devtools<br/>document · test · build"]
    B --> C["rforge<br/>discover · deps · impact · cascade"]
    C --> D["CRAN<br/>ordered submission"]
    style C fill:#5e35b1,color:#fff
```

!!! abstract "rforge orchestrates an ecosystem; it does not build packages"
    **They build one package. rforge runs the ecosystem.** rforge sits *alongside* the
    standard R toolchain, it doesn't replace it.

    - **`usethis` / `devtools`** scaffold, document, test, and build a *single* package.
    - **rforge** answers cross-cutting questions: *Which packages exist here? What depends on what? If I change `medfit`, what breaks downstream? In what order do I submit to CRAN?*

    Looking for `create_package()` or `document()`? That's `usethis`/`devtools`. rforge picks
    up where they leave off — see **[rforge in the R package lifecycle](tutorials/rforge-in-the-r-lifecycle.md)**.

## Where to start

<div class="grid cards" markdown>

-   :material-rocket-launch: **Just want it working**

    ---
    3-minute install + first command.

    [:octicons-arrow-right-24: Quick Start](QUICK-START.md)

-   :material-school: **New, have a package to try**

    ---
    Guided 10-minute walkthrough.

    [:octicons-arrow-right-24: Getting started](tutorials/getting-started.md)

-   :material-puzzle: **How it fits with devtools/usethis**

    ---
    Where rforge plugs into the lifecycle.

    [:octicons-arrow-right-24: The R lifecycle](tutorials/rforge-in-the-r-lifecycle.md)

-   :material-graph: **Managing several packages**

    ---
    Cross-package orchestration.

    [:octicons-arrow-right-24: Ecosystem](tutorials/ecosystem-orchestration.md)

-   :material-package-up: **Preparing a CRAN submission**

    ---
    The full submission gate.

    [:octicons-arrow-right-24: CRAN prep](tutorials/cran-release-prep.md)

-   :material-card-text: **Looking up command syntax**

    ---
    All {{ rforge.command_count }} commands, one page.

    [:octicons-arrow-right-24: Reference Card](REFCARD.md)

</div>

## What you'll run daily

Most work runs through these four; the rest of the {{ rforge.command_count }} commands are specialized — see the [Reference Card](REFCARD.md).

<div class="grid cards" markdown>

-   :material-flash: **`/rforge:quick`** · <10s

    ---
    Ultra-fast snapshot. Run before every commit.

-   :material-magnify-scan: **`/rforge:analyze "<change>"`** · ~30s

    ---
    Balanced analysis with impact + recommendations after a change.

-   :material-clipboard-check: **`/rforge:r:cran-prep`** · per-pkg

    ---
    The full CRAN gate; document → strict check → Tier 4 → revdep; writes `cran-comments.md`.

-   :material-layers-triple: **`/rforge:thorough`** · 2-5 min

    ---
    Cross-package ecosystem rollup + submission order.

</div>

## What's new in {{ rforge.version }}

Three recommendations from a documentation gap analysis — **{{ rforge.command_count }} commands** (no surface change).

- **`docs/commands.md` sync-gate** — a new test gate (`tests/_check_commands_doc.py`) cross-checks every command + flag against the reference page; it immediately surfaced and fixed 10 undocumented flags. Closes the last drift-prone documentation surface.
- **diff-aware `[uncommitted]` tag** — `/rforge:r:check`/`r:test`/`r:lint --changed` now re-tags an `[introduced]` finding in a file with uncommitted changes as **`[uncommitted]`**, so you can tell "edits I haven't committed yet" from committed branch work. See the [diff-aware checks tutorial](tutorials/diff-aware-checks.md).
- **`/rforge:r:s7-review method_undeclared_dependency`** — the `--runtime` pass now flags a method dispatching on an S7 class whose providing package isn't declared in `DESCRIPTION` (typically a `Suggests`-only class that silently never dispatches at a user's site). See the [S7 convention checking tutorial](tutorials/s7-convention-checking.md).

Full release history: [CHANGELOG.md](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md).

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

- **[Reference Card](REFCARD.md)** — all {{ rforge.command_count }} commands on one page
- **[Commands](commands.md)** — full per-command reference
- **[Architecture](architecture.md)** — how the `lib/` modules fit together
- **[Hooks & Skills](hooks-and-skills.md)** — the R-aware `PreToolUse` hook
- **[Configuration](configuration.md)** — CRAN mirror, vignette engine, R version pin, CLAUDE.md budget
- **[Troubleshooting](troubleshooting.md)** — when commands misbehave

## License

MIT. Source: <https://github.com/Data-Wise/rforge>

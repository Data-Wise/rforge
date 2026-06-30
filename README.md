# RForge Plugin

[![Version](https://img.shields.io/github/package-json/v/Data-Wise/rforge?label=version&color=blue)](https://github.com/Data-Wise/rforge/releases)
[![License: MIT](https://img.shields.io/github/license/Data-Wise/rforge?color=green)](https://github.com/Data-Wise/rforge/blob/main/LICENSE)
[![CI](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml)

**R package ecosystem orchestrator for Claude Code — 41 commands, R-aware hooks, validation skills.**

Self-contained R package analysis for Claude Code. As of v1.3.0 the plugin is fully self-sufficient — pure-Python `lib/` modules handle discovery, dependencies, status, and init. No MCP server required.

## What's new in v2.17.0

- 🛡️ **`r:cran-prep` tarball-check stage** — builds the source tarball with `devtools::build()`, inspects it for stray build artifacts (`.quarto/`, `_freeze/`, `.html`, `*_files/`), then runs `rcmdcheck(tarball, --as-cran, --run-donttest)`. Catches the class of failures CRAN and win-builder see but a source-tree `devtools::check()` hides. Blocks `ready` on errors/warnings/real NOTEs.
- 🪟 **`r:winbuilder` fallback** — detects when the plugin's `lib/` is not on `PYTHONPATH` and falls back to `devtools::check_win_*()` directly in R, instead of failing silently with `ModuleNotFoundError`.
- 🧪 **CLI dogfood + e2e tests** — new `tests/cli/automated-tests.sh` and `tests/cli/e2e-tests.sh` exercise plugin structure and public `lib/` modules against fixtures.

## What's new in v2.16.0

- 🌐 **`r:site --deploy` leak guard** — builds the pkgdown site from a clean named temp-branch worktree so untracked working-directory files never leak into the published `gh-pages` branch. `r:site --check-leaks` scans the render surface for stray files.

Full release history: [`CHANGELOG.md`](CHANGELOG.md).

## Quick Start

```bash
# Quick analysis (< 30 seconds)
/rforge:analyze "Update RMediation bootstrap algorithm"

# Ultra-fast (< 10 seconds)
/rforge:quick

# CRAN submission gate (per-package)
/rforge:r:cran-prep

# Ecosystem rollup (2-5 minutes)
/rforge:thorough "Prepare for CRAN release"
```

## Features

✨ **Auto-delegation** - Recognizes task patterns, selects appropriate tools
⚡ **Parallel execution** - Invokes multiple `lib/` modules simultaneously
📊 **Live progress** - Real-time updates as tools complete
🎯 **Smart synthesis** - Combines results into actionable summary
🧠 **ADHD-friendly** - Fast feedback, clear structure, visual progress
🐍 **Pure-Python `lib/`** - `lib/discovery.py`, `lib/deps.py`, `lib/status.py`, `lib/init.py`, `lib/cranlint.py` (pure Python, no R); `lib/rcmd.py` runs R engines for the `r:*` dev-cycle + CRAN commands. No MCP server, no Node.js. See [`docs/lib-modules.md`](docs/lib-modules.md).

## How It Works

```
User Request
    ↓
Pattern Recognition (CODE_CHANGE, BUG_FIX, etc.)
    ↓
Tool Selection (impact, tests, docs, health)
    ↓
Parallel `lib/` invocations (python3 -m lib.* in subprocess)
    ↓
Results Synthesis (impact + quality + maintenance + next steps)
    ↓
Actionable Summary
```

## Skills

### /rforge:analyze
Balanced analysis with recommendations (< 30 seconds)
```bash
/rforge:analyze "Update code"
```

### /rforge:quick
Ultra-fast status check (< 10 seconds)
```bash
/rforge:quick
```

### /rforge:thorough
Comprehensive analysis with R CMD check (2-5 minutes)
```bash
/rforge:thorough "Prepare for CRAN"
```

## Requirements

1. **Python 3.10+** (the `lib/` modules run via `python3 -m lib.<tool>`)
2. **R Environment**
   - R >= 4.0.0
   - devtools package (optional, for `/rforge:thorough`)
   - testthat package (optional)
   - covr package (optional, for coverage analysis)
3. **Claude Code CLI or Claude Desktop**
   - Plugin works in both environments

> **Migrating from v1.2.x?** If you have an `mcpServers.rforge` entry in
> `~/.claude/settings.json`, you can remove it — v1.3.0 no longer needs the
> MCP server. See [`docs/migration/rforge-mcp-deprecation.md`](docs/migration/rforge-mcp-deprecation.md).

## Installation

#### Option 1: Claude Code Marketplace (Recommended)

From inside Claude Code:

```text
/plugin marketplace add Data-Wise/rforge
/plugin install rforge
```

The marketplace install reads `.claude-plugin/marketplace.json` from the
repository, fetches the plugin into `~/.claude/plugins/rforge`, and wires
it up automatically. Works on macOS, Linux, and Windows. Update later with
`/plugin update rforge`.

#### Option 2: Homebrew (macOS)

```bash
# Add the Data-Wise tap
brew tap data-wise/tap

# Install rforge plugin
brew install rforge
```

The Homebrew formula automatically:
- Installs the plugin to `~/.claude/plugins/rforge`
- Makes it available in Claude Code CLI and Claude Desktop

#### Option 3: Manual Installation (Local Development)

**For Claude Code CLI and Claude Desktop:**

```bash
# Clone the repository
git clone https://github.com/Data-Wise/rforge.git
cd rforge

# Install in development mode (symlink - changes reflected immediately)
ln -s $(pwd) ~/.claude/plugins/rforge

# Or install in production mode (copy - stable)
cp -r . ~/.claude/plugins/rforge
```

**Installation locations:**
- Plugin directory: `~/.claude/plugins/rforge`
- Commands: `~/.claude/plugins/rforge/commands/`
- Agent: `~/.claude/plugins/rforge/agents/orchestrator.md`
- Lib: `~/.claude/plugins/rforge/lib/`

### Verify Installation

**Step 1: Check plugin**

```bash
# Check plugin directory exists
ls -la ~/.claude/plugins/rforge

# Verify plugin.json
cat ~/.claude/plugins/rforge/.claude-plugin/plugin.json
```

**Step 2: Check Python**

```bash
python3 --version    # Expect 3.10+
```

**Step 3: Test end-to-end**

```bash
# Navigate to an R package
cd ~/projects/r-packages/active/RMediation

# Start Claude Code
claude

# Test a command
/rforge:status
```

**Expected output:**

```
📊 RMediation - Single Package
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Version: 2.4.0
Tests: 187 passing
Health: 87/100 (B+)
```

### Using in Claude Code CLI

After installation, commands are immediately available:

```bash
# Navigate to any R package
cd ~/my-r-package

# Start Claude Code
claude

# Use rforge commands
/rforge:analyze "Update bootstrap algorithm"
/rforge:status
/rforge:quick
```

### Using in Claude Desktop App

RForge automatically loads when you open Claude Desktop. Commands work the same way:

1. Open Claude Desktop app
2. Navigate conversation to an R package directory (or specify path)
3. Use slash commands: `/rforge:analyze`, `/rforge:status`, etc.

### Migration

- **From v1.2.x:** the `mcpServers.rforge` entry in `~/.claude/settings.json` is no longer needed in v1.3.0. Remove it manually (we don't auto-edit user settings). See [`docs/migration/rforge-mcp-deprecation.md`](docs/migration/rforge-mcp-deprecation.md) for the full migration table.

### Migration from rforge-orchestrator (historical, pre-v1.3.0)

> Only relevant if you skipped v1.2.x and are coming from a much older
> `rforge-orchestrator` setup. v1.3.0 doesn't use any MCP server, so the
> end state is just: remove these entries entirely.

If your `~/.claude/settings.json` has either an `rforge-orchestrator` or `rforge-mcp` entry under `mcpServers`, **delete it**:

```json
// Delete BOTH of these patterns if present:
{
  "mcpServers": {
    "rforge-orchestrator": { ... },
    "rforge-mcp": { ... }
  }
}
```

In v1.3.0+ the plugin runs entirely in-process via `lib/` modules — there's no MCP server to configure. The plugin loads via `/plugin install rforge`; no `settings.json` entries are required.

For the full transition narrative, see [`docs/migration/rforge-mcp-deprecation.md`](docs/migration/rforge-mcp-deprecation.md).

## Pattern Recognition

The orchestrator automatically detects what you're doing:

| Your Request | Pattern | Tools Used |
|-------------|---------|------------|
| "Update algorithm" | CODE_CHANGE | impact, tests, docs, health |
| "Add function" | NEW_FUNCTION | detect, tests, docs |
| "Fix bug" | BUG_FIX | tests, impact |
| "Update docs" | DOCUMENTATION | docs, detect |
| "Release 2.1.0" | RELEASE | health, impact, tests, docs |

## Example Outputs

### Quick Analysis
```
⚡ Quick analysis running...
✅ Done! (8.2 seconds)

📊 QUICK SUMMARY:
✅ Impact: 2 packages (MEDIUM)
✅ Tests: 187/187 passing
⚠️ Docs: NEWS.md needs update
✅ Health: 87/100 (B+)
```

### Full Analysis
```
🎯 IMPACT: MEDIUM
  • 2 packages affected (mediate, sensitivity)
  • Estimated cascade: 4 hours

✅ QUALITY: EXCELLENT
  • Tests: 187/187 passing (94% coverage)
  • CRAN: Clean

📝 MAINTENANCE: 2 items
  • NEWS.md needs entry
  • Vignette example outdated

📋 NEXT STEPS:
  1. Implement changes (3 hours)
  2. Auto-fix documentation
  3. Run cascade for dependents
```

## Architecture

```
┌─────────────────────────────────────┐
│      Claude Code Session            │
│                                     │
│  ┌───────────────────────────────┐ │
│  │  RForge Orchestrator Plugin   │ │
│  │                               │ │
│  │  • Pattern Recognition        │ │
│  │  • Tool Selection             │ │
│  │  • Parallel Execution         │ │
│  │  • Progress Display           │ │
│  │  • Results Synthesis          │ │
│  └───────┬───────────────────────┘ │
│          │                          │
└──────────┼──────────────────────────┘
           │ Parallel python3 -m lib.* calls
           ↓
    ┌──────┴──────┬──────┬──────┐
    ↓             ↓      ↓      ↓
[discovery]  [deps] [status] [init]
    ↓             ↓      ↓      ↓
  (8s)          (5s)   (3s)   (7s)
    │             │      │      │
    └─────────────┴──────┴──────┘
                  │
                  ↓
         Results synthesized
         by orchestrator
```

## Performance

| Mode | Tools | Time | Use Case |
|------|-------|------|----------|
| Quick | 4 quick tools | ~10s | Status check |
| Analyze | 4 quick + synthesis | ~30s | Daily dev |
| Thorough | Background R | 2-5m | Pre-release |

**Time savings:** Parallel execution = 4x faster than sequential!

## ADHD-Friendly Design

1. **Fast feedback** - Results in seconds, not minutes
2. **Clear structure** - Consistent output format
3. **Visual progress** - See what's happening
4. **Actionable** - Always provides next steps
5. **Interruptible** - Can cancel/resume anytime
6. **Incremental** - Results stream as they complete

## Troubleshooting

**"python3: command not found"**
```bash
# Verify Python 3.10+ is on PATH
python3 --version

# macOS: install via Homebrew
brew install python@3.12
```

**"Package not detected"**
```bash
# Run from package directory
cd /path/to/package

# Or specify path explicitly
/rforge:analyze --package /path/to/package
```

**"Analysis too slow"**
- Use `/rforge:quick` for fast status
- Use `/rforge:analyze` for balanced speed/depth
- Only use `/rforge:thorough` when needed

## Configuration

Plugin settings in `plugin.json`:

```json
{
  "settings": {
    "default_mode": "quick",           // quick, analyze, or thorough
    "parallel_execution": true,         // Run tools in parallel
    "show_progress": true,              // Show progress bars
    "auto_synthesize": true             // Auto-generate summary
  }
}
```

## Development

**Plugin structure:**
```
~/.claude/plugins/rforge/
├── .claude-plugin/
│   ├── plugin.json          # Plugin manifest (v2.8.0)
│   ├── marketplace.json     # Marketplace install metadata
│   ├── config.json          # User-tunable options (CRAN mirror, etc.)
│   ├── hooks/
│   │   └── pretooluse.py    # R-aware Write/Edit guard (4 rules)
│   └── skills/
│       └── validation/
│           └── description-sync.md  # DESCRIPTION ↔ NEWS.md drift check
├── commands/                # 33 slash commands (/rforge:*)
├── agents/
│   └── orchestrator.md      # Pattern recognition + delegation
├── lib/                     # Pure-Python analysis modules
│   ├── discovery.py         # Package detection + ecosystem layout
│   ├── deps.py              # Dependency graph + impact
│   ├── status.py            # DESCRIPTION + .STATUS health snapshot
│   ├── init.py              # ~/.rforge/context.json initializer
│   ├── rcmd.py              # R dev-cycle + quality + CRAN-submission engines (v2.7.0)
│   ├── cranlint.py          # CRAN-incoming linter — DESCRIPTION + build-hygiene (v2.3.0)
│   └── formatters.py        # Output formatting helpers
└── docs/                    # User-facing docs
```

## Contributing

Ideas for improvement:
- [ ] Add caching for repeated analyses
- [ ] Track user preferences for tool selection
- [ ] Add more pattern types
- [ ] Improve time estimates
- [ ] Add result export (markdown, JSON)

## License

MIT

## Links

- v1.3.0 absorbed the prior `rforge-mcp` prototype (local-only, never published to GitHub or npm). See [`docs/migration/rforge-mcp-deprecation.md`](docs/migration/rforge-mcp-deprecation.md) for the migration narrative.
- Claude Code: https://claude.com/code
- Documentation: See `docs/` folder

---

**Version:** 2.18.0
**Status:** Active development
**Compatibility:** Claude Code 0.1.0+

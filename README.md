# RForge Orchestrator Plugin

**Auto-delegation orchestrator for RForge MCP tools**

Automatically analyzes R package changes by intelligently delegating to RForge MCP tools and synthesizing results.

## What's new in v1.2.0

- 🛒 **Marketplace install** — one-shot setup via
  `/plugin marketplace add Data-Wise/rforge` (no clone, no symlinks).
  See [`docs/configuration.md`](docs/configuration.md) for tunable
  options (CRAN mirror, vignette engine, R version pin, CLAUDE.md budget).
- 🪝 **R-aware `PreToolUse` hook** — four rules that fire on every
  `Write`/`Edit`: blocks hand-edits to roxygen-generated `man/*.Rd`,
  warns when `R/*.R` edits may need NAMESPACE/DESCRIPTION sync, warns
  on non-SemVer `DESCRIPTION` Version bumps, warns on writes outside
  the active worktree. Diagnostic, not adversarial — only the
  `man/*.Rd` rule blocks. See [`docs/hooks-and-skills.md`](docs/hooks-and-skills.md).
- 🔍 **`description-sync` validation skill** — pure-shell sanity check
  that `DESCRIPTION` Version matches the top entry in `NEWS.md` /
  `CHANGELOG.md`. Catches the most common pre-CRAN release-prep failure.
  No R required.
- 📐 **Plugin Surface architecture diagram** — new Mermaid diagram in
  [`docs/architecture.md`](docs/architecture.md) showing how marketplace,
  config, commands, agents, hooks, and skills relate.

Full changelog: [`CHANGELOG.md`](CHANGELOG.md).

## Quick Start

```bash
# Quick analysis (< 30 seconds)
/rforge:analyze "Update RMediation bootstrap algorithm"

# Ultra-fast (< 10 seconds)
/rforge:quick

# Comprehensive (2-5 minutes)
/rforge:thorough "Prepare for CRAN release"
```

## Features

✨ **Auto-delegation** - Recognizes task patterns, selects appropriate tools
⚡ **Parallel execution** - Calls multiple MCP tools simultaneously
📊 **Live progress** - Real-time updates as tools complete
🎯 **Smart synthesis** - Combines results into actionable summary
🧠 **ADHD-friendly** - Fast feedback, clear structure, visual progress

## How It Works

```
User Request
    ↓
Pattern Recognition (CODE_CHANGE, BUG_FIX, etc.)
    ↓
Tool Selection (impact, tests, docs, health)
    ↓
Parallel MCP Calls (4 tools × 8 sec = 8 sec total, not 32 sec!)
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

**RForge requires BOTH the plugin AND MCP server:**

1. **RForge MCP Server** (required for all functionality)
   - Provides R package analysis tools
   - Must be configured in Claude settings

2. **R Environment**
   - R >= 4.0.0
   - devtools package
   - testthat package
   - covr package (optional, for coverage analysis)

3. **Claude Code CLI or Claude Desktop**
   - Plugin works in both environments

## Installation

RForge has a two-part installation: the plugin (commands/UI) and the MCP server (backend tools).

### Part 1: Install RForge MCP Server

The MCP server must be installed FIRST and configured in Claude settings.

```bash
# Install rforge-mcp globally
npm install -g rforge-mcp
```

**Configure in Claude settings:**

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "npx",
      "args": ["rforge-mcp"]
    }
  }
}
```

**Or use project-specific configuration:**

Add to `.claude/settings.local.json` in your R package:

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "npx",
      "args": ["rforge-mcp"],
      "env": {
        "RFORGE_MODE": "default"
      }
    }
  }
}
```

**Verify MCP server is configured:**

```bash
# Check settings file
cat ~/.claude/settings.json | grep rforge-mcp

# Expected output:
# "rforge-mcp": {
```

### Part 2: Install RForge Plugin

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
- Reminds you to install rforge-mcp if not present

#### Option 3: npm (When published)

```bash
# Install from npm (after publishing)
npm install -g @data-wise/rforge-plugin

# Plugin will auto-install to ~/.claude/plugins/rforge
```

#### Option 4: Manual Installation (Local Development)

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

### Verify Complete Installation

**Step 1: Check MCP server**

```bash
# Verify npm package is installed
npm list -g rforge-mcp

# Expected output:
# └── rforge-mcp@0.1.0
```

**Step 2: Check plugin**

```bash
# Check plugin directory exists
ls -la ~/.claude/plugins/rforge

# Verify plugin.json
cat ~/.claude/plugins/rforge/.claude-plugin/plugin.json
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
Connecting to rforge-mcp...
✅ RForge MCP server connected

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

### MCP Server Configuration Options

**Basic configuration (most users):**

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "npx",
      "args": ["rforge-mcp"]
    }
  }
}
```

**Advanced configuration with environment variables:**

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "npx",
      "args": ["rforge-mcp"],
      "env": {
        "RFORGE_MODE": "default",
        "RFORGE_FORMAT": "terminal"
      }
    }
  }
}
```

**Environment variables:**
- `RFORGE_MODE` - Default mode: `default` (< 10s), `debug` (< 120s), `optimize` (< 180s), `release` (< 300s)
- `RFORGE_FORMAT` - Output format: `terminal`, `json`, `markdown`

### Migration from rforge-orchestrator

If you previously used `rforge-orchestrator` from the monorepo:

**Important:** The MCP server name changed from `rforge-orchestrator` to `rforge-mcp`.

**Update your settings:**

```json
// OLD (remove this):
{
  "mcpServers": {
    "rforge-orchestrator": { ... }
  }
}

// NEW (use this):
{
  "mcpServers": {
    "rforge-mcp": { ... }
  }
}
```

**See [MCP-MIGRATION.md](MCP-MIGRATION.md) for complete migration guide.**

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
           │ Parallel MCP calls
           ↓
    ┌──────┴──────┬──────┬──────┐
    ↓             ↓      ↓      ↓
[Impact]     [Tests] [Docs] [Health]
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

**"RForge MCP not found"**
```bash
npx rforge-mcp configure
# Then restart Claude Code
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
│   ├── plugin.json          # Plugin manifest (v1.2.0)
│   ├── marketplace.json     # Marketplace install metadata
│   ├── config.json          # User-tunable options (CRAN mirror, etc.)
│   ├── hooks/
│   │   └── pretooluse.py    # R-aware Write/Edit guard (4 rules)
│   └── skills/
│       └── validation/
│           └── description-sync.md  # DESCRIPTION ↔ NEWS.md drift check
├── commands/                # 15 slash commands (/rforge:*)
├── agents/
│   └── orchestrator.md      # Pattern recognition + delegation
├── lib/
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

- RForge MCP Server: https://github.com/data-wise/rforge-mcp
- Claude Code: https://claude.com/code
- Documentation: See `docs/` folder

---

**Version:** 0.1.0
**Status:** Active development
**Compatibility:** Claude Code 0.1.0+

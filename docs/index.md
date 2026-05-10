# RForge Plugin

[![Version](https://img.shields.io/github/package-json/v/Data-Wise/rforge?label=version&color=blue)](https://github.com/Data-Wise/rforge/releases)
[![npm](https://img.shields.io/npm/v/@data-wise/rforge-plugin?label=npm&color=red)](https://www.npmjs.com/package/@data-wise/rforge-plugin)
[![License: MIT](https://img.shields.io/github/license/Data-Wise/rforge?color=green)](https://github.com/Data-Wise/rforge/blob/main/LICENSE)
[![CI](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml/badge.svg?branch=dev)](https://github.com/Data-Wise/rforge/actions/workflows/ci.yml)

**R package ecosystem orchestrator for Claude Code — 15 commands, R-aware hooks, validation skills.**

Automatically analyzes R package changes by intelligently delegating to RForge MCP tools and synthesizing results. As of v1.2.0 the MCP server is optional — the plugin works standalone via Claude Code's built-in tools.

## What's new in v1.2.0

- 🛒 **Marketplace install** — `/plugin marketplace add Data-Wise/rforge`
- 🪝 **R-aware `PreToolUse` hook** — 4 rules (block `man/*.Rd` edits, warn on `R/*.R` and DESCRIPTION SemVer drift, warn on outside-worktree writes). See [Hooks & Skills](hooks-and-skills.md).
- 🔍 **`description-sync` validation skill** — pure-shell DESCRIPTION ↔ NEWS.md drift check. No R required.
- 📐 **Plugin Surface diagram** in [Architecture](architecture.md) (Mermaid).
- 🔓 **MCP decoupled** — `npm install` now works without `rforge-mcp` (was failing with 404 for fresh users).
- ⚙️ **User options** — see [Configuration](configuration.md) for `cran_mirror`, `vignette_engine`, `r_version_pin`, `claude_md_budget`.

Full release notes: [CHANGELOG.md](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md).

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

1. **RForge MCP Server** - Must be installed and configured
   ```bash
   npx rforge-mcp configure
   ```

2. **R Environment**
   - R >= 4.0.0
   - devtools
   - testthat
   - covr (optional, for coverage)

3. **Claude Code** - This is a Claude Code plugin

## Installation

1. **Install RForge MCP**
   ```bash
   npx rforge-mcp configure
   ```

2. **Install this plugin** (recommended: Claude Code marketplace)
   ```text
   /plugin marketplace add Data-Wise/rforge
   /plugin install rforge
   ```

   Alternative options (Homebrew, npm, manual symlink) are documented in
   the main [README](https://github.com/Data-Wise/rforge#installation).

3. **Restart Claude Code**

4. **Test it**
   ```bash
   cd /path/to/r-package
   /rforge:analyze "Test installation"
   ```

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

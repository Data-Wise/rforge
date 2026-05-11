# RForge Plugin - Reference Card

> **Version:** 1.3.0 | **Last Updated:** 2026-05-11

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RFORGE ORCHESTRATOR REFERENCE                                     v0.1.0  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COMMANDS (3)                                                               │
│  ─────────                                                                  │
│                                                                             │
│  /rforge:analyze [task]           Balanced analysis (~30 sec)              │
│    Auto-detects patterns, delegates to RForge MCP, synthesizes results     │
│    Example: /rforge:analyze "Update bootstrap algorithm"                   │
│                                                                             │
│  /rforge:quick                    Ultra-fast check (~10 sec)               │
│    Quick health check with minimal tool calls                              │
│    Use: Pre-commit checks, quick status                                    │
│                                                                             │
│  /rforge:thorough [milestone]     Comprehensive review (2-5 min)           │
│    Full analysis with all tools, detailed recommendations                  │
│    Example: /rforge:thorough "Prepare for CRAN release"                    │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  HOW IT WORKS                                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Pattern Recognition → Analyzes your task description                   │
│     • CODE_CHANGE - Code modifications                                     │
│     • BUG_FIX - Bug fixes                                                  │
│     • RELEASE_PREP - Release preparation                                   │
│     • HEALTH_CHECK - Quick status check                                    │
│     • FEATURE_ADD - New features                                           │
│                                                                             │
│  2. Tool Selection → Picks appropriate RForge MCP tools                     │
│     • impact - Code change impact analysis                                 │
│     • tests - Test coverage and execution                                  │
│     • docs - Documentation completeness                                    │
│     • health - Package health check                                        │
│     • rdoc - R documentation check                                         │
│                                                                             │
│  3. Parallel Execution → Calls multiple tools simultaneously               │
│     ⚡ 4 tools × 8 sec each = 8 sec total (not 32 sec!)                     │
│                                                                             │
│  4. Results Synthesis → Combines into actionable summary                   │
│     • Impact assessment                                                    │
│     • Quality metrics                                                      │
│     • Maintenance concerns                                                 │
│     • Next steps                                                           │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  COMMON WORKFLOWS                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  After Code Changes              │  Before Commit                          │
│  1. Make changes                 │  1. /rforge:quick                       │
│  2. /rforge:analyze "what changed"│  2. Fix any issues                      │
│  3. Review impact + next steps   │  3. git commit                          │
│  4. Run suggested checks         │                                         │
│                                  │  Release Preparation                    │
│  Feature Development             │  1. /rforge:thorough "CRAN release"     │
│  1. /rforge:analyze "add feature"│  2. Address all recommendations         │
│  2. Check impact on tests/docs   │  3. Run R CMD check                     │
│  3. Update based on suggestions  │  4. Submit to CRAN                      │
│  4. /rforge:quick (verify)       │                                         │
│                                  │                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  REQUIREMENTS                                                               │
│  • Claude Code CLI installed                                               │
│  • RForge MCP server configured in ~/.claude/settings.json                 │
│  • R package project (DESCRIPTION file required)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  TIPS                                                                       │
│  • Use /rforge:quick for pre-commit checks - it's fast!                     │
│  • /rforge:analyze is best for understanding impact of changes              │
│  • /rforge:thorough before CRAN submission finds issues early               │
│  • Orchestrator runs tools in parallel - much faster than sequential        │
│  • Pattern recognition improves - describe tasks clearly for best results   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Command Reference

| Command | Speed | When to Use | Output |
|---------|-------|-------------|--------|
| `/rforge:init` | <5s | First run on a package or ecosystem | Writes `~/.rforge/context.json` |
| `/rforge:quick` | ~10s | Pre-commit, quick status | Basic health check |
| `/rforge:analyze` | ~30s | After changes, understand impact | Impact + recommendations |
| `/rforge:thorough` | 2-5m | Release prep, major changes | Comprehensive analysis |

---

## Pattern Recognition

The orchestrator automatically detects task types:

| Pattern | Triggers When... | Tools Called |
|---------|------------------|--------------|
| **CODE_CHANGE** | "update", "modify", "change code" | impact, tests, docs |
| **BUG_FIX** | "fix", "bug", "error" | impact, tests |
| **RELEASE_PREP** | "release", "CRAN", "publish" | health, tests, docs, rdoc |
| **HEALTH_CHECK** | "check", "status", "quick" | health |
| **FEATURE_ADD** | "add feature", "new function" | impact, tests, docs |

---

## RForge Lib Modules (v1.3.0+)

As of v1.3.0 the plugin is self-contained — slash commands dispatch to pure-Python `lib/` modules instead of an MCP server. CLI form: `python3 -m lib.<module>`.

| Module | Purpose | Speed |
|--------|---------|-------|
| `lib.discovery` | Ecosystem + package detection | <2s |
| `lib.deps` | Dependency graph + impact analysis | ~8s |
| `lib.status` | Ecosystem health snapshot | <5s |
| `lib.init` | Initialize `~/.rforge/context.json` | <5s |

See [`docs/lib-modules.md`](lib-modules.md) and the [reference API docs](reference/discovery.md) for full call signatures.

---

## Hooks & Skills (v1.2.0+)

RForge ships autonomous tooling that activates without an explicit
slash command.

**`pretooluse.py` hook** — runs on every `Write`/`Edit`:

| Rule | Severity |
|------|----------|
| Edit `man/*.Rd` (roxygen-generated) | **BLOCK** |
| Edit `R/*.R` | warn (NAMESPACE/DESCRIPTION reminder) |
| Bad SemVer in `DESCRIPTION` `Version:` | warn |
| Write outside current worktree | warn |

**`skills/validation/description-sync.md`** — verifies `DESCRIPTION`
`Version:` matches the top entry of `NEWS.md` / `CHANGELOG.md`. Pure
shell, no R required. Runs in `release` mode pre-CRAN.

See [Hooks & Skills Reference](hooks-and-skills.md) for full details.

---

## Installation

**Claude Code marketplace (Recommended, v1.2.0+):**

From inside Claude Code:

```text
/plugin marketplace add Data-Wise/rforge
/plugin install rforge
```

Update later with `/plugin update rforge`. Works on macOS, Linux, Windows.

**Homebrew (macOS):**

```bash
brew install data-wise/tap/rforge
```

**Manual:**

```bash
git clone https://github.com/Data-Wise/rforge.git
ln -s "$(pwd)/rforge" ~/.claude/plugins/rforge
```

See the [Home page](index.md#installation) for the full matrix of
install options.

---

## Configuration

RForge MCP server must be configured in `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "node",
      "args": ["/path/to/rforge-mcp/dist/index.js"]
    }
  }
}
```

---

## File Structure

```
rforge/
├── .claude-plugin/        # Plugin manifest + extras (v1.3.0)
│   ├── plugin.json
│   ├── marketplace.json
│   ├── config.json
│   ├── hooks/pretooluse.py
│   └── skills/validation/description-sync.md
├── commands/              # 15 slash commands (/rforge:*)
├── agents/                # 1 orchestrator agent
│   └── orchestrator.md
├── scripts/               # Installation scripts
│   ├── install.sh
│   └── uninstall.sh
├── lib/formatters.py
└── docs/                  # Documentation
    └── REFCARD.md (this file)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Commands not showing | Restart Claude Code, check `~/.claude/plugins/` |
| "RForge MCP not configured" | Add rforge-mcp to settings.json |
| Slow performance | Check RForge MCP server is running |
| Pattern not recognized | Use clearer task description |
| No R package found | Must be in R package directory (has DESCRIPTION) |

---

## Examples

### After Code Changes
```
/rforge:analyze "Updated bootstrap algorithm in mediate() function"

→ Pattern: CODE_CHANGE
→ Tools: impact, tests, docs
→ Result: Impact assessment + test status + doc updates needed
```

### Quick Pre-commit Check
```
/rforge:quick

→ Pattern: HEALTH_CHECK
→ Tools: health (minimal)
→ Result: Quick health status + blocking issues
```

### Before CRAN Release
```
/rforge:thorough "Prepare v2.0.0 for CRAN submission"

→ Pattern: RELEASE_PREP
→ Tools: health, tests, docs, rdoc (all tools)
→ Result: Comprehensive checklist + recommendations
```

---

## More Documentation

- **Main README:** `README.md`
- **Installation Guide:** Homebrew formula includes full guide
- **Plugin Repository:** https://github.com/Data-Wise/rforge
- **GitHub Releases:** https://github.com/Data-Wise/rforge/releases

---

## Comparison: When to Use Each Command

| Situation | Use | Why |
|-----------|-----|-----|
| Made small code change | `/rforge:analyze` | Understand impact |
| About to commit | `/rforge:quick` | Fast sanity check |
| Preparing release | `/rforge:thorough` | Catch everything |
| Testing new feature | `/rforge:analyze` | Check tests/docs |
| Fixing bug | `/rforge:analyze` | Verify fix, check tests |
| Daily development | `/rforge:quick` | Regular health checks |

---

**Quick Start:** `/rforge:quick` → Get instant health check of your R package!

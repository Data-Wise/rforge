# 📚 RForge Plugin - Reference Card

> **Version:** 2.0.0 | **Last Updated:** 2026-05-12

!!! tip "TL;DR (30 seconds)"
    - **What:** All 16 commands in one page — categorized by use case.
    - **Why:** Forget command syntax? Scan the ASCII box below.
    - **How:** Daily? `/rforge:status` `/rforge:quick`. After changes? `/rforge:analyze "what?"`. Pre-CRAN? `/rforge:thorough`.
    - **Next:** [Commands reference](commands.md) for full per-command docs.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  RFORGE PLUGIN REFERENCE                                            v2.0.0  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COMMANDS (16)                                                              │
│  ─────────                                                                  │
│                                                                             │
│  DAILY                                                                      │
│    /rforge:status         Ecosystem status dashboard                        │
│    /rforge:next           Get next-task recommendation                      │
│    /rforge:quick          Ultra-fast snapshot (<10s)                        │
│                                                                             │
│  ANALYSIS                                                                   │
│    /rforge:analyze        Mode-aware analysis (~30s)                        │
│    /rforge:thorough       Comprehensive analysis + R CMD check (2-5m)       │
│    /rforge:impact         Change impact across ecosystem                    │
│    /rforge:deps           Dependency graph                                  │
│    /rforge:detect         Auto-detect project structure                     │
│                                                                             │
│  ECOSYSTEM                                                                  │
│    /rforge:health         Ecosystem health check                            │
│    /rforge:cascade        Plan coordinated updates across packages          │
│    /rforge:release        Plan CRAN submission sequence                     │
│                                                                             │
│  TASKS                                                                      │
│    /rforge:capture        Capture tasks / ideas                             │
│    /rforge:complete       Mark complete (with doc cascade)                  │
│                                                                             │
│  CHECKS                                                                     │
│    /rforge:r:check        R CMD check (smart output parsing)                │
│    /rforge:docs:check     Documentation drift check                         │
│                                                                             │
│  SETUP                                                                      │
│    /rforge:init           Initialize ~/.rforge/context.json                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How It Works (v1.3.0+)

```text
User invokes /rforge:<command>
    ↓
Claude reads commands/<name>.md as its prompt
    ↓
Claude orchestrates lib/ modules + Bash tools as needed
    ├── python3 -m lib.discovery   (ecosystem + package detection)
    ├── python3 -m lib.deps        (dependency graph + impact)
    ├── python3 -m lib.status      (health snapshot)
    └── python3 -m lib.init        (~/.rforge/context.json setup)
    ↓
PreToolUse hook diagnoses risky Write/Edit ops (man/*.Rd block, etc.)
    ↓
Validation skills run autonomously (description-sync, etc.)
    ↓
Results synthesized into actionable summary
```

No MCP server. No Node.js. No R subprocess for status/discovery/deps —
only `r:check` and `thorough` shell out to R.

---

## Common Workflows

| Daily check-in              | Pre-commit                      |
|-----------------------------|---------------------------------|
| 1. `/rforge:status`         | 1. `/rforge:quick`              |
| 2. `/rforge:next`           | 2. Fix any issues               |
|                             | 3. `git commit`                 |

| After code changes               | Pre-CRAN release                |
|----------------------------------|---------------------------------|
| 1. `/rforge:analyze "what?"`     | 1. `/rforge:thorough`           |
| 2. Review impact + tests         | 2. `/rforge:r:check`            |
| 3. `/rforge:cascade` if dep      | 3. `/rforge:docs:check`         |
|    updates needed                | 4. `/rforge:release`            |

---

## Requirements

- **Claude Code CLI** installed
- **Python 3.10+** (for `lib/` modules)
- **R 4.0+** — only needed for `r:check` / `thorough` workflows

No MCP server or Node.js required (since v1.3.0).

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

## Pattern Recognition

When `/rforge:analyze` runs, it detects task types and selects which `lib/` modules to invoke:

| Pattern | Triggers When... | Modules / Tools |
|---------|------------------|-----------------|
| **CODE_CHANGE** | "update", "modify", "change code" | `lib.deps` (impact), `lib.discovery` |
| **BUG_FIX** | "fix", "bug", "error" | `lib.deps`, `lib.status` |
| **RELEASE_PREP** | "release", "CRAN", "publish" | `lib.status`, R CMD check, `description-sync` |
| **HEALTH_CHECK** | "check", "status", "quick" | `lib.status` |
| **FEATURE_ADD** | "add feature", "new function" | `lib.deps`, `lib.discovery` |

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

User-tunable settings live in `.claude-plugin/config.json` (CRAN mirror, vignette engine, R version pin, CLAUDE.md budget). See [`docs/configuration.md`](configuration.md) for the full list of options.

No `~/.claude/settings.json` entries required since v1.3.0 — the plugin is fully self-contained.

---

## File Structure

```text
rforge/
├── .claude-plugin/        # Plugin manifest + extras (v2.0.0)
│   ├── plugin.json
│   ├── marketplace.json
│   ├── config.json
│   ├── hooks/pretooluse.py
│   └── skills/validation/description-sync.md
├── commands/              # 16 slash commands (/rforge:*)
│   ├── docs/check.md      # /rforge:docs:check (v2.0.0+)
│   └── r/check.md         # /rforge:r:check (v2.0.0+)
├── agents/                # 1 orchestrator agent
│   └── orchestrator.md
├── scripts/               # Installation scripts
│   ├── install.sh
│   └── uninstall.sh
├── lib/                   # Pure-Python analysis modules (v1.3.0+)
│   ├── discovery.py
│   ├── deps.py
│   ├── status.py
│   ├── init.py
│   └── formatters.py
└── docs/                  # Documentation
    └── REFCARD.md (this file)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Commands not showing | Restart Claude Code, check `~/.claude/plugins/` |
| `/rforge:<old-name>` says "RENAMED" | Use the new v2.0.0 name (see [migration tutorial](migration/v2.0.0-rename.md)) |
| Slow performance | Check Python 3.10+ is on PATH; `lib/` modules should run in seconds |
| Pattern not recognized | Use clearer task description |
| No R package found | Must be in R package directory (has DESCRIPTION) |
| R CMD check missing | Install R 4.0+ from CRAN; required for `r:check` / `thorough` only |

---

## Examples

### After Code Changes

```text
/rforge:analyze "Updated bootstrap algorithm in mediate() function"

→ Pattern: CODE_CHANGE
→ Modules: lib.deps (impact), lib.discovery
→ Result: Impact assessment + test status + doc updates needed
```

### Quick Pre-commit Check

```text
/rforge:quick

→ Pattern: HEALTH_CHECK
→ Module: lib.status
→ Result: Quick health status + blocking issues
```

### Before CRAN Release

```text
/rforge:thorough "Prepare for CRAN submission"

→ Pattern: RELEASE_PREP
→ Modules: lib.status + R CMD check + description-sync skill
→ Result: Comprehensive checklist + recommendations
```

---

## More Documentation

- **Main README:** [README.md](https://github.com/Data-Wise/rforge/blob/main/README.md) on GitHub
- **Plugin Repository:** <https://github.com/Data-Wise/rforge>
- **GitHub Releases:** <https://github.com/Data-Wise/rforge/releases>
- **Migration tutorials:** [`docs/migration/`](migration/)

---

## Comparison: When to Use Each Command

| Situation | Use | Why |
|-----------|-----|-----|
| Made small code change | `/rforge:analyze` | Understand impact |
| About to commit | `/rforge:quick` | Fast sanity check |
| Preparing release | `/rforge:thorough` | Catch everything |
| Testing new feature | `/rforge:analyze` | Check tests/docs |
| Fixing bug | `/rforge:analyze` | Verify fix, check tests |
| Daily development | `/rforge:status` + `/rforge:next` | Dashboard + decision |
| Running R CMD check | `/rforge:r:check` | Single-package deep check |
| Documentation drift | `/rforge:docs:check` | NEWS.md, API consistency |

---

**Quick Start:** `/rforge:status` → Get instant health snapshot of your R package ecosystem!

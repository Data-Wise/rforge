# RForge Plugin - Documentation

> **Complete documentation for the RForge Plugin v2.3.0**

---

## 📚 Documentation Index

### Quick References

| Document | Purpose | Read Time |
|----------|---------|-----------|
| **[QUICK-START.md](QUICK-START.md)** | Get running in 3 minutes | 2 min |
| **[REFCARD.md](REFCARD.md)** | One-page command reference | 2 min |

### Detailed Guides

| Document | Purpose | Location |
|----------|---------|----------|
| **[README.md](../README.md)** | Main plugin documentation | Root |
| **Homebrew Formula** | Installation and usage | `brew info data-wise/tap/rforge` |

---

## 🚀 Getting Started

**New users:** Start with [QUICK-START.md](QUICK-START.md)

**Need a reminder:** Check [REFCARD.md](REFCARD.md)

**Installing:** Run `brew install data-wise/tap/rforge`

---

## 📖 What's What

### QUICK-START.md
Perfect for:
- First-time users
- Getting up and running fast
- Learning the headline commands (`/rforge:quick`, `analyze`, `thorough`)

**Contents:**
- Installation (1 minute)
- Prerequisites
- First commands to try
- Common workflows
- Example session

### REFCARD.md
Perfect for:
- Quick command lookups
- Understanding pattern recognition
- One-page printable reference

**Contents:**
- All commands in tables (28 total)
- Pattern recognition guide
- `lib/` modules overview
- Common workflows
- Troubleshooting quick reference

### Main README (../README.md)
Perfect for:
- Detailed feature explanation
- Understanding how it works
- Architecture overview

**Contents:**
- Features and capabilities
- How orchestration works
- Pattern recognition details
- Installation options
- Examples and use cases

---

## 📂 Plugin Structure

```
rforge/
├── .claude-plugin/            # Claude Code plugin manifest + extras
│   ├── plugin.json            # Plugin manifest (v2.3.0)
│   ├── marketplace.json       # Marketplace install metadata
│   ├── config.json            # User-tunable options
│   ├── hooks/
│   │   └── pretooluse.py      # R-aware Write/Edit guard
│   └── skills/
│       └── validation/        # Autonomous validation skills
├── commands/                  # 28 slash commands (/rforge:*)
├── agents/                    # Orchestrator agent
│   └── orchestrator.md        # Pattern recognition + delegation
├── docs/                      # 👈 You are here
│   ├── README.md              # This file
│   ├── QUICK-START.md         # 3-minute guide
│   ├── REFCARD.md             # One-page reference
│   ├── architecture.md        # Plugin Surface diagram + details
│   ├── hooks-and-skills.md    # Hook rules + skill reference
│   └── configuration.md       # config.json options
├── lib/
│   └── formatters.py          # Output formatting helpers
├── tests/                     # Validation suite (test-all.sh)
├── scripts/                   # Installation scripts
├── README.md                  # Main documentation
├── package.json               # npm metadata
└── LICENSE                    # MIT license
```

---

## 🎯 Finding What You Need

### I want to...

**Get started quickly**
→ [QUICK-START.md](QUICK-START.md)

**Look up a command**
→ [REFCARD.md](REFCARD.md)

**Install the plugin**
→ Run `brew install --HEAD data-wise/tap/rforge`

**Understand pattern recognition**
→ [REFCARD.md](REFCARD.md#pattern-recognition)

**See example workflows**
→ [QUICK-START.md](QUICK-START.md#common-workflows) or [REFCARD.md](REFCARD.md#common-workflows)

**Troubleshoot issues**
→ [QUICK-START.md](QUICK-START.md#troubleshooting) or [REFCARD.md](REFCARD.md#troubleshooting)

**Installation & setup**
→ [QUICK-START.md](QUICK-START.md#prerequisites)

---

## 🔧 How It Works

The orchestrator uses a **4-step process**:

1. **Pattern Recognition** - Analyzes your task description
   - CODE_CHANGE, BUG_FIX, RELEASE_PREP, HEALTH_CHECK, FEATURE_ADD

2. **Module Selection** - Picks appropriate `lib/` modules + Bash tools
   - `lib.discovery`, `lib.deps`, `lib.status`, `lib.init`, R CMD check, etc.

3. **Parallel Execution** - Invokes multiple modules simultaneously
   - 4 modules × 8 sec = 8 sec total (not 32 sec!)

4. **Results Synthesis** - Combines into actionable summary
   - Impact + quality + maintenance + next steps

See [REFCARD.md](REFCARD.md) for detailed pattern recognition guide.

---

## 💡 Key Features

✨ **Auto-delegation** - Recognizes task patterns, selects appropriate tools

⚡ **Parallel execution** - Runs multiple pure-Python `lib/` modules at once (no MCP server)

📊 **Live progress** - Real-time updates as tools complete

🎯 **Smart synthesis** - Combines results into actionable summary

📦 **CRAN-incoming hardening (v2.3.0)** - `r:cran-prep` runs strict Suggests-withholding passes by default (blocking `ready`) plus Tier 4 advisory checks (`description`, `build-hygiene`, `docs-consistency`) via `lib/cranlint.py`

🧠 **ADHD-friendly** - Fast feedback, clear structure, visual progress

---

## 📊 Command Comparison

| Command | Speed | Use Case | Tools Called |
|---------|-------|----------|--------------|
| `/rforge:quick` | ~10s | Pre-commit checks | health (minimal) |
| `/rforge:analyze` | ~30s | After changes | impact, tests, docs |
| `/rforge:thorough` | 2-5m | Release prep | All tools |

---

## 🔗 External Links

- **Plugin Repository:** https://github.com/Data-Wise/rforge
- **GitHub Releases:** https://github.com/Data-Wise/rforge/releases
- **Homebrew Tap:** https://github.com/Data-Wise/homebrew-tap
- **Homebrew Formula:** `brew info data-wise/tap/rforge`

---

## 📦 Installation

**Claude Code marketplace (Recommended for v1.2.0+):**

```text
/plugin marketplace add Data-Wise/rforge
```

**Homebrew (stable):**

```bash
brew install --HEAD data-wise/tap/rforge
```

**Manual:**

```bash
cd ~/.claude/plugins
git clone https://github.com/Data-Wise/rforge.git
```

**Uninstall:**

```bash
brew uninstall rforge
```

---

## ⚙️ Configuration

User-tunable settings live in `.claude-plugin/config.json` (CRAN mirror,
vignette engine, R version pin, CLAUDE.md budget). See
[configuration.md](configuration.md) for the full option list.

No `~/.claude/settings.json` entries required since v1.3.0 — the plugin
runs entirely in-process. If you have a stale `mcpServers.rforge` entry
from a previous version, remove it (see
[migration/rforge-mcp-deprecation.md](migration/rforge-mcp-deprecation.md)).

---

## 📝 Document Maintenance

**Last Updated:** 2026-06-02
**Plugin Version:** 2.3.0
**Documentation Version:** 2.3.0

**Releases:** https://github.com/Data-Wise/rforge/releases

---

**Need help?** Start with [QUICK-START.md](QUICK-START.md) or check [REFCARD.md](REFCARD.md) for quick answers!

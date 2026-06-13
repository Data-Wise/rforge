# 📚 RForge Plugin - Reference Card

> **Version:** {{ rforge.version }} | **Last Updated:** {{ rforge.release_date }}

!!! tip "TL;DR (30 seconds)"
    - **What:** All {{ rforge.command_count }} commands in one page — categorized by use case.
    - **Why:** Forget command syntax? Scan the ASCII box below.
    - **How:** Daily? `/rforge:status` `/rforge:quick`. After changes? `/rforge:analyze "what?"`. Per-package CRAN gate? `/rforge:r:cran-prep`. Ecosystem rollup? `/rforge:thorough`.
    - **Next:** [Commands reference](commands.md) for full per-command docs.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  RFORGE PLUGIN REFERENCE                                            v{{ rforge.version }}  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  COMMANDS ({{ rforge.command_count }})                                                              │
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
│    /rforge:docs:check     Documentation drift check                         │
│                                                                             │
│  SETUP                                                                      │
│    /rforge:init           Initialize ~/.rforge/context.json                 │
│                                                                             │
│  R DEV CYCLE (v2.1.0)                                                       │
│    /rforge:r:load         Load package namespace (pkgload)                  │
│    /rforge:r:document     Regenerate Rd docs + NAMESPACE (roxygen2)         │
│    /rforge:r:test         Run tests, pass/fail/skip counts (testthat)       │
│    /rforge:r:check        R CMD check with structured output (rcmdcheck)    │
│    /rforge:r:coverage     Coverage report + untested lines (covr)           │
│    /rforge:r:build        Build source tarball (pkgbuild)                   │
│    /rforge:r:install      Install locally (R CMD INSTALL)                   │
│    /rforge:r:site         Build pkgdown website                             │
│    /rforge:r:cycle        document → test → check in one pass               │
│                                                                             │
│  R QUALITY (v2.1.0)                                                         │
│    /rforge:r:lint         Static analysis (lintr)                           │
│    /rforge:r:spell        Spell check (spelling)                            │
│    /rforge:r:urlcheck     URL breakage check (urlchecker)                   │
│    /rforge:r:style        Auto-format source (styler)                       │
│    /rforge:r:deps-sync    Reconcile DESCRIPTION vs code usage (--write)     │
│                                                                             │
│  CRAN SUBMISSION (v2.2.0)                                                   │
│    /rforge:r:revdep       Reverse-dep check vs CRAN downstream (revdepcheck)│
│    /rforge:r:goodpractice Advisory best-practice bundle (goodpractice)      │
│    /rforge:r:winbuilder   Dispatch to win-builder R-devel — async           │
│    /rforge:r:rhub         Multi-platform checks via R-hub v2 — async        │
│    /rforge:r:cran-prep    Full CRAN gate + strict passes + cran-comments.md │
│    /rforge:r:submit       Pre-release of tarball + CRAN submit handoff      │
│                                                                             │
│  CRAN-INCOMING STRICT (v2.3.0)                                              │
│    r:check --strict       Both Suggests-withholding flavor passes           │
│    r:check --incoming     + opt-in CRAN-incoming _R_CHECK_* bundle          │
│    cran-prep stages:      check, check (noSuggests), check (suggests-only), │
│                           [check (incoming)], description, build-hygiene,   │
│                           docs-consistency  (strict ERROR blocks ready)     │
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
only `r:*` commands and `thorough` shell out to R (via `lib.rcmd`).

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
- **R 4.0+** — needed for all `r:*` commands and `thorough`

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
| `lib.rcmd` | R dev-cycle + quality + CRAN-submission engines (v2.2.0) | R-bound |
| `lib.cranlint` | CRAN-incoming linter — DESCRIPTION + build-hygiene (v2.3.0) | <2s |

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
├── .claude-plugin/        # Plugin manifest + extras (v{{ rforge.version }})
│   ├── plugin.json
│   ├── marketplace.json
│   ├── config.json
│   ├── hooks/pretooluse.py
│   └── skills/validation/description-sync.md
├── commands/              # {{ rforge.command_count }} slash commands (/rforge:*)
│   ├── docs/check.md      # /rforge:docs:check (v2.0.0+)
│   └── r/                 # /rforge:r:* (v2.0.0+, expanded v2.1.0, v2.2.0)
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
│   ├── rcmd.py            # R dev-cycle + quality + CRAN-submission engines (v2.7.0)
│   ├── cranlint.py        # CRAN-incoming linter (DESCRIPTION + build-hygiene) (v2.3.0)
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
- **Migration tutorials:** [v2.0.0 rename](migration/v2.0.0-rename.md) · [rforge-mcp deprecation](migration/rforge-mcp-deprecation.md)

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
| CRAN pre-submission gate | `/rforge:r:cran-prep` | Full gate + cran-comments.md |
| CRAN Windows check | `/rforge:r:winbuilder` | Async R-devel on Windows |
| CRAN multi-platform | `/rforge:r:rhub` | Async GitHub Actions matrix |
| Reverse-dep check | `/rforge:r:revdep` | CRAN downstream obligation |
| Advisory best practices | `/rforge:r:goodpractice` | Pre-submission advisory pass |

---

**Quick Start:** `/rforge:status` → Get instant health snapshot of your R package ecosystem!

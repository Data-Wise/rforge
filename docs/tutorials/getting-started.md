# Getting started with rforge

> **For whom:** First-time rforge user. You have Claude Code installed
> and at least one R package directory you want to analyze.
> **Estimated time:** 10 minutes.
> **Prior knowledge:** Basic familiarity with R packages (you know what
> a `DESCRIPTION` file is). No prior rforge experience required.

This tutorial walks through installing rforge, running your first
analysis, and understanding what each command does. By the end you'll
know the three headline commands (`/rforge:detect`, `/rforge:status`,
`/rforge:analyze`) and where to look when something doesn't work.

## Step 1: Install

Pick one — they're equivalent for v1.3.0+:

```zsh
# Claude Code marketplace (recommended — single command)
/plugin marketplace add Data-Wise/rforge

# Or via Homebrew
brew install data-wise/tap/rforge

# Or via npm
npm install -g @data-wise/rforge-plugin
```

Verify the plugin loaded:

```text
/help
```

You should see commands prefixed `/rforge:` in the listing. If not,
restart Claude Code and try again.

## Step 2: Open an R package in Claude Code

```zsh
cd ~/your/r/package    # any directory containing a DESCRIPTION file
claude
```

If you don't have an R package handy, the tutorial works on any folder
that *contains* one or more package subdirectories (an "ecosystem"
layout — see Step 3).

## Step 3: Detect the project structure

```text
/rforge:detect
```

Expected output (single package):

```text
📦 Single: /Users/you/your/r/package
   Packages: 1 | mode: minimal | config: not found

   ├─ medfit 1.0.0
```

Or (ecosystem with multiple packages):

```text
🏗️  Ecosystem: /Users/you/your/r/packages
   Packages: 4 | mode: standard | config: not found

   ├─ medfit 1.0.0
   ├─ medsim 0.3.2
   ├─ probmed 0.1.0
   └─ mediationverse 1.2.0
```

**What just happened:** rforge walked the filesystem looking for
`DESCRIPTION` files. Each found file becomes a package entry. The
"mode" reflects how thorough subsequent analysis will be — see
[`lib.discovery` reference](../reference/discovery.md) for details.

## Step 4: Check ecosystem status

```text
/rforge:status
```

Expected output:

```text
📊 ECOSYSTEM STATUS: /Users/you/your/r/packages

Package                Version    Check      Test       Progress
──────────────────────────────────────────────────────────────────────
medfit                 1.0.0      ❔ unknown ❔ unknown --
medsim                 0.3.2      ❔ unknown ❔ unknown --

Health score: 70/100
🟡 Some issues to address
Generated: 2026-05-11T12:34:56
```

**Reading the output:**

- **`Check`/`Test` columns**: `unknown` means rforge hasn't yet run R
  CMD check or test suites. In v1.3.0, these are stubs — to be wired up
  in v1.4.0. Don't worry about it for now.
- **`Progress`**: read from each package's `.STATUS` file (if present).
  `--` means no `.STATUS` file exists. See
  [lib.status reference](../reference/status.md) for the `.STATUS`
  format rforge can parse.
- **`Health score`**: 0-100 composite. Each `unknown` deducts a bit;
  staleness (>14 days since last `.STATUS` update) deducts more.

## Step 5: Initialize the active package

```text
/rforge:init
```

Expected output:

```text
✓ rforge initialized
  Package: medfit (1.0.0)
  Path:    /Users/you/your/r/package
  State:   /Users/you/.rforge/context.json
  Mode:    full
```

**What this does:** writes `~/.rforge/context.json` marking this
package as the current active context. Other rforge tools (and future
features) read this file to know what package you're working on. It's
**per-user, not per-package** — only one active context at a time.

To switch contexts later: `cd` to a different package directory and run
`/rforge:init` again.

## Step 6: Run a deeper analysis

```text
/rforge:analyze "Updated bootstrap algorithm"
```

This is the headline orchestration command. It:

1. Detects the project structure (Step 3)
2. Checks status (Step 4)
3. Analyzes dependencies + impact of the described change
4. Synthesizes recommendations

Expected output (abbreviated):

```text
📦 Pattern: CODE_CHANGE
🔍 Analyzing impact of "Updated bootstrap algorithm"...

   Direct dependents:   2 (medsim, mediationverse)
   Indirect dependents: 0
   Estimated work:      90 min
   Risk level:          medium

🔄 UPDATE SEQUENCE
   1. medfit
   2. medsim
   3. mediationverse

💡 RECOMMENDATIONS
   • Update 2 direct dependent package(s)
   • Run tests on dependents after change
```

## Three headline commands

Use these for daily work; the rest of the plugin's 16 commands are
specialized.

| Command | When | What |
|---|---|---|
| `/rforge:quick` | Pre-commit, fast check | <10s ecosystem snapshot |
| `/rforge:analyze "description"` | After code changes | ~30s — impact + recommendations |
| `/rforge:thorough "release prep"` | Before CRAN submission | 2-5 min — full validation |

## What's next

- **[REFCARD](../REFCARD.md)** — all 16 commands in one page
- **[Hooks & Skills](../hooks-and-skills.md)** — the `pretooluse` hook
  that flags R-aware mistakes on every Write/Edit
- **[Architecture](../architecture.md)** — how the plugin's `lib/`
  modules fit together
- **[Troubleshooting](../troubleshooting.md)** — when commands don't
  behave as expected

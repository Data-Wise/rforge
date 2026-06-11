# 📦 Installation

!!! tip "TL;DR (30 seconds)"
    - **What:** All install paths for the rforge plugin.
    - **Why:** macOS users prefer brew; cross-platform users prefer the marketplace.
    - **How:** Pick one method below — they all install the same thing.
    - **Next:** [Quick Start](QUICK-START.md) to run your first command.

⏱️ **2 minutes** • 🟢 Beginner • Pick ONE method

## Pick an install method

### Claude Code marketplace (cross-platform, recommended)

From inside Claude Code:

```text
/plugin marketplace add Data-Wise/rforge
/plugin install rforge
```

Works on macOS, Linux, and Windows. Updates with `/plugin update rforge`.

### Homebrew (macOS, recommended for CLI users)

```zsh
brew install data-wise/tap/rforge
```

Stable v2.0.0. Updates automatically with `brew upgrade`.

To track the development branch instead:

```zsh
brew install --HEAD data-wise/tap/rforge
```

### npm (cross-platform, if you already have Node)

```zsh
npm install -g @data-wise/rforge-plugin
```

### Manual (any platform)

```zsh
git clone https://github.com/Data-Wise/rforge.git
ln -s "$(pwd)/rforge" ~/.claude/plugins/rforge
```

## Verify the install

After any method, confirm Claude Code sees the plugin:

```text
/help
```

Expected: 35 commands prefixed `/rforge:` appear in the listing. If they
don't, restart Claude Code and try again.

A quicker confirmation from the shell:

```zsh
ls ~/.claude/plugins/rforge/commands/r/
```

Expected: a list of 17 `.md` files in `commands/r/` (check, load, document,
test, coverage, build, install, site, cycle, lint, spell, urlcheck, style,
revdep, goodpractice, winbuilder, cran-prep) plus `commands/rhub.md`, and
the 15 top-level commands in `commands/` (analyze, capture, cascade,
complete, deps, detect, health, impact, init, next, quick, release, status,
thorough, plus `docs/check.md`).

## Requirements

- **Claude Code CLI** installed and configured
- **Python 3.10+** on `PATH` (for the `lib/` modules)
- **R 4.0+** — required for all `r:*` commands and `/rforge:thorough`
  workflows. The rest of the plugin runs without R.

No MCP server or Node.js runtime is required at runtime as of v1.3.0.

## Upgrading

### From v1.x to v2.0.0 (BREAKING)

3 commands were renamed in v2.0.0. After upgrading, typing an old name
produces a verbatim error message pointing at the new name — no silent
failures. See the [v2.0.0 migration tutorial](migration/v2.0.0-rename.md)
for the mapping table and a POSIX `sed` recipe to mass-update local
scripts.

### From v0.x with rforge-mcp

If you still have the deprecated `rforge-mcp` MCP server, follow the
[migration tutorial](tutorials/migrate-from-mcp.md) (5 min) to clean up
the old install. The plugin no longer needs the MCP server as of v1.3.0.

## Uninstall

| Install method | Uninstall command |
|---|---|
| Marketplace | `/plugin remove rforge` |
| Homebrew | `brew uninstall data-wise/tap/rforge` |
| npm | `npm uninstall -g @data-wise/rforge-plugin` |
| Manual | `rm ~/.claude/plugins/rforge` (removes symlink only — the clone stays) |

State files are preserved after uninstall. To remove them too:

```zsh
rm -rf ~/.rforge
```

## Troubleshooting install issues

See [Troubleshooting → Install / setup issues](troubleshooting.md#install-setup-issues)
for fixes to common install errors (npm 404, plugin not loading, symlink
permission issues on macOS).

## What you get

- **16 slash commands** for R-package ecosystem analysis (see [REFCARD](REFCARD.md))
- **4 pure-Python `lib/` modules** invokable as `python3 -m lib.<mod>`
- **R-aware `PreToolUse` hook** that protects roxygen-generated files
- **`description-sync` validation skill** for pre-CRAN release checks
- **Self-contained** — no MCP server, no Node runtime requirement

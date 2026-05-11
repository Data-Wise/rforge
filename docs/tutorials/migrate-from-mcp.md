# Migrating from `rforge-mcp` to v1.3.0+

> **For whom:** You have `rforge-mcp` installed (npm-global or via the
> plugin's old peer dependency) and want to move to the self-contained
> v1.3.0+ plugin.
> **Estimated time:** 5 minutes.
> **Reversible:** Yes — you can reinstall `rforge-mcp` if anything goes wrong.

As of v1.3.0, the rforge plugin no longer needs the `rforge-mcp` server.
All 7 implemented MCP tools have been ported to pure-Python modules under
the plugin's `lib/` directory. This tutorial walks through the cleanup.

## Quick check: do I have rforge-mcp installed?

```zsh
# (1) npm global install?
npm list -g rforge-mcp 2>&1 | grep rforge-mcp

# (2) MCP server config in Claude settings?
jq '.mcpServers.rforge // "not configured"' ~/.claude/settings.json

# (3) Plugin peer dependency complaint on `npm install`?
# If you previously saw `npm error 404 — rforge-mcp not found`,
# you were affected.
```

If any of those return signals, this tutorial applies to you. If all are
clean, you're already on the new setup — skip to the [verification step](#step-5-verify).

---

## Step 1: Upgrade the rforge plugin to v1.3.0+

```zsh
# Via Claude Code marketplace (recommended)
/plugin marketplace add Data-Wise/rforge

# Or via Homebrew
brew upgrade data-wise/tap/rforge

# Or via npm
npm install -g @data-wise/rforge-plugin@latest
```

Verify:

```zsh
brew list --versions rforge
# expected: rforge 1.3.0 (or later)
```

## Step 2: Remove the MCP server config

Open `~/.claude/settings.json` and delete the `mcpServers.rforge` block:

```diff
 {
   "mcpServers": {
-    "rforge": {
-      "command": "node",
-      "args": ["/path/to/rforge-mcp/dist/index.js"]
-    },
     "other-server": { ... }
   }
 }
```

Save. Restart Claude Code (or run `/mcp` and reconnect, depending on
your setup) so the change takes effect.

## Step 3: Uninstall the `rforge-mcp` package

```zsh
# If installed globally via npm
npm uninstall -g rforge-mcp

# If installed via Homebrew (uncommon but possible)
brew uninstall rforge-mcp 2>/dev/null || true
```

This step is **optional** — leaving `rforge-mcp` installed doesn't break
anything; it just sits unused. But removing it frees the disk space and
removes a stale dependency you'll never run again.

## Step 4: Clean up any local `.rforge/` state (optional)

If you previously initialized a package via `rforge_init` (the old MCP
tool), your state lives at `~/.rforge/context.json`. The new
`/rforge:init` reads and writes the *same file* — so existing state
migrates transparently. **No action needed unless** you want a fresh
start:

```zsh
# Fresh start (optional)
rm ~/.rforge/context.json
```

## Step 5: Verify

```zsh
# 1) Discovery — should find your R packages without an MCP server
python3 -m lib.discovery --path . --format text

# 2) Status — should print ecosystem snapshot + health score
python3 -m lib.status --path . --format text

# 3) Init — should re-detect and write context.json
python3 -m lib.init --path . --format text
```

From within Claude Code, the same operations are available via slash
commands:

```text
/rforge:detect
/rforge:status
/rforge:init
```

If all three produce output and don't error, you've successfully
migrated. The `rforge-mcp` server is no longer in your runtime path.

---

## What changed under the hood

| Old (rforge-mcp tool)  | New (rforge plugin v1.3.0+)         |
|------------------------|--------------------------------------|
| `rforge_detect`        | `python3 -m lib.discovery`           |
| `rforge_deps`          | `python3 -m lib.deps`                |
| `rforge_impact`        | `python3 -m lib.deps impact ...`     |
| `rforge_status`        | `python3 -m lib.status`              |
| `rforge_init`          | `python3 -m lib.init`                |
| `rforge_plan*`         | Dropped — Claude handles planning natively |
| `rforge_cascade_plan`  | Dropped — never reached implementation |

Plugin slash commands (`/rforge:status`, `/rforge:deps`, `/rforge:quick`,
...) continue to work exactly as before — they now dispatch to the
in-plugin Python modules instead of the MCP server.

## Rollback (if something goes wrong)

```zsh
# Reinstall rforge-mcp
npm install -g rforge-mcp

# Restore the mcpServers.rforge block in ~/.claude/settings.json
# (you backed it up before deleting, right? if not, see the v1.2.x docs)

# Downgrade the plugin
brew install data-wise/tap/rforge@1.2.0
```

The `rforge-mcp` repo is archived (read-only on GitHub), but the npm
package and any local installs remain functional. Don't be afraid to
roll back; nothing is destroyed.

## Next steps

- **Read [Hooks & Skills](../hooks-and-skills.md)** — the v1.2.0 hook
  layer and validation skills still apply post-migration.
- **Check [Troubleshooting](../troubleshooting.md)** if you hit
  unexpected errors.
- **See [Architecture](../architecture.md)** for the v1.3.0 plugin
  surface diagram showing how `lib/` modules replace the MCP boundary.

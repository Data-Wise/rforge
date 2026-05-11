# rforge-mcp is deprecated

> This MCP server has been absorbed into the `rforge` Claude Code plugin
> as of plugin version 1.3.0 (released 2026-05-11). The functionality
> is now provided in pure Python under the plugin's `lib/` directory —
> no MCP server is required at runtime.

## TL;DR

- Update the `rforge` plugin to v1.3.0 or later.
- Remove the `mcpServers.rforge` entry from `~/.claude/settings.json`.
- Uninstall any local `rforge-mcp` package install.
- This repository is now archived (read-only).

## What changed

The MCP tool surface previously exposed by `rforge-mcp` is now available
directly inside the plugin. Each former tool maps cleanly onto a Python
module under `lib/` and (where applicable) a slash command.

| Old (rforge-mcp tool)  | New (rforge plugin)                  |
|------------------------|--------------------------------------|
| `rforge_discovery`     | `python3 -m lib.discovery`           |
| `rforge_deps`          | `python3 -m lib.deps`                |
| `rforge_status`        | `python3 -m lib.status`              |
| `rforge_init`          | `python3 -m lib.init`                |
| `rforge_quick_*` tools | `/rforge:quick` (composed lib calls) |

The slash commands (`/rforge:status`, `/rforge:deps`, `/rforge:quick`, ...)
continue to work exactly as before — they now invoke the absorbed Python
modules instead of crossing an MCP boundary.

## Migration steps for existing users

1. **Update the rforge plugin** to v1.3.0 or later via your plugin manager
   or `git pull` in your plugin checkout.

2. **Remove the MCP server entry** from `~/.claude/settings.json`:

   ```json
   // DELETE this block if present:
   "mcpServers": {
     "rforge": { ... }
   }
   ```

   Leave any other `mcpServers` entries intact. If `mcpServers` becomes
   empty after the deletion, you can remove the empty object entirely.

3. **Uninstall the `rforge-mcp` package** if you installed it locally:

   ```bash
   npm uninstall -g rforge-mcp
   ```

   (rforge-mcp was never published to a package registry, so this only
   applies if you installed from a local clone via `npm link` or similar.)

4. **State file**: the absorbed `lib/init.py` writes to `~/.rforge/context.json`
   using the same schema as `rforge-mcp`. Existing state migrates transparently —
   no manual conversion needed.

## Why the absorption

The MCP server added a process boundary and a Node.js runtime dependency
for a tool that was, by line count, mostly file parsers and dependency-graph
walkers. Moving that logic into pure Python inside the plugin gives users:

- One fewer thing to install (no `rforge-mcp` package).
- Zero network or IPC dependencies at runtime.
- Direct CLI access via `python3 -m lib.<tool>` for scripting and debugging.
- A single source of truth for the discovery / deps / status logic, instead
  of split implementations between plugin and MCP server.

## This repository is archived

This repo is read-only as of [DATE TO BE FILLED IN AT ARCHIVE TIME]. Issues
and PRs are not accepted. For bugs in the absorbed implementations, please
file at https://github.com/Data-Wise/rforge.

The source history remains visible and clonable for anyone who needs to
reference the original MCP implementation.

## Final version

rforge-mcp's final version (whatever was in `main` at archive time) remains
available via this repo's source history. No further releases are planned.

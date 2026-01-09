# MCP Server Migration Guide

## RForge Plugin MCP Configuration

RForge **requires** the `rforge-mcp` server for full functionality. This guide helps you configure it correctly.

## Quick Setup

### 1. Install RForge MCP Server

```bash
npm install -g rforge-mcp
```

### 2. Configure Claude Code Settings

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

### 3. Install RForge Plugin

```bash
brew install rforge
```

### 4. Verify Setup

```bash
# In Claude Code, try:
/rforge:status
```

If you see status output, you're all set! ✅

---

## Migration from rforge-orchestrator

If you previously used `rforge-orchestrator` from the claude-plugins monorepo, follow these steps:

### Step 1: Update MCP Server Name

**Old configuration:**
```json
{
  "mcpServers": {
    "rforge-orchestrator": {
      "command": "npx",
      "args": ["rforge-mcp"]
    }
  }
}
```

**New configuration:**
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

**⚠️ Important:** The server name changed from `rforge-orchestrator` to `rforge-mcp` to match the npm package name.

### Step 2: Remove Old Plugin

```bash
rm -rf ~/.claude/plugins/rforge-orchestrator
```

### Step 3: Install New Plugin

```bash
brew install rforge
```

### Step 4: Test

```bash
# In Claude Code:
/rforge:analyze
/rforge:status
```

---

## Detailed Configuration

### Location Options

You can configure MCP servers in multiple locations:

**Global (All Projects):**
```bash
~/.claude/settings.json
```

**Project-Specific:**
```bash
<project>/.claude/settings.local.json
```

**Browser Extension (claude.ai):**
```bash
~/projects/dev-tools/claude-mcp/MCP_SERVER_CONFIG.json
```

### Full Configuration Example

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

### Environment Variables

Optional environment variables:

- `RFORGE_MODE` - Default mode (default, debug, optimize, release)
- `RFORGE_FORMAT` - Default format (terminal, json, markdown)

---

## Verification

### Check MCP Server is Running

```bash
# List MCP servers in Claude Code
# (No direct command, but errors will show if misconfigured)
```

### Test RForge Commands

Try each mode and format:

```bash
/rforge:status default terminal
/rforge:status debug json
/rforge:analyze optimize markdown
/rforge:quick
/rforge:thorough
```

### Common Issues

**Error: "MCP server not found"**
- Solution: Verify `npm install -g rforge-mcp` was successful
- Check: `which rforge-mcp` or `npm list -g rforge-mcp`

**Error: "Command failed"**
- Solution: Check `~/.claude/settings.json` syntax (valid JSON)
- Verify: Server name is `rforge-mcp` (not `rforge-orchestrator`)

**Error: "Permission denied"**
- Solution: Ensure `npx` is in your PATH
- Try: `npm install -g rforge-mcp` again with sudo if needed

---

## Advanced: Multiple MCP Servers

RForge works alongside other MCP servers:

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "npx",
      "args": ["rforge-mcp"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/Users/dt"]
    }
  }
}
```

---

## Troubleshooting

### Enable Debug Mode

Set environment variable for detailed logs:

```json
{
  "mcpServers": {
    "rforge-mcp": {
      "command": "npx",
      "args": ["rforge-mcp"],
      "env": {
        "DEBUG": "rforge:*"
      }
    }
  }
}
```

### Check Logs

MCP server logs location (if enabled):
```bash
~/.claude/logs/mcp-servers/rforge-mcp.log
```

### Reinstall MCP Server

If issues persist:

```bash
npm uninstall -g rforge-mcp
npm cache clean --force
npm install -g rforge-mcp
```

---

## Questions?

- **RForge Plugin Issues:** https://github.com/Data-Wise/rforge/issues
- **RForge MCP Server Issues:** https://github.com/Data-Wise/mcp-servers/issues
- **Documentation:** https://data-wise.github.io/rforge/

---

**TL;DR:**
1. `npm install -g rforge-mcp`
2. Add `rforge-mcp` server to `~/.claude/settings.json`
3. `brew install rforge`
4. Test with `/rforge:status`

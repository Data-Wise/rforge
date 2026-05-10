# RForge Plugin Hooks

This directory contains hook scripts that execute during Claude Code tool
lifecycle events. The pattern mirrors craft's `.claude-plugin/hooks/`.

## pretooluse.py

PreToolUse hook that fires on every `Write` and `Edit` call and applies
R-package-aware rules.

### Rules

| Rule | Severity | What it catches |
|------|----------|-----------------|
| `man/*.Rd` edit | **BLOCK** (exit 2) | Hand-edits to roxygen2-generated files. |
| `R/*.R` edit reminder | warn | Reminds developer about NAMESPACE/DESCRIPTION sync. |
| `DESCRIPTION` Version SemVer | warn | Non-SemVer version strings (e.g. `1.2`, `v1.2.0`). |
| Outside-worktree write | warn | File path outside the current git toplevel. |

### Wiring

The hook is **not auto-wired** by writing it to this directory. Add to
your `~/.claude/settings.json` (or project `.claude/settings.json`) to
activate:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/hooks/pretooluse.py"
          }
        ]
      }
    ]
  }
}
```

### Environment Contract

| Variable | Provided by | Purpose |
|----------|-------------|---------|
| `CLAUDE_TOOL_NAME` | Claude Code | Name of the tool being invoked (e.g. `Write`, `Edit`). |
| `CLAUDE_TOOL_INPUT` | Claude Code | JSON-encoded tool input parameters. |

### Testing

```bash
# Block: editing a roxygen-generated .Rd file
CLAUDE_TOOL_NAME=Edit \
CLAUDE_TOOL_INPUT='{"file_path":"man/foo.Rd","old_string":"x","new_string":"y"}' \
  python3 .claude-plugin/hooks/pretooluse.py
echo $?  # → 2 (blocked)

# Warn: editing R/ source
CLAUDE_TOOL_NAME=Edit \
CLAUDE_TOOL_INPUT='{"file_path":"R/foo.R","old_string":"x","new_string":"y"}' \
  python3 .claude-plugin/hooks/pretooluse.py
echo $?  # → 0 (allowed, with warning to stderr)

# Warn: bad SemVer in DESCRIPTION
CLAUDE_TOOL_NAME=Write \
CLAUDE_TOOL_INPUT='{"file_path":"DESCRIPTION","content":"Version: not-semver\n"}' \
  python3 .claude-plugin/hooks/pretooluse.py
echo $?  # → 0 (allowed, with warning)
```

## See Also

- `.claude-plugin/skills/validation/description-sync.md` — companion
  validator that catches DESCRIPTION ↔ NEWS.md drift at release time.
- craft's `pretooluse.py` — upstream pattern this hook is modeled on.

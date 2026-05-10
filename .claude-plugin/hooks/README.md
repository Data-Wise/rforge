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

### Input Contract

Claude Code passes the hook payload as **JSON on stdin** (NOT as
environment variables — see `~/.claude/hooks/branch-guard.sh:6` for the
canonical contract documentation).

```json
{
  "session_id": "...",
  "tool_name": "Write",
  "tool_input": { "file_path": "...", "content": "..." },
  "cwd": "..."
}
```

The hook reads `tool_name` and `tool_input` from this payload. Empty or
malformed stdin is handled gracefully (silent no-op, exit 0).

### Testing

```bash
# Block: editing a roxygen-generated .Rd file
echo '{"tool_name":"Edit","tool_input":{"file_path":"man/foo.Rd","old_string":"x","new_string":"y"}}' \
  | python3 .claude-plugin/hooks/pretooluse.py
echo $?  # → 2 (blocked)

# Warn: editing R/ source
echo '{"tool_name":"Edit","tool_input":{"file_path":"R/foo.R","old_string":"x","new_string":"y"}}' \
  | python3 .claude-plugin/hooks/pretooluse.py
echo $?  # → 0 (allowed, with warning to stderr)

# Warn: bad SemVer in DESCRIPTION
echo '{"tool_name":"Write","tool_input":{"file_path":"DESCRIPTION","content":"Version: not-semver\n"}}' \
  | python3 .claude-plugin/hooks/pretooluse.py
echo $?  # → 0 (allowed, with warning)

# Full validation suite (includes contract correctness checks):
bash tests/test-all.sh
```

## See Also

- `.claude-plugin/skills/validation/description-sync.md` — companion
  validator that catches DESCRIPTION ↔ NEWS.md drift at release time.
- craft's `pretooluse.py` — original inspiration for this hook's rules.
  **Note:** craft's hook reads from env vars, which appears to be a
  silent no-op against the actual Claude Code stdin contract. This
  rforge port intentionally diverges to use the working stdin protocol.

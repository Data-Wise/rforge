"""rforge plugin's pure-Python library modules.

These are the in-plugin replacements for `rforge-mcp` tools (Path B of
the MCP-absorb migration). Each module is independently invokable as a
CLI:

    python3 -m lib.discovery --path . --format text
    python3 -m lib.deps --path . --format text
    python3 -m lib.deps impact --package <name> --change-type breaking

Or imported as a Python API:

    from lib.discovery import detect_ecosystem
    from lib.deps import build_graph, analyze_impact

## Public modules (documented in docs/reference/)

- `lib.discovery` — ecosystem detection
- `lib.deps` — dependency graph + impact
- `lib.status` — ecosystem health snapshot
- `lib.init` — `~/.rforge/context.json` initialization

## Internal modules (not part of the public API)

- `lib.formatters` — output formatting (`terminal`, `json`, `markdown`)
  used by the command prompts when they emit structured results.
  Stable in v2.x but no `docs/reference/` page; subject to refactor
  without notice. If you need formatting outside the command-prompt
  context, copy the format functions rather than importing them.

See `docs/lib-modules.md` and `docs/specs/SPEC-mcp-absorb-2026-05-10.md`
for the full migration plan.
"""

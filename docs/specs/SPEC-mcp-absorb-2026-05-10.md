# SPEC: Absorb rforge-mcp into rforge plugin (Path B)

> **Date:** 2026-05-10
> **Status:** Shipped (pending v1.3.0 PR merge) — Path A shipped in v1.2.0; Phases B.1 (discovery + deps), B.2 (status), B.3 (init), B.4 (archive paperwork) all complete on `feature/mcp-absorb-rest` (2026-05-11). See [Scope correction](#scope-correction-2026-05-11) below.
> **Related:** [Path A in CHANGELOG v1.2.0](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md). The `rforge-mcp` prototype lived only as a local working directory at `~/projects/dev-tools/mcp-servers/rforge/` — not on GitHub, not on npm (see [Scope correction #2](#scope-correction-2--phase-b4-archival-2026-05-11) at the bottom). ORCHESTRATE files for each phase were deleted at merge time per the CLAUDE.md cleanup rule — see PR #3 (B.1) and PR #4 (B.2+B.3+B.4) for the as-shipped commits.

## Summary

After Path A landed (peer dep removed in v1.2.0), the plugin runs standalone
via Claude Code's built-in tools. Path B is the longer-term migration: move
`rforge-mcp`'s implemented logic into the plugin's `lib/`, make plugin commands
self-contained, and archive the MCP repo. Result: **one repo to maintain**.

## Goals

- Single repository (`Data-Wise/rforge`) houses all R-package analysis logic
- Each plugin command is self-contained — no cross-repo runtime dependency
- Drop the rforge-mcp repo (archive on GitHub) once migration is complete
- No regression in functional capability for the 7 implemented MCP tools
- Drop the 6 placeholder MCP tools that never shipped (or implement the
  high-value ones inside the plugin if needed)

## Non-goals

- Recreating MCP's typed JSON I/O for plugin commands (commands are markdown
  prompts — Claude provides the structured response directly)
- Multi-client compatibility (Claude Desktop, Cursor, etc.) — accepted loss
- Backward compat with `rforge_*` MCP tool invocations from external scripts

## Inventory: 13 MCP tools, 7 implemented

From `dist/index.js` of `rforge-mcp@0.1.0`:

| MCP tool | Status | Implementation site (in MCP) | Migration target |
|---|---|---|---|
| `rforge_detect` | ✅ implemented | `dist/tools/discovery/detect.js` | `lib/discovery.py` (FS scan, parse DESCRIPTION) |
| `rforge_status` | ✅ implemented | `dist/tools/discovery/status.js` | `lib/status.py` (parse R package state, supports default/debug/optimize/release modes) |
| `rforge_deps` | ✅ implemented | `dist/tools/deps/deps.js` | `lib/deps.py` (parse DESCRIPTION Imports/Suggests, build graph) |
| `rforge_impact` | ✅ implemented | `dist/tools/deps/impact.js` | `lib/deps.py` (graph traversal — co-locate with deps logic) |
| `rforge_init` | ✅ implemented | (function `E3` in dist) | `lib/init.py` (writes context state file) |
| `rforge_plan` | ✅ implemented | (function `e8` in dist) | **Drop** — Claude can do planning via the existing prompt-based workflow; no need for typed plan generation |
| `rforge_plan_quick_fix` | ✅ implemented | (function `YX` in dist) | **Drop** — same as above |
| `rforge_cascade_plan` | ❌ placeholder | "not yet implemented" stub | **Drop** unless explicitly needed; current `/rforge:cascade` command exists |
| `rforge_doc_check` | ❌ placeholder | stub | **Drop** unless needed; existing `/rforge:doc-check` command + `description-sync` skill cover most ground |
| `rforge_release_plan` | ❌ placeholder | stub | **Drop** — existing `/rforge:release` command |
| `rforge_capture` | ❌ placeholder | stub | **Drop** — existing `/rforge:capture` command |
| `rforge_complete` | ❌ placeholder | stub | **Drop** — existing `/rforge:complete` command |
| `rforge_next` | ❌ placeholder | stub | **Drop** — existing `/rforge:next` command |

**Net migration scope:** 5 modules to port (`discovery`, `status`, `deps` (with impact), `init`). The 2 plan tools and 6 placeholder tools all go away.

## Migration plan (4 phases)

### Phase B.1 — Port `discovery` and `deps` (foundation modules)

These are pure-FS / pure-parsing logic. Smallest risk, biggest reward.

- `lib/discovery.py` — function: `detect_ecosystem(path: str) -> Ecosystem`
  - Walks filesystem looking for DESCRIPTION files
  - Returns dataclass: `{packages: [...], mode: "single" | "ecosystem" | "hybrid", ...}`
  - Used by every other module
- `lib/deps.py` — functions: `build_graph(ecosystem) -> DepGraph`, `analyze_impact(graph, package, change) -> Impact`
  - Parses DESCRIPTION `Imports:` / `Suggests:` / `Depends:`
  - Builds DAG, detects cycles, computes topo layers
  - Impact analysis = downstream BFS

**Acceptance:**
- Existing `/rforge:detect` and `/rforge:deps` commands updated to invoke
  `python3 -m lib.discovery` / `python3 -m lib.deps` (or equivalent)
- Output matches what MCP server returned (run both side-by-side on
  mediationverse ecosystem; diff outputs)

### Phase B.2 — Port `status` (with mode awareness)

- `lib/status.py` — function: `aggregate_status(ecosystem, mode) -> Status`
  - 4 modes: default (<5s), debug (<30s), optimize (<60s), release (<120s)
  - Mode determines depth: file checks only → R CMD check → benchmarks → full CRAN dry-run
  - Output formats: terminal (Rich), json, markdown

**Acceptance:**
- `/rforge:status` and `/rforge:quick` and `/rforge:thorough` all work via
  the new module
- Mode performance budgets honored
- Format-equivalence test against MCP `rforge_status` output

### Phase B.3 — Port `init` (state file)

- `lib/init.py` — function: `init_context(quick: bool = False)`
  - Writes a `.rforge/context.json` (or similar) marking the package as initialized
  - "Quick" mode skips comprehensive analysis
  - Idempotent — running twice is a no-op for state, may refresh analysis

**Acceptance:**
- `/rforge:init` (if it exists; else `/rforge:detect` does this implicitly)
  produces the same context file format as MCP did, so users with existing
  `.rforge/` state migrate transparently

### Phase B.4 — Archive `rforge-mcp`

- Add `DEPRECATED.md` to `data-wise/rforge-mcp` repo explaining the
  migration. Link to `Data-Wise/rforge`.
- GitHub UI: archive the repo (read-only, can't open issues/PRs).
- npm: never published, so no npm action needed.
- Homebrew: no formula exists for `rforge-mcp` — no action.

## Open questions for future sessions

1. **Python vs shell vs Node for `lib/`?** Current `lib/formatters.py` is
   Python. MCP server is Node. Plugin commands are shell-friendly. Probably
   Python (familiar, structured, no compile step), but TBD.
2. **Where does the analysis actually run?** Plugin commands are markdown
   prompts. Claude can `Bash` into `python3 lib/foo.py` — that's the pattern.
   Worth establishing a `lib/` calling convention before porting starts.
3. **Test strategy?** MCP had `npm test` / `pytest`. New `lib/` should have
   pytest tests in `tests/test_lib_*.py`, run alongside the existing
   `tests/test-all.sh`.
4. **Mediationverse ecosystem as the test fixture?** Real-world-data integration
   test — port a module, run on mediationverse, diff vs MCP output.

## Sequencing

- **Phase B.1** is the foundation; everything depends on `discovery`. ~1 worktree
  session, scoped non-breaking.
- **Phase B.2 + B.3** can run in parallel after B.1.
- **Phase B.4** is paperwork after the others land.

Estimated total: 3-4 focused sessions (~3-4 hours each), spread over weeks.
Not urgent — Path A already unblocks `npm install`.

## How to start

```bash
# When ready to begin Phase B.1:
git checkout dev
git worktree add ~/.git-worktrees/rforge/feature-mcp-absorb-discovery \
  -b feature/mcp-absorb-discovery dev

cd ~/.git-worktrees/rforge/feature-mcp-absorb-discovery
# Reference: rforge-mcp source at ~/projects/dev-tools/mcp-servers/rforge/
# Local install: /opt/homebrew/lib/node_modules/rforge-mcp/
# Compiled tools: dist/tools/{discovery,deps}/
```

## Related

- Path A (this v1.2.0): peer dep removed, plugin standalone — see CHANGELOG
- `.STATUS` backlog: this SPEC supersedes "publish rforge-mcp to npm"

## Scope correction (2026-05-11)

During implementation, research surfaced that the MCP server's `status` tool
was substantially thinner than this SPEC described — no modes, no R subprocess,
no escalating fidelity. The original 4-mode contract reflected aspirational
design rather than what MCP actually shipped.

`lib/status.py` is a faithful port of MCP's actual behavior: `DESCRIPTION` +
`.STATUS` parsing with a health-score heuristic. The 4-mode design is
descoped to a future v1.4.0 SPEC, to be informed by real-user requests for
specific check depths.

All other phase B.3 / B.4 acceptance criteria ship as planned.

## Scope correction #2 — Phase B.4 archival (2026-05-11) { #scope-correction-2--phase-b4-archival-2026-05-11 }

After v1.3.0 shipped, attempting Phase B.4's `gh repo archive
data-wise/rforge-mcp` revealed the repo never existed on GitHub.
`rforge-mcp` was a local-only working directory during pre-v1.3.0
development — never pushed to GitHub, never published to npm.

Phase B.4 was rewritten in
[`docs/migration/v1.3.0-post-merge-checklist.md`](../migration/v1.3.0-post-merge-checklist.md)
to reflect the actual cleanup tasks: drop the global `npm link` symlink
and tombstone the local source directory. The SPEC's assumption that
rforge-mcp had public artifacts to retire is preserved here as historical
context, but **not action-guidance**.

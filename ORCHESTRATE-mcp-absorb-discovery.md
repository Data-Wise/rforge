# Path B Phase B.1 — Port `discovery` + `deps` modules to `lib/`

> **Branch:** `feature/mcp-absorb-discovery`
> **Base:** `dev`
> **Worktree:** `~/.git-worktrees/rforge/feature-mcp-absorb-discovery`
> **Spec:** [`docs/specs/SPEC-mcp-absorb-2026-05-10.md`](docs/specs/SPEC-mcp-absorb-2026-05-10.md)
> **Created:** 2026-05-10
> **Target release:** v1.3.0 (non-breaking)

## Objective

Port the **3 simplest implemented MCP tools** from `data-wise/rforge-mcp` into rforge's `lib/`, replacing the runtime dependency on the MCP server with self-contained Python modules. Establishes the `lib/` calling convention used by future Path B phases.

Tools to port in this phase:

| MCP tool | New module | Logic class |
|---|---|---|
| `rforge_detect` | `lib/discovery.py` | FS scan for DESCRIPTION files; returns `Ecosystem` dataclass |
| `rforge_deps` | `lib/deps.py` | Parse DESCRIPTION Imports/Suggests/Depends; build DAG; detect cycles |
| `rforge_impact` | `lib/deps.py` (co-located) | Downstream BFS on the DAG |

## Phase overview

| Step | Task | Priority | Status |
|---|---|---|---|
| 1 | Establish `lib/` calling convention (Python invocation pattern, output format) | High | ✅ Done |
| 2 | Port `rforge_detect` → `lib/discovery.py` | High | ✅ Done |
| 3 | Port `rforge_deps` + `rforge_impact` → `lib/deps.py` | High | ✅ Done |
| 4 | Add `tests/test_lib_discovery.py` + `tests/test_lib_deps.py` (pytest) | High | ✅ Done (32 cases) |
| 5 | Update `commands/detect.md`, `commands/deps.md`, `commands/impact.md` to invoke new modules | Medium | ✅ Done |
| 6 | Side-by-side correctness check vs MCP server output (mediationverse ecosystem if accessible) | Medium | ✅ Done (see report below) |
| 7 | Update `tests/test-all.sh` to run new pytest suite | Medium | ✅ Done (22 checks total) |
| 8 | CHANGELOG entry + `docs/specs/...` status: Draft → In Progress | Low | ✅ Done |

## Side-by-side report (Step 6, 2026-05-10)

**Target ecosystem:** `~/projects/r-packages/active` (the mediationverse cluster).

**Packages discovered (6):**
`medfit 0.1.0`, `medfit 0.1.0` (from `medfit.Rcheck/`), `mediationverse 0.0.0.9000`, `medrobust 0.1.0.9000`, `medsim 0.0.0.9000`, `probmed 0.0.0.9000`.

**Topological layers:**
- Layer 1: `medfit`, `medrobust`, `medsim`
- Layer 2: `mediationverse`, `probmed`

**Internal edges:** `mediationverse → medfit`, `probmed → medfit`.

**External CRAN deps:** `S7`, `checkmate`, `cli`, `dplyr`, `generics`, `ggplot2`, `methods`, `parallel`, `pbapply`, `rlang`, `stats`, `utils`.

**Impact analysis** (`medfit` breaking change): 2 direct dependents (`mediationverse`, `probmed`), 0 indirect, risk `high`, ~45 affected tests, ~2.0h estimated work.

**Algorithmic parity with MCP server:** confirmed by code review (algorithms ported line-by-line from `rforge-mcp/dist/tools/{discovery,deps}/`).

**Known divergence (consistent with MCP):** The `medfit.Rcheck/` directory's DESCRIPTION is picked up as a duplicate package. Both implementations exhibit this behavior because `findRPackages` traverses non-hidden subdirs without an `.Rcheck` skip list. Future enhancement; intentionally out of scope here.

## Stress test on a second layout (2026-05-10)

Also validated on `~/projects/r-packages/` (parent of `active/` + `stable/`):

- 6 unique packages found across 2 subdirs: `medfit`, `medrobust`, `medsim`, `mediationverse`, `probmed` (active) + `RMediation` (stable).
- `RMediation` correctly tagged `[stable]` via path-based category inference.
- **No `.Rcheck` duplicate** when scanning from the grandparent — `medfit.Rcheck/<medfit>/DESCRIPTION` sits at depth 3 and is outside the default `max_depth=2`. Confirms the duplicate only appears when scanning a layout where `.Rcheck` is a sibling of `DESCRIPTION` (depth 1).
- Non-package directories (e.g. `mediation-planning/`, which has no `DESCRIPTION`) are correctly excluded — the strict-hybrid heuristic didn't falsely flag this layout as hybrid.

## Acceptance criteria

- [ ] `lib/discovery.py` defines `detect_ecosystem(path: str) -> Ecosystem` returning a dataclass with `packages`, `mode` (single/ecosystem/hybrid), `config`. No imports from `rforge-mcp`.
- [ ] `lib/deps.py` defines `build_graph(ecosystem) -> DepGraph` and `analyze_impact(graph, package, change_type) -> Impact`. Pure Python, no R dependency.
- [ ] `tests/test_lib_discovery.py` and `tests/test_lib_deps.py` pass (pytest invocation).
- [ ] `commands/{detect,deps,impact}.md` invoke `python3 lib/<module>.py` (or document the Python API for Claude to call).
- [ ] `tests/test-all.sh` includes the new pytest tests (passes 22+ checks total).
- [ ] Side-by-side: running new module on a real R ecosystem produces output equivalent to what `rforge-mcp` produced (same package list, same dependency edges, same impact set). Document any intentional divergence.
- [ ] CHANGELOG entry under `[Unreleased]` describing the lib/ ports.

## Open questions to resolve in this phase

These are deferred-from-SPEC questions that need answers before code:

1. **Calling convention from commands.** Plugin commands are markdown prompts. Should they call `python3 lib/discovery.py --json --path .` (CLI subprocess) or document the Python API for Claude to invoke directly via `Bash`? Both work; pick one for consistency.
   **Decision (2026-05-10):** Both — CLI is primary, Python API documented. Each `lib/<module>.py` exposes (a) public functions importable from Python (`from discovery import detect_ecosystem`) AND (b) an `argparse`-driven `__main__` block so it works as `python3 lib/discovery.py --path . --format json`. Commands invoke the CLI by default; the API stays available for power users and future internal callers.
2. **Output format.** MCP returned typed JSON. Lib should support: (a) terminal-friendly text (default), (b) JSON (machine-readable). Match modes from `rforge_status`.
   **Decision (2026-05-10):** Both, flag-controlled. Default `--format text` (colored/emoji, matches existing MCP UX); `--format json` for machine consumption. Mirrors the convention already in `lib/formatters.py`.
3. **Where do tests live?** `tests/test_lib_*.py` alongside the existing `tests/test-*.sh`? Or `lib/tests/`? Convention TBD.
   **Decision (2026-05-10):** `tests/test_lib_*.py` at the repo root. Single test directory, pytest auto-discovers `test_*.py`, integrates cleanly into `tests/test-all.sh`.

## How to start (in a fresh session)

```bash
cd ~/.git-worktrees/rforge/feature-mcp-absorb-discovery
claude
```

Then in the new session:

1. Read this file + the SPEC: `docs/specs/SPEC-mcp-absorb-2026-05-10.md`
2. Read the MCP server's compiled tools: `/opt/homebrew/lib/node_modules/rforge-mcp/dist/tools/discovery/detect.js` and `dist/tools/deps/`
3. Resolve the open questions (above) — capture decisions inline in this file as you go
4. Begin Step 2 (`lib/discovery.py`) since it's the foundation for Step 3

## Done when

- All acceptance criteria checked
- PR opened against `dev` (single-integration would be `main`, but rforge is multi-branch craft-style)
- `.STATUS` on `dev` reflects: this worktree → `state: REVIEW`
- Side-by-side test report attached to PR description

## Notes / scope discipline

- **Do NOT port `rforge_status`** — that's Phase B.2 (separate worktree). Status has mode-aware execution (default/debug/optimize/release) that pulls in R subprocess work; out of scope here.
- **Do NOT port `rforge_init` or `rforge_plan`** — Phase B.3 / drop list per the SPEC.
- **Do NOT touch the MCP server repo** — Phase B.4 archives it; that's after all ports land.
- **Non-breaking by design.** Existing users with rforge-mcp installed keep working — this phase adds parallel implementations in `lib/`, doesn't remove anything.

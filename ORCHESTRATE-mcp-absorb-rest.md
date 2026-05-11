# Path B Phases B.2 + B.3 + B.4 — Finish the MCP absorption

> **Branch:** `feature/mcp-absorb-rest`
> **Base:** `dev` (at `9e4f8f4`, includes B.1 merged as `951e055`)
> **Worktree:** `~/.git-worktrees/rforge/feature-mcp-absorb-rest`
> **Spec:** [`docs/specs/SPEC-mcp-absorb-2026-05-10.md`](docs/specs/SPEC-mcp-absorb-2026-05-10.md)
> **Created:** 2026-05-10
> **Target release:** v1.3.0 (non-breaking)

## Objective

Finish Path B in a single worktree. After this lands:

- All 7 implemented `rforge-mcp` tools have pure-Python replacements in `lib/`
- `rforge-mcp` repo is archived on GitHub
- The plugin is fully self-sufficient — no MCP server required at runtime

## Why one worktree (consolidation rationale)

B.1 shipped (PR #3, merge `951e055`). The remaining work splits into:

- **B.2** — substantive port (`rforge_status` with mode-aware execution + R subprocess decision)
- **B.3** — small port (`rforge_init` state file, ~50 lines)
- **B.4** — paperwork (DEPRECATED.md + GitHub archive button)

B.3 is too small to deserve its own worktree; B.4 is non-code paperwork that benefits from being bundled with the work that triggers it. Consolidating B.2+B.3+B.4 into one PR ships v1.3.0 atomically — users get the complete absorbed plugin in one release.

## Stacking note (resolved)

Earlier B.2 ORCHESTRATE asked "rebase onto B.1 or wait?" — moot now: B.1 is merged. This worktree branches from `dev` (which includes `lib/discovery.py`, `lib/deps.py`, the `lib/__init__.py` package marker, and the `python3 -m lib.<module>` invocation pattern). Build on top.

## Phase overview

| Phase | Step | Task | Priority | Status |
|---|---|---|---|---|
| B.2 | 1 | Read `rforge-mcp/dist/tools/discovery/status.js` + helpers | High | Pending |
| B.2 | 2 | Design 4-mode contract (default <5s, debug <30s, optimize <60s, release <120s) | High | Pending |
| B.2 | 3 | Decide R subprocess strategy (open question 1 below) | High | Pending |
| B.2 | 4 | Port `lib/status.py` with `aggregate_status(ecosystem, mode) -> Status` | High | Pending |
| B.2 | 5 | Add `tests/test_lib_status.py` — mock R subprocess where needed | High | Pending |
| B.2 | 6 | Update `commands/{status,quick,thorough}.md` to invoke `python3 -m lib.status` | Medium | Pending |
| B.2 | 7 | Honor performance budgets — measure on mediationverse | Medium | Pending |
| B.3 | 1 | Read `rforge-mcp` E3 (init) function in `dist/index.js` | Medium | Pending |
| B.3 | 2 | Port `lib/init.py` with `init_context(quick: bool = False)` | Medium | Pending |
| B.3 | 3 | Add `tests/test_lib_init.py` (state file round-trip, idempotency) | Medium | Pending |
| B.3 | 4 | Update `commands/init.md` (or fold into `detect.md` if no init command exists) | Medium | Pending |
| B.4 | 1 | Add `DEPRECATED.md` to the `data-wise/rforge-mcp` repo (separate cross-repo work) | Low | Pending |
| B.4 | 2 | Archive `data-wise/rforge-mcp` on GitHub via `gh repo archive` or UI | Low | Pending |
| B.4 | 3 | Drop the `mcpServers.rforge` entry from `~/.claude/settings.json` (user-side cleanup; document, don't auto-edit) | Low | Pending |
| All | — | `tests/test-all.sh` total: 26+ checks (was 23 after B.1) | Medium | Pending |
| All | — | CHANGELOG `[Unreleased]` entry covering all three phases | Medium | Pending |
| All | — | SPEC status: In Progress → Shipped (after PR merges) | Low | Pending |

## Acceptance criteria

### B.2 — `rforge_status`

- [ ] `lib/status.py` defines `aggregate_status(ecosystem: Ecosystem, mode: str) -> Status` returning a dataclass with per-package checks (`check_status`, `test_status`, `doc_status`, `version_drift`, etc.).
- [ ] Four modes implemented with documented depth + perf budget:
  - **default** (<5s): file-existence checks only (DESCRIPTION valid, NAMESPACE present, R/ has files, tests/ has files).
  - **debug** (<30s): adds parse-time checks (DESCRIPTION semver, NAMESPACE exports, broken imports).
  - **optimize** (<60s): adds `R CMD check --no-tests --no-manual` (or equivalent fast lint).
  - **release** (<120s): full `R CMD check --as-cran` style (or document why we skip).
- [ ] R subprocess is **optional**: if `Rscript` not on PATH, modes that need it degrade gracefully (warn + skip; don't fail). `default` and `debug` must work without R installed.
- [ ] Output supports both `--format text` and `--format json` (same convention as B.1).
- [ ] `commands/{status,quick,thorough}.md` invoke `python3 -m lib.status --mode <mode>` (matching B.1's package-style invocation; `python3 lib/status.py` will fail with relative-import error — intentional).
- [ ] Performance budgets honored on mediationverse (5 pkgs): measure + record in PR description.

### B.3 — `rforge_init`

- [ ] `lib/init.py` defines `init_context(path: str = ".", quick: bool = False) -> Path` returning the path to the written state file.
- [ ] State file format: `.rforge/context.json` (matches MCP convention so existing `.rforge/` state migrates transparently).
- [ ] Idempotent: running twice is a no-op for the state file's identity, may refresh contents (timestamp + analysis snapshot).
- [ ] `quick=True` skips comprehensive analysis (fast path).
- [ ] CLI: `python3 -m lib.init --path . [--quick]`.
- [ ] If `commands/init.md` exists, update it; otherwise document that `/rforge:detect` does this implicitly.

### B.4 — Archive

- [ ] `data-wise/rforge-mcp` has a `DEPRECATED.md` at repo root explaining the migration. Links to `Data-Wise/rforge`. Brief migration notes for anyone with the package locally.
- [ ] GitHub repo `data-wise/rforge-mcp` is archived (read-only, can't open issues/PRs).
- [ ] No npm action needed — `rforge-mcp` was never published.
- [ ] No Homebrew action needed — no formula exists for `rforge-mcp`.
- [ ] `~/.claude/settings.json` `mcpServers.rforge` cleanup is documented (note in CHANGELOG migration section), not auto-edited.

### All-up

- [ ] `bash tests/test-all.sh` passes — target 26+ checks total (B.1 left it at 23; +3 from `lib_status` runners ≈ 26).
- [ ] `python3 -m pytest tests/test_lib_*.py` all pass.
- [ ] `lib_reference_in_sync` test still passes after regenerating reference docs (`scripts/gen_lib_reference.py` extends to cover `lib.status` and `lib.init`).
- [ ] CHANGELOG `[Unreleased]` entry covers all three phases.
- [ ] SPEC status: Draft → In Progress → Shipped (lifecycle transitions in commits).

## Open questions to resolve

These need answers before the relevant phase begins. Capture decisions inline in this file as you go (preserves the audit trail; B.1's pre-merge review captured the same way).

### B.2 questions

1. **R subprocess strategy.** Three options:
   - (a) Pure Python (no R) — fastest, but loses depth in `optimize`/`release` modes.
   - (b) Shell out to `Rscript -e '...'` per-package per-check — flexible but slow per call.
   - (c) Shell out once per mode, batching all checks — fast, but more complex orchestration.
   - **Recommendation TBD in session** — leaning (c) for performance but (a) for simplicity if `optimize`/`release` modes are rarely used.

2. **Caching.** Should status results cache to `.rforge/status-cache.json`? B.3 creates `.rforge/`, so coordinate. Suggest: yes, with a TTL keyed on file mtimes.

3. **MCP semantics parity.** `rforge-mcp` had specific mode names — verify ours match exactly, or document divergence (B.1 already did this for `mode` vs `kind`).

4. **What does `release` mode actually do?** MCP's release mode ran "full CRAN dry-run" — that's expensive (5+ min for a real package). Decision: trust the budget, or downgrade to "full check, no benchmarks"?

### B.3 questions

5. **`/rforge:init` command exists?** Check `commands/init.md`. If yes, update; if no, document that `/rforge:detect` covers this (init might just be a detect-with-side-effects).

6. **State file location.** `.rforge/context.json` matches MCP. Inside the package directory, or at ecosystem root? MCP put it at the package level. Stay consistent.

### B.4 questions

7. **Settings.json cleanup — auto or manual?** The user has `mcpServers.rforge` entry pointing at the now-archived `rforge-mcp` binary. Auto-edit is risky (what if they have customizations?). Document in CHANGELOG migration section + suggest the user remove it themselves. Don't touch their settings.

## How to start (in a fresh session)

```bash
cd ~/.git-worktrees/rforge/feature-mcp-absorb-rest
claude
```

Then in the new session:

1. Read this file + the SPEC: `docs/specs/SPEC-mcp-absorb-2026-05-10.md`
2. Read the MCP server's status tool: `/opt/homebrew/lib/node_modules/rforge-mcp/dist/tools/discovery/status.js`
3. Resolve B.2 open questions inline (especially Q1 — R subprocess strategy gates everything else)
4. Begin B.2 Step 4 once Q1 is decided
5. After B.2 lands, do B.3 (small, ~50 lines code)
6. Last: B.4 paperwork in the rforge-mcp repo (cross-repo work — separate small PR there + GitHub archive button)

## Done when

- All 16 acceptance criteria checked above
- PR opened against `dev` (multi-branch craft-style: feature → dev → main on release)
- `.STATUS` on `dev` reflects: this worktree → `state: REVIEW`
- v1.3.0 release planning kicks in (PR description should indicate "ready for v1.3.0")
- Side-by-side + perf-budget report attached to PR description (mediationverse for B.2; round-trip integrity for B.3)

## Notes / scope discipline

- **Non-breaking by design.** Existing rforge-mcp users keep all functionality; this PR adds parallel implementations in `lib/` and doesn't remove anything from the rforge plugin until B.4 (which is rforge-mcp-side, not plugin-side).
- **Don't bundle craft-parity Phase 3 / 4** — those are separate roadmaps with different release targets (BREAKING v2.0.0 vs non-breaking v1.3.0).
- **B.4 cross-repo work** lives in `data-wise/rforge-mcp` — needs a separate small PR there. This worktree only contains the rforge-side acknowledgment (CHANGELOG note).

## Pre-merge cleanup (per CLAUDE.md)

Before opening the PR, **delete this ORCHESTRATE file** as part of the merge cleanup. It's a working artifact, not part of the shipped product. Last commit on the feature branch should be:

```
chore: remove ORCHESTRATE (merge cleanup)
```

(This was caught and applied for B.1 — same procedure here.)

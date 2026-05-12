# Phase 3 — Command Namespacing (v2.0.0 BREAKING) — Orchestration Plan

> **Branch:** `feature/phase3-namespacing-v2`
> **Base:** `dev`
> **Worktree:** `~/.git-worktrees/rforge/feature-phase3-namespacing-v2`
> **Spec:** `docs/specs/SPEC-phase3-namespacing-2026-05-11.md`
> **Brainstorm:** `BRAINSTORM-phase3-namespacing-2026-05-11.md`
> **Version Target:** v2.0.0 (major; BREAKING)
> **Created:** 2026-05-11

## Objective

Rename 3 of rforge's 16 commands to align with craft's hybrid namespacing (`docs:check`, `health`, `r:check`); leave 13 commands flat. Old names produce a verbatim rename-error via stub command files. Smallest possible v2.0.0 with a clean break and a one-page migration tutorial.

## Phase Overview

| Phase | Increment | Priority | Effort | Status |
|-------|----------|----------|--------|--------|
| 1 | Rename mechanics (file moves + cross-ref sweep) | High | 1-2 h | |
| 2 | Stubs (3 rename-error files + live-test) | High | 45 min | |
| 3 | Tests (rewrite + rename-error assertion) | High | 45 min | |
| 4 | Docs (migration tutorial + REFCARD + README + CHANGELOG + mkdocs.yml) | High | 1 h | |
| 5 | Tap docs (separate PR to data-wise/homebrew-tap) | Medium | 30 min | |
| 6 | Release v2.0.0 (`/craft:release`) | High | 1 h | |

**Total estimated effort:** ~6 hours across 2-3 focused sessions.

## Phase 1: Rename mechanics

**Scope:** Move 3 command files to their new paths; sweep all cross-references in the codebase. ONE atomic commit, no semantic prompt changes.

- [ ] 1.1 Inventory cross-references: `grep -rn '/rforge:doc-check\|/rforge:ecosystem-health\|/rforge:rpkg-check' --include='*.md' --include='*.py' --include='*.sh' --include='*.yml' .` — capture the surface list (~30-50 hits expected)
- [ ] 1.2 Move files:
  - `git mv commands/doc-check.md commands/docs/check.md` (create `commands/docs/` dir)
  - `git mv commands/ecosystem-health.md commands/health.md`
  - `git mv commands/rpkg-check.md commands/r/check.md` (create `commands/r/` dir)
- [ ] 1.3 Update each renamed file's frontmatter `name:` field:
  - `name: rforge:docs:check`
  - `name: rforge:health`
  - `name: rforge:r:check`
- [ ] 1.4 Sed-rewrite all cross-references from the inventory (use the grep output as the worklist)
- [ ] 1.5 Verify with re-grep: 0 hits for old names should remain anywhere EXCEPT CHANGELOG.md (historical entries stay) and the stub files (Phase 2)
- [ ] 1.6 Atomic commit: `git commit -m "feat(rename): v2.0.0 command rename (BREAKING)"`

**Key files:**
- `commands/doc-check.md` → `commands/docs/check.md` (rename + frontmatter update)
- `commands/ecosystem-health.md` → `commands/health.md`
- `commands/rpkg-check.md` → `commands/r/check.md`
- ~30-50 cross-reference updates across `commands/*.md`, `docs/**/*.md`, `README.md`, `tests/test-all.sh`, `tests/test_lib_*.py`

**STOP after this phase.** Verify the commit reviews cleanly before proceeding.

## Phase 2: Rename-error stubs

**Scope:** Recreate the 3 old-name files as stubs containing only the rename-error message. Live-test the first stub before proceeding with the other two.

- [ ] 2.1 Create `commands/doc-check.md` as stub (use the format from SPEC's "Option A" section):
  - Frontmatter: `name: rforge:doc-check`, `description: ⚠️ RENAMED to /rforge:docs:check in v2.0.0`
  - Body: verbatim-emit prompt-control pattern
- [ ] 2.2 **LIVE-TEST the first stub:**
  - Restart Claude Code IN THIS WORKTREE: `cd <worktree> && claude`
  - Type `/rforge:doc-check`
  - **Expected:** verbatim emission of the rename-error message, no execution, no paraphrase
  - **If output drifts:** iterate prompt-control wording in `commands/doc-check.md` until reliable
- [ ] 2.3 Once Phase 2.1's stub is validated, create the other 2 stubs using the same format:
  - `commands/ecosystem-health.md` (stub → points at `/rforge:health`)
  - `commands/rpkg-check.md` (stub → points at `/rforge:r:check`)
- [ ] 2.4 Commit: `git commit -m "feat(stubs): rename-error stubs for renamed commands"`

**Risk:** If the stub mechanism doesn't produce reliable verbatim emission even with prompt-control patterns, fall back to hook-based interception (Option B in the SPEC). Decision point at 2.2.

**STOP after this phase.** Confirm all 3 stubs work before tests.

## Phase 3: Tests

**Scope:** Update test suite to use new names; add a rename-error assertion test.

- [ ] 3.1 Update `tests/test-all.sh` — replace all old slash-command name references with new names
- [ ] 3.2 Update `tests/test_lib_*.py` — same sweep, all old-name strings replaced
- [ ] 3.3 Add a new test that asserts the 3 stub files exist AND that their content contains the expected rename-error format
- [ ] 3.4 Update CI command-count check in `.github/workflows/ci.yml` — verify the count assertion still holds (16 commands net: 13 flat + 3 sub-namespaced)
- [ ] 3.5 Run full test suite — both `bash tests/test-all.sh` (23+ checks) and `python3 -m pytest tests/` (65 checks) must pass
- [ ] 3.6 Commit: `git commit -m "test: update tests for v2.0.0 rename + rename-error assertion"`

**STOP after this phase.** All green before doc sweep.

## Phase 4: Docs

**Scope:** Write the migration tutorial; update REFCARD, README, CHANGELOG, mkdocs.yml, and per-command docstrings.

- [ ] 4.1 Write `docs/migration/v2.0.0-rename.md` — single-page mapping table per SPEC's wireframe
- [ ] 4.2 Update `docs/REFCARD.md` — replace all old slash-command refs with new names; bump version line to v2.0.0; update last-updated date
- [ ] 4.3 Update `README.md` — "What's new in v2.0.0" section with link to migration tutorial; update tree-diagram comments
- [ ] 4.4 Update `docs/index.md` — same as README
- [ ] 4.5 Update `docs/commands.md` — full command reference now uses new names; the 3 renamed commands get their new section paths
- [ ] 4.6 Update `docs/tutorials/getting-started.md` — replace any slash-command examples that touched the renamed commands
- [ ] 4.7 Update `docs/troubleshooting.md` — same
- [ ] 4.8 Update `mkdocs.yml` — `site_description`, nav items (add Migration → v2.0.0-rename)
- [ ] 4.9 Update `CHANGELOG.md` — `[2.0.0] - YYYY-MM-DD` entry with BREAKING-CHANGE callout and link to migration tutorial
- [ ] 4.10 Verify with `mkdocs build --strict` — clean except the known structural README/index warning
- [ ] 4.11 Commit: `git commit -m "docs: v2.0.0 migration tutorial + doc-surface rename sweep"`

**STOP after this phase.** Verify rendered output via `mkdocs serve` and a fresh REFCARD read.

## Phase 5: Tap docs (separate PR)

**Scope:** Update `data-wise/homebrew-tap`'s `docs/formulas/plugins.md` to reflect v2.0.0 names. Lives outside this worktree.

- [ ] 5.1 Switch context: `cd ~/projects/dev-tools/homebrew-tap`
- [ ] 5.2 Edit `docs/formulas/plugins.md` rforge section — install command examples may not need changes (no install-time slash-command refs), but verify; if any v1.x slash-command references appear, update them
- [ ] 5.3 Commit + push to homebrew-tap main (it's a private tap; admin-bypass on direct push)
- [ ] 5.4 Verify the Pages site updates within ~60s

**STOP after this phase.** Tap is now ready for v2.0.0 release.

## Phase 6: Release v2.0.0

**Scope:** Run `/craft:release` following the v1.3.0 playbook with a major-version emphasis.

- [ ] 6.1 Pre-flight: `bash tests/test-all.sh` + `python3 -m pytest tests/` (both must be green on dev after PR merge)
- [ ] 6.2 PR `dev` → `main` titled "Release: v2.0.0 — Phase 3 command namespacing (BREAKING)"
- [ ] 6.3 PR body: link to migration tutorial, summarize the 3 renames, test count
- [ ] 6.4 Merge + tag v2.0.0
- [ ] 6.5 `/craft:release` Step 10a: update tap formula (`url`/`sha256`) — same recipe as v1.3.0
- [ ] 6.6 **Manifest sync:** update `generator/manifest.json` rforge entry to v2.0.0 + new SHA, verify with `generate.py rforge --diff` → IDENTICAL (per the homebrew tap drift memory)
- [ ] 6.7 Verify downstream: live docs site, brew info, brew livecheck
- [ ] 6.8 Open GitHub Discussions thread asking for feedback on the renames (informs v2.1.0 decision on `quick`/`thorough`)

## Friction Prevention (from this session's memory)

- **Branch-guard CWD false-positives:** session CWD is THIS worktree; cross-repo ops to homebrew-tap should work without bypass. If they don't, switch this session's repo branch to `dev` first.
- **Manifest-formula drift:** after Phase 6 ships, IMMEDIATELY update `generator/manifest.json`. See `~/.claude/projects/.../memory/reference_homebrew_tap_drift.md`. Don't skip.
- **Tap Pages drift:** Phase 5 prevents the "tap docs site doesn't show latest release" symptom that bit us during v1.3.0 debug. Do not skip Phase 5.
- **No autonomous starts:** STOP after every phase. Verify the artifacts before proceeding to the next phase. Per CLAUDE.md ORCHESTRATE rule, implementation requires fresh-session conversation context, not 6-phase momentum.
- **Test per phase:** Run tests after every phase to catch regressions. Don't accumulate.
- **chezmoi cd anti-pattern:** if syncing memory mid-implementation, use `claude-sync` (correctly handles non-interactive context).

## Acceptance Criteria

(from `docs/specs/SPEC-phase3-namespacing-2026-05-11.md`)

- [ ] All 16 commands accessible under v2.0.0 naming after merge
- [ ] Invoking any old command name produces verbatim rename-error message
- [ ] `/help` lists only v2.0.0 names
- [ ] `bash tests/test-all.sh` and `pytest` both green on post-rename branch
- [ ] REFCARD, README, docs/index, docs/commands, tutorials, troubleshooting, tap docs all reference new names
- [ ] Migration tutorial exists at `docs/migration/v2.0.0-rename.md`
- [ ] `[2.0.0]` CHANGELOG entry with migration link

## Commit Strategy

One semantic commit per phase. All conventional commits:

- Phase 1: `feat(rename): v2.0.0 command rename (BREAKING)`
- Phase 2: `feat(stubs): rename-error stubs for renamed commands`
- Phase 3: `test: update tests for v2.0.0 rename + rename-error assertion`
- Phase 4: `docs: v2.0.0 migration tutorial + doc-surface rename sweep`
- Phase 5: `docs(rforge): update v2.0.0 command names` (committed to homebrew-tap)
- Phase 6: standard `/craft:release` commits

## Verification

After each phase:

```bash
# rforge test suite
bash tests/test-all.sh
python3 -m pytest tests/

# Doc strict-build (after Phase 4)
mkdocs build --strict 2>&1 | grep -E '^(WARNING|ERROR)' | grep -v 'Excluding .README.md'

# Stub live-test (after Phase 2.1)
# Manual: restart Claude in worktree, type `/rforge:doc-check`, confirm verbatim emission
```

## Session Instructions

### Context

You are in the **rforge plugin's `feature/phase3-namespacing-v2` worktree**. The SPEC at `docs/specs/SPEC-phase3-namespacing-2026-05-11.md` has the frozen design; this ORCHESTRATE file has the phasing + per-phase checklists.

### How to Start

```bash
cd ~/.git-worktrees/rforge/feature-phase3-namespacing-v2
claude
```

On session start, paste:

> Read `ORCHESTRATE-phase3-namespacing.md` and the spec at `docs/specs/SPEC-phase3-namespacing-2026-05-11.md`. Start Phase 1.

### Phase-by-Phase Rules

1. Read the SPEC's relevant section before each phase
2. Implement only what's listed in this phase's checklist — do not pull work from later phases
3. Run verification commands after EVERY phase
4. Commit in logical groups (use the commit-strategy section's exact messages or close variants)
5. **STOP** between phases and confirm with the user before proceeding
6. If a live-test fails (Phase 2.2 stub validation), DO NOT proceed — iterate or fall back to Option B per the SPEC

### What NOT to Do

- ❌ Do not begin implementation in the session that created this worktree (per CLAUDE.md)
- ❌ Do not skip the live-test in Phase 2.2
- ❌ Do not bundle phases into a single commit
- ❌ Do not start v2.0.1 work before v2.0.0 ships — even if the SPEC mentions it
- ❌ Do not update the homebrew-tap repo from this worktree's session if it requires worktree-CWD branch-guard workarounds; do tap work from a separate Claude session in the tap repo

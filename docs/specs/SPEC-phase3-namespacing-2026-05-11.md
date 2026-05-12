# SPEC — Phase 3: Command Namespacing (v2.0.0 BREAKING)

> **Status:** draft
> **Created:** 2026-05-11
> **From Brainstorm:** [BRAINSTORM-phase3-namespacing-2026-05-11.md](../../BRAINSTORM-phase3-namespacing-2026-05-11.md)
> **Target Version:** v2.0.0 (major; BREAKING)
> **Predecessor:** v1.3.0 (released 2026-05-11; Path B complete)
> **Related:** craft-parity roadmap (this is Phase 3 of 4)

## Overview

rforge currently ships 16 commands under a flat `/rforge:<verb>` namespace. craft (the sibling plugin we mirror) organizes its ~100 commands across 13 functional sub-namespaces (`docs:`, `git:`, `workflow:`, etc.) plus 7 flat top-level commands. **Phase 3 brings rforge's namespacing into hybrid alignment with craft: shared concepts share sub-namespaces, R-specific concepts get their own (`r:`), and high-frequency daily commands stay flat.**

Net mechanical scope: 13 of 16 commands stay flat; 3-5 move under sub-namespaces. The breaking part is removing old names with a helpful rename-error response — no silent aliases, no compat window. Migration is a single mapping-table page.

## Primary User Story

> **As an R-package developer using rforge daily**, **I want** command names that signal what each command does at a glance (e.g., `/rforge:r:check` clearly invokes R CMD check) **so that** I can discover and remember commands without re-reading the REFCARD every time.

### Acceptance Criteria

- [ ] All 16 commands are accessible under v2.0.0 naming after the rename PR merges.
- [ ] Invoking any old command name produces an error of the form: `Renamed to /rforge:<new:path> — see migration tutorial at <https://data-wise.github.io/rforge/migration/v2.0.0-rename/>`.
- [ ] `/help` in Claude Code lists only v2.0.0 names; old names are absent.
- [ ] `bash tests/test-all.sh` and `python3 -m pytest tests/` both pass on the post-rename branch. Test rewrites use new names; one dedicated test asserts the rename-error path.
- [ ] REFCARD.md, README.md, docs/index.md, docs/commands.md, docs/tutorials/*.md, docs/troubleshooting.md, and the tap's `docs/formulas/plugins.md` all reference the new names exclusively (no stale `/rforge:status` etc.).
- [ ] Migration tutorial exists at `docs/migration/v2.0.0-rename.md` as a single-page mapping table with one-sentence rationale per move.
- [ ] CHANGELOG.md `[2.0.0]` entry explains the breaking change with a link to the migration tutorial.

## Secondary User Stories

> **As a craft user discovering rforge for the first time**, **I want** rforge's namespacing to feel familiar (`docs:check` works in both) so that I can transfer mental models without re-learning.

**Acceptance:** Where craft has a directly-analogous verb (`docs:check`, `release`), rforge's equivalent uses the same sub-namespace. Where rforge has R-specific verbs without craft equivalents, they go under `r:`.

> **As a contributor reviewing the v2.0.0 PR**, **I want** the rename to be reviewable by inspection rather than re-reading every command's prompt content.

**Acceptance:** The rename ships in one atomic commit (file moves + cross-ref updates). Subsequent commits in the PR handle tests, migration tutorial, and CHANGELOG separately. The rename commit is git-mv-only and ref-rewrite — no semantic changes to prompts.

## Architecture

### Current state (v1.3.x)

```text
commands/
├── analyze.md         /rforge:analyze
├── capture.md         /rforge:capture
├── cascade.md         /rforge:cascade
├── complete.md        /rforge:complete
├── deps.md            /rforge:deps
├── detect.md          /rforge:detect
├── doc-check.md       /rforge:doc-check
├── ecosystem-health.md /rforge:ecosystem-health
├── impact.md          /rforge:impact
├── init.md            /rforge:init
├── next.md            /rforge:next
├── quick.md           /rforge:quick
├── release.md         /rforge:release
├── rpkg-check.md      /rforge:rpkg-check
├── status.md          /rforge:status
└── thorough.md        /rforge:thorough
```

### Target state (v2.0.0)

```mermaid
graph TD
    rforge[/rforge:*]
    rforge --> analyze[analyze]
    rforge --> capture[capture]
    rforge --> cascade[cascade]
    rforge --> complete[complete]
    rforge --> deps[deps]
    rforge --> detect[detect]
    rforge --> impact[impact]
    rforge --> init[init]
    rforge --> next[next]
    rforge --> quick[quick]
    rforge --> release[release]
    rforge --> status[status]
    rforge --> thorough[thorough]
    rforge --> health[health]

    rforge --> docs_ns[docs:]
    docs_ns --> docs_check[docs:check]

    rforge --> r_ns[r:]
    r_ns --> r_check[r:check]
```

13 flat commands + 2 sub-namespaces (`docs:` 1 command, `r:` 1 command) + 1 reverted-to-flat (`health` from `ecosystem-health`).

### Rename mapping table (FROZEN by this SPEC)

| Current (v1.x) | New (v2.0.0) | Reason |
|---|---|---|
| `/rforge:analyze` | (unchanged) | High-freq entry-point verb |
| `/rforge:capture` | (unchanged) | Task management — keep flat per "rest stay flat" |
| `/rforge:cascade` | (unchanged) | Specialized but flat-friendly |
| `/rforge:complete` | (unchanged) | Task management — flat |
| `/rforge:deps` | (unchanged) | High-freq dependency verb |
| `/rforge:detect` | (unchanged) | Discovery entry-point |
| `/rforge:doc-check` | `/rforge:docs:check` | Aligns with craft's `docs:` namespace; pluralizes for consistency |
| `/rforge:ecosystem-health` | `/rforge:health` | Single command, no sub-namespace needed; shorter daily-use name |
| `/rforge:impact` | (unchanged) | High-freq, sibling of `deps` |
| `/rforge:init` | (unchanged) | Setup command |
| `/rforge:next` | (unchanged) | Workflow entry-point — flat for ergonomics |
| `/rforge:quick` | (unchanged) | Headline speed verb — defer rename to v2.1.0 if user demand |
| `/rforge:release` | (unchanged) | Single-command sub-namespace would add typing without payoff |
| `/rforge:rpkg-check` | `/rforge:r:check` | R-specific; cleaner name; `r:` namespace established |
| `/rforge:status` | (unchanged) | Daily-use; flat for ergonomics; `health:status` rejected to avoid 2-command `health:` namespace tension with the `health` rename above |
| `/rforge:thorough` | (unchanged) | Headline speed verb — defer rename to v2.1.0 if user demand |

**Open-question resolutions** (the 4 questions left open in the brainstorm):

1. **`status` placement:** REMAINS FLAT. Daily-use overrides namespace consistency; `health` (singular, flat) absorbs the only naturally-health-themed verb.
2. **`release` placement:** REMAINS FLAT. One-command sub-namespaces add typing without payoff.
3. **`quick`/`thorough` rename:** DEFERRED to v2.1.0. They're headline commands; renaming would surprise users beyond the spec's "minimum surprise" goal. Revisit after v2.0.0 user feedback.
4. **Task-management commands (`capture`/`complete`/`next`) under `workflow:`:** REJECTED. The user's "rest stay flat" preference + craft's own pattern of keeping high-freq commands flat (`do`, `smart-help`, etc.) makes this the right call.

**Net change:** 3 renames (`doc-check → docs:check`, `ecosystem-health → health`, `rpkg-check → r:check`). 13 commands unchanged. Smallest possible breaking change that still earns the v2.0.0 major bump.

### Rename-error mechanism

When a user invokes a renamed command, the plugin responds with a structured error rather than executing. Implementation:

**Option A (chosen): stub command files with explicit verbatim instruction**

After inspecting existing rforge command files (`commands/quick.md` is the canonical reference), the file format is:
- YAML frontmatter (`name`, `description`) — the `description` shows up in Claude Code's `/help` listing
- Markdown body — becomes Claude's prompt when the user types the slash command

The stub leverages BOTH layers for resilience:

```markdown
---
name: rforge:doc-check
description: ⚠️ RENAMED to /rforge:docs:check in v2.0.0 — see migration tutorial
---

# /rforge:doc-check — RENAMED in v2.0.0

You MUST respond with EXACTLY the message below. Do not interpret it, paraphrase it, or take any action beyond emitting it.

---

❌ **Renamed:** this command (`/rforge:doc-check`) was renamed in v2.0.0.

**Use instead:** `/rforge:docs:check`

See the migration tutorial: <https://data-wise.github.io/rforge/migration/v2.0.0-rename/>

---

Reason for rename: aligns rforge's `docs:` namespace with craft's `docs:` namespace. Two other commands were renamed in v2.0.0:

- `/rforge:ecosystem-health` → `/rforge:health`
- `/rforge:rpkg-check` → `/rforge:r:check`

End of response.
```

**Why this works:**

1. **Frontmatter `description` shows the warning in `/help` BEFORE invocation.** Users browsing the command list see the rename hint without typing anything.
2. **"You MUST respond with EXACTLY the message below" + "End of response"** is the well-tested Claude prompt-control pattern that produces literal output without paraphrasing or follow-through behavior.
3. **The stub doesn't reference `lib/` or any real action**, so even if Claude misbehaves, there's nothing to execute.
4. **The body sits as the Claude prompt** — Claude reads it like any other rforge command prompt, then responds.

**Live-test plan (implementation worktree, before merge):**

1. Create the first stub (`commands/doc-check.md` rewritten as stub) in the feature worktree
2. User restarts Claude Code in that worktree (slash commands load at session start)
3. User types `/rforge:doc-check`
4. Expected output: the rename-error message verbatim, no execution
5. If output drifts (paraphrases or executes), iterate on prompt-control wording before proceeding with the other 2 stubs

**Option B (rejected): hook interception**
- Requires modifying the `pretooluse.py` hook to recognize old slash-command invocations
- More complex; the hook intercepts `Write`/`Edit` tool calls, not slash-command-name resolution
- Risk: hook doesn't run for command-name lookup

**Decision:** Option A. Simplest mechanism, no hook changes, easy to remove in v3.0.0 (just delete the 3 stub files).

## API Design

**N/A — this is a rename refactor, no API contract changes.** The internal `lib/` modules are unchanged. The plugin's external surface is the slash-command names, which are renaming per the table above.

## Data Models

**N/A — no data model changes.** State files (`~/.rforge/context.json`), config (`config.json`), and the pretooluse hook contract are unchanged.

## Dependencies

No new dependencies. The rename:
- Reuses existing `bash`, `python3`, `pytest`, `mkdocs` toolchains
- Adds no new system or runtime requirements
- Affects only file paths and string references in command/doc files

## UI/UX Specifications

### User flow — a v1.x user discovers the rename

```text
1. User opens Claude Code, types `/rforge:doc-check`
2. Plugin responds (via the stub file's content):
     "This command was renamed in v2.0.0.
      Renamed to: /rforge:docs:check
      See the migration tutorial: <URL>"
3. User reads, optionally clicks/copies the URL
4. User types `/rforge:docs:check` — works
5. (Optional) User reads the migration tutorial table to learn the other 2 renames
```

### Wireframe — migration tutorial page

```text
# Migrating to rforge v2.0.0

> **3 commands renamed.** Update your habits or scripts using the table below.

| You used to type | In v2.0.0+, type | Why |
|---|---|---|
| /rforge:doc-check       | /rforge:docs:check | Aligns with craft's docs: namespace |
| /rforge:ecosystem-health | /rforge:health     | Shorter, daily-use friendly         |
| /rforge:rpkg-check      | /rforge:r:check    | R-specific commands get an r: prefix |

13 other commands (analyze, capture, cascade, complete, deps,
detect, impact, init, next, quick, release, status, thorough)
are unchanged.

## Why these renames?

[1 paragraph explaining the hybrid-with-craft alignment principle]

## What about my scripts?

[grep recipe + sed one-liner to mass-update local clones]
```

### Accessibility checklist

- [ ] Migration tutorial is a single page (cognitive-load-friendly)
- [ ] Rename-error response includes the new name in the first line (screen-reader-friendly placement)
- [ ] Tutorial table is plain markdown (no JavaScript dependencies)
- [ ] Migration tutorial linked from README, REFCARD, CHANGELOG, and rename-error stubs (5 entry points)

## Implementation Notes

### Phasing

1. **SPEC review** (this document) — resolves the 4 open questions, freezes the rename table.
2. **Worktree creation** — `feature/phase3-namespacing-v2` from dev. NOT orchestrated (single-session refactor); a regular feature worktree per global CLAUDE.md.
3. **Rename commit 1** — `git mv` for the 3 renamed files; `sed` for all `/rforge:doc-check`, `/rforge:ecosystem-health`, `/rforge:rpkg-check` references across markdown + Python.
4. **Stub commit 2** — recreate the 3 old-name files as stubs containing only the rename-error message.
5. **Test commit 3** — update `tests/test-all.sh` and pytest cases; add the rename-error assertion test.
6. **Docs commit 4** — write `docs/migration/v2.0.0-rename.md`, update REFCARD, README, CHANGELOG, mkdocs.yml.
7. **Tap docs commit 5** — separate PR to `Data-Wise/homebrew-tap` to update `docs/formulas/plugins.md` references.
8. **Release** — `/craft:release` for v2.0.0, same playbook as v1.3.0.

### Files to update (surface inventory)

Run `grep -rn '/rforge:doc-check\|/rforge:ecosystem-health\|/rforge:rpkg-check' --include='*.md' --include='*.py' --include='*.sh' --include='*.yml' .` for the full list. Expected hits: ~30-50 references across:
- `commands/*.md` (internal cross-refs in command prompts)
- `README.md`, `docs/index.md`, `docs/REFCARD.md`, `docs/commands.md`
- `docs/tutorials/getting-started.md`, `docs/troubleshooting.md`
- `tests/test-all.sh`, `tests/test_lib_*.py` (test command invocations)
- `CHANGELOG.md` (historical entries — leave alone; don't rewrite history)

### Risks

1. **Stub-file lookup behavior in Claude Code.** Designed per the "Option A" format above (verbatim-emit prompt-control pattern, with `description` frontmatter showing the rename in `/help`). Validation: implementation worktree will live-test the first stub before proceeding with the other two — see "Live-test plan" in the rename-error mechanism section. Fallback if the test fails: hook-based interceptor (Option B) with a documented prompt-control retry first.

2. **Documentation update sprawl.** The mkdocs nav, REFCARD, tutorials, troubleshooting page, hub.md, per-command docstrings, AND the homebrew-tap's `docs/formulas/plugins.md` all reference command names. The rename script must handle this OR a separate doc-sweep PR follows. Mitigation: include the doc sweep as commits 4-5 of the same PR, not a follow-up.

3. **CI commands count check.** `tests/test-plugin-structure.sh` and `.github/workflows/ci.yml` assert `>= 15 commands`. After the rename, the count is still 16 (3 stub files + 13 originals; renamed files just move). Sanity-check the assertion logic before merging.

## Open Questions

**All 4 brainstorm-stage open questions are RESOLVED in this SPEC** (see "Open-question resolutions" under the rename mapping table above). The SPEC review may surface new questions during scrutiny — log them here before approving.

- [ ] (none yet — add here during SPEC review)

## Review Checklist

- [ ] Rename mapping table reviewed for completeness (all 16 commands accounted for)
- [ ] Each rename has a 1-sentence rationale in the "Reason" column
- [ ] Open questions resolved (4 of 4 are decided in this SPEC)
- [ ] Acceptance criteria for primary user story are testable
- [ ] Stub-file mechanism (Option A) format locked in SPEC; live-test scheduled for first stub in implementation worktree
- [ ] Risks reviewed; mitigations are concrete actions, not "be careful"
- [ ] Cross-repo dependency (homebrew-tap docs/formulas/plugins.md) acknowledged
- [ ] CI command-count check expected to pass post-rename

## History

| Date | Change |
|---|---|
| 2026-05-11 | Initial draft generated from BRAINSTORM-phase3-namespacing-2026-05-11.md via `/workflow:brainstorm --deep --feat save`. All 4 brainstorm open questions resolved with rationale. |

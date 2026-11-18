# Phase 3 — Command Namespacing (v2.0.0 BREAKING)

> **Generated:** 2026-05-11 via `/workflow:brainstorm --deep --feat`
> **Mode:** deep + feat + max (agent-assisted)
> **Status:** Brainstorm — not yet a spec

## Context (from this session's release sweep)

- v1.3.0 just shipped (16 commands, MCP absorbed, plugin self-contained)
- Phase 3 is the next item in `.STATUS` backlog after v1.3.0
- The 16 commands ship under a flat `/rforge:<verb>` namespace; craft uses 13 hierarchical sub-namespaces (arch:, ci:, code:, dist:, docs:, git:, orchestrate:, plan:, site:, test:, utils:, workflow:, plus a few flat). craft-parity Phase 3 = adopt the same scheme where it fits.

## User decisions (8 questions answered)

1. **Categorization:** Hybrid — align with craft for shared concepts, diverge for R-specific
2. **Compat window:** None — clean break at v2.0.0
3. **Old-name behavior:** Clean break + helpful error ("Renamed to /rforge:new:name — see migration tutorial at <link>")
4. **v2.0.0 scope:** Namespacing only (Phase 4 + v1.4.0 4-mode ship separately)
5. **Migration tutorial:** Single mapping table on a docs page (5-min read)
6. **Subnamespaces in scope:** `docs:`, `release:`, `health:`, `r:` (R-specific); rest stay flat
7. **Testing:** Replace all tests with new names + add a rename-error assertion test

## Reference: craft's namespacing (from Explore agent)

13 sub-namespaces in craft. Most-shared with rforge's domain:

- **`docs:`** — doc generation, validation, links, lint, tutorials (18 commands in craft)
- **`workflow:`** — task management, brainstorm, focus, next, recap, stuck (13 commands)
- **`check`** (flat) — universal pre-flight validation
- **`release`** (in `code:`) — release planning workflow
- **`do`** (flat) — intelligent router

7 top-level flat commands in craft: `check`, `do`, `discovery-usage`, `hub`, `orchestrate`, `smart-help`, `test`. These are high-frequency entry-point commands. Craft kept them flat for ergonomics — same principle applies to rforge's daily commands.

## User stories

### Primary

> **As an R-package developer** using rforge daily, **I want** command names that signal what each command does at a glance (e.g., `/rforge:r:check` clearly invokes R CMD check, `/rforge:health:status` is clearly a health-related status) **so that** I can discover and remember commands without re-reading the REFCARD every time.

**Acceptance:**
- [ ] All 16 commands accessible under the v2.0.0 naming scheme.
- [ ] Old names produce a helpful error ("Renamed to X — see <migration-tutorial>") on first invocation.
- [ ] `/help` shows only new names; old names are absent from listings.
- [ ] REFCARD.md and tutorials reference the new names exclusively.
- [ ] Migration tutorial is a single page with a mapping table.

### Secondary

> **As a craft user discovering rforge**, **I want** rforge's namespacing to feel familiar so that I can transfer mental models (e.g., expecting `docs:check` to exist in both plugins).

**Acceptance:**
- [ ] `docs:`, `release:`, `health:` align conceptually with craft's namespaces.
- [ ] Where craft has a doc-check or release verb, rforge's equivalent uses the same sub-namespace.

> **As a contributor**, **I want** the rename mechanics to be a mechanical file-and-string operation so I can review the v2.0.0 PR by inspection rather than re-reading every command's prompt.

**Acceptance:**
- [ ] Rename script is committed and reviewable (renames files + updates internal cross-references).
- [ ] The v2.0.0 PR contains the rename in a single atomic commit, not a series of intermediate states.

## Proposed name mapping (DRAFT — open questions below)

Working draft. Final mapping needs a spec/SPEC review before code:

| Current | Proposed v2.0.0 | Rationale |
|---|---|---|
| `/rforge:analyze` | flat — unchanged | High-frequency entry-point verb |
| `/rforge:capture` | flat — unchanged | Task management (matches craft pattern of keeping `do`/`smart-help` flat) |
| `/rforge:cascade` | flat — unchanged | Specialized but flat-friendly verb |
| `/rforge:complete` | flat — unchanged | Task management — keep flat |
| `/rforge:deps` | flat — unchanged | High-freq dependency verb |
| `/rforge:detect` | flat — unchanged | Discovery entry-point |
| `/rforge:doc-check` | `/rforge:docs:check` | Aligns with craft's `docs:` namespace; pluralizes for consistency |
| `/rforge:ecosystem-health` | `/rforge:health:check` ⚠️ | Open Q: see below |
| `/rforge:impact` | flat — unchanged | High-freq, sibling of `deps` |
| `/rforge:init` | flat — unchanged | Setup command |
| `/rforge:next` | flat — unchanged | Workflow entry-point (matches craft's `workflow:next` but keep flat for ergonomics) |
| `/rforge:quick` | flat — unchanged | Daily-use speed verb |
| `/rforge:release` | flat — unchanged ⚠️ | Open Q: should be `release:plan`? See below |
| `/rforge:rpkg-check` | `/rforge:r:check` | R-specific; cleaner name; `r:` namespace established |
| `/rforge:status` | flat — unchanged ⚠️ | Open Q: should be `health:status`? See below |
| `/rforge:thorough` | flat — unchanged | Daily-use speed verb |

**Net:** 13 commands stay flat, 3 move under sub-namespaces (`docs:check`, `health:check`, `r:check`). Two more might move depending on open-question resolutions.

## Open questions for spec review

1. **`status` and `health:` tension.** User said health: is in-scope but also "rest stay flat." `status` is a daily-use command — moving it to `health:status` adds typing. If `health:` only has `health:check`, it's a one-command namespace (awkward). Three options:
   - Keep `status` flat AND `health:` namespace dies (rename `ecosystem-health` → `health` flat)
   - Move both: `health:status` + `health:check` (consistent but typing cost)
   - Move only `ecosystem-health`: it becomes `/rforge:health` flat (single command, no sub-namespace)
   - **Recommendation:** Pre-spec poll on real-user typing frequency, then decide.

2. **`release` and `release:` tension.** If `release:` namespace has only `release:plan`, the colon adds no value. Two options:
   - Keep `release` flat (recommended unless a sibling like `release:notes` joins)
   - Bump to `release:plan` only if v2.x adds `release:notes` or `release:dry-run` soon

3. **Should we rename `quick` and `thorough` to a depth-aware namespace?** Like `/rforge:analyze:quick` and `/rforge:analyze:thorough`. Risk: those are the headline commands; renaming them would surprise users beyond the spec's "minimum surprise" goal. **Recommendation:** Defer to v2.1.0 if real users complain about the flat naming.

4. **Where do task-management commands go?** `capture`, `complete`, `next` look like craft's `workflow:` namespace. Should they become `/rforge:workflow:capture` etc.? **Recommendation:** No — keep flat for the daily flow. The spec answer "rest stay flat" supports this.

## Implementation plan

### Quick wins (< 30 min each)

⚡ **Draft the mapping table doc** — pure markdown, the migration tutorial itself. Even before code, the table is the contract. Lives at `docs/migration/v2.0.0-rename-table.md`.

⚡ **Write the rename-error message format** — what does `/rforge:status` produce in v2.0.0? Decide the exact text and where the migration link points. One sentence, one URL.

⚡ **Inventory cross-references in code+docs** — `grep -rn '/rforge:' --include='*.md' --include='*.py' --include='*.sh'` produces the surface area that needs updating. Probably 50-80 references.

### Medium effort (1-2 hours)

- [ ] **SPEC draft for v2.0.0** — `docs/specs/SPEC-phase3-namespacing-2026-05-11.md`. Resolves the open questions above, freezes the mapping table.
- [ ] **Rename script** — `scripts/rename-v2.sh` that moves command files and updates internal cross-refs in one atomic pass. Idempotent (re-running on already-renamed state is a no-op).
- [ ] **pretooluse hook rename detector** — when user invokes an old-name command via slash-command syntax (which the plugin handles via `commands/<name>.md`), the hook intercepts and writes the rename error. Or alternatively, leave stub `commands/<old>.md` files that contain only the rename error.

### Long-term (future sessions)

- [ ] **v2.0.0 release pipeline** — same as v1.3.0's `/craft:release` pattern, with extra step for tap site update (`docs/formulas/plugins.md` will need new install command examples).
- [ ] **Post-v2.0.0 user-feedback collection** — open a GitHub Discussions thread asking: which renames feel awkward? Use the feedback to inform v2.1.0 (might revisit `quick`/`thorough` flat-vs-namespaced decision).
- [ ] **Migration script for power users** — optional `rforge migrate` shell script that finds old-name references in user's local clones and offers to rewrite. Lower priority than the table.

## Recommended path

→ **Start with `/brainstorm save` to capture this as a SPEC.** The decisions are coherent but the 4 open questions need explicit resolution before any code work. SPEC review is where you freeze the exact mapping table.

→ **After SPEC merges:** create `feature/phase3-namespacing-v2` worktree (NOT a worktree-orchestrated branch — this is a single-session refactor). Implement the rename in one commit, the rename-error mechanism in a second, and the tests + migration tutorial in subsequent commits. PR titled "v2.0.0 — Phase 3: command namespacing (BREAKING)".

→ **Coordinate v2.0.0 with v2.0.1 plan.** The first patch after a breaking version usually fixes overlooked old-name references. Have a `v2.0.1` placeholder ready in CHANGELOG.md to land within ~3 days of v2.0.0.

## Risks / non-obvious considerations

- **`/help` collisions in Claude Code itself.** If `commands/status.md` and `commands/health/status.md` both exist during the transition, Claude Code may not handle the duplication gracefully. The clean-break strategy avoids this since old files are removed entirely.
- **Documentation update sprawl.** The mkdocs nav, REFCARD, tutorials, troubleshooting page, hub.md, and all per-command docstrings reference old names. The rename script must handle this OR a separate doc-sweep PR follows. The latter is cleaner for review.
- **The tap's `docs/formulas/plugins.md`** also documents install + usage. Same drift category we hit during v1.3.0 (and patched in the just-finished `/debug` session). Add it to the surface inventory.

## Estimated effort

- SPEC draft: 1 session (~1-2 hours)
- Implementation worktree: 1 session (~4-6 hours) — code rename, doc sweep, tests, migration tutorial
- Release pipeline (v2.0.0): 1 session (~1 hour, mostly waiting on CI + tap deploy)

**Total: 3 sessions, ~6-9 focused hours over ~2 weeks**

## What this brainstorm does NOT decide

The 4 open questions above (status placement, release placement, quick/thorough naming, task-management placement) need an explicit SPEC review with a fresh eye. Don't merge the rename PR until the SPEC is approved and the mapping table is frozen.

---

**Next step:** Run `/workflow:brainstorm s` (or capture this as a spec via the `--save` prompt) to convert the open questions into a formal SPEC, then start implementation.

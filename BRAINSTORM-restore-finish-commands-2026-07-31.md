# BRAINSTORM: `/rforge:restore` + `/rforge:finish` — R-package session boundary commands

**Date:** 2026-07-31
**Depth:** default · **Focus:** arch
**Categories:** tech, risks, existing, scope

## Context

craft ships `/craft:restore` (thin shim → `dev/git` skill Op 7 + `adhd-workflow` skill's
Context Restoration) and `/craft:finish` (thin shim → `adhd-workflow`'s Session Completion
op). savant ships `/savant:restore` (a self-contained *prompt-command* — no skill, no
generator module — that recaps + reports doc-quartet currency, `--sync` applies gated
fixes) and `/savant:session` (open/close/report lifecycle).

rforge has neither today. This brainstorm designs rforge-native equivalents, scoped to run
**inside an R package repo** (e.g. `medfit`, `probmed`), not inside the rforge plugin repo
itself — anticipating a future root-level `/restore`/`/finish` dispatcher that detects "this
is an R package" and re-routes here instead of to craft's or savant's generic version.

## What already exists in rforge (overlap check)

| Command | Scope | Why it's *not* restore/finish |
|---|---|---|
| `/rforge:status` | Ecosystem-wide dashboard (`lib/status.py`, multi-package) | Aggregates *across* packages; doesn't do single-repo "where did I leave off" |
| `/rforge:health` | Ecosystem health score | Same axis as status — breadth, not session-boundary |
| `/rforge:next` | Ecosystem-aware next-task suggestion | Answers "what should I work on," not "what's the current state" |
| `/rforge:capture` | Quick task/idea capture mid-session | Session-*interior*, not session-*boundary* |
| `/rforge:complete` | Mark **one task** done + doc cascade | Task-scoped, not session-scoped (no CLAUDE.md sync, no memory capture, no worktree check) |
| `/rforge:init` | Idempotent context init for a package dir | One-time setup, not a recurring open/close pair |

**No naming or purpose collision** — restore/finish sit on a different axis (session
boundary) than the existing ecosystem/task-tracking commands. They compose: `/rforge:restore`
would *read* the same `.STATUS` the ecosystem dashboard aggregates; `/rforge:finish` would be
the thing that *produces* the state `/rforge:next` reasons from — same producer/consumer
relationship craft's own restore/finish/next trio already documents.

## Design

### 1. State source: full `.STATUS` parity (with R-native fallback)

Most R packages have no `.STATUS` file — that convention lives in craft/savant/rforge's own
repos, not in typical CRAN packages. Per your answer, `/rforge:restore` should still **offer
to scaffold one** when absent (mirroring `savant:restore`'s propose-never-auto-write doc
quartet), but the recap itself is always groundable in R-native artifacts that exist
regardless:

- **DESCRIPTION** — `Version`, `Suggests`/`Imports` drift
- **NEWS.md** — presence + contents of an `[Unreleased]`/dev-version header
- **git** — last commit, branch, dirty state, ahead/behind (same primitives `dev/git`
  Op 7 already computes generically)
- **Check/test cache** — rforge already has diff-aware baseline caching
  (`~/.rforge/baseline-cache/`, keyed by repo+merge-base+kind+package) from `lib/changed.py`
  (v2.13.0) — reuse this as the "last r:check/r:test result" surface instead of re-running
  anything. **Read-only, never triggers a check.**
- **`.STATUS`** (if present) — layered on top for `next:`/`blockers:` fields a human curated

### 2. `.STATUS` scaffold shape for R packages

An R package's `.STATUS` should NOT be a verbatim copy of the plugin-repo template (which
has `version:`/`last_release:` fields tuned for a *tool* release cadence). Proposed R-package
shape:

```yaml
package: medfit
updated: 2026-07-31
status: Active
version: 0.4.0          # from DESCRIPTION, read-only mirror — never hand-edited independently
cran_status: not-submitted | on-cran | resubmission-pending
last_check: 2026-07-28 PASS (R 4.5, --as-cran)
last_release: ...       # same free-form dated-entry convention as craft/savant
next: ...
blockers: ...
```

Key difference from the plugin-repo template: `version:` is a **read-only mirror** of
`DESCRIPTION`'s `Version` field (single source of truth already established by rforge's own
`version_sync.py` precedent) — `/rforge:finish` would refuse to hand-edit it independently,
just report drift if `.STATUS` and `DESCRIPTION` disagree.

### 3. Implementation: prompt-command + new `lib/rstatus.py`

Matches rforge's existing convention exactly (no `skills/` directory exists in rforge —
that's a craft/savant-specific mechanism):

```
commands/restore.md   — prompt-command, declarative rules (savant:restore pattern:
                         no generator module, LLM performs the inventory itself)
commands/finish.md    — prompt-command, declarative rules
lib/rstatus.py         — NEW shared module: DESCRIPTION/NEWS.md parsing,
                         check-cache reader (wraps lib/changed.py's cache),
                         .STATUS parse/diff (reuses lib/status.py's
                         parse_status_file, doesn't fork it)
```

`lib/rstatus.py` is deliberately thin — it's a **reader/differ**, not a new check-runner.
It composes existing modules (`lib.changed` for cache, `lib.status.parse_status_file` for
the `.STATUS` grammar, `lib.discovery` if invoked from an ecosystem root) rather than
duplicating their logic — same reuse discipline already documented for `rcmd`/`cranlint`.

### 4. Command naming

Keep **`restore`/`finish`** (not `status`/`complete-session` or similar) — deliberately
matching craft/savant's vocabulary. This is the load-bearing reason: the future re-routing
dispatcher (below) is a **name-based** dispatch (`/restore` routes somewhere), so the
rforge-side target must share the verb, not a synonym. `/rforge:status` and `/rforge:complete`
keep their existing names/scope unchanged — no rename, no deprecation.

### 5. Re-routing detection signal (forward-looking, not built now)

For a future root-level `/restore` (or `/finish`) to hand off to rforge instead of craft's or
savant's generic version, it needs one cheap, false-positive-resistant signal, checked in this
order (first match wins — mirrors savant:restore's own project-type detection precedent):

1. **`DESCRIPTION` file at repo root** — the single authoritative signal an R package exists
   here. Cheapest possible check (`os.path.isfile`), no parsing needed for detection (parsing
   happens only after the route is chosen).
2. **Guard against false positives**: a `DESCRIPTION` file alone doesn't distinguish "this repo
   IS an R package" from "this repo vendors/tests-against one two directories down" — scope the
   check to **repo root only** (or root of the invoked `<path>`), not a recursive scan, so a
   monorepo containing an R package subdirectory doesn't mis-route the whole repo.
3. **Hand-off contract**: the dispatcher passes the resolved `<path>` (defaulting to cwd) and
   nothing else — no shared state, no imported modules — `/rforge:restore`/`finish` re-derive
   everything from that path independently, same "one state read, own module" boundary
   `savant:restore` already enforces for its own project-type detection. This keeps the
   dispatcher itself trivial (a lookup table: DESCRIPTION → rforge, manuscript markers →
   savant, else → craft) and avoids coupling three separate command implementations together.

**Explicitly out of scope for this brainstorm**: building the dispatcher itself. This section
exists so `/rforge:restore`/`finish`'s own argument contract (`[path]` optional, defaults to
cwd) is already shaped to be dispatcher-callable without a later breaking change.

## Risks

- **Duplicating `.STATUS` grammar logic** — mitigated by reusing `lib.status.parse_status_file`
  rather than writing a second parser; if the R-package `.STATUS` shape (§2) needs fields the
  current grammar doesn't have, extend that one parser, don't fork it.
- **Scope creep into ecosystem territory** — `/rforge:restore` must stay single-package-scoped
  (like `savant:restore`), not accidentally re-derive what `/rforge:status`/`/rforge:health`
  already do ecosystem-wide. If invoked from an ecosystem root rather than a single package,
  degrade to "which package?" (same disambiguation `lib.discovery` already does for other
  commands) rather than silently aggregating.
- **`.STATUS` scaffold offered too eagerly** — many CRAN maintainers will never want a
  `.STATUS` file. Keep the offer read-only/declined-by-default, never auto-created, exactly
  as `savant:restore` already treats a missing README.

## Test-plan scaffold

Change shape: **new command + new `lib/rstatus.py` module** → tier `count-cascade dogfood` +
`unit` + `e2e`.

- **unit** (`tests/`) — `lib/rstatus.py`: DESCRIPTION/NEWS.md parsing, `.STATUS` read/diff,
  check-cache reader wrapping. `# TODO(author): delete if not contract-bearing`.
- **e2e** — real invocation of `/rforge:restore` against a throwaway R package fixture (with
  and without an existing `.STATUS`); real invocation of `/rforge:finish` verifying it refuses
  a redundant `updated:` bump with no real content delta (mirrors `savant:restore`'s
  redundant-edit guard test).
- **count-cascade dogfood** — `tests/test-all.sh`'s "commands.md sync-gate" and command-count
  checks (41→43 if both ship together) must be updated; `docs/commands.md` needs both new
  entries.
- **dependency** — N/A, no external dependency changes.
- **integration** — N/A at this stage (no cross-command data flow yet; becomes relevant once
  the re-routing dispatcher consumes these commands' output).

## Documentation scaffold

Per the doc-impact rubric (reuse, not reinvent):

- [x] `docs/commands.md` entries for both (score ≥3 — new commands, always required)
- [x] `docs/guides/` — new "Session Boundary" command-family guide, following the existing
      per-family Command Guide tier (score ≥3 — two new commands is enough for a family page)
- [ ] `docs/reference/rstatus.md` — auto-generated via `scripts/gen_lib_reference.py` once
      `lib/rstatus.py` exists (mechanical, not a manual-authoring decision — N/A for this
      brainstorm, applies automatically per the public-module convention)
- [ ] Tutorial — N/A score <3 at this stage; revisit once the re-routing dispatcher exists and
      there's an actual end-to-end story to walk through

## Recommendation

Build `/rforge:restore` + `/rforge:finish` as prompt-commands backed by a new `lib/rstatus.py`
that composes (never forks) `lib.status.parse_status_file` + `lib.changed`'s cache reader.
Scope `.STATUS` to full parity with the propose-not-auto-scaffold discipline, using the
R-package-shaped fields in §2 rather than the plugin-repo template verbatim. Keep the
`[path]`-only argument contract now so the future re-routing dispatcher (out of scope here)
can call either command without a breaking change later.

## Suggested Next Command

`/rforge:brainstorm` → `save` action to capture this as `docs/specs/SPEC-restore-finish-commands-2026-07-31.md`,
or straight to implementation via a feature worktree (`git worktree add ... -b feature/restore-finish dev`)
following rforge's spec→TDD→adversarial-review→release cadence.

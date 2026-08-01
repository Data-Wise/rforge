# 🔖 Session boundary commands

!!! tip "TL;DR (30 seconds)"
    - **What:** `/rforge:restore` (recap where you left off) and `/rforge:finish` (sync
      `.STATUS` to what actually happened) — a single-package pair, not ecosystem-wide.
    - **Why:** rforge already has ecosystem-wide state commands (`status`, `health`, `next`)
      and task-scoped ones (`capture`, `complete`) — this pair fills the session-*boundary*
      slot craft's and savant's own `restore`/`finish` fill for their repos.
    - **The flow:** `restore` (open, read-only) → do the work → `finish` (close, diff-gated
      write).
    - **Safety:** both are read-only or dry-run by default; `finish --write` only ever
      applies after showing the diff, and never commits.
    - **Next:** [SPEC-restore-finish-commands-2026-07-31.md](https://github.com/Data-Wise/rforge/blob/dev/SPEC-restore-finish-commands-2026-07-31.md)
      for the full design rationale (repo-root working doc, not part of the published docs site).

> **For whom:** an R-package maintainer returning to (or wrapping up) a work session on a
> single package repo — medfit, probmed, medrobust, or any CRAN package using rforge.
> **Prior knowledge:** none beyond `/rforge:init` having been run once on the package.

---

## What this family covers

Two commands, one boundary each:

| Command | Boundary | Default mode | Writes? |
|---|---|---|---|
| `/rforge:restore` | Session open | read-only, always | never |
| `/rforge:finish` | Session close | dry-run | only on `--write`, diff-gated |

Both operate on **one R package repo** at a time — not the ecosystem. If invoked from an
ecosystem root without a `DESCRIPTION` at the target path, they ask which package rather
than aggregating (same disambiguation `/rforge:status`/`/rforge:detect` already use).

## Why this doesn't collide with existing commands

| Existing command | Axis | How it differs from restore/finish |
|---|---|---|
| `/rforge:status` | Ecosystem-wide dashboard | Multi-package; restore/finish are single-package |
| `/rforge:health` | Ecosystem-wide health score | Same breadth axis as status |
| `/rforge:next` | Ecosystem-aware task recommendation | Generates a new suggestion; `restore` only surfaces `.STATUS`'s existing `next:` field verbatim |
| `/rforge:complete` | One task, doc cascade | Task-scoped; `finish` is session-scoped (may span several completed tasks, syncs `.STATUS` wholesale) |

## State sources

`/rforge:restore` grounds its recap in artifacts every R package already has, never assuming
a `.STATUS` file exists:

- **DESCRIPTION** — package name, version, dependencies (via `lib.discovery.read_description`)
- **NEWS.md** — top section only (`## Unreleased` or the latest `## Package X.Y.Z` header),
  same convention `lib.tidyaudit.check_news_header` already established
- **git** — branch, last commit, dirty-tree flag
- **`.STATUS`** (if present) — `next:`/`blockers:`/`cran_status:` layered on top

## The `.STATUS` shape for R packages

Distinct from the plugin-repo `.STATUS` template (which has `version:`/`last_release:`
fields tuned for a *tool's* release cadence):

```yaml
package: medfit
updated: 2026-07-31
status: Active
version: 0.4.0          # read-only mirror of DESCRIPTION's Version — never hand-edited
                         # independently; /rforge:finish flags drift, never reverses it
cran_status: not-submitted | on-cran | resubmission-pending
last_check: 2026-07-28 PASS (R 4.5, --as-cran)
last_release: <free-form dated entry>
next: <free-form>
blockers: <free-form>
```

Never auto-created — both commands only **propose** scaffolding one when absent, and proceed
with the R-native-only recap if declined.

## The redundant-edit guard

`/rforge:finish` refuses to write a `.STATUS` update whose only change is the `updated:`
timestamp — a date bump unbacked by real content is worse than no edit (the same
`doc-update-currency-check` discipline `savant:restore --sync` already encodes). Genuine
content changes (a new `next:`, a resolved `blocker:`, a fresh `last_check:` result) are
required to trigger a write.

## Usage

```bash
# Open a session
/rforge:restore

# ... do the work ...

# Close it out (dry-run first)
/rforge:finish

# Review the diff, then apply
/rforge:finish --write
```

## Related

- [`/rforge:status`](../commands.md) — ecosystem-wide dashboard
- [`/rforge:complete`](../commands.md) — single-task completion + doc cascade
- [`rstatus` API reference](../reference/rstatus.md) — the underlying `lib/rstatus.py` module

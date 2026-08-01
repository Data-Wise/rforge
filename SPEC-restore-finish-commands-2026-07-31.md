# SPEC: `/rforge:restore` + `/rforge:finish` (R-package session boundary commands)

- **Status:** ✅ Implemented and shipped in v2.20.0 (2026-08-01) — PR #71 (feature/restore-finish → dev), PR #72 (dev → main), release https://github.com/Data-Wise/rforge/releases/tag/v2.20.0. See `.STATUS` `last_release` for full detail, including the `apply_updates()` fix added during pre-merge adversarial review.
- **Date:** 2026-07-31
- **Target version:** next minor (v2.20.0 — 42→44 commands)
- **Author:** brainstormed with Claude — see `BRAINSTORM-restore-finish-commands-2026-07-31.md`
- **Branch plan:** `feature/restore-finish` off `dev`

## Summary

Add `/rforge:restore` (session-open recap) and `/rforge:finish` (session-close doc sync) as
rforge-native counterparts to craft's `/craft:restore`/`/craft:finish` and savant's
`/savant:restore`/`/savant:session`. Scoped to run **inside a single R package repo**
(medfit, probmed, medrobust, ...), not the rforge plugin repo itself, and designed so a
future root-level `/restore`/`/finish` dispatcher can detect "this is an R package" (via a
root-level `DESCRIPTION` file) and re-route here instead of to craft's or savant's generic
version. Building that dispatcher is explicitly **out of scope** for this spec.

## Motivation

craft and savant both have a session-boundary pair (open: recap where you left off; close:
sync docs + capture durable state) tailored to their own repo conventions. rforge has neither
— its existing commands (`status`, `health`, `next`, `capture`, `complete`) operate on a
different axis (ecosystem-wide dashboards, single-task capture/completion), not "recap this
one package's state" / "close out this package's session."

Most R packages have no `.STATUS` file (that convention belongs to tool repos like
craft/savant/rforge itself, not to typical CRAN packages), so the recap must be groundable in
R-native artifacts every package already has — `DESCRIPTION`, `NEWS.md`, git, and rforge's
own check/test cache — with `.STATUS` layered on top only where a maintainer has opted in.

## Scope

### In scope

| Item | Notes |
|---|---|
| `commands/restore.md` | Prompt-command (savant:restore pattern — no generator module, declarative rules the LLM executes) |
| `commands/finish.md` | Prompt-command, same pattern |
| `lib/rstatus.py` (new) | Shared reader/differ: `DESCRIPTION`/`NEWS.md` parsing, check-cache reader (wraps `lib.changed`'s cache), `.STATUS` parse/diff (reuses `lib.status.parse_status_file`, does not fork it) |
| R-package `.STATUS` scaffold shape | New field set distinct from the plugin-repo template (see below) — offered, never auto-created |
| `[path]` argument contract | Both commands accept an optional path (default cwd) — shaped so a future dispatcher can call in without a breaking change |

### Out of scope (this spec)

- The root-level `/restore`/`/finish` re-routing dispatcher itself (detection logic only
  *anticipated*, not built)
- Any change to `/rforge:status`, `/rforge:health`, `/rforge:next`, `/rforge:complete` — no
  rename, no behavior change, no deprecation
- Auto-scaffolding `.STATUS`/`README`/`CLAUDE.md` content — always propose, never auto-write
- Ecosystem-wide (multi-package) recap — single-package only; if invoked from an ecosystem
  root, ask "which package?" (reuse `lib.discovery`'s existing disambiguation) rather than
  aggregating

## Duplicate & overlap audit

| Existing command | Overlap risk | Resolution |
|---|---|---|
| `/rforge:status` | Both "report current state" | `status` is ecosystem-wide multi-package; `restore` is single-package session-boundary. No shared code path other than optionally reading the same `.STATUS` file if present. |
| `/rforge:health` | Both read package state | `health` scores across the ecosystem; `restore` recaps one package. Different output shape (score vs. recap). |
| `/rforge:next` | Both could suggest "what's next" | `next` is ecosystem-aware task recommendation (its own algorithm); `restore` only *surfaces* `.STATUS`'s existing `next:` field verbatim — it does not generate a new recommendation. |
| `/rforge:complete` | Both touch `.STATUS`/doc cascade | `complete` marks **one task** done with doc cascade; `finish` is session-scoped (multiple tasks, CLAUDE.md/memory sync, redundant-edit guard) — same relationship craft's `/craft:complete`-equivalent (task marking) has to `/craft:finish` (session close). No forced merge; `finish` may internally note completed tasks but does not replace `complete`'s doc-cascade detection logic — reuse it instead. |

## Architecture

### `lib/rstatus.py` (new, thin reader/differ — no new check-runner)

```
parse_description(pkg_path) -> {version, imports, suggests, ...}   # regex/DCF read, no R subprocess
parse_news_header(pkg_path) -> {has_unreleased, entries: [...]}     # top-of-file parse only
read_check_cache(pkg_path)  -> last check/test result | None        # wraps lib.changed's
                                                                      # baseline-cache reader —
                                                                      # never triggers a new check
read_rstatus(pkg_path)      -> ParsedStatus | None                  # delegates to
                                                                      # lib.status.parse_status_file
diff_rstatus(current, intended) -> [(field, old, new), ...]         # redundant-edit guard:
                                                                      # timestamp-only diffs are
                                                                      # filtered out before writing
```

All four functions are pure-stdlib, read-only, no R subprocess — same tier as `discovery`,
`deps`, `status` (not the `rcmd` tier that shells to `Rscript`).

### R-package `.STATUS` scaffold shape (distinct from the plugin-repo template)

```yaml
package: medfit
updated: 2026-07-31
status: Active
version: 0.4.0          # read-only mirror of DESCRIPTION Version — flagged as drift if they
                         # disagree, never independently hand-edited by /rforge:finish
cran_status: not-submitted | on-cran | resubmission-pending
last_check: 2026-07-28 PASS (R 4.5, --as-cran)
last_release: <free-form dated entry, same convention as craft/savant/rforge's own .STATUS>
next: <mirrors NEWS.md [Unreleased] entries + open GH issues, human-editable>
blockers: <free-form>
```

### `/rforge:restore` flow (prompt-command, no generator module)

1. Detect target: `[path]` arg or cwd. Confirm a `DESCRIPTION` file exists at that root (if
   not, this isn't an R package — bail with guidance, do not guess).
2. Read state once: `parse_description`, `parse_news_header`, `read_check_cache`,
   `read_rstatus` (if `.STATUS` exists), git (last commit, branch, dirty state — same
   primitives `dev/git` Op 7 computes generically, no need to duplicate that logic here since
   it's a direct `git` call, not a skill dependency).
3. Compose recap: version, CRAN status, last check/test result, `next:`/`blockers:` (from
   `.STATUS` if present, otherwise "no `.STATUS` — inferred next steps from NEWS.md
   `[Unreleased]`" as a clearly-labeled fallback, never fabricated).
4. If no `.STATUS`: offer to scaffold one (per the shape above) — propose only, do not write
   without confirmation.
5. Read-only otherwise. No commits, no `.STATUS` writes without an explicit follow-up
   confirmation (mirrors `savant:restore`'s default-read-only / `--sync`-gated-write split,
   but `restore` here has no `--sync` flag of its own — that's `finish`'s job, see below).

### `/rforge:finish` flow (prompt-command, no generator module)

1. Same state read as `restore` (reuse `lib.rstatus`, don't re-derive).
2. Diff intended `.STATUS` update against current via `diff_rstatus` — **redundant-edit
   guard**: a timestamp-only change is skipped, classified "already current" (directly
   reuses the `doc-update-currency-check` discipline `savant:restore` already encodes).
3. Show the diff, confirm before writing (same per-target confirm gate as
   `savant:restore --sync`).
4. Version drift check: if `.STATUS`'s `version:` mirror disagrees with `DESCRIPTION`'s
   actual `Version`, flag it — never auto-correct (DESCRIPTION is the source of truth,
   `.STATUS` follows).
5. Never commits or pushes — leaves staged/working-tree edits + a suggested commit message,
   same invariant every other rforge command and craft/savant's restore/finish already hold.

## Hand-off contract for a future re-routing dispatcher (not built here)

- **Detection signal:** a `DESCRIPTION` file at the resolved `<path>` root (not a recursive
  scan — avoids mis-routing a monorepo that merely vendors an R package subdirectory).
- **Call contract:** dispatcher passes only the resolved `<path>` (default cwd); no shared
  state, no imported modules. `/rforge:restore`/`finish` re-derive everything from that path
  independently.
- This spec's `[path]`-only argument shape (already in scope above) is what makes that future
  call possible without a breaking change — no further action needed now.

## Testing

| Tier | Coverage |
|---|---|
| unit | `lib/rstatus.py`: DESCRIPTION/NEWS.md parsing (valid + malformed), `.STATUS` read/diff via `diff_rstatus`, check-cache reader against `lib.changed`'s existing cache format |
| e2e | Real invocation of `/rforge:restore` against a throwaway R package fixture, with and without an existing `.STATUS`; real invocation of `/rforge:finish` verifying the redundant-edit guard refuses a timestamp-only bump |
| count-cascade dogfood | `tests/test-all.sh` commands.md sync-gate + command-count checks (42→44); `docs/commands.md` entries for both |
| dependency | N/A — no external dependency change |
| integration | N/A at this stage — becomes relevant once the re-routing dispatcher exists |

## Documentation impact

- [x] `docs/commands.md` — two new entries (required, score ≥3 for new commands)
- [x] `docs/guides/` — new "Session Boundary" command-family guide (two new commands = enough
      for a family page, per existing per-family Command Guide tier)
- [ ] `docs/reference/rstatus.md` — auto-generated via `scripts/gen_lib_reference.py` once
      `lib/rstatus.py` exists (mechanical, applies automatically per the public-module
      convention — not a manual decision)
- [ ] Tutorial — deferred; revisit once the re-routing dispatcher exists and there's an
      end-to-end story spanning multiple repos to walk through

## Implementation order

1. `lib/rstatus.py` + unit tests (parse/diff functions, composing `lib.status` + `lib.changed`)
2. `commands/restore.md` (prompt-command) + e2e fixture test
3. `commands/finish.md` (prompt-command) + e2e fixture test (redundant-edit guard)
4. `docs/commands.md` + new guide page + `scripts/gen_lib_reference.py` regen
5. `test-all.sh` count-cascade updates (42→44)
6. Adversarial review pass (per rforge's spec→TDD→adversarial-review→release cadence)

## Open questions / risks

- **`.STATUS` scaffold offered too eagerly** — mitigated by propose-only, decline-by-default,
  matching `savant:restore`'s treatment of a missing README.
- **Duplicating `.STATUS` grammar** — mitigated by extending `lib.status.parse_status_file`
  if the R-package shape needs new fields, never forking a second parser.
- **Naming stability** — `restore`/`finish` chosen deliberately to match craft/savant's
  vocabulary since the future dispatcher's routing is name-based; revisit only if that
  assumption changes before the dispatcher is built.

## Appendix

Full option analysis, expert-question rationale, and the existing-command overlap audit live
in `BRAINSTORM-restore-finish-commands-2026-07-31.md` (same directory).

---
name: rforge:finish
description: Sync a single R package's .STATUS from its current state — diff-gated, never auto-applies
argument-hint: "[path] [--write]"
arguments:
  - name: path
    description: R package directory to close out (defaults to current directory)
    required: false
    type: string
  - name: write
    description: Apply the diffed .STATUS changes. Default is dry-run (shows the diff, writes nothing).
    required: false
    type: boolean
    default: false
---

# /rforge:finish - R Package Session Close

Close out a work session on a single R package repo by syncing `.STATUS` to match its actual
current state — the rforge counterpart to craft's `/craft:finish` and savant's
`/savant:session close`. **Dry-run by default**, same convention as `/rforge:r:use-test`/
`use-package`; `--write` applies only after the diff is shown and confirmed.

## What It Does

1. Reads the same state `/rforge:restore` recaps (`lib.rstatus.build_recap`) — one state
   read, not re-derived.
2. Composes the *intended* `.STATUS` content: bump `updated:` to today, and — **only if you
   have something real to report this session** — update `next:`/`blockers:`/`last_check:`/
   `cran_status:` from what actually happened (new NEWS.md entries, a check/test run you just
   ran, an issue you closed). Never invent a next-step or blocker that wasn't discussed.
3. Diffs current vs. intended via `lib.rstatus.diff_rstatus`.
4. **Redundant-edit guard**: if the diff is a `updated:`-only change (no real content delta),
   report "already current" and stop — do not write a timestamp-only bump. This is the same
   `doc-update-currency-check` discipline `savant:restore --sync` already enforces.
5. **Version-drift check**: if `.STATUS`'s `version:` mirror disagrees with `DESCRIPTION`'s
   actual `Version`, flag it in the diff — `.STATUS`'s `version:` field is corrected to match
   DESCRIPTION (never the reverse; DESCRIPTION is always the source of truth).
6. Show the diff. On `--write`, apply it via the Edit/Write tool after confirmation — never
   silently.

## Usage

```bash
# Dry-run: show what would change, write nothing (default)
/rforge:finish

# Apply after reviewing the diff
/rforge:finish --write

# Close out a specific package
/rforge:finish /path/to/medfit --write
```

Compute the diff via the Python API before presenting it:

```python
from lib.rstatus import build_recap, read_rstatus, RStatus, diff_rstatus

recap = build_recap(path)
current = read_rstatus(path)
intended = RStatus(package=..., updated=today, version=recap["description"]["version"], ...)
changes = diff_rstatus(current, intended)
if not changes:
    print("already current — nothing to sync")
```

## No `.STATUS` found

Same as `/rforge:restore`: **propose** scaffolding one (R-package shape), never auto-create.
If declined, there is nothing to sync — report that and stop.

## Never commits

Leaves the `.STATUS` edit in the working tree (or staged, if the repo's convention stages
docs) and prints a suggested commit message. No commit, no push — matches every other
rforge command's and craft/savant's restore/finish invariant.

## Ecosystem root disambiguation

Same as `/rforge:restore` — single-package only. Ask which package if invoked from an
ecosystem root rather than one.

## Related Commands

- `/rforge:restore` - Session open: reads the same state this command syncs
- `/rforge:complete` - Marks **one task** done with doc cascade; this command is
  session-scoped (may reference completed tasks, but does not replace `complete`'s
  doc-cascade detection — reuse it, don't duplicate it)
- `/rforge:next` - Reads `.STATUS`'s `next:` field this command writes

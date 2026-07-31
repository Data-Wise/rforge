---
name: rforge:restore
description: Recap a single R package's state (DESCRIPTION, NEWS.md, git, .STATUS) — read-only
argument-hint: "[path] [--format text|json]"
arguments:
  - name: path
    description: R package directory to recap (defaults to current directory)
    required: false
    type: string
  - name: format
    description: Output format (text, json)
    required: false
    type: string
    default: "text"
---

# /rforge:restore - R Package Session Recap

Recap where a single R package repo stands — the rforge counterpart to craft's
`/craft:restore` and savant's `/savant:restore`, scoped to one R package instead of a
generic dev repo or research project. **Read-only.** Never writes, never commits.

## What It Does

Runs `lib.rstatus.build_recap` to compose, from one state read:

- **DESCRIPTION** — package name, version, declared dependencies
- **NEWS.md** — top section (`[Unreleased]` or latest version header) + its bullet entries
- **git** — current branch, last commit, dirty-tree flag
- **`.STATUS`** (if present) — `next:`/`blockers:`/`cran_status:` fields, human- or
  `/rforge:finish`-curated
- **Version drift** — flags when `.STATUS`'s `version:` mirror disagrees with
  `DESCRIPTION`'s actual `Version` (DESCRIPTION is always the source of truth)

## Usage

```bash
# Recap the current directory
python3 -m lib.rstatus recap --path .

# Recap a specific package
python3 -m lib.rstatus recap --path /path/to/medfit

# Machine-readable JSON
python3 -m lib.rstatus recap --path . --format json
```

The same logic is importable as a Python API:

```python
from lib.rstatus import build_recap
recap = build_recap(".")
print(recap["version_drift"])
```

## No `.STATUS` found

If the target package has no `.STATUS` file, the recap still runs from R-native artifacts
alone (DESCRIPTION/NEWS.md/git) — most CRAN packages have never adopted this convention, so
its absence is not an error. Additionally, **offer** (never auto-write) to scaffold one using
the R-package shape, distinct from the plugin-repo `.STATUS` template:

```yaml
package: <name>
updated: <today>
status: Active
version: <mirrored from DESCRIPTION, read-only>
cran_status: not-submitted | on-cran | resubmission-pending
last_check: <date> <PASS|FAIL> (<R version>, <flags>)
last_release: <free-form dated entry>
next: <free-form>
blockers: <free-form>
```

Wait for explicit confirmation before writing it. If declined, proceed with the R-native-only
recap and note that no `.STATUS` exists.

## Not an R package

If no `DESCRIPTION` file exists at the target path, `lib.rstatus.build_recap` reports
`is_r_package: false` — bail with that message rather than guessing at a different project
type (that's craft's/savant's job, not this command's).

## Ecosystem root disambiguation

If invoked from an ecosystem root (multiple packages, no single `DESCRIPTION` at the target
path) rather than one package, do **not** silently aggregate — ask which package, the same
disambiguation `/rforge:status`/`/rforge:detect` already use via `lib.discovery`. This command
stays single-package-scoped; `/rforge:status` covers the ecosystem-wide view.

## Use When

- Returning to an R package repo after a break — "where did I leave off?"
- Before starting work, to confirm the current version/CRAN state
- Precedes `/rforge:finish` the way `/craft:restore` precedes `/craft:finish`

## Related Commands

- `/rforge:finish` - Session close: syncs `.STATUS` from the same state this command recaps
- `/rforge:status` - Ecosystem-wide dashboard (multi-package; this command is single-package)
- `/rforge:next` - Ecosystem-aware next-task recommendation (this command only surfaces
  `.STATUS`'s existing `next:` field verbatim, it does not generate a new recommendation)

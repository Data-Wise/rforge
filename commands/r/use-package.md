---
name: rforge:r:use-package
description: Add a declared dependency (Imports vs Suggests, AI-picked) and an @importFrom tag
argument-hint: "<package> [--write] [--force]"
arguments:
  - name: package
    description: The dependency to declare (one per call)
    required: true
    type: string
  - name: write
    description: Apply the change to DESCRIPTION + the @importFrom. Default is dry-run.
    required: false
    type: boolean
    default: false
  - name: force
    description: Reserved for symmetry with the other use-* commands (re-apply even if anchor differs)
    required: false
    type: boolean
    default: false
---

# R Use Package

Declare a single dependency for an **existing** package. The `Imports`-vs-`Suggests` decision
reuses `lib/deps_sync.py`'s usage scan (unconditional `R/` use → **Imports**; tests/vignettes or
guarded only → **Suggests**); the `DESCRIPTION` edit reuses the **same DCF writer** as
`/rforge:r:deps-sync`. For an Imports dep, an `#' @importFrom <pkg> <symbol>` is inserted in the
file that uses it.

**Dry-run by default.** The recommendation + reason is always surfaced so you can override it.

## Usage

```bash
# Dry-run: show the field decision + planned DESCRIPTION/@importFrom edits (default)
python3 -m lib.scaffold package --pkg "<package>" --path "<path>"

# Apply: write DESCRIPTION (deps_sync writer) + insert @importFrom
python3 -m lib.scaffold package --pkg "<package>" --path "<path>" --write
```

The `--force` flag is reserved for symmetry with the other `use-*` commands.

## Imports vs Suggests

| Usage detected | Field | Why |
|---|---|---|
| `pkg::` / `library()` / `@importFrom` in `R/` | **Imports** | runtime dependency — must be present |
| only in `tests/` or `vignettes/`, or `requireNamespace()`-guarded | **Suggests** | optional / dev-time |
| not used yet | **Imports** (stated) | default; re-run intending Suggests if test/vignette-only |

After `--write` on an Imports dep, run `/rforge:r:document` to regenerate `NAMESPACE`.

## Related Commands

- `/rforge:r:deps-sync` — reconcile **all** deps at once (this adds **one named** dep)
- `/rforge:r:document` — regenerate `NAMESPACE` after the `@importFrom` edit
- `/rforge:r:check --strict` — runtime sibling that catches a misclassified Suggests

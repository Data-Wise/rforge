---
name: rforge:r:deps-sync
description: Reconcile DESCRIPTION against actual code usage (missing/unused/misclassified deps)
argument-hint: "[package] [--write]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: write
    description: Apply the unambiguous Imports/Suggests changes to DESCRIPTION (default is report-only)
    required: false
    type: boolean
    default: false
---

# R Dependency Sync

Reconcile a package's `DESCRIPTION` against what its code actually uses. Pure-Python
(`lib/deps_sync.py`) — scans `R/`, `tests/`, `vignettes/` + `NAMESPACE` for namespace usage
(`pkg::`, `library()`, `@importFrom`, …) and compares against `Depends`/`Imports`/`Suggests`.

**Report-only by default.** `--write` applies the *unambiguous* changes; advisory removals are
never auto-applied.

## Process

```bash
# Report (dry-run default)
python3 -m lib.deps_sync --path "<path>" --format json

# Apply unambiguous Imports/Suggests changes
python3 -m lib.deps_sync --path "<path>" --write --format json
```

## Finding classes

| Kind | Meaning | Suggested fix |
|---|---|---|
| `missing` | used in `R/`, undeclared | add to **Imports** |
| `misclassified` | in **Suggests** but used *unconditionally* in `R/` | **move to Imports** (the medfit/MASS class — the static sibling of `r:check --strict`'s noSuggests pass) |
| `missing_suggests` | used only in tests/vignettes (or guarded), undeclared | add to **Suggests** |
| `unused` | declared, no usage found | advisory removal candidate (may be used dynamically — never auto-removed) |

## Output Format

```markdown
## Deps-sync: {package}
### Status: {🟢 in sync / 🟡 {n} findings}
{Group findings by kind; for misclassified, surface the move-to-Imports hint}
### Suggested patch
{add_imports / move_to_imports / add_suggests; remove_candidates as advisory}
{If --write: list applied changes}
```

When a `misclassified` finding fires, surface the hint verbatim: *"A Suggests package is used
unconditionally in R/. Move it to Imports, or guard with `requireNamespace()` in code AND
`skip_if_not_installed()` in tests."*

## Related Commands

- `/rforge:deps` — *inter*-package ecosystem dependency graph (this is *intra*-package)
- `/rforge:r:check --strict` — the runtime sibling: catches a misclassified Suggests at check time
- `/rforge:r:document` — regenerate NAMESPACE after editing `@importFrom` tags

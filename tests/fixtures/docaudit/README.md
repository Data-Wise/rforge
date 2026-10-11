# Fixtures for `lib/docaudit.py`

Read-only excerpts; nothing here is edited by hand except `controls/`.

| Dir | Origin | Role |
|---|---|---|
| `defect/` | medfit `17d976d^` (`DESCRIPTION`, `NAMESPACE`, `man/joint_effects.Rd`, `man/bootstrap_mediation.Rd`, `vignettes/articles/refcard.qmd` lines 60-105) | Known answer: refcard row 13 lists `joint_effects(x, theta)`; formals are `(object, estimates)` |
| `clean/` | the same files at medfit `17d976d` (the fix, PR #133) | Identical except that one row reads `joint_effects(object, estimates)`; must raise no `error` |
| `controls/` | synthetic | Positive controls: variadic arity, partial matching, nested/quoted/commented names, foreign `pkg::fn` |
| `defects.json` | medfit history | The 18-defect recall manifest used by `tests/harness/replay.py` |

The Rd files were created with `git show <ref>:<path>`; the PreToolUse hook blocks Write/Edit on `man/*.Rd`.
`tests/harness/plant.py` mutates a copy of `clean/` to plant defects; the fixtures themselves are never written to.

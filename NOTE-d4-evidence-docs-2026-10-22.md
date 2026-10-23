# Evidence-bounded verification website update

Local docs-only branch `codex/d4-evidence-docs`, based on dev `fe8c8ef`.
The dev checkout has unrelated dirty agent files and was not modified.

`docs/tutorials/r-dev-cycle.md` now explains configured pkgdown destinations,
deterministic subset versus full acceptance, source pinning, saved-result
protection, review omissions, partial-likelihood evidence and separate deployment
authority. This is workflow guidance, not a claim that missingmed T5 is accepted
or that D4 is released. No new command, dependency or generated reference.

User restrictions: no installs, simulations, saved-result changes, push or merge.
Website build/verification results are recorded in the final checkpoint below.

## Verification

Existing `/Users/davood/.venvs/rforge-py315` used; no installs. Full pytest:
920 passed, 4 skipped. Version-sync check passes. Generated-reference check
reports drift in eight pre-existing reference pages; those files were not edited.
Full default strict build cannot finish: the standalone MkDocs runtime lacks
imaging dependencies; the existing rforge runtime loads Cairo with
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` but social cards then need unavailable
fonts.google.com access. No dependency or production config was changed.

A strict offline content preview succeeds using inherited config with only the
social-card plugin omitted in a scratch config. Verified the actual output at
`/private/tmp/rforge-evidence-docs.m9eD08/preview/tutorials/r-dev-cycle/index.html`:
90040 bytes, seven h2 sections, edited heading/admonition/authorization text present.
This is content inspection, not visual browser inspection or full social-card
verification. No deployment, push or merge. Existing dev dirty work preserved.

Wrap-up validation: `tests/test-all.sh` passed 46/47 checks; the only failure is
the same eight pre-existing generated-reference drift pages listed above.

# SPEC: pkgdown deploy from a clean ref + stray-root-`.md` guard

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-21
- **Target version:** v2.16.0
- **Author:** brainstormed with Claude, grounded in `PROPOSAL-pkgdown-deploy-cleantree-guard.md` (rforge root)
- **Related:** GitHub issue [#52](https://github.com/Data-Wise/rforge/issues/52), [commands/r/site.md](../../commands/r/site.md)

## Summary

`r:site` builds + previews the pkgdown site but has no deploy path, so users fall back to
manual `pkgdown::deploy_to_branch("gh-pages")` — which builds the **working directory** and
publishes untracked/uncommitted root `.md` files (pkgdown renders *every* root `.md`, not
just README/NEWS). Add `r:site --deploy` that builds from a **clean ref** (`git archive HEAD`
into a temp dir), making it structurally impossible to leak untracked files, plus a standalone
**preflight lint** (`--check-leaks`) that flags stray root `.md` — catching *tracked* scratch
docs too. No new command (41 stays 41); two new flags on `r:site` + one new `lib.rcmd` path.

## Motivation

Observed in the wild (medrobust, 2026-06-21): a scratch `PLAN-website-enhancements-*.md` in
the package root was rendered to `.html` and force-pushed to public `gh-pages` by a manual
`deploy_to_branch()`. Two failure modes:

1. **Manual deploy** builds the working dir → publishes **untracked/uncommitted** root files.
2. **CI deploy** builds the committed tree → publishes any **tracked** scratch doc in root
   (`PLAN-*.md`, `ISSUE-*.md`, `START-HERE-*.md`).

`.Rbuildignore` does **not** gate pkgdown (common wrong assumption — it only affects
`R CMD build`). rforge owns the R-package site lifecycle via `r:site`; deploy + guardrails
are the missing piece.

## Goals

- A first-class deploy path that cannot publish untracked/uncommitted files (clean-ref build).
- A standalone, deploy-free leak detector usable at build time (catches tracked scratch docs).
- A documented gotcha in `commands/r/site.md` so the failure mode is discoverable.

## Non-goals

- **Branch-protecting `gh-pages`** (proposal item #6) — out of band; a repo-admin / GitHub
  policy concern, not plugin tooling.
- **Auto-moving scratch docs** into a gitignored subdir — that's a per-consumer convention
  (documented as a hint), not something rforge mutates.
- **Re-implementing pkgdown deploy mechanics** — we delegate to `pkgdown::deploy_to_branch()`,
  only changing *what tree* it runs against and *what we check first*.

## Scope

### In scope (decided)

| Kind | Surface | Engine | Tier |
|------|---------|--------|------|
| deploy | `r:site --deploy` | `pkgdown` (via `lib.rcmd` site path) | mutating + network (recommend-only; never auto-run) |
| lint | `r:site --check-leaks` | pure-Python (`git`/stdlib, no R) | read-only advisory |
| docs | `commands/r/site.md` callout | — | — |

### Out of scope (YAGNI / deferred)

- `gh-pages` branch protection (#6) — repo policy, not tooling.
- A general "publishable-files preview" beyond root `.md` — start with the proven leak class.

## Architecture

- **Leak detector** (new, pure-stdlib, no R): a function that lists root-level `*.md` not in
  an allowlist (`README`, `NEWS`, `LICENSE`, `LICENCE`, `CHANGELOG`, plus `index.md`) and
  cross-references `git status --porcelain` to tag each as `tracked` / `untracked` /
  `modified`. Emits the standard advisory envelope. Lives alongside the analysis modules
  (candidate: extend `lib/cranlint.py` or a small new `lib/sitelint.py` — decide in review).
- **Clean-ref deploy**: `r:site --deploy` runs the site `--kind` path in `lib.rcmd` against a
  throwaway checkout produced by `git archive HEAD | tar -x` (or `git worktree add` at HEAD),
  not the working dir. Runs the leak detector first; aborts on a non-allowlisted **tracked**
  root `.md` (since clean-ref can't see untracked ones — those are now structurally excluded)
  and prints a "files pkgdown will publish" preview requiring confirmation.
- **Safety boundary**: `--deploy` is a mutating + network kind → orchestrator/agent must
  **recommend, never auto-run** (consistent with the SAFE_AUTORUN taxonomy in
  `reference_rforge_lib_envelopes`). `--check-leaks` is read-only → auto-runnable.

## Dependencies

- `pkgdown` (already optional for `r:site`; same `_guard("pkgdown", …)` + 🟡 degrade).
- `git` (assumed present; the leak detector degrades to "git unavailable → skip status tags,
  still lint by filename" if `git` is absent).
- No new R packages.

## Error handling

- `--deploy` with a dirty/leak-prone tree → `blocked` envelope listing the offending root
  `.md` files + hint ("move scratch docs to a gitignored subdir, or commit them").
- `pkgdown` missing → existing `engine_missing` 🟡 path, unchanged.
- `git archive` failure (e.g. not a git repo) → `warn`, fall back to refusing deploy with a
  clear message (never silently deploy the working dir).

## Testing

- `lib/` pytest: leak detector — allowlist hits, tracked vs untracked vs modified tagging,
  git-absent degrade, `index.md` allowed, case-insensitive `LICENCE`.
- Fixture: a temp pkg dir with `README.md` + `PLAN-scratch.md` (tracked) + an untracked
  `NOTES.md`; assert detector flags both non-allowlisted files with correct status tags.
- `tests/test-all.sh`: CLI smoke for `--check-leaks`; command-doc sync for the two new flags.
- Both gates green (`python3 -m pytest tests/`, `bash tests/test-all.sh`).

## Documentation impact

- `commands/r/site.md` — frontmatter (`--deploy`, `--check-leaks` in `arguments:` +
  `argument-hint`) and a `!!! warning` callout on the leak gotcha.
- `CHANGELOG.md` `[Unreleased]`, `.STATUS`, CLAUDE.md test-gate counts.
- Auto-gen reference (`scripts/gen_lib_reference.py`) if a new `lib/sitelint.py` is added.
- `docs/guides/*` site-family guide + REFCARD flag list.

## Implementation order

1. (docs-only, on `dev`) `commands/r/site.md` gotcha callout — immediate, no code.
2. (worktree) Leak detector module + pytest fixtures.
3. (worktree) Wire `--check-leaks` into `r:site` (read-only, auto-runnable).
4. (worktree) `--deploy` clean-ref path in `lib.rcmd` + leak-gate + confirm preview.
5. (worktree) Doc surfaces, version bump, reference regen, CHANGELOG/.STATUS.
6. Pre-release adversarial review (per [[feedback_adversarial_review_prose_contracts]]).

## Open questions / risks

- **New `lib/sitelint.py` vs extend `lib/cranlint.py`?** Leak detection is site-lifecycle, not
  CRAN; a dedicated module keeps `cranlint` focused. Resolve in review.
- **`git archive` vs `git worktree add` for the clean ref?** `archive|tar` is lighter and
  needs no cleanup; `worktree` preserves submodules/`.git`. Lean `archive` unless pkgdown
  needs git metadata. Resolve in review.
- **Behavior change:** none for existing flags — `--deploy`/`--check-leaks` are additive.

## Sources

- [pkgdown — Deploy to GitHub Pages (`deploy_to_branch`)](https://pkgdown.r-lib.org/reference/deploy_to_branch.html)
- [Writing R Extensions §1.3.6 — `.Rbuildignore` scope (build only)](https://cran.r-project.org/doc/manuals/r-release/R-exts.html)
- `PROPOSAL-pkgdown-deploy-cleantree-guard.md` (rforge root — driving writeup)

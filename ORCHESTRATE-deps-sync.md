# ORCHESTRATE: `r:deps-sync` (v2.5.0)

> Working artifact for the `feature/r-deps-sync` worktree. Delete on merge to `dev`.
> **Authoritative spec:** [`docs/specs/SPEC-r-deps-sync-2026-06-10.md`](docs/specs/SPEC-r-deps-sync-2026-06-10.md)
> (Status: Draft, placement locked) — read it first; this is the execution checklist.

- **Branch:** `feature/r-deps-sync` (off `dev` @ 51e6973)
- **Target:** v2.5.0
- **Start:** a **fresh session in this worktree** (`cd` here, then `claude`). Do not implement from the main-repo session.

## Phase 0 — decisions already locked (spec Open Questions)

- ✅ **Module placement** — new `lib/deps_sync.py` (pure-stdlib, like `discovery`/`cranlint`).
  `lib/deps.py` is the *inter*-package graph (478 lines); deps-sync is *intra*-package.
- ⚠️ Still open (decide during impl, low-stakes): guarded-usage detection fidelity; `--write`
  DESCRIPTION formatting; Remotes hint when no manifest present.
- 🆕 **Remotes hint is now feasible** — ecosystem-manifest (v2.4.0) is **merged to dev**, so
  `lib/discovery.py` exposes `Package.manifest` (with `cran:`); deps-sync can consult it to decide
  "needs `Remotes:`". Degrade gracefully when no manifest is configured.

## Phase 1 — scanner (`lib/deps_sync.py`, pure-Python)

- [ ] Scan `R/*.R` for `pkg::`/`pkg:::`, `library(pkg)`, `require(pkg)`, `requireNamespace("pkg")`,
  `loadNamespace`, and roxygen `@importFrom pkg fn` / `@import pkg`. Track **guarded vs
  unconditional** use in `R/`.
- [ ] Scan `NAMESPACE` (`importFrom`/`import`) and `tests/`, `vignettes/` (usage here → `Suggests`).
- [ ] Reuse `lib/discovery.py:parse_description` for the DESCRIPTION fields
  (`Depends`/`Imports`/`Suggests`/`LinkingTo`/`Remotes`).

## Phase 2 — reconcile + classify

- [ ] Emit findings: **missing** (used in `R/`, undeclared → Imports), **missing-suggests**
  (tests/vignettes only), **unused** (declared, no usage — advisory), **misclassified**
  (`Suggests` used unconditionally in `R/` → Imports — the static sibling of cran-incoming's
  noSuggests catch; cross-reference it).
- [ ] Remotes hint: a used pkg neither on CRAN nor base/recommended → flag; consult the ecosystem
  manifest's `cran:` field when present, else "verify origin".

## Phase 3 — patch + CLI

- [ ] Suggested-DESCRIPTION-patch builder; **report-only by default**, `--write` applies
  **unambiguous** changes only (ambiguous ones listed for the user); `--dry-run` default.
- [ ] `commands/r/deps-sync.md` (`arguments:` for `--write`/`--dry-run`).

## Phase 4 — tests (both gates)

- [ ] `python3 -m pytest tests/` — fixtures: missing; **misclassified (the cran-incoming class)**
  with guarded NOT flagged; missing-suggests; unused; patch + `--write` (unambiguous only);
  no-DESCRIPTION/unparseable → warn not raise.
- [ ] `bash tests/test-all.sh` — keep green; add `deps_sync` to `gen_lib_reference.py` public list
  → new `docs/reference/deps_sync.md`; reference-in-sync gate must pass.

## Phase 5 — docs sweep + version

- [ ] Frontmatter `commands/r/deps-sync.md`; help/hub: `docs/commands.md` (Dependency section next
  to `r:deps`/`impact`), `docs/REFCARD.md`, `docs/index.md`/`docs/README.md` (counts 33→34, trees),
  root `README.md`, `docs/lib-modules.md` (+ `deps_sync` row + `docs/reference/deps_sync.md`).
- [ ] `CHANGELOG.md` `[Unreleased]`; `.STATUS`; **v2.5.0 version sync** across the 4 sources +
  live-version doc refs. `test-all.sh` "all 4 version sources agree" must pass.

## Done criteria

- [ ] Both gates green; the misclassified-Suggests fixture proves the static catch.
- [ ] Full doc sweep; v2.5.0 synced.
- [ ] Ready to integrate to `dev` (PR); delete this ORCHESTRATE file as merge cleanup.

# SPEC: CRAN-submission suite — `r:cran-prep` + revdep / goodpractice / multi-platform

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-01
- **Target version:** v2.2.0 (bumps the parked Phase 4 "agents" work to v2.3.0)
- **Author:** brainstormed with Claude, grounded in `RESEARCH-cran-dev-2026-06-01.md`
- **Branch plan:** `feature/r-cran-prep` off `dev`

## Summary

Close rforge's "CRAN last-mile" gap. v2.1.0 covers the local dev cycle
(build/test/check/coverage/site + quality) but has almost nothing for the
*submission* phase. This spec adds a per-package **`r:cran-prep` orchestrator**
plus the sub-commands it sequences, all on the existing `lib/rcmd.py` envelope:

- **`r:cran-prep`** — gate orchestrator (hybrid failure handling) that runs the
  full pre-submission sequence, generates `cran-comments.md`, and emits a
  machine-readable readiness verdict for handoff to `/rforge:release`.
- **`r:revdep`** — reverse-dependency check (`revdepcheck`).
- **`r:goodpractice`** — advisory best-practice bundle (`goodpractice::gp()`), opt-in.
- **`r:winbuilder`** — dispatch to win-builder (`devtools::check_win_devel()`).
- **`r:rhub`** — dispatch to R-hub v2 (GitHub-Actions-based).
- **`r:check` enhancement** — classify CRAN NOTEs as expected-spurious vs real.

Commands 28 → **33** (+5 new; `r:check` enhanced, not new).

## Motivation

Per `RESEARCH-cran-dev-2026-06-01.md` (gap table): the CRAN bar is
**0 errors / 0 warnings / 0 notes** under `R CMD check --as-cran`, with surviving
NOTEs justified in `cran-comments.md`, plus reverse-dependency obligations and
multi-platform pre-checks. rforge currently provides none of: `cran-comments`
(#14), revdepcheck (#15), win-builder/R-hub (#16–18), NOTE classification (#1),
or a per-package submission orchestrator (#21). `/rforge:release` plans
*cross-package* submission ordering — orthogonal to per-package readiness.

## Scope

### In scope (decided)

| Kind | Command | Engine | Tier |
|------|---------|--------|------|
| `cran-prep` | `/rforge:r:cran-prep` | orchestrator — reuses `run()` per stage | **gate** |
| `revdep` | `/rforge:r:revdep` | `revdepcheck::revdep_check()` | gate (structured) |
| `goodpractice` | `/rforge:r:goodpractice` | `goodpractice::gp()` | advisory (opt-in) |
| `winbuilder` | `/rforge:r:winbuilder` | `devtools::check_win_devel()` *(see note)* | dispatch (async) |
| `rhub` | `/rforge:r:rhub` | R-hub v2 `rhub_setup`/`rhub_doctor`/`rhub_check` | dispatch (GH Actions) |
| — | `/rforge:r:check` (enhanced) | classify NOTEs spurious-vs-real | — |

> **`winbuilder` engine note:** `devtools::check_win_devel()` is the documented
> path but pulls in devtools. To honor the "no devtools" rule, prefer the
> lower-level equivalent if one exists; otherwise `winbuilder` MAY depend on
> devtools as an **optional** engine (degrade to 🟡 + install hint), since it is
> a single dispatch command, not core. Implementer verifies at build time.

### Out of scope (YAGNI / deferred)

- **`r:macbuilder`** — R-hub v2's macOS-arm64 platform + win-builder cover the
  gap; standalone mac-builder wrapper is marginal.
- **CI-matrix scaffolder** — overlaps craft's `ci:generate`/`ci:detect`;
  document "use `usethis::use_github_action('check-standard')` or craft CI".
- **NEWS-polish command** — `docs:check` + `complete` cascade partially cover;
  low ROI vs. submission gaps.
- **A standalone `r:cran-comments` command** — `cran-comments.md` is generated
  *within* `r:cran-prep` (and regenerable by re-running it); no separate
  top-level command, to avoid command sprawl.

## Architecture (extend `lib/rcmd.py`, do not duplicate)

All new behavior reuses the v2.1.0 envelope pattern: an R `kind` snippet emits
JSON via `jsonlite`; `lib/rcmd.py` normalizes to the common envelope; the
`commands/r/*.md` prompt renders it. New code paths:

### 1. New `kind`s in `r_snippet()` / `run()`

- **`revdep`** — `revdepcheck::revdep_check(num_workers=4)`; serialize the
  `revdep/` summary (broken[], new_problems[], failures[]) to JSON. One-time
  `usethis::use_revdep()` if `revdep/` config absent (idempotent). Status:
  `error` if broken downstream packages, `warn` if new problems, `ok` if clean.
  Gate behind "has CRAN downstream deps" detection to avoid noise for new pkgs
  (if none, return `ok` with a "no reverse dependencies" message).
- **`goodpractice`** — `goodpractice::gp()`; serialize the checks list. Status:
  always `warn` if any advisory items, else `ok` (never `error` — advisory).
  **Opt-in only** (not run by `cran-prep` unless `--goodpractice`); never run
  inside `r:cycle`.
- **`winbuilder`** — dispatch `check_win_devel()`; returns no parseable result
  (emailed). New status **`dispatched`**. Envelope notes "results emailed to the
  DESCRIPTION maintainer; check inbox."
- **`rhub`** — R-hub v2: ensure `rhub_setup()` (writes `.github/workflows/rhub.yaml`,
  idempotent) → `rhub_doctor()` (validate) → `rhub_check()` (dispatch). Returns
  the GitHub Actions run URL. Status **`dispatched`**; envelope includes the run
  link. For non-GitHub packages, note `rhub::rc_submit()` fallback.

### 2. `r:check` NOTE classification (enhancement)

In `normalize()` for `kind == "check"`, tag each NOTE. A `SPURIOUS_NOTE_PATTERNS`
list (regex) marks expected NOTEs:
`New submission`, `Days since last update`, `checking CRAN incoming feasibility`,
`Possibly misspelled words in DESCRIPTION`, `installed size is`. Envelope gains:

```jsonc
"check": {
  "errors": [], "warnings": [],
  "notes": ["..."],                 // unchanged (all notes)
  "notes_classified": [             // NEW
    {"text": "New submission", "kind": "spurious", "reason": "expected on first submission"},
    {"text": "...", "kind": "real"}
  ]
}
```

Drives the `cran-comments` justification stubs and a clearer report
("2 NOTEs: 1 expected, 1 needs attention").

### 3. New status value: `dispatched`

Extend the status vocabulary (currently `ok`/`warn`/`error`) with `dispatched`
(🚀) for async commands (`winbuilder`, `rhub`) whose work completes elsewhere.
`main()` returns exit 0 for `dispatched` (not a failure). `_status_for` returns
`dispatched` for those kinds on successful launch.

### 4. `cran-prep` orchestrator (`_run_cran_prep`, like `_run_cycle`)

Hybrid failure handling — **stop at first hard ERROR; continue through
WARN/NOTE/advisory collecting them.** Reuses `run()` for every existing stage
(no reimplementation):

```
r:cran-prep <pkg>  [--goodpractice] [--multi-platform] [--no-revdep]
  1. run("document")                 # Rd/NAMESPACE current
  2. run("lint")  + run("style", check-only)   # advisory
  3. run("spell")
  4. run("urlcheck")                 # surface url_update() hint
  5. run("test")                     # hard ERROR stops here
  6. run("coverage")                 # advisory
  7. run("check", as_cran=True)      # THE gate; hard ERROR/WARNING stops; NOTEs classified
  8. run("revdep")          unless --no-revdep or no downstream deps
  9. run("goodpractice")    only if --goodpractice          [advisory]
 10. winbuilder + rhub      only if --multi-platform        [dispatched]
 11. generate cran-comments.md  (counts + classified-NOTE stubs + revdep/cran.md)
 12. version-bump advisory (reuse description-sync skill signal)
  ── emit readiness envelope ──
```

**Readiness envelope** (the handoff contract to `/rforge:release`):

```jsonc
{
  "kind": "cran-prep", "package": "foo", "version": "0.2.0",
  "status": "ready" | "blocked" | "warn",
  "stages": [{"kind": "check", "status": "ok"}, ...],
  "blockers": ["test failed: ...", "1 real NOTE: ..."],
  "open_notes": [{"text": "...", "kind": "spurious"}],
  "cran_comments_path": "cran-comments.md",
  "dispatched": ["winbuilder", "rhub"],     // async work in flight
  "handoff": "ready for /rforge:release ecosystem sequencing"
}
```

`status: "ready"` only when no ERRORs, no WARNINGs, and no *real* NOTEs remain.

### 5. New command files

`commands/r/{cran-prep,revdep,goodpractice,winbuilder,rhub}.md`, each mirroring
the v2.1.0 command-file shape (frontmatter + `## Process` calling
`python3 -m lib.rcmd --kind <kind>` + `## Output Format` + `## Related Commands`).
Retrofit `commands/r/check.md` output format to show classified NOTEs.

## Duplicate & overlap audit (avoid redundancy)

Audited against the 28 v2.1.0 commands on 2026-06-01.

**Name collisions:** none (`cran-prep`/`revdep`/`goodpractice`/`winbuilder`/`rhub`
are all new under `r:`). `tests/test-all.sh` command-name-uniqueness must stay green.

**Functional boundaries (compose, do NOT reimplement):**

| New | Could overlap | Boundary |
|-----|---------------|----------|
| `r:cran-prep` | `r:cycle`, `r:check`, `/rforge:release` | cran-prep = **single-package CRAN gate** that *calls* the others; `r:cycle` = quick dev loop (doc→test→check); `release` = **cross-package** submission ordering. cran-prep emits per-package verdicts that `release` consumes. They compose. |
| `r:revdep` | `deps`, `impact`, `release` | revdep = **CRAN downstream** reverse-deps (external); `deps`/`impact`/`release` = **internal ecosystem** edges. Orthogonal. |
| `r:goodpractice` | `r:check`, `r:lint`, `r:coverage` | gp re-runs check+lint+covr → **opt-in only**, never inside `r:cycle`/`cran-prep`-default; documented as "advisory bundle, expect overlap." |
| `cran-comments` (artifact) | `/rforge:release` | a generated *file*, not a command; release doesn't generate it. |
| `r:winbuilder`/`r:rhub` | `r:check` | local check ≠ multi-platform remote check. No overlap. |

**Internal DRY rules:** `_run_cran_prep` MUST call `run("<kind>")` for each
existing stage — never inline their snippets. All `r:` commands keep routing
through the single `lib/rcmd.py`. The NOTE classifier lives once in `normalize`.

## Dependencies

Confirmed installed (R 4.6.0): `rcmdcheck`, `pkgbuild`, `roxygen2`, `testthat`,
`pkgload`, `covr`, `pkgdown`, `lintr`, `urlchecker`, `styler`, `spelling`, `jsonlite`.

- **New required engines (optional, command-specific — degrade to 🟡 + hint):**
  `revdepcheck` (r:revdep), `goodpractice` (r:goodpractice), `rhub` (r:rhub).
  `devtools` is acceptable **only** as an optional engine for `r:winbuilder`
  (single dispatch command) if no lower-level path exists — never for the gate.
- **System:** `pandoc` (already noted for `r:site`); a GitHub remote for `r:rhub` v2.

## Error handling

- **Optional engine missing** → 🟡 + `install.packages("<pkg>")` hint via
  `engine_missing[]` (same pattern as covr/pkgdown).
- **`revdep` with no downstream deps** → `ok` + "no reverse dependencies" (not an error).
- **`cran-prep` hard ERROR** (test fail, R CMD check error/warning) → stop,
  `status: "blocked"`, name the failing stage in `blockers[]`.
- **Async dispatch** (`winbuilder`/`rhub`) → `dispatched`; never block on results;
  envelope tells the user where to look.
- **Not a package / no DESCRIPTION** → fail fast → pointer to `/rforge:detect`.

## Testing

Both gates must pass; CI stays R-free (mock `Rscript` / inject fixtures):

- **`tests/test_rcmd.py`** additions (~20 cases): each new `kind`'s snippet
  string-asserted; `normalize` for revdep/goodpractice/dispatched; the NOTE
  classifier (spurious vs real); `_run_cran_prep` sequencing + hybrid early-stop
  (mock `run()` to fail at `check` → assert `blocked` + stages collected);
  `dispatched` status → exit 0; readiness-envelope shape.
- **`tests/test-all.sh`**: new command files covered by frontmatter/uniqueness/
  skills gates; extend the `lib.rcmd` smoke to a `cran-prep` dry path.
- **lib reference**: `gen_lib_reference.py --check` stays green (rcmd already a
  public module; new functions documented).
- **Live sanity (pre-release, needs R):** run `r:revdep`/`r:goodpractice` against
  a real package; confirm `winbuilder`/`rhub` dispatch + return links. (This is
  the lesson from v2.1.0 — string-only tests can't catch R-serialization bugs.)

## Documentation impact (per directive — full docs in this spec)

- **5 new `commands/r/*.md`** + retrofit `commands/r/check.md` (classified NOTEs).
- **`docs/reference/rcmd.md`** — regenerate (new functions).
- **`docs/lib-modules.md`** — extend the `rcmd` row/notes for the new kinds +
  the `dispatched` status; note the gate-vs-dispatch-vs-advisory tiers.
- **New tutorial** `docs/tutorials/cran-submission-with-rforge.md` — end-to-end:
  `r:cran-prep` → fix → re-run → multi-platform → `cran-comments.md` → handoff to
  `/rforge:release`. Add to `mkdocs.yml` nav (Learn section) + tutorials/README.
- **Command tables + counts** 28 → **33**: README.md, docs/index.md,
  docs/REFCARD.md, docs/commands.md (+ a "CRAN submission" group), QUICK-START
  if it lists counts.
- **`docs/index.md`** "What's new in v2.2.0" section.
- **CHANGELOG** `[Unreleased]` → `## [2.2.0]`.
- **4-source version bump** (plugin.json, marketplace.json ×2, package.json) +
  live-version doc refs per CLAUDE.md; tap manifest + `Formula/rforge.rb` regen
  on release (28→33 in desc/caveat).
- **`CLAUDE.md`** current-state refresh (v2.2.0, 33 commands, new kinds, backlog).
- **`.STATUS`** + this spec status → Shipped on release.

## Implementation order (for the plan)

1. `dispatched` status + `_status_for`/`main` exit handling (+ tests).
2. NOTE classifier in `normalize` for `check` (+ tests); retrofit `check.md`.
3. `revdep` kind + command (+ tests).
4. `goodpractice` kind + command (opt-in) (+ tests).
5. `winbuilder` + `rhub` kinds + commands (dispatch) (+ tests).
6. `cran-comments.md` generator (consumes check+revdep envelopes).
7. `_run_cran_prep` orchestrator + `cran-prep` command (+ sequencing/early-stop tests).
8. Docs: reference regen, lib-modules, new tutorial, tables, nav, CHANGELOG, counts.
9. Version bump (4 sources + doc refs) + `.STATUS`.
10. Both gates green; live R sanity on the new kinds; PR `feature/r-cran-prep` → `dev`.

## Open questions / risks

- **`winbuilder` + devtools:** if no devtools-free path exists, it carries an
  optional devtools dep — acceptable for one dispatch command; flagged for the
  implementer to confirm.
- **`rhub` v2 requires a GitHub remote + one-time `rhub_setup`** committing a
  workflow file — `r:rhub` should detect/offer this, not silently commit.
- **`revdep` is slow** (builds downstream pkgs) — document the runtime; keep it
  opt-out (`--no-revdep`) and auto-skip when no downstream deps.

## Appendix: source

Grounded in `docs/specs/RESEARCH-cran-dev-2026-06-01.md` (CRAN policy,
r-pkgs.org Releasing-to-CRAN, R-hub v2, revdepcheck, testthat 3e, goodpractice;
full citations there).

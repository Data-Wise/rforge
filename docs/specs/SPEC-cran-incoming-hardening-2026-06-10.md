# SPEC: CRAN-incoming hardening for rforge `check` / `cran-prep`

- **Status:** Reviewed — approved (2026-06-10); ready for implementation
- **Date:** 2026-06-10
- **Target version:** v2.3.0 (minor — carries a behavior change; bumps parked Phase 4 "agents" work accordingly)
- **Author:** brainstormed with Claude, grounded in `RESEARCH-cran-incoming-checks-2026-06-10.md`
- **Related:** [RESEARCH-cran-incoming-checks-2026-06-10.md](RESEARCH-cran-incoming-checks-2026-06-10.md),
  [SPEC-r-cran-prep-2026-06-01.md](SPEC-r-cran-prep-2026-06-01.md)
- **Supersedes:** `PROPOSAL-cran-incoming-hardening-2026-06-10.md` (promoted to this SPEC)

## Summary

Make rforge's submission gate emulate CRAN's *incoming* and *ongoing* (post-acceptance)
checks, so the error classes that "only CRAN submission detects" are caught locally.
Today the `check` stage runs only `rcmdcheck(args=c("--as-cran"))`
([`lib/rcmd.py:233`](../../lib/rcmd.py)); this spec adds, behind a `strict` flavor:
`--run-donttest`, a **noSuggests** pass (`_R_CHECK_DEPENDS_ONLY_=true`), a
**suggests-only** pass (`_R_CHECK_SUGGESTS_ONLY_=true`), and an opt-in `--incoming`
`_R_CHECK_*` bundle. The strict passes run **by default in `cran-prep` and block the
`ready` verdict on failure.** It also adds three pure-Python (no-R) checks that emulate
CRAN's *metadata + structure* scrutiny: a **DESCRIPTION linter** (incoming nits the local
`--as-cran` run misses), a **build-hygiene scan** that flags planning/dev docs which would
ship in the tarball (CRAN's "non-standard top-level files" NOTE) with the exact
`.Rbuildignore` fix, and an **advisory planning-doc consistency** check. No new commands;
`r:check` and `r:cran-prep` gain flags.

## Motivation

A **medfit 0.2.1** bug — `MASS::mvrnorm` (a `Suggests` package) used unconditionally in a
default code path — passed `--as-cran` but would fail CRAN's post-acceptance noSuggests
flavor (full case + citations in `RESEARCH-cran-incoming-checks-2026-06-10.md`, "The
triggering case" and §A.1). rforge's `cran-prep` gate runs only `--as-cran`, so it can
report 🟢 `ready` on a package CRAN will bounce. Per Writing R Extensions, the fix is to
check **with each** of the two Suggests-withholding flavors and with neither — the gate
should do all three.

## Goals

- Catch a `Suggests` package used unconditionally **before** submission (the medfit class).
- Catch undeclared-package use (the `SUGGESTS_ONLY` class).
- Run `\donttest{}` examples and verify the PDF manual builds.
- Optionally emulate CRAN's incoming-only `_R_CHECK_*` bundle (`--incoming`).
- Catch DESCRIPTION incoming nits (non-`Authors@R`, weak `Title`, `Description` prose, stale
  `Date`) that a local `--as-cran` run does not reliably flag.
- Catch planning/dev docs that would ship in the tarball (CRAN's "non-standard top-level
  files" NOTE) **before** R does, with the exact `.Rbuildignore` fix attached.
- Keep the in-repo planning surface honest (advisory staleness/dangling-ref check).
- Keep `cran-prep`'s `ready` verdict trustworthy: a strict failure blocks it.

## Non-goals

- **No new top-level commands.** This enhances `r:check` and `r:cran-prep` only.
- **No `devtools` dependency for the gate.** Strict passes use `rcmdcheck`'s `env=` arg
  (the "no devtools for gate commands" rule from `SPEC-r-cran-prep` still holds).
- **Not** reimplementing the full CRAN incoming machine (e.g. cross-reference against the
  live CRAN package DB, archival policy). `--incoming` covers the env-var flavors only.
- **No change to the subprocess layer** (`_invoke_r`) — env rides through `rcmdcheck(env=)`.
- **No auto-fixing.** The DESCRIPTION linter and build-hygiene scan *report + hint* (the exact
  `.Rbuildignore` regex, the field to fix); they do not edit `DESCRIPTION` or `.Rbuildignore`.
- **Planning-doc consistency (4c) is rforge-internal hygiene, not a CRAN requirement** — it is
  advisory and never blocks the `ready` verdict.

## Scope

### In scope (decided)

| Tier | Behavior | Mechanism | Default in `cran-prep`? |
|---|---|---|---|
| 1a | run `\donttest{}` examples | `args += "--run-donttest"` (on each strict pass) | yes (part of strict) |
| 1b | verify PDF manual builds; warn (not skip) if no LaTeX | inspect rcmdcheck manual output | yes (warn only) |
| 2a | **noSuggests** pass | `env=c("_R_CHECK_DEPENDS_ONLY_"="true")` | **yes — blocks `ready`** |
| 2b | **suggests-only** pass | `env=c("_R_CHECK_SUGGESTS_ONLY_"="true")` | **yes — blocks `ready`** |
| 3 | incoming-only `_R_CHECK_*` bundle | `--incoming` → `env=c(...)` | **no — opt-in** |
| 4a | DESCRIPTION linter — incoming nits | pure-Python DCF parse (no R) | yes (advisory/warn) |
| 4b | build-hygiene scan — non-`.Rbuildignore`d planning docs | pure-Python: top-level entries vs `.Rbuildignore` | yes (warn + fix hint) |
| 4c | planning-doc consistency | reuse `docs:check` staleness/dangling-ref logic | yes (advisory — never blocks) |

**Command surface (decided):**

- **`r:check`** (no flag) — unchanged: a single `--as-cran` pass.
- **`r:check --strict`** — runs **both** flavor passes (Tier 2a + 2b) as two distinct stage
  rows, each with `--run-donttest` (Tier 1a) — the same set `cran-prep` runs by default. One
  mental model across both commands. (Cost: ≈ 2× check time; see Open questions.)
- **`r:check --incoming`** (implies `--strict`) — adds the Tier 3 bundle as a third row.
- **`r:cran-prep`** — runs the Tier 2 strict passes (and Tier 1a/1b, Tier 4) **by default**;
  `--incoming` adds Tier 3.

Stage rows surface as distinct entries: `check`, `check (noSuggests)`,
`check (suggests-only)`, (when `--incoming`) `check (incoming)`, plus `description`,
`build-hygiene`, and `docs-consistency`.

> **DESCRIPTION — what's new vs already covered.** The *hard* DESCRIPTION failures
> (invalid `License`, missing mandatory fields, malformed `Description`) already surface
> through `rcmdcheck` in the `check` stage; 4a adds the *incoming style* nits that a local
> `--as-cran` run does **not** reliably flag (non-`Authors@R` with no `cph`, weak/echoed
> `Title`, `Description` not a complete sentence, stale `Date`) and classifies the hard ones
> with actionable hints. See RESEARCH §A.5.
>
> **Build hygiene — what's new vs already covered.** R CMD check's "non-standard top-level
> files" NOTE already flows through and classifies as `real` (so it already blocks via the
> real-NOTE path). 4b is the *proactive* half: scan **before** running R and emit the exact
> `.Rbuildignore` regex (`usethis::use_build_ignore()` equivalent) for each planning/dev doc
> that would ship. See RESEARCH §A.6.

### Out of scope (YAGNI / deferred)

- **`--incoming` per-variable set is not finalized here.** Each candidate
  (`_R_CHECK_S3_REGISTRATION_`, `_R_CHECK_LENGTH_1_CONDITION_`, partial-match vars) must
  be confirmed against R Internals §8 during implementation (RESEARCH §A.2); vars already
  implied by `--as-cran` (e.g. `_R_CHECK_RD_VALIDATE_RD2HTML_`) are **excluded**.
- **Refusing `ready` until win-builder/R-hub dispatched** (RESEARCH gap #7) — desirable but
  deferred; tracked as a follow-up so this spec stays a single focused change.

## Architecture

All changes in [`lib/rcmd.py`](../../lib/rcmd.py); the `strict` kwarg already exists on
`r_snippet`/`run` (used for `site`) and `--strict` is already an argparse flag.

- **`r_snippet(kind="check", …)`** ([`lib/rcmd.py:233`](../../lib/rcmd.py)) — extend with a
  flavor selector (e.g. `flavor: str | None` ∈ `{None,"depends","suggests"}` and
  `incoming: bool`). Build `args` (`--as-cran` [+ `--run-donttest`] when strict) and an
  `env=` named vector for the flavor / incoming bundle, threaded into the existing
  `rcmdcheck(...)` call inside the `_guard("rcmdcheck", …)` wrapper. See RESEARCH §A.4 for
  the exact `rcmdcheck(args=, env=)` shape.
- **`run("check", …)`** ([`lib/rcmd.py:362`](../../lib/rcmd.py)) — already threads kwargs to
  `r_snippet`; pass the new flavor/incoming through. **No `_invoke_r` change.** `flavor` is an
  *internal* selector, not a user-facing flag: `--strict` drives a **loop over both flavors**
  (`"depends"` then `"suggests"`), each emitting its own stage row. The single combined path is
  rejected (it would conflate two distinct bug classes — see review).
- **`_run_cran_prep()`** ([`lib/rcmd.py:440`](../../lib/rcmd.py)) — after the existing
  `check` stage ([line 462](../../lib/rcmd.py)) and its real-NOTE blocker (467–470), run the
  two strict flavors (`--run-donttest` + each env). On `error`, append a blocker:
  `"noSuggests/donttest check failed (Suggests used unconditionally?)"`. Accept an
  `incoming=` param and add the bundle stage when set. Thread `ns.strict`/`ns.incoming`
  from argparse into `_run_cran_prep(...)` ([the missing link at lines 530–535](../../lib/rcmd.py)).
- **Failure hint** — when a strict flavor errors, surface: *"A Suggests package is used
  unconditionally. Move it to Imports, or guard with `requireNamespace()` in code AND
  `skip_if_not_installed()` in tests."*

The metadata + structure checks (Tier 4) are **pure-Python, no R** — they fit rforge's
analysis-module convention (stdlib-only, like `discovery`/`deps`/`status`), *not* `rcmd`
(which shells to R). Proposed home: a new `lib/cranlint.py` module (public → needs a
`docs/reference/cranlint.md` page generated by `scripts/gen_lib_reference.py`; final
placement vs folding into an existing module is an implementation decision):

- **`lint_description(path)`** — parse the DESCRIPTION DCF (stdlib `email.parser`/manual DCF
  read) and emit advisory findings per RESEARCH §A.5 (Authors@R, Title, Description prose,
  Date). Returns rows in the standard envelope shape so `cran-prep` can render them.
- **`check_build_hygiene(path)`** — list top-level entries, compile `.Rbuildignore` lines as
  case-insensitive regexes (matching R's `tools:::.Rbuildignore` semantics, RESEARCH §A.6),
  and report planning/dev docs that match neither — each with the `.Rbuildignore` regex to add.
- **Consistency (4c)** — reuse the existing `docs:check` staleness/dangling-ref logic rather
  than reimplementing; invoke it as an advisory stage. (Confirm the reusable entry point
  during implementation.)

`_run_cran_prep` calls these after the check passes; 4a/4b are `warn`-level (advisory) and
do **not** block `ready` on their own — but 4b's findings correspond to a real R CMD check
NOTE, so the same issue still blocks via the existing real-NOTE path once R runs. 4c never blocks.

## Dependencies

- **`rcmdcheck`** — already the engine; uses its existing `env=` argument (RESEARCH §A.4).
  No new packages. No `devtools`.
- **Tier 4 checks** — pure Python stdlib (DCF parse, dir scan, regex). **No R, no new deps.**

## Error handling

- New stage statuses reuse the existing vocab (`ok`/`warn`/`error`); strict flavors that
  `error` become `cran-prep` **blockers** → verdict `blocked`/`warn`, never `ready`.
- The manual-build check emits `warn` (not `error`) when LaTeX is absent.
- `--incoming` failures: same blocker treatment **only** when `--incoming` is explicitly
  requested (it is opt-in, so it never silently flips a default-green package).
- **Tier 4** findings are `warn`-level and **advisory** — they never directly flip
  `ready` → `blocked`. (Build-hygiene issues still block indirectly, via the real R CMD check
  NOTE.) A missing/unparseable `DESCRIPTION` or `.Rbuildignore` degrades the relevant Tier 4
  stage to `warn` with a clear reason, never an unhandled error.

## Testing

Both gates must pass (`python3 -m pytest tests/` and `bash tests/test-all.sh`):

- **Snippet generation** — assert `r_snippet("check", flavor="depends", strict=True)`
  produces `args` containing `--run-donttest` and `env=c("_R_CHECK_DEPENDS_ONLY_"="true")`;
  likewise `flavor="suggests"` → `_R_CHECK_SUGGESTS_ONLY_`.
- **`cran-prep` blocking** — mock `_invoke_r` so a strict flavor returns `error`; assert
  `_run_cran_prep` appends the blocker and the verdict is not `ready`.
- **No-regression** — a clean package (all flavors `ok`) still reaches `ready`.
- **Regression fixture (the proof)** — point the strict gate at **medfit 0.2.1 before** the
  MASS fix → `check (noSuggests)` must FAIL; **after** the fix → must PASS. Confirm
  `--run-donttest` flags a deliberately broken `\donttest{}` example.
- **DESCRIPTION linter** — fixtures with (a) `Author`/`Maintainer` but no `Authors@R`,
  (b) a `Description` with no trailing period, (c) a clean `Authors@R` DESCRIPTION → assert
  the right advisory rows fire / none fire.
- **Build-hygiene scan** — fixture package dir containing `specs/`, `BRAINSTORM.md`, `.STATUS`
  with a `.Rbuildignore` that ignores only some → assert the un-ignored ones are flagged with
  a suggested regex, and ignored/standard entries are not.
- **Tier 4 never hard-fails** — assert advisory rows don't flip `ready`; missing DESCRIPTION
  degrades to `warn`, not an exception.
- If `rcmd`'s (or the new module's) public surface changes, regenerate the affected
  `docs/reference/*.md` (`scripts/gen_lib_reference.py`) so the CI `--check` gate stays green.

## Documentation impact

Per the rforge "typical doc update scope" rule, treat this as a full sweep — `grep -r` for
`cran-prep` / `r:check` and update every surface. Three groups:

**1. Command frontmatter (machine-readable spec):**

- **`commands/r/check.md`** — add `--strict` and `--incoming` to the `arguments:` frontmatter
  and `## Usage` (keep the array and prose in sync); document the two-row behavior.
- **`commands/r/cran-prep.md`** — update the documented stage sequence to include the default
  `check (noSuggests)` + `check (suggests-only)` passes, opt-in `check (incoming)`, and the
  Tier 4 `description` / `build-hygiene` / `docs-consistency` stages; add the `--incoming` arg.

**2. Help / hub / reference docs (user-facing discovery):**

- **`docs/commands.md`** — the command **hub**: extend the CRAN Submission section with the new
  flags, the strict stage rows, and the Tier 4 checks.
- **`docs/REFCARD.md`** — the quick-reference **help** card: update the CRAN SUBMISSION box with
  `--strict` / `--incoming` and the new stages (mind the ASCII box width + the live version ref).
- **`docs/index.md`** and **`docs/README.md`** — hub landing pages: refresh any command counts /
  "what rforge does" CRAN bullets and the version-tagged tree diagrams.
- **`README.md`** (repo root) — command list + tree-diagram comments showing the version.
- **`docs/quickstart.md`** / **`docs/QUICK-START.md`** — if they show a CRAN-prep walkthrough,
  note the strict default.
- **`docs/lib-modules.md`** — add `cranlint` to the module overview (and the auto-generated
  **`docs/reference/cranlint.md`** if `lib/cranlint.py` lands public — register it in
  `scripts/gen_lib_reference.py`).
- **`docs/tutorials/cran-release-prep.md`** — note the strict passes + Tier 4 in the walkthrough.

**3. Project trackers:**

- **`CHANGELOG.md`** — `[Unreleased]`, flagging the **behavior change** (packages green today may
  turn red once Suggests misuse is detected).
- **`.STATUS`** — link this SPEC; move the item out of backlog when shipped.

> All four version-sync surfaces (`plugin.json`, `marketplace.json` ×2, `package.json`) and the
> live-version doc refs (REFCARD/README/index headers) bump to **v2.3.0** at release per CLAUDE.md.

## Implementation order

1. *(docs, this session — DONE)* convention templates + README standard; this SPEC + its
   RESEARCH companion on `dev`.
2. *(code — feature worktree, fresh session)* `r_snippet` flavor/env + `--run-donttest`.
3. Thread flavor/incoming through `run()` and into `_run_cran_prep()`; insert strict stages.
4. Failure hint + manual-build warn.
5. `--incoming` bundle — **confirm each `_R_CHECK_*` var against R Internals §8 first**.
6. Tier 4: `lib/cranlint.py` — `lint_description()` + `check_build_hygiene()` (pure-Python);
   wire both into `_run_cran_prep` as advisory stages.
7. Tier 4c: wire the existing `docs:check` consistency logic in as an advisory stage.
8. Tests (both gates) incl. the medfit regression fixture and the Tier 4 fixtures.
9. Full doc sweep (Documentation impact): command frontmatter; **help/hub/reference** —
   `commands.md`, `REFCARD.md`, `index.md`/`README.md` hubs, `lib-modules.md` + new
   `cranlint.md`, quickstart, tutorial; then CHANGELOG, `.STATUS`, and the v2.3.0 version-sync.

> **Branch note:** steps 2–7 touch `lib/rcmd.py` (code) and must run in a
> `feature/cran-incoming` worktree off `dev`, in a new session — not on `dev`.

## Open questions / risks

- **Behavior change.** ✅ *Resolved:* lands in **v2.3.0 (minor)** with a clear CHANGELOG note —
  default-on strict passes can turn a currently-🟢 package 🔴, which is intended but not
  patch-safe.
- **`r:check --strict` semantics.** ✅ *Resolved:* runs **both** flavor passes (two rows) +
  donttest — the same set `cran-prep` runs. `flavor` stays internal; no per-flavor CLI flag.
- **`--run-donttest` scope.** ✅ *Resolved (intentional):* donttest rides the two restricted
  flavor passes, not the unrestricted baseline `check`. A donttest example that needs a
  Suggests package unconditionally *should* fail the noSuggests pass — coupling is correct.
- **`--incoming` scope.** The exact variable set is deferred to per-variable confirmation
  (RESEARCH §A.2). Risk: asserting a var/default that isn't actually documented — mitigated
  by the "confirm against R Internals §8 before coding" gate in step 5.
- **Strict-pass runtime.** `cran-prep` now runs the baseline + two strict passes ≈ 3× check
  time (4× with `--incoming`). Acceptable for a submission gate; note it so users aren't surprised.
- **Tier 4 module placement.** New `lib/cranlint.py` vs folding into an existing analysis
  module — decide during implementation; affects whether a `docs/reference/cranlint.md` page
  is generated. *Resolution needed.*
- **`docs:check` reuse (4c).** Confirm `docs:check` exposes a reusable, importable entry point
  for the consistency logic; if it's prompt-only, extract the core into `lib/` first.

## Sources

- [Writing R Extensions — CRAN](https://cran.r-project.org/doc/manuals/r-release/R-exts.html)
- [R Internals §8 "Tools" — CRAN](https://cran.r-project.org/doc/manuals/r-release/R-ints.html)
- [rcmdcheck::rcmdcheck() reference](https://rdrr.io/cran/rcmdcheck/man/rcmdcheck.html)
- [CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html) — Authors@R, License standard form
- [r-pkgs §3 Package structure](https://r-pkgs.org/structure.html), [Appendix A — R CMD check](https://r-pkgs.org/R-CMD-check.html) — top-level files, `.Rbuildignore` regex semantics
- Companion: [`RESEARCH-cran-incoming-checks-2026-06-10.md`](RESEARCH-cran-incoming-checks-2026-06-10.md)

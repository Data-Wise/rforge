# RESEARCH: CRAN incoming + ongoing checks (2026) vs rforge v2.2.0 `check`/`cran-prep`

> **Type:** Research + recommendations (no code, no spec). Feeds
> [`SPEC-cran-incoming-hardening-2026-06-10.md`](SPEC-cran-incoming-hardening-2026-06-10.md);
> that spec references this doc instead of re-deriving the claims below.
> **Date:** 2026-06-10
> **Scope:** Why `R CMD check --as-cran` (what rforge's `check` stage runs today,
> [`lib/rcmd.py:233`](../../lib/rcmd.py)) does not catch the full set of errors CRAN's
> *incoming* and *ongoing* (post-acceptance) checks catch, and exactly which flags/env
> vars close the gap. Triggered by a **medfit 0.2.1** near-miss (below). The first
> worked example of the repo's [Research & Citation Standard](README.md#research--citation-standard).

---

## The triggering case

While fixing CRAN round-2 feedback for **medfit 0.2.1**, a strict local check
(`_R_CHECK_DEPENDS_ONLY_=true` + `--run-donttest`) caught a latent bug that
`R CMD check --as-cran` did not: a *default* parametric-bootstrap path
(`R/bootstrap.R:250`, `MASS::mvrnorm`) hard-requires **MASS**, which sits in
`Suggests`. 13 tests error when MASS is absent. `--as-cran` installs Suggests, so
the bug passes `--as-cran` and the win-builder pretest — but **fails CRAN's
post-acceptance "noSuggests" flavor**, producing a "please fix" email weeks later.
rforge's submission gate (`/rforge:r:cran-prep`) runs only `--as-cran`, so it shares
the blind spot.

> **Citation correction (recorded per the standard):** an earlier draft of the
> hardening proposal named `_R_CHECK_SUGGESTS_ONLY_=true` as the catcher. That is the
> wrong flavor — see A.1. The catcher is `_R_CHECK_DEPENDS_ONLY_=true`.

---

## PART A — Current (2026) state of CRAN check flavors

### A.1 The two Suggests-withholding flavors

`R CMD check` can be run with a restricted set of packages on the library path, via
two distinct environment variables ([Writing R Extensions §"Checking packages"](https://cran.r-project.org/doc/manuals/r-release/R-exts.html)):

- **`_R_CHECK_DEPENDS_ONLY_=true`** — only packages in `Depends` and `Imports` (and
  their recursive dependencies) are available. **`Suggests` is withheld.** This is the
  flavor that flags a `Suggests` package used *unconditionally* — i.e. the medfit/MASS
  bug. It approximates CRAN's post-acceptance "noSuggests" flavor.
- **`_R_CHECK_SUGGESTS_ONLY_=true`** — `Depends` + `Imports` + `Suggests` are available,
  but **not** `Enhances`, and **not** packages absent from `DESCRIPTION`. This flavor
  catches use of *undeclared* packages — a different bug class than DEPENDS_ONLY.

WRE explicitly recommends: *"a package is checked with each of these set, as well as
with neither."* So the rigorous gate runs **both** flavors plus the ordinary
`--as-cran` pass — they are complementary, not redundant.

| Flavor | On the lib path | Catches |
|---|---|---|
| `--as-cran` (no env) | Depends + Imports + Suggests + Enhances | baseline CRAN checks |
| `_R_CHECK_DEPENDS_ONLY_=true` | Depends + Imports only | **Suggests used unconditionally** (medfit/MASS) |
| `_R_CHECK_SUGGESTS_ONLY_=true` | Depends + Imports + Suggests | **undeclared** package use |

### A.2 The `_R_CHECK_*` "incoming" env bundle

`R CMD check --as-cran` already turns on a large set of `_R_CHECK_*` variables; CRAN's
incoming/r-devel machine turns on a few *more*. The authoritative per-variable reference
is [R Internals §8 "Tools"](https://cran.r-project.org/doc/manuals/r-release/R-ints.html).
Two confirmed examples that frame the split:

- **`_R_CHECK_RD_VALIDATE_RD2HTML_`** — HTML (Rd) validation. **Already enabled by
  `--as-cran`** (setting it false *overrides* `--as-cran` to turn validation off). So it
  is **not** part of the incoming-only bundle.
- **`_R_CHECK_S3_REGISTRATION_`** — reports already-registered S3 methods in
  base/recommended packages overwritten on namespace load. Documented as "false by
  default but true for CRAN submission checks."

**Consequence for the spec:** the Tier 3 `--incoming` bundle must contain **only the
incoming-only extras not already implied by `--as-cran`.** Blindly setting a list
(e.g. the candidate set `_R_CHECK_S3_REGISTRATION_`, `_R_CHECK_LENGTH_1_CONDITION_`,
partial-match warnings) risks (a) re-setting vars `--as-cran` already owns, or (b)
asserting behavior not actually documented. Each candidate variable below is
**marked for per-variable confirmation against R Internals §8 during implementation**
(Deliverable D) — they are *not* yet verified individually in this pass.

| Candidate var | Purpose (claimed) | Status |
|---|---|---|
| `_R_CHECK_S3_REGISTRATION_` | overwritten base/recommended S3 methods | ⚠️ documented true-for-submission; confirm whether `--as-cran` already sets it |
| `_R_CHECK_LENGTH_1_CONDITION_` | `if`/`while` given length > 1 condition | ⚠️ confirm name + default vs `--as-cran` |
| partial-match warnings (`_R_CHECK_*PARTIAL*`) | `$`/`[[` partial matching, arg partial match | ⚠️ confirm exact var names |
| `_R_CHECK_RD_VALIDATE_RD2HTML_` | Rd→HTML validation | ✅ already on under `--as-cran` — **exclude** from bundle |

### A.3 `--run-donttest`, manual, and vignettes

- **`\donttest{}` examples** are *not run* by a plain `--as-cran` check; `--run-donttest`
  forces them to execute, surfacing breakage CRAN catches on incoming
  ([Writing R Extensions](https://cran.r-project.org/doc/manuals/r-release/R-exts.html)).
  This is a pure addition to the `args` vector.
- **PDF reference manual** builds during check only when a LaTeX toolchain is present;
  CRAN always builds it. Locally, absence of LaTeX should be a *warning* ("rely on
  win-builder"), not a silent skip.
- **Vignettes** are built by `--as-cran` unless `--no-build-vignettes` is passed; the gate
  must not suppress them.

### A.4 Implementation mechanism — `rcmdcheck`'s `env=` argument

`rcmdcheck::rcmdcheck()` accepts **`env`** — *"A named character vector, extra environment
variables to set in the check process"* — alongside `args`, `build_args`, and `error_on`
([rcmdcheck reference](https://rdrr.io/cran/rcmdcheck/man/rcmdcheck.html)). So the flavors
are applied directly:

```r
rcmdcheck::rcmdcheck(path,
  args = c("--as-cran", "--run-donttest"),
  env  = c("_R_CHECK_DEPENDS_ONLY_" = "true"),
  quiet = TRUE, error_on = "never")
```

**No change to rforge's subprocess layer** (`_invoke_r`, [`lib/rcmd.py:343`](../../lib/rcmd.py),
which calls `subprocess.run([rscript,"-e",snippet])` with no `env=`) is required — the env
vars ride through `rcmdcheck`'s own argument into the child check process.

### A.5 DESCRIPTION meta-information (incoming)

`R CMD check` runs "checking DESCRIPTION meta-information"; CRAN's incoming-feasibility pass
applies stricter, human-adjacent scrutiny to the same file
([CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html),
[r-pkgs §22 Releasing to CRAN](https://r-pkgs.org/release.html),
[Writing R Extensions §"The DESCRIPTION file"](https://cran.r-project.org/doc/manuals/r-release/R-exts.html)):

- **`License`** must be in a *standard form* so `R CMD check` and CRAN can verify it
  automatically; a license stub that is invalid DCF is flagged. (R CMD check catches the
  hard cases; a non-canonical-but-parseable license can still draw an incoming NOTE.)
- **`Authors@R`** is recommended over `Author`/`Maintainer`; its absence draws a CRAN
  incoming-feasibility NOTE, and it should name a copyright holder (`cph` role) and exactly
  one maintainer (`cre`) with an email.
- **`Description`** must be one or more *complete sentences*; malformed/stub Descriptions
  (and "This package…"/title-echo openings) are flagged.
- **`Title`** — title case, concise, no trailing period, no redundant "A package to…".
  Title + Description are the prime targets of CRAN's human review.

**Split, like the env flavors:** the hard failures (invalid `License`, missing mandatory
fields, malformed `Description`) already surface through `rcmdcheck` → the existing `check`
stage. The *style/incoming* nits (non-`Authors@R`, weak `Title`, missing trailing period,
stale `Date`) are **not** reliably caught by a local `--as-cran` run — they are a good fit
for a small **pure-Python DCF linter** on rforge's side (the DESCRIPTION file is DCF; no R
needed), run as an **advisory** stage.

### A.6 Non-standard top-level files & `.Rbuildignore` (build hygiene)

"Only specified files and directories are allowed at the top level of the package" (e.g.
`DESCRIPTION`, `R/`, `man/`, `src/`, `tests/`, `vignettes/`). Anything else — planning/spec
docs, `BRAINSTORM*`, `ROADMAP`, `TODO`, `.STATUS`, dev notes — triggers R CMD check's
"checking top-level files" **NOTE** unless it is either listed in `.Rbuildignore` or moved
to `inst/` ([r-pkgs §3 Package structure](https://r-pkgs.org/structure.html),
[r-pkgs Appendix A — R CMD check](https://r-pkgs.org/R-CMD-check.html)).

- `.Rbuildignore` lines are **case-insensitive Perl-compatible regexes** matched against
  each file path; matching paths are excluded from the built bundle (and so never reach
  CRAN). The canonical helper is `usethis::use_build_ignore()`.
- rforge develops packages that *also* carry planning artifacts in-repo, so this is a live
  risk for the ecosystem: a spec doc left un-ignored ships in the tarball and draws the NOTE.

**rforge's leverage:** the NOTE itself flows through the existing `check` stage (and the
note classifier defaults unknown notes to `real`, so it already contributes to the
real-NOTE blocker). The *additive* value is a **proactive, pre-R, pure-Python scan** —
list top-level entries, match them against `.Rbuildignore`, and flag the planning docs that
would ship, with the exact `.Rbuildignore` regex to add. Catch it before R does, with the fix attached.

### A.7 Planning-doc consistency (orthogonal to the build)

Separately from CRAN: planning/spec docs that are *not* part of the R build can still rot
(stale status, dangling spec cross-references). rforge already has `docs:check`-style
staleness/dangling-reference logic; running it as an **advisory** alongside the CRAN gate
keeps the in-repo planning surface honest. This is rforge-internal hygiene, not a CRAN
requirement — so it never blocks the `ready` verdict.

---

## PART B — Gap analysis vs rforge v2.2.0

Current `check` stage: `rcmdcheck(args=c("--as-cran"))`, no `env`, no `--run-donttest`
([`lib/rcmd.py:233`](../../lib/rcmd.py)). `cran-prep` runs that single check at
[`lib/rcmd.py:462`](../../lib/rcmd.py). ✅ covered · ⚠️ partial · ❌ missing.

| # | CRAN check behavior | rforge today | Status | Closes the gap |
|---|---|---|---|---|
| 1 | `\donttest{}` examples run | `--as-cran` only | ❌ | add `--run-donttest` to `args` |
| 2 | noSuggests flavor (Suggests withheld) | never run | ❌ | `env=c("_R_CHECK_DEPENDS_ONLY_"="true")` |
| 3 | undeclared-package flavor | never run | ❌ | `env=c("_R_CHECK_SUGGESTS_ONLY_"="true")` |
| 4 | incoming-only `_R_CHECK_*` bundle | never set | ❌ | `--incoming` env bundle (per-var, A.2) |
| 5 | PDF manual builds | only if local TeX, unverified | ⚠️ | force; warn if no LaTeX |
| 6 | vignettes build under check | built by `--as-cran` | ✅ | confirm not `--no-build-vignettes` |
| 7 | R-devel cross-platform | win-builder/R-hub dispatchable | ⚠️ | nudge harder pre-`ready` |
| 8 | DESCRIPTION spelling, URL/DOI | `spell` + `urlcheck` stages | ✅ | already covered |
| 9 | reverse deps | `revdep` stage | ✅ | already covered |
| 10 | DESCRIPTION hard checks (License, mandatory fields) | via `rcmdcheck` | ⚠️ | surfaced but not classified/hinted |
| 11 | DESCRIPTION incoming nits (Authors@R, Title, Description prose, Date) | not run locally | ❌ | pure-Python DCF linter (advisory) |
| 12 | non-standard top-level files | NOTE via `rcmdcheck` (classified `real`) | ⚠️ | add proactive `.Rbuildignore` scan + fix hint |
| 13 | planning-doc consistency (staleness, dangling refs) | `docs:check` exists, not in gate | ❌ | run `docs:check` logic as advisory |

The two highest-value, lowest-cost wins are **#1 (`--run-donttest`)** and **#2
(DEPENDS_ONLY)** — both pure additions, no new dependencies.

---

## PART C — Prioritized recommendations (feed the SPEC)

### Quick wins
- Add `--run-donttest` to the check `args` when `as_cran` (gap #1).
- Add a `check (noSuggests)` stage via `env=c("_R_CHECK_DEPENDS_ONLY_"="true")` (gap #2)
  — the single change that converts the medfit near-miss into a permanent guardrail.

### Medium
- Add a `check (suggests-only)` stage via `_R_CHECK_SUGGESTS_ONLY_=true` (gap #3), so the
  gate matches the WRE "check with each" recommendation.
- Verify the PDF manual builds; warn (not skip) when LaTeX is absent (gap #5).
- On any strict failure, surface the targeted hint: *"A Suggests package is used
  unconditionally. Move it to Imports, or guard with `requireNamespace()` in code AND
  `skip_if_not_installed()` in tests."*
- **Build-hygiene scan** (gaps #12): pre-R, pure-Python — flag planning/dev docs at the
  package top level that aren't `.Rbuildignore`d, with the exact regex to add (gap #12).
- **DESCRIPTION linter** (gap #11): pure-Python DCF parse — advisory NOTEs for non-`Authors@R`,
  weak `Title`, `Description` not ending in a complete sentence, stale `Date`; classify the
  hard DESCRIPTION findings already surfaced by `rcmdcheck` (gap #10).

### Long-term
- `--incoming`: add the incoming-only `_R_CHECK_*` bundle (gap #4) — **only after**
  confirming each variable per A.2 against R Internals §8.
- Refuse a 🟢 `ready` verdict in `cran-prep` until win-builder/R-hub have at least been
  *dispatched* (gap #7).
- **Planning-doc consistency** (gap #13): run `docs:check`-style staleness/dangling-ref
  logic as an advisory stage (never blocks).

---

## Sources

- [Writing R Extensions — CRAN](https://cran.r-project.org/doc/manuals/r-release/R-exts.html) — the two Suggests-withholding flavors and the "check with each, and with neither" recommendation; `--run-donttest`; manual/vignette build behavior.
- [R Internals §8 "Tools" — CRAN](https://cran.r-project.org/doc/manuals/r-release/R-ints.html) — authoritative per-variable reference for `_R_CHECK_*`; `_R_CHECK_RD_VALIDATE_RD2HTML_` (on under `--as-cran`), `_R_CHECK_S3_REGISTRATION_` (true for submission checks).
- [rcmdcheck::rcmdcheck() reference](https://rdrr.io/cran/rcmdcheck/man/rcmdcheck.html) — the `env=` named-character-vector argument.
- [CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html) — `Authors@R`/`cph`, `License` standard form, DESCRIPTION expectations.
- [r-pkgs §3 Package structure](https://r-pkgs.org/structure.html) and [Appendix A — R CMD check](https://r-pkgs.org/R-CMD-check.html) — top-level files allowed, `.Rbuildignore` regex semantics, `usethis::use_build_ignore()`.
- [r-pkgs §22 Releasing to CRAN](https://r-pkgs.org/release.html) — DESCRIPTION incoming nits (Title/Description hotspots, Authors@R).
- Existing rforge docs: [`RESEARCH-cran-dev-2026-06-01.md`](RESEARCH-cran-dev-2026-06-01.md), [`SPEC-r-cran-prep-2026-06-01.md`](SPEC-r-cran-prep-2026-06-01.md).

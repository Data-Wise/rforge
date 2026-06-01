# SPEC: R Package Dev-Cycle Commands (`r:` namespace)

- **Status:** Draft — awaiting user review
- **Date:** 2026-05-31
- **Target version:** v2.1.0 (bumps the parked Phase 4 "agents" work to v2.2.0)
- **Author:** brainstormed with Claude (research-backed, see Appendix)
- **Branch plan:** `feature/r-dev-commands` off `dev`

## Summary

Bring R package **build, test, and website-building** capabilities into the
rforge plugin as Claude-Code-native slash commands, mirroring the daily R
development loop offered by flow-cli's `r` dispatcher (`r build`, `r test`,
`r pkgdown`, ...). rforge already ships one such command — `/rforge:r:check`
(R CMD check with smart output parsing). This spec extends the existing `r:`
namespace into a full dev cycle and factors the output-handling logic into a
single shared, testable `lib/rcmd.py` module.

The value-add over the instant ZSH `r` dispatcher is **AI-assisted,
structured output**: each command runs R via a subprocess that emits JSON
(not free text), which is rendered into a consistent ADHD-optimized report
(status dot, errors/warnings/notes counts, test pass/fail, coverage %, next
actions).

## Motivation

The "package building capabilities of the defunct rforge-mcp" the user wants
back were never in rforge-mcp itself — the MCP only did ecosystem discovery,
deps, status, init, cascade, release planning, and ideation. The literal R
dev workflow (build/test/document/install/pkgdown) lives in flow-cli's `r`
dispatcher (`lib/dispatchers/r-dispatcher.zsh`, ~25 actions).

The user wants those actions available **inside Claude Code**, ecosystem-aware
and with parsed output, the way `/rforge:r:check` already works.

## Scope

### In scope (decided)

| Command            | R engine (direct, not via devtools)                    | Notes |
|--------------------|--------------------------------------------------------|-------|
| `/rforge:r:load`     | `pkgload::load_all()`                                | Mirrors `devtools::load_all`; simulate-install into namespace. Report exit status |
| `/rforge:r:build`    | `pkgbuild::build()`                                  | Returns tarball path string; report path + size |
| `/rforge:r:test`     | `testthat::test_local(load_package="source", reporter="list")` | **Self-loads** via `pkgload::load_all()` (no separate load step); `as.data.frame()` → pass/fail/skip/warn + failing files |
| `/rforge:r:document` | `roxygen2::roxygenize()`                             | Regenerates `man/*.Rd` + `NAMESPACE` (blessed path, see Hook interaction) |
| `/rforge:r:install`  | `R CMD INSTALL` (via Bash) or `pkgbuild::build()`+install | No structured result; report installed version + exit status |
| `/rforge:r:coverage` | `covr::package_coverage()` + `coverage_to_list()`    | Total % + per-file %, lowest offenders |
| `/rforge:r:site`     | `pkgdown::pkgdown_sitrep()` (report all) → `build_site(preview=FALSE, install=TRUE)` | Flags: `--preview` (`preview_site()`), `--strict` (`check_pkgdown()` fail-fast / CI), `--articles-only` (`build_articles()`, reinstall first), `--devel` (`load_all`, fast iteration). Classify **vignette render errors** (abort) vs **config/index** problems (warn). Needs `pandoc` |
| `/rforge:r:lint`     | `lintr::lint_package()`                              | Structured lints (file/line/linter/message) → grouped report; read-only. 🟡 if any |
| `/rforge:r:spell`    | `spelling::spell_check_package()`                    | Misspelled words + locations; AI triages real typos vs WORDLIST. 🟡 if any |
| `/rforge:r:urlcheck` | `urlchecker::url_check()`                            | Broken/redirected URLs + suggested fix. 🟡 if any |
| `/rforge:r:style`    | `styler::style_pkg()`                                | **Mutates source** — reformats, then reports the git diff summary (run + show diff; rely on git to undo) |
| `/rforge:r:cycle`    | `roxygenize()` → `test_local()` → `rcmdcheck()`      | Combined ADHD summary; stops early on hard error |

> **Vignettes/articles:** pkgdown renders `vignettes/*.Rmd` *source* (not the
> R-CMD-built vignette) into the site's "Articles"; `vignettes/articles/*.Rmd`
> are web-only (`.Rbuildignore`d). A vignette **chunk error aborts** the build
> (non-zero exit) — surface the failing `.Rmd`; index/url/OpenGraph gaps only
> **warn**. Default `build_site(install=TRUE)` installs to a temp lib for
> fidelity; `--devel` uses `pkgload::load_all()` for speed. `--articles-only`
> must reinstall first (standalone `build_articles()` renders the *installed*
> version).

Plus a retrofit of the **existing** `/rforge:r:check` onto the shared module
(it already runs `R CMD check`; switch it to `rcmdcheck::rcmdcheck(error_on="never")`
for structured counts; report shape unchanged).

### Out of scope (YAGNI)

- CRAN-specific variants beyond `r:check --as-cran` (`win`, `fast`, `spell`).
- Version-bump commands — handled by `/rforge:release` + the 4-source bump.
- **Deferred to their own specs** (per BRAINSTORM-r-command-expansion-2026-05-31):
  `r:deps-sync` (DESCRIPTION dep reconciliation); the **scaffolding theme**
  `r:create`/`r:use-test`/`r:use-package`/`r:use-vignette` (package creation is
  in rforge's mission — confirmed — but it's a file-writing/content-drafting
  shape distinct from run-and-parse, so separate spec); `r:cran-prep`
  (pre-CRAN orchestrator handing off to `/rforge:release`).
- The CRAN package literally named `checkthat` — it is a tidyverse
  data-validation tool, unrelated to build/test/site (see Appendix).
- Any dependency on flow-cli, or on `devtools` (see Architecture).
- A config/profile layer or generic `r:` runner (rejected approach "C").

## Architecture (Approach B, refined: R emits JSON → thin Python normalizer)

Two layers, matching rforge's existing `lib/` (interpretation) vs
`commands/` (presentation) split. The research changed the *mechanism*: R
serializes structured objects to JSON; Python does not regex free text.

### Core principle: do not text-parse

`rcmdcheck`, `testthat`, and `covr` return structured objects. The R
subprocess serializes them with `jsonlite::toJSON(..., auto_unbox=TRUE)`;
`lib/rcmd.py` consumes that with `json.loads()`. Regex over `R CMD check`
console text is only a **fallback** when `jsonlite` or a structured path is
unavailable (the known console formats are recorded below).

### 1. `lib/rcmd.py` — shared runner + normalizer (new public module)

Responsibilities:

1. **Locate the package** (DESCRIPTION in CWD or a `--path` arg); fail fast
   with a pointer to `/rforge:detect` if none.
2. **Hold the R snippets**, one per `kind` (`check`/`test`/`build`/`document`/
   `install`/`coverage`/`site`). Each snippet calls the lower-level package
   and prints a single JSON blob to stdout.
3. **Run** via `Rscript -e '<snippet>'` (subprocess), capture stdout + exit code.
4. **Normalize** the JSON into a common envelope and print it (the command
   prompt renders it; `lib/rcmd.py` itself does no formatting beyond JSON).
5. **Degrade gracefully**: missing engine package → `status:"error"` with the
   exact install hint; unparseable output → `status:"warn"` + raw lines in
   `messages[]` (never a false 🟢).

Invocation (package-module convention — never `python3 lib/rcmd.py`):

```bash
python3 -m lib.rcmd --kind check --path . [--as-cran] [--preview]
```

Normalized envelope:

```jsonc
{
  "kind": "check",
  "status": "ok" | "warn" | "error",        // drives 🟢/🟡/🔴
  "package": "foo", "version": "0.2.0",
  "check":    { "errors": [], "warnings": ["..."], "notes": ["...","..."] },
  "tests":    { "passed": 41, "failed": 0, "skipped": 3, "warnings": 0,
                "failing_files": [] },
  "coverage": { "total_pct": 87.4, "per_file": {"R/foo.R": 12.0} },
  "build":    { "artifact": "foo_0.2.0.tar.gz", "bytes": 184320 },
  "site":     { "checked": true, "built": true, "problems": [] },
  "install":  { "installed_version": "0.2.0", "exit": 0 },
  "lint":     { "count": 2, "lints": [{"file":"R/foo.R","line":3,"linter":"object_name_linter","message":"..."}] },
  "spell":    { "count": 1, "misspelled": [{"word":"teh","files":["R/foo.R:3"]}] },
  "urlcheck": { "count": 1, "broken": [{"url":"http://x","status":404,"new_url":null}] },
  "style":    { "changed_files": ["R/foo.R"], "count": 1 },
  "engine_missing": [],                       // e.g. ["pkgdown"]
  "messages": ["raw lines worth surfacing verbatim"]
}
```

Counts derive directly from the structured objects:
`length(chk$errors/$warnings/$notes)`; testthat `as.data.frame()` columns
(`passed`/`failed`/`skipped`/`warning`, failing files = rows where
`failed>0 | error`); `covr::percent_coverage()` + `coverage_to_list()`.

Becomes the **5th public lib module** → `docs/reference/rcmd.md` generated by
`scripts/gen_lib_reference.py`, gated in CI by `--check`.

### 2. `commands/r/*.md` — prompt commands

Each new command is a `commands/r/<verb>.md` file with the same frontmatter
shape as `commands/r/check.md`. The prompt instructs Claude to call
`python3 -m lib.rcmd --kind <kind> ...` via Bash and render the returned JSON
as the standard ADHD report (status dot, counts, failing items, recommended
next actions). Self-contained — no flow-cli runtime dependency.

### Data flow

```
user → /rforge:r:test
  → Claude: python3 -m lib.rcmd --kind test --path .
        → lib.rcmd finds DESCRIPTION (package + version)
        → Rscript -e 'res<-testthat::test_local(".",reporter="list",
              stop_on_failure=FALSE); df<-as.data.frame(res);
              jsonlite::toJSON(...summary...)'
        → json.loads, normalize → envelope JSON to stdout
  → Claude renders ADHD report from envelope
```

## Underlying packages & runtime dependencies

Confirmed in the dev environment (R 4.6.0): `rcmdcheck` 1.4.0, `testthat`
3.3.2, `covr` 3.6.5, `roxygen2` 8.0.0, `pkgbuild` 1.4.8, `checkmate` 2.3.4.
**Not installed:** `devtools`, `usethis`, `pkgdown`.

- **Required for full functionality:** `rcmdcheck`, `pkgbuild`, `roxygen2`,
  `testthat`, `jsonlite` (for the JSON bridge — near-universal, but treat as
  required and hint if missing). `pkgload` powers `r:load` and is pulled in
  automatically by `testthat` (it's in testthat's `Imports`), so it is present
  whenever `testthat` is.
- **Optional (command-specific):** `covr` (r:coverage), `pkgdown` (r:site),
  `lintr` (r:lint), `spelling` (r:spell), `urlchecker` (r:urlcheck),
  `styler` (r:style). These commands must detect absence and emit a clean
  `install.packages("<pkg>")` hint via `engine_missing[]`, not a stack trace
  (🟡, not 🔴, since each is a single optional command).
- **System dependency:** `pandoc` is required to render vignettes/articles in
  `r:site`. If absent, `r:site` reports 🟡 with the pandoc-install hint rather
  than a render stack trace.
- **Deliberately NOT required:** `devtools`, `usethis` — the commands call the
  lower-level engines directly. This is lighter and matches what's installed.

## Hook interaction (R-aware PreToolUse hook)

`/rforge:r:document` regenerates `man/*.Rd` and `NAMESPACE`. The hook's
**BLOCK rule 1** ("no hand-edits to `man/*.Rd`") fires on the **Write/Edit**
tools only. `r:document` regenerates these via `roxygen2::roxygenize()` run
through **Bash** — a different tool surface — so it is the explicitly blessed
regeneration path and does not trip the hook. No hook change needed.

## Error handling

- **Engine package missing** (`devtools`-free world): detect "there is no
  package called X" / non-zero exit → 🔴 (or 🟡 for optional covr/pkgdown)
  with the exact `install.packages()` line; list it in `engine_missing[]`.
- **Not an R package (no DESCRIPTION):** fail fast → pointer to `/rforge:detect`.
- **`rcmdcheck` on a failing package:** always pass `error_on="never"` so the
  object is returned and serialized even when the check fails.
- **`pkgdown` build:** success = process exit 0 (build_site returns nothing
  structured); structured problems come from `check_pkgdown()`/sitrep, surfaced
  in `site.problems[]`.
- **`r:cycle` early stop:** if `roxygenize()` or `test_local()` errors hard,
  stop before `rcmdcheck()` and report which stage failed.
- **Unrecognized output / no jsonlite:** fall back to the documented console
  formats (`[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]` for testthat;
  `0 errors ✔ | 1 warning ✖ | 0 notes ✔` for rcmdcheck), `status:"warn"`.

## Testing

Both existing gates must continue to pass, with additions:

- **`tests/test-all.sh`** (currently 29 checks): new command files covered by
  frontmatter-valid / command-name-uniqueness / skills-valid checks. Add a
  **lib CLI smoke** line for `python3 -m lib.rcmd --kind check` against a
  fixture (mock Rscript or a captured JSON blob — no live R in CI).
- **`python3 -m pytest tests/`** (currently 65 lib cases): add
  `tests/test_rcmd.py` (~15–20 cases) feeding captured JSON blobs and console
  fallbacks through the normalizer: clean check, check-with-notes, failing
  tests, low coverage, pkgdown problems, missing-engine, no-DESCRIPTION,
  no-jsonlite fallback. R subprocess is mocked (inject a fake `Rscript`),
  keeping CI R-free per the existing lib test pattern.
- **lib reference docs in sync:** `scripts/gen_lib_reference.py --check` must
  pass after `docs/reference/rcmd.md` is generated and committed.

## Documentation impact

Per rforge conventions (~15-file scope):

- `commands/r/{build,test,document,install,coverage,site,cycle}.md` (new) +
  retrofit `commands/r/check.md`.
- `docs/reference/rcmd.md` (generated).
- README.md + docs/index.md + docs/REFCARD.md command tables and counts
  (16 → 28 commands).
- `mkdocs.yml` nav additions.
- CHANGELOG.md `[Unreleased]` → `[2.1.0]`.
- 4-source version bump + live-version doc refs (per CLAUDE.md).
- `.STATUS`: move "Phase 4 agents (v2.1.0)" → v2.2.0; add this feature.

## Implementation order (for the plan)

1. `lib/rcmd.py` + `tests/test_rcmd.py` (TDD: envelope + normalizer + fallbacks).
2. Retrofit `commands/r/check.md` onto `lib.rcmd` (proves the pattern end-to-end).
3. Add the six new `commands/r/*.md` files.
4. `r:cycle` orchestrator.
5. Docs: reference page (generated), tables, REFCARD, mkdocs nav, CHANGELOG.
6. Version bump (4 sources + doc refs) + `.STATUS`.
7. Run both gates; PR `feature/r-dev-commands` → `dev`.

## Open questions / risks

- **Overlap with `r:check`/`thorough`:** `r:cycle` includes a check step;
  acceptable — cross-link rather than dedupe.
- **`jsonlite` assumption:** near-universal but not guaranteed; the console
  fallback covers its absence.
- **`pkgdown`/`covr` optional:** commands must degrade cleanly, not error.

## Appendix: research findings (2026-05-31)

Three parallel research agents reviewed the r-lib docs/sources:

- **devtools is a free-text meta-wrapper** over `pkgbuild` (build),
  `rcmdcheck` (check), `roxygen2` (document), `testthat` (test). Calling the
  lower-level packages directly yields structured objects *and* a lighter dep
  tree → chosen.
- **`rcmdcheck::rcmdcheck()`** returns `$errors`/`$warnings`/`$notes` as
  character vectors (counts via `length()`), plus `$status`, `$test_output`,
  `$session_info`, `$checkdir`. No JSON method — serialize with `jsonlite`.
  Use `error_on="never"`.
- **`covr`**: `coverage_to_list()` → `{filecoverage, totalcoverage}`;
  `percent_coverage()` → total numeric.
- **`testthat` / `pkgload`**: `devtools::test()` ≈ `testthat::test_local(path,
  load_package="source")`. `test_local()` **self-loads** the source package via
  `pkgload::load_all()` (its default `load_package="source"`), so no explicit
  load step is needed (a preceding `load_all()` double-loads). Per-function:
  `test_local`→source(load_all), `test_dir`→none, `test_package`/`test_check`
  →installed(`library()`). `pkgload` is in testthat's `Imports` ⇒ no devtools
  needed. `as.data.frame(results)` → 13 cols (`file,...,failed,skipped,error,
  warning,...,passed,result`); failing files = rows with `failed>0 | error`.
  Console fallback line: `[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]`.
- **`pkgdown` (vignettes/articles)**: renders `vignettes/*.Rmd` *source* into
  the site's "Articles" (`vignettes/articles/*.Rmd` = web-only). A vignette
  **chunk error aborts** `build_site()`; index/url/OpenGraph gaps only **warn**.
  Use `pkgdown_sitrep()` (reports all, non-fatal) by default; reserve
  `check_pkgdown()` (fail-fast) for `--strict`/CI. `build_site(install=TRUE)`
  installs to a temp lib for fidelity; `--devel` uses `load_all` for speed;
  `build_articles()` is an articles-only fast path but renders the *installed*
  version (reinstall first). Common issues: missing `pandoc`, erroring/network
  vignette chunks, missing `url:`, un-indexed topics. `preview_site()` →
  `--preview`. (Refs: pkgdown #635/#1283/#2093/#1230/#861/#2830.)
- **`checkthat`**: a real CRAN package (Ian Cero, 2023) — *"Intuitive Unit
  Testing Tools for Data Manipulation"*, a tidyverse data-validation toolkit,
  **unrelated** to build/test/site. Intended meaning is `testthat`/`rcmdcheck`,
  already the engines here. `checkmate` (installed) is runtime arg validation —
  also not relevant.

Key URLs: rcmdcheck.r-lib.org/reference/rcmdcheck.html ·
covr.r-lib.org/reference/package_coverage.html ·
testthat.r-lib.org/reference/testthat_results.html ·
pkgdown.r-lib.org/reference/{build_site,check_pkgdown}.html ·
devtools.r-lib.org/reference/index.html · cran.r-project.org/package=checkthat

# Changelog - RForge Plugin

All notable changes to the RForge plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.18.0] - 2026-06-30

> Creative doc enhancements + CI/staleness fixes. **41 commands** (no surface change).
> New in-site pages: changelog, glossary, command cards, contributor guide, example
> sessions. CI fix: remove `cache: pip` from `setup-python` (no requirements.txt),
> add pillow+cairosvg for social card generation. Stale refs cleaned from
> `install.sh` and `package.json`. pytest 524, test-all 44/44.

### Added

- **In-site changelog** (`docs/changelog.md`) — version history summary with links
  to the full GitHub CHANGELOG.
- **Glossary** (`docs/glossary.md`) — A–Z terminology covering all rforge concepts.
- **Command quick-reference cards** (`docs/command-cards.md`) — commands grouped by
  purpose in compact tables.
- **Contributor guide** (`docs/contributing.md`) — setup, testing, PR workflow.
- **Example session transcripts** (`docs/tutorials/example-sessions.md`) — 5 real
  transcripts showing rforge in day-to-day use.
- **Command decision tree** (Mermaid flowchart on `docs/index.md`) — helps users
  pick the right command.
- **Tarball-check workflow diagram** (`docs/workflows/index.md`) — visual overview
  of the v2.17.0 tarball-stage flow.
- **404 page** (`docs/404.md`) — friendly fallback with nav links.
- **Social cards** — OG image previews via Material `social` plugin (all pages).
- **Symptom/fix admonitions** — consistent `!!! warning "Symptom"` / `!!! success "Fix"`
  pattern across every troubleshooting section.

### Fixed

- **CI: `setup-python` `cache: pip` error** (`ci.yml`, `docs.yml`). The project has
  no `requirements.txt`/`pyproject.toml`, so the cache key lookup errored. Removed
  `cache: pip` from all three setup-python steps.
- **CI: social card deps** (`ci.yml`, `docs.yml`). Added `pillow` + `cairosvg` to
  docs dependency install — required by the Material social plugin.
- **Stale MCP ref in `install.sh`** — `scripts/install.sh` still told users to
  `npx rforge-mcp configure` (deprecated since v1.3.0). Replaced with accurate
  Python 3.10+ / R 4.0+ requirement hints.
- **Stale Node.js metadata in `package.json`** — removed non-existent `"main": "index.js"`
  and misleading `"engines": {"node": ">=18.0.0"}` (zero JS files in the repo).
- **Admonition accuracy** (`docs/index.md`) — "rforge does not build packages" was
  false; rforge wraps `r:build` / `r:cycle`. Reworded to "orchestrates and automates
  your build cycle."

### Changed

- **"Where rforge fits" diagram** (`docs/index.md`) — teal/amber palette matching
  the site theme; added diff-aware feedback loop; updated feature list to v2.18.0.
- **REFCARD accessibility note** — added screen-reader hint after the ASCII box.

## [2.17.0] - 2026-06-30

> Implements `PROPOSAL-winbuilder-fallback-and-tarball-check.md` — two fixes
> surfaced during medrobust v0.4.0 CRAN-prep. **41 commands** (no surface change;
> one new cran-prep stage + winbuilder fallback logic). pytest 524, test-all 44/44.

### Added

- **`r:cran-prep` `tarball-check` stage** (`lib/rcmd.py`, `lib/rsnippets.py`).
  Builds a source tarball via `devtools::build()`, inspects it for vignette/build
  artifacts (`.quarto/`, `_freeze/`, `.html`, `*_files/`), then runs
  `rcmdcheck::rcmdcheck(tarball, --as-cran, --run-donttest)`. Catches the class
  of failures CRAN and win-builder see but a source-tree `devtools::check()`
  hides (it pre-builds vignettes into `inst/doc/` before R CMD check runs, masking
  missing `VignetteBuilder` entries and artifact leaks). **Blocks `ready`** on
  errors/warnings/real NOTEs; suspicious tarball contents surface as advisory
  messages.
- **`check_build_hygiene` tarball inspection** (`lib/cranlint.py`). When
  `cran-prep` passes the built tarball path, `check_build_hygiene` now also
  scans the tarball contents (pure-stdlib `tarfile`) for build artifacts that
  `.Rbuildignore` failed to exclude — the delta between "what the dev thinks is
  excluded" and "what actually ships." New `tarball_build_artifact` finding code;
  degrades to `tarball_unreadable` advisory on a corrupt tarball.

### Fixed

- **`r:winbuilder` silent failure when `lib.rcmd` is not importable**
  (`commands/r/winbuilder.md`). The command previously called
  `python3 -m lib.rcmd --kind winbuilder` with no fallback; if the plugin's
  `lib/` was not on `PYTHONPATH` (e.g. invoked from an R package directory), it
  failed with `ModuleNotFoundError` and produced no useful output. The command
  now detects `lib.rcmd` availability and falls back to `devtools::check_win_*()`
  directly in R, with a `🟡` warning that the fallback path was used. Also
  clarifies that the argument must be a **package directory**, not a `.tar.gz`
  (devtools rejects tarball paths).

### Changed

- `r:cran-prep` default stage sequence now includes `tarball-check` between the
  strict/incoming check passes and the Tier-4 advisory stages.

---

## [2.16.0] - 2026-06-21

> pkgdown deploy leak guard (issue #52), built spec→TDD→adversarial-review.
> **41 commands** (no surface change; three additive `r:site` flags). New public
> module `lib/sitelint.py`. pytest 509, test-all 44/44.

### Added

- **`lib/sitelint.py` — pkgdown leak detector.** `check_site_leaks(path)` scans
  the pkgdown render surface (root `*.md`, non-`.Rd` files in `man/`, and
  `vignettes/` — aggressively in `vignettes/articles/**`, with top-level rendered
  vignettes auto-trusted) minus a core allowlist ∪ `.rforge.yaml` `site.allowlist`
  (path-aware), tagging each hit `tracked`/`untracked`/`modified`/`ignored` from
  `git` HEAD ∪ working tree. Pure-stdlib; advisory envelope (never blocks). CLI:
  `python3 -m lib.sitelint <path>`.
- **`r:site --check-leaks`** — standalone read-only lint surfacing stray files
  pkgdown would publish.
- **`r:site --deploy [--branch gh-pages] [--force]`** — clean-ref pkgdown deploy.
  Builds from a `git worktree add --detach HEAD` checkout (shares `.git`+remote so
  `deploy_to_branch` works, and excludes untracked working-dir files), runs the
  leak gate first (hard-abort on a committed non-allowlisted file; `--force`
  overrides), prints a "files pkgdown will publish" preview. Recommend-only:
  MUTATING + NETWORK, never auto-run.
- **`r:cran-prep` Tier-4 `site-leaks` advisory stage** — surfaces strays during
  CRAN prep; never blocks a `ready` verdict.

### Fixed

- Pre-release adversarial review caught + fixed a blocker (scan read the working
  tree while deploy publishes HEAD — a committed-then-deleted scratch file could
  leak) plus path-vs-basename allowlist collisions, an incomplete publish preview,
  a missing orchestrator recommend-only boundary (now gate-enforced), a
  decode-safe `git` regression, and temp-dir cleanup.
- **Deploy worktree uses a NAMED temp branch, not `--detach`** (found by the
  end-to-end smoke test): `deploy_to_branch` does `checkout --orphan` then returns
  to `git_current_branch()`, which a detached HEAD lacks → the worktree stayed on
  `gh-pages` and pkgdown's own worktree-add collided. Cleanup now removes the temp
  branch too.

### Note

- The full end-to-end `deploy_to_branch` path is validated by a manual smoke test
  (real build + push to a local bare `origin`): the published `gh-pages` contains
  the site and **excludes the untracked scratch file** — the #52 guarantee holds
  in a real deploy. The unit suite mocks the R call; a `_git_worktree_head`
  regression test pins the named-branch invariant.

---

## [2.15.0] - 2026-06-21

> Hardening and de-cluttering of `lib/rcmd.py` from a code review (P1–P4), built
> TDD-first from an approved spec. **41 commands** (no surface change); the
> `python3 -m lib.rcmd` CLI and every envelope key are byte-identical.
> pytest 470+, test-all 44/44.

### Security

- **`--platforms` allow-list validation** (`lib/rhub.py`; `_run_rhub`). The
  R-hub `--platforms` list is now validated against `ALLOWED_RHUB_PLATFORMS`
  (a frozenset superset of every `_RHUB_PRESETS` token) **before** any R call.
  An unknown or injection-shaped token (e.g. `x"); cat(1); ("`) returns a clean
  `{"kind":"rhub","status":"error",...}` envelope instead of reaching `Rscript` —
  closing an R-injection vector.

### Changed

- **Bounded timeouts on the quick `Rscript` calls** (`lib/rcmd.py`; `_invoke_r`).
  `_invoke_r` gained a `timeout` kwarg (default `None` keeps the long kinds —
  check/test/coverage/revdep — unbounded). `_r_version_key` (15s) and the R-hub
  dispatch (120s) now pass a bound; a `subprocess.TimeoutExpired` surfaces as
  exit code 124 / `{"timed_out": true}` and folds to `status:"error"` with a
  "Rscript timed out" message.

### Internal

- **Extracted `s7runtime` R into a shipped `lib/r/s7runtime.R`** — the embedded
  S7 runtime-introspection program (`s7_runtime_report(pkg_path)`, four stable
  return keys) now lives in a real `.R` script `source()`d by the snippet, not an
  inline Python f-string. Establishes the `lib/r/*.R` script convention.
- **Split `rcmd.py` → `lib/rsnippets.py` + `lib/rhub.py`** (behavior-preserving).
  Snippet builders + CRAN env constants moved to `rsnippets`; the seven R-hub
  names moved to `rhub`. Both are **internal** modules (no `docs/reference/`
  page). `rcmd.py` re-exports the names it still references; the rhub dispatch is
  a lazy import to keep the module graph acyclic. No surface change (41 commands).

---

## [2.14.0] - 2026-06-19

> Eight CRAN pre-submission gap-fills across `lib/cranlint.py` and `lib/rcmd.py`,
> each built TDD-first from an approved spec. **41 commands** (no surface change).
> pytest 435+, test-all 43/43.

### Added

- **G2 — DESCRIPTION `Date` staleness** (`lib/cranlint.py`; `lint_description`).
  New `description_date_stale` advisory finding when the `Date:` field is absent or
  more than 30 days old relative to today. Surfaces via the `description` Tier 4
  stage in `/rforge:r:cran-prep` (non-blocking).

- **G3 — `check_planning_consistency` DESCRIPTION drift** (`lib/cranlint.py`).
  New `check_planning_consistency` Tier 4 function detects CRAN-rejected boilerplate
  (`DESCRIPTION` still says "What the Package Does" / "A Short Description") and
  URL-in-title violations. Non-blocking advisory.

- **G5 — testthat edition check** (`lib/cranlint.py`; wired into `r:cran-prep`).
  New `check_test_config` Tier 4 function warns when `Config/testthat/edition` is
  absent (edition 2 default — CI snapshot failures) or explicitly `"2"`. Surfaced as
  the `test_config` stage row in `/rforge:r:cran-prep` (non-blocking advisory).

- **G4 — doi.org 403 URL classification** (`lib/rcmd.py`; `normalize("urlcheck")`).
  doi.org URLs returning 403 (firewall block, not real breakage) are now classified
  separately as `doi_blocked_count` — status becomes `warn` (not `error`). Real
  broken URLs still produce `error`. See `urlcheck.doi_blocked_count` in the envelope.

- **G1 — win-builder `--platform` kwarg** (`lib/rcmd.py`; `r:winbuilder`).
  `/rforge:r:winbuilder` now accepts `--platform devel|release|oldrelease|all`.
  Default `all` submits all three win-builder flavours in one call. (Multi-platform
  R-hub dispatch moved to the dedicated `/rforge:r:rhub` command — see Fixed below.)

- **G6 — `--run-donttest` in strict/incoming** (`lib/rcmd.py`; confirmed present).
  `--run-donttest` is already set whenever `strict=True`, `flavor` is set, or
  `incoming=True` — confirmed and covered by tests.

- **G7 — sequential incoming passes** (`lib/rcmd.py`; `r_snippet("check", incoming=True)`).
  `_R_CHECK_DEPENDS_ONLY_` and `_R_CHECK_SUGGESTS_ONLY_` are mutually exclusive in
  rcmdcheck. The `incoming=True` path now runs two sequential `rcmdcheck::rcmdcheck()`
  calls (pass 1 + pass 2) in one R process and merges `errors/warnings/notes` via
  `c(r1$X, r2$X)` — both dependency perspectives captured in one `check (incoming)`
  stage row. Adds `_CRAN_CHECKS_REGISTRY` (versioned env-var bundles keyed by R
  version) and `_r_version_key()` helper. Backward-compat: plain `r_snippet("check")`
  output is byte-identical.

- **G8 — PDF manual skip advisory** (`lib/rcmd.py`; `normalize("check")`).
  When R CMD check emits a "skipping PDF manual" / "LaTeX not found" message (no
  LaTeX on the build host), a `pdf_manual_skipped` finding is now surfaced as an
  advisory in the envelope — prompting the user to rely on win-builder for the PDF
  manual instead of treating the skip as silent.

### Fixed

- **`r:rhub` headless dispatch overhaul** (`lib/rcmd.py`, `commands/r/rhub.md`).
  The command was non-functional: `rhub::rhub_check()` with no `platforms=` arg
  opened an interactive console menu and hung headlessly, and `rhub::rhub_setup()`
  was called on every invocation (a spurious git commit each run). It now:
  - Passes platforms **explicitly** (never `NULL`); defaults to the `cran-submission`
    preset (`linux, windows, macos-arm64, atlas`) — new `--platforms`/`--preset` flags.
  - **Never** calls `rhub_setup()`; a Python-side pre-flight hard-stops with
    `rhub_yaml_missing` when `.github/workflows/rhub.yaml` is absent.
  - Hard-blocks known-broken platforms (`macos`, macos-13 runner retired Dec 2025)
    and advises (non-blocking) on missing `pak-version: stable` (r-lib/pak #887) and
    broken default-config platforms.
  - Adds `--rc-mode` (`rhub::rc_submit()` on RC shared runners) and opens the GitHub
    Actions URL (built from the git remote) in the browser.
  - Removes the stale `r:winbuilder --platform rhub` sub-path (same hang bug, second
    entry point). New `tests/test_rcmd_rhub.py` (18 tests).

---

## [2.13.0] - 2026-06-13

> Two diff-aware/ecosystem features, each built TDD-first from an approved spec and
> hardened by a pre-merge adversarial review (which caught BLOCKERs the green gates
> missed). **41 commands** (no surface change — both add flags/families, no new
> command). pytest 416, test-all 42/42.

### Added

- **Cross-package S7 contract checks** (`lib/s7review.py`; `r:s7-review --eco`, no
  new flag). The ecosystem-only `cross-package-contract` family — candidate B
  sub-item 1, the **static, ecosystem-scoped sibling** of v2.12.0's runtime
  `method_undeclared_dependency`. `--eco` now builds an ecosystem-wide registry of
  every S7 class binding → defining package (`build_class_registry`), then flags a
  `method(generic, C)` that dispatches on a **sibling** package's class C when:
  (1) that package isn't declared in this package's `Imports`/`Depends`/`LinkingTo`
  (`cross_package_undeclared_contract` — C never resolves at the consumer's load,
  the method silently never dispatches); or (2) it IS declared but no declared
  provider exports C (`cross_package_unexported_class`). Static and **name-based**
  (resolves on the R binding `method(g, C)` references, not the `@name` string;
  can't do the runtime object-identity `--runtime` uses), so deliberately
  conservative: flags only when no declared, exporting provider can exist, and
  **suppresses** the export check when a provider's NAMESPACE is absent or uses
  `exportPattern()` (export set unknowable → no false positive). Multi-dispatch
  `method(g, list(A, B))` checks each class; `class_*` base helpers and `pkg::`
  explicit refs are skipped. Surfaced in the `--eco` rollup `by_family`; automatic
  (inherently needs the ecosystem), silent when no cross-package S7 dispatch
  exists. Reachability is **re-export-aware**: a class reached through a declared
  re-exporting facade (`importFrom` + `export`) is correctly clean, not flagged.
  Hardened by a 3-lens pre-merge adversarial review that caught 2 BLOCKERs + 2
  IMPORTANTs the green gates missed — re-export false positive; `=`-assigned
  classes (`Foo = new_class()`) invisible to the registry → genuine contracts
  silently missed (the `_CALL_RE` binding fix also restores `check_naming`'s
  bound-vs-`@name` check for `=`); multi-line `export()` parsed as the empty set
  → false unexported (now balanced-paren, multi-line aware); and the `run_eco`
  pre-loop registry build guarded so a malformed package can't abort the sweep —
  all fixed + re-verified. +19 pytest cases. Spec:
  `SPEC-s7-cross-package-contracts-2026-06-13.md`. (Candidate B sub-item 2 — full
  R6/S4 convention checking — parked.)

- **Diff-aware baseline caching** (`lib/changed.py`; `r:check`/`r:test`/`r:lint`
  `--changed` + new `--no-cache` flag). The last v2.11.0 `--changed` follow-up
  (`[uncommitted]` tagging shipped v2.12.0). Each `--changed` run does two engine
  passes: a HEAD run and a **baseline** run in a detached worktree at
  `merge-base(HEAD, --base)` — and for `kind=check` that baseline is `R CMD check`
  per package, costing minutes. A package's baseline finding list is a **pure
  function** of `(merge-base SHA, kind, package, engine flags)`, so it is now cached
  **per package** under `~/.rforge/baseline-cache/<repo-id>/<sha>-<keyhash>.json`.
  A repeat `--changed` run with an unchanged merge-base reuses each package's
  baseline and re-runs **only** the packages not yet cached — so an ecosystem
  cascade where the changed-package set *grows* (edit pkgA, then pkgB, then pkgC)
  reuses every package already baselined, and when the whole set is cached no
  detached worktree is created at all. **Self-invalidating** — new commits on
  `--base` move the merge-base SHA → new key → automatic miss; no manual
  invalidation. The key includes the package and engine flags precisely *because*
  an under-keyed cache would serve an under-covering baseline and mis-tag
  pre-existing findings as `[introduced]`. **LRU prune** to the 20 newest entries
  per repo (by mtime, on write). New `--no-cache` (bypass read+write, e.g. after an
  R-engine upgrade that changes the immutable-tree baseline) and
  `python3 -m lib.changed --clear-cache`. `lib/changed.py` stays R-free: a generic
  `cached_baseline(items, run_item, key_item)` helper takes opaque items + injected
  callbacks (rcmd supplies the per-package decomposition) and owns only repo-id +
  SHA + file IO + prune; `scope_check` is now caching-agnostic (it takes a pluggable
  `baseline` provider). Advisory throughout — a cache failure degrades to a normal
  uncached baseline; nothing here raises (incl. an unresolvable HOME — `_cache_root`
  resolves home the raise-proof `expanduser` way, falling back to the temp dir, NOT
  `Path.home()` which raises in container/scratch-CI uids). +17 pytest cases
  (cache roundtrip/miss/corrupt/prune/clear/repo-id, per-package partial-hit +
  all-hits-skip + use_cache-false + worktree-fail, scope_check injected-baseline /
  None-fallback / default-uncached, CLI, dict-finding hit==miss equivalence,
  never-raises-on-unresolvable-HOME). Hardened by a 4-lens pre-merge adversarial
  review of the initial whole-baseline design (1 BLOCKER unresolvable-HOME crash +
  2 IMPORTANT tmp-leak/premature-version-label + 2 MINOR, all fixed + re-verified)
  before the per-package generalization. Spec:
  `SPEC-diff-aware-baseline-caching-2026-06-13.md`.

---

## [2.12.0] - 2026-06-13

> Three recommendations from a doc gap analysis, built TDD-first and hardened by a
> 3-dimension pre-release adversarial review. **41 commands** (no surface change).

### Added

- **Diff-aware `[uncommitted]` tag** (`lib/changed.py`; refines `r:check`/`r:test`/`r:lint`
  `--changed`, no new flag). v2.11.0's two-run `--changed` tags findings `[introduced]`
  (new on this branch vs the merge-base) vs `[pre-existing]`; it deferred
  uncommitted-change tagging. This refines it: an `[introduced]` finding whose file has
  **uncommitted** changes (per new `uncommitted_files()` → `git status --porcelain`) is
  re-tagged **`[uncommitted]`**, so you can tell "I caused this with edits I haven't
  committed yet" from committed branch work. File-level, **no third check run** (a
  finding-precise version would need a clean-HEAD run, tripling cost): all introduced
  findings in a dirty file tag `[uncommitted]`. String findings (R CMD check messages
  with no file) stay `[introduced]`; `[pre-existing]` is never re-tagged; a finding is
  never both. `[uncommitted]` is a **subset of introduced** — `--fail-on introduced`
  (default) still fails on it (it's your work). Advisory: a git failure yields no
  refinement (never raises). +8 pytest cases (real-git e2e + `uncommitted_files` units +
  `--fail-on` on uncommitted-only). Spec: `SPEC-diff-aware-uncommitted-tag-2026-06-13.md`.

- **`docs/commands.md` sync-gate** (`tests/_check_commands_doc.py`, wired into
  `tests/test-all.sh`; 41→42 checks). A pure-stdlib presence check closing the last
  drift-prone documentation surface: (1) **command coverage** — every non-stub command
  file (`commands/**/*.md`, excluding the v2.0.0 rename stubs) has a matching
  `### /rforge:<name>` section, and every such section has a backing command file (both
  directions); (2) **flag coverage** — every real CLI flag declared in a command's
  frontmatter `arguments:` is documented as `--<name>` in that command's section.
  Positionals (`package`/`path`/`context`/`task_id`/`function`/`name`) and lib-only
  forwarded args are excluded, but a positional name genuinely exposed as a slash flag
  (e.g. `/rforge:impact --package`) is still covered. Core logic is importable; a pytest
  self-test (`tests/test_commands_doc.py`, 12 cases) feeds it fixtures to prove the gate
  catches missing flags/sections/orphans (not vacuous). Spec:
  `SPEC-commands-doc-sync-gate-2026-06-13.md`.

- **`r:s7-review` `method_undeclared_dependency`** runtime finding (closes the
  cross-package check deferred in v2.11.1; no new flag). The `--runtime`
  `method-dispatch` family now flags a method dispatching on an S7 class that *does*
  resolve but whose providing package (`attr(class, "package")`) is set, differs from
  this package, and is **not** in `DESCRIPTION` `Imports`/`Depends`/`LinkingTo` —
  typically a `Suggests`-only class. At a site without that package the dispatch class
  never registers, so the method silently never fires (a real correctness/CRAN bug).
  Extends the v2.11.1 per-signature loop in the `s7runtime` engine (`lib/rcmd.py`):
  declared deps are parsed R-side once from the loaded DESCRIPTION, with an always-allow
  set (the package itself + `base`/`methods`/`stats`/`utils`/`graphics`/`grDevices`/
  `datasets`/`tools`/`S7`); the three per-signature outcomes are mutually exclusive
  (unresolvable → `method_on_missing_class`; resolvable + undeclared package →
  `method_undeclared_dependency`; resolvable + declared → clean). Engine emits
  structured `{generic, class, package}`; consumer (`lib/s7review.py`) maps them into
  advisory `source: "runtime"` findings. +3 pytest cases (real-R e2e with two installed
  helper packages — one declared, one not — plus consumer-mapping + normalize units).
  Spec: `SPEC-s7-undeclared-dependency-2026-06-13.md`.

### Fixed

- **`docs/commands.md` flag drift surfaced + fixed by the new gate** — 10 undocumented
  command flags added to their sections: `/rforge:quick --package`,
  `/rforge:detect --format`, `/rforge:cascade --detailed`,
  `/rforge:impact --package`/`--change-type`/`--affected-exports`,
  `/rforge:release --detailed`, `/rforge:docs:check --detailed`,
  `/rforge:complete --no-cascade`, `/rforge:next --context`.

### Fixed (pre-release adversarial review)

A 3-dimension adversarial review caught issues the green gates missed:

- **BLOCKER — diff-aware `[uncommitted]` cross-package collision.** The file match
  was basename/suffix-fuzzy, so a *committed clean* finding in `pkgB/R/utils.R` was
  mis-tagged `[uncommitted]` when an unrelated `pkgA/R/utils.R` was dirty. Now findings
  are rebased to repo-relative coordinates and matched **exactly** against
  `git status --porcelain -z` (the `-z` form also fixes spaced/quoted paths).
- **IMPORTANT — sync-gate multi-line stripping.** `_check_commands_doc.py` only stripped
  the first line of a `\`-continued `python3 -m lib.*` invocation, which could promote a
  positional name to a required flag. Now tracks continuation state.
- Plus: quoted-name handling + `--flag` prefix-collision (`--base` vs `--base-dir`) in the
  sync-gate; the s7 base-package allowlist now derives from
  `installed.packages(priority="base")`; `next`/`quick` `argument-hint` aligned to `--flags`.

---

## [2.11.1] - 2026-06-13

### Added

- **`r:s7-review` `method_on_missing_class`** runtime finding (closes the family
  deferred in v2.11.0). The `--runtime` `method-dispatch` family now flags a method
  whose dispatch signature references an S7 class with **no resolvable namespace
  binding** (e.g. an inline `new_class()` left in a `method()` call) — an unreachable
  method, the runtime sibling of `dead_generic`. The v2.11.0 "not decidable from the
  registry alone" deferral was refuted empirically: each `S7_method` carries
  `attr(., "signature")` (its dispatch class objects), so resolvability is decidable.
  Base-type methods and imported classes are guarded against false positives. Lands in
  the `s7runtime` engine (`lib/rcmd.py`) + consumer (`lib/s7review.py`); R-gated e2e
  test. Spec: `SPEC-s7-method-missing-class-2026-06-13.md`. No command-count change.

---

## [2.11.0] - 2026-06-13

> Bundles three follow-up features — diff-aware `[introduced]`/`[pre-existing]`
> tagging (P0 completion), `r:s7-review --eco`/`--runtime`, and the
> `r:use-data`/`r:use-citation` scaffolders — each built TDD-first from an
> approved spec, then hardened by a pre-release adversarial review.
> **39 → 41 commands.**

### Added

- **`r:use-data` + `r:use-citation`** (scaffolding v2 — completes the `r:use-*`
  family; **39 → 41 commands**). Same contract as the v2.10.0 scaffolders:
  dry-run by default, `--write` applies, pure-stdlib (no R). **`r:use-data`**
  documents a package dataset — appends a roxygen stub to `R/data.R` (`@title`,
  `@format` with a `\describe{}` skeleton, `@source`, and the trailing
  `"<name>"` documented-data idiom) and patches `DESCRIPTION`
  (`LazyData: true` / `Depends: R (>= 2.10)`) through the shared
  constraint-preserving DCF writer (`deps_sync._read_field_specs` /
  `_rewrite_field` — existing version floors survive, regression-locking the
  v2.10.0 fix on the new path). It **never fabricates the `.rda`** (the data is
  the user's) — it emits the exact `usethis::use_data(<name>)` reminder — and a
  collision guard skips duplicate `\name` docs. **`r:use-citation`** scaffolds
  `inst/CITATION` from `DESCRIPTION` (`Title`/`Authors@R`→`person()`/`Version`)
  as a `bibentry(bibtype = "Manual", ...)`; the year comes from `Date:` if
  present, else a `<YEAR>` TODO — **never a wall-clock date** (determinism).
  `--write` writes the file, `--force` to clobber; unparseable authors degrade
  to a `# TODO` block + warn (never raises). Both land in `lib/scaffold.py`
  (12 new tests). Spec: `SPEC-r-scaffolding-v2-2026-06-13.md`.
- **`r:s7-review --eco` + `--runtime`** (v2 sibling of the v2.10.0 static checker) —
  two composable flags, no new command. **`--eco`** runs the 5 static families
  across **every package** in the ecosystem manifest and aggregates one
  `s7review-eco` envelope (per-package breakdown + roll-up by family, ordered by
  the manifest's `manifest_order`); pure-stdlib, a parse-failure package degrades
  to a per-package `warn` without aborting the sweep. **`--runtime`** adds an
  R-backed pass — a new **`s7runtime` engine in `lib/rcmd.py`** (`pkgload::load_all`
  + S7 runtime introspection) contributing two new families: **`method-dispatch`**
  (`dead_generic` — an S7 generic with zero registered methods) and
  **`validator-runtime`** (`validator_not_enforcing` — a validator whose body is a
  constant no-op that can never reject input). The runtime families carry
  `source: "runtime"`; static findings keep `source: "static"`. All R routes
  through `lib.rcmd` (the only R-touching module); `s7runtime` is read-only and
  added to `SAFE_AUTORUN`. The flags compose (`--eco --runtime`). `--runtime`
  degrades to advisory `warn` stages ("runtime pass skipped: …") when R / S7 is
  unavailable — the static result is always intact, exit 0 always (mirrors
  `runiverse` offline degradation). Spec: `SPEC-r-s7-review-eco-2026-06-13.md`.
- **diff-aware `--changed` tagging** (P0 completion) — completes the v2.10.0
  scope-only `--changed` flag on `r:check`/`r:test`/`r:lint`. Each finding is now
  tagged **`[introduced]`** (new on your branch) vs **`[pre-existing]`** (already
  present at the fork point), computed honestly via a second baseline run in a
  detached worktree checked out at `git merge-base(HEAD, --base)` (`--base`
  default: `dev`). New `merge_base()` + `run_baseline()` in `lib/changed.py`
  (guaranteed worktree cleanup in a `finally`) wake the previously dormant
  `scope_check()`; `lib/rcmd.run_changed` wires them in with a per-kind runner.
  New **`--fail-on`** flag (default `introduced`) exits non-zero iff ≥1 introduced
  finding, so CI fails only on regressions you caused — not pre-existing debt;
  `--fail-on none` is advisory. No command-count change (flags). Spec:
  `SPEC-diff-aware-tagging-2026-06-13.md`.

### Changed

- `--changed` baseline now runs in a real merge-base detached worktree instead of
  the scope-only fallback. The fallback (real status, no tagging) is preserved
  when no merge-base / baseline worktree is available — no regression of v2.10.0.

### Fixed (pre-release adversarial review)

A multi-agent adversarial review caught three bug-classes the green gates missed:

- **`r:use-citation` emitted invalid R** for the standard `Authors@R` idioms —
  a flat regex truncated `person(role = c("aut", "cre"))` (fired on the repo's
  own fixture), and interpolated `Title`/`Version` weren't escaped (a `"` in the
  title broke the literal). Now the `Authors@R` value is re-emitted verbatim and
  every interpolated value routes through `_r_string()`. New tests assert the
  generated CITATION actually parses under `Rscript`.
- **diff-aware tagging mis-tagged shifted lint findings** — `tag_findings` keyed
  on the raw line number, so inserting a blank line above a pre-existing lint
  tagged it `[introduced]` (a false positive). Dict findings now key on
  `(file, message, linter)`, line-shift-immune.
- **`r:s7-review` advertised a non-working family** — `method_on_missing_class`
  was a hardcoded-empty placeholder listed as a runtime finding. Removed the dead
  code path and marked it deferred in the command help + spec.
- Plus: dead `_CHANGED_SCOPE_ONLY` constant removed, s7 test fixtures fixed to
  actually load under S7 (real-R runtime path now has a regression test), and
  `use-data`'s collision guard now matches indented doc lines.

---

## [2.10.0] - 2026-06-13

> Bundles three roadmap features — an S7 convention checker, diff-aware checks,
> and a scaffolding theme — each built TDD-first from an approved spec.
> **35 → 39 commands.**

### Added

- **`r:s7-review`** (#26) — S7 convention checker. New pure-stdlib
  `lib/s7review.py` (`cranlint` archetype) statically checks five families —
  naming, validators, methods, legacy-OOP leftovers, class docs — and emits an
  advisory warn-only envelope (never blocks). `--eco` deferred to a follow-up;
  R-backed runtime checks deferred to a v2 sibling. +1 command.
- **Scaffolding theme** — `r:use-test`, `r:use-package`, `r:use-vignette` for
  **existing** packages. Dry-run by default; writes only with `--write`. New
  `lib/scaffold.py` + `lib/usethis_infra.py`; `r:use-package` **reuses**
  `deps_sync`'s DESCRIPTION-patch writer (`_apply_patch`) and `scan_usage` for
  the Imports-vs-Suggests call. +3 commands.
- **diff-aware `--changed`** (P0) — new `lib/changed.py` (git-diff →
  changed-files → owning packages via `discovery.find_r_packages`); `--changed`
  **scopes** `r:check`/`r:test`/`r:lint` to the package(s) touched on the branch
  and reports their genuine full status. No command-count change (flags).
  `[introduced]`/`[pre-existing]` finding tagging is **deferred** until a
  merge-base checkout is wired (see `commands/r/check.md`) — `--changed` is
  scope-only for now.

### Changed

- Test gates rise: `tests/test-all.sh` **36 → 41 checks**; `pytest` **232 → 298**
  (new `test_s7review`/`test_scaffold`/`test_changed` + rcmd flag cases). New
  `docs/reference/{s7review,changed,scaffold}.md` (auto-generated, `--check`
  gated).

### Fixed (pre-release adversarial review)

- An adversarial review before the release caught three bug-classes the gates
  missed (fixed in the same release): a diff-aware `--changed` **silent
  false-negative** (it had compared HEAD against itself, reporting `ok` even
  with real `R CMD check` errors — now honest scope-only); a `deps_sync`
  `--write` bug that **dropped version constraints** on untouched deps (also
  affected `r:deps-sync`); and four `r:s7-review` **false positives** (the
  parser hadn't masked comments/strings, flagging idiomatic `new_property()`).

---

## [2.9.0] - 2026-06-12

> Rewrites the single agent (`agents/orchestrator.md`), which had been stale
> since v1.3.0: it delegated to 13 `rforge_*` MCP tools (43 references) removed
> when rforge-mcp was absorbed into pure-Python `lib/` modules. The rewrite
> delegates via `python3 -m lib.*` envelopes instead. Last craft-parity item
> (Phase 4). No command-surface change — still 35 commands, still 1 agent.

### Changed

- **Orchestrator agent rewritten** — `agents/orchestrator.md` now delegates via
  `python3 -m lib.*` envelopes (run through Bash) instead of the removed
  `rforge_*` MCP tools. Adds `name`/`description` frontmatter, an intent→lib
  mapping over **7 intents** (CODE_CHANGE incl. `lib.deps impact` / NEW_FUNCTION /
  BUG_FIX / DEPS_AUDIT / QUALITY / CRAN_READINESS / ECOSYSTEM_HEALTH), a strict
  read-only/recommend-only safety boundary (mirrors "never auto-submit": every
  file-writing or network command — `document`/`cran-prep`/`style`/`build`/
  `submit`/`winbuilder`/`rhub`/`urlcheck`/`revdep`/`--write` — is recommended,
  never auto-run), correct `--format json` flags, and per-module envelope
  synthesis (modules don't share one schema).

### Added

- Three `tests/test-all.sh` guards (**33 → 36 checks**): no removed rforge-mcp
  refs in any agent file (`rforge_`/`mcp__rforge`; regression lock for the bug
  this release fixes), orchestrator carries `name`+`description` frontmatter, and
  a recipe validator (`tests/_check_agent_engines.py`) asserting every `--kind`
  is a **real** `lib.rcmd` engine, is **safe to auto-run** (read-only — the gate
  rejects mutating kinds like `document`/`cran-prep` in auto-run recipes, in both
  `--kind x` and `--kind=x` forms), every `lib.<module>` it names exists, and
  every recipe command **actually parses** (no argparse usage error — catches
  wrong flag ordering / missing required args that token checks miss).
- **`Ecosystem.manifest_order`** (issue #20) — `lib.discovery` now exposes the
  manifest's package names in *declared* order (empty in the zero-manifest case)
  via the dataclass field and `to_dict()`, so consumers like `/rforge:status` can
  render in a curated order rather than disk/alphabetical. Closes the PR #17
  follow-up gap where manifest order was discarded after enrichment.

### Documentation

- **Orchestrator agent docs** — new [`orchestrator.md`](docs/orchestrator.md) guide
  (4-step flow, 7-intent table, safety boundary, synthesis) + a worked-examples
  [cookbook tutorial](docs/tutorials/orchestrator-cookbook.md), a REFCARD section,
  an architecture.md refresh (pre-v2.9.0 "pattern recognition" → intent
  recognition), and mkdocs nav entries.
- **`commands.md` count drift fixed** — the header now renders
  `{{ rforge.command_count }}` (was a stale literal "33"; drift-proof like the
  other v2.8.0-macro'd surfaces), and three category subtotals were corrected to
  match the actual entries (Ecosystem 5→6, R Dev Cycle 9→8, R Quality 5→4; now
  sum to 35).
- **Inline help completed** — added `argument-hint` frontmatter to the 10 `r:`
  commands that lacked it (`load`/`document`/`test`/`build`/`install`/`site`/
  `lint`/`spell`/`urlcheck`/`style`), so `/help` shows usage hints for every
  non-stub command. `r:site` carries its four boolean flags; the rest `[package]`.

> Makes docs render the current version/command-count from a single source of
> truth (`package.json`) so they stop drifting (the 33→35 staleness root-caused
> in `5267825`). Two Python-native layers: a `mkdocs-macros` render layer and a
> `version_sync.py --check` CI gate. No command-surface change — still 35 commands.

### Added

- **`scripts/version_sync.py`** — pure-stdlib sync tool (matches `gen_lib_reference.py`
  style). Reads `version` from `package.json` and `command_count` from
  `mkdocs.yml extra.rforge.command_count`, then syncs the derived surfaces
  (`mkdocs.yml extra.rforge.version`, `.claude-plugin/plugin.json`, `package.json`
  + `README.md` count strings, `CLAUDE.md` command-count heading). `--check` is a
  CI drift gate (exit 1 on drift), `--dry-run` previews; wired into both
  `tests/test-all.sh` and `.github/workflows/ci.yml`. New tests in
  `tests/test_version_sync.py` (7 cases).
- **mkdocs-macros render layer** — `mkdocs-macros-plugin` enabled in `mkdocs.yml`
  with an `extra.rforge` namespace (`version`/`prev_version`/`release_date`/
  `command_count`); installed in `docs.yml` CI. ~10 user-facing docs now render the
  current version/count via `{{ rforge.version }}` / `{{ rforge.command_count }}`
  macros (historical "introduced-in vX.Y.Z" refs left literal). See
  `docs/specs/SPEC-mkdocs-version-macros-2026-06-12.md`.

### Changed

- Release runbook (`CLAUDE.md`): after bumping `package.json`, run
  `python3 scripts/version_sync.py` to propagate version/count; mkdocs docs are no
  longer hand-edited for the current version/count.

---

## [2.7.0] - 2026-06-11

> Adds an **R-universe early-access tier** to `r:submit` — verify your package's
> fast-channel build is green while CRAN's slower review runs. CRAN submission
> stays explicit and never automatic.

### Added

- **`r:submit --universe`** (`lib/runiverse.py`) — new opt-in flag that verifies the package's
  [R-universe](https://r-universe.dev) early-access build. R-universe rebuilds from your GitHub
  repo within minutes and serves CRAN-like binaries, so users can install the new version
  (`install.packages("<pkg>", repos = "https://<owner>.r-universe.dev")`) while CRAN review runs
  in parallel. The flag auto-detects the universe from the git `origin` remote (override with
  `--universe-name <owner>`), reads the public R-universe API, and reports per-platform build
  status. **Read-only** — R-universe builds on `git push`, so it never uploads; and the R-universe
  status appears as an **advisory** line in the CRAN checklist that never blocks the (still manual)
  CRAN handoff. New public, pure-stdlib module `lib/runiverse.py` (`urllib`-only; no `gh`/R).
  Degrades to a `warn` envelope when offline or unregistered (prints one-time setup guidance);
  never raises. See `docs/specs/SPEC-r-submit-runiverse-early-access-2026-06-11.md`. Command count
  unchanged at 35 (a flag, not a new command).

---

## [2.6.0] - 2026-06-10

> Collapses four roadmapped minors into one release — cran-incoming hardening,
> ecosystem-manifest discovery, `r:deps-sync`, and `r:submit` — that accumulated
> on `dev` since v2.2.0.

### Added

- **Ecosystem manifest discovery** (`lib/discovery.py`): `detect_ecosystem()` optionally reads an ecosystem manifest (e.g. `ECOSYSTEM-MANIFEST.yaml`) located via a new `manifest:` key in the root `.rforge.yaml`, and enriches discovered packages with curated metadata (`role`, `repo`, `cran`, `status_file`). Matching is by package name (case-insensitive). Mismatches surface as `Ecosystem.drift` (`manifest_only` / `disk_only`). New public API: `Manifest`, `ManifestEntry`, `Drift`, `parse_manifest()`, `read_manifest()`.
- **Vendored YAML-subset parser** — `parse_manifest()` reads top-level scalars + a `packages:` list of flat maps with inline-comment stripping, keeping `discovery.py` stdlib-only (no PyYAML). See `docs/specs/SPEC-ecosystem-manifest-discovery-2026-06-10.md`.
- **Manifest surfaced in output**: `/rforge:detect` text output shows a `manifest:` header field, an inline `role` per package, and a `⚠️  Manifest drift` block. `/rforge:status` adds a (conditional) `Role` column and the same drift block. Both render the extra detail only when a manifest is configured — zero-manifest output is byte-for-byte unchanged.
- **`r:deps-sync`** (`lib/deps_sync.py`) — new pure-Python per-package command that reconciles `DESCRIPTION` against actual code usage. Scans `R/`/`tests/`/`vignettes/` + `NAMESPACE` for namespace usage (`pkg::`, `library()`, `@importFrom`, …) and reports **missing** (used, undeclared → Imports), **misclassified** (in Suggests but used unconditionally in `R/` → Imports — the static sibling of `r:check --strict`'s noSuggests pass), **missing_suggests** (tests/vignettes-only), and **unused** findings, plus a suggested patch. Report-only by default; `--write` applies the unambiguous changes. Commands 33 → 34.
- **`r:submit`** (`lib/ghrelease.py`) — new per-package command wrapping the moment of CRAN submission: gate on `cran-prep` `ready` → build the tarball → cut a GitHub **pre-release** (not "Latest") of it + `cran-comments.md` → print the CRAN submit checklist (**never auto-submits**). `r:submit --promote` flips the pre-release to a full release on acceptance (`gh release edit --prerelease=false --latest`). Plain `v<version>` tags promoted in place; `gh` is a soft dependency with a printed manual-recipe fallback. Sidesteps the r-pkgs anti-pattern of tagging a final release pre-acceptance. Commands 34 → 35.

### Changed

- `Ecosystem` gains `manifest_path` and `drift` fields (both default to the empty/zero-manifest case); `Package` gains an optional `manifest` field. `Ecosystem.to_dict()` includes both. Zero behavior change when no manifest is configured.
- `lib/status.py`: `PackageStatus` gains `role`; `EcosystemStatus` gains `drift`; both `to_dict()`s include the new fields. `aggregate_status()` passes manifest role + drift through from discovery.

---

## [2.3.0] - 2026-06-10

> ⚠️ **Behavior change.** `r:cran-prep` now runs two strict Suggests-withholding
> check passes **by default** and **blocks the `ready` verdict** when they fail.
> A package that reports 🟢 `ready` today under `--as-cran` alone can turn 🔴 if
> it uses a `Suggests` package unconditionally (the medfit 0.2.1 class). This is
> intended — CRAN's post-acceptance noSuggests flavor would bounce it anyway —
> but it is not patch-safe, hence the minor bump.

### Added

- **CRAN-incoming strict check passes** (`lib/rcmd.py`): `r:check --strict` runs
  both Suggests-withholding flavors as distinct stage rows — `check (noSuggests)`
  (`_R_CHECK_DEPENDS_ONLY_=true`) and `check (suggests-only)`
  (`_R_CHECK_SUGGESTS_ONLY_=true`) — each with `--run-donttest` (runs
  `\donttest{}` examples). `r:check --incoming` implies `--strict` and adds a
  third `check (incoming)` row (`_R_CHECK_CRAN_INCOMING_*`, confirmed against R
  Internals §8). Mechanism: `rcmdcheck(args=, env=)` — no `devtools`, no
  subprocess-layer change.
- **`lib/cranlint.py`** — new pure-stdlib (no R) analysis module with three
  advisory checks wired into `r:cran-prep`: `lint_description` (DESCRIPTION
  incoming nits — non-`Authors@R`/no `cph`, weak `Title`, `Description` prose,
  stale `Date`), `check_build_hygiene` (planning/dev docs that would ship in the
  tarball, each with the exact `.Rbuildignore` regex to add), and
  `check_planning_consistency`. These surface as the `description`,
  `build-hygiene`, and `docs-consistency` stages and **never block** `ready`.
- **Tier 1b manual-build check** — `r:cran-prep` verifies the PDF reference
  manual builds; emits a `warn` (never a blocker) when LaTeX is absent.
- **Failure hint** on a strict-pass error: move the package to `Imports`, or
  guard with `requireNamespace()` in code AND `skip_if_not_installed()` in tests.
- **E2E regression proof** — `tests/fixtures/suggestbug.{before,after}` +
  `tests/test_regression_suggests_e2e.py` (opt-in via `RFORGE_E2E`) prove the
  noSuggests pass catches the medfit bug class with the real R toolchain.

### Changed

- `r:cran-prep` default sequence now includes `check (noSuggests)`,
  `check (suggests-only)`, `description`, `build-hygiene`, and `docs-consistency`
  (plus opt-in `check (incoming)` via `--incoming`).
- `r_snippet`/`run("check", …)` gained internal `flavor`/`incoming` selectors;
  `lib.rcmd` argparse gained `--incoming`.

---

## [2.2.0] - 2026-06-02

### Added

- **5 new `r:` CRAN-submission commands**: `r:revdep` (reverse-dependency check via `revdepcheck`), `r:goodpractice` (advisory best-practice bundle), `r:winbuilder` (async dispatch to win-builder via `devtools`), `r:rhub` (async dispatch to R-hub v2 via `rhub`), `r:cran-prep` (full CRAN-readiness gate: document→lint→spell→urlcheck→test→coverage→check(--as-cran)→revdep + generates `cran-comments.md` with a `ready`/`warn`/`blocked` verdict).
- **`r:check` NOTE classifier**: each R CMD check NOTE is now classified as `spurious` (expected on first CRAN submission) or `real` (needs attention) in the `notes_classified` field of the envelope.
- **`render_cran_comments`** pure-Python function in `lib/rcmd.py` generates `cran-comments.md` from check + revdep envelopes.
- **28 → 33 commands** total.
- **Tutorial**: `docs/tutorials/cran-submission-with-rforge.md` — per-package CRAN gate walkthrough.

### Changed

- `r:check`: envelope now includes `check.notes_classified` (list of `{text, kind, reason}` dicts).
- `lib/rcmd.py`: new CRAN-submission engine kinds (`revdep`, `goodpractice`, `winbuilder`, `rhub`, `cran-prep`); `OPTIONAL_ENGINES` and `INSTALL_HINT` extended; `_status_for` + `normalize` updated; `dispatched` status added for async kinds.

---

## [2.1.0] - 2026-05-31

### Added

- **`lib/rcmd.py`** — new pure-Python module that runs lower-level R engines (`rcmdcheck`, `pkgbuild`, `roxygen2`, `testthat`, `pkgload`, `covr`, `pkgdown`, `lintr`, `spelling`, `urlchecker`, `styler`) and normalizes JSON output to a common envelope. CLI: `python3 -m lib.rcmd --kind <kind> --path <path>`. Never uses `devtools`.
- **12 new `r:` commands** (`r:load`, `r:document`, `r:test`, `r:coverage`, `r:build`, `r:install`, `r:site`, `r:cycle`, `r:lint`, `r:spell`, `r:urlcheck`, `r:style`) — total 16 → **28** commands.
- **`r:cycle`** — orchestrates `document → test → check` in sequence, stopping at the first hard error.
- **`r:site`** flags: `--preview`, `--strict`, `--articles-only`, `--devel`.
- **`docs/reference/rcmd.md`** — auto-generated API reference for `lib/rcmd.py`.

### Changed

- **`r:check`** — retrofitted to drive its report from `python3 -m lib.rcmd --kind check`. No longer calls `R CMD check` directly.

---

## [2.0.0] - 2026-05-12

> **Breaking change:** 3 of 16 commands renamed to align with craft's hybrid
> namespacing. The other 13 commands are unchanged. See
> [`docs/migration/v2.0.0-rename.md`](docs/migration/v2.0.0-rename.md) for
> the full mapping table and a `sed` recipe to update local scripts.

### Changed (BREAKING)

- `/rforge:doc-check` → `/rforge:docs:check` — aligns with craft's `docs:` namespace.
- `/rforge:ecosystem-health` → `/rforge:health` — shorter daily-use name; no sub-namespace needed for a single command.
- `/rforge:rpkg-check` → `/rforge:r:check` — R-specific commands get an `r:` prefix.

### Added

- **`docs/migration/v2.0.0-rename.md`** — single-page migration tutorial with mapping table and POSIX `sed` recipes for macOS + Linux.
- **Rename-error stubs** at the 3 old filenames (`commands/doc-check.md`, `commands/ecosystem-health.md`, `commands/rpkg-check.md`). Typing an old name in Claude Code produces a verbatim error message pointing at the new name plus a link to the migration tutorial. Stubs ship through the v2.x line; slated for removal in v3.0.0.
- **`rename_stubs_present` test** in `tests/test-all.sh` — asserts each stub exists, retains its old slash-command name in frontmatter, contains a `RENAMED` marker, and references its new name. Wording-tolerant (key-string match, not exact prose).

### Internal

- New `commands/docs/` and `commands/r/` subdirectories for the renamed commands; explicit `name:` frontmatter added to the two files that lacked it (`commands/health.md` and `commands/r/check.md`) so the colon-namespaced names resolve.
- Cross-reference sweep across `docs/commands.md`, `docs/quickstart.md`, `docs/configuration.md`, the `description-sync` skill, `commands/complete.md`, and `commands/impact.md`.

---

## [1.3.0] - 2026-05-11

> **Path B complete** — `rforge-mcp` is fully absorbed into the plugin via
> pure-Python `lib/` ports. With this release, the plugin no longer has any
> runtime dependency on the MCP server. The `data-wise/rforge-mcp` repo will
> be archived separately post-merge per `docs/migration/v1.3.0-post-merge-checklist.md`.

### Added — Path B Phase B.1: discovery + deps ported to `lib/`

- **`lib/discovery.py`** — pure-Python R ecosystem detector. Walks the filesystem
  for `DESCRIPTION` files, classifies layouts as `single | ecosystem | hybrid`,
  preserves MCP-compatible `mode` field (`minimal | standard | full`) for
  side-by-side validation. Exposes `detect_ecosystem()` API and an
  `argparse` CLI (`python3 -m lib.discovery --path . --format {text,json}`).
- **`lib/deps.py`** — dependency-graph + impact analysis, ported from
  `rforge-mcp` `tools/deps/{deps,impact}.js`. Builds DAG from
  `Imports`/`Depends`/`Suggests`/`LinkingTo`, computes topological layers
  (leaves first), detects cycles, identifies blockers. `analyze_impact()`
  estimates direct/indirect dependents, risk level, work hours, and
  generates change-type-aware recommendations. CLI subcommands:
  `python3 -m lib.deps [--path .] [--format {text,json}] [graph|impact ...]`.
- **`tests/test_lib_discovery.py` + `tests/test_lib_deps.py`** — 32 pytest cases
  covering DESCRIPTION parsing edge cases (continuation lines, version
  constraints, `R` filtering), FS traversal (hidden-dir handling, no descent
  into packages), classification rules, graph construction, cycle detection,
  impact heuristics, and blockers.

### Added — Path B Phases B.2 + B.3: status + init ported to `lib/`

- **`lib/status.py`** — pure-Python port of `rforge-mcp`'s `status` tool. Reads
  `DESCRIPTION` + `.STATUS` files and computes ecosystem health score.
  Faithful port: same algorithm, same field names, no R subprocess. CLI:
  `python3 -m lib.status [--path .] [--format text|json]`. (B.2)
- **`lib/init.py`** — pure-Python port of `rforge-mcp`'s `init` tool. Writes
  `~/.rforge/context.json` (global per-user state, matches MCP). Idempotent.
  CLI: `python3 -m lib.init [--path .] [--quick] [--format text|json]`. (B.3)
- **`commands/init.md`** — first-class `/rforge:init` command (B.3 makes init
  a real, addressable tool).
- **`docs/reference/{status,init}.md`** — auto-generated API reference from
  module introspection; kept in sync by `scripts/gen_lib_reference.py --check`.

### Changed

- **`commands/detect.md`, `commands/deps.md`, `commands/impact.md`** — invoke
  the new `lib/` Python modules via Bash instead of the `rforge_*` MCP tools.
  Both subprocess CLI usage and Python API documented.
- **`commands/{status,quick,thorough}.md`** now dispatch
  `python3 -m lib.status` instead of the MCP tool. `thorough.md` simplified
  to point users at `R CMD check` / `devtools::test()` / `covr` directly.
- **`commands/analyze.md`** — last two inline `rforge_status` / `rforge_detect`
  references swapped for the `lib/` CLIs.
- **`scripts/gen_lib_reference.py`** now generates references for `lib.status`
  and `lib.init` alongside `lib.discovery` and `lib.deps`.
- **`tests/test-all.sh`**: `lib_pytest` and `lib_cli_smoke` runners now
  exercise all four `lib/` modules (discovery + deps + status + init). Total
  checks remain 23 — coverage grew within existing runners.

### Scope notes

- **Status port is faithful, not aspirational.** The original SPEC called for
  a 4-mode (default/debug/optimize/release) status contract with R subprocess
  support. Wave 1 research surfaced that the MCP server's `status` tool had
  no modes and ran no R subprocess — it's a `.STATUS` file reader with a
  health-score heuristic. The 4-mode design is descoped to v1.4.0 pending
  real-user input on what depth is wanted.
- **`mcpServers.rforge` cleanup.** Users with `~/.claude/settings.json`
  referencing the now-archived `rforge-mcp` binary should remove that entry
  manually. We don't auto-edit user settings.

### Removed

- N/A — the plugin no longer depends on `rforge-mcp` at runtime, but no
  rforge-side files are deleted in v1.3.0. (The `data-wise/rforge-mcp` repo
  itself is archived separately after this PR merges.)

### Notes

- Non-breaking: existing users with `rforge-mcp` installed keep working; new
  users get pure-Python analysis with no peer dependency.
- B.1 was validated side-by-side against MCP server output on the
  mediationverse ecosystem (5 packages); algorithmic parity confirmed.

---

## [1.2.0] - 2026-05-09

> **Note:** v1.2.0 was developed across multiple sessions on `dev`. The list
> below captures the full scope of the upcoming release, including post-merge
> polish (rename-debt cleanup, MCP decoupling, version-sync hardening). Tagged
> release date will reflect the final ship date.

### Changed — MCP server is now optional (decoupling)

- **`package.json`** — removed `peerDependencies.rforge-mcp`. The plugin no
  longer requires `rforge-mcp` to be installed. Existing users with the MCP
  server keep all functionality; new users can install plugin standalone via
  marketplace, npm, or Homebrew without hitting the long-standing 404 from
  `rforge-mcp` not being on the npm registry.
- **`README.md`** — "Part 1: Install RForge MCP Server" reframed as optional.
- Plugin commands work via Claude Code's built-in tools (Read, Bash, etc.).
  MCP integration provides typed I/O for users who want it; not required for
  core functionality.

### Changed — Rename debt cleanup (post-extraction)

- All user-facing install instructions now use the `rforge` formula and plugin
  name (was `rforge-orchestrator`, the pre-extraction monorepo name).
- All `Data-Wise/claude-plugins` URLs in current-install contexts replaced
  with `Data-Wise/rforge`.
- Plugin install path: `~/.claude/plugins/rforge` (was `rforge-orchestrator`).
- Migration section in `README.md` and `MCP-MIGRATION.md` retain the old name
  intentionally (documents the rename for users on the old install).
- `scripts/install.sh` + `scripts/uninstall.sh`: `PLUGIN_NAME` now `rforge`.
  Comments document the legacy `rforge-orchestrator` cleanup path.

### Changed — Version-sync hardening

- **`tests/test-all.sh`** — the `versions_match` test now asserts all 4 version
  sources agree: `plugin.json`, `marketplace.json/metadata`,
  `marketplace.json/plugins[0]`, `package.json`. Previously only the first two
  were compared; `package.json` drifted from 1.1.0 → 1.2.0 unnoticed in the
  initial PR. Negative-tested by injecting a fake mismatch.

### Fixed — broken internal links

- 9 broken internal links in `docs/` and `README.md` from the monorepo
  extraction (paths like `../../docs/MODE-USAGE-GUIDE.md`,
  `../../KNOWLEDGE.md`) removed. Documents that survived the extraction now
  link to surviving siblings only.

### Added — Craft-Parity Foundations (Phases 1 + 2)

Brings rforge's plugin architecture to parity with craft for the
foundation layers — installable via the Claude Code marketplace, hook-aware
on every Write/Edit, and shipping its first autonomous validation skill.

#### Marketplace + Config

- **`.claude-plugin/marketplace.json`** — enables one-shot install via
  `/plugin marketplace add Data-Wise/rforge`. Mirrors craft's structure.
- **`.claude-plugin/config.json`** — user-configurable options stub with
  R-specific defaults: `cran_mirror` (cloud.r-project.org), `vignette_engine`
  (knitr::rmarkdown), `r_version_pin` (>= 4.1.0), `claude_md_budget` (600).

#### R-Aware Hooks

- **`.claude-plugin/hooks/pretooluse.py`** — PreToolUse hook with four rules:
  - **Block** edits to roxygen-generated `man/*.Rd` files (exit 2).
  - **Warn** on `R/*.R` edits — reminder to keep NAMESPACE/DESCRIPTION in sync.
  - **Warn** when `DESCRIPTION` `Version:` isn't SemVer-compatible.
  - **Warn** on writes outside the current worktree (port of craft's rule).
- **`.claude-plugin/hooks/README.md`** — wiring + testing reference.

#### Skills Layer

- **`.claude-plugin/skills/validation/description-sync.md`** — first
  autonomous validator. Checks that `DESCRIPTION` `Version:` matches the
  top entry of `NEWS.md` / `CHANGELOG.md` and flags non-SemVer bumps.
  Pure shell — no R or devtools required.

### Changed

- **`plugin.json`** — version 1.1.0 → 1.2.0; description tightened.
- **`README.md`** — adds a marketplace install section.

### Notes

- Phase 3 (command namespacing, breaking) and Phase 4 (discovery engine)
  remain in separate worktrees.
- Pre-existing blocker `npm install` failing on `rforge-mcp@>=0.1.0` (404)
  is unrelated to this release and tracked separately.

---

## [1.1.0] - 2025-12-26

### Added - R Package Commands

Migrated R-specific commands from user commands into the plugin:

#### New Commands (2 total)
- **`/rforge:rpkg-check`** - Run R CMD check on package with smart output parsing
- **`/rforge:ecosystem-health`** - Check health across R package ecosystem

### Changed
- **Total commands:** 13 → 15
- **Plugin installed via symlink** for easier development

---

## [1.0.0] - 2024-12-23

### Added - Initial Release

#### Commands (13 total)
- **`/rforge:analyze`** - Quick analysis with auto-delegation (< 30 seconds)
- **`/rforge:quick`** - Ultra-fast analysis using only quick tools (< 10 seconds)
- **`/rforge:thorough`** - Comprehensive analysis with background R processes (2-5 minutes)
- **`/rforge:detect`** - Auto-detect R package project structure
- **`/rforge:deps`** - Build and visualize dependency graph
- **`/rforge:impact`** - Analyze change impact across ecosystem
- **`/rforge:cascade`** - Plan coordinated updates across packages
- **`/rforge:doc-check`** - Check documentation drift and inconsistencies
- **`/rforge:release`** - Plan CRAN submission sequence
- **`/rforge:capture`** - Quick capture ideas and tasks
- **`/rforge:complete`** - Mark tasks complete with documentation cascade
- **`/rforge:next`** - Get ecosystem-aware next task recommendation
- **`/rforge:status`** - Ecosystem-wide status dashboard

#### Agents
- **orchestrator** - Auto-delegation for RForge MCP tools

#### Features
- Auto-delegation to RForge MCP tools
- Parallel execution of multiple MCP calls
- Live progress updates
- Smart result synthesis
- ADHD-friendly output

---

## Version History Summary

| Version | Date | Major Changes |
|---------|------|---------------|
| **1.2.0** | 2026-05-09 | Marketplace install, R-aware PreToolUse hook, first validation skill |
| **1.1.0** | 2025-12-26 | Added rpkg-check and ecosystem-health commands |
| **1.0.0** | 2024-12-23 | Initial release: 13 commands, 1 agent |

---

**Last Updated:** 2026-05-09
**Maintained By:** Data-Wise
**License:** MIT

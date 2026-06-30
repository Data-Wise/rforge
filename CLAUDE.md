# rforge plugin — project-specific notes

> Local CLAUDE.md for the rforge Claude Code plugin.
> Follows the global `~/.claude/CLAUDE.md`; this file only captures
> rforge-specific patterns that don't apply to other dev-tools repos.

## Current state (2026-06-30)

**v2.18.0 (released — on `main`) — creative doc enhancements + CI/staleness fixes:** New in-site pages (changelog, glossary, command cards, contributor guide, example sessions, 404 page, decision tree diagram, social cards, symptom/fix admonitions). CI fix: removed `cache: pip` from `setup-python` (no `requirements.txt`); added `pillow`+`cairosvg` for social cards. Stale refs cleaned from `install.sh` and `package.json`. "Where rforge fits" diagram updated to teal/amber palette with diff-aware feedback loop. 41 commands (no surface change). pytest 524, test-all 44/44.

**v2.16.0 — pkgdown deploy leak guard (issue #52):** new public module `lib/sitelint.py` (`check_site_leaks` — scans the pkgdown render surface: root `*.md`, non-`.Rd` `man/`, `vignettes/` aggressively in `articles/**` with top-level rendered vignettes auto-trusted; minus core allowlist ∪ `.rforge.yaml` `site.allowlist`, path-aware; candidates from git HEAD ∪ working tree; advisory, never blocks). Three additive `r:site` flags: `--check-leaks` (read-only lint), `--deploy [--branch] [--force]` (clean-ref pkgdown deploy via `git worktree add -b <tmp> HEAD` — shares `.git`+remote so `deploy_to_branch` works **and** excludes untracked files; recommend-only, MUTATING+NETWORK). `r:cran-prep` gains a Tier-4 `site-leaks` advisory stage. 41 commands (no new command). Built spec→TDD (workflow)→C-RISK resolution (archive non-functional; worktree mandatory)→Phase-5 adversarial review (1 blocker + 3 important + minors, all fixed)→**end-to-end smoke test PASSED** (real build+push to a local bare origin; untracked scratch excluded — caught the `--detach`→named-branch deploy bug). pytest 510, test-all 44/44. Lesson [[feedback_smoke_test_mocked_network_paths]].

**v2.15.0 — `lib/rcmd.py` review remediation (P1–P4):** `--platforms` allow-list validation (closes an R-injection vector), bounded timeouts on the quick `Rscript` calls, `s7runtime` R extracted to a shipped `lib/r/s7runtime.R`, and `rcmd.py` split into internal `rsnippets`/`rhub` modules. No surface change (41 commands); CLI byte-identical. See CHANGELOG `[2.15.0]`.

**v2.13.0 — 41 commands, 1 agent.** Two diff-aware/ecosystem features:
**per-package diff-aware baseline caching** (`lib/changed.py`) — `r:check`/`r:test`/`r:lint --changed` cache the merge-base baseline **per package** under `~/.rforge/baseline-cache/`, keyed by `(repo, merge-base SHA, kind, package, engine flags)`; self-invalidating, LRU-20, `--no-cache` + `python3 -m lib.changed --clear-cache`. And **cross-package S7 contracts** (`lib/s7review.py`) — `r:s7-review --eco`'s `cross-package-contract` family (`cross_package_undeclared_contract` / `cross_package_unexported_class`; name-based, re-export-aware), the static sibling of v2.12.0's `method_undeclared_dependency`. B2 (full R6/S4 convention checking) **parked** — low ecosystem value. Pattern reinforced: [[feedback_adversarial_review_prose_contracts]].

### Release history — architecture deltas only (release mechanics live in CHANGELOG + git)

- **v2.18.0** — creative doc enhancements (changelog, glossary, command cards, contributor guide, example sessions, social cards, decision tree, symptom/fix admonitions, 404) + CI fix (`cache: pip` removed, pillow+cairosvg) + stale ref cleanup.
- **v2.17.0** — winbuilder fallback + tarball-check stage (medrobust v0.4.0 CRAN-prep).
- **v2.16.0** — pkgdown deploy leak guard (issue #52), `lib/sitelint.py`, `r:site --check-leaks/--deploy`.
- **v2.15.0** — `lib/rcmd.py` review remediation (P1–P4: injection vector fix, timeouts, module split).
- **v2.14.0** — CRAN gap-fill bundle (PR #47, G1–G8: DESCRIPTION Date/boilerplate/testthat-edition/doi-403 lints, `r:winbuilder --platform devel|release|oldrelease|all`, `--run-donttest`, sequential incoming, PDF-skip) + `r:rhub` overhaul (PR #48: explicit `platforms=`, no `rhub_setup()`, `_RHUB_PRESETS`, `--platforms`/`--preset`/`--rc-mode`) + docs audit/Command-Guides tier (`docs/guides/*`). test-all 43/43.

- **v2.12.0** — `commands.md` sync-gate (`tests/_check_commands_doc.py`); diff-aware `[uncommitted]` tag; `r:s7-review method_undeclared_dependency`.
- **v2.11.1** — `r:s7-review method_on_missing_class` (unreachable-method runtime finding; object-identity resolution).
- **v2.11.0** — diff-aware `[introduced]`/`[pre-existing]` tagging (merge-base detached-worktree baseline, `--fail-on`); `r:s7-review --eco`/`--runtime` (new `s7runtime` engine); `r:use-data`/`r:use-citation` (→41 commands).
- **v2.10.0** — `r:s7-review` (`lib/s7review.py`); scaffolding `r:use-test`/`use-package`/`use-vignette` (`lib/scaffold.py`); diff-aware `--changed` scope-only (`lib/changed.py`). 35→39 commands.
- **v2.9.0** — Phase 4 (last craft-parity item): `agents/orchestrator.md` rewrite to `python3 -m lib.*` delegation with a read-only-auto-run / recommend-only boundary + 3 agent guards.
- **v2.8.0** — single-source version/count: mkdocs-macros + `scripts/version_sync.py --check` gate (see Version sync).
- **v2.7.0** — `r:submit --universe` R-universe early-access (`lib/runiverse.py`; pure-stdlib, read-only).
- **v2.6.0** — `r:submit` GitHub pre-release + CRAN handoff (`lib/ghrelease.py`; never auto-submits).
- **v2.5.0** — `r:deps-sync` DESCRIPTION<->usage reconciliation (`lib/deps_sync.py`).
- **v2.4.0** — ecosystem-manifest discovery (`lib/discovery.py` reads `.rforge.yaml` `manifest:`).
- **v2.3.0** — CRAN-incoming hardening: `r:check --strict`/`--incoming` + `lib/cranlint.py` advisory stages.
- **v2.2.0** — 5 CRAN-submission commands + `r:check` NOTE classifier (`notes_classified`).
- **v2.1.0** — 12 `r:` dev-cycle + quality commands (`lib/rcmd.py`); `r:check` retrofitted onto it.
- **v2.0.0** — sub-namespacing (`docs:check`, `r:check`, `health`).
- **v1.3.0** — absorbed `rforge-mcp` into pure-Python `lib/*` (see "rforge-mcp is gone" below).

**Roadmap** (`.STATUS`): craft-parity **COMPLETE**; the pkgdown deploy leak guard (#52) shipped in v2.16.0. Open candidates (rforge-native, all low-priority): `contract_drift` (S7 cross-package 3rd family — candidate, deferred from v2.13.0 B1); full R6/S4 convention checking (B2 — parked); R-universe `sensitivity` follow-up (add to `data-wise.r-universe.dev` once public). Issues #9 (rename ergonomics — closed resolved-by-time 2026-06-21) and #46 (CRAN gap-fill — closed, shipped v2.14.0) are done. Cadence: approved spec → TDD → pre-merge adversarial review → end-to-end smoke test for network/deploy paths → release; multi-feature bundles built in one worktree by sequential implementer agents.

## Branch architecture

Multi-branch (craft-style): `main` (PR only) ← `dev` (integration) ← `feature/*` (worktrees for larger work). See global CLAUDE.md for the full pattern — rforge follows it exactly.

## Version sync (4 sources, no bump-version.sh)

Version bumps are manual edits across **4 files**:

- `.claude-plugin/plugin.json` → `"version"`
- `.claude-plugin/marketplace.json` → `metadata.version` AND `plugins[0].version` (both must match)
- `package.json` → `"version"`

After bumping, also update:

- `CHANGELOG.md` — convert `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
- Live-version doc refs in `docs/REFCARD.md` header, `docs/README.md` (Plugin Version, Documentation Version), tree-diagram comments showing "(vX.Y.Z)" in `README.md`, `docs/index.md`, `docs/README.md`, `docs/REFCARD.md`
- ASCII box version inside `docs/REFCARD.md` (easy to miss — the version sits between box-drawing characters)

`tests/test-all.sh` includes a "All 4 version sources agree" check — that gate must pass.

**As of v2.8.0 — `scripts/version_sync.py` propagates version + command_count.**
After bumping `package.json` `"version"` (the source of truth), run
`python3 scripts/version_sync.py` to sync the derived surfaces:
`mkdocs.yml` `extra.rforge.version`, `.claude-plugin/plugin.json` (`version` +
`NN commands` in `description`), `package.json` description count, `README.md`
footer + tagline, and the CLAUDE.md `## Command-file conventions (all NN commands)`
heading. `command_count` lives in `mkdocs.yml extra.rforge.command_count`
(hardcoded-for-v1, CI-validated). The mkdocs docs (REFCARD, index, installation,
tutorials, workflows) now render current version/count via `{{ rforge.version }}` /
`{{ rforge.command_count }}` macros — **do not hand-edit those**; bump the source
and re-run the script. `marketplace.json` version stays a manual edit (above).
`python3 scripts/version_sync.py --check` is wired into both `tests/test-all.sh`
and `.github/workflows/ci.yml` — CI fails on drift.

## lib/ Python package convention

The `lib/` directory is a Python package (has `__init__.py`). Modules use relative imports.

- **Run modules as a package**: `python3 -m lib.<module>` (e.g., `python3 -m lib.discovery`)
- **Never**: `python3 lib/<module>.py` — breaks relative imports
- **Public modules** (with `docs/reference/` pages): `discovery`, `deps`, `status`, `init`, `rcmd`, `cranlint`, `deps_sync`, `ghrelease`, `runiverse`, `s7review`, `changed`, `scaffold`, `sitelint`
- **R-universe module** (`runiverse`, v2.7.0): pure-stdlib (`urllib`-only, no R, no `gh`), like the analysis modules. Backs `r:submit --universe` — `verify()` reads the R-universe API and reports per-platform early-access build status; **read-only** (never uploads) and degrades to a `warn` envelope offline/unregistered (never raises).
- **CRAN-lint module** (`cranlint`, v2.3.0): pure-stdlib (no R), like the analysis modules. `lint_description`/`check_build_hygiene`/`check_planning_consistency`/`check_test_config`/`run_all` emit advisory envelopes; the first three wire into `r:cran-prep` as the `description`/`build-hygiene`/`docs-consistency` Tier 4 stages (never block `ready`); `check_test_config` wires into `r:test` as a pre-flight advisory. CLI: `python3 -m lib.cranlint <lint|build-hygiene|docs-consistency|check_test_config> <path>`. **G7 update protocol:** on each R major.minor release, audit R Internals §8 for new `_R_CHECK_*` env vars and update `_CRAN_CHECKS_REGISTRY` in `lib/rcmd.py` with a new versioned key (e.g. `"R4.6"`).
- **R-runner module** (`rcmd`, v2.2.0): unlike the analysis modules (pure-stdlib, no R), `rcmd` shells out to `Rscript` running lower-level R engines (`rcmdcheck`/`pkgbuild`/`roxygen2`/`testthat`/`pkgload`/`covr`/`pkgdown`/`lintr`/`spelling`/`urlchecker`/`styler`/`revdepcheck`/`goodpractice`/`rhub`) which emit JSON; it normalizes to one envelope. Backs the `r:` dev-cycle / quality / CRAN-submission commands. The `devtools` engine is used only by `r:winbuilder`.
- **Internal modules** (no reference page, subject to refactor): `formatters`, `rsnippets`, `rhub` — used from command prompts / `rcmd`; if importing externally, copy don't reuse. `rsnippets` (extracted v2.15.0) holds the R snippet builders (`r_snippet`, `_guard`, `_r_named_char`, `_r_version_key`) + CRAN env constants; `rhub` (extracted v2.15.0) holds the R-hub dispatch (`_RHUB_PRESETS`, `ALLOWED_RHUB_PLATFORMS`, `_check_rhub_yaml`, `_rhub_preflight`, `_run_rhub`). `rcmd` re-exports the rsnippets names it references and lazy-imports `rhub._run_rhub` inside `run()` to keep the module graph acyclic (`rcmd`→`rhub`→`rcmd` only inside functions).
- **`lib/r/*.R` script convention** (v2.15.0): long R programs that a snippet would otherwise embed as a Python f-string ship as real `.R` files under `lib/r/` and are `source()`d by the snippet (e.g. `lib/r/s7runtime.R` → `s7_runtime_report(pkg_path)`, sourced by `rsnippets.r_snippet("s7runtime", …)`). They ship in the package `files:` list (libexec) and are parse-checked in `tests/test-all.sh` (R-optional). Keep the script's return keys stable — the caller serializes them to the envelope verbatim.
- **Auto-generated reference docs**: `docs/reference/{discovery,deps,status,init,rcmd,cranlint,deps_sync,ghrelease,runiverse,s7review,changed,scaffold}.md` are produced by `scripts/gen_lib_reference.py`
- **CI gate**: `scripts/gen_lib_reference.py --check` compares regenerated output against committed files; any drift fails CI

## Command-file conventions (all 41 commands)

Every `commands/*.md` has structured frontmatter:

```yaml
---
name: rforge:<slash-path>
description: One-line description (appears in /help)
argument-hint: Plain-text hint (single string, optional)
arguments:
  - name: <flag>
    description: <what>
    required: false
    type: string | boolean
    default: ...
---
```

The `arguments:` array is the machine-readable spec; the `## Usage` body is the human equivalent. **Keep them in sync** when adding/removing flags.

**v2.0.0 rename-error stubs:** `commands/{doc-check,ecosystem-health,rpkg-check}.md` are stubs that emit a verbatim "Renamed to /rforge:..." message. Slated for removal in v3.0.0. Don't add normal command-file content to them.

## Test gates

Both must pass before any PR:

- `bash tests/test-all.sh` — **43 checks** (versions, hook compile + behavior, manifests parse, skills valid, lib pytest, lib CLI smoke incl. `rcmd`/`cranlint`/`runiverse`/`s7review`/`changed`, lib reference docs in sync, **version/count sync (`version_sync.py --check`)**, **commands.md sync (`_check_commands_doc.py`)**, **mkdocs nav integrity (every nav file exists + no orphaned guide/tutorial/reference page)**, rename stubs/targets, command-name uniqueness, migration recipe E2E, **agent guards: no `rforge_` MCP refs / orchestrator frontmatter / real `lib.rcmd` engines**)
- `python3 -m pytest tests/` — **400+ lib/\* cases** (discovery, deps, status, init, rcmd, cranlint, deps_sync, ghrelease, runiverse, s7review, changed, scaffold, **version_sync**)

## Homebrew tap quirks (rforge-specific)

`data-wise/tap/rforge` uses **dual stable + head** distribution (most tap plugins are stable-only). Manifest entry includes BOTH `version`/`sha256` AND `head:` so users can `brew install` (stable) or `brew install --HEAD` (track main).

After every `/craft:release` Step 10a:

1. `/craft:release` sed-edits `Formula/rforge.rb` with new url + sha256
2. **Also update** `~/projects/dev-tools/homebrew-tap/generator/manifest.json` (rforge entry) to match
3. Verify: `cd ~/projects/dev-tools/homebrew-tap && python3 generator/generate.py rforge --diff` → must report `IDENTICAL`

Failing to update the manifest creates drift — any later regeneration would strip the stable url+sha256.

## R-aware PreToolUse hook (`.claude-plugin/hooks/pretooluse.py`)

Diagnostic, not adversarial. Fires on every Write/Edit. 4 rules:

1. **BLOCK** hand-edits to `man/*.Rd` (regenerate via `devtools::document()`)
2. **WARN** on `R/*.R` edits (NAMESPACE/DESCRIPTION may need sync)
3. **WARN** on non-SemVer `DESCRIPTION` Version bumps
4. **WARN** on writes outside the active worktree

Only rule 1 blocks. Hook contract: reads JSON via stdin (NOT env vars). Tested by 7 cases in `tests/test-all.sh`.

## Docs conventions

- **Three doc tiers** (v2.13.0+): `docs/commands.md` (terse per-command, gated by `_check_commands_doc.py`) -> `docs/guides/*` (exhaustive per-family **Command Guides**) -> `docs/tutorials/*` (task walkthroughs). `test-all.sh` gates nav-orphans: every `docs/{guides,tutorials,reference}/*` page must appear in `mkdocs.yml` nav.
- **Material admonitions** for ADHD-friendliness: `!!! tip "TL;DR (30 seconds)"` on major pages; `!!! warning "Symptom"` + `!!! tip "Fix"` for troubleshooting pairs; `!!! note "Expected behavior in vX.Y.Z+"` for clarifying quirks. Don't write custom CSS — the Material palette covers note/tip/warning/danger/success/info/abstract.
- **Verification trap** when curl-grepping deployed pages: HTML entities + `<code>`-tag fragmentation + box-drawing characters all break naive regexes. If a deploy "looks broken," parse the `<article>` body with `re.sub(r'<[^>]+>', ' ', body)` before searching. Details in `reference_rforge_doc_conventions.md`.

## rforge-mcp is gone — don't reach for it

The `rforge-mcp` prototype was absorbed into the plugin in v1.3.0 via pure-Python `lib/` modules. It was a local-only working directory at `~/projects/dev-tools/mcp-servers/rforge/` — **never on GitHub, never on npm**. The `npm link` symlink was dropped 2026-05-11 and the source dir was tombstoned with `DEPRECATED.md`.

SPEC documents (e.g., `archive/specs/SPEC-mcp-absorb-2026-05-10.md`) reference `data-wise/rforge-mcp` as if it were public — those are historical artifacts, not action-guidance. See `docs/migration/v1.3.0-post-merge-checklist.md` for the rewritten "what archival actually meant" doc.

## Release pipeline observations

Per the global rules (see `## Pre-PR & Release Checklist` in `~/.claude/CLAUDE.md`), with these rforge-specific addenda:

- **Docs deploy on push to main is automatic** (`.github/workflows/docs.yml` triggers on `push: branches: [main]`). To force-deploy from `dev` between releases: `gh workflow run docs.yml --ref dev`.
- **No `bump-version.sh`** — manual 4-source edit per the version-sync section above.
- **Tap manifest sync** must follow every release per the Homebrew section above. Three gotchas (v2.16.0, see `reference_homebrew_tap_drift`): (1) the tap repo may be checked out on a *feature branch* — stash → `checkout main` → apply formula+manifest → push → restore the original branch; (2) `brew upgrade` can't run from the agent sandbox (no PTY) — verify via `brew audit` + raw formula + `generate.py --diff IDENTICAL`, then have the user run `brew upgrade` themselves; (3) `generate.py rforge --diff` is **IDENTICAL** again (the old bin.mkpath drift is resolved).
- **`Closes #N` needs the default branch.** Putting `Closes #N` in a `feature→dev` PR does NOT auto-close the issue (GitHub only auto-closes on merge to `main`). Either repeat the keyword in the `dev→main` release PR, or `gh issue close N` manually post-release — and verify issue state as a release-done check.
- **End-to-end smoke test for network/deploy paths.** Mocked unit tests validate intent, not integration (see `feedback_smoke_test_mocked_network_paths`). Before shipping a MUTATING+NETWORK path (e.g. `r:site --deploy`), run a real throwaway-repo smoke test (bare repo as origin).
- **GitHub Pages CDN** propagates in 30–90s for `meta` descriptions and most content; rarely longer.

## Memory pointers

For details not in this file, see project memory at `~/.claude/projects/-Users-dt-projects-dev-tools-rforge/memory/`:

- `reference_rforge_doc_conventions.md` — frontmatter standard, admonition palette, doc-gap audit recipe, verification gotchas
- `reference_homebrew_tap_drift.md` — manifest sync recipe + 6-surface drift inventory + release-time gotchas (tap-on-feature-branch, no-PTY brew, `Closes #N` auto-close)
- `feedback_smoke_test_mocked_network_paths.md` — mocks validate intent not integration; smoke-test MUTATING+NETWORK paths against a throwaway repo before done
- `reference_dotfiles_sync_workflow.md` — chezmoi for `~/.claude/`, flow-cli for `~/.config/zsh/`, `claude-sync` helper
- `project_rforge_mcp_never_public.md` — historical context for the v1.3.0 absorption
- `reference_brew_outdated_testing.md` — Cellar-rename trick for testing `brew outdated` UX

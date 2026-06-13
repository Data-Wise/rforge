# rforge plugin — project-specific notes

> Local CLAUDE.md for the rforge Claude Code plugin.
> Follows the global `~/.claude/CLAUDE.md`; this file only captures
> rforge-specific patterns that don't apply to other dev-tools repos.

## Current state (2026-06-13)

**v2.11.1 — in release** (feature/s7-method-missing-class → dev → main). **41 commands** (no surface change; patch). Closes the one runtime family deferred in v2.11.0: **`r:s7-review` `method_on_missing_class`**. Refuted the "not decidable from the registry alone" deferral empirically — each `S7_method` carries `attr(.,"signature")` (its dispatch class objects), so the `s7runtime` engine (`lib/rcmd.py`) flags a method whose dispatch class has **no resolvable namespace binding** (unreachable method, e.g. inline `new_class()` in a `method()` call); consumer in `lib/s7review.py` maps it into the `method-dispatch` family. Resolution is by **object identity** over the package's classes (not `@name` — the adversarial review caught a binding≠`@name` false positive on the idiomatic `Foo <- new_class("Bar")`); engine emits structured `{generic, class}` objects. Base types + imported classes guarded. Built TDD-first from `SPEC-s7-method-missing-class-2026-06-13.md` (autonomous, pre-approved), focused adversarial review (1 BLOCKER + 2 MINORs, all fixed + re-verified vs real R). pytest 349, test-all 41/41.

**v2.11.0 — released 2026-06-13** (PR #35 feature→dev merge 0f3f548, PR #36 dev→main merge 989eb23; [release](https://github.com/Data-Wise/rforge/releases/tag/v2.11.0); CI green on main RForge CI + Deploy Documentation; docs live-verified 41 commands + "NOT YET WIRED" gone + /reference/{s7review,scaffold}/ HTTP 200; tap PR Data-Wise/homebrew-tap#122 MERGED — formula+manifest → v2.11.0, sha256 196686eb…, desc 39→41, ruby -c OK, --diff only pre-existing bin.mkpath drift). **41 commands, 1 agent.** A three follow-up-feature bundle, each built TDD-first from an approved spec by sequential implementer agents in one worktree, then hardened by a 4-dimension pre-release adversarial review (caught 3 BLOCKERs + 3 IMPORTANTs the green gates missed — recurrence of the v2.10.0 doc-overclaim + spec-claims-unbuilt-mitigation classes; all fixed). **(1) diff-aware `[introduced]`/`[pre-existing]` tagging** (P0 completion) — `merge_base()`+`run_baseline()` in `lib/changed.py` run a baseline check in a detached worktree at `git merge-base(HEAD,--base)` (default `dev`, guaranteed `finally` cleanup), waking the dormant `scope_check()`; `rcmd.run_changed` wires it with a per-kind runner; new `--fail-on` (default `introduced`); line-shift-immune dict-finding identity; scope-only fallback preserved. **(2) `r:s7-review --eco`** (pure-stdlib ecosystem sweep via `discovery`) **+ `--runtime`** (new `s7runtime` engine in `lib.rcmd` — `pkgload::load_all` + S7 introspection; families `dead_generic` + `validator_not_enforcing`; `method_on_missing_class` deferred; SAFE_AUTORUN; degrades when R/S7 absent). **(3) `r:use-data` + `r:use-citation`** (+2 → 41 commands; `lib/scaffold.py`, citation re-emits `Authors@R` verbatim + `_r_string()`-escaped, deterministic year). pytest 347, test-all 41/41. Specs/plans: `SPEC-diff-aware-tagging`/`SPEC-r-s7-review-eco`/`SPEC-r-scaffolding-v2` (+ `PLAN-*`), all 2026-06-13.

**v2.10.0 — released 2026-06-13** (PR #32 bundle + #33 review fixes feature→dev, PR #34 dev→main merge e478fca; [release](https://github.com/Data-Wise/rforge/releases/tag/v2.10.0); CI green on main RForge CI + Deploy Documentation; docs live-verified v2.10.0 + new reference/tutorial pages HTTP 200; tap PR Data-Wise/homebrew-tap#121 MERGED — formula+manifest → v2.10.0, sha256 96ef1108…, ruby -c OK, --diff only pre-existing bin.mkpath drift). **Hardened by a pre-release adversarial review** that caught + fixed 3 bug-classes the gates missed (diff-aware `--changed` silent false-negative → honest scope-only; deps_sync `--write` constraint-drop; s7review false positives). pytest 298, test-all 41/41. — **39 commands, 1 agent**. A three-feature bundle, each built TDD-first from an approved spec: **`r:s7-review`** (#26, S7 convention checker — new pure-stdlib `lib/s7review.py`, `cranlint` archetype, 5 advisory families, `--eco`/R-pass deferred; +1); **scaffolding** (`r:use-test`/`r:use-package`/`r:use-vignette` for existing packages, dry-run default + `--write`, new `lib/scaffold.py`+`lib/usethis_infra.py`, reuses `deps_sync._apply_patch`/`scan_usage`; +3); **diff-aware `--changed`** (P0, new `lib/changed.py` — git-diff→changed-packages; flags on `r:check`/`r:test`/`r:lint`, `[introduced]`/`[pre-existing]` tagging, merge-base second-check deferred; +0). 35→39 commands; test-all 36→41; pytest 232→290. Built by 3 sequential implementer agents in one bundle worktree. Specs+plans: `SPEC-r-s7-review`/`SPEC-r-scaffolding`/`SPEC-diff-aware-checks-and-coverage` (+ `PLAN-*`).

**v2.9.0 — released 2026-06-12** (PR #29+#30 feature→dev, PR #31 dev→main merge c747b24; [release](https://github.com/Data-Wise/rforge/releases/tag/v2.9.0); CI green on main RForge CI + Deploy Documentation; docs live-verified v2.9.0 + /orchestrator/ HTTP 200; tap PR Data-Wise/homebrew-tap#120 MERGED — formula+manifest → v2.9.0, sha256 08c45b9b…, ruby -c OK, --diff shows only pre-existing bin.mkpath drift) — **35 commands, 1 agent** (no surface change). **Phase 4 — the last craft-parity item.** Rewrites `agents/orchestrator.md`, stale since v1.3.0: it delegated to 13 removed `rforge_*` MCP tools (43 refs) that vanished when rforge-mcp was absorbed into `lib/`. The rewrite delegates via `python3 -m lib.*` envelopes (Bash), with `name`/`description` frontmatter, an **intent→lib mapping** over 7 intents (CODE_CHANGE incl. `lib.deps impact`/NEW_FUNCTION/BUG_FIX/DEPS_AUDIT/QUALITY/CRAN_READINESS/ECOSYSTEM_HEALTH), a strict **read-only auto-run / recommend-only safety boundary** (mirrors never-auto-submit: every file-writing or network command — `document`/`cran-prep`/`style`/`submit`/`winbuilder`/`rhub`/`urlcheck`/`revdep`/`--write` — is recommended, never run), and per-module envelope synthesis. Three new `test-all.sh` guards (**33→36**) lock it in: a regression guard failing on any `rforge_`/`mcp__rforge` ref in `agents/*.md`, frontmatter presence, and a recipe validator asserting every auto-run `--kind` is a real **and safe-to-auto-run** `lib.rcmd` engine (rejects mutating kinds). Validated by a max-effort adversarial review workflow that caught 2 safety-boundary blockers in the first draft. Spec/plan: `SPEC-phase4-orchestrator-rewrite-2026-06-12.md` + `PLAN-…`.

**v2.8.0 — released 2026-06-12** (PR #27 feature→dev, PR #28 dev→main; [release](https://github.com/Data-Wise/rforge/releases/tag/v2.8.0); CI green on main RForge CI + Deploy Documentation; tap PR Data-Wise/homebrew-tap#119 MERGED — formula+manifest → v2.8.0, sha256 9dc3c5d2…, `--diff` shows only pre-existing `bin.mkpath` drift) — **35 commands** (no surface change). **Single-source-of-truth version/count for docs**, killing the drift that produced the 33→35 staleness: a **mkdocs-macros render layer** (`extra.rforge.{version,prev_version,release_date,command_count}`; ~10 user-facing docs render `{{ rforge.version }}`/`{{ rforge.command_count }}`) plus pure-stdlib **`scripts/version_sync.py`** that stamps the macro-unreachable surfaces (`plugin.json`/`package.json`/`README.md`/`CLAUDE.md`/`mkdocs.yml extra`); `--check` is a CI drift gate wired into `ci.yml` + `test-all.sh`. Bump `package.json` version → run `version_sync.py` (see Version sync section). Spec: `SPEC-mkdocs-version-macros-2026-06-12.md`.

**v2.7.0 — released 2026-06-11** (PR #24 feature→dev, PR #25 dev→main; [release](https://github.com/Data-Wise/rforge/releases/tag/v2.7.0); CI green on main RForge CI + Deploy Documentation; tap PR Data-Wise/homebrew-tap#115 MERGED — formula+manifest → v2.7.0, sha256 6c31a316…, --diff IDENTICAL) — 35 commands (count unchanged; a flag, not a
new command). Adds an **R-universe early-access tier** to `r:submit`: the new opt-in `--universe`
flag verifies the package's R-universe build (CRAN-like binaries built from GitHub within minutes)
so users can install the new version while CRAN's slower review runs in parallel. Backed by new
public pure-stdlib `lib/runiverse.py` (`urllib`-only, no `gh`/R). **Read-only** — R-universe builds
on `git push`, so it never uploads; R-universe status is **advisory** in the CRAN checklist and
never blocks the (still manual, never-automatic) CRAN handoff. Live-verified against the new
`data-wise.r-universe.dev` universe. Spec: `SPEC-r-submit-runiverse-early-access-2026-06-11.md`.

**v2.6.0 — released 2026-06-10** (PR #23; [release](https://github.com/Data-Wise/rforge/releases/tag/v2.6.0); CI green; tap PR #114 pending) — 35 commands. One release bundling four features accumulated on `dev` since v2.2.0 (each roadmapped as a separate minor, shipped together as v2.6.0):
- **v2.3.0 CRAN-incoming hardening** (PR #18): `r:check --strict` runs both
  Suggests-withholding flavors (`check (noSuggests)` + `check (suggests-only)`) with
  `--run-donttest`; `--incoming` adds the CRAN-incoming `_R_CHECK_*` bundle; `r:cran-prep`
  runs the strict passes **by default** and blocks `ready` on failure (behavior change).
  New pure-stdlib `lib/cranlint.py` adds advisory `description`/`build-hygiene`/
  `docs-consistency` stages. Spec: `SPEC-cran-incoming-hardening-2026-06-10.md`.
- **v2.4.0 ecosystem-manifest discovery** (PR #16 spec + #17 impl): `lib/discovery.py`
  optionally reads an ecosystem manifest (via `.rforge.yaml` `manifest:`) → enrich packages
  with role/repo/cran metadata + report drift. Follow-ups: issues #19, #20.
- **v2.5.0 `r:deps-sync`** (PR #21): new pure-stdlib `lib/deps_sync.py` — reconcile
  `DESCRIPTION` vs `R/`/tests/vignettes usage (missing/misclassified/missing_suggests/unused)
  + suggested patch (`--write`). 33→34 commands. The misclassified finding is the *static*
  sibling of `r:check --strict`'s noSuggests pass. Spec: `SPEC-r-deps-sync-2026-06-10.md`.
- **v2.6.0 `r:submit`** (PR #22): GitHub pre-release of the submitted tarball + CRAN submit
  handoff (never auto-submits); `--promote` flips to a full release on acceptance. Backed by
  pure-Python `lib/ghrelease.py` (`gh` soft-dep). 34→35 commands. Spec: `SPEC-r-submit-github-prerelease-2026-06-10.md`.

**v2.2.0 (released 2026-06-02)** — 33 commands. v2.2.0 adds 5 `r:` CRAN-submission commands (`r:revdep`/`r:goodpractice`/`r:winbuilder`/`r:rhub`/`r:cran-prep`) plus `r:check` NOTE classifier (`notes_classified` field). v2.1.0 added 12 `r:` dev-cycle + quality commands (`load`/`document`/`test`/`coverage`/`build`/`install`/`site`/`cycle` + `lint`/`spell`/`urlcheck`/`style`) backed by `lib/rcmd.py`; `r:check` retrofitted onto it. v2.0.0 (2026-05-12) introduced sub-namespacing (`docs:check`, `r:check`, `health`); v1.3.0 absorbed `rforge-mcp` into pure-Python `lib/*` modules.

**Roadmap** (`.STATUS`): v2.6.0 release in progress (bundles the four features above) → Phase 4 agents (post-v2.6.0, unspecced). Unscheduled candidates: diff-aware P0 (`--changed`), scaffolding theme (`r:use-test`/`r:use-package`/`r:use-vignette`, existing-only). Parked: Path B v1.4.0 (4-mode status). Plus issue #9 (rename-ergonomics watch).

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
- **Public modules** (with `docs/reference/` pages): `discovery`, `deps`, `status`, `init`, `rcmd`, `cranlint`, `deps_sync`, `ghrelease`, `runiverse`, `s7review`, `changed`, `scaffold`
- **R-universe module** (`runiverse`, v2.7.0): pure-stdlib (`urllib`-only, no R, no `gh`), like the analysis modules. Backs `r:submit --universe` — `verify()` reads the R-universe API and reports per-platform early-access build status; **read-only** (never uploads) and degrades to a `warn` envelope offline/unregistered (never raises).
- **CRAN-lint module** (`cranlint`, v2.3.0): pure-stdlib (no R), like the analysis modules. `lint_description`/`check_build_hygiene`/`check_planning_consistency`/`run_all` emit advisory envelopes wired into `r:cran-prep` as the `description`/`build-hygiene`/`docs-consistency` stages (never block `ready`).
- **R-runner module** (`rcmd`, v2.2.0): unlike the analysis modules (pure-stdlib, no R), `rcmd` shells out to `Rscript` running lower-level R engines (`rcmdcheck`/`pkgbuild`/`roxygen2`/`testthat`/`pkgload`/`covr`/`pkgdown`/`lintr`/`spelling`/`urlchecker`/`styler`/`revdepcheck`/`goodpractice`/`rhub`) which emit JSON; it normalizes to one envelope. Backs the 17 `r:` commands. The `devtools` engine is used only by `r:winbuilder`.
- **Internal module** (no reference page, subject to refactor): `formatters` — used from command prompts; if importing externally, copy don't reuse
- **Auto-generated reference docs**: `docs/reference/{discovery,deps,status,init,rcmd,cranlint,deps_sync,ghrelease,runiverse}.md` are produced by `scripts/gen_lib_reference.py`
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

- `bash tests/test-all.sh` — **36 checks** (versions, hook compile + behavior, manifests parse, skills valid, lib pytest, lib CLI smoke incl. `rcmd`/`cranlint`/`runiverse`, lib reference docs in sync, **version/count sync (`version_sync.py --check`)**, rename stubs/targets, command-name uniqueness, migration recipe E2E, **agent guards: no `rforge_` MCP refs / orchestrator frontmatter / real `lib.rcmd` engines**)
- `python3 -m pytest tests/` — **230 lib/\* cases** (discovery, deps, status, init, rcmd, cranlint, deps_sync, ghrelease, runiverse, **version_sync**)

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

- **Material admonitions** for ADHD-friendliness: `!!! tip "TL;DR (30 seconds)"` on major pages; `!!! warning "Symptom"` + `!!! tip "Fix"` for troubleshooting pairs; `!!! note "Expected behavior in vX.Y.Z+"` for clarifying quirks. Don't write custom CSS — the Material palette covers note/tip/warning/danger/success/info/abstract.
- **Verification trap** when curl-grepping deployed pages: HTML entities + `<code>`-tag fragmentation + box-drawing characters all break naive regexes. If a deploy "looks broken," parse the `<article>` body with `re.sub(r'<[^>]+>', ' ', body)` before searching. Details in `reference_rforge_doc_conventions.md`.

## rforge-mcp is gone — don't reach for it

The `rforge-mcp` prototype was absorbed into the plugin in v1.3.0 via pure-Python `lib/` modules. It was a local-only working directory at `~/projects/dev-tools/mcp-servers/rforge/` — **never on GitHub, never on npm**. The `npm link` symlink was dropped 2026-05-11 and the source dir was tombstoned with `DEPRECATED.md`.

SPEC documents (e.g., `docs/specs/SPEC-mcp-absorb-2026-05-10.md`) reference `data-wise/rforge-mcp` as if it were public — those are historical artifacts, not action-guidance. See `docs/migration/v1.3.0-post-merge-checklist.md` for the rewritten "what archival actually meant" doc.

## Release pipeline observations

Per the global rules (see `## Pre-PR & Release Checklist` in `~/.claude/CLAUDE.md`), with these rforge-specific addenda:

- **Docs deploy on push to main is automatic** (`.github/workflows/docs.yml` triggers on `push: branches: [main]`). To force-deploy from `dev` between releases: `gh workflow run docs.yml --ref dev`.
- **No `bump-version.sh`** — manual 4-source edit per the version-sync section above.
- **Tap manifest sync** must follow every release per the Homebrew section above.
- **GitHub Pages CDN** propagates in 30–90s for `meta` descriptions and most content; rarely longer.

## Memory pointers

For details not in this file, see project memory at `~/.claude/projects/-Users-dt-projects-dev-tools-rforge/memory/`:

- `reference_rforge_doc_conventions.md` — frontmatter standard, admonition palette, doc-gap audit recipe, verification gotchas
- `reference_homebrew_tap_drift.md` — manifest sync recipe + 6-surface drift inventory
- `reference_dotfiles_sync_workflow.md` — chezmoi for `~/.claude/`, flow-cli for `~/.config/zsh/`, `claude-sync` helper
- `project_rforge_mcp_never_public.md` — historical context for the v1.3.0 absorption
- `reference_brew_outdated_testing.md` — Cellar-rename trick for testing `brew outdated` UX

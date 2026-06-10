# SPEC: `r:submit` — GitHub pre-release + CRAN submit handoff

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-10
- **Target version:** v2.6.0 (after v2.5.0 `r:deps-sync`; roadmap: v2.3.0 cran-incoming → v2.4.0 ecosystem-manifest → v2.5.0 deps-sync → v2.6.0 r:submit)
- **Author:** brainstormed with Claude, grounded in r-pkgs + GitHub CLI docs
- **Related:** [SPEC-cran-incoming-hardening-2026-06-10.md](SPEC-cran-incoming-hardening-2026-06-10.md),
  [SPEC-r-cran-prep-2026-06-01.md](SPEC-r-cran-prep-2026-06-01.md), `commands/release.md`

## Summary

Add a per-package command, **`r:submit`**, that wraps the *moment of CRAN submission*: build
the exact source tarball, cut a GitHub **pre-release** of it (not marked "Latest"), attach
`cran-comments.md`, and hand off the actual CRAN submit step to the user with a checklist. A
second invocation, `r:submit --promote`, flips that pre-release to a full release once CRAN
accepts. This fills the gap between `r:cran-prep` (which reports "ready") and CRAN going live —
today rforge plans submission *order* (`/rforge:release`) and preps a package (`r:cran-prep`)
but has nothing for the *submission lifecycle* itself. Commands 33 → **34**.

## Motivation

CRAN review takes days to weeks and may bounce. During that window a maintainer often wants an
**installable, citable snapshot** of exactly what was submitted — but r-pkgs deliberately
advises tagging the GitHub release *after* acceptance, because resubmissions bump the version,
so a pre-acceptance *final* tag (`v0.2.1`) can end up pointing at code CRAN rejected
([r-pkgs §22 Releasing to CRAN](https://r-pkgs.org/release.html)). The resolution: cut a GitHub
**pre-release** (clearly not "Latest"), then **promote in place** on acceptance — which GitHub
CLI supports directly via `gh release edit <tag> --prerelease=false --latest`
([Managing releases — GitHub Docs](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)).
This gives the snapshot, a reproducible record of the submitted artifact, and a rollback point —
without the version-mismatch footgun.

## Goals

- From a `ready` package, build the submitted tarball and cut a GitHub **pre-release** of it,
  with `cran-comments.md` attached.
- Hand off the CRAN submit step with an exact command + checklist — **never auto-submit**.
- Promote the pre-release to a full release on acceptance, via an explicit second invocation.
- Degrade gracefully when `gh` is missing/unauthed (print a manual recipe).
- Keep `r:cran-prep` (is-it-ready), `r:submit` (ship the artifact + hand off), and
  `/rforge:release` (ecosystem order) as three clean, separable concerns.

## Non-goals

- **No auto-submit to CRAN.** Submitting is irreversible and outward-facing; `r:submit` prints
  the command and checklist for the user to run. No `devtools::submit_cran()` automation (also
  preserves the "no `devtools` for gate work" rule from `SPEC-r-cran-prep`).
- **No scraping CRAN for acceptance** beyond an *optional* version-on-CRAN check in Phase 2.
  Promotion is user-triggered (the maintainer has the acceptance email).
- **Not** the post-acceptance `usethis::use_dev_version()` bump or `use_github_release()` notes
  automation — possible extension, not v1.
- **Not** ecosystem sequencing — that stays in `/rforge:release`, which *hands off* to `r:submit`.

## Scope

### In scope (decided)

| Phase | Invocation | Behavior |
|---|---|---|
| 1 | `r:submit` | gate on `cran-prep` = `ready` → build tarball (reuse `r:build`) → `gh release create v<ver> --prerelease` + attach tarball + `cran-comments.md` → print CRAN submit command + checklist |
| 2 | `r:submit --promote` | (optional CRAN-page verify) → `gh release edit v<ver> --prerelease=false --latest` |
| — | `r:submit --dry-run` | show the tag, attachments, and submit checklist without touching GitHub |

### Out of scope (YAGNI / deferred)

- Auto-detecting acceptance / polling CRAN. (Optional one-shot version check only, Phase 2.)
- Rejection bookkeeping automation — on reject the user bumps + re-runs `cran-prep` + `r:submit`;
  the prior pre-release stays as a historical "rejected" marker (or is deleted manually).
- Multi-package submission in one call — `r:submit` is per-package; `/rforge:release` orchestrates.

## Architecture

`r:submit` is a markdown command (like all rforge commands), orchestrating existing pieces:

- **Tarball — reuse, don't rebuild.** Use the existing `lib/rcmd.py` build engine (the `r:build`
  / pkgbuild path) to produce the source tarball; `r:submit` attaches that artifact. No new build
  code.
- **Readiness gate — reuse the verdict.** Refuse (or loudly warn + require `--force`) to cut a
  pre-release unless `cran-prep` reports `ready`. Reuses the readiness envelope from
  `SPEC-r-cran-prep`; with cran-incoming hardening (v2.3.0) that verdict is already stricter.
- **GitHub — `gh` CLI, guarded.** Cut with
  `gh release create v<ver> --prerelease --title "v<ver> (submitted to CRAN)" --notes-file <cran-comments.md> <tarball>`;
  promote with `gh release edit v<ver> --prerelease=false --latest`
  ([create](https://cli.github.com/manual/gh_release_create),
  [managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)).
  A guard checks `gh auth status`; if `gh` is absent/unauthed, print the exact manual recipe
  instead of failing (mirrors how `r:winbuilder` degrades when its engine is absent).
- **Optional Phase-2 verify.** Before promoting, optionally fetch
  `https://cran.r-project.org/package=<pkg>` (or the CRANDB) to confirm `v<ver>` is live — a
  safety check in the spirit of the cran-incoming research-workflow. Skippable with `--no-verify`.

Data flow (Mermaid N/A — linear): `cran-prep ready → r:build tarball → gh pre-release (+cran-comments)
→ [user submits to CRAN] → r:submit --promote → gh full release`.

> **Tag convention (decided):** plain `v<version>` tag; the **prerelease flag** carries the
> "pending CRAN" semantics, and promotion flips that flag in place. No `-rc`/`-cran` suffix
> (a suffix would force a new tag on promotion). Alternative suffix scheme noted in Open questions.

## Dependencies

- **`gh` CLI (new external tool).** rforge shells only to `Rscript` today; `r:submit` adds `gh`.
  Guarded with `gh auth status` + manual-recipe fallback. No new R packages. **No `devtools`.**
- **Reuses** the existing `lib/rcmd.py` build engine and the `cran-prep` readiness envelope.

## Error handling

- `cran-prep` not `ready` → refuse to cut a pre-release; print the blocking reasons (require an
  explicit `--force` to override).
- `gh` missing/unauthed → no failure; emit the exact manual `gh`/web steps and a clear hint.
- Tarball build fails → surface the `r:build` error; do not touch GitHub.
- `--promote` when no matching pre-release exists, or version already live as a full release →
  `warn` with guidance, never a destructive action.
- Optional CRAN verify fails (version not yet visible) → `warn`, ask the user to confirm before
  promoting; never auto-promote past a failed verify.

## Testing

Both gates must pass (`python3 -m pytest tests/` and `bash tests/test-all.sh`). Since GitHub side
effects can't run in CI, **mock the `gh` boundary**:

- **Gate** — `cran-prep` not `ready` → `r:submit` refuses (asserts no `gh` call); `--force` overrides.
- **Pre-release command shape** — assert the constructed `gh release create` includes `--prerelease`,
  the `v<ver>` tag, the tarball, and `--notes-file cran-comments.md`.
- **Promote command shape** — assert `--promote` constructs `gh release edit v<ver> --prerelease=false --latest`.
- **gh-absent fallback** — mock `gh auth status` failure → asserts manual recipe printed, exit non-fatal.
- **Dry-run** — `--dry-run` performs no `gh` mutation; prints the plan.
- Command-name uniqueness + `arguments:`-frontmatter checks in `test-all.sh` cover the new command.

## Documentation impact

**Command frontmatter:** new `commands/r/submit.md` (`arguments:` for `--promote`/`--dry-run`/`--no-verify`/`--force`).

**Help / hub:** `docs/commands.md` (CRAN Submission section — add `r:submit` + the lifecycle),
`docs/REFCARD.md` (CRAN SUBMISSION box), `docs/index.md` + `docs/README.md` (command counts 33→34,
tree diagrams), root `README.md`, `docs/lib-modules.md` if any lib helper is added,
`docs/tutorials/cran-submission-with-rforge.md` (add the submit→pre-release→promote step),
`commands/release.md` (note the handoff to `r:submit`).

**Trackers:** `CHANGELOG.md` (`[Unreleased]`), `.STATUS`. Version sync → **v2.6.0** across the four
sources + live-version doc refs at release.

## Implementation order

1. *(docs — this spec, on `dev`)* — DONE on write.
2. *(code — feature worktree)* `commands/r/submit.md` Phase 1: gate + reuse `r:build` + `gh release create --prerelease` + checklist.
3. `gh` guard + manual-recipe fallback; `--dry-run`.
4. Phase 2 `--promote` (`gh release edit --prerelease=false --latest`) + optional CRAN verify.
5. Tests (both gates) with the `gh` boundary mocked.
6. Full doc sweep (help/hub) + CHANGELOG/.STATUS + v2.6.0 version sync.

> **Branch note:** steps 2–6 are code/command work → a `feature/r-submit` worktree off `dev`, fresh session.

## Open questions / risks

- **Command name.** ✅ *Resolved:* **`r:submit`** — the submit handoff + checklist is its center
  of gravity.
- **Version slot.** ✅ *Resolved:* **v2.6.0**, after `r:deps-sync` (v2.5.0). Phase 4 (agents)
  follows.
- **CRAN-page verify (Phase 2).** Include the optional `cran.r-project.org/package=<pkg>` check in
  v1, or defer? *Proposed:* include it behind `--no-verify` (cheap, high-confidence guard).
- **`gh` as a hard vs soft dep.** Soft (guarded + manual fallback) is chosen; revisit if real use
  shows the fallback is rarely useful.
- **Notes content.** Use `cran-comments.md` as the pre-release notes, or a dedicated submission
  note? *Proposed:* `--notes-file cran-comments.md` (single source of truth for "what was submitted").

## Sources

- [r-pkgs §22 Releasing to CRAN](https://r-pkgs.org/release.html) — tag/GitHub-release *after* acceptance; resubmissions bump the version (the anti-pattern this spec sidesteps).
- [GitHub CLI — `gh release create`](https://cli.github.com/manual/gh_release_create) — `--prerelease`, `--notes-file`, asset attachment.
- [Managing releases in a repository — GitHub Docs](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) — promote a prerelease in place via `gh release edit <tag> --prerelease=false`, and "Latest" semantics.
- rforge: `commands/release.md` (ecosystem sequencing), `SPEC-r-cran-prep-2026-06-01.md` (readiness envelope), `SPEC-cran-incoming-hardening-2026-06-10.md` (stricter `ready`).

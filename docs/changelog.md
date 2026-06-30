# Changelog

Release history for the RForge plugin.

The full changelog lives in the repository:
[`CHANGELOG.md`](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md).

---

## 2.17.0 — 2026-06-30

Winbuilder fallback + tarball-check stage. `r:cran-prep` gains a blocking
`tarball-check` stage, `check_build_hygiene` inspects the built tarball for
leaked artifacts, and `r:winbuilder` detects `lib.rcmd` availability,
falling back to `devtools::check_win_*()`. 41 commands.

## 2.16.0 — 2026-06-21

Pkgdown deploy leak guard (issue #52). New `lib/sitelint.py` —
`check_site_leaks` scans the pkgdown render surface; `r:site --deploy`
push-deploys `gh-pages` via a clean worktree. `r:cran-prep` Tier 4 gains
a `site-leaks` advisory stage.

## 2.15.0 — 2026-06-11

`lib/rcmd.py` review remediation (P1–P4): `--platforms` allow-list
validation, bounded timeouts, `s7runtime` R extracted to `lib/r/s7runtime.R`,
`rcmd.py` split into internal `rsnippets`/`rhub` modules. No surface change.

## 2.14.0 — 2026-06-07

CRAN gap-fill bundle (PR #47, G1–G8) + `r:winbuilder --platform` +
`r:rhub` overhaul (explicit `platforms=`, `_RHUB_PRESETS`) + docs audit.

## 2.13.0 — 2026-05-30

Diff-aware per-package baseline caching (`lib/changed.py`) and
cross-package S7 contracts (`lib/s7review.py --eco`). 41 commands.

## 2.12.0 — 2026-05-24

Commands.md sync-gate; diff-aware `[uncommitted]` tag; S7
`method_undeclared_dependency`.

## 2.11.x — 2026-05-22

Diff-aware `[introduced]`/`[pre-existing]` tagging; S7 `--eco`/`--runtime`
mode; `r:use-data`/`r:use-citation`. 41 commands.

## 2.10.0 — 2026-05-20

S7 review (`lib/s7review.py`); scaffolding commands (`r:use-test`,
`r:use-package`, `r:use-vignette`); diff-aware `--changed` scope.
35 → 39 commands.

## 2.9.0–2.1.0 — 2026-05

Phase 4 (craft-parity), version sync single-source, R-universe,
GitHub pre-release, deps-sync, ecosystem manifest, CRAN-incoming,
5 CRAN-submission commands, check NOTE classifier, 12 dev-cycle commands,
sub-namespacing.

## 2.0.0 — 2026-04

Sub-namespacing (`docs:check`, `r:check`, `health`).

## 1.3.0 — 2026-04

Absorbed `rforge-mcp` into pure-Python `lib/*` modules. No MCP server needed.

## 1.2.0–1.0.0 — 2026-03–2026-04

Initial plugin releases with MCP server architecture (deprecated).

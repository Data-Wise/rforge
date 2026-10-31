# PROPOSAL: v2.23 backlog and scope

**Status:** DRAFT, not applied. Written 2026-10-31 after v2.22.2 shipped (PR #119, tag v2.22.2, tap PR #248).
**For:** `~/projects/dev-tools/rforge`.
**Basis:** open GitHub issues (#73, #74, #98, #111, #112, #114), `PROPOSAL-fast-tier-and-test-profile.md`, the
`.STATUS` roadmap and the v2.22.2 release cycle. Issue bodies were read; code was not scoped, so sizes are estimates.

## TL;DR

- **Recommendation:** v2.23.0 is a focused site-audit release: **#111** (Quarto articles and pkgdown development-mode
  routes in `docs:check --site`) plus the **#114** decision as docs.
- **Why #111:** it has a real failing run behind it (medfit returns `audited: false`), it changes no command surface,
  and it unblocks #112.
- **Cost to plan for:** `lib/_docsite.py` is under the A2 gate, so expect a manifest refresh, fresh
  `a2-observations` and `a2-release` evidence at the candidate SHA, and a real-network smoke test.

## Candidates

| # | Item | Source | Size | Notes |
|---|------|--------|------|-------|
| 1 | Quarto articles and pkgdown development-mode routes in `docs:check --site` | #111 | M | `lib/_docsite.py` refuses `development.mode: auto` and any `.qmd` article; a real medfit run returned `audited: false`. No command-surface change. |
| 2 | Website audit, update, publish and verify skills/commands | #112 | L | Depends on #1. Adds commands, so the count-sync chain applies. Target the Claude side only: `CLAUDE.md` says not to grow the Codex adapter into website generation. |
| 3 | Decide whether `/rforge:finish` gets an opt-in `--pr` | #114 | S | A decision, not code. Option 1 (stay as is, point R users at `/craft:finish --pr`) keeps the deliberate "never commits" rule; option 2 adds a git-mutating path. |
| 4 | `--fast` tier and `--profile` for `r:test`, `r:check`, `r:cycle` | `PROPOSAL-fast-tier-and-test-profile.md` | M | Draft since 2026-10-11, not applied. Flags on existing commands, so the 44-command count stays. |
| 5 | Write submission status after `r:rhub` and `r:winbuilder` | #73 | S-M | Needs a state-file path and format decision. The consumer is a `cc-config` pacing-nudge hook, so the design spans two repos. |
| 6 | CI trigger hygiene across the R packages | #98 | M | Mostly work in other repos, each needing explicit per-instance permission; may fit better as an rforge check than as edits. |
| 7 | Shiny app lifecycle command family | #74 | L | New command family; no comments since 2026-08-04. Needs a brainstorm before a spec. |
| 8 | S7 `contract_drift` (third cross-package family) | `.STATUS` roadmap | M | Low priority, deferred from v2.13.0. R6/S4 convention checking stays parked; R-universe `sensitivity` waits until the site is public. |

## Maintenance (small, no release needed)

- Dependabot: confirm the next PR opens against `dev`; `target-branch` took effect only when v2.22.2 reached `main`.
- `macos-15` will itself retire: plan the next A2 migration before GitHub announces it.
- Codex adapter: a real-package `rforge-lint` CI-parity check; cause of "No description provided" for all three skills.
- `.STATUS`: two older entries still say the `rforge-lint` fresh-session check is unverified. They are history,
  superseded by the top entry.

## Proposed scope

| Release | Contents | Why |
|---------|----------|-----|
| v2.23.0 | #1 and #3 (as docs) | One theme; #1 is evidence-backed and unblocks #2 |
| v2.24.0 | #2, optionally #4 | Builds on #1; #4 is independent and can move earlier as a quick win |
| Decision first | #5, #6, #7 | Cross-repo or large, and not ready to spec |

## Cadence and risks

- Cadence: approved spec, TDD, pre-merge adversarial review, end-to-end smoke test for network paths, release.
- #1 needs a real-network smoke test (`--site` is a network path); mocks validate intent, not integration.
- A2: refresh the manifest with `env -u PYTEST_ADDOPTS ...`, then re-attest at the candidate SHA (about an hour of CI
  per attempt in v2.22.2). Batch changes before attesting.
- Dependabot PRs and the pytest pin (8.4.2) must stay compatible with the A2 manifest node IDs.

## Open questions

1. Does #1 ship alone, or with #4 as a quick win?
2. For #3, is "stay out of git" the intended long-term position for `/rforge:finish`?
3. For #5 and #6, which side owns the deliverable: rforge, `cc-config`, or each R package?

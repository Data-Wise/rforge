# PROPOSAL — Prevent pkgdown-deploy leaks of untracked files (rforge)

**Date:** 2026-06-21 · **Trigger:** medrobust manual `pkgdown::deploy_to_branch("gh-pages")`
published an untracked working-dir file (`PLAN-website-enhancements-2026-06-21.md` →
rendered to `.html`) to the public site. Cleaned after the fact via a temp gh-pages worktree.

## Root cause

1. **pkgdown renders *every* root-level `.md`** into an HTML page (not just README/NEWS) —
   so any stray `PLAN-*.md` / `ISSUE-*.md` / scratch note in the package root becomes a
   published page.
2. **`deploy_to_branch()` builds the working directory, not a clean ref** — so *untracked*
   and *uncommitted* root files are included. CI never hits this (it checks out the
   committed tree, where the file is untracked → absent).
3. **`.Rbuildignore` does NOT gate pkgdown** — it only affects `R CMD build`. A file
   ignored for the tarball is still rendered by pkgdown. (Easy to assume otherwise.)

→ Net: the safe-feeling "expedite publish" silently leaks local scratch docs.

## Quick Wins (< 30 min)

1. **Convention: working docs live in a gitignored *subdir*, never the root.** pkgdown
   only scans the root for stray `.md`; a `dev-diagnostics/` or `dev-docs/` subdir is
   never rendered. medrobust already has gitignored `dev-diagnostics/` — move
   `PLAN-*/ISSUE-*/START-HERE*` there. **(Recommended — zero tooling, kills the class.)**
2. **Doc the gotcha in `commands/r/site.md`** — one callout: "manual deploy publishes
   untracked root files; commit/stash/clean first, or let CI publish."

## Medium Effort (1–2 hrs)

3. **`rforge:r:site --deploy` with a clean-tree guard.** Today `r:site` builds (+ optional
   preview) but has no deploy path. Add `--deploy` that, before deploying:
   - aborts if `git status --porcelain` shows untracked/modified files pkgdown would
     render (root `*.md` not in a known allowlist: README, NEWS, LICENSE, ...);
   - prints a "**files pkgdown will publish**" preview (esp. flagging non-standard root
     `.md`) and requires confirmation.
4. **`rforge:r:site` preflight lint** (no deploy) — same "stray root `.md`" detector,
   runnable standalone, so it catches the problem at build time too.

## Long-term (most robust)

5. **Deploy from a clean ref, not the working dir.** Wrap deploy to build from
   `git archive HEAD` (or a fresh worktree at HEAD) → structurally impossible to publish
   untracked/uncommitted files. This is the real fix; #1–#4 are guards around the same
   hole. Mirrors how CI already behaves.
6. **Branch-protect `gh-pages`** (no force-push by humans) + CI-only deploy policy, so the
   manual path is reserved for true emergencies.

## Is it an rforge issue?

**Yes — file it.** rforge owns the R-package site lifecycle (`rforge:r:site`) and already
standardizes build/preview; deploy + its guardrails are the missing piece. #5 (build from
HEAD) is the headline feature; #1 is the immediate convention fix that needs no code.

## Recommended sequence

→ **#1 now** (move scratch docs to a gitignored subdir — kills the leak class today),
then **file an rforge issue for #5** (clean-ref deploy) with #3/#4 as the user-facing
surface. #2 lands alongside whichever ships first.

---
*Connects to:* medsim (release cascade on CRAN acceptance) · mediationverse (cross-links live).
*Saved here because the durable fix belongs in rforge (`commands/r/site.md`).*

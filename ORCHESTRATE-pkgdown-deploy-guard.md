# ORCHESTRATE: pkgdown clean-ref deploy guard (v2.16.0, issue #52)

> **Working artifact** — lives on `feature/pkgdown-deploy-guard` only. Delete before the
> feature→dev merge (per global CLAUDE.md). Source of truth for the build is
> `docs/specs/SPEC-pkgdown-clean-ref-deploy-2026-06-21.md` (Status: In Progress).

- **Branch:** `feature/pkgdown-deploy-guard`
- **Worktree:** `~/.git-worktrees/rforge/feature-pkgdown-deploy-guard`
- **Base:** `dev` @ synced (refined SPEC present)
- **Target:** v2.16.0 · 41 commands stay 41 (additive flags only)
- **Cadence:** approved SPEC → TDD → sequential implementer agents → pre-release adversarial review → release

## ⛔ Session boundary

This plan was authored from the **main-repo session** (CWD-pinned to `dev`). **Do not implement
from there.** Start a fresh session in the worktree:

```bash
cd ~/.git-worktrees/rforge/feature-pkgdown-deploy-guard && claude
```

Everything below runs in that worktree session.

## Decisions (locked — see SPEC § Resolved design decisions)

| Axis | Choice |
|------|--------|
| Module | new `lib/sitelint.py` (public; reference page) |
| Clean ref | `git archive HEAD \| tar -x` → tempdir (no `.git`, no cleanup) |
| Allowlist | fixed core (`README`,`NEWS`,`LICENSE`/`LICENCE`,`CHANGELOG`,`index`,`cran-comments`) ∪ `.rforge.yaml` `site.allowlist` (via `lib.discovery`) |
| Gate | hard-abort on non-allowlisted tracked hit + `--force` override |
| Lint scope | root `*.md` + `man/` (non-`.Rd`) + `vignettes/` (non-vignette) |
| Wiring | standalone `--check-leaks` + `r:cran-prep` Tier-4 advisory |
| Deploy target | `--branch` (default `gh-pages`) |

## Gates (both green before PR)

- `python3 -m pytest tests/`
- `bash tests/test-all.sh`
- `python3 scripts/gen_lib_reference.py --check` (clean)
- `python3 scripts/version_sync.py --check` (clean after bump)

---

## Phase 0 — docs callout (no worktree code; safe anywhere)

- [ ] **S1.** `commands/r/site.md`: add a `!!! warning` callout — "pkgdown renders every root
  `.md`; manual `deploy_to_branch()` publishes untracked files; use `r:site --deploy` (clean
  ref) or let CI publish." No flag wiring yet.

## Phase 1 — leak detector (TDD-first) → Agent A

**Subgoal:** `lib/sitelint.py` with `check_site_leaks(path)` + CLI, fully tested, no command wiring.

- [ ] **A1.** Write failing pytest first (`tests/test_sitelint.py`): allowlist hits;
  tracked/untracked/modified tagging via `git status --porcelain`; scope (root+`man/`+`vignettes/`);
  case-insensitive `LICENCE`; `index.md` allowed; `.rforge.yaml` `site.allowlist` override;
  malformed `.rforge.yaml` → fallback (warn, no crash); git-absent degrade.
- [ ] **A2.** Implement `lib/sitelint.py` (archetype: `lib/cranlint.py`; pure-stdlib; relative
  imports; reuse `lib.discovery` for `.rforge.yaml`). CLI: `python3 -m lib.sitelint <path>`.
- [ ] **A3.** Fixtures: temp pkg dir with `README.md` + tracked `PLAN-scratch.md` + untracked
  `NOTES.md`; assert both flagged with correct status; assert `site.allowlist: [PLAN-scratch.md]`
  clears the tracked hit.
- [ ] **A4.** Green: `pytest` for the new module.

**Report:** module path, public function signature, envelope keys, test count delta.

## Phase 2 — wire `--check-leaks` + cran-prep stage → Agent B (after A)

**Subgoal:** read-only surfaces consume the detector.

- [ ] **B1.** `commands/r/site.md`: add `--check-leaks` to `arguments:` + `argument-hint`;
  Process block calls `python3 -m lib.sitelint`. Read-only → auto-runnable.
- [ ] **B2.** `r:cran-prep` Tier 4: add `check_site_leaks` as an advisory stage (envelope merged;
  **never blocks `ready`**); update `commands/r/cran-prep.md`.
- [ ] **B3.** Gates: `pytest` + relevant `test-all.sh` checks (command-doc sync).

**Report:** flags added, cran-prep stage id, any `ready`-path regression check.

## Phase 3 — `--deploy` clean-ref path → Agent C (after A; independent of B)

**Subgoal:** the headline structural fix.

- [ ] **C1.** New deploy path in `lib.rcmd` (mutating + network kind; **recommend-only**, never
  in SAFE_AUTORUN). Flow: `check_site_leaks` → hard-abort on non-allowlisted tracked hit
  (with `--force` override) → `git archive HEAD | tar -x` into tempdir → run
  `pkgdown::deploy_to_branch(branch=<--branch default gh-pages>)` inside the archived tree →
  print "files pkgdown will publish" preview.
- [ ] **C2.** `commands/r/site.md`: add `--deploy`, `--branch`, `--force` to `arguments:` +
  `argument-hint` + Usage.
- [ ] **C3.** Error envelopes: `git archive` fail → refuse (never deploy working dir);
  `pkgdown` missing → existing 🟡; `--force` downgrades block→warn.
- [ ] **C4.** Tests: deploy path is network/mutating — test the **pre-deploy gate + archive
  construction** in isolation (mock the actual `deploy_to_branch`); do not perform a real push.
- [ ] **⚠️ C-RISK.** Validate `git archive` (no `.git`) against a **real pkgdown build** — confirm
  whether last-modified dates / "edit this page" links degrade. If material: document the tradeoff
  or switch to `git worktree add` at HEAD (SPEC-sanctioned fallback). Surface the finding; do not
  silently pick.

**Report:** deploy flow, gate behavior, the C-RISK finding (archive vs worktree verdict).

## Phase 4 — docs + version + reference (after B & C) → Agent D

- [ ] **D1.** `scripts/gen_lib_reference.py`: add `lib.sitelint` to the public set; regenerate
  → `docs/reference/sitelint.md`; `--check` clean.
- [ ] **D2.** `docs/guides/*` site-family guide + REFCARD flag list; mkdocs nav (no orphans).
- [ ] **D3.** Version bump to 2.16.0 across the 4 sources + `scripts/version_sync.py`; CHANGELOG
  `[Unreleased]`→`[2.16.0]`; CLAUDE.md public-module list (+`sitelint`) + test-gate counts; `.STATUS`.
- [ ] **D4.** Full gates green: `pytest`, `test-all.sh`, `gen_lib_reference.py --check`,
  `version_sync.py --check`.

## Phase 5 — pre-release adversarial review (REQUIRED, parent session)

Per [[feedback_adversarial_review_prose_contracts]] — green gates are necessary, not sufficient.
Run a **multi-agent adversarial Workflow** (not `/orchestrate`) before declaring done. Dimensions:

1. **Clean-ref correctness** — can an untracked/uncommitted file still reach the published site?
   (the whole point of #52). Try to defeat the archive boundary.
2. **Gate bypass** — does `--force` or an allowlist edge (case, subdir, symlink) leak a stray file?
3. **cran-prep safety** — can the new Tier-4 stage flip a previously-`ready` verdict? (must not).
4. **Envelope/recommend-only** — is `--deploy` ever auto-runnable by the orchestrator? (must not).

Bake any finding into a test gate before merge.

## Definition of done

- [ ] All gates green (4 listed above).
- [ ] Adversarial review clean (findings fixed + regression-tested).
- [ ] `ORCHESTRATE-pkgdown-deploy-guard.md` **deleted** (this file) before the feature→dev PR.
- [ ] PR `feature/pkgdown-deploy-guard → dev`; SPEC status Draft-marker → Shipped on release.

---
*Authored from the main-repo session; implementation must begin in the worktree session.*

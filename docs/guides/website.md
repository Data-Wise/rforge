# 🌐 Package website (`r:site`) + deploy leak guard

!!! tip "TL;DR (30 seconds)"
    - **What:** `r:site` builds the [pkgdown](https://pkgdown.r-lib.org/) website
      (vignettes → articles), previews it, and — as of v2.16.0 — **deploys** it safely.
    - **The trap:** pkgdown renders **every** root-level `.md` (not just README/NEWS), and a
      manual `pkgdown::deploy_to_branch()` builds your *working directory* — so a stray
      `PLAN-*.md` / `ISSUE-*.md` scratch file gets published to your public `gh-pages`.
    - **The guard:** `--check-leaks` flags strays before they ship; `--deploy` builds from a
      **clean `HEAD` checkout** so untracked/uncommitted files are structurally excluded.
    - **Next:** run `r:site --check-leaks` any time; use `r:site --deploy` instead of a manual
      `deploy_to_branch`.

---

## What this command covers

This is the **Command Guide** for `r:site` — build, preview, leak-detection, and clean-ref
deploy. The leak detector is also wired into `r:cran-prep` as a Tier-4 advisory stage.

`r:site` shells out to `pkgdown` (via `lib.rcmd`); the leak detector is pure-stdlib
(`lib.sitelint`, no R). The flags **compose** with the build flags.

| Mode | Flag | Engine | Does |
|---|---|---|---|
| Build (default) | *(none)* | `pkgdown` via `lib.rcmd` | validate (`pkgdown_sitrep`) then build the site |
| Preview | `--preview` | `pkgdown` | open the built site locally |
| Strict | `--strict` | `pkgdown` | fail-fast config check (`check_pkgdown`) for CI |
| Articles only | `--articles-only` | `pkgdown` | rebuild only vignettes/articles (reinstalls first) |
| Devel | `--devel` | `pkgdown` | fast in-process build via `load_all` (lower fidelity) |
| Leak lint | `--check-leaks` | pure-stdlib `lib.sitelint` | list stray files pkgdown would publish (read-only) |
| Deploy | `--deploy [--branch] [--force]` | `pkgdown` via clean-ref worktree | safe deploy to `gh-pages` (MUTATING + NETWORK) |

---

## The leak problem

pkgdown's render surface is wider than people expect, and `.Rbuildignore` does **not** gate it
(that only affects `R CMD build`). Two failure modes:

1. **Manual `deploy_to_branch()`** builds the *working directory* → publishes **untracked /
   uncommitted** root files. (Seen in the wild: a scratch `PLAN-website-enhancements-*.md`
   rendered to `.html` and force-pushed to a public `gh-pages`.)
2. **CI deploy** builds the committed tree → publishes any **tracked** scratch doc in root
   (`PLAN-*.md`, `ISSUE-*.md`, `START-HERE-*.md`).

!!! warning "Symptom"
    A scratch planning note appears as a published page on your package's public website.

!!! tip "Fix"
    Use `r:site --check-leaks` to catch strays, and `r:site --deploy` (clean-ref) instead of a
    manual `pkgdown::deploy_to_branch()`. Keep working docs in a gitignored subdir
    (e.g. `dev-diagnostics/`) — pkgdown only scans the package root and standard render dirs.

---

## `--check-leaks` — the detector

`r:site --check-leaks` scans the pkgdown render surface and flags non-allowlisted files:

- **Scope:** root `*.md`, non-`.Rd` files in `man/`, and `vignettes/` — **aggressively** in
  `vignettes/articles/**` (the web-only convention, prime scratch territory), while top-level
  rendered vignettes (`.Rmd`/`.qmd`/`.Rnw`/`.Rmarkdown`) are **auto-trusted**.
- **Allowlist:** a fixed core set (`README`, `NEWS`, `LICENSE`/`LICENCE`, `CHANGELOG`, `index`,
  `cran-comments`) **∪** a per-package `.rforge.yaml` `site.allowlist` (path-aware — a bare entry
  means the root file, a `dir/name` entry means that exact path).
- **Status tags:** each hit is tagged `tracked` / `untracked` / `modified` / `ignored` from
  `git` (HEAD ∪ working tree), so you can tell a committed scratch doc from a local-only one.

Every finding is **advisory** (`severity: "advisory"`) — the lint never blocks, and the same
check runs inside `r:cran-prep` as a Tier-4 stage that can never flip a `ready` verdict.

```yaml
# .rforge.yaml — permit intentional non-standard site files
site:
  allowlist:
    - ROADMAP.md            # an intentional root page
    - vignettes/articles/faq.Rmd
```

---

## `--deploy` — clean-ref deploy

`r:site --deploy` is the safe replacement for a manual `deploy_to_branch()`. It is
**MUTATING + NETWORK** (it pushes to a remote branch) and is **recommend-only** — agents never
auto-run it.

What it does, in order:

1. **Leak gate** — runs `--check-leaks` first and **hard-aborts** if a non-allowlisted file is
   present in `HEAD` (i.e. would actually publish). `--force` overrides the abort after printing
   the preview.
2. **Clean ref** — materializes a `git worktree add -b <tmp> HEAD` checkout (a named temp
   branch). This both (a) shares the repo's `.git` + remote so `pkgdown::deploy_to_branch()` can
   actually push, and (b) contains only committed files, so untracked working-dir files are
   **structurally excluded**.
3. **Publish preview** — prints the files pkgdown will publish before deploying.
4. **Deploy** — runs `deploy_to_branch(branch=<--branch, default gh-pages>)` inside the clean
   worktree, then cleans up the worktree and temp branch.

!!! note "Why a worktree, not `git archive`?"
    `deploy_to_branch` drives the package's *own* git repo (`checkout --orphan` / `remote` /
    `fetch` / `push`). A `git archive` tempdir has no `.git` or remote, so deploy would fail at
    the first git call. A linked worktree at `HEAD` is the mechanism that both works **and**
    excludes untracked files. (The worktree must be on a **named** temp branch, not `--detach` —
    `deploy_to_branch` returns to `git_current_branch()`, which a detached HEAD lacks.)

```bash
# safe deploy to gh-pages (aborts on a committed stray file)
python3 -m lib.rcmd --kind deploy --path . --branch gh-pages
# or, from the command surface:
#   /rforge:r:site --deploy
#   /rforge:r:site --deploy --branch gh-pages --force   # override the leak gate
```

!!! warning "Recommend-only"
    `--deploy` pushes to a public branch. The orchestrator agent will **recommend** it but never
    run it, and `python3 -m lib.rcmd --kind deploy` is deliberately absent from every auto-run
    enumeration.

---

## Related

- `r:cran-prep` — runs the `site-leaks` detector as a Tier-4 advisory stage.
- Doc conventions — see the repo `CLAUDE.md` (admonition palette + version-sync rules these pages follow).

---
name: rforge:r:site
description: Build the pkgdown website (vignettes→articles); optional preview
argument-hint: "[package] [--preview] [--strict] [--articles-only] [--devel] [--check-leaks] [--deploy] [--branch gh-pages] [--force]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: preview
    description: Open the built site (pkgdown::preview_site)
    required: false
    type: boolean
    default: false
  - name: strict
    description: Fail-fast config check (check_pkgdown) for CI
    required: false
    type: boolean
    default: false
  - name: articles-only
    description: Build only articles/vignettes (reinstalls first)
    required: false
    type: boolean
    default: false
  - name: devel
    description: Fast in-process build via load_all (lower fidelity)
    required: false
    type: boolean
    default: false
  - name: check-leaks
    description: Read-only preflight (lib.sitelint) — flag stray scratch files pkgdown would publish; no build
    required: false
    type: boolean
    default: false
  - name: deploy
    description: Deploy from a clean ref (git archive HEAD) via pkgdown::deploy_to_branch — MUTATING + NETWORK, recommend-only (never auto-run)
    required: false
    type: boolean
    default: false
  - name: branch
    description: Target branch for --deploy
    required: false
    type: string
    default: gh-pages
  - name: force
    description: Override the --deploy leak gate — proceed despite non-allowlisted committed files (downgrades block→warn)
    required: false
    type: boolean
    default: false
---

# R Package Website

!!! warning "pkgdown publishes every root `.md` — including scratch files"
    pkgdown renders **every** top-level `.md` (not just `README`/`NEWS`), so a stray
    `PLAN-*.md`, `ISSUE-*.md`, or `START-HERE-*.md` in the package root gets built to
    `.html` and published. `.Rbuildignore` does **not** gate this — it only affects
    `R CMD build`. A manual `pkgdown::deploy_to_branch("gh-pages")` builds the **working
    directory**, so it also publishes **untracked/uncommitted** files. To avoid leaking
    scratch docs: deploy from a clean ref via `r:site --deploy` (builds `git archive HEAD`,
    structurally excluding untracked files) or let CI publish the committed tree. Use
    `r:site --check-leaks` to surface stray docs (tracked or not) before deploying.

Validate (`pkgdown_sitrep`, or `check_pkgdown` with `--strict`) then build the site.
`pkgdown` is optional — if `engine_missing` includes `pkgdown`, report 🟡 + hint.
Needs `pandoc` to render vignettes; if absent, report 🟡 with the pandoc hint.

## Process

```bash
python3 -m lib.rcmd --kind site --path "<path>"   # + --preview / --strict / --articles-only / --devel
```

With `--check-leaks`, **skip the build** and run the read-only leak preflight
instead (pure-Python, no R — auto-runnable):

```bash
python3 -m lib.sitelint "<path>"
```

It scans the pkgdown-rendered surface (root `*.md` + non-`.Rd` `man/` +
non-vignette `vignettes/`), subtracts the core allowlist ∪ `.rforge.yaml`
`site.allowlist`, and tags each stray hit `tracked`/`untracked`/`modified`
(or `ignored`; `null` when git is absent). Advisory only — emits `ok`/`warn`,
never blocks, exit 0. Surface each finding + the move/allowlist/remove hint.

### `--deploy` (clean-ref deploy — MUTATING + NETWORK, recommend-only)

!!! danger "Never auto-run — always recommend the command, let the user run it"
    `--deploy` pushes to a remote branch (`pkgdown::deploy_to_branch`). It is
    **recommend-only**: the orchestrator/agent must surface the command, never
    execute it automatically.

```bash
python3 -m lib.rcmd --kind deploy --path "<path>" [--branch gh-pages] [--force]
```

Flow (issue #52):

1. Run `lib.sitelint.check_site_leaks` first.
2. **Hard-abort** (`status: blocked`) if any non-allowlisted file is **in HEAD**
   (`git_status` `tracked`/`modified`) — it would be published. Untracked files
   are ignored here (they cannot reach the archive). `--force` downgrades the
   block to `warn` and proceeds after printing the publish preview.
3. Build a clean ref with `git archive HEAD | tar -x` into a **tempdir** (not the
   working dir) — so untracked/uncommitted files are structurally excluded. If
   `git archive` fails (not a repo, no commits), the deploy is **refused**
   (`warn`) — it never silently builds the working directory.
4. Run `pkgdown::deploy_to_branch(branch=<--branch, default gh-pages>)` **inside**
   the archived tree.
5. The envelope carries a "files pkgdown will publish (root .md)" preview.

!!! warning "Known tradeoff (unvalidated): git-archive strips `.git`"
    The clean ref has no `.git`, so pkgdown git-backed metadata (last-modified
    dates, "edit this page" links) may degrade in the published site. The
    SPEC-sanctioned fallback is `git worktree add` at HEAD (preserves `.git`).
    This needs a real pkgdown build to confirm — see the SPEC open questions.

## Output Format
```markdown
## Website: {package} v{version}
### Status: {🟢 built clean / 🟡 built with problems / 🔴 build failed}
- Checked: {site.checked} · Built: {site.built}
{If status 🔴: "### Vignette/render errors" — point at the failing .Rmd from messages}
{If site.problems: "### Config/index problems" — list each (url, un-indexed topics)}
### Recommended Actions
{Fix problems, or "Site built to docs/ ✅"}
```

## Related Commands
- `/rforge:r:document` — ensure Rd docs exist before building the site

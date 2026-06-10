---
name: rforge:r:submit
description: GitHub pre-release of the submitted tarball + CRAN submit handoff; promote on acceptance
argument-hint: "[package] [--promote] [--dry-run] [--no-verify] [--force]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: promote
    description: "Phase 2 — promote the existing pre-release to a full release (after CRAN accepts)"
    required: false
    type: boolean
    default: false
  - name: dry-run
    description: Show the tag, attachments, and submit checklist without touching GitHub
    required: false
    type: boolean
    default: false
  - name: no-verify
    description: "With --promote, skip the optional cran.r-project.org version check"
    required: false
    type: boolean
    default: false
  - name: force
    description: Cut the pre-release even if cran-prep is not 'ready' (records the override)
    required: false
    type: boolean
    default: false
---

# R Submit — GitHub pre-release + CRAN submit handoff

Wrap the *moment of CRAN submission*: build the exact tarball, cut a GitHub **pre-release** of it
(not "Latest"), and hand off the CRAN submit step. A second invocation (`--promote`) flips the
pre-release to a full release once CRAN accepts. **Never auto-submits to CRAN.**

> Fills the gap between `/rforge:r:cran-prep` (reports `ready`) and CRAN going live. The actual
> CRAN upload stays a manual step you run.

## Phase 1 — `r:submit` (build + pre-release + handoff)

```bash
# 1. Gate: refuse unless cran-prep is ready (override only with --force)
python3 -m lib.rcmd --kind cran-prep --path "<path>"   # check verdict == "ready"

# 2. Build the submitted tarball (reuse r:build)
python3 -m lib.rcmd --kind build --path "<path>"        # → <pkg>_<version>.tar.gz

# 3. Cut the GitHub pre-release (construct the gh command via lib.ghrelease)
python3 -c "from lib.ghrelease import prerelease_cmd, gh_available, manual_recipe; \
import shlex; \
print(' '.join(prerelease_cmd('<version>', '<tarball>', notes_file='cran-comments.md')) \
      if gh_available() else manual_recipe('<version>', '<tarball>', notes_file='cran-comments.md'))"
# then run that `gh release create … --prerelease` (or print the manual recipe if gh is absent)
```

Then **print the CRAN submit checklist** (do not run it):

```markdown
## Ready to submit v{version} to CRAN
- [ ] Pre-release cut: {tag} (pre-release, not "Latest") with cran-comments.md + tarball attached
- [ ] Submit: `devtools::submit_cran()`  — or the web form at https://cran.r-project.org/submit.html
- [ ] Confirm via the emailed link
- [ ] On acceptance: `/rforge:r:submit --promote`
```

## Phase 2 — `r:submit --promote` (after CRAN accepts)

```bash
# Optional verify (skip with --no-verify): confirm v{version} is live on CRAN
#   https://cran.r-project.org/package=<pkg>
# Promote the pre-release to a full release:
python3 -c "from lib.ghrelease import promote_cmd; print(' '.join(promote_cmd('<version>')))"
# → run `gh release edit {tag} --prerelease=false --latest`
```

## Flags

- `--dry-run` — show the tag/assets/checklist; touch nothing on GitHub.
- `--force` — cut the pre-release even if `cran-prep` is not `ready` (record the override + reasons).
- `--no-verify` — with `--promote`, skip the CRAN-page version check.

## Guards & degradation

- **Not ready** → refuse (print the blocking reasons); `--force` overrides.
- **`gh` absent/unauthed** (`gh_available()` false, or `gh auth status` fails) → print the manual
  `gh` recipe via `lib.ghrelease.manual_recipe`; never fail.
- **`--promote` with no matching pre-release** → warn with guidance, never a destructive action.

## Related Commands

- `/rforge:r:cran-prep` — the upstream readiness gate (must be `ready`)
- `/rforge:r:build` — produces the tarball this attaches
- `/rforge:release` — ecosystem submission *sequencing* (hands off to per-package `r:submit`)

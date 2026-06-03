---
name: rforge:r:cran-prep
description: Per-package CRAN-readiness gate — runs the full pre-submission sequence
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: goodpractice
    description: Also run the advisory goodpractice bundle
    required: false
    type: boolean
    default: false
  - name: multi-platform
    description: Dispatch win-builder + R-hub (async)
    required: false
    type: boolean
    default: false
  - name: no-revdep
    description: Skip the reverse-dependency check
    required: false
    type: boolean
    default: false
---

# R Package CRAN-Prep Gate

Run the full per-package CRAN-readiness sequence and generate `cran-comments.md`.
Composes with `/rforge:release` (this = single-package gate; release = cross-package
submission ordering).

## Process
```bash
python3 -m lib.rcmd --kind cran-prep --path "<path>"   # + --goodpractice / --multi-platform / --no-revdep
```

## Output Format
```markdown
## CRAN-Prep: {package} v{version}
### Status: {🟢 ready / 🟡 warn (open notes) / 🔴 blocked}
| Stage | Result |
|-------|--------|
{one row per stages[] with its status dot}
{If blockers: "### Blockers" list}
{If dispatched: "### Dispatched (async)" — winbuilder/rhub + where to check}
- cran-comments.md: {cran_comments_path}
### Next
{If ready: "→ hand off to /rforge:release for submission ordering"}
{else: fix blockers and re-run}
```

## Related Commands
- `/rforge:release` — ecosystem-level submission ordering (consumes this verdict)
- `/rforge:r:revdep`, `/rforge:r:check`, `/rforge:r:winbuilder`, `/rforge:r:rhub` — individual stages
- `/rforge:r:cycle` — quick dev loop (doc→test→check); cran-prep is the submission gate

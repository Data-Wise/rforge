---
name: rforge:r:winbuilder
description: Submit to win-builder (devel/release/oldrelease or R-hub) — async
argument-hint: "[package] [--platform devel|release|oldrelease|all|rhub]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: --platform
    description: "Target platform: devel (default), release, oldrelease, all (all three win-builder flavours), or rhub (dispatches via rhub::rhub_check to GitHub Actions)"
    required: false
    type: string
    default: "all"
---

# Win-Builder Submission

Submit the package to [win-builder](https://win-builder.r-project.org/) for a
remote Windows check. This is an **async dispatch** — the check runs remotely
and results are **emailed to the DESCRIPTION Maintainer** (or appear in GitHub
Actions for `--platform rhub`); nothing returns synchronously.

This is a CRAN pre-submission obligation for packages targeting Windows
compatibility. Run it at least once per release, typically after a clean
`/rforge:r:check --as-cran` pass.

**Platforms:**
- `all` (default) — submits to devel, release, and oldrelease in one call
- `devel` / `release` / `oldrelease` — single win-builder flavour
- `rhub` — dispatches via `rhub::rhub_check()` to GitHub Actions instead of win-builder email

`devtools` is optional — if `engine_missing` includes it, report 🟡 + install
hint:

```
install.packages("devtools")
```

## Process

```bash
python3 -m lib.rcmd --kind winbuilder --path "<path>"
```

## Output Format

````markdown
## Win-Builder: {package} v{version}
### Status: 🚀 dispatched
- {winbuilder.note}
- Check your inbox in ~30 min for the R-devel results email.
````

## Related Commands

- `/rforge:r:cran-prep` — full CRAN submission gate (runs winbuilder under `--multi-platform`)
- `/rforge:r:rhub` — multi-platform checks via R-hub v2 (GitHub Actions)

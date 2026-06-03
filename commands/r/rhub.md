---
name: rforge:r:rhub
description: Multi-platform checks via R-hub v2 (rhub::rhub_check) — async, GitHub Actions
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R-Hub v2 Multi-Platform Check

Run `rhub::rhub_check()` — **async dispatch** to R-hub v2, which triggers
GitHub Actions workflows to check the package across multiple platforms
(Linux, macOS, Windows, various R versions). Results appear in the **repo's
Actions tab**, not here.

!!! warning "First run commits a workflow file"
    `rhub::rhub_setup()` (called automatically) is idempotent but writes a
    `.github/workflows/rhub.yaml` to the repo on the first run. **A GitHub
    remote is required.** Subsequent runs skip setup.

`rhub` is optional — if `engine_missing` includes it, report 🟡 + install
hint:

```
install.packages("rhub")
```

## Process

```bash
python3 -m lib.rcmd --kind rhub --path "<path>"
```

## Output Format

````markdown
## R-Hub: {package} v{version}
### Status: 🚀 dispatched
- {rhub.note}
- Run URL: {rhub.run_url} (null until the run-URL capture lands — check the repo's Actions tab for results)
````

## Related Commands

- `/rforge:r:cran-prep` — full CRAN submission gate (includes rhub under `--multi-platform`)
- `/rforge:r:winbuilder` — win-builder (R-devel) submission via devtools

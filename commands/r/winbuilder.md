---
name: rforge:r:winbuilder
description: Submit to win-builder (R-devel) via devtools::check_win_devel — async
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# Win-Builder Submission

Submit the package to [win-builder](https://win-builder.r-project.org/) for a
remote R-devel check on Windows via `devtools::check_win_devel()`. This is an
**async dispatch** — the check runs remotely and results are **emailed to the
DESCRIPTION Maintainer**; nothing returns synchronously.

This is a CRAN pre-submission obligation for packages targeting Windows
compatibility. Run it at least once per release, typically after a clean
`/rforge:r:check --as-cran` pass.

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

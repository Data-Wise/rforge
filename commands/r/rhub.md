---
name: rforge:r:rhub
description: Multi-platform checks via R-hub v2 (rhub::rhub_check) — async, GitHub Actions
argument-hint: "[package] [--platforms linux,windows] [--preset cran-submission] [--rc-mode]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: platforms
    description: Comma-separated platform list (e.g. linux,windows,macos-arm64,atlas)
    required: false
    type: string
  - name: preset
    description: Named platform preset (cran-submission | cran-submission-strict | sanitizers | all-vm)
    required: false
    type: string
  - name: rc-mode
    description: Use RC shared runners via rc_submit() instead of your own GitHub account
    required: false
    type: boolean
    default: false
---

# R-Hub v2 Multi-Platform Check

Run `rhub::rhub_check()` — **async dispatch** to R-hub v2, which triggers
GitHub Actions workflows to check the package across multiple platforms
(Linux, Windows, macOS-ARM, sanitizers). Results appear in the **repo's
Actions tab**, not here. The Actions URL is constructed from your git remote
and opened in your browser automatically.

!!! warning "rhub.yaml must already exist"
    This command **never** runs `rhub::rhub_setup()` — doing so on every
    invocation would create a spurious git commit. `.github/workflows/rhub.yaml`
    must already exist and be committed. If it's missing, the pre-flight check
    hard-stops with `rhub_yaml_missing`; run `rhub::rhub_setup()` in R once
    (a GitHub remote is required) and commit the file before dispatching.

!!! note "Expected behavior in v2.14.0+"
    Platforms are always passed explicitly to `rhub_check()` — the command
    never passes `NULL` (which would open an interactive menu and hang
    headlessly). With no `--platforms`/`--preset`, the `cran-submission` preset
    is used.

`rhub` is optional — if `engine_missing` includes it, report 🟡 + install
hint:

```
install.packages("rhub")
```

## Process

```bash
# Default: cran-submission preset (linux, windows, macos-arm64, atlas)
python3 -m lib.rcmd --kind rhub --path "<path>"

# Named preset
python3 -m lib.rcmd --kind rhub --path "<path>" --preset cran-submission-strict

# Explicit platforms
python3 -m lib.rcmd --kind rhub --path "<path>" --platforms linux,windows,macos-arm64

# RC shared runners (rc_submit — no own GitHub account needed)
python3 -m lib.rcmd --kind rhub --path "<path>" --rc-mode
```

### Presets

| Preset | Platforms |
|--------|-----------|
| `cran-submission` (default) | linux, windows, macos-arm64, atlas |
| `cran-submission-strict` | + clang-asan `[unstable]` |
| `sanitizers` | clang-asan `[unstable]`, atlas |
| `all-vm` | linux, windows, macos-arm64 |

`clang-asan` is opt-in only (intermittent ASAN linker failures, rhub #645).

## Pre-flight checks (automatic, before dispatch)

1. **`.github/workflows/rhub.yaml` missing** → hard-stop (`rhub_yaml_missing`).
   User must run `rhub::rhub_setup()` in R first.
2. **Broken platform requested** → hard-stop (`rhub_broken_platform`).
   E.g. `macos` (macos-13 runner retired Dec 2025) → suggest `macos-arm64`.
3. **`pak-version: stable` missing in rhub.yaml** → advisory (`rhub_pak_devel_regression`).
   Dispatch continues; finding surfaced in output. (pak devel bootstrap
   regression, r-lib/pak #887.)
4. **Default config field contains broken platform** → advisory (`rhub_yaml_default_broken_platform`).
   Dispatch continues; suggests updating rhub.yaml `config.default` field.

Only `error`-severity findings (1–2) block dispatch; advisories (3–4) never
short-circuit it — they ride along in the returned envelope's `findings`.

## Output Format

### Success (dispatched)

````markdown
## R-Hub: {package} v{version}
### Status: 🚀 dispatched
- Platforms: linux, windows, macos-arm64, atlas
- Mode: rhub_check (own GH account)  [or: rc_submit (RC shared runners)]
- Actions URL: {run_url} (opened in browser)

⚠️ Advisory findings:
- [rhub_pak_devel_regression] setup-deps block 2 is missing `pak-version: stable`...
````

### Error (hard-blocked)

````markdown
## R-Hub: {package} v{version}
### Status: ❌ blocked

- [rhub_yaml_missing] .github/workflows/rhub.yaml not found...
  Run rhub::rhub_setup() in R to create it.
````

## Related Commands

- `/rforge:r:cran-prep` — full CRAN submission gate (includes rhub under `--multi-platform`)
- `/rforge:r:winbuilder` — win-builder (R-devel) submission via devtools

# SPEC: rhub Platform Selection & Known-Issues Guard
**Date:** 2026-06-19  
**Status:** READY — user answers collected 2026-06-19  
**Scope:** `lib/rcmd.py` + `commands/r-winbuilder.md` (+ possibly new `commands/r-rhub.md`)  
**Priority:** Low-medium (non-blocking for v2.14.0; next bundle candidate)

---

## Background

rforge currently dispatches rhub in two places:

1. `r_snippet("winbuilder", platform="rhub")` — calls `rhub::rhub_check(path)` headlessly,
   no `platforms=` arg → falls into rhub's interactive console menu (broken headlessly).
2. `r_snippet("rhub")` — calls `rhub_setup()` + `rhub::rhub_check(path)` → same problem;
   hardcodes `run_url=NA`.

Both entry points share three structural problems:
- **Interactive**: `rhub_check()` prompts for platform selection via a numbered console menu;
  headless `_invoke_r()` gets no TTY → hangs or errors.
- **No JSON output**: results land in GitHub Actions, not stdout; rforge parses nothing useful.
- **Platform drift**: the `macos` platform (backed by GitHub macos-13 runner) was retired
  December 2025 — any invocation selecting `macos` fails immediately.

---

## Research Summary (2026-06-19)

### rhub v2 Architecture

rhub v2 (≥ 2.0.0, released April 2024) is GitHub Actions-based:

- User calls `rhub_setup()` once per repo → adds `.github/workflows/rhub.yaml`
- `rhub_check(platforms=...)` dispatches a GH Actions workflow run
- Results appear in the **Actions tab**, not in stdout or email
- Package must be pushed to GitHub first; local changes not picked up
- Two modes: **own GH account** (private, consumes your GH minutes) vs
  **RC shared runners** via `rc_submit()` (public results, 5-min wait between submissions)

### Platform Status Map (June 2026)

| Type | Name | OS / Runner | R | Status |
|------|------|-------------|---|--------|
| VM | `linux` | ubuntu-latest | any | ✅ Stable |
| VM | `macos` | **macos-13** | any | ❌ **BROKEN** — runner retired Dec 2025 ([#669](https://github.com/r-hub/rhub/issues/669)) |
| VM | `macos-arm64` | macos-latest (ARM) | any | ⚠️ qpdf/brew failures on R-devel ([#648](https://github.com/r-hub/rhub/issues/648)) |
| VM | `m1-san` | macos-15 + ASAN | any | ⚠️ ARM+ASAN — niche, some failures |
| VM | `windows` | windows-latest | any | ✅ Stable |
| CT | `atlas` | Fedora 42 container | R-devel | ✅ Likely stable |
| CT | `c23` | Ubuntu 22.04 container | R-devel | ✅ C23 standards |
| CT | `donttest` | Ubuntu 22.04 container | R-devel | ✅ Runs `\donttest{}` |
| CT | `clang-asan` | Ubuntu 22.04 container | R-devel | ⚠️ ASAN shared object errors ([#645](https://github.com/r-hub/rhub/issues/645)) |
| CT | `gcc-asan` | Fedora 42 container | R-devel | ⚠️ DescTools compilation failures ([#672](https://github.com/r-hub/rhub/issues/672)) |
| CT | `clang16`–`clang22` | Ubuntu 22.04 container | R-devel | ⚠️ gcc16 setup failing ([#672](https://github.com/r-hub/rhub/issues/672)) |

**Key open issues**:
- `rhub_check()` fails with `"Failed to start check: Not Found"` in some configurations ([#675](https://github.com/r-hub/rhub/issues/675))
- `rhub_doctor()` doesn't recognize non-standard GH URLs ([#674](https://github.com/r-hub/rhub/issues/674))
- `quarto` vignettes missing `gh` in container ([#638](https://github.com/r-hub/rhub/issues/638))
- No `env_vars` argument to `rhub_check()` yet ([#637](https://github.com/r-hub/rhub/issues/637))

---

## Proposed Changes

### Proposal A — Broken-platform guard (Quick Win, ~30 min)

Add a `_RHUB_BROKEN_PLATFORMS` dict to `rcmd.py`:

```python
_RHUB_BROKEN_PLATFORMS = {
    "macos": (
        "macos-13 runner retired December 2025; "
        "use `macos-arm64` (ARM) or wait for rhub to update. "
        "See https://github.com/r-hub/rhub/issues/669"
    ),
}
```

In `r_snippet("winbuilder", platform="rhub")` (and `kind="rhub"`), before dispatching,
surface a `notes_classified` advisory for any platform in `_RHUB_BROKEN_PLATFORMS`.

**Decision needed (Q3)**: hard-block, warn-only, or silent-substitute?

---

### Proposal B — Non-interactive platform dispatch (Medium, ~1-2 hrs)

Extend `r_snippet("rhub")` to accept a `rhub_platforms` list:

```python
def r_snippet(kind, path, ..., rhub_platforms=None):
    ...
    if kind == "rhub":
        if rhub_platforms:
            plats_r = "c(" + ", ".join(f'"{p}"' for p in rhub_platforms) + ")"
        else:
            plats_r = "NULL"   # falls back to rhub's interactive menu
        return _guard("rhub",
            f'rhub::rhub_setup({p}); '
            f'rhub::rhub_check({p}, platforms={plats_r}); '
            f'cat(jsonlite::toJSON(list(submitted=TRUE, platforms={plats_r},'
            f'note="Results in GitHub Actions tab"), auto_unbox=TRUE))')
```

Wire through `run()` and argparse with `--rhub-platforms linux,windows,macos-arm64`.

---

### Proposal C — CRAN submission preset (Medium, ~1 hr)

Define curated platform presets in `rcmd.py`:

```python
_RHUB_PRESETS = {
    "cran-submission": ["linux", "windows", "macos-arm64"],
    "sanitizers":      ["clang-asan", "atlas"],
    "all-vm":          ["linux", "windows", "macos-arm64"],
}
```

**Decision needed (Q6)**: should `cran-submission` include a sanitizer container
(`clang-asan` or `atlas`) to mirror CRAN's own check environment?

---

### Proposal D — Dedicated `r:rhub` command (Long-term)

Separate `commands/r-rhub.md` with:
- `--platforms` (comma-separated or preset name)
- `--preset cran-submission|sanitizers|all-vm`
- `--rc-mode` (use RC shared runners via `rc_submit()` instead of own GH account)
- `--setup-check` (verify `.github/workflows/rhub.yaml` exists before dispatching)

**Decision needed (Q1)**: separate command vs `r:winbuilder --platform rhub`.

---

### Proposal E — Run-URL surfacing (Medium, ~1 hr)

`rhub_check()` prints the GH Actions URL to stdout but doesn't return it.
Parse it from stdout, include in the rforge output envelope.

```python
# parse from rhub stdout: "See <url>" or "Actions tab: <url>"
# Surface in env["rhub"]["run_url"] instead of hardcoded NA
```

**Decision needed (Q5)**: print-only vs auto-open vs poll-for-status.

---

## Open Questions (User Input Required)

## User Decisions (2026-06-19)

| Q | Decision |
|---|----------|
| Q1. Command structure | **Dedicated `r:rhub` command** — clean separation from `r:winbuilder` |
| Q2. Platform UX | **Interactive rhub menu** (native UX; rforge advises but doesn't override) |
| Q3. Broken `macos` platform | **Hard-block + suggest `macos-arm64`** |
| Q4. Runner mode | **Both** — support `rhub_check()` (own GH) + `rc_submit()` (RC shared) via `--rc-mode` |
| Q5. Result surfacing | **Print URL + open in browser** |
| Q6. CRAN preset | **OS matrix + `atlas`**: `linux`, `windows`, `macos-arm64`, `atlas` |
| Q7. Setup check | **Warn and stop** if `.github/workflows/rhub.yaml` missing |
| Q8. Sanitizers | `clang-asan` for packages with compiled C/C++; `atlas` as stable bonus; mark `[unstable]` in advisory |

### Sanitizer guidance (Q8 detail)

CRAN runs ASAN internally — catching memory errors before submission matters.
Current container stability (June 2026):
- `clang-asan` — ⚠️ intermittent (ASAN shared-object linker bug, issue #645). Include
  but mark `[unstable]` — real signal, noisy delivery.
- `gcc-asan` — ⚠️ DescTools dep failures (issue #672). Skip for now.
- `atlas` — ✅ stable. Tests BLAS/LAPACK alternative linking. Add to CRAN preset as
  lightweight bonus for packages doing matrix operations.

**Recommended preset tiers:**
- `cran-submission` (default): `linux`, `windows`, `macos-arm64`, `atlas`
- `cran-submission-strict` (opt-in): above + `clang-asan` (warns: intermittently unstable)

---

## Non-Goals

- Polling GitHub Actions for results (too complex for this iteration; would need GH token)
- Supporting rhub v1 functions (`check_for_cran`, `rc_submit` in legacy mode)
- Auto-configuring PAT or GitHub repo setup

---

## Test Gates (if implemented)

- `test_rhub_broken_platform_advisory()` — broken platform name emits advisory note
- `test_rhub_platform_snippet_with_list()` — `r_snippet("rhub", rhub_platforms=["linux","windows"])` produces correct `c("linux","windows")` in snippet
- `test_rhub_preset_cran_submission()` — preset expands to expected platform list
- `test_rhub_platform_guard_passthrough()` — non-broken platform has no advisory

---

*Awaiting answers to Q1–Q8 before implementation begins.*

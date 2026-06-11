---
title: "r:submit --universe — R-universe early-access tier"
status: draft
created: 2026-06-11
from_brainstorm: /workflow:brainstorm -d -s "github → r-universe → CRAN early-access"
target_version: 2.7.0
---

# SPEC: `r:submit --universe` — R-universe early-access tier

## Overview

Add an opt-in `--universe` flag to `/rforge:r:submit`. When set, after the existing build +
GitHub pre-release steps, rforge confirms the package's [R-universe](https://r-universe.dev) is
registered, reads the R-universe API for the package's per-platform build/check status, reports
green/red, and prints the early-access install snippet. The CRAN checklist gains one **advisory**
R-universe line. The CRAN handoff itself is unchanged and **never automatic**.

**Why:** CRAN review is human-reviewed and takes days. R-universe (rOpenSci) rebuilds an R
package from its GitHub repo within minutes and serves it as a CRAN-like binary repo — the
natural early-access channel. Users install the new version from R-universe immediately while
CRAN review runs in parallel.

**Hard constraint — CRAN stays explicit.** The two channels have structurally different triggers,
so automation cannot leak across them:

| Channel | Trigger | Nature |
|---|---|---|
| **R-universe** | a `git push` (once the universe is registered) | passive / automatic build |
| **CRAN** | you running `devtools::submit_cran()` from the printed checklist | active / manual |

## User stories

### Primary
*As an R-package author, when I submit to CRAN I want to simultaneously verify my package is live
and green on R-universe, so users get the new version immediately — without any risk of CRAN being
submitted automatically.*

### Secondary
- *As a maintainer whose universe isn't set up yet, when I run `--universe` I want clear one-time
  setup guidance rather than a cryptic error.*
- *As a CI job, when I run the lib smoke test offline I want a clean `warn` envelope, not a crash.*

## Acceptance criteria

- [ ] `r:submit --universe` reports per-platform R-universe build status; exits non-error when green.
- [ ] Unregistered universe/package → prints one-time setup guidance (`<owner>.r-universe.dev` repo
      + `packages.json` entry + GitHub App) and degrades to `warn` — never errors.
- [ ] No network (CI/offline) → lib CLI smoke exits 0 with a `warn` envelope.
- [ ] CRAN checklist shows an advisory R-universe line; the manual CRAN step is never auto-run.
- [ ] All 30 `test-all.sh` checks + full pytest suite pass; 4 version sources agree; reference docs in sync.

## Architecture

```
r:submit --universe
  │  (existing) cran-prep gate → r:build → gh pre-release (lib.ghrelease)
  └─► NEW: lib.runiverse.verify(path, universe=None)
            ├─ resolve owner   ← git remote origin  →  <owner>.r-universe.dev
            ├─ resolve package ← DESCRIPTION Package
            ├─ GET https://<owner>.r-universe.dev/api/packages/<pkg>   (urllib, stdlib)
            │       → parse _status / per-platform build+check results
            ├─ not found → setup-guidance finding (status=warn)
            └─ emit envelope {kind:"runiverse", status, findings, messages, engine_missing:[]}
  └─► CRAN checklist gains advisory line: "R-universe: <green|red|unregistered>"
```

## New module: `lib/runiverse.py` (public, pure-stdlib)

- Standard envelope: `{kind, status (ok|warn|error), findings, messages, engine_missing: []}`
  — same shape as `lib/cranlint.py` / `lib/deps_sync.py`.
- Network via `urllib.request` only (no new deps, no R engine; `engine_missing` always `[]`).
- Public functions (mirroring `ghrelease.py` style):
  - `resolve_universe(path) -> owner | None` (parse `git remote origin` GitHub owner)
  - `api_url(owner, pkg) -> str`
  - `fetch_status(owner, pkg, *, timeout) -> dict | None` (None on network/HTTP failure)
  - `summarize(status_json) -> {green: bool, platforms: [...], messages: [...]}`
  - `verify(path, universe=None) -> envelope`
  - `install_snippet(owner, pkg) -> str`
- CLI: `python3 -m lib.runiverse --path <dir> [--universe <name>] --format json` — must degrade
  to a `warn` envelope (not crash) when offline or unregistered, so the smoke test is hermetic.

**API note for implementation:** canonical endpoint is
`https://<owner>.r-universe.dev/api/packages/<pkg>` (JSON; includes `_status` + binary/check
results); badge fallback `https://<owner>.r-universe.dev/badges/<pkg>`. Re-verify exact field
names against a live response during implementation (the docs API page 403'd to automated fetch).

## API design

N/A — no HTTP server exposed. rforge is a *client* of the public R-universe HTTPS API
(`GET /api/packages/<pkg>`), read-only.

## Data models

N/A — CLI only. Output is the standard JSON envelope (see module section).

## Command wiring: `commands/r/submit.md`

- Frontmatter `arguments`: add `--universe` (boolean, default false) and `--universe-name`
  (string, optional override of auto-detected `<owner>`).
- Body: add a **Phase 0 / early-access** section describing the `lib.runiverse` call + printed
  snippet `install.packages("<pkg>", repos = "https://<owner>.r-universe.dev")`.
- Add the advisory R-universe line to the existing CRAN checklist block (non-blocking).

## Dependencies

None new. Pure stdlib (`urllib`, `json`, `subprocess` for `git remote`). `gh` not required for
this tier (R-universe status is a public HTTPS endpoint).

## UI/UX specifications

N/A — CLI only. Terminal output: a per-platform status table + the install snippet + an advisory
CRAN-checklist line.

## Open questions

1. **(OPEN)** Exact R-universe JSON field names for per-platform pass/fail — the parser is
   defensive (`_status`, `_binaries[].status|check`); verify against a live universe response.
2. **(RESOLVED — single-shot)** `--universe` does a single status read, **not** a block-wait
   (avoids hanging CI). A future `--wait` could poll.
3. **(RESOLVED — no)** `--universe` does **not** push the current commit first — it stays
   read-only/verify; the author pushes via normal git.
4. **(RESOLVED — lowercase)** The universe name is normalized to lowercase in
   `resolve_universe`/`api_url`/`install_snippet`: the `Data-Wise` GitHub org maps to
   `data-wise.r-universe.dev` (DNS is case-insensitive, but the registry/monorepo names are
   canonically lowercase).

## Review checklist

- [ ] Envelope matches the shared shape; `engine_missing == []`.
- [ ] Offline + unregistered paths return `warn`, never raise.
- [ ] CRAN step remains manual; checklist line is advisory only.
- [ ] Frontmatter `arguments` ↔ `## Usage` body in sync.
- [ ] `runiverse` added to `gen_lib_reference.py` MODULES; reference doc in sync.
- [ ] 4 version sources agree at 2.7.0.

## Implementation notes

- Owner resolution must handle both `https://github.com/<owner>/<repo>.git` and
  `git@github.com:<owner>/<repo>.git` remote forms; `--universe-name` overrides. The resolved
  name is **lowercased** (canonical R-universe subdomain — `Data-Wise` → `data-wise`).
- Offline degradation is the key correctness requirement — wrap the urllib call and treat any
  `URLError`/timeout/non-200 as "status unknown" → `warn`, with a message, never an exception.
- Command count stays **35** (a flag, not a new command).

## History

- 2026-06-11 — draft created from `/workflow:brainstorm -d -s`; design decisions resolved
  (opt-in flag, verify-green action, advisory CRAN gate).

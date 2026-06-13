# Orchestrator cookbook — worked examples

!!! tip "TL;DR (30 seconds)"
    - **What:** Copy-paste-style scenarios showing what the [orchestrator](../orchestrator.md) runs and synthesizes for common R-package goals.
    - **Why:** See the intent → recipe → summary flow before you rely on it.
    - **Prereq:** An R package or ecosystem directory; rforge installed.

Each recipe below is **read-only** unless the summary explicitly *recommends* a
file-writing command — the orchestrator never runs those for you (see the
[safety boundary](../orchestrator.md#step-3-the-safety-boundary-recommend-only)).

---

## Recipe 1 — "Is this package CRAN-ready?"

**Intent:** `CRAN_READINESS`

> **You:** "Is RMediation ready to submit to CRAN?"

The orchestrator runs the read-only CRAN analyses and synthesizes them:

```
$ python3 -m lib.rcmd --kind check        # R CMD check (into a temp dir)
$ python3 -m lib.cranlint                 # advisory description/build-hygiene/docs
$ python3 -m lib.runiverse --format json  # R-universe early-access status (network read)
```

```
┌─ RForge Orchestrator ─────────────────────────────┐
│ Intent: CRAN_READINESS                            │
│ Findings:                                         │
│   • rcmd check: ok — 0 errors, 0 warnings, 1 NOTE │
│   • cranlint: warn — DESCRIPTION Title in title-case│
│ 🔴 Blockers: none                                 │
│ → Next: /rforge:r:cran-prep  (writes cran-comments;│
│         gated — run it yourself)                  │
└───────────────────────────────────────────────────┘
```

!!! note "Why it stops at `cran-prep`"
    `r:cran-prep` **writes** `cran-comments.md` and regenerates docs, so it sits
    behind the safety boundary — the orchestrator recommends it, never runs it.

---

## Recipe 2 — "What's the impact of this change?"

**Intent:** `CODE_CHANGE`

> **You:** "I refactored the bootstrap function in medfit — what does it affect?"

```
$ python3 -m lib.discovery --format json
$ python3 -m lib.deps --format json impact --package medfit
$ python3 -m lib.rcmd --kind test
```

```
┌─ RForge Orchestrator ─────────────────────────────┐
│ Intent: CODE_CHANGE                               │
│ Findings:                                         │
│   • deps impact: 2 downstream pkgs depend on medfit│
│     (probmed, RMediation)                          │
│   • rcmd test: ok — 48 passed                      │
│ → Next: re-run tests in the 2 downstream pkgs      │
└───────────────────────────────────────────────────┘
```

---

## Recipe 3 — "Check the ecosystem"

**Intent:** `ECOSYSTEM_HEALTH`

> **You:** "Give me a status overview of the mediationverse."

```
$ python3 -m lib.status --format json
$ python3 -m lib.discovery --format json
$ python3 -m lib.deps --format json
```

The summary rolls up `.STATUS` health, the discovered packages (in
[`manifest_order`](../reference/discovery.md) if a manifest is configured), and the
dependency layers — then points you at `/rforge:health` or `/rforge:thorough` for
the full dashboard.

---

## Recipe 4 — "Audit my dependencies"

**Intent:** `DEPS_AUDIT`

> **You:** "Are my DESCRIPTION imports in sync with the code?"

```
$ python3 -m lib.deps_sync --format json   # dry-run — never writes
$ python3 -m lib.deps --format json
```

```
┌─ RForge Orchestrator ─────────────────────────────┐
│ Intent: DEPS_AUDIT                                │
│ Findings:                                         │
│   • deps_sync: warn — 1 missing (rlang), 1 unused  │
│     (stringr), 1 misclassified (testthat in Imports)│
│ → Next: /rforge:r:deps-sync --write  (applies the  │
│         patch — run it yourself)                   │
└───────────────────────────────────────────────────┘
```

---

## What it will *not* do for you

The orchestrator surfaces these as recommendations and stops — run them yourself:

- regenerate docs (`/rforge:r:document`), format (`/rforge:r:style`), build/install
- write `cran-comments.md` (`/rforge:r:cran-prep`)
- submit / pre-release (`/rforge:r:submit`), upload to win-builder / R-hub
- apply a dependency patch (`/rforge:r:deps-sync --write`)

## See also

- [The orchestrator agent](../orchestrator.md) — the full intent + safety contract
- [Ecosystem orchestration](ecosystem-orchestration.md) — the multi-package workflow

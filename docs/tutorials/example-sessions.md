# Example Sessions

Real transcripts showing how rforge commands work in practice.

## Session 1: Starting the day with a health check

```text
User: /rforge:status
Claude:
╔═══════════════════════════════════════╗
║  RForge Ecosystem Status             ║
╚═══════════════════════════════════════╝

  📦 ecosystem: data-wise (9 packages)
  ├── medfit        v0.3.1   🟢 clean
  ├── probmed       v0.2.0   🟢 clean
  ├── medrobust     v0.3.2   🟡 needs check
  ├── medsim        v0.1.0   🟢 clean
  ├── rmediation    v0.5.1   🟢 clean
  ├── mediationverse v0.1.0  🔴 check failed
  ├── medsurv       v0.1.0   🟡 needs check
  ├── mediang       v0.1.0   🟢 clean
  └── medbayes      v0.1.0   ⚪ unknown

  📊 next steps:
  ┌──────────────────────────────────────┐
  │ mediationverse — check failed        │
  │ medrobust — needs check              │
  │ medsurv — needs check                │
  └──────────────────────────────────────┘
```

The user sees the overall health at a glance. Two packages need attention.

## Session 2: Diagnosing a check failure

Building on the status above:

```text
User: /rforge:r:check mediationverse --as-cran

Claude:
Running rcmdcheck on mediationverse...

  ┌──────────────────────────────────────┐
  │ mediationverse v0.1.0                │
  │ R CMD check --as-cran                │
  ├──────────────────────────────────────┤
  │ NOTE  1                              │
  │ WARNING  0                           │
  │ ERROR  1                             │
  └──────────────────────────────────────┘

  ERROR: vignette build failed
    vignettes/mediation-intro.Rmd uses `mediationverse` (which
    depends on `mediationverse`) — circular. Move the vignette
    to a leaf package or use an external dataset.

  NOTE: Namespace in Imports field but not in NAMESPACE
    `ggplot2` is in DESCRIPTION Imports but not used in
    any @importFrom. Move to Suggests or add a re-export.

Tier 4 (advisory):
  ✔ description: clean
  ✔ build-hygiene: clean
  ✔ docs-consistency: 1 suggestion (see below)

→ Ready to fix the vignette error and the NOTE.
```

The user now knows exactly which two issues to fix.

## Session 3: Diff-aware pre-merge check

After fixing the issues, before merging a feature branch:

```text
User: /rforge:r:check --changed --base dev

Claude:
Merge-base: abc1234 (origin/dev)
Changed packages: [mediationverse, medrobust]

Baseline cached for mediationverse (abc1234 → hit) ✓
Baseline cached for medrobust (abc1234 → hit) ✓

Running rcmdcheck on mediationverse (diff-aware)...
Running rcmdcheck on medrobust (diff-aware)...

mediationverse:
  [introduced] NOTE: Namespace in Imports field but not in NAMESPACE
  [pre-existing] NOTE: no visible binding for global variable

medrobust:
  [pre-existing] WARNING: R CMD check found 1 NOTE

Result: ❌ 1 [introduced] finding (--fail-on introduced)
→ Review the introduced NOTE before merging.
```

The diff-aware system separates debt the developer introduced from pre-existing
issues, making it clear what's actionable for this PR.

## Session 4: CRAN prep

Preparing a package for CRAN submission:

```text
User: /rforge:r:cran-prep medrobust

Claude:

  ┌──────────────────────────────────────┐
  │   medrobust — CRAN Prep Gate v2      │
  └──────────────────────────────────────┘

  Pass 1 (dev cycle):
    ✔ document
    ✔ lint
    ✔ spell
    ✔ test (42 passed, 0 failed, 2 skipped)

  Pass 2 (check):
    ✔ check (--as-cran) — 0❌ 0⚠ 0ℹ
    ✔ check (noSuggests) — 0❌ 0⚠ 1ℹ
    ✔ check (suggests-only) — 0❌ 0⚠ 1ℹ

  Pass 3 (ecosystem):
    ✔ revdep — 1 downstream, clean

  Tier 4 (advisory):
    ✔ description: clean
    ✔ build-hygiene: clean
    ✔ docs-consistency: clean

  Status: ✅ ready

  → cran-comments.md written. Next: /rforge:thorough for ecosystem rollup,
    or /rforge:r:winbuilder for Windows check.
```

The multi-pass gate gives confidence before submission.

## Session 5: Multi-platform check

```text
User: /rforge:r:winbuilder medrobust

Claude:
Checking win-builder availability...
→ lib.rcmd found — using python rcmd backend
  Dispatched to win-builder (devel).
  Results will be emailed to maintainer@example.com.

User: /rforge:r:rhub medrobust --preset cran

Claude:
Checking R-hub availability...
  R-hub dispatch via GitHub Actions.
  Platforms:
    - windows (R-devel)
    - ubuntu (R-release)
    - macos (R-release)
  Dispatch complete.
  → Check the Actions tab in 15-30 min.
```

Async dispatch frees the user to continue working while results arrive.

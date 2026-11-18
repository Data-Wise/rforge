# Cookbook: task recipes

!!! tip "TL;DR (30 seconds)"
    - **What:** one-command answers to "how do I find out X about my packages?", each run for real.
    - **Who:** R-package authors who know what they want to check and just need the command.
    - **Scope:** read-only, pure-Python commands (no R needed). Recipes that write files live in the [tutorials](tutorials/README.md).

Every recipe that shows output was run against a throwaway two-package ecosystem: `corepkg` (no dependencies) and
`apppkg` (imports `corepkg`). The ecosystem path is shortened to `~/r-eco`, and long output is trimmed to the lines
that matter. The last two recipes only point to a tutorial and show no output. The `/rforge:` commands run the same
`python3 -m lib.*` modules shown here.

For intent-driven examples that run several analyses at once, see the
[Orchestrator cookbook](tutorials/orchestrator-cookbook.md).

---

## Which packages are in this directory?

```bash
python3 -m lib.discovery --path ~/r-eco
```

```text
🏗️  Ecosystem: ~/r-eco
   Packages: 2 | mode: standard | config: not found

   ├─ apppkg 0.2.0
   ├─ corepkg 0.1.0
```

Slash command: `/rforge:detect`.

## In what order do I build and release them?

```bash
python3 -m lib.deps --path ~/r-eco graph
```

```text
📊 BUILD ORDER (Topological Layers)
  Layer 1: corepkg
  Layer 2: apppkg

→ DEPENDENCIES
  apppkg → corepkg

🚧 BLOCKING PACKAGES
  • corepkg blocks: apppkg
```

Release lower layers first. Slash command: `/rforge:deps`.

## What breaks if I change this package?

```bash
python3 -m lib.deps --path ~/r-eco impact \
  --package corepkg --change-type breaking --affected-exports core_mean
```

```text
📊 IMPACT: corepkg (breaking)

  Direct dependents:   1
  Indirect dependents: 0
  Risk level:          high

→ DIRECT DEPENDENTS
  • apppkg

🔄 UPDATE SEQUENCE
  1. corepkg
  2. apppkg
```

The same command with `--package apppkg --change-type fix` reports 0 dependents and `Risk level: low`.

!!! note "Heuristic fields"
    `Affected tests` and `Estimated work` in the full output are rough estimates, not measurements. Use the dependents
    list and the update sequence for decisions. Slash command: `/rforge:impact`.

## What is the health of the whole ecosystem?

```bash
python3 -m lib.status --path ~/r-eco
```

```text
Package                Version    Check      Test       Progress
──────────────────────────────────────────────────────────────────
apppkg                 0.2.0      ❔ unknown ❔ unknown --
corepkg                0.1.0      ❔ unknown ❔ unknown --

Health score: 75/100
```

!!! warning "Symptom"
    `Check` and `Test` show `unknown`, and the health score is a middle value.

!!! tip "Fix"
    `lib.status` reports only what it can read from `.STATUS` files. It does not run `R CMD check` or the tests, so a
    package with no recorded results is `unknown`, not passing. By design each `unknown` deducts points (a quarter of a
    package's share when both check and test are unknown), so two unchecked packages score 75. Run
    [`/rforge:r:check`](commands.md) for a real result.

## Will CRAN's human reviewers flag my metadata?

```bash
python3 -m lib.cranlint --path ~/r-eco/corepkg
```

Output is JSON; condensed here to one line per stage:

```text
status: warn
description     warn   title_weak
build-hygiene   ok
docs-consistency ok
test_config     ok
```

`title_weak` means the `Title` field is very short. These findings are **advisory** and never block. The stronger
CRAN gate is [`r:cran-prep`](tutorials/cran-release-prep.md).

## Does `DESCRIPTION` match what my code uses?

```bash
python3 -m lib.deps_sync --path ~/r-eco/apppkg
```

Report-only by default. Add `--write` to apply the unambiguous additions and moves; removals always stay advisory.
Full walkthrough: [Dependency reconciliation](tutorials/dependency-reconciliation.md).

## Is my package tidy?

```bash
python3 -m lib.rcmd --kind tidy --path ~/r-eco/corepkg
```

Needs R with `lintr`, `usethis` and `styler`. Full walkthrough: [Tidy a package](tutorials/tidy-your-package.md).

---

## What next

- [Visual workflows](workflows/index.md): the same commands as flow diagrams.
- [Command reference](commands.md): every flag.
- [Troubleshooting](troubleshooting.md): when output is not what you expect.

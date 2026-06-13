---
name: rforge:r:s7-review
description: Static S7 OOP convention checker (advisory — naming/validators/methods/legacy/docs)
argument-hint: "[package] [--kind all|naming|validators|methods|legacy|docs] [--eco] [--runtime] [--format json|text]"
arguments:
  - name: package
    description: Package directory to review (positional; default cwd)
    required: false
    type: string
  - name: --kind
    description: Which convention family to run
    required: false
    type: string
    default: all
  - name: --eco
    description: Sweep the static families across every package in the ecosystem manifest, aggregated (pure-stdlib; composes with --runtime)
    required: false
    type: boolean
    default: false
  - name: --runtime
    description: Add an R-backed runtime pass (method-dispatch + validator-runtime) via lib.rcmd; degrades to advisory warn when R/S7 is unavailable
    required: false
    type: boolean
    default: false
  - name: --format
    description: Output format
    required: false
    type: string
    default: json
---

# /rforge:r:s7-review

Statically check **S7 OOP conventions** across an R package. Advisory only —
**never blocks** anything, mirrors `r:cran-prep`'s Tier-4 advisory tone. Pure
Python (no R, no Rscript): scans `R/*.R` + `NAMESPACE`.

## Usage

```bash
python3 -m lib.s7review --path "<package-dir>" --kind all --format json
```

- `package` (positional) — package directory (default: cwd).
- `--kind all|naming|validators|methods|legacy|docs` — limit to one family (default `all`).
- `--eco` — sweep the static families across **every package** in the ecosystem
  manifest and aggregate into one report (per-package breakdown + roll-up by
  family, ordered by the manifest's `manifest_order`). Pure-stdlib (no R). A
  package that fails to parse becomes a per-package `warn` — the sweep continues.
- `--runtime` — add an **R-backed runtime pass** that loads the package and
  introspects S7 at runtime, contributing two more families (`method-dispatch`,
  `validator-runtime`). Routed through `lib.rcmd` (the only R-touching module).
  Degrades to advisory `warn` stages ("runtime pass skipped: …") when R / S7 is
  unavailable — the static result is always intact, exit 0 always.
- The flags **compose**: `--eco --runtime` sweeps the ecosystem statically *and*
  runs the runtime pass per package.
- `--format json|text` — default `json`.

```bash
# ecosystem static sweep
python3 -m lib.s7review --path . --eco --format text
# single package, static + runtime
python3 -m lib.s7review --path "<package-dir>" --runtime
```

There is **no** `--write`/`--fix` (S7 fixes need human judgement, like `r:cran-prep`).

## Convention families

| Family | Codes | Source |
|---|---|---|
| naming | `class_name_case`, `class_name_mismatch`, `generic_name_case`, `prop_name_case` | static |
| validators | `missing_validator`, `validator_return_shape` | static |
| methods | `dangling_method`, `missing_methods_register` | static |
| legacy | `legacy_s4_in_s7`, `legacy_r5_in_s7`, `legacy_s3_generic` | static |
| docs | `undocumented_export`, `prop_type_unresolvable` | static |
| method-dispatch (`--runtime`) | `dead_generic`, `method_on_missing_class` | runtime |
| validator-runtime (`--runtime`) | `validator_not_enforcing` | runtime |

Static findings carry `source: "static"`; the two `--runtime` families carry
`source: "runtime"`. Every finding is `severity: "advisory"`, worded "looks
like / consider", never "must".

## Deferred

- **Cross-package S7 *contract* checks** (a class defined in pkg A and consumed
  by pkg B) remain future work; `--eco` today aggregates per-package static
  results, it does not yet cross-reference between packages.
- `--runtime` for non-S7 OOP (R6/S4) is out of scope — S7 only.

## Output

- Single package: `{kind: "s7review", status: "ok"|"warn", stages: [...],
  engine_missing: []}` (or one family envelope with `--kind X`). With `--runtime`,
  `stages` also includes the `method-dispatch` + `validator-runtime` stages.
- `--eco`: `{kind: "s7review-eco", status, packages: [...], rollup: {by_family,
  packages_total, packages_flagged, packages_clean}, engine_missing: []}`.

Advisory — exit 0 always.

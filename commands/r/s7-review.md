---
name: rforge:r:s7-review
description: Static S7 OOP convention checker (advisory — naming/validators/methods/legacy/docs)
argument-hint: "[package] [--kind all|naming|validators|methods|legacy|docs] [--format json|text]"
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
- `--format json|text` — default `json`.

There is **no** `--write`/`--fix` (S7 fixes need human judgement, like `r:cran-prep`).

## Convention families

| Family | Codes |
|---|---|
| naming | `class_name_case`, `class_name_mismatch`, `generic_name_case`, `prop_name_case` |
| validators | `missing_validator`, `validator_return_shape` |
| methods | `dangling_method`, `missing_methods_register` |
| legacy | `legacy_s4_in_s7`, `legacy_r5_in_s7`, `legacy_s3_generic` |
| docs | `undocumented_export`, `prop_type_unresolvable` |

Each finding carries `source: "static"` and `severity: "advisory"`, worded
"looks like / consider", never "must".

## Deferred (v1)

- **`--eco` (ecosystem consistency)** is deferred until the mediationverse
  house-convention spec lands (codes `divergent_class_def`,
  `inconsistent_prop_type`). Findings already carry `source: "static"`, so
  `--eco` is an additive follow-up with no envelope break.
- **Runtime checks** (validator soundness, actual registration,
  abstract-instantiability) are deferred to an R-backed v2 sibling.

## Output

A single `{kind: "s7review", status: "ok"|"warn", stages: [...], engine_missing: []}`
envelope (or one family envelope with `--kind X`). Advisory — exit 0 always.

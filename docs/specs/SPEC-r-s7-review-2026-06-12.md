# SPEC: `r:s7-review` — S7 convention checker for mediationverse

- **Status:** Draft — awaiting user review  <!-- Draft → In Progress → Shipped (vX.Y.Z) | Abandoned -->
- **Date:** 2026-06-12  <!-- creation date -->
- **Target version:** unscheduled candidate (post-v2.9.0); `35 → 36` commands when scheduled
- **Author:** synthesized by a max-effort design-panel Workflow (3 competing engine
  archetypes → 3 judges → synthesis), grounded in `lib/cranlint.py`, `lib/rcmd.py`,
  `lib/discovery.py`, `lib/deps_sync.py`
- **Related:** issue #26; [SPEC-cran-incoming-hardening-2026-06-10.md](SPEC-cran-incoming-hardening-2026-06-10.md)
  (`lib/cranlint.py` archetype + Tier-4 wiring); [SPEC-r-deps-sync-2026-06-10.md](SPEC-r-deps-sync-2026-06-10.md)
  (NAMESPACE/`@export` parser to reuse; static-precedes-runtime precedent)

## Summary

A new command `r:s7-review` backed by a new public pure-stdlib module
`lib/s7review.py` that statically checks **S7 OOP conventions** across an R package
(or the whole ecosystem with `--eco`). S7 is the modern R class system
(`new_class()`/`new_generic()`/`method()`); this polices *idiomatic, statically
verifiable* usage — naming, validator-presence, no S4/R5 leftovers, documented
exported classes. Advisory-only (never blocks `ready`), `cranlint.py` archetype.
`35 → 36` commands.

## Motivation

The mediationverse ecosystem is adopting S7, whose API is young and easy to use
inconsistently (snake_case vs UpperCamelCase classes, typed properties with no
validator, S4/R5 leftovers mid-migration, methods registered in the wrong place).
rforge can *run and validate* the dev cycle but has no S7-aware convention gate.
A static checker fills the gap cheaply and joins the existing analysis family
(`discovery`/`deps`/`deps_sync`/`cranlint`). Issue #26 requests exactly this.

A design panel scored three engine archetypes — pure-stdlib (static regex over
`R/*.R`), R-backed (load the package, introspect via the `S7` reflection API),
and hybrid. All three judges chose **pure-stdlib decisively** (28/22/19; 80/75/67;
26.5/23.5/22): the mission is *conventions*, which static analysis catches well,
with zero R/Rscript dependency and a hermetic single-fixture test path — exactly
the `cranlint.py` model. Runtime-only traps (validators that `error()` instead of
returning `character()`/`NULL`; methods silently unregistered without
`methods_register()`; abstract-instantiable classes) are real but are *correctness*
bugs in `r:check`/testthat territory, not conventions — deferred to an R-backed v2
sibling, exactly as static `r:deps-sync` preceded runtime `r:check --strict`.

## Goals

- Statically detect the 5 convention families below and emit advisory findings.
- Byte-identical `cranlint.py` envelope shape; advisory warn-only; exit 0 always;
  `engine_missing` always `[]`; stdlib-only imports.
- Reuse — not re-implement — `deps_sync`'s NAMESPACE/`@export` parser for the docs
  family; `discovery.find_r_packages()` for `--eco`.
- Forward-compat with the deferred R pass: every finding carries
  `source: "static"` so a future R pass can promote/clear without an envelope break.
- Config-driven house style via a `.rforge.yaml` `s7:` block (`class_case`,
  `generic_case`) so mediationverse sets its own conventions.

## Non-goals

- **No R / Rscript / S7-runtime dependency.** Pure-stdlib only. Runtime checks
  (validator-soundness, actual method registration, abstract-instantiability,
  property-type-resolves-at-runtime) are **deferred to an R-backed v2 sibling**.
- **No `--write`/`--fix`.** S7 fixes need human judgement (like `cranlint`).
- **Never blocks `ready`.** Advisory Tier-4 only if wired into `r:cran-prep`.
- **No new NAMESPACE/`@export` parser** — reuse `deps_sync`'s.
- `--eco` consistency checks are the most speculative — they ship only if Open
  Question 1 is resolved; otherwise `--eco` is deferred.

## Scope

### In scope (decided) — 5 convention families + gated ecosystem

| Family | Codes | Static check |
|---|---|---|
| **naming** | `class_name_case`, `class_name_mismatch`, `generic_name_case`, `prop_name_case` | `new_class()` name UpperCamelCase + unique; bound var matches `name=` string; generics snake_case; property names snake_case |
| **validators** | `missing_validator`, `validator_return_shape` | every `new_class()` with typed `properties=` declares a `validator=`; flag validators that obviously `return(TRUE/FALSE)` vs `character()`/`NULL` |
| **methods** | `dangling_method`, `missing_methods_register` | `method(generic, Class) <- fn` references a generic/class defined-or-imported in source; flag `method()` for an external generic with no `methods_register()` anywhere (heuristic) |
| **legacy** | `legacy_s4_in_s7`, `legacy_r5_in_s7`, `legacy_s3_generic` | no `setClass`/`setGeneric`/`setMethod`/`setRefClass`/`representation()`/`R6Class()` co-residing with `new_class`; flag `UseMethod()` dispatching on an S7 class |
| **docs** | `undocumented_export`, `prop_type_unresolvable` | every exported S7 class (NAMESPACE `export()` or `@export`) has a `#'` block before `new_class`; property's declared class resolves to a class in scanned source |
| **(ecosystem, `--eco`)** | `divergent_class_def`, `inconsistent_prop_type` | same class name not defined with divergent property sets across packages; consistent `class_*` vocabulary — gated, advisory, most speculative |

### Out of scope (YAGNI / deferred)

- R-backed runtime pass (v2 sibling): validator-soundness, runtime method
  registration, abstract-instantiability, runtime type resolution.
- `--eco` ships only if Open Question 1 resolves; else deferred.
- Autofix.

## Architecture

New public module `lib/s7review.py`, mirroring `lib/cranlint.py:`

- Public: `check_naming(path)`, `check_validators(path)`, `check_methods(path)`,
  `check_legacy_oop(path)`, `check_class_docs(path)`, `run_all(path)` (worst-of
  `ok<warn` roll-up), `review_ecosystem(root)` (maps `run_all` over
  `discovery.find_r_packages`).
- Internal: `_scan_r_files(path)`, `_find_s7_constructs(text)` (call +
  balanced-paren match), `_envelope(kind, status, findings, messages)`
  byte-identical to `cranlint`'s. A single `_S7_VOCAB` constant block
  (`new_class`/`new_generic`/`method`/`class_*`) pins the targeted S7 API — one
  edit point as S7 churns.
- Imports limited to `argparse`/`json`/`os`/`re`/`sys`/`pathlib`.
- Docs family reuses `deps_sync`'s NAMESPACE/`@export` parser.
- Invoked `python3 -m lib.s7review` (never `python3 lib/s7review.py`). Joins the
  public-modules list in CLAUDE.md; `docs/reference/s7review.md` via
  `gen_lib_reference.py` (`--check` CI gate).

Command file `commands/r/s7-review.md`, `name: rforge:r:s7-review`:

| Flag | Type | Default | Meaning |
|---|---|---|---|
| `package` (positional) | string | cwd | single package dir OR ecosystem root |
| `--eco` | boolean | false | scan all packages via `discovery.find_r_packages`; emits eco rollup |
| `--kind` | string | `all` | `all\|naming\|validators\|methods\|legacy\|docs` |
| `--format` | string | `json` | `json\|text` |

No `--write`/`--fix`. Body invocation: `python3 -m lib.s7review --path "<path>" --kind all --format json`.

## Dependencies

None new — Python 3 stdlib only. No R, no `gh`. Pure-stdlib like `cranlint`/
`runiverse`, so `engine_missing` is always `[]`.

## Error handling

Advisory, exit 0 always, never raises:

- No `R/` dir / unreadable files → `warn` envelope with a clear message
  (`"No R/ directory found — is this an R package? Try /rforge:detect"`).
- Package using no S7 → `ok` + `"No S7 constructs found — nothing to review"`
  (absence is not a violation).
- A construct whose nested parens won't balance → silently skipped (false negative,
  never a false BLOCK), mirroring `cranlint` swallowing `re.error`.
- `--eco`: one unparseable package degrades that package's row to `warn`; the sweep
  continues.

Envelope (single package, `run_all`):
```
{kind:"s7review", status:"ok"|"warn", stages:[<5 per-check envelopes>], engine_missing:[]}
```
Each finding: `{code, severity:"advisory", file, line, symbol, source:"static", message}`.
Messages worded "looks like / consider", never "must". Ecosystem (`--eco`):
`{kind:"s7review-eco", status:<worst across pkgs>, packages:[...], findings:[divergent_class_def, inconsistent_prop_type], engine_missing:[]}`.

## Testing

Both gates must pass: `python3 -m pytest tests/` and `bash tests/test-all.sh`.

- `tests/test_s7review.py` — fixture cases per family (a deliberately-bad S7
  fixture package + a clean one), asserting codes/severity and the advisory
  envelope contract (`status ∈ {ok,warn}`, `engine_missing == []`, exit 0).
- `tests/test-all.sh` — a `lib.s7review` CLI-smoke line (R-free, advisory envelope),
  plus `gen_lib_reference.py --check` covering the new reference page. Gates rise
  ~33→34 checks, ~230→231 pytest.

## Documentation impact

- `commands/r/s7-review.md` (new) + `arguments:` array synced with `## Usage`.
- `lib/s7review.py` added to CLAUDE.md "lib/ Python package convention" public list.
- `docs/reference/s7review.md` auto-generated by `gen_lib_reference.py`.
- Command-count `35 → 36` everywhere version_sync touches; bump `package.json` →
  `version_sync.py`; `marketplace.json` manual; `mkdocs.yml extra.rforge.command_count`.
- CHANGELOG, `.STATUS`, REFCARD (CRAN/quality box), a short tutorial mention.
- Optionally wire into `r:cran-prep` as an advisory Tier-4 stage (never blocks).

## Implementation order

1. **(worktree)** `feature/r-s7-review` off `dev`.
2. TDD `lib/s7review.py`: bad/clean fixture package → write failing
   `tests/test_s7review.py` per family → implement `_find_s7_constructs` +
   the 5 `check_*` + `run_all` → green. Reuse `deps_sync`'s NAMESPACE parser.
3. `commands/r/s7-review.md` + frontmatter.
4. `--eco` via `review_ecosystem` (only if Open Question 1 resolved).
5. test-all CLI-smoke + `gen_lib_reference.py` regen; both gates green.
6. Version bump (`35→36`), docs, CHANGELOG/.STATUS.
7. PR feature → dev.

Steps 2–5 are code (worktree). This spec file itself is docs-only (committed on `dev`).

## Open questions / risks

1. **What defines the mediationverse house convention?** The `--eco` consistency
   checks are only grounded against a shared spec. Encode defaults
   (UpperCamelCase classes / snake_case generics) + read overrides from a
   `.rforge.yaml` `s7:` block, or require an explicit ecosystem-manifest convention
   section before `--eco` emits anything? *Decides whether `--eco` ships in v1.*
2. **How aggressive should `missing_methods_register` be statically?** It is the
   highest-value static approximation of S7's silent-non-registration trap, but the
   most false-positive-prone (the call may legitimately live elsewhere). Ship as a
   quiet advisory in v1, or hold for the R-backed v2 sibling that confirms
   registration at runtime?

## Sources

- S7 package reference — `new_class()`/`new_generic()`/`method()`, typed properties,
  validators returning `character()`/`NULL`, `methods_register()` in `.onLoad`.
  <https://rconsortium.github.io/S7/>
- rforge `lib/cranlint.py` (advisory pure-stdlib archetype), `lib/deps_sync.py`
  (NAMESPACE/`@export` parser), `lib/discovery.py` (`find_r_packages`), `CLAUDE.md`
  (lib/ package convention).

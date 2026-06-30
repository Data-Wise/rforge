# SPEC: `r:s7-review --eco` + R-backed runtime checks (v2 sibling)

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved
**Parent:** `SPEC-r-s7-review-2026-06-12.md` (the shipped v1 static checker)
**Target:** v2.11.0 bundle (feature 2 of 3)

---

## Summary

`r:s7-review` v1 (shipped v2.10.0) is a **pure-stdlib static** S7 convention checker:
5 advisory families (naming/validators/methods/legacy/docs) parsed from source, no R.
This adds two **composable flags** that extend it without rewriting v1:

| Flag | What it adds | Architecture impact |
|---|---|---|
| `--eco` | Run the existing 5 static families across **every package** in the ecosystem manifest, aggregate into one report. | **None — stays pure-stdlib.** |
| `--runtime` | An **R subprocess pass** that loads the package and introspects S7 at runtime; 2 new families. | Adds R, routed through `lib.rcmd` (the only R-touching module). |

The flags compose: `r:s7-review --eco --runtime` sweeps the ecosystem statically *and*
runs the runtime pass per package.

## `--eco` — ecosystem static sweep (pure-stdlib)

- Resolve the package set via **`lib.discovery.find_r_packages`** (the single source of
  truth for the on-disk package set; honors the ecosystem manifest + `manifest_order`).
- Run `s7review.run_all` (the existing static families) on each package.
- Aggregate: one envelope with a per-package breakdown + an ecosystem roll-up
  (total findings by family, packages clean vs flagged). Ordered by `manifest_order`
  when present, else discovery order.
- Degrades gracefully: a package that fails to parse is reported as a per-package warn,
  never aborts the sweep.

## `--runtime` — R-backed runtime checks

The architecture invariant: **`lib.rcmd` is the only module that shells out to Rscript.**
So the runtime pass is a **new `s7runtime` engine in `lib/rcmd.py`**, not a direct
subprocess call from `s7review.py`.

### New engine: `s7runtime`

- `lib.rcmd.run(kind="s7runtime", path=...)` shells to `Rscript` running an embedded R
  program that: loads the package (`pkgload::load_all` / installed namespace), enumerates
  S7 classes, generics, and methods, then emits **JSON** (via `jsonlite`, the existing
  rcmd convention — auto_unbox guarded, stdout-contamination guarded per the v2.1.0
  serialization lessons).
- Normalized into the standard rcmd envelope, then **merged** by `s7review` with the
  static findings into one combined envelope.

### Two new runtime families

1. **`method-dispatch`** — for each declared S7 generic, does dispatch actually resolve
   to a method for its registered classes? Flags generics with no resolvable method
   (`dead_generic`) **and** methods whose dispatch class has no resolvable namespace
   binding (`method_on_missing_class`). **UPDATE (post-v2.11.0):** `method_on_missing_class`
   is now implemented — the original "not decidable from the registry alone" deferral was
   refuted: each `S7_method` carries `attr(., "signature")` (its dispatch class objects),
   so resolvability against the loaded namespace is decidable. See
   `SPEC-s7-method-missing-class-2026-06-13.md`.
2. **`validator-runtime`** — instantiate each S7 class with a deliberately invalid
   property value; flag classes whose `validator` fails to reject it (validator present
   in source but not actually enforcing — the runtime sibling of v1's static
   `validators` family).

### Safety classification

- `s7runtime` **loads and executes package code** (like `load`/`test`), so it is *not*
  inert — but it is **read-only** (no file writes, no network, no install). It is added
  to **`SAFE_AUTORUN`** alongside `load`/`test`/`check`/`coverage`/`lint`/`spell`.
- The orchestrator agent's recipe validator (`tests/_check_agent_engines.py`) already
  asserts auto-run kinds are real + safe; `s7runtime` must pass it.
- Requires R + the package's deps. When R is missing or load fails, `--runtime` degrades
  to a `warn` envelope ("runtime pass skipped: <reason>") and the static result still
  returns — never raises, mirroring `runiverse`'s offline degradation.

## Command surface

`commands/r/s7-review.md` gains `--eco` and `--runtime` in the `arguments:` array +
`## Usage` body. No new command (flags, not commands) → **command count unchanged**.

## Out of scope

- Fixing S7 issues (advisory only, like v1).
- Cross-package S7 *contract* checks (e.g. a class in pkg A used by pkg B) — future.
- `--runtime` for non-S7 OOP (R6/S4) — S7 only.

## Tests (gates)

- `--eco` over a 2-package fixture ecosystem → asserts aggregation + `manifest_order`.
- `s7runtime` rcmd engine: opt-in real-R e2e (like the existing rcmd e2e tests) against
  a fixture package with (a) a dead generic and (b) a non-enforcing validator → asserts
  both runtime families fire. Skipped when R absent.
- Degradation: `--runtime` with R unavailable → warn envelope, static result intact,
  exit 0.
- `_check_agent_engines.py` still green with `s7runtime` in SAFE_AUTORUN.
- pure-stdlib guard: `s7review.py` imports no R and shells out to nothing (greppable —
  all R goes through `lib.rcmd`).

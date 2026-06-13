# SPEC: s7-review `methods_on_missing_class` — close the deferred runtime family

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved (autonomous build, pre-approved)
**Parent:** `SPEC-r-s7-review-eco-2026-06-13.md` (Deferred note)
**Target:** post-v2.11.0 (single deferred family)

---

## Summary

`r:s7-review --runtime` (v2.11.0) ships two working runtime families (`dead_generic`,
`validator_not_enforcing`) plus a **third hardcoded-empty placeholder**:
`methods_on_missing_class`. The v2.11.0 spec deferred it claiming it was "not decidable
from the S7 method registry alone." **This spec refutes that empirically and implements it.**

## Empirical finding (refutes the deferral)

Investigated S7's real method-table structure (R + S7 present):

- `attr(generic, "methods")` is an environment keyed by class **name** (nested for
  multi-dispatch). Each value is an `S7_method` object.
- Each `S7_method` carries **`attr(method, "signature")`** — a *list of the actual
  dispatch class objects* (S7_class objects for S7 classes; base-type specs otherwise).
- So for every registered method we can recover its dispatch class object(s) and check
  **resolvability by name against the loaded namespace** — fully decidable.

Confirmed detection: a method registered on an inline, unbound class
(`method(gen, new_class("Ghost")) <- fn`) yields a registry whose `Ghost` signature
class is an `S7_class` whose name does **not** resolve in the namespace → a dead,
unreachable method (nothing can ever construct a `Ghost` to dispatch on). Base-type
methods (`method(gen, class_integer)`) have a signature element that is **not** an
`S7_class` and are correctly excluded.

## What the family detects

**`methods_on_missing_class`**: a registered method whose dispatch signature includes an
**S7 class that is not resolvable by name** in the loaded package namespace (or a declared,
loaded import). This is the runtime sibling of `dead_generic` — a method that can never be
dispatched because its dispatch class has no reachable binding (typically an inline /
unexported `new_class()` left in a `method()` call, or a method left dangling after a
class was renamed/removed).

## Algorithm (in the `s7runtime` engine, `lib/rcmd.py`)

For each S7 generic in the namespace, walk its method registry; for each `S7_method`, for
each element of `attr(method, "signature")`:

1. **Skip non-S7 signature elements** — base types (`class_integer`/`class_character`/…)
   are not `S7_class` objects → never "missing".
2. **Skip the universal types** — `S7_object` / `class_any` (`ANY`) union dispatch.
3. For an `S7_class` element with name `N` and package `P`:
   - `P` set and `P != this_package` → **resolvable** iff `exists(N, asNamespace(P))`
     (imported class — the import is loaded, so it resolves). Not missing.
   - `P` unset or `P == this_package` → **resolvable** iff `N` is bound to an `S7_class`
     in this package's namespace. If not bound → **MISSING** → flag
     `"<generic> -> <N>"`.

Emit `methods_on_missing_class` as the list of `"<generic> -> <class>"` strings (was
`character()`). Normalization in `_status_for` / `normalize` already aggregates all three
runtime lists — no change needed there.

## False-positive guards (the adversarial concerns)

- **Base types** — excluded by the `inherits(sig, "S7_class")` gate (empirically verified:
  `integer` key → `s7class=FALSE`).
- **Imported classes** — resolved via the class's `package` attribute against that
  package's loaded namespace; not flagged.
- **`ANY` / `S7_object` union dispatch** — explicitly skipped.
- **Parent classes** — irrelevant; only the dispatch class itself is checked.
- **Multi-dispatch** — every signature element checked independently; a method dispatching
  on `list(Real, Ghost)` flags only `Ghost`.

## Out of scope

- Cross-package *undeclared-dependency* dispatch (method on `otherpkg::Class` where
  `otherpkg` ∉ DESCRIPTION) — a different, DESCRIPTION-aware check; future.
- Static (non-runtime) detection — this is a `--runtime`-only family, like its siblings.

## Tests (gates)

- **Real-R e2e** (R-gated `skipif`, like the existing s7runtime tests): a fixture package
  with (a) a method on a real bound class (NOT flagged) and (b) a method on an inline
  unbound class (flagged). Assert `methods_on_missing_class` contains exactly the dangling
  one. Reuse/extend the `s7pkg.bad` fixture.
- **Base-type non-flag**: a `method(gen, class_integer)` in the fixture must NOT appear.
- **Degradation**: unchanged — R/S7 absent → `--runtime` still degrades to advisory `warn`.
- `_check_agent_engines.py`, `version_sync --check`, `gen_lib_reference --check` stay green.
- Update `commands/r/s7-review.md` (move `method_on_missing_class` from Deferred into the
  active family table) + this parent spec's Deferred note.

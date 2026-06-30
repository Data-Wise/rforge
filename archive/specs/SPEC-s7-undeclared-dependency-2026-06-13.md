# SPEC: s7-review `method_undeclared_dependency` (cross-package breadth)

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved (bundle build)
**Parent:** `SPEC-r-s7-review-eco-2026-06-13.md` / `SPEC-s7-method-missing-class-2026-06-13.md`
**Target:** v2.12.0 bundle (3 of 3)

---

## Summary

The s7-review `--runtime` `method-dispatch` family flags `dead_generic` and
`method_on_missing_class`. This adds the cross-package check named (and deferred) in the
parent spec: **`method_undeclared_dependency`** — a method dispatching on an S7 class from
a package that is **not declared** in `DESCRIPTION` (`Imports`/`Depends`/`LinkingTo`),
typically a `Suggests`-only class. At a user's site without that package the dispatch class
never registers → the method silently never fires. A real, decidable correctness/CRAN bug.

## Decidability

`method_on_missing_class` (v2.11.1) established that each `S7_method` carries
`attr(., "signature")` — the dispatch class objects — and an S7 class object exposes its
originating package via `attr(class, "package")`. So for each dispatch class we know its
package. Cross-checking that package against the loaded package's `DESCRIPTION` declared
deps is decidable.

## Design (in the `s7runtime` engine, `lib/rcmd.py`)

Extend the existing per-signature loop (the one added for `method_on_missing_class`):

1. Read the loaded package's declared deps once: parse `DESCRIPTION`
   `Imports` + `Depends` + `LinkingTo` package names (R-side, from the loaded path; the
   package name itself + `base`/`methods`/recommended-pkgs are always allowed).
2. For a dispatch class that **is** resolvable (so not `method_on_missing_class`) and whose
   `package` attribute `P` is set, `P != this_package`, and `P ∉ declared_deps` →
   flag `methods_undeclared_dependency` as `"<generic> -> <P>::<class>"` (structured
   `{generic, class, package}`).
3. The two checks are mutually exclusive per signature: unresolvable → `missing_class`;
   resolvable-but-undeclared-package → `undeclared_dependency`; resolvable-and-declared →
   clean.

Consumer (`lib/s7review.py` `_runtime_stages`): map the new engine list into
`method_undeclared_dependency` findings in the `method-dispatch` family (advisory,
`source: "runtime"`).

## False-positive guards (the adversarial concerns)

- **Base types** — not S7 classes; never considered (same gate as missing_class).
- **This package's own classes** — `P` unset or `== this_package`; skipped.
- **Recommended/base packages** (`methods`, `stats`, `utils`, …) — treated as always-allowed
  (they need no `Imports` declaration); maintain an allowlist so a method on a base-S7 type
  isn't flagged.
- **`Depends` vs `Imports`** — both count as declared (a `Depends` package is attached).
- **`ANY`/`S7_object`/unions** — skipped (same as missing_class).

## Scope decisions

- Reuses the v2.11.1 signature-walking machinery — no new traversal.
- DESCRIPTION parsing is R-side in the engine (the path is already loaded); the package's
  own name is read via `pkgload::pkg_name` (already used).
- Out of scope: cross-package S7 *contract* checks (a class in pkg A consumed by pkg B's
  generic) — that needs an ecosystem-wide S7 registry, a separate larger feature.

## Tests (gates)

- Real-R e2e (R-gated): a fixture package whose method dispatches on a class from a helper
  package that is installed but **not** in the fixture's `DESCRIPTION` → assert
  `methods_undeclared_dependency` fires; a method on a properly-`Imports`-declared class
  does NOT fire; a base-type/`methods` class does NOT fire.
- Consumer mapping test (monkeypatched engine env) → `method_undeclared_dependency` finding
  in `method-dispatch`.
- `commands/r/s7-review.md` family table + `docs/commands.md` + parent spec + CHANGELOG
  updated; `_check_agent_engines.py`, `version_sync --check`, `gen_lib_reference --check`,
  and the new commands-doc sync-gate all green.

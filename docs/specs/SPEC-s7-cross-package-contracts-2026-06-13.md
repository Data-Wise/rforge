# SPEC — cross-package S7 contract checks (candidate B, sub-item 1)

**Date:** 2026-06-13
**Branch:** `feature/s7-cross-package-contracts` (worktree off `dev` — created at
implementation time, a separate session; not while `feature/diff-aware-baseline-caching`
is still open).
**Status:** approved design (approach + v1 taxonomy confirmed via AskUserQuestion).
**Builds on:** `lib/s7review.py` (`run_eco`, `_find_s7_constructs`, NAMESPACE
parsing at `_imported_symbols`/`_registered_s3_methods`), `lib/discovery.py`
(`detect_ecosystem`, `Package`, `read_description` → `Description.{imports,depends,
linking_to}`), and v2.12.0's runtime `method_undeclared_dependency` (this is its
**static, ecosystem-scoped** sibling).

## Problem

`r:s7-review --eco` sweeps every package in an ecosystem but runs the five static
families **per package, in isolation**. It has no cross-package view, so it cannot
catch the failure mode that only an ecosystem orchestrator can see:

> Package **B** defines an S7 `method(generic, C)` dispatching on a class **C**
> that is defined in a **sibling** package **A** — but B doesn't declare A in its
> `DESCRIPTION`. At a user's site the class object never resolves at B's load time,
> so the method **silently never dispatches**. (Or: A *is* declared, but A's
> `NAMESPACE` doesn't `export(C)`, so B still can't reach it.)

This is the same contract v2.12.0's runtime `method_undeclared_dependency` enforces
— but that resolves the dispatch class against **installed** packages (needs R +
the whole stack installed and loadable). The ecosystem version resolves against
**sibling source packages in the repo**, catching the break *before* anything is
installed — exactly when a cascade developer introduces it (edit A's class, add a
method in B that uses it, forget to declare A).

## Goal

In the `--eco` sweep, build an ecosystem-wide S7 class registry and flag
cross-package S7 dispatch whose dependency contract is unsatisfiable:

- **`cross_package_undeclared_contract`** — B dispatches on A's class C; A ∉ B's
  `DESCRIPTION` `Imports`/`Depends`/`LinkingTo`.
- **`cross_package_unexported_class`** — A *is* declared in B's deps, but A's
  `NAMESPACE` does not export C (no `export(C)` / `exportClasses(C)`), so B can't
  reach it either.

Both answer one question: *can B actually reach A's class C?* Advisory family
`cross-package-contract`, surfaced in the `--eco` rollup. Automatic under `--eco`
(it inherently needs the ecosystem); silent when no cross-package S7 dispatch
exists. **No new command, no new flag.**

## Non-goals

- **Runtime resolution.** Static, name-based, in `s7review.py` (pure-stdlib). A
  runtime version would need every ecosystem package simultaneously loadable via
  `pkgload` — a high, fragile bar — and the existing `--runtime` engine
  (`rcmd.s7runtime`) is single-package. The static tradeoff is acceptable because
  the family is advisory.
- **`contract_drift`** (A changes C's property set → B's methods that assume the
  old shape break). Deferred — needs static property-set extraction + usage
  analysis in B; fuzzy and false-positive-prone. Noted as a future iteration.
- **Sub-item 2 of candidate B (full R6/S4 convention checking).** A separate spec
  if pursued at all (rforge is S7-focused; `check_legacy_oop` already gives the
  migration signal).

## Design

### Approach: static, extending `run_eco`

`run_eco` is pure-stdlib and already resolves the package set + paths via
`discovery.detect_ecosystem`. The cross-package pass slots in there: build the
registry once across all packages, then run a per-package contract check that
consults it.

### 1. Ecosystem class registry

```python
def build_class_registry(packages: list[discovery.Package]) -> dict[str, list[str]]:
    """Map every S7 class NAME → the package(s) that define it (via new_class).

    Scans each package's R/ with _find_s7_constructs; a `new_class` construct's
    name is `_name_arg(args_raw)` or its `bound` LHS. Returns name → sorted unique
    package names. A name defined in >1 package (a collision) maps to a list with
    >1 entry — the consumer treats that as statically ambiguous (see below).
    """
```

Name-based, because static parsing has only names (no runtime object identity —
the v2.11.1 lesson that S7 resolution should be by identity applies to the
*runtime* engine; the static `--eco` registry cannot do better than names). This
is the **key limitation**, documented in the family's messages: two packages
defining a same-named class is ambiguous; the check is conservative there (below).

### 2. Per-package contract check

```python
def check_cross_package_contracts(
    pkg: discovery.Package,
    registry: dict[str, list[str]],
    exports: dict[str, set[str]],   # pkg name → set of exported class names
) -> dict:                          # envelope, kind="cross-package-contract"
```

For each `method(generic, C)` in `pkg`'s `R/` (dispatch class `C` extracted from
the `method(...)` construct, the arg after the generic — reuse `_find_s7_constructs`
+ the `check_methods` arg parsing; handle `method(g, ClassName)` and the
multi-dispatch `method(g, list(A, B))` forms):

1. `providers = registry.get(C, [])`. If empty → **skip** (C is local-undefined,
   a base type, or an *external* CRAN class — out of scope here; the runtime
   `method_on_missing_class` / `method_undeclared_dependency` families handle
   external/missing). 
2. If `pkg.name in providers` → **skip** (C is defined locally; local definition
   satisfies dispatch even if the name also exists elsewhere — ambiguous but
   not a cross-package break).
3. `siblings = [p for p in providers if p != pkg.name]` (all sibling definers).
   `declared = imports ∪ depends ∪ linking_to` (version specs stripped) from
   `read_description(Path(pkg.path)/"DESCRIPTION")`.

   **Reachability (re-export-aware — hardened after the adversarial review).** C is
   reachable from `pkg` iff some **declared ecosystem dep exports C** — whether it
   *defines* C **or** *re-exports* it (`importFrom(A, C)` + `export(C)`, the facade
   idiom: `pkg` rightly depends on the re-exporter, not the original definer) — OR a
   declared **definer**'s export set is statically unknowable (no NAMESPACE /
   `exportPattern` → suppress to avoid a false positive). Concretely:

   ```
   declared_definers = [s for s in siblings if s in declared]
   reachable = any(C in (exports[d] or set()) for d in declared if d in exports) \
               or any(exports[s] is None for s in declared_definers)
   if reachable:            → clean
   elif declared_definers:  → cross_package_unexported_class (a declared definer
                              exists but no declared dep exports/re-exports C)
   else:                    → cross_package_undeclared_contract (no declared dep
                              defines OR re-exports C)
   ```

   Collision handling falls out naturally: if any declared dep exports C, it's clean
   regardless of other ambiguous definers; only when no declared dep can provide C is
   it flagged. The finding message names the candidate provider packages.

   > **Why re-export-aware:** the first design checked only whether a declared
   > *definer* exported C, which false-flagged the common facade pattern (consumer
   > depends on a re-exporter, not the definer). The adversarial review (whose
   > rollout focus list below explicitly named "re-exported classes") caught it; the
   > reachability test now consults every declared dep's export set, not just
   > definers'. Two other review fixes: the construct parser binds on `=` as well as
   > `<-` (`Foo = new_class()` was invisible to the registry → missed contracts), and
   > NAMESPACE `export()` is parsed with balanced parens across lines (a wrapped
   > multi-line export() had read as the empty set → false `unexported`).

Finding shape (consistent with existing s7review dict findings):

```python
{"code": "cross_package_undeclared_contract", "severity": "advisory",
 "file": "R/methods.R", "line": 42, "class": "C", "generic": "format",
 "providers": ["A"], "consumer": "B",
 "message": "method(format, C) in 'B' dispatches on S7 class 'C' defined in "
            "sibling package 'A', which 'B' does not declare in "
            "Imports/Depends/LinkingTo — the class will not resolve at B's site "
            "and the method will never dispatch. Declare 'A'."}
```

### 3. NAMESPACE export extraction

```python
def _exported_s7_classes(pkg_path) -> set[str]:
    """Class names a package exports via NAMESPACE export(C)/exportClasses(C)."""
```

Reuse the existing NAMESPACE-reading pattern (`_imported_symbols`/
`_registered_s3_methods` already open + scan `NAMESPACE`). S7 classes are usually
exported with plain `export(<ClassName>)`; also honor `exportClasses(...)`. Treat
exports as **unknown** (and **suppress** the unexported finding for that provider,
to avoid a false positive) when the class set can't be enumerated statically:
(a) the package has **no** NAMESPACE (source-only, not yet `document()`-ed), or
(b) the NAMESPACE uses `exportPattern(...)` (regex export — the exported set is
unknowable without evaluating the pattern against all symbols). In both cases only
`undeclared` can fire for that provider, never `unexported`.

### 4. Wiring into `run_eco`

```text
eco = discovery.detect_ecosystem(root)
pkgs = ordered(eco.packages)
registry = build_class_registry(pkgs)              # one pass over all pkgs
exports  = {p.name: _exported_s7_classes(p.path) for p in pkgs}
for pkg in pkgs:
    ... existing run_all(pkg.path) stages ...
    contract = check_cross_package_contracts(pkg, registry, exports)
    append contract as an extra stage; fold its count into rollup.by_family
```

The per-package stages gain a `cross-package-contract` entry; the rollup
`by_family` gains its count. `run_eco`'s "never raises / per-package warn on
exception" contract is preserved (wrap the contract check the same way).

## New / changed functions (`lib/s7review.py`)

| Function | Responsibility |
|---|---|
| `build_class_registry(packages) -> dict[str, list[str]]` | ecosystem class name → defining package(s) |
| `_exported_s7_classes(pkg_path) -> set[str]` | class names a package exports via NAMESPACE |
| `check_cross_package_contracts(pkg, registry, exports) -> dict` | per-package envelope, `cross-package-contract` family |
| `run_eco(...)` | build registry + exports once; add the contract stage per package; roll up |

All three new functions are **public** (s7review is a public module) → add to
`docs/reference/s7review.md` via `scripts/gen_lib_reference.py` (CI gate).

## Tests (TDD, `tests/test_s7review.py`, pure-stdlib tmp ecosystems)

Build small multi-package fixtures (pkgA defines `new_class`, pkgB has a
`method(g, C)` + a DESCRIPTION + NAMESPACE):

1. `build_class_registry` maps class → defining package across packages.
2. registry collision: same-named class in two packages → both listed.
3. **undeclared**: B's `method(g, C)`, C defined in A, A ∉ B deps → `cross_package_undeclared_contract`.
4. **declared + exported** → no finding.
5. **declared, NOT exported** (A lacks `export(C)`) → `cross_package_unexported_class`.
6. **declared, no NAMESPACE** (un-generated) → undeclared suppressed-or-fires per deps, unexported **suppressed** (no FP).
7. **local class** (C defined in B itself) → no finding.
8. **external/unknown class** (C not in registry) → no finding (out of scope).
9. **collision, one declared+exporting**: C in A (declared+exported) and D (not declared) → no finding (a satisfying provider exists).
10. `run_eco` surfaces `cross-package-contract` in `rollup.by_family` and the per-package stages.
11. single-package ecosystem → zero cross-package findings; never raises.
12. multi-dispatch `method(g, list(A_class, B_class))` → each dispatch class checked.

## Gates

- `python3 -m pytest tests/` — new cross-package cases + all existing green.
- `bash tests/test-all.sh` — incl. lib reference sync (regen `s7review.md`),
  version/count sync, commands-doc sync-gate (no new flag, but update the
  `r:s7-review` command prose + `docs/commands.md` to describe the new `--eco`
  family — prose, gate is flag-level so it won't fail, but keep docs honest).
- No version bump on the feature branch — ships in the next release bundle.

## Docs to update (ungated — audit manually)

- `commands/r/s7-review.md` — `--eco` section: add the `cross-package-contract`
  family (the two findings + the static name-based caveat).
- `docs/commands.md` — `r:s7-review` `--eco` description.
- `docs/tutorials/s7-convention-checking.md` — a cross-package example.
- `docs/reference/s7review.md` — auto-regen (gated).

## Rollout

Feature branch `feature/s7-cross-package-contracts` off `dev`, **its own session**
(no worktree stacking). TDD per `superpowers:subagent-driven-development` or inline.
Pre-merge adversarial review (per the established cadence) focused on:

- **False-positive control** — the static name-based limitation: collisions,
  re-exported classes (pkg B re-exports A's class), classes defined via a non-`new_class`
  path the parser misses, `method()` on a base-type/`class_*` S7 builtin.
- **Registry completeness** — dynamically/programmatically defined classes,
  `new_class` inside a function body, classes defined in a package but used only
  internally (not a contract issue).
- **DESCRIPTION/NAMESPACE parsing edges** — version specs, `Remotes`, no-NAMESPACE
  source packages, `exportPattern` (a regex export → exports unknowable → suppress).

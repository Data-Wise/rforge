# 🔎 S7 convention review

!!! tip "TL;DR (30 seconds)"
    - **What:** `r:s7-review` is the complete convention auditor for [S7](https://rconsortium.github.io/S7/)
      (the modern R OOP system) — naming, validators, methods, legacy leftovers, docs, plus
      ecosystem and runtime families.
    - **Why:** S7 has idioms a linter won't catch — unbound classes, no-op validators, methods
      that silently never dispatch. This command catalogs them.
    - **Three modes:** **static** (default, pure-Python, no R) → **`--eco`** (sweep every package
      in the manifest + cross-package contracts) → **`--runtime`** (load the package, introspect S7).
    - **Next:** the [S7 convention checking tutorial](../tutorials/s7-convention-checking.md) for a
      hands-on walkthrough; this page is the **complete finding-family catalog**.

---

## What this command covers

This is the **Command Guide** for `r:s7-review` — the exhaustive finding-family reference. For a
guided walkthrough, fix-and-recheck loop, and mermaid mode diagram, read the
[S7 convention checking tutorial](../tutorials/s7-convention-checking.md) instead; this page does
not duplicate it.

`r:s7-review` runs in three layered modes. The default static mode is pure-stdlib (no R, no
`Rscript`) and parses `R/*.R` + `NAMESPACE`. `--eco` adds an ecosystem-wide sweep with a family the
single-package modes can't compute. `--runtime` adds an R-backed pass that actually loads the
package. The flags **compose** — `--eco --runtime` sweeps the ecosystem statically *and* runs the
runtime pass per package.

| Mode | Flag | Engine | Adds families |
|---|---|---|---|
| Static (default) | *(none)* | pure-stdlib `lib.s7review` (no R) | naming, validators, methods, legacy, docs |
| Ecosystem sweep | `--eco` | pure-stdlib `lib.s7review` (no R) | **cross-package-contract** (the 5 static families run per package too) |
| Runtime pass | `--runtime` | `s7runtime` R engine via `lib.rcmd` | **method-dispatch**, **validator-runtime** |

**Every finding is advisory** — `severity: "advisory"`, worded "looks like / consider", never
"must". The command **always exits 0** and never blocks anything.

---

## Finding-family catalog

The catalog is the centerpiece. Each section below covers one mode's families and the exact codes
each can emit.

### Static families (default — always run)

Pure-Python parsing of `R/*.R` + `NAMESPACE`. These run in every mode (static, `--eco`, and
`--runtime`). Findings carry `source: "static"`.

| Family | What it flags | Severity |
|---|---|---|
| **naming** | `class_name_case` — class not UpperCamelCase; `class_name_mismatch` — bound variable name ≠ the class's `name=`; `generic_name_case` / `prop_name_case` — generic or property name not snake_case | advisory |
| **validators** | `missing_validator` — a `new_class` with typed properties but no `validator=`; `validator_return_shape` — a validator returning `TRUE`/`FALSE` (S7 wants `character()`/`NULL`) | advisory |
| **methods** | `dangling_method` — a `method(generic, Class)` whose `generic` is neither defined (`new_generic`) nor imported in scanned source; `missing_methods_register` — a method on an external generic with no `methods_register()` call anywhere in `R/` (quiet advisory) | advisory |
| **legacy** | `legacy_s4_in_s7` — `setClass`/`setGeneric`/`representation` co-residing with S7; `legacy_r5_in_s7` — `setRefClass`/`R6Class` alongside S7; `legacy_s3_generic` — an S3 generic of the name shape `foo.<S7Class> <- function` (migration leftover) | advisory |
| **docs** | `undocumented_export` — an exported S7 class (NAMESPACE `export()` or `@export`) with no `#'` block immediately above its `new_class`; `prop_type_unresolvable` — a property whose declared class resolves to neither a `class_*` builtin nor a class defined in scanned source | advisory |

!!! note "Legacy family is registration-aware"
    `legacy_s3_generic` is a static heuristic on the **method name** — it does not inspect the body
    for `UseMethod()`. A method *registered* as a real S3 method (roxygen `@exportS3Method` directly
    above it, or NAMESPACE `S3method(generic, class)`) is **exempt** — that's a deliberate
    registration, not a leftover. Comments and string literals are masked before scanning, and the
    legacy checks run only when the package also uses `new_class`.

### `--eco` family: cross-package contracts

`--eco` runs the 5 static families across **every package** in the ecosystem manifest (resolved via
`discovery.detect_ecosystem`, ordered by `manifest_order`), then adds one family the per-package
modes structurally cannot compute — it needs the whole package set to build a class registry. Still
pure-stdlib, name-based, and re-export-aware.

| Family | What it flags | Severity |
|---|---|---|
| **cross-package-contract** | `cross_package_undeclared_contract` — package B has `method(generic, C)` where class `C` is defined in **sibling** package A, but B doesn't declare A in `Imports`/`Depends`/`LinkingTo`; `C` never resolves at B's load, so the method silently never dispatches. `cross_package_unexported_class` — A *is* declared, but no declared provider `export()`s `C`, so B still can't reach it | advisory |

!!! note "Static, conservative, and re-export-aware"
    This family is name-based (it can't use the runtime object-identity that `--runtime` uses), so it
    flags **only** when no declared, exporting provider can exist. If a provider's `NAMESPACE` is
    missing or uses `exportPattern()`, the export set is unknowable and the unexported check is
    **suppressed** — no false positive. A statically-ambiguous name collision (the same class name
    defined in more than one package) is treated conservatively. It's the static, ecosystem-scoped
    sibling of `--runtime`'s `method_undeclared_dependency`, caught *before* anything is installed.

### `--runtime` families: method-dispatch + validator-runtime

`--runtime` adds an R-backed pass routed through `lib.rcmd`'s `s7runtime` engine — it `pkgload::load_all`s
the package and introspects S7 at runtime, catching correctness traps source parsing can't see.
Findings carry `source: "runtime"`.

| Family | What it flags | Severity |
|---|---|---|
| **method-dispatch** | `dead_generic` — an S7 generic with **no registered method** (dispatch can never resolve); `method_on_missing_class` — a method whose dispatch class has **no resolvable namespace binding** (e.g. an inline `new_class()` left in a `method()` call — an unreachable method); `method_undeclared_dependency` — a method dispatching on a resolvable S7 class whose providing package is set, differs from this package, and is **not** in `DESCRIPTION` `Imports`/`Depends`/`LinkingTo` (typically a `Suggests`-only class — at a site without that package the dispatch class never registers) | advisory |
| **validator-runtime** | `validator_not_enforcing` — a validator whose body is a constant no-op, so it accepts a deliberately-invalid property value at runtime (present, but not actually enforcing) | advisory |

!!! tip "Why object identity, not name"
    `method_on_missing_class` resolves classes by **object identity** over the package's classes, not
    by `@name` — so the idiomatic `Foo <- new_class("Bar")` (binding name ≠ `@name`) is correctly
    **not** flagged. For `method_undeclared_dependency`, the package itself plus base/recommended
    packages (`base`, `methods`, `stats`, `utils`, `graphics`, `grDevices`, `datasets`, `tools`,
    `S7`) are always allowed, and `Depends` counts as declared the same as `Imports`. Base types and
    imported classes are excluded.

---

## Flags

From the command's `arguments:` spec:

| Flag | Type | Default | Effect |
|---|---|---|---|
| `package` (positional) | string | cwd | Package directory to review |
| `--kind` | string | `all` | Limit to one static family: `all` \| `naming` \| `validators` \| `methods` \| `legacy` \| `docs` |
| `--eco` | boolean | `false` | Sweep the static families across every package in the ecosystem manifest, aggregated; adds the **cross-package-contract** family. Pure-stdlib; composes with `--runtime` |
| `--runtime` | boolean | `false` | Add the R-backed runtime pass (method-dispatch + validator-runtime) via `lib.rcmd`; degrades to advisory `warn` when R/S7 is unavailable |
| `--format` | string | `json` | Output format: `json` \| `text` |

There is **no** `--write` / `--fix` — S7 fixes need human judgement (like `r:cran-prep`'s advisory tier).

---

## Examples

```bash
# Static review of the current package — pure-Python, no R needed
/rforge:r:s7-review

# Limit to one family, human-readable output
/rforge:r:s7-review --kind validators --format text

# A specific package, JSON for tooling
/rforge:r:s7-review path/to/pkg --format json
```

```bash
# Ecosystem sweep: static families across every package + cross-package contracts
/rforge:r:s7-review --eco

# Same, human-readable
/rforge:r:s7-review --eco --format text
```

```bash
# Runtime pass: load the package and introspect S7 at runtime
/rforge:r:s7-review --runtime

# Compose: sweep the ecosystem statically AND run the runtime pass per package
/rforge:r:s7-review --eco --runtime
```

---

## Behavior notes

!!! note "Advisory only"
    Every finding is `severity: "advisory"`, worded "looks like / consider", never "must". The
    command always exits 0 and never blocks a commit, PR, or release — it mirrors `r:cran-prep`'s
    Tier-4 advisory tone. Static findings carry `source: "static"`; the two `--runtime` families
    carry `source: "runtime"`, so a runtime pass can later promote or clear a static finding without
    breaking the envelope.

!!! warning "`--runtime` needs R + S7, and degrades gracefully"
    `--runtime` requires R plus the `S7` and `pkgload` packages. When they're absent — or the load
    fails — the runtime stages degrade to advisory `warn` ("runtime pass skipped: …"). The static
    result is **always intact** and the command **always exits 0**. The static modes never need R at
    all.

!!! tip "Start static, escalate as needed"
    Run the default static pass first (it's instant and runs anywhere). Reach for `--eco` when you
    maintain a package family and want cross-package contract checks, and `--runtime` when you want
    the correctness traps — dead generics, no-op validators, unreachable methods — that only show up
    once S7 is actually loaded. A package that fails to parse during an `--eco` sweep becomes a
    per-package `warn` and never aborts the sweep.

---

## See also

- [`r:s7-review` in commands](../commands.md) — the terse command-list entry
- [`s7review` reference](../reference/s7review.md) — the `lib.s7review` engine API (`run_all`,
  `run_eco`, `run_all_with_runtime`, `build_class_registry`, `check_cross_package_contracts`, …)
- [S7 convention checking tutorial](../tutorials/s7-convention-checking.md) — the hands-on
  walkthrough this guide complements

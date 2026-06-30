# SPEC: `r:use-data` + `r:use-citation` (scaffolding v2)

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved
**Parent:** `SPEC-r-scaffolding-2026-06-10.md` (the shipped v1 `r:use-*` family)
**Target:** v2.11.0 bundle (feature 3 of 3)

---

## Summary

Two new scaffolders extend the v2.10.0 `r:use-*` family (`r:use-test`/`use-package`/
`use-vignette`). Same contract as v1: **dry-run by default**, `--write` applies, hybrid
engine (usethis-style infra in `lib/usethis_infra.py` + Python/AI content in
`lib/scaffold.py`). Existing-package only (never `r:create`).

| Command | Scaffolds | Source of truth |
|---|---|---|
| `r:use-data` | `data/<name>.rda` placeholder + `R/data.R` roxygen doc stub | a named dataset (user supplies/object) |
| `r:use-citation` | `inst/CITATION` | parsed from `DESCRIPTION` (`Authors@R`, `Title`, year) |

**Command count: 39 → 41.**

## `r:use-data`

- **Args:** `<name>` (dataset/object name, required), `--write` (default dry-run).
- **Dry-run output:** shows the `R/data.R` roxygen block it *would* write + notes the
  `data/<name>.rda` it would expect, and whether `DESCRIPTION` needs `LazyData: true` /
  `Depends: R (>= 2.10)` (reported, applied on `--write` via the shared
  `deps_sync._apply_patch` / `_read_field_specs` writer — which **preserves version
  constraints**, the v2.10.0 fix).
- **`--write`:** appends the roxygen stub to `R/data.R` (creating it if absent; never
  clobbers an existing doc for the same `\name`), and patches `DESCRIPTION` fields.
  Does **not** fabricate the `.rda` (data is the user's); emits the exact
  `usethis::use_data(<name>)` / `save()` command to produce it.
- **Roxygen stub:** `@title`, `@format` (a `\describe{}` skeleton with TODO items),
  `@source` TODO, and the `"<name>"` string at the end (the documented-data idiom).

## `r:use-citation`

- **Args:** `--write` (default dry-run). No positional arg — reads `DESCRIPTION`.
- **Parse** `DESCRIPTION`: `Title`, `Authors@R` (or fallback `Author`), `Version`, and
  the year (from `Date` if present, else a `<YEAR>` TODO — **never** a wall-clock date,
  per the determinism rule).
- **Dry-run:** prints the `inst/CITATION` it would write (a `bibentry(bibtype = "Manual",
  ...)` for the package, with `Authors@R` mapped to `person()` entries).
- **`--write`:** writes `inst/CITATION` (refuses to overwrite an existing one without an
  explicit confirmation flag `--force`); creates `inst/` if absent.
- Degrades: unparseable `Authors@R` → a `# TODO` author block + a warn, never raises.

## Reuse / architecture

- Both land in **`lib/scaffold.py`** (the v1 module) + reuse `lib/usethis_infra.py`.
- `DESCRIPTION` edits go through the **shared constraint-preserving writer**
  (`deps_sync._read_field_specs` + `_apply_patch`) — the same path hardened in v2.10.0.
  No new DESCRIPTION-writing code.
- Pure-stdlib (no R): like the rest of `scaffold`/`deps_sync`.

## Out of scope

- Generating dataset *contents* (`r:use-data` documents + wires; the user owns the data).
- Multi-dataset batch scaffolding.
- BibTeX import for `use-citation` (DESCRIPTION-derived only).

## Tests (gates)

- `r:use-data` dry-run: asserts roxygen stub + DESCRIPTION-delta report, **no files
  written**.
- `r:use-data --write`: asserts `R/data.R` appended, `"<name>"` string present,
  `DESCRIPTION` `LazyData`/`Depends` patched **with any existing version constraints
  preserved** (regression-locks the v2.10.0 fix on the new path).
- `r:use-data --write` collision: existing `\name` doc for the same dataset → no
  duplicate, warn.
- `r:use-citation` dry-run: asserts `bibentry()` rendered from a fixture DESCRIPTION;
  year is a TODO placeholder when `Date` absent (determinism check — no real date).
- `r:use-citation --write` refuses to clobber an existing `inst/CITATION` without
  `--force`.
- Both: pure-stdlib import guard (no R).

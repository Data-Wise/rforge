# PLAN: r:use-data + r:use-citation — v2.11.0 feature 3

> REQUIRED: TDD. Spec: `SPEC-r-scaffolding-v2-2026-06-13.md`.

**Goal:** Two new `r:use-*` scaffolders (dry-run default + `--write`), reusing
`lib/scaffold.py` + `lib/usethis_infra.py` + the constraint-preserving DESCRIPTION writer
(`deps_sync._read_field_specs`/`_apply_patch`). 39 → 41 commands.

**Files:**
- Modify: `lib/scaffold.py` (`scaffold_data`, `scaffold_citation`)
- Create: `commands/r/use-data.md`, `commands/r/use-citation.md`
- Test: `tests/test_scaffold.py`, `tests/test-all.sh` (command count 39→41, uniqueness)

### Task 1: `r:use-data` dry-run (roxygen + DESCRIPTION delta)
- [ ] Write failing test: `scaffold_data(name="mydat", path=fixture, write=False)` returns
      the `R/data.R` roxygen block + the DESCRIPTION delta (`LazyData`/`Depends`) it would
      apply; asserts **no files written**.
- [ ] Implement `scaffold_data(name, path=".", write=False)`: build roxygen stub
      (`@title`/`@format \describe{}`/`@source` TODOs + trailing `"<name>"`); compute
      DESCRIPTION needs; return dry-run envelope.
- [ ] Run test → pass. Commit.

### Task 2: `r:use-data --write` (+ constraint preservation, collision guard)
- [ ] Write failing test: `--write` appends to `R/data.R`, `"<name>"` present; DESCRIPTION
      `LazyData`/`Depends` patched **with existing version constraints preserved**
      (regression-lock v2.10.0 fix); existing `\name` doc → no duplicate + warn.
- [ ] Implement `--write`: append stub (create `R/data.R` if absent, skip on collision);
      patch DESCRIPTION via `deps_sync._read_field_specs` + `_apply_patch`; emit
      `use_data(<name>)` reminder (never fabricates `.rda`).
- [ ] Run test → pass. Commit.

### Task 3: `r:use-citation` dry-run + write
- [ ] Write failing test: `scaffold_citation(path=fixture, write=False)` renders a
      `bibentry(bibtype="Manual", ...)` from fixture DESCRIPTION; year is a `<YEAR>` TODO
      when `Date` absent (determinism — **no wall-clock date**); `--write` writes
      `inst/CITATION`, refuses to clobber existing without `--force`.
- [ ] Implement `scaffold_citation(path=".", write=False, force=False)`: parse
      `Title`/`Authors@R`/`Version`/year; map `Authors@R` → `person()`; render bibentry;
      dry-run vs write-with-clobber-guard. Unparseable authors → `# TODO` + warn.
- [ ] Run test → pass. Commit.

### Task 4: Command files + count bump + docs
- [ ] Create `commands/r/use-data.md` + `commands/r/use-citation.md` with full frontmatter
      (`name`/`description`/`argument-hint`/`arguments:`) matching the `r:use-*` v1 style.
- [ ] Update command count 39→41: `mkdocs.yml extra.rforge.command_count` then run
      `python3 scripts/version_sync.py` (propagates count); update `docs/commands.md`
      (R Authoring subtotal + 2 entries) + REFCARD; `CHANGELOG.md` [Unreleased].
- [ ] `bash tests/test-all.sh` (count + uniqueness gates) + `pytest` → green. Commit.

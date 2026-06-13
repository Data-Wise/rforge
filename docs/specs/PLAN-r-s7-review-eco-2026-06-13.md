# PLAN: r:s7-review --eco + --runtime — v2.11.0 feature 2

> REQUIRED: TDD. Spec: `SPEC-r-s7-review-eco-2026-06-13.md`.

**Goal:** Add `--eco` (pure-stdlib ecosystem static sweep) and `--runtime` (R-backed
runtime pass via a new `lib.rcmd` `s7runtime` engine) to `r:s7-review`. No new command.

**Files:**
- Modify: `lib/s7review.py` (`--eco` sweep, `--runtime` orchestration + merge)
- Modify: `lib/rcmd.py` (new `s7runtime` engine; add to `SAFE_AUTORUN`)
- Modify: `commands/r/s7-review.md` (frontmatter `--eco`/`--runtime`)
- Test: `tests/test_s7review.py`, `tests/test_rcmd.py` (opt-in e2e), `tests/test-all.sh`

### Task 1: `--eco` ecosystem static sweep (pure-stdlib)
- [ ] Write failing test: 2-package fixture ecosystem (+ manifest with `manifest_order`);
      `run_eco(root)` returns a per-package breakdown + roll-up, ordered by
      `manifest_order`; a parse-failure package becomes a per-package warn (sweep
      continues).
- [ ] Implement `run_eco(root=".")`: `discovery.find_r_packages(root)` → `run_all` per
      package → aggregate envelope (per-package + totals-by-family). Order by
      `manifest_order` when present.
- [ ] Run test → pass. Commit.

### Task 2: `s7runtime` engine in lib/rcmd.py
- [ ] Write failing test (opt-in real-R, skip when R absent): fixture package with (a) a
      dead S7 generic and (b) a non-enforcing validator; `rcmd.run(kind="s7runtime",
      path=...)` returns a normalized envelope whose JSON lists both issues.
- [ ] Implement: embedded Rscript program — load pkg (`pkgload::load_all`), enumerate S7
      classes/generics/methods, test dispatch resolution + instantiate-with-invalid →
      emit `jsonlite` JSON (auto_unbox guarded, no stdout contamination). Normalize to
      the standard rcmd envelope. Add `"s7runtime"` to `SAFE_AUTORUN`.
- [ ] Run test → pass (or skip cleanly w/o R). Commit.

### Task 3: `--runtime` orchestration + merge in s7review
- [ ] Write failing test: `--runtime` merges static families + the 2 runtime families
      (`method-dispatch`, `validator-runtime`) into one envelope; with R unavailable it
      degrades to a warn ("runtime pass skipped"), static result intact, exit 0.
- [ ] Implement: when `--runtime`, call `rcmd.run(kind="s7runtime")`, map its JSON to the
      two families, merge with static `run_all`. Compose with `--eco` (sweep + per-pkg
      runtime). Never raise.
- [ ] Run test → pass. Commit.

### Task 4: Frontmatter + guards + docs
- [ ] Add `--eco`, `--runtime` to `commands/r/s7-review.md` `arguments:` + `## Usage`.
- [ ] Confirm `tests/_check_agent_engines.py` passes with `s7runtime` in SAFE_AUTORUN;
      add a pure-stdlib import guard for `s7review.py` (no R, all R via rcmd).
- [ ] Regenerate `docs/reference/{s7review,rcmd}.md` via `scripts/gen_lib_reference.py`;
      update `CHANGELOG.md` [Unreleased] + `docs/reference/s7review.md` notes.
- [ ] `bash tests/test-all.sh` + `python3 -m pytest tests/` → green. Commit.

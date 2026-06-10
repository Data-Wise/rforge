# ORCHESTRATE: CRAN-incoming hardening (v2.3.0)

> Working artifact for the `feature/cran-incoming` worktree. Delete on merge to `dev`.
> **Authoritative spec:** [`docs/specs/SPEC-cran-incoming-hardening-2026-06-10.md`](docs/specs/SPEC-cran-incoming-hardening-2026-06-10.md)
> (Status: Reviewed/approved) — read it first; this file is the execution checklist, the spec is the *why*.
> **Companion research (cited):** `docs/specs/RESEARCH-cran-incoming-checks-2026-06-10.md`.

- **Branch:** `feature/cran-incoming` (off `dev` @ b335340)
- **Target:** v2.3.0 (minor — carries a behavior change)
- **Start:** a **fresh session in this worktree** (`cd` here, then `claude`). Do not implement from the main-repo session.

---

## Phase 0 — Decisions to lock before any code (spec Open Questions)

- [ ] **Tier 4 module placement** — new `lib/cranlint.py` (pure-stdlib analysis module, like
  `discovery`/`deps`/`status`) **vs** fold the functions into an existing module. Decides whether
  a `docs/reference/cranlint.md` page is generated and registered in `scripts/gen_lib_reference.py`.
- [ ] **`docs:check` reuse (Tier 4c)** — confirm `docs:check` exposes a reusable, importable entry
  point for the staleness/dangling-ref logic. If it's prompt-only, **extract the core into `lib/` first**.

## Phase 1 — Strict check passes (`lib/rcmd.py`)

- [ ] **1.1 `r_snippet(kind="check", …)`** — add an internal `flavor ∈ {None,"depends","suggests"}`
  + `incoming: bool`. Build `args` (`--as-cran` [+ `--run-donttest` when strict]) and an `env=`
  named vector, threaded into the existing `rcmdcheck(...)` call inside `_guard("rcmdcheck", …)`.
  Mechanism per RESEARCH §A.4: `rcmdcheck(args=, env=c("_R_CHECK_DEPENDS_ONLY_"="true"))`. **No `_invoke_r` change.**
- [ ] **1.2 `run("check", …)`** — pass flavor/incoming through. `--strict` drives a **loop over both
  flavors** (depends → suggests), each its own stage row. No per-flavor CLI flag.
- [ ] **1.3 `_run_cran_prep()`** — after the existing `check` (rcmd.py:462) + real-NOTE blocker,
  run the two strict flavors by default; on `error` append blocker
  `"noSuggests/donttest check failed (Suggests used unconditionally?)"`. Thread `ns.strict`/`ns.incoming`
  into `_run_cran_prep(...)` (the missing link at rcmd.py:530–535).
- [ ] **1.4 Failure hint** — *"A Suggests package is used unconditionally. Move it to Imports, or guard
  with `requireNamespace()` in code AND `skip_if_not_installed()` in tests."*
- [ ] **1.5 Manual build (Tier 1b)** — verify the PDF manual builds; `warn` (not skip) if no LaTeX.

## Phase 2 — Opt-in incoming bundle (`--incoming`, Tier 3)

- [ ] **2.1** Add the incoming-only `_R_CHECK_*` bundle — **confirm each variable against R Internals
  §8 first** (RESEARCH §A.2); exclude vars already implied by `--as-cran` (e.g. `_R_CHECK_RD_VALIDATE_RD2HTML_`).

## Phase 3 — Metadata + hygiene (pure-Python, Tier 4)

- [ ] **3.1 `lint_description(path)`** — DCF parse (stdlib); advisory rows for non-`Authors@R`/no `cph`,
  weak/echoed `Title`, `Description` not a complete sentence, stale `Date` (RESEARCH §A.5).
- [ ] **3.2 `check_build_hygiene(path)`** — list top-level entries; compile `.Rbuildignore` as
  case-insensitive regexes; flag planning/dev docs that match neither, each with the `.Rbuildignore`
  regex to add (RESEARCH §A.6). Report-only — no auto-fix.
- [ ] **3.3 Tier 4c** — wire `docs:check` consistency logic in as an advisory stage (per Phase 0 decision).
- [ ] **3.4** All Tier 4 stages are `warn`-level / never block `ready` directly; degrade missing
  DESCRIPTION/.Rbuildignore to `warn`, never an exception.

## Phase 4 — Tests (both gates must pass)

- [ ] `python3 -m pytest tests/` — snippet generation (right `args`/`env=` per flavor); `cran-prep`
  blocks on a mocked strict `error`; clean pkg still `ready`; DESCRIPTION-lint + build-hygiene fixtures;
  Tier 4 never hard-fails.
- [ ] **Regression fixture (the proof)** — medfit 0.2.1 *before* MASS fix → `check (noSuggests)` FAILS;
  *after* → PASS; broken `\donttest{}` example caught by `--run-donttest`.
- [ ] `bash tests/test-all.sh` — keep all checks green; regen `docs/reference/*.md` via
  `scripts/gen_lib_reference.py` if the public surface changed.

## Phase 5 — Docs sweep (spec "Documentation impact")

- [ ] **Frontmatter:** `commands/r/check.md` (+`--strict`/`--incoming`), `commands/r/cran-prep.md` (stages).
- [ ] **Help / hub:** `docs/commands.md` (hub), `docs/REFCARD.md` (CRAN SUBMISSION box + ASCII width),
  `docs/index.md` + `docs/README.md` (hub landings), root `README.md` tree diagrams, `docs/quickstart.md`,
  `docs/lib-modules.md` (+ new `docs/reference/cranlint.md`), `docs/tutorials/cran-release-prep.md`.
- [ ] **Trackers:** `CHANGELOG.md` (`[Unreleased]` — flag the behavior change), `.STATUS`.
- [ ] **Version sync → v2.3.0:** `plugin.json`, `marketplace.json` (×2), `package.json`, + live-version
  doc refs (REFCARD/README/index headers). `tests/test-all.sh` "All 4 version sources agree" must pass.

## Done criteria

- [ ] Both gates green; medfit regression fixture proves the noSuggests catch.
- [ ] Full doc sweep complete; version sync at v2.3.0.
- [ ] Ready to integrate to `dev` (PR) — and delete this ORCHESTRATE file as part of the merge.

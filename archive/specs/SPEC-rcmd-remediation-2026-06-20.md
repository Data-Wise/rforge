# SPEC: `lib/rcmd.py` review remediation (P1–P4)

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-20
- **Target version:** v2.15.0 (minor — security hardening + behavior-preserving refactor; **no command-surface change**, 41 commands unchanged)
- **Branch plan:** `feature/rcmd-remediation` off `dev`
- **Origin:** code review of `lib/rcmd.py` (v2.14.0, 1331 lines). One bundled spec, sequenced tasks; safe additive changes first, behavior-preserving refactors last.

## Summary

Address the four findings from the `lib/rcmd.py` review, in risk order:

| # | Finding | Type | Risk |
|---|---------|------|------|
| **P1** | `--platforms` interpolated into R without validation → R-code injection / brittle snippet | Security | low (additive) |
| **P3** | No timeout on the *quick* `Rscript` calls (`_r_version_key`, rhub dispatch) | Robustness | low (additive) |
| **P2** | `s7runtime` embeds a ~110-line R program as a Python f-string (no R syntax check, brittle escaping) | Maintainability | medium (behavior-preserving) |
| **P4** | `rcmd.py` is 1331 lines spanning snippets + rhub + orchestration | Architecture | medium (behavior-preserving) |

Sequenced so each intermediate commit is shippable: **P1 → P3 → P2 → P4.**

## Non-goals

- No new commands, flags, or envelope-key changes. The `python3 -m lib.rcmd --kind …` public CLI is **unchanged** (a hard invariant the refactors must preserve).
- No behavior change to any `r:` command output (P2/P4 are pure refactors; live-R output must be byte-identical).

---

## P1 — Validate `--platforms` (security)

**Problem.** `main():1319` parses `--platforms` as free text (no `choices=`); `_run_rhub` uses the list as-is (`_rhub_preflight` only rejects *known-broken* platforms); `r_snippet` rhub builds `c("…")` by raw f-string interpolation (line ~670). A token with a `"` escapes the R literal → arbitrary R runs under `Rscript`. Self-injection (local), but a real vector and a brittle-failure source.

**Design.**
- Add an authoritative allow-list constant (in the rhub module after P4, or `rcmd.py` before it):

  ```python
  # R-hub v2 platform tokens (rhub::rhub_platforms()). Single source of truth for
  # --platforms / presets. Keep in sync with _RHUB_PRESETS values.
  ALLOWED_RHUB_PLATFORMS = frozenset({
      "linux", "windows", "macos", "macos-arm64", "atlas",
      "clang-asan", "gcc-asan", "valgrind", "ubuntu-clang", "ubuntu-gcc",
      "ubuntu-next", "ubuntu-release", "nosuggests", "donttest",
  })  # VERIFY the exact set against installed rhub at build time (Task: live).
  ```
- In `_run_rhub`, after resolving `platforms` (preset/explicit/default), **validate every token**; on any unknown token return an error envelope (mirror the existing `--preset` validation at `_run_rhub:827`):

  ```python
  bad = [p for p in platforms if p not in ALLOWED_RHUB_PLATFORMS]
  if bad:
      return {"kind": "rhub", "status": "error", "engine_missing": [],
              "messages": [f"Unknown platform(s): {', '.join(bad)}. "
                           f"Valid: {', '.join(sorted(ALLOWED_RHUB_PLATFORMS))}"]}
  ```
- Defense-in-depth: this makes the f-string interpolation safe (every token is now a known dquote-free literal). No quote-escaping hack needed, but a one-line assertion that tokens are quote-free is a cheap belt-and-suspenders.

**Tests (R-free):** `--platforms 'x"); cat(1); ("'` → error envelope (rejected, no R run); unknown token `foo` → error; valid `linux,windows` → passes to dispatch; preset path still validated.

**Risk:** none — additive guard, rejects only previously-injectable/typo input.

---

## P3 — Timeouts on the quick `Rscript` calls (robustness)

**Problem.** `_invoke_r:803` and `_r_version_key:496` call `subprocess.run` with **no timeout**. A hung `Rscript` (interactive prompt, network stall) blocks forever. A blanket timeout is wrong — `check`/`test`/`coverage`/`revdep` legitimately run for minutes.

**Design.**
- Add an optional `timeout: float | None = None` param to `_invoke_r`; default `None` preserves the unbounded behavior for the long kinds.
- On `subprocess.TimeoutExpired`, return a typed envelope: `('{"timed_out":true}', 124)` (124 = conventional timeout exit), and have `normalize`/`run` surface `status:"error"` + a "timed out after Ns" message.
- Apply a bounded timeout only to the **quick / dispatch** paths: `_r_version_key` (~15s), and the rhub dispatch call in `_run_rhub` (~120s — it dispatches a GH Actions run, shouldn't block long). Long kinds keep `timeout=None`.

**Tests (R-free):** monkeypatch `subprocess.run` to raise `TimeoutExpired` → `_invoke_r(timeout=…)` returns the timeout tuple; `run("rhub")`/version-key path yields `status:"error"` with the timeout message; default long-kind call unaffected (timeout stays `None`).

**Risk:** low — only adds an upper bound where work is expected to be quick.

---

## P2 — Extract `s7runtime`'s embedded R into a shipped `.R` script (maintainability)

**Problem.** `r_snippet`'s `s7runtime` branch (685–794) is a ~110-line R program built by Python string interpolation — no R syntax checking, no highlighting, brittle `{}`/quote escaping (cf. the `fixed=TRUE` split workaround at 743).

**Design.**
- Create `lib/r/s7runtime.R` containing the R logic as a **function** `s7_runtime_report(pkg_path)` returning the result list (`dead_generics`, `methods_on_missing_class`, `methods_undeclared_dependency`, `nonenforcing_validators`). Move the verbatim logic out of the f-string into real R.
- `r_snippet("s7runtime", path)` shrinks to: `_guard(...)` + source the shipped script + call + `cat(jsonlite::toJSON(...))`:

  ```python
  script = json.dumps(str(Path(__file__).parent / "r" / "s7runtime.R"))
  return _guard("S7",
      '... pkgload presence check ...; '
      f'source({script}); '
      f'res <- tryCatch(s7_runtime_report({json.dumps(path)}), '
      'error=function(e) list(messages=paste("s7runtime failed:", conditionMessage(e)))); '
      'cat(jsonlite::toJSON(res, auto_unbox=TRUE, null="list"))')
  ```
  The `_guard`/`tryCatch`/`auto_unbox`/`null="list"` serialization discipline is preserved exactly.
- **Packaging:** ensure `lib/r/*.R` ships in the Homebrew libexec. The tap formula copies `lib/`; confirm the `r/` subdir is included (the generator's `libexec` copy map). Add a `test-all.sh` check that `lib/r/s7runtime.R` exists and `Rscript -e 'parse(...)'`-validates (syntax-only, skip if R absent).

**Tests:**
- R-free: the `s7runtime` snippet now references the `.R` path (string assert); `_guard` + tryCatch still present.
- **Live (MANDATORY, behavior-identical):** run `--kind s7runtime` against a real S7 fixture package BEFORE and AFTER extraction; the emitted JSON must be **byte-identical**. (This is the v2.1.0 lesson — string tests can't prove R behavior.) Reuse/extend the s7review test fixtures.

**Risk:** medium — re-deriving the R must not change behavior. The before/after live diff is the gate. Packaging (shipping the `.R`) is the second risk; the existence test + a `brew`-install smoke catch it.

---

## P4 — Split `rcmd.py` into focused modules (architecture)

**Problem.** 1331 lines doing envelope-normalization + 19-kind snippet generation + rhub preflight/dispatch + orchestration. Hard to hold in context; each concern is independently testable.

**Design (behavior-preserving extraction — public CLI unchanged).**
- **`lib/rsnippets.py`** (new, internal): `r_snippet` + the per-kind builders + CRAN env constants (`_CHECK_ENV`, `_INCOMING_ENV`, `_CRAN_CHECKS_REGISTRY`, `_r_named_char`, `_WIN_FN`, `_r_version_key`, `_guard`). After P2, the s7runtime branch is already thin.
- **`lib/rhub.py`** (new, internal): `_RHUB_PRESETS`, `_RHUB_BROKEN_PLATFORMS`, `ALLOWED_RHUB_PLATFORMS` (from P1), `_check_rhub_yaml`, `_rhub_preflight`, `_rhub_actions_url`, `_run_rhub`.
- **`lib/rcmd.py`** (keeps the envelope core + entry point): `find_package`, `_as_list`, `_parse_json`, `_classify_notes`, `_status_for`, `normalize`, `console_fallback`, `_invoke_r`, `_install_package`, `run`, `_extract_findings`, `run_changed` (or confirm it already delegates to `lib/changed.py`), `_run_cycle`, `render_cran_comments`, `_run_cran_prep`, `main`.
- **Import graph (no cycles):** `rcmd` → imports `rsnippets`, `rhub`; `rhub` → imports `rsnippets` (for `r_snippet`) + `rcmd`'s pure helpers (move shared helpers like `_parse_json`/`console_fallback`/`normalize` references via function args or a tiny `_core` if needed to avoid `rhub`→`rcmd` back-edge). Prefer: `rhub._run_rhub` receives `r_snippet`/`normalize`/`_parse_json` by import from `rsnippets`/`rcmd` carefully; if a cycle appears, hoist the 3 shared pure helpers into `rcmd` and import one-way `rhub`→`rcmd` is fine as long as `rcmd` does NOT import `rhub` at module top (lazy import inside `run` for `kind=="rhub"`). **Document the chosen direction in the PR.**
- **`lib/` reference docs:** `rcmd` stays the public module (keeps its `docs/reference/rcmd.md`); `rsnippets`/`rhub` are **internal** (like `formatters`) — no reference page. Confirm `scripts/gen_lib_reference.py --check` still passes (its MODULES list should NOT add the internals).
- **`CLAUDE.md`** `lib/` section: list `rsnippets`/`rhub` as internal modules + the `lib/r/*.R` script convention from P2.

**Tests:** the full existing sweep is the gate — `pytest` (463+) and `test-all.sh` (43/43) must stay green; `python3 -m lib.rcmd --kind …` behaves identically; `gen_lib_reference.py --check` green; `mkdocs build --strict` clean. No new tests required beyond import-smoke, but any test importing moved private helpers (`from lib.rcmd import _rhub_preflight`) must be repointed.

**Risk:** medium — mechanical but wide. Mitigated by: public CLI invariant, the green-gate requirement, and doing it LAST (after P1–P3 are committed) so a stall doesn't block the security fix.

---

## Dedup / boundary check

No overlap with existing modules: `rsnippets`/`rhub` are *extractions from* `rcmd.py`, not new behavior. `run_changed` already has a sibling `lib/changed.py` (662 lines) — confirm whether `rcmd.run_changed` delegates to it; if so, leave as-is (out of scope). Do not touch `s7review.py`/`scaffold.py`/`cranlint.py`.

## Testing summary (gates)

- R-free CI throughout (mock `Rscript`). New: P1 injection-rejection, P3 timeout, P2 snippet-references-script.
- **Two mandatory live-R checks before PR:** (1) P2 s7runtime byte-identical before/after; (2) a real `r:rhub --platforms linux,windows` smoke to confirm P1 validation + dispatch still work.
- `pytest` + `test-all.sh` green after every task; `gen_lib_reference --check` + `mkdocs --strict` green after P4.

## Documentation impact

- `CLAUDE.md` `lib/` conventions: new internal modules + `lib/r/*.R` script convention.
- `CHANGELOG.md` `[Unreleased]` → `## [2.15.0]` (Security: `--platforms` validation; Internal: s7runtime extraction + rcmd split; Robustness: timeouts).
- 4-source version bump → 2.15.0 + live-version doc refs; tap manifest + `Formula/rforge.rb` regen on release (desc count unchanged at 41).
- No command-doc/count changes (no surface change). Optional one-line note in `commands/r/rhub.md` that invalid `--platforms` now errors clearly.

## Implementation order (for the plan)

1. **P1** — `ALLOWED_RHUB_PLATFORMS` + `_run_rhub` validation + tests. Commit.
2. **P3** — `_invoke_r(timeout=)` + timeout envelope + apply to quick paths + tests. Commit.
3. **P2** — extract `lib/r/s7runtime.R`; thin the snippet; packaging check; **live byte-identical verify**. Commit.
4. **P4** — extract `lib/rsnippets.py` + `lib/rhub.py`; rewire imports (no cycles); repoint tests; green sweep + gen-ref + mkdocs. Commit.
5. Docs + CHANGELOG + version bump (2.15.0) + `.STATUS`. Commit.
6. Both gates + 2 live checks; PR `feature/rcmd-remediation` → `dev`.

## Open questions / risks

- **P1 allow-list exactness:** the precise R-hub v2 platform token set should be confirmed against installed `rhub::rhub_platforms()` (build-time verify); start from `_RHUB_PRESETS` ∪ known tokens, widen if a legitimate platform is rejected.
- **P4 import direction:** pick one acyclic direction (lazy `import rhub` inside `run` is the safe default) and document it.
- **P2 packaging:** verify `lib/r/` ships in libexec via the tap generator before relying on it at runtime.

# lib/rcmd.py Review Remediation Implementation Plan (P1–P4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden and de-clutter `lib/rcmd.py` — validate `--platforms` (close an R-injection vector), add timeouts to quick `Rscript` calls, extract the embedded `s7runtime` R program to a shipped `.R` file, and split the 1331-line module into `rsnippets`/`rhub` — all behavior-preserving.

**Architecture:** Sequenced safe→risky (P1 → P3 → P2 → P4) so every commit is shippable. P1/P3 are additive; P2/P4 are behavior-preserving refactors gated by live byte-identical R output + the full green test sweep. The `python3 -m lib.rcmd` CLI and every envelope key stay **identical**.

**Tech Stack:** Python 3 stdlib (`argparse`/`json`/`subprocess`/`re`/`pathlib`); R via `Rscript`; pytest with `Rscript`/`subprocess` mocked (R-free CI).

**Spec:** `docs/specs/SPEC-rcmd-remediation-2026-06-20.md`

## Global Constraints

- **No command-surface change** — 41 commands, no new flags/kinds/envelope keys. Target **v2.15.0** (minor).
- **Public CLI invariant** — `python3 -m lib.rcmd --kind <kind> …` output must be byte-identical before/after P2 and P4.
- **R-free CI** — all pytest mocks `Rscript`/`subprocess`; never requires a real R in unit tests.
- **lib package convention** — run as `python3 -m lib.<module>`; new modules `rsnippets`/`rhub` are **internal** (no `docs/reference/` page, like `formatters`).
- **Both gates green before PR:** `python3 -m pytest tests/` (463+) and `bash tests/test-all.sh` (43/43).
- **Two mandatory live-R checks before PR** (Task 6): P2 s7runtime byte-identical; P1 `r:rhub` smoke.
- Conventional commits + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Don't touch the rename stubs.

---

## Pre-flight (read first)

- You are in `~/.git-worktrees/rforge/feature-rcmd-remediation` on `feature/rcmd-remediation`. Verify: `git branch --show-current`.
- **Read `lib/rcmd.py` end-to-end first.** Key anchors (v2.14.0 line numbers, will drift as you edit): `_RHUB_PRESETS` ~350, `_check_rhub_yaml` ~358, `_rhub_preflight` ~428, `_r_version_key` ~491, `r_snippet` 506–795 (s7runtime branch 675–794), `_invoke_r` ~798, `_run_rhub` ~817, `run` ~872, `main` ~1252.
- Existing tests live in `tests/test_rcmd.py` (+ others). Find the rhub tests before editing.

---

## Task 1 (P1): Validate `--platforms` against an allow-list

**Files:**
- Modify: `lib/rcmd.py` (add `ALLOWED_RHUB_PLATFORMS`; guard in `_run_rhub`)
- Test: `tests/test_rcmd.py`

**Interfaces:**
- Produces: `ALLOWED_RHUB_PLATFORMS: frozenset[str]` (module-level). `_run_rhub` returns an error envelope `{"kind":"rhub","status":"error","engine_missing":[],"messages":[...]}` for any unknown/injection token.

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_rcmd.py
def test_run_rhub_rejects_injection_platform(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    # _invoke_r must NOT be reached — validation happens first.
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("R ran!")))
    env = rcmd._run_rhub(str(tmp_path), {"package": "foo", "version": "1.0"},
                         platforms=['x"); cat(1); ("'])
    assert env["status"] == "error"
    assert "Unknown platform" in " ".join(env["messages"])

def test_run_rhub_rejects_unknown_platform(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("R ran!")))
    env = rcmd._run_rhub(str(tmp_path), {"package": "foo"}, platforms=["linux", "nope"])
    assert env["status"] == "error" and "nope" in " ".join(env["messages"])

def test_allowed_platforms_covers_presets():
    # every token in every preset must be in the allow-list (internal consistency)
    for plats in rcmd._RHUB_PRESETS.values():
        for p in plats:
            assert p in rcmd.ALLOWED_RHUB_PLATFORMS
```

- [ ] **Step 2: Run → FAIL** (`python3 -m pytest tests/test_rcmd.py -k "rhub_rejects or allowed_platforms" -v`)

- [ ] **Step 3: Implement.** Add after `_RHUB_PRESETS` (~line 355):

```python
# Authoritative R-hub v2 platform tokens (superset of _RHUB_PRESETS values).
# VERIFY the exact set against installed `rhub::rhub_platforms()` in Task 6;
# widen here if a legitimate platform is rejected.
ALLOWED_RHUB_PLATFORMS = frozenset({
    "linux", "windows", "macos", "macos-arm64", "atlas",
    "clang-asan", "gcc-asan", "valgrind",
    "ubuntu-clang", "ubuntu-gcc", "ubuntu-next", "ubuntu-release",
    "nosuggests", "donttest",
})
```

In `_run_rhub`, immediately AFTER the preset/explicit/default resolution block (right before `# Pre-flight gate`), add:

```python
    bad = [p for p in platforms if p not in ALLOWED_RHUB_PLATFORMS]
    if bad:
        return {"kind": "rhub", "status": "error", "engine_missing": [],
                "messages": [f"Unknown platform(s): {', '.join(bad)}. "
                             f"Valid: {', '.join(sorted(ALLOWED_RHUB_PLATFORMS))}"]}
```

- [ ] **Step 4: Run → PASS** (`-k "rhub_rejects or allowed_platforms"`).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "fix(rcmd): validate --platforms against allow-list (closes R-injection)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2 (P3): Timeouts on the quick `Rscript` calls

**Files:**
- Modify: `lib/rcmd.py` (`_invoke_r` gains `timeout`; apply to `_r_version_key` + rhub dispatch; surface timeout in `run`)
- Test: `tests/test_rcmd.py`

**Interfaces:**
- Produces: `_invoke_r(snippet: str, *, timeout: float | None = None) -> tuple[str, int]`. On `subprocess.TimeoutExpired` returns `('{"timed_out": true}', 124)`. `run()`/`_run_rhub` map exit 124 / `timed_out` → `status:"error"` + a "timed out" message.

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_rcmd.py
import subprocess as _sp

def test_invoke_r_timeout_returns_124(monkeypatch):
    def boom(*a, **k):
        raise _sp.TimeoutExpired(cmd="Rscript", timeout=k.get("timeout", 1))
    monkeypatch.setattr(rcmd.shutil, "which", lambda x: "/usr/bin/Rscript")
    monkeypatch.setattr(rcmd.subprocess, "run", boom)
    out, code = rcmd._invoke_r("1+1", timeout=1)
    assert code == 124 and '"timed_out"' in out

def test_run_surfaces_timeout_as_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda *a, **k: ('{"timed_out": true}', 124))
    env = rcmd.run("check", str(tmp_path))
    assert env["status"] == "error"
    assert any("timed out" in m.lower() for m in env["messages"])
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.** Replace `_invoke_r`:

```python
def _invoke_r(snippet: str, *, timeout: float | None = None) -> tuple[str, int]:
    """Run an R snippet via Rscript; return (stdout, exit_code). Mocked in tests.

    timeout=None (default) keeps the unbounded behavior the long kinds
    (check/test/coverage/revdep) need; quick/dispatch callers pass a bound.
    """
    rscript = shutil.which("Rscript")
    if rscript is None:
        return ('{"engine_missing":["R"]}', 127)
    try:
        proc = subprocess.run([rscript, "-e", snippet],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ('{"timed_out": true}', 124)
    return (proc.stdout.strip(), proc.returncode)
```

In `run()` and `_run_rhub`, after computing `(stdout/raw, code)`, surface the timeout. Add to `run()` right before `env = normalize(...)` (and the same two lines in `_run_rhub` before its `normalize`):

```python
        if code == 124 or raw.get("timed_out"):
            raw = {"messages": ["Rscript timed out — the operation took too long "
                                "(quick path bounded; long kinds are unbounded)."]}
```

Then ensure `normalize` yields `status:"error"` for `code==124` (it already does — any non-zero code → error for non-check kinds; for `check`, add `if exit_code == 124: return "error"` at the top of the `check` branch in `_status_for`). Apply bounded timeouts:
- `_r_version_key`: `subprocess.run([...], ..., timeout=15)` wrapped in `try/except TimeoutExpired: return "base"`.
- rhub dispatch in `_run_rhub`: `_invoke_r(snippet, timeout=120)`.

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "fix(rcmd): bound the quick Rscript calls with timeouts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3 (P2): Extract `s7runtime` R into a shipped `lib/r/s7runtime.R`

**Files:**
- Create: `lib/r/s7runtime.R`
- Modify: `lib/rcmd.py` (`r_snippet` s7runtime branch → source the file), `tests/test-all.sh` (existence + syntax check)
- Test: `tests/test_rcmd.py`

**Interfaces:**
- Produces: `lib/r/s7runtime.R` defining `s7_runtime_report(pkg_path)` returning a list with keys `dead_generics`, `methods_on_missing_class`, `methods_undeclared_dependency`, `nonenforcing_validators`. `r_snippet("s7runtime", path)` returns a `_guard`-wrapped snippet that `source()`s the script, calls the function inside `tryCatch`, and `cat`s `jsonlite::toJSON(...)`.

- [ ] **Step 1: Create `lib/r/s7runtime.R`.** Move the R logic VERBATIM from the current `r_snippet` s7runtime branch (`lib/rcmd.py` ~688–790, the body inside the outer `tryCatch({ ... })`) into a real R function. De-f-string it (real R, not Python-escaped). Skeleton:

```r
# lib/r/s7runtime.R — S7 runtime introspection for r:s7-review --runtime.
# Sourced by lib/rcmd.py (kind="s7runtime"); returns a list serialized to JSON
# by the caller. Keep the four return keys stable.

s7_runtime_report <- function(pkg_path) {
  suppressMessages(pkgload::load_all(pkg_path, quiet = TRUE,
                                     helpers = FALSE, export_all = FALSE))
  nm <- pkgload::pkg_name(pkg_path)
  ns <- asNamespace(nm)
  objs <- mget(ls(ns, all.names = TRUE), envir = ns, ifnotfound = list(NULL))
  is_gen <- function(o) inherits(o, "S7_generic")
  is_cls <- function(o) inherits(o, "S7_class")
  gens <- Filter(is_gen, objs); clss <- Filter(is_cls, objs)
  # (1) dead generics  — count_methods() recursion  [MOVE verbatim from rcmd.py]
  # (2) non-enforcing validators — is_noop()         [MOVE verbatim]
  # (3) declared deps read-once + allow set          [MOVE verbatim]
  # (4) methods on missing/undeclared class           [MOVE verbatim]
  list(dead_generics = dead,
       methods_on_missing_class = missing,
       methods_undeclared_dependency = undeclared,
       nonenforcing_validators = lax)
}
```

> Copy the existing logic exactly — comments and all. The ONLY change is
> Python-f-string → plain R (drop the `f'...'` quoting; `{` stays a single `{`).

- [ ] **Step 2: Thin the snippet.** Replace the `if kind == "s7runtime":` branch in `r_snippet` with:

```python
    if kind == "s7runtime":
        script = json.dumps(str(Path(__file__).parent / "r" / "s7runtime.R"))
        return _guard("S7",
            'if (!requireNamespace("pkgload", quietly=TRUE)) {'
            'cat(\'{"engine_missing":["pkgload"]}\'); quit(status=0)}; '
            f'source({script}); '
            f'res <- tryCatch(s7_runtime_report({json.dumps(path)}), '
            'error=function(e) list(messages=paste('
            '"s7runtime load/introspection failed:", conditionMessage(e)))); '
            'cat(jsonlite::toJSON(res, auto_unbox=TRUE, null="list"))')
```

- [ ] **Step 3: R-free test** (snippet references the script + guard intact):

```python
# append to tests/test_rcmd.py
def test_s7runtime_snippet_sources_script():
    src = rcmd.r_snippet("s7runtime", "/tmp/foo")
    assert "s7runtime.R" in src and "s7_runtime_report" in src
    assert 'requireNamespace("S7"' in src and "tryCatch" in src
```

- [ ] **Step 4: Packaging check in `tests/test-all.sh`** — add a check that the script exists and parses (syntax-only, R-optional):

```bash
# Lib: s7runtime.R ships + parses
if [ -f lib/r/s7runtime.R ]; then
  if command -v Rscript >/dev/null 2>&1; then
    Rscript -e 'invisible(parse("lib/r/s7runtime.R"))' >/dev/null 2>&1 \
      && pass "Lib: s7runtime.R parses" || fail "Lib: s7runtime.R parse error"
  else
    pass "Lib: s7runtime.R present (R absent — skip parse)"
  fi
else
  fail "Lib: s7runtime.R missing"
fi
```
(Match the existing pass/fail helper names in `test-all.sh`.)

- [ ] **Step 5: Run** `python3 -m pytest tests/test_rcmd.py -k s7 -v` → PASS; `bash tests/test-all.sh` → green.

- [ ] **Step 6: Commit** (live byte-identical verify happens in Task 6 before PR)

```bash
git add lib/r/s7runtime.R lib/rcmd.py tests/test_rcmd.py tests/test-all.sh
git commit -m "refactor(rcmd): extract s7runtime R into shipped lib/r/s7runtime.R

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4 (P4): Split `rcmd.py` → `lib/rsnippets.py` + `lib/rhub.py`

**Files:**
- Create: `lib/rsnippets.py`, `lib/rhub.py`
- Modify: `lib/rcmd.py` (imports), any test importing moved privates
- Test: existing suite is the gate

**Interfaces:**
- `lib/rsnippets.py` exports: `r_snippet(...)`, `_guard`, `_r_named_char`, `_r_version_key`, and the constants `_CHECK_ENV`/`_INCOMING_ENV`/`_CRAN_CHECKS_REGISTRY`/`_WIN_FN`/`_PDF_SKIP_RE`.
- `lib/rhub.py` exports: `_RHUB_PRESETS`, `_RHUB_BROKEN_PLATFORMS`, `ALLOWED_RHUB_PLATFORMS`, `_check_rhub_yaml`, `_rhub_preflight`, `_rhub_actions_url`, `_run_rhub`.
- `lib/rcmd.py` keeps the envelope core + `main`; re-exports moved names it still references via `from lib.rsnippets import ...` / lazy `import lib.rhub`.

- [ ] **Step 1: Create `lib/rsnippets.py`** — move `r_snippet` + `_guard` + `_r_named_char` + `_r_version_key` + the CRAN/win constants VERBATIM from `rcmd.py`. Add at top: `import json, re, shutil, subprocess; from pathlib import Path`. `r_snippet`'s s7runtime branch uses `Path(__file__)` — note `__file__` is now `lib/rsnippets.py`, so the `lib/r/s7runtime.R` relative path still resolves (`Path(__file__).parent / "r" / ...`). ✅ no change needed.

- [ ] **Step 2: Create `lib/rhub.py`** — move the 7 rhub names VERBATIM. Add imports: `import re, subprocess; from pathlib import Path; from lib.rsnippets import r_snippet`. `_run_rhub` also calls `_parse_json`, `console_fallback`, `normalize`, `INSTALL_HINT`, `OPTIONAL_ENGINES` — import those from `lib.rcmd` INSIDE `_run_rhub` (lazy, function-local) to avoid a top-level cycle:

```python
def _run_rhub(path, pkg, *, platforms=None, preset=None, rc_mode=False):
    from lib.rcmd import _parse_json, console_fallback, normalize, \
        INSTALL_HINT, OPTIONAL_ENGINES
    ...
```

- [ ] **Step 3: Rewire `lib/rcmd.py`** — delete the moved definitions; add near the top:

```python
from lib.rsnippets import (r_snippet, _guard, _r_named_char, _r_version_key)
```
and in `run()`, make the rhub dispatch a lazy import (keeps `rcmd`→`rhub` off the module top, matching the chosen acyclic direction):

```python
    if kind == "rhub":
        from lib.rhub import _run_rhub
        return _run_rhub(path, pkg, platforms=platforms, preset=preset, rc_mode=rc_mode)
```
Keep `ALLOWED_RHUB_PLATFORMS` etc. in `rhub.py`; if any `rcmd` test referenced `rcmd._RHUB_PRESETS`/`rcmd._run_rhub`, repoint to `lib.rhub`.

- [ ] **Step 4: Repoint tests** — `grep -rn "rcmd\._\(run_rhub\|RHUB\|rhub_\|check_rhub\|ALLOWED_RHUB\)\|rcmd\.r_snippet\|rcmd\._guard\|rcmd\._r_version_key" tests/`. Update each to `from lib import rsnippets, rhub` and `rsnippets.r_snippet` / `rhub._run_rhub` / `rhub.ALLOWED_RHUB_PLATFORMS`. (Tasks 1–3 added tests under `rcmd.` — fix those too.)

- [ ] **Step 5: Green sweep**

```bash
python3 -c "import lib.rcmd, lib.rsnippets, lib.rhub"   # import smoke (no cycles)
python3 -m pytest tests/ -q                              # 463+ green
bash tests/test-all.sh                                   # 43/43
python3 scripts/gen_lib_reference.py --check             # rsnippets/rhub NOT added → still green
mkdocs build --strict --site-dir /tmp/rforge_site >/dev/null && echo mkdocs-ok
```
Expected: all green; `python3 -m lib.rcmd --kind check --path tests/fixtures/<pkg>` output unchanged.

- [ ] **Step 6: Commit**

```bash
git add lib/rsnippets.py lib/rhub.py lib/rcmd.py tests/
git commit -m "refactor(rcmd): split into rsnippets + rhub modules (behavior-preserving)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Docs, CHANGELOG, version bump

**Files:** `CLAUDE.md`, `CHANGELOG.md`, 4 version sources, `.STATUS`, doc version refs

- [ ] **Step 1: `CLAUDE.md`** `lib/` section — add `rsnippets` + `rhub` as **internal** modules (no reference page, like `formatters`) and document the **`lib/r/*.R` script convention** (sourced by snippets; ships in libexec). Update current-state to v2.15.0 if it tracks version.
- [ ] **Step 2: `CHANGELOG.md`** `[Unreleased]` → `## [2.15.0] - 2026-06-20`:
  - Security: `--platforms` allow-list validation (closes R-injection vector).
  - Robustness: bounded timeouts on quick `Rscript` calls.
  - Internal: extracted `s7runtime` R to `lib/r/s7runtime.R`; split `rcmd.py` → `rsnippets`/`rhub`. No surface change (41 commands).
- [ ] **Step 3: Version bump → 2.15.0** in all 4 sources (`plugin.json`, `marketplace.json` ×2, `package.json`) + live-version doc refs per `CLAUDE.md`.
- [ ] **Step 4: Grep** `grep -rn "2\.14\.0" --include='*.md' --include='*.json' . | grep -iv changelog` → no stale live refs.
- [ ] **Step 5: `.STATUS`** — record the feature; update worktrees entry.
- [ ] **Step 6: Commit** `docs: v2.15.0 — rcmd remediation (CLAUDE.md, CHANGELOG, version bump)`.

---

## Task 6: Live verification (MANDATORY, needs R) + PR

- [ ] **Step 1: P1 allow-list exactness** — `Rscript -e 'rhub::rhub_platforms()'` (if rhub installed); confirm `ALLOWED_RHUB_PLATFORMS` covers the real tokens, widen if needed; re-run pytest.
- [ ] **Step 2: P2 byte-identical** — against a real S7 package (reuse an s7review fixture): capture `python3 -m lib.rcmd --kind s7runtime --path <pkg>` output, then `git stash` the P2/P4 commits' state vs the v2.14.0 baseline and diff. The JSON envelope MUST be byte-identical. If not, fix `s7runtime.R` until it matches.
- [ ] **Step 3: P1 rhub smoke** — `python3 -m lib.rcmd --kind rhub --platforms linux,windows --path <pkg-with-rhub-yaml>` dispatches (or reports a clean preflight error); `--platforms 'bad"x'` → error envelope, no R run.
- [ ] **Step 4: Final gates + PR**

```bash
git fetch origin dev && git rebase origin/dev
python3 -m pytest tests/ && bash tests/test-all.sh
gh pr create --base dev --title "v2.15.0: rcmd review remediation (P1–P4)" \
  --body "Implements docs/specs/SPEC-rcmd-remediation-2026-06-20.md. Security (--platforms validation), robustness (Rscript timeouts), maintainability (s7runtime→.R, rcmd split). No surface change; CLI byte-identical (live-verified)."
```

- [ ] **Step 5: After merge** — delete `ORCHESTRATE-rcmd-remediation.md`, `git worktree remove`, update `.STATUS`.

---

## Self-Review (completed by plan author)

- **Spec coverage:** P1 (Task 1) · P3 (Task 2) · P2 (Task 3) · P4 (Task 4) · docs/version (Task 5) · live verify + PR (Task 6). All four findings + the two mandatory live checks + the public-CLI invariant covered. ✅
- **Placeholder scan:** new code shown in full; the only "move verbatim" steps are P2's R logic and P4's function moves — explicitly bounded by source line ranges + the exact names/imports, not vague "implement later". Live byte-identical check is the gate that proves the verbatim move. ✅
- **Type consistency:** `ALLOWED_RHUB_PLATFORMS` (frozenset), `_invoke_r(..., timeout=None)`, `s7_runtime_report(pkg_path)` → 4 stable keys, the `rsnippets`/`rhub` export lists, and the lazy-import direction (`rcmd`→`rhub` only inside `run()`/`_run_rhub`→`rcmd` only inside the function) are consistent across tasks. Envelope error shape `{kind,status,engine_missing,messages}` matches existing. ✅
- **No duplicates / boundary:** `rsnippets`/`rhub` are extractions, not new behavior; `run_changed`/`changed.py`, `s7review.py`, `cranlint.py` untouched. ✅

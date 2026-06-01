# R Dev-Cycle Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a full R package dev-cycle (`build`, `test`, `document`, `install`, `coverage`, `site`, `cycle`) to the rforge plugin's `r:` command namespace, backed by a single structured-output module `lib/rcmd.py`.

**Architecture:** Each command is a `commands/r/<verb>.md` prompt file that shells out to `python3 -m lib.rcmd --kind <kind>`. `lib/rcmd.py` runs the *lower-level* R engine for that kind (`rcmdcheck`, `pkgbuild`, `roxygen2`, `testthat`, `covr`, `pkgdown` — **not** `devtools`), which serializes its structured result to JSON via `jsonlite`; Python normalizes that into one envelope. R subprocess output is JSON, never regex-scraped (console regex is a documented fallback only). CI stays R-free by mocking `Rscript`.

**Tech Stack:** Python 3 (stdlib only: `argparse`, `json`, `subprocess`, `pathlib`, `re`, `shutil`), R 4.x with `rcmdcheck`/`pkgbuild`/`roxygen2`/`testthat`/`covr`/`pkgdown`/`jsonlite`, pytest, rforge's `commands/*.md` + `lib/` conventions.

**Spec:** `docs/specs/SPEC-r-dev-commands-2026-05-31.md`

---

## Pre-flight (read before starting)

- **You are in the worktree** `~/.git-worktrees/rforge/feature-r-dev-commands` on branch `feature/r-dev-commands`. Verify: `git branch --show-current` → `feature/r-dev-commands`. All work happens here.
- **Run lib as a package:** `python3 -m lib.rcmd ...` — never `python3 lib/rcmd.py` (relative imports / package convention; see CLAUDE.md).
- **Conventions to mirror:** read `commands/r/check.md` (command-file shape) and `lib/status.py` (lib module shape: `argparse` CLI, `main()`, module-level docstring) before Task 1.
- **Test gates (must pass before PR):** `python3 -m pytest tests/` and `bash tests/test-all.sh`.
- **Commit style:** conventional commits, sign-off footer `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `lib/rcmd.py` (create) | Locate package, build per-kind R snippet, run `Rscript`, normalize JSON → common envelope, compute status dot, console fallback, graceful degradation |
| `tests/test_rcmd.py` (create) | Unit tests for `find_package`, `normalize`, `console_fallback`, `r_snippet`, `main` (R subprocess mocked) |
| `tests/fixtures/rcmd/*.json` (create) | Captured raw-engine JSON blobs + console samples |
| `commands/r/check.md` (modify) | Retrofit onto `lib.rcmd --kind check` |
| `commands/r/build.md` (create) | `--kind build` prompt + report |
| `commands/r/test.md` (create) | `--kind test` prompt + report |
| `commands/r/document.md` (create) | `--kind document` prompt + report |
| `commands/r/install.md` (create) | `--kind install` prompt + report |
| `commands/r/coverage.md` (create) | `--kind coverage` prompt + report |
| `commands/r/site.md` (create) | `--kind site` (+`--preview`) prompt + report |
| `commands/r/cycle.md` (create) | document→test→check orchestration prompt |
| `docs/reference/rcmd.md` (generate) | Auto-generated lib reference page |
| `README.md`, `docs/index.md`, `docs/REFCARD.md` (modify) | Command tables + 16→23 count |
| `mkdocs.yml` (modify) | Nav entries for new pages |
| `CHANGELOG.md` (modify) | `[Unreleased]` → `[2.1.0]` |
| 4 version sources + doc refs (modify) | Bump to 2.1.0 |
| `.STATUS` (modify) | Feature entry; Phase 4 → v2.2.0 |

---

## Task 1: `lib/rcmd.py` — package locator (TDD)

**Files:**
- Create: `lib/rcmd.py`
- Test: `tests/test_rcmd.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rcmd.py
import json
import textwrap
from pathlib import Path
import pytest
from lib import rcmd


def _write_desc(tmp_path: Path, name="foo", version="0.2.0"):
    (tmp_path / "DESCRIPTION").write_text(
        textwrap.dedent(f"""\
            Package: {name}
            Version: {version}
            Title: Test
            """)
    )
    return tmp_path


def test_find_package_reads_description(tmp_path):
    _write_desc(tmp_path, "mypkg", "1.4.0")
    info = rcmd.find_package(str(tmp_path))
    assert info == {"package": "mypkg", "version": "1.4.0"}


def test_find_package_missing_returns_none(tmp_path):
    assert rcmd.find_package(str(tmp_path)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rcmd.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'lib.rcmd'` (or `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

```python
# lib/rcmd.py
"""Run R package dev-cycle engines and normalize their output to one JSON envelope.

Each "kind" maps to a lower-level R package (NOT devtools):
  check -> rcmdcheck | build -> pkgbuild | document -> roxygen2
  test  -> testthat  | coverage -> covr  | site -> pkgdown | install -> R CMD INSTALL

The R subprocess emits JSON via jsonlite; this module normalizes it. Console
regex parsing exists only as a fallback when jsonlite/structured output is absent.

Usage:  python3 -m lib.rcmd --kind <kind> [--path .] [--as-cran] [--preview]
"""
from __future__ import annotations

import re
from pathlib import Path


def find_package(path: str = ".") -> dict | None:
    """Return {'package','version'} from DESCRIPTION, or None if not a package."""
    desc = Path(path) / "DESCRIPTION"
    if not desc.is_file():
        return None
    fields: dict[str, str] = {}
    for line in desc.read_text().splitlines():
        m = re.match(r"^(Package|Version):\s*(.+)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    if "Package" not in fields:
        return None
    return {"package": fields["Package"], "version": fields.get("Version", "")}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_rcmd.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): package locator from DESCRIPTION

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `normalize()` — envelope + status logic (TDD)

**Files:**
- Modify: `lib/rcmd.py`
- Test: `tests/test_rcmd.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_rcmd.py
def test_normalize_check_clean_is_ok():
    raw = {"errors": [], "warnings": [], "notes": []}
    env = rcmd.normalize("check", raw, exit_code=0, pkg={"package": "foo", "version": "1.0"})
    assert env["status"] == "ok"
    assert env["check"] == {"errors": [], "warnings": [], "notes": []}
    assert env["package"] == "foo"


def test_normalize_check_notes_is_warn():
    raw = {"errors": [], "warnings": [], "notes": ["one note"]}
    env = rcmd.normalize("check", raw, exit_code=0, pkg=None)
    assert env["status"] == "warn"


def test_normalize_check_errors_is_error():
    raw = {"errors": ["boom"], "warnings": [], "notes": []}
    env = rcmd.normalize("check", raw, exit_code=1, pkg=None)
    assert env["status"] == "error"


def test_normalize_test_failures_is_error():
    raw = {"passed": 40, "failed": 2, "skipped": 1, "warnings": 0,
           "failing_files": ["test-a.R"]}
    env = rcmd.normalize("test", raw, exit_code=1, pkg=None)
    assert env["status"] == "error"
    assert env["tests"]["failing_files"] == ["test-a.R"]


def test_normalize_engine_missing_is_error():
    raw = {"engine_missing": ["pkgdown"]}
    env = rcmd.normalize("site", raw, exit_code=1, pkg=None)
    assert env["status"] == "error"
    assert env["engine_missing"] == ["pkgdown"]
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_rcmd.py -k normalize -v`
Expected: FAIL — `AttributeError: module 'lib.rcmd' has no attribute 'normalize'`.

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py

def _status_for(kind: str, raw: dict, exit_code: int) -> str:
    if raw.get("engine_missing"):
        return "error"
    if kind == "check":
        if raw.get("errors"):
            return "error"
        if raw.get("warnings") or raw.get("notes"):
            return "warn"
        return "ok"
    if kind == "test":
        if raw.get("failed") or exit_code != 0:
            return "error"
        if raw.get("warnings") or raw.get("skipped"):
            return "warn"
        return "ok"
    if kind == "site":
        if exit_code != 0 or not raw.get("built", True):
            return "error"
        return "warn" if raw.get("problems") else "ok"
    if kind == "coverage":
        return "ok"  # informational; low files surfaced, not failed
    # build, document, install: success == exit 0
    return "ok" if exit_code == 0 else "error"


def normalize(kind: str, raw: dict, exit_code: int, pkg: dict | None) -> dict:
    """Fold a raw engine result into the common envelope."""
    env: dict = {
        "kind": kind,
        "status": _status_for(kind, raw, exit_code),
        "engine_missing": raw.get("engine_missing", []),
        "messages": raw.get("messages", []),
    }
    if pkg:
        env["package"] = pkg.get("package", "")
        env["version"] = pkg.get("version", "")
    if kind == "check":
        env["check"] = {k: raw.get(k, []) for k in ("errors", "warnings", "notes")}
    elif kind == "test":
        env["tests"] = {
            "passed": raw.get("passed", 0), "failed": raw.get("failed", 0),
            "skipped": raw.get("skipped", 0), "warnings": raw.get("warnings", 0),
            "failing_files": raw.get("failing_files", []),
        }
    elif kind == "coverage":
        env["coverage"] = {"total_pct": raw.get("total_pct"),
                           "per_file": raw.get("per_file", {})}
    elif kind == "build":
        env["build"] = {"artifact": raw.get("artifact"), "bytes": raw.get("bytes")}
    elif kind == "site":
        env["site"] = {"checked": raw.get("checked", False),
                       "built": raw.get("built", False),
                       "problems": raw.get("problems", [])}
    elif kind == "install":
        env["install"] = {"installed_version": raw.get("installed_version"),
                          "exit": exit_code}
    return env
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rcmd.py -k normalize -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): normalize raw engine output into common envelope

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `console_fallback()` — regex fallback (TDD)

**Files:**
- Modify: `lib/rcmd.py`
- Test: `tests/test_rcmd.py`

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_rcmd.py
def test_console_fallback_testthat_summary():
    text = "Some chatter\n[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]\n"
    raw = rcmd.console_fallback("test", text)
    assert raw == {"failed": 2, "warnings": 0, "skipped": 1, "passed": 41}


def test_console_fallback_rcmdcheck_summary():
    text = "... \n0 errors v | 1 warning x | 2 notes x\n"
    raw = rcmd.console_fallback("check", text)
    assert len(raw["errors"]) == 0
    assert len(raw["warnings"]) == 1
    assert len(raw["notes"]) == 2


def test_console_fallback_unknown_returns_messages():
    raw = rcmd.console_fallback("test", "no summary line here")
    assert "messages" in raw
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_rcmd.py -k console -v`
Expected: FAIL — no attribute `console_fallback`.

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py

def console_fallback(kind: str, text: str) -> dict:
    """Best-effort parse of human console output when JSON is unavailable.

    Recognized formats:
      testthat: '[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]'
      rcmdcheck: '0 errors X | 1 warning Y | 2 notes Z'
    """
    if kind == "test":
        m = re.search(r"FAIL\s+(\d+)\s*\|\s*WARN\s+(\d+)\s*\|\s*"
                      r"SKIP\s+(\d+)\s*\|\s*PASS\s+(\d+)", text)
        if m:
            return {"failed": int(m.group(1)), "warnings": int(m.group(2)),
                    "skipped": int(m.group(3)), "passed": int(m.group(4))}
    if kind == "check":
        m = re.search(r"(\d+)\s+errors?\b.*?(\d+)\s+warnings?\b.*?(\d+)\s+notes?\b",
                      text, re.IGNORECASE | re.DOTALL)
        if m:
            return {"errors": [""] * int(m.group(1)),
                    "warnings": [""] * int(m.group(2)),
                    "notes": [""] * int(m.group(3))}
    return {"messages": [ln for ln in text.splitlines() if ln.strip()][-10:]}
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rcmd.py -k console -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): console-output fallback parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `r_snippet()` — per-kind R source (TDD)

**Files:**
- Modify: `lib/rcmd.py`
- Test: `tests/test_rcmd.py`

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_rcmd.py
@pytest.mark.parametrize("kind,needle", [
    ("check", "rcmdcheck::rcmdcheck"),
    ("build", "pkgbuild::build"),
    ("document", "roxygen2::roxygenize"),
    ("test", "testthat::test_local"),
    ("coverage", "covr::package_coverage"),
    ("site", "pkgdown::build_site"),
])
def test_r_snippet_uses_lower_level_engine(kind, needle):
    src = rcmd.r_snippet(kind, path="/tmp/foo", as_cran=False, preview=False)
    assert needle in src
    assert "jsonlite::toJSON" in src
    assert "devtools::" not in src  # never the meta-wrapper


def test_r_snippet_check_as_cran_flag():
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True, preview=False)
    assert "--as-cran" in src
    assert 'error_on = "never"' in src


def test_r_snippet_site_preview():
    assert "preview_site" in rcmd.r_snippet("site", "/tmp/f", False, preview=True)
    assert "preview_site" not in rcmd.r_snippet("site", "/tmp/f", False, preview=False)
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_rcmd.py -k snippet -v`
Expected: FAIL — no attribute `r_snippet`.

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py
import json as _json

# Each engine is gated: if requireNamespace fails, emit engine_missing JSON.
def _guard(pkg_name: str, body: str) -> str:
    return (
        f'if (!requireNamespace("{pkg_name}", quietly=TRUE) || '
        f'!requireNamespace("jsonlite", quietly=TRUE)) {{'
        f'cat(\'{{"engine_missing":["{pkg_name}"]}}\'); quit(status=0)}}; '
        + body
    )


def r_snippet(kind: str, path: str, as_cran: bool, preview: bool) -> str:
    p = _json.dumps(path)  # safely quote the path for R
    if kind == "check":
        args = 'c("--as-cran")' if as_cran else "character()"
        return _guard("rcmdcheck",
            f'r <- rcmdcheck::rcmdcheck({p}, args={args}, quiet=TRUE, error_on = "never"); '
            f'cat(jsonlite::toJSON(list(errors=r$errors, warnings=r$warnings, '
            f'notes=r$notes), auto_unbox=TRUE, null="list"))')
    if kind == "build":
        return _guard("pkgbuild",
            f'p <- pkgbuild::build({p}, quiet=TRUE); '
            f'cat(jsonlite::toJSON(list(artifact=basename(p), '
            f'bytes=as.integer(file.info(p)$size)), auto_unbox=TRUE))')
    if kind == "document":
        return _guard("roxygen2",
            f'roxygen2::roxygenize({p}); cat(\'{{"documented":true}}\')')
    if kind == "test":
        return _guard("testthat",
            f'res <- testthat::test_local({p}, reporter="list", stop_on_failure=FALSE); '
            f'df <- as.data.frame(res); '
            f'cat(jsonlite::toJSON(list(passed=sum(df$passed), failed=sum(df$failed), '
            f'skipped=sum(df$skipped), warnings=sum(df$warning), '
            f'failing_files=unique(df$file[df$failed>0 | df$error>0])), auto_unbox=TRUE))')
    if kind == "coverage":
        return _guard("covr",
            f'cv <- covr::package_coverage({p}); l <- covr::coverage_to_list(cv); '
            f'cat(jsonlite::toJSON(list(total_pct=covr::percent_coverage(cv), '
            f'per_file=as.list(l$filecoverage)), auto_unbox=TRUE))')
    if kind == "site":
        prev = ('pkgdown::preview_site(' + p + '); ' if preview else '')
        return _guard("pkgdown",
            f'chk <- tryCatch({{pkgdown::check_pkgdown({p}); list(ok=TRUE, problems=character())}}, '
            f'error=function(e) list(ok=FALSE, problems=conditionMessage(e))); '
            f'pkgdown::build_site({p}, preview=FALSE, new_process=TRUE, quiet=TRUE); {prev}'
            f'cat(jsonlite::toJSON(list(checked=TRUE, built=TRUE, '
            f'problems=as.list(chk$problems)), auto_unbox=TRUE))')
    raise ValueError(f"unknown kind: {kind}")
```

> NOTE for `install`: handled in Python (`R CMD INSTALL`), not via `r_snippet` — see Task 5.

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rcmd.py -k snippet -v`
Expected: PASS (8 parametrized + 2).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): per-kind R snippets using lower-level engines

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `run()` + `main()` CLI with mocked R (TDD)

**Files:**
- Modify: `lib/rcmd.py`
- Test: `tests/test_rcmd.py`

- [ ] **Step 1: Write failing tests** (mock the R subprocess via monkeypatch)

```python
# append to tests/test_rcmd.py
def test_run_check_happy_path(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.2.0")

    def fake_invoke(snippet):  # returns (stdout, exit_code)
        return ('{"errors":[],"warnings":["W"],"notes":[]}', 0)

    monkeypatch.setattr(rcmd, "_invoke_r", lambda snippet: fake_invoke(snippet))
    env = rcmd.run("check", str(tmp_path), as_cran=False, preview=False)
    assert env["status"] == "warn"
    assert env["package"] == "foo"
    assert env["check"]["warnings"] == ["W"]


def test_run_no_description_errors(tmp_path):
    env = rcmd.run("check", str(tmp_path), as_cran=False, preview=False)
    assert env["status"] == "error"
    assert "detect" in " ".join(env["messages"]).lower()


def test_run_falls_back_on_nonjson(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ("[ FAIL 1 | WARN 0 | SKIP 0 | PASS 9 ]", 1))
    env = rcmd.run("test", str(tmp_path), as_cran=False, preview=False)
    assert env["tests"]["failed"] == 1
    assert env["status"] == "error"


def test_main_emits_json(tmp_path, monkeypatch, capsys):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ('{"errors":[],"warnings":[],"notes":[]}', 0))
    rc = rcmd.main(["--kind", "check", "--path", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "ok"
    assert rc == 0
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_rcmd.py -k "run or main" -v`
Expected: FAIL — no attribute `run`/`_invoke_r`/`main`.

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py
import argparse
import json
import shutil
import subprocess
import sys

OPTIONAL_ENGINES = {"covr", "pkgdown"}
INSTALL_HINT = {
    "rcmdcheck": 'install.packages("rcmdcheck")',
    "pkgbuild": 'install.packages("pkgbuild")',
    "roxygen2": 'install.packages("roxygen2")',
    "testthat": 'install.packages("testthat")',
    "covr": 'install.packages("covr")',
    "pkgdown": 'install.packages("pkgdown")',
    "jsonlite": 'install.packages("jsonlite")',
}


def _invoke_r(snippet: str) -> tuple[str, int]:
    """Run an R snippet via Rscript; return (stdout, exit_code). Mocked in tests."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return ('{"engine_missing":["R"]}', 127)
    proc = subprocess.run([rscript, "-e", snippet], capture_output=True, text=True)
    return (proc.stdout.strip(), proc.returncode)


def _install_package(path: str) -> tuple[dict, int]:
    """R CMD INSTALL <path>; return (raw, exit_code)."""
    pkg = find_package(path) or {}
    rbin = shutil.which("R")
    if rbin is None:
        return ({"engine_missing": ["R"]}, 127)
    proc = subprocess.run([rbin, "CMD", "INSTALL", path],
                          capture_output=True, text=True)
    return ({"installed_version": pkg.get("version")}, proc.returncode)


def run(kind: str, path: str = ".", *, as_cran: bool = False,
        preview: bool = False) -> dict:
    pkg = find_package(path)
    if pkg is None:
        return {"kind": kind, "status": "error", "engine_missing": [],
                "messages": ["No DESCRIPTION found — is this an R package? "
                             "Try /rforge:detect to locate packages."]}
    if kind == "install":
        raw, code = _install_package(path)
    else:
        stdout, code = _invoke_r(r_snippet(kind, path, as_cran, preview))
        try:
            raw = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            raw = console_fallback(kind, stdout)
    env = normalize(kind, raw, code, pkg)
    # attach install hints for any missing engine
    for eng in env.get("engine_missing", []):
        hint = INSTALL_HINT.get(eng)
        if hint:
            env.setdefault("messages", []).append(f"Missing R package — run: {hint}")
        if eng in OPTIONAL_ENGINES and env["status"] == "error":
            env["status"] = "warn"  # optional engines downgrade
    return env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m lib.rcmd",
                                 description="Run an R dev-cycle engine, emit JSON.")
    ap.add_argument("--kind", required=True,
                    choices=["check", "build", "test", "document",
                             "install", "coverage", "site", "cycle"])
    ap.add_argument("--path", default=".")
    ap.add_argument("--as-cran", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ns = ap.parse_args(argv)
    if ns.kind == "cycle":
        env = _run_cycle(ns.path)
    else:
        env = run(ns.kind, ns.path, as_cran=ns.as_cran, preview=ns.preview)
    print(json.dumps(env, indent=2))
    return 0 if env.get("status") != "error" else 1


def _run_cycle(path: str) -> dict:
    """document -> test -> check; stop at first hard error."""
    stages = []
    for kind in ("document", "test", "check"):
        env = run(kind, path)
        stages.append({"kind": kind, "status": env["status"]})
        if env["status"] == "error":
            return {"kind": "cycle", "status": "error", "stages": stages,
                    "failed_stage": kind, "detail": env,
                    "engine_missing": env.get("engine_missing", []),
                    "messages": env.get("messages", [])}
    worst = "warn" if any(s["status"] == "warn" for s in stages) else "ok"
    return {"kind": "cycle", "status": worst, "stages": stages,
            "engine_missing": [], "messages": []}


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run full suite**

Run: `python3 -m pytest tests/test_rcmd.py -v`
Expected: PASS (all ~20 tests).

- [ ] **Step 5: Add a `cycle` test, then commit**

```python
# append to tests/test_rcmd.py
def test_cycle_stops_on_first_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    calls = []

    def fake_run(kind, path, **kw):
        calls.append(kind)
        return {"kind": kind, "status": "error" if kind == "test" else "ok",
                "engine_missing": [], "messages": []}

    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cycle(str(tmp_path))
    assert env["failed_stage"] == "test"
    assert calls == ["document", "test"]  # never reached "check"
```

Run: `python3 -m pytest tests/test_rcmd.py -k cycle -v` → PASS, then:

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): run/main CLI + cycle orchestration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Retrofit `commands/r/check.md`

**Files:**
- Modify: `commands/r/check.md`

- [ ] **Step 1: Replace the body** (keep frontmatter `name`/`arguments`; update process to call lib.rcmd)

Replace everything below the frontmatter with:

````markdown
# R Package Check

Run `R CMD check` (via `rcmdcheck`) on an R package and report structured results.

## Process

1. Resolve the package path from `$ARGUMENTS` (default: current directory).
2. Run the check through the shared runner:

   ```bash
   python3 -m lib.rcmd --kind check --path "<path>"   # add --as-cran if requested
   ```

3. Parse the JSON envelope and render the report below. Do **not** re-run R yourself.

## Output Format

```markdown
## Package Check: {package} v{version}

### Status: {🟢 if ok / 🟡 if warn / 🔴 if error}

### R CMD Check
- Errors: {len check.errors}
- Warnings: {len check.warnings}
- Notes: {len check.notes}

{If any errors/warnings/notes: list each message as a bullet}

### Recommended Actions
{1-3 concrete next steps, or "None — package is clean ✅"}
```

If `engine_missing` is non-empty, report 🔴 and surface the install hint from `messages`.

## Related Commands
- `/rforge:r:cycle` — document → test → check in one pass
- `/rforge:thorough` — multi-package rollup including R CMD check
- `/rforge:docs:check` — documentation drift (complements R CMD check)
````

- [ ] **Step 2: Verify frontmatter still valid**

Run: `bash tests/test-all.sh 2>&1 | grep -iE "frontmatter|command-name|uniqueness"`
Expected: those checks PASS.

- [ ] **Step 3: Commit**

```bash
git add commands/r/check.md
git commit -m "refactor(r:check): drive report from lib.rcmd envelope

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: New command files (`build`, `test`, `document`, `install`, `coverage`, `site`, `cycle`)

**Files:** Create all seven under `commands/r/`. Each mirrors `check.md`'s shape: frontmatter (`name: rforge:r:<verb>`, `description`, `arguments`) + a `## Process` calling `python3 -m lib.rcmd --kind <verb>` + an `## Output Format` rendering the relevant envelope fields.

- [ ] **Step 1: Create `commands/r/build.md`**

````markdown
---
name: rforge:r:build
description: Build an R package tarball (pkgbuild) and report the artifact
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Build

Build a source tarball via `pkgbuild::build()` and report the artifact.

## Process

```bash
python3 -m lib.rcmd --kind build --path "<path from $ARGUMENTS or .>"
```

Render the JSON envelope. Do not run R directly.

## Output Format

```markdown
## Build: {package} v{version}
### Status: {🟢/🔴}
- Artifact: `{build.artifact}`
- Size: {build.bytes / 1024} KB
{If engine_missing or status error: show messages / install hint}
```

## Related Commands
- `/rforge:r:check` — validate before building
- `/rforge:r:install` — install the built package
````

- [ ] **Step 2: Create `commands/r/test.md`**

````markdown
---
name: rforge:r:test
description: Run package tests (testthat) and report pass/fail/skip counts
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Tests

Run the test suite via `testthat::test_local()` and report results.

## Process

```bash
python3 -m lib.rcmd --kind test --path "<path>"
```

## Output Format

```markdown
## Tests: {package} v{version}
### Status: {🟢 if 0 failed / 🟡 if skips or warnings / 🔴 if failures}
- Passed: {tests.passed}
- Failed: {tests.failed}
- Skipped: {tests.skipped}
- Warnings: {tests.warnings}
{If failing_files: list each under "### Failing files"}
### Recommended Actions
{Next steps or "All green ✅"}
```

## Related Commands
- `/rforge:r:cycle` — document → test → check
- `/rforge:r:coverage` — test coverage report
````

- [ ] **Step 3: Create `commands/r/document.md`**

````markdown
---
name: rforge:r:document
description: Regenerate Rd docs and NAMESPACE (roxygen2)
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Documentation

Regenerate `man/*.Rd` and `NAMESPACE` via `roxygen2::roxygenize()`.

> This is the blessed regeneration path. The PreToolUse hook blocks *hand-edits*
> to `man/*.Rd`; running roxygen via this command (Bash) is allowed.

## Process

```bash
python3 -m lib.rcmd --kind document --path "<path>"
```

## Output Format

```markdown
## Document: {package} v{version}
### Status: {🟢/🔴}
{On success: "Regenerated man/ and NAMESPACE."}
{On error: surface messages}
### Recommended Actions
- Review changes: `git diff man/ NAMESPACE`
```

## Related Commands
- `/rforge:r:check` — verify docs after regenerating
- `/rforge:docs:check` — documentation drift across packages
````

- [ ] **Step 4: Create `commands/r/install.md`**

````markdown
---
name: rforge:r:install
description: Install the package locally (R CMD INSTALL) and report version
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Install

Install the package via `R CMD INSTALL` and report the installed version.

## Process

```bash
python3 -m lib.rcmd --kind install --path "<path>"
```

## Output Format

```markdown
## Install: {package} v{version}
### Status: {🟢 if exit 0 / 🔴}
- Installed version: {install.installed_version}
{On error: surface messages (e.g. unmet dependencies)}
```

## Related Commands
- `/rforge:r:build` — build before installing
- `/rforge:r:check` — validate first
````

- [ ] **Step 5: Create `commands/r/coverage.md`**

````markdown
---
name: rforge:r:coverage
description: Test coverage report (covr) — total and per-file
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Coverage

Compute coverage via `covr::package_coverage()`.

## Process

```bash
python3 -m lib.rcmd --kind coverage --path "<path>"
```

`covr` is optional — if `engine_missing` includes `covr`, report 🟡 with the install hint.

## Output Format

```markdown
## Coverage: {package} v{version}
### Total: {coverage.total_pct}%
### Lowest-covered files
{Sorted ascending from coverage.per_file, top 5: "- R/foo.R — 12.0%"}
### Recommended Actions
{Point at the lowest files, or "Coverage looks healthy ✅"}
```

## Related Commands
- `/rforge:r:test` — run the tests behind the coverage
````

- [ ] **Step 6: Create `commands/r/site.md`**

````markdown
---
name: rforge:r:site
description: Build the pkgdown website; optionally preview it
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: preview
    description: Open the built site locally (pkgdown::preview_site)
    required: false
    type: boolean
    default: false
---

# R Package Website

Validate and build the pkgdown site via `check_pkgdown()` + `build_site()`.

## Process

```bash
python3 -m lib.rcmd --kind site --path "<path>"   # add --preview if requested
```

`pkgdown` is optional — if `engine_missing` includes `pkgdown`, report 🟡 with the install hint.

## Output Format

```markdown
## Website: {package} v{version}
### Status: {🟢 built clean / 🟡 built with problems / 🔴 build failed}
- Checked: {site.checked}
- Built: {site.built}
{If site.problems: list each under "### Problems"}
### Recommended Actions
{Fix problems, or "Site built to docs/ ✅"}
```

## Related Commands
- `/rforge:r:document` — ensure Rd docs exist before building the site
````

- [ ] **Step 7: Create `commands/r/cycle.md`**

````markdown
---
name: rforge:r:cycle
description: Full dev cycle — document → test → check (stops at first error)
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Dev Cycle

Run `document` → `test` → `check` in sequence, stopping at the first hard error.

## Process

```bash
python3 -m lib.rcmd --kind cycle --path "<path>"
```

## Output Format

```markdown
## Dev Cycle: {package}
### Status: {🟢 all ok / 🟡 warnings / 🔴 failed at a stage}
| Stage | Result |
|-------|--------|
| document | {stages[0].status dot} |
| test | {stages[1].status dot} |
| check | {stages[2].status dot} |
{If failed_stage: "Stopped at **{failed_stage}** — {detail summary}"}
### Recommended Actions
{Next steps based on which stage failed}
```

## Related Commands
- `/rforge:r:check`, `/rforge:r:test`, `/rforge:r:document` — individual stages
````

- [ ] **Step 8: Verify all command files parse**

Run: `bash tests/test-all.sh 2>&1 | tail -30`
Expected: frontmatter-valid, command-name-uniqueness, skills-valid all PASS. Fix any reported issue.

- [ ] **Step 9: Commit**

```bash
git add commands/r/
git commit -m "feat(r): add build/test/document/install/coverage/site/cycle commands

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Reference docs + CI gen-check

**Files:**
- Generate: `docs/reference/rcmd.md`
- Verify: `scripts/gen_lib_reference.py`

- [ ] **Step 1: Inspect the generator to confirm it discovers public modules**

Run: `python3 scripts/gen_lib_reference.py --help` and read `scripts/gen_lib_reference.py` to find the module list (it currently covers discovery/deps/status/init). Add `rcmd` to its public-module list if the list is hardcoded.

- [ ] **Step 2: Generate the reference page**

Run: `python3 scripts/gen_lib_reference.py`
Expected: writes/updates `docs/reference/rcmd.md`.

- [ ] **Step 3: Verify the CI gate is satisfied**

Run: `python3 scripts/gen_lib_reference.py --check`
Expected: exit 0 (no drift).

- [ ] **Step 4: Commit**

```bash
git add scripts/gen_lib_reference.py docs/reference/rcmd.md
git commit -m "docs(rcmd): generate lib reference page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Docs tables, nav, CHANGELOG, version bump

**Files:** `README.md`, `docs/index.md`, `docs/REFCARD.md`, `mkdocs.yml`, `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `package.json`, `.STATUS`

- [ ] **Step 1: Add the 7 commands to every command table**

Grep current tables: `grep -rn "r:check" README.md docs/index.md docs/REFCARD.md`. Add rows for `r:build`, `r:test`, `r:document`, `r:install`, `r:coverage`, `r:site`, `r:cycle` adjacent to `r:check`. Update any "16 commands" count to "23".

- [ ] **Step 2: Add nav entries in `mkdocs.yml`**

Add `docs/reference/rcmd.md` under the Reference section and any command pages under their nav group (mirror how `r:check`/`docs:check` are listed).

- [ ] **Step 3: CHANGELOG** — convert `[Unreleased]` → `## [2.1.0] - 2026-05-31` with an "Added" section listing the 7 commands + `lib/rcmd.py`.

- [ ] **Step 4: Bump version to 2.1.0 in all 4 sources**

Edit: `.claude-plugin/plugin.json` `version`; `.claude-plugin/marketplace.json` `metadata.version` AND `plugins[0].version`; `package.json` `version`. Then update live-version doc refs listed in CLAUDE.md (REFCARD header + ASCII box, docs/README.md, README.md tree comments, docs/index.md).

- [ ] **Step 5: Grep for stale version strings**

Run: `grep -rn "2\.0\.0" --include='*.md' --include='*.json' . | grep -iv changelog`
Expected: no remaining live refs to the old version (history entries in CHANGELOG are fine).

- [ ] **Step 6: Update `.STATUS`** — add a "v2.1.0: r: dev-cycle commands" entry; move "Phase 4 (agents)" target to v2.2.0; note the worktree.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/ mkdocs.yml CHANGELOG.md .claude-plugin/ package.json .STATUS
git commit -m "docs: command tables, nav, CHANGELOG; bump to v2.1.0

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Full gate + add lib smoke check

**Files:** `tests/test-all.sh`

- [ ] **Step 1: Add a `lib.rcmd` CLI smoke line** to `tests/test-all.sh`

Mirror the existing "lib CLI smoke" lines (for discovery/deps/status/init). Add a check that runs the module against a fixture package directory and asserts it emits valid JSON — using a stubbed `Rscript` on PATH (or a `--path` to `tests/fixtures/` with `_invoke_r` short-circuited). Keep CI R-free: assert `python3 -m lib.rcmd --kind check --path tests/fixtures/<pkg>` exits 0 and prints JSON when R is absent it should still emit an `engine_missing`/`error` envelope and exit non-zero — assert the JSON parses either way.

- [ ] **Step 2: Run both gates**

```bash
python3 -m pytest tests/ -v          # expect 65 + ~21 new = ~86 passing
bash tests/test-all.sh                # expect prior 29 checks + new smoke = PASS
```
Expected: both green. Fix anything red before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test-all.sh tests/fixtures/
git commit -m "test: lib.rcmd CLI smoke check in test-all.sh

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Live sanity check (optional, needs R) + PR

- [ ] **Step 1: If R is available, run against a real package**

```bash
python3 -m lib.rcmd --kind check --path ~/projects/r-packages/<somepkg>
python3 -m lib.rcmd --kind test  --path ~/projects/r-packages/<somepkg>
```
Confirm envelopes look right. (covr/pkgdown may report `engine_missing` — expected.)

- [ ] **Step 2: Final gate, then PR to dev**

```bash
git fetch origin dev && git rebase origin/dev
python3 -m pytest tests/ && bash tests/test-all.sh
gh pr create --base dev --title "feat: r: dev-cycle commands (build/test/site + lib/rcmd)" \
  --body "Implements docs/specs/SPEC-r-dev-commands-2026-05-31.md. Adds 7 r: commands backed by lib/rcmd.py (structured JSON from rcmdcheck/pkgbuild/roxygen2/testthat/covr/pkgdown). Ships v2.1.0."
```

- [ ] **Step 3: Cleanup after merge** — remove this `ORCHESTRATE-r-dev-commands.md` as part of the merge (per CLAUDE.md: ORCHESTRATE files don't belong on `dev`), then `git worktree remove ~/.git-worktrees/rforge/feature-r-dev-commands`.

---

## Addendum (2026-05-31, post-research) — SUPERSEDES the snippets it names

Research on `pkgload`/`testthat` and `pkgdown` vignettes refined three things.
Where this addendum conflicts with earlier tasks, **the addendum wins.**

### A. `r:test` snippet — make the self-load explicit (Task 4)

`testthat::test_local()` already loads the source package via `pkgload::load_all()`
(default `load_package="source"`); do **not** add a separate `load_all()` (double-load).
In Task 4's `test` branch of `r_snippet`, change the call to:

```r
testthat::test_local({p}, load_package="source", reporter="list", stop_on_failure=FALSE)
```

### B. New command `r:load` (extends Tasks 4, 5, 7) — 8th new command

- **`r_snippet` (Task 4):** add a `load` branch:

```python
    if kind == "load":
        return _guard("pkgload",
            f'pkgload::load_all({p}); cat(\'{{"loaded":true}}\')')
```

- **`main` choices (Task 5):** add `"load"` to the `--kind` `choices` list.
- **`normalize` (Task 2):** `load` needs no special block — status falls through
  to the default (`ok` if exit 0 else `error`); add a test asserting that.
- **Command file `commands/r/load.md` (Task 7):** mirror `build.md`; engine
  `pkgload::load_all()`; report 🟢/🔴 + "Loaded {package} into namespace."; relate
  to `/rforge:r:test`. Add to the Task 9 command tables (now **16 → 24**).

### C. `r:site` snippet + flags (Tasks 4, 5, 7) — pkgdown vignette-aware

Default to `pkgdown_sitrep()` (reports all problems, non-fatal), not the
fail-fast `check_pkgdown()`. Add flags `--strict`, `--articles-only`, `--devel`.

- **Signature change:** extend `r_snippet(kind, path, as_cran, preview, *,
  strict=False, articles_only=False, devel=False)` and thread the same kwargs
  through `run()` and `main()` (add `--strict`, `--articles-only`, `--devel`
  to the argparse in Task 5; pass them into `run()`).
- **`site` branch of `r_snippet` (replaces Task 4's `site` branch):**

```python
    if kind == "site":
        prev = (f'pkgdown::preview_site({p}); ' if preview else '')
        gate = (f'pkgdown::check_pkgdown({p}); '          # --strict: abort on first
                if strict else
                f'probs <- paste(utils::capture.output('   # default: report all
                f'pkgdown::pkgdown_sitrep({p})), collapse="\\n"); ')
        if articles_only:
            build = f'pkgdown::build_articles({p}, preview=FALSE)'  # reinstall handled in run()
        else:
            build = (f'pkgdown::build_site({p}, preview=FALSE, new_process=TRUE, '
                     f'quiet=TRUE, devel={"TRUE" if devel else "FALSE"})')
        probs_expr = 'character()' if strict else 'if (exists("probs")) probs else ""'
        return _guard("pkgdown",
            f'{gate}{build}; {prev}'
            f'cat(jsonlite::toJSON(list(checked=TRUE, built=TRUE, '
            f'problems=as.list({probs_expr})), auto_unbox=TRUE))')
```

- **`run()` (Task 5):** when `kind=="site"` and `articles_only`, reinstall first
  (`_install_package(path)`), since standalone `build_articles()` renders the
  *installed* version. A non-zero exit during the build = **vignette render error**
  (status `error`); sitrep-only problems with exit 0 = **config/index** (status
  `warn`) — `_status_for("site", ...)` already encodes this.
- **`commands/r/site.md` (Task 7):** document the four flags; in Output Format,
  separate a "### Vignette/render errors" section (when status 🔴) from a
  "### Config/index problems" section (sitrep warnings). Add the pandoc-missing
  note (🟡 + install hint).

### D. Tests to add (Task 5/10)

- `test_r_snippet_test_uses_load_package_source` — asserts `load_package="source"`.
- `test_r_snippet_load_uses_pkgload` — asserts `pkgload::load_all` in `load` snippet.
- `test_normalize_load_ok` — exit 0 ⇒ `ok`.
- `test_r_snippet_site_strict_uses_check_pkgdown` / default uses `pkgdown_sitrep`.
- `test_r_snippet_site_articles_only_uses_build_articles`.

## Addendum 2 (2026-05-31) — quality commands folded into v2.1.0

Per BRAINSTORM-r-command-expansion, four quality commands join this feature
(they reuse `lib/rcmd.py`). Now **16 → 28 commands**. These are optional-engine
commands (🟡 + install hint if the engine is absent).

### E. New kinds in `r_snippet` (Task 4)

```python
    if kind == "lint":
        return _guard("lintr",
            f'ls <- lintr::lint_package({p}); '
            f'cat(jsonlite::toJSON(list(lints=lapply(ls, function(x) list('
            f'file=x$filename, line=x$line_number, linter=x$linter, '
            f'message=x$message))), auto_unbox=TRUE, null="list"))')
    if kind == "spell":
        return _guard("spelling",
            f'sp <- spelling::spell_check_package({p}); '
            f'cat(jsonlite::toJSON(list(misspelled=lapply(seq_len(nrow(sp)), '
            f'function(i) list(word=sp$word[i], files=sp$found[[i]]))), '
            f'auto_unbox=TRUE, null="list"))')
    if kind == "urlcheck":
        return _guard("urlchecker",
            f'u <- urlchecker::url_check({p}); '
            f'cat(jsonlite::toJSON(list(broken=lapply(seq_len(nrow(u)), '
            f'function(i) list(url=u$URL[i], message=u$message[i], '
            f'new_url=u$newURL[i]))), auto_unbox=TRUE, null="list"))')
    if kind == "style":
        return _guard("styler",
            f'res <- styler::style_pkg({p}); '
            f'cat(jsonlite::toJSON(list(changed_files='
            f'as.list(res$file[isTRUE(res$changed) | res$changed %in% TRUE])), '
            f'auto_unbox=TRUE, null="list"))')
```

> `urlchecker::url_check()` column names vary by version — the implementer must
> verify (`names(urlchecker::url_check("."))`) and adjust `URL`/`message`/`newURL`.

### F. `normalize` blocks (Task 2)

```python
    elif kind == "lint":
        lints = raw.get("lints", [])
        env["lint"] = {"count": len(lints), "lints": lints}
    elif kind == "spell":
        miss = raw.get("misspelled", [])
        env["spell"] = {"count": len(miss), "misspelled": miss}
    elif kind == "urlcheck":
        broken = raw.get("broken", [])
        env["urlcheck"] = {"count": len(broken), "broken": broken}
    elif kind == "style":
        changed = raw.get("changed_files", [])
        env["style"] = {"count": len(changed), "changed_files": changed}
```

And in `_status_for` (Task 2): lint/spell/urlcheck → `warn` if their count > 0
else `ok` (findings are advisory, never `error`); style → `ok` if exit 0.

```python
    if kind in ("lint", "spell", "urlcheck"):
        counts = {"lint": "lints", "spell": "misspelled", "urlcheck": "broken"}
        return "warn" if raw.get(counts[kind]) else "ok"
    if kind == "style":
        return "ok" if exit_code == 0 else "error"
```

### G. `main` choices (Task 5)

Add `"lint", "spell", "urlcheck", "style"` to the `--kind` `choices` list.

### H. Command files (Task 7) — create four more under `commands/r/`

Mirror `build.md`'s shape. Key per-file specifics:

- **`r:lint`** → `--kind lint`; Output: count + group lints by file (`R/foo.R:3 — object_name_linter: …`); 🟢 if 0 / 🟡 if any. Read-only.
- **`r:spell`** → `--kind spell`; Output: list misspelled words + locations; suggest "add to `inst/WORDLIST`" for false positives; 🟢/🟡.
- **`r:urlcheck`** → `--kind urlcheck`; Output: each broken URL + status + suggested replacement; 🟢/🟡.
- **`r:style`** → `--kind style`; **mutates source** — after running, show `git diff --stat` then a brief summary of what reformatted; note "review with `git diff`, undo with `git checkout`". 🟢 always (it's an action); list `changed_files`.

Each: if engine in `engine_missing`, report 🟡 + the `install.packages()` hint.

### I. Tests (Task 5/10)

- `test_r_snippet_lint_uses_lintr` / `spell`→spelling / `urlcheck`→urlchecker / `style`→styler.
- `test_normalize_lint_warns_when_findings` (count>0 ⇒ warn; count 0 ⇒ ok).
- `test_normalize_style_ok_on_exit0`.

### J. Docs (Task 9)

Tables/REFCARD/mkdocs now list **28** commands. Group the four under a "Quality"
heading adjacent to the dev-cycle list. CHANGELOG `[2.1.0]` Added section gains
the four quality commands.

---

## Self-Review (completed by plan author)

- **Spec coverage:** all 7 commands + `r:check` retrofit (Tasks 6-7), `lib/rcmd.py` with JSON-not-regex + fallback (Tasks 1-5), engine-missing degradation incl. optional covr/pkgdown (Task 5), hook interaction noted in `document.md` (Task 7), testing both gates + R-free CI (Tasks 1-5,10), docs/version/.STATUS (Tasks 8-9). ✅
- **Placeholder scan:** no TBD/TODO; every code step shows full code. ✅
- **Type consistency:** envelope keys (`check`/`tests`/`coverage`/`build`/`site`/`install`, `engine_missing`, `messages`, `status`) used identically across `normalize` (Task 2), `run` (Task 5), and all command render specs (Tasks 6-7). `_invoke_r` is the single mock seam used by tests. `r_snippet` excludes `install` (handled by `_install_package`) — consistent with Task 4 note and Task 5 `run()`. ✅

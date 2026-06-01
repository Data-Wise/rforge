# R Dev-Cycle + Quality Commands Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **This is the consolidated plan** (addenda folded in 2026-05-31). It is the single source of truth — no superseding sections.

**Goal:** Add a full R package dev cycle **and** a quality layer to the rforge plugin's `r:` namespace — 12 new commands backed by one structured-output module `lib/rcmd.py`. Total commands 16 → **28**.

**Architecture:** Each command is a `commands/r/<verb>.md` prompt that shells out to `python3 -m lib.rcmd --kind <kind>`. `lib/rcmd.py` runs the *lower-level* R engine for that kind (`rcmdcheck`, `pkgbuild`, `roxygen2`, `testthat`, `pkgload`, `covr`, `pkgdown`, `lintr`, `spelling`, `urlchecker`, `styler` — **never** `devtools`), which serializes its structured result to JSON via `jsonlite`; Python normalizes that into one envelope. R output is JSON, never regex-scraped (console regex is a documented fallback only). CI stays R-free by mocking `Rscript`.

**Tech Stack:** Python 3 (stdlib only), R 4.x with the engine packages above + `jsonlite`, pytest, rforge's `commands/*.md` + `lib/` conventions.

**Spec:** `docs/specs/SPEC-r-dev-commands-2026-05-31.md`

---

## The 12 new commands (+ `r:check` retrofit)

| Kind | Command | Engine | Status rule |
|------|---------|--------|-------------|
| `load` | `r:load` | `pkgload::load_all()` | ok if exit 0 |
| `document` | `r:document` | `roxygen2::roxygenize()` | ok if exit 0 |
| `test` | `r:test` | `testthat::test_local(load_package="source")` | error if failed/exit≠0; warn if skip/warn |
| `check` | `r:check` *(retrofit)* | `rcmdcheck::rcmdcheck(error_on="never")` | error if errors; warn if warnings/notes |
| `coverage` | `r:coverage` | `covr::package_coverage` + `coverage_to_list` + `zero_coverage` | always ok (advisory) |
| `build` | `r:build` | `pkgbuild::build()` | ok if exit 0 |
| `install` | `r:install` | `R CMD INSTALL` (Python) | ok if exit 0 |
| `site` | `r:site` | `pkgdown::pkgdown_sitrep` → `build_site`; flags below | error if build fails; warn if problems |
| `cycle` | `r:cycle` | document→test→check (reuses `run()`) | worst of stages |
| `lint` | `r:lint` | `lintr::lint_package()` | warn if any lints |
| `spell` | `r:spell` | `spelling::spell_check_package()` | warn if any misspellings |
| `urlcheck` | `r:urlcheck` | `urlchecker::url_check()` | warn if any broken |
| `style` | `r:style` | `styler::style_pkg()` (mutates → show git diff) | ok if exit 0 |

`r:site` flags: `--preview` (`preview_site()`), `--strict` (`check_pkgdown()` fail-fast / CI), `--articles-only` (`build_articles()`, reinstall first), `--devel` (`load_all`, fast).

---

## Pre-flight (read before starting)

- **You are in the worktree** `~/.git-worktrees/rforge/feature-r-dev-commands` on branch `feature/r-dev-commands`. Verify: `git branch --show-current`.
- **Run lib as a package:** `python3 -m lib.rcmd ...` — never `python3 lib/rcmd.py`.
- **Mirror conventions:** read `commands/r/check.md` (command shape) and `lib/status.py` (lib module shape) first.
- **Engines:** required `rcmdcheck`/`pkgbuild`/`roxygen2`/`testthat`/`jsonlite` (`pkgload` rides along with testthat). Optional, degrade to 🟡 + install hint: `covr`/`pkgdown`/`lintr`/`spelling`/`urlchecker`/`styler`. System dep `pandoc` for `r:site` vignettes.
- **Gates (must pass before PR):** `python3 -m pytest tests/` and `bash tests/test-all.sh`.
- **Commits:** conventional + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Do NOT touch** the rename stubs `commands/{doc-check,ecosystem-health,rpkg-check}.md`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `lib/rcmd.py` (create) | Locate package; per-kind R snippet; run `Rscript`; normalize JSON → envelope; status; console fallback; graceful degradation; cycle orchestration; install |
| `tests/test_rcmd.py` (create) | Unit tests for every function; R subprocess mocked |
| `commands/r/check.md` (modify) | Retrofit onto `lib.rcmd --kind check` |
| `commands/r/{load,build,test,document,install,coverage,site,cycle,lint,spell,urlcheck,style}.md` (create) | One prompt per kind |
| `docs/reference/rcmd.md` (generate) | Auto-generated lib reference |
| `README.md`, `docs/index.md`, `docs/REFCARD.md` (modify) | Command tables + 16→28 count |
| `mkdocs.yml` (modify) | Nav entries |
| `CHANGELOG.md` (modify) | `[Unreleased]` → `[2.1.0]` |
| 4 version sources + doc refs (modify) | Bump to 2.1.0 |
| `tests/test-all.sh` (modify) | `lib.rcmd` CLI smoke check |
| `.STATUS` (modify) | Feature entry; Phase 4 → v2.2.0 |

---

## Task 1: `lib/rcmd.py` — package locator (TDD)

**Files:** Create `lib/rcmd.py`; Test `tests/test_rcmd.py`

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
        textwrap.dedent(f"Package: {name}\nVersion: {version}\nTitle: Test\n")
    )
    return tmp_path


def test_find_package_reads_description(tmp_path):
    _write_desc(tmp_path, "mypkg", "1.4.0")
    assert rcmd.find_package(str(tmp_path)) == {"package": "mypkg", "version": "1.4.0"}


def test_find_package_missing_returns_none(tmp_path):
    assert rcmd.find_package(str(tmp_path)) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_rcmd.py -v` → FAIL (`No module named 'lib.rcmd'`).

- [ ] **Step 3: Implement**

```python
# lib/rcmd.py
"""Run R package dev-cycle + quality engines and normalize output to one JSON envelope.

Each "kind" maps to a lower-level R package (NOT devtools):
  load->pkgload | document->roxygen2 | test->testthat | check->rcmdcheck
  coverage->covr | build->pkgbuild | install->R CMD INSTALL | site->pkgdown
  lint->lintr | spell->spelling | urlcheck->urlchecker | style->styler

The R subprocess emits JSON via jsonlite; this module normalizes it. Console
regex parsing is only a fallback when jsonlite/structured output is absent.

Usage: python3 -m lib.rcmd --kind <kind> [--path .] [--as-cran]
       [--preview] [--strict] [--articles-only] [--devel]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

OPTIONAL_ENGINES = {"covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler"}
INSTALL_HINT = {
    p: f'install.packages("{p}")'
    for p in ("rcmdcheck", "pkgbuild", "roxygen2", "testthat", "pkgload",
              "covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler",
              "jsonlite")
}


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

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rcmd.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): package locator from DESCRIPTION

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `normalize()` + status for all kinds (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_rcmd.py
def test_normalize_check_clean_ok():
    env = rcmd.normalize("check", {"errors": [], "warnings": [], "notes": []}, 0,
                         {"package": "foo", "version": "1.0"})
    assert env["status"] == "ok" and env["package"] == "foo"


def test_normalize_check_notes_warn():
    assert rcmd.normalize("check", {"notes": ["n"]}, 0, None)["status"] == "warn"


def test_normalize_check_errors_error():
    assert rcmd.normalize("check", {"errors": ["e"]}, 1, None)["status"] == "error"


def test_normalize_test_failures_error():
    env = rcmd.normalize("test", {"passed": 40, "failed": 2, "skipped": 1,
                                  "warnings": 0, "failing_files": ["t-a.R"]}, 1, None)
    assert env["status"] == "error" and env["tests"]["failing_files"] == ["t-a.R"]


def test_normalize_coverage_includes_untested():
    raw = {"total_pct": 80.0, "per_file": {"R/a.R": 50.0},
           "untested": [{"file": "R/a.R", "first_line": 3, "last_line": 7}]}
    env = rcmd.normalize("coverage", raw, 0, None)
    assert env["status"] == "ok"
    assert env["coverage"]["untested"][0]["first_line"] == 3


@pytest.mark.parametrize("kind,key", [("lint", "lints"), ("spell", "misspelled"),
                                      ("urlcheck", "broken")])
def test_normalize_quality_warns_when_findings(kind, key):
    assert rcmd.normalize(kind, {key: [{"x": 1}]}, 0, None)["status"] == "warn"
    assert rcmd.normalize(kind, {key: []}, 0, None)["status"] == "ok"


def test_normalize_style_ok_on_exit0():
    assert rcmd.normalize("style", {"changed_files": ["R/a.R"]}, 0, None)["status"] == "ok"


def test_normalize_engine_missing_error():
    env = rcmd.normalize("site", {"engine_missing": ["pkgdown"]}, 1, None)
    assert env["status"] == "error" and env["engine_missing"] == ["pkgdown"]
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_rcmd.py -k normalize -v` → FAIL (no `normalize`).

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py
_QUALITY_KEY = {"lint": "lints", "spell": "misspelled", "urlcheck": "broken"}


def _status_for(kind: str, raw: dict, exit_code: int) -> str:
    if raw.get("engine_missing"):
        return "error"
    if kind == "check":
        if raw.get("errors"):
            return "error"
        return "warn" if (raw.get("warnings") or raw.get("notes")) else "ok"
    if kind == "test":
        if raw.get("failed") or exit_code != 0:
            return "error"
        return "warn" if (raw.get("warnings") or raw.get("skipped")) else "ok"
    if kind == "site":
        if exit_code != 0 or not raw.get("built", True):
            return "error"
        return "warn" if raw.get("problems") else "ok"
    if kind == "coverage":
        return "ok"  # advisory; untested lines surfaced, never "error"
    if kind in _QUALITY_KEY:
        return "warn" if raw.get(_QUALITY_KEY[kind]) else "ok"
    # load, document, install, build, style: success == exit 0
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
        env["tests"] = {k: raw.get(k, 0) for k in
                        ("passed", "failed", "skipped", "warnings")}
        env["tests"]["failing_files"] = raw.get("failing_files", [])
    elif kind == "coverage":
        env["coverage"] = {"total_pct": raw.get("total_pct"),
                           "per_file": raw.get("per_file", {}),
                           "untested": raw.get("untested", [])}
    elif kind == "build":
        env["build"] = {"artifact": raw.get("artifact"), "bytes": raw.get("bytes")}
    elif kind == "site":
        env["site"] = {"checked": raw.get("checked", False),
                       "built": raw.get("built", False),
                       "problems": raw.get("problems", [])}
    elif kind == "install":
        env["install"] = {"installed_version": raw.get("installed_version"),
                          "exit": exit_code}
    elif kind == "lint":
        env["lint"] = {"count": len(raw.get("lints", [])), "lints": raw.get("lints", [])}
    elif kind == "spell":
        env["spell"] = {"count": len(raw.get("misspelled", [])),
                        "misspelled": raw.get("misspelled", [])}
    elif kind == "urlcheck":
        env["urlcheck"] = {"count": len(raw.get("broken", [])),
                           "broken": raw.get("broken", [])}
    elif kind == "style":
        env["style"] = {"count": len(raw.get("changed_files", [])),
                        "changed_files": raw.get("changed_files", [])}
    # load: no extra block — status carries the result
    return env
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_rcmd.py -k normalize -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): normalize all kinds into common envelope

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `console_fallback()` (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_console_fallback_testthat():
    raw = rcmd.console_fallback("test", "[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]\n")
    assert raw == {"failed": 2, "warnings": 0, "skipped": 1, "passed": 41}


def test_console_fallback_rcmdcheck():
    raw = rcmd.console_fallback("check", "0 errors v | 1 warning x | 2 notes x\n")
    assert len(raw["errors"]) == 0 and len(raw["warnings"]) == 1 and len(raw["notes"]) == 2


def test_console_fallback_unknown_returns_messages():
    assert "messages" in rcmd.console_fallback("test", "nothing here")
```

- [ ] **Step 2: Run → FAIL** (`python3 -m pytest tests/test_rcmd.py -k console -v`).

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py
def console_fallback(kind: str, text: str) -> dict:
    """Best-effort parse when JSON is unavailable.
    testthat: '[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]'
    rcmdcheck: '0 errors X | 1 warning Y | 2 notes Z'
    """
    if kind == "test":
        m = re.search(r"FAIL\s+(\d+)\s*\|\s*WARN\s+(\d+)\s*\|\s*"
                      r"SKIP\s+(\d+)\s*\|\s*PASS\s+(\d+)", text)
        if m:
            return {"failed": int(m[1]), "warnings": int(m[2]),
                    "skipped": int(m[3]), "passed": int(m[4])}
    if kind == "check":
        m = re.search(r"(\d+)\s+errors?\b.*?(\d+)\s+warnings?\b.*?(\d+)\s+notes?\b",
                      text, re.IGNORECASE | re.DOTALL)
        if m:
            return {"errors": [""] * int(m[1]), "warnings": [""] * int(m[2]),
                    "notes": [""] * int(m[3])}
    return {"messages": [ln for ln in text.splitlines() if ln.strip()][-10:]}
```

- [ ] **Step 4: Run → PASS.**

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): console-output fallback parser

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `r_snippet()` — per-kind R source (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

> `install` is NOT in `r_snippet` — it runs `R CMD INSTALL` from Python (Task 5).
> `load` has its own snippet. Signature carries the `r:site` flags.

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
@pytest.mark.parametrize("kind,needle", [
    ("check", "rcmdcheck::rcmdcheck"), ("build", "pkgbuild::build"),
    ("document", "roxygen2::roxygenize"), ("test", "testthat::test_local"),
    ("coverage", "covr::package_coverage"), ("site", "pkgdown::build_site"),
    ("load", "pkgload::load_all"), ("lint", "lintr::lint_package"),
    ("spell", "spelling::spell_check_package"), ("urlcheck", "urlchecker::url_check"),
    ("style", "styler::style_pkg"),
])
def test_r_snippet_uses_lower_level_engine(kind, needle):
    src = rcmd.r_snippet(kind, "/tmp/foo")
    assert needle in src and "jsonlite::toJSON" in src and "devtools::" not in src


def test_r_snippet_check_as_cran():
    src = rcmd.r_snippet("check", "/tmp/foo", as_cran=True)
    assert "--as-cran" in src and 'error_on = "never"' in src


def test_r_snippet_test_uses_load_package_source():
    assert 'load_package="source"' in rcmd.r_snippet("test", "/tmp/foo")


def test_r_snippet_coverage_uses_zero_coverage():
    assert "zero_coverage" in rcmd.r_snippet("coverage", "/tmp/foo")


def test_r_snippet_site_flags():
    assert "preview_site" in rcmd.r_snippet("site", "/tmp/f", preview=True)
    assert "preview_site" not in rcmd.r_snippet("site", "/tmp/f")
    assert "check_pkgdown" in rcmd.r_snippet("site", "/tmp/f", strict=True)
    assert "pkgdown_sitrep" in rcmd.r_snippet("site", "/tmp/f")  # default
    assert "build_articles" in rcmd.r_snippet("site", "/tmp/f", articles_only=True)
```

- [ ] **Step 2: Run → FAIL** (no `r_snippet`).

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py
def _guard(pkg_name: str, body: str) -> str:
    """Prefix that emits engine_missing JSON if the package or jsonlite is absent."""
    return (
        f'if (!requireNamespace("{pkg_name}", quietly=TRUE) || '
        f'!requireNamespace("jsonlite", quietly=TRUE)) {{'
        f'cat(\'{{"engine_missing":["{pkg_name}"]}}\'); quit(status=0)}}; ' + body
    )


def r_snippet(kind: str, path: str, *, as_cran: bool = False, preview: bool = False,
              strict: bool = False, articles_only: bool = False,
              devel: bool = False) -> str:
    p = json.dumps(path)  # safely quote path for R
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
        return _guard("roxygen2", f'roxygen2::roxygenize({p}); cat(\'{{"documented":true}}\')')
    if kind == "load":
        return _guard("pkgload", f'pkgload::load_all({p}); cat(\'{{"loaded":true}}\')')
    if kind == "test":
        return _guard("testthat",
            f'res <- testthat::test_local({p}, load_package="source", '
            f'reporter="list", stop_on_failure=FALSE); df <- as.data.frame(res); '
            f'cat(jsonlite::toJSON(list(passed=sum(df$passed), failed=sum(df$failed), '
            f'skipped=sum(df$skipped), warnings=sum(df$warning), '
            f'failing_files=unique(df$file[df$failed>0 | df$error>0])), auto_unbox=TRUE))')
    if kind == "coverage":
        return _guard("covr",
            f'cv <- covr::package_coverage({p}); l <- covr::coverage_to_list(cv); '
            f'z <- covr::zero_coverage(cv); '
            f'untested <- if (nrow(z)) {{ag <- stats::aggregate(line ~ filename, z, '
            f'function(x) c(first=min(x), last=max(x))); lapply(seq_len(nrow(ag)), '
            f'function(i) list(file=ag$filename[i], '
            f'first_line=as.integer(ag$line[i,"first"]), '
            f'last_line=as.integer(ag$line[i,"last"])))}} else list(); '
            f'cat(jsonlite::toJSON(list(total_pct=covr::percent_coverage(cv), '
            f'per_file=as.list(l$filecoverage), untested=untested), '
            f'auto_unbox=TRUE, null="list"))')
    if kind == "site":
        prev = f'pkgdown::preview_site({p}); ' if preview else ''
        gate = (f'pkgdown::check_pkgdown({p}); ' if strict
                else f'probs <- paste(utils::capture.output('
                     f'pkgdown::pkgdown_sitrep({p})), collapse="\\n"); ')
        build = (f'pkgdown::build_articles({p}, preview=FALSE)' if articles_only
                 else f'pkgdown::build_site({p}, preview=FALSE, new_process=TRUE, '
                      f'quiet=TRUE, devel={"TRUE" if devel else "FALSE"})')
        probs = 'character()' if strict else 'if (exists("probs")) probs else ""'
        return _guard("pkgdown",
            f'{gate}{build}; {prev}'
            f'cat(jsonlite::toJSON(list(checked=TRUE, built=TRUE, '
            f'problems=as.list({probs})), auto_unbox=TRUE, null="list"))')
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
        # NOTE: verify column names with names(urlchecker::url_check(".")) — vary by version
        return _guard("urlchecker",
            f'u <- urlchecker::url_check({p}); '
            f'cat(jsonlite::toJSON(list(broken=lapply(seq_len(nrow(u)), '
            f'function(i) list(url=u$URL[i], message=u$message[i], '
            f'new_url=u$newURL[i]))), auto_unbox=TRUE, null="list"))')
    if kind == "style":
        return _guard("styler",
            f'res <- styler::style_pkg({p}); '
            f'cat(jsonlite::toJSON(list(changed_files='
            f'as.list(res$file[res$changed %in% TRUE])), auto_unbox=TRUE, null="list"))')
    raise ValueError(f"unknown kind: {kind}")
```

- [ ] **Step 4: Run → PASS** (`python3 -m pytest tests/test_rcmd.py -k snippet -v`).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): per-kind R snippets (lower-level engines, JSON out)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `run()`, `main()`, cycle, install (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_run_check_happy(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.2.0")
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ('{"errors":[],"warnings":["W"],"notes":[]}', 0))
    env = rcmd.run("check", str(tmp_path))
    assert env["status"] == "warn" and env["package"] == "foo"
    assert env["check"]["warnings"] == ["W"]


def test_run_no_description_error(tmp_path):
    env = rcmd.run("check", str(tmp_path))
    assert env["status"] == "error" and "detect" in " ".join(env["messages"]).lower()


def test_run_falls_back_on_nonjson(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r",
                        lambda s: ("[ FAIL 1 | WARN 0 | SKIP 0 | PASS 9 ]", 1))
    env = rcmd.run("test", str(tmp_path))
    assert env["tests"]["failed"] == 1 and env["status"] == "error"


def test_run_optional_engine_missing_downgrades_to_warn(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"engine_missing":["pkgdown"]}', 0))
    env = rcmd.run("site", str(tmp_path))
    assert env["status"] == "warn"  # optional engine → warn, not error
    assert any("pkgdown" in m for m in env["messages"])


def test_cycle_stops_on_first_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    calls = []
    def fake_run(kind, path, **kw):
        calls.append(kind)
        return {"kind": kind, "status": "error" if kind == "test" else "ok",
                "engine_missing": [], "messages": []}
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cycle(str(tmp_path))
    assert env["failed_stage"] == "test" and calls == ["document", "test"]


def test_main_emits_json(tmp_path, monkeypatch, capsys):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"errors":[],"warnings":[],"notes":[]}', 0))
    rc = rcmd.main(["--kind", "check", "--path", str(tmp_path)])
    assert json.loads(capsys.readouterr().out)["status"] == "ok" and rc == 0
```

- [ ] **Step 2: Run → FAIL** (no `run`/`_invoke_r`/`main`).

- [ ] **Step 3: Implement**

```python
# add to lib/rcmd.py
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
    proc = subprocess.run([rbin, "CMD", "INSTALL", path], capture_output=True, text=True)
    return ({"installed_version": pkg.get("version")}, proc.returncode)


def run(kind: str, path: str = ".", *, as_cran: bool = False, preview: bool = False,
        strict: bool = False, articles_only: bool = False, devel: bool = False) -> dict:
    pkg = find_package(path)
    if pkg is None:
        return {"kind": kind, "status": "error", "engine_missing": [],
                "messages": ["No DESCRIPTION found — is this an R package? "
                             "Try /rforge:detect to locate packages."]}
    if kind == "install":
        raw, code = _install_package(path)
    else:
        if kind == "site" and articles_only:
            _install_package(path)  # standalone build_articles renders installed version
        snippet = r_snippet(kind, path, as_cran=as_cran, preview=preview,
                            strict=strict, articles_only=articles_only, devel=devel)
        stdout, code = _invoke_r(snippet)
        try:
            raw = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            raw = console_fallback(kind, stdout)
    env = normalize(kind, raw, code, pkg)
    for eng in env.get("engine_missing", []):
        if INSTALL_HINT.get(eng):
            env.setdefault("messages", []).append(f"Missing R package — run: {INSTALL_HINT[eng]}")
        if eng in OPTIONAL_ENGINES and env["status"] == "error":
            env["status"] = "warn"
    return env


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m lib.rcmd",
                                 description="Run an R dev-cycle/quality engine, emit JSON.")
    ap.add_argument("--kind", required=True,
                    choices=["load", "document", "test", "check", "coverage", "build",
                             "install", "site", "cycle", "lint", "spell", "urlcheck", "style"])
    ap.add_argument("--path", default=".")
    ap.add_argument("--as-cran", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--articles-only", action="store_true")
    ap.add_argument("--devel", action="store_true")
    ns = ap.parse_args(argv)
    if ns.kind == "cycle":
        env = _run_cycle(ns.path)
    else:
        env = run(ns.kind, ns.path, as_cran=ns.as_cran, preview=ns.preview,
                  strict=ns.strict, articles_only=ns.articles_only, devel=ns.devel)
    print(json.dumps(env, indent=2))
    return 0 if env.get("status") != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run full suite → PASS** (`python3 -m pytest tests/test_rcmd.py -v`, ~30 tests).

- [ ] **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): run/main CLI, cycle orchestration, install

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Retrofit `commands/r/check.md`

**Files:** Modify `commands/r/check.md` (keep frontmatter `name`/`arguments`; replace body)

- [ ] **Step 1: Replace body below frontmatter**

````markdown
# R Package Check

Run `R CMD check` (via `rcmdcheck`) and report structured results.

## Process

1. Resolve package path from `$ARGUMENTS` (default: current dir).
2. `python3 -m lib.rcmd --kind check --path "<path>"` (add `--as-cran` if requested).
3. Render the JSON envelope below. Do not re-run R yourself.

## Output Format

```markdown
## Package Check: {package} v{version}
### Status: {🟢 ok / 🟡 warn / 🔴 error}
### R CMD Check
- Errors: {len check.errors}
- Warnings: {len check.warnings}
- Notes: {len check.notes}
{list each message as a bullet, if any}
### Recommended Actions
{1-3 steps, or "None — package is clean ✅"}
```

If `engine_missing` is non-empty, report 🔴 with the install hint from `messages`.

## Related Commands
- `/rforge:r:cycle` — document → test → check in one pass
- `/rforge:thorough` — **ecosystem** rollup incl. R CMD check (this is **single-package**)
- `/rforge:docs:check` — documentation drift (complements R CMD check)
````

- [ ] **Step 2: Verify** `bash tests/test-all.sh 2>&1 | grep -iE "frontmatter|uniqueness"` → PASS.

- [ ] **Step 3: Commit**

```bash
git add commands/r/check.md
git commit -m "refactor(r:check): drive report from lib.rcmd envelope

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Create the 12 new command files

**Files:** Create under `commands/r/`. Each mirrors `check.md`: frontmatter (`name: rforge:r:<verb>`, `description`, `arguments`) + `## Process` calling `python3 -m lib.rcmd --kind <verb>` + `## Output Format` + `## Related Commands` (with boundary cross-links per the dedup audit).

> Full content for each is below. After creating all, run the gate in Step 13.

- [ ] **Step 1: `commands/r/load.md`**

````markdown
---
name: rforge:r:load
description: Load the package into a namespace (pkgload::load_all) for dev
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Load

Simulate-install the package into a namespace via `pkgload::load_all()`.

## Process
```bash
python3 -m lib.rcmd --kind load --path "<path>"
```

## Output Format
```markdown
## Load: {package} v{version}
### Status: {🟢/🔴}
{On success: "Loaded {package} into the namespace."}
{On error or engine_missing: surface messages}
```

## Related Commands
- `/rforge:r:test` — load happens automatically inside test_local
- `/rforge:r:document` — regenerate docs after changing exports
````

- [ ] **Step 2: `commands/r/document.md`**

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

> Blessed regeneration path. The PreToolUse hook blocks *hand-edits* to
> `man/*.Rd`; running roxygen via this command (Bash) is allowed.

## Process
```bash
python3 -m lib.rcmd --kind document --path "<path>"
```

## Output Format
```markdown
## Document: {package} v{version}
### Status: {🟢/🔴}
{On success: "Regenerated man/ and NAMESPACE."}
### Recommended Actions
- Review: `git diff man/ NAMESPACE`
```

## Related Commands
- `/rforge:r:check` — verify docs after regenerating
- `/rforge:docs:check` — **detect** doc drift across packages (this **regenerates**)
````

- [ ] **Step 3: `commands/r/test.md`**

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

Run the suite via `testthat::test_local()` (self-loads the package via pkgload).

## Process
```bash
python3 -m lib.rcmd --kind test --path "<path>"
```

## Output Format
```markdown
## Tests: {package} v{version}
### Status: {🟢 0 failed / 🟡 skips or warnings / 🔴 failures}
- Passed: {tests.passed}
- Failed: {tests.failed}
- Skipped: {tests.skipped}
- Warnings: {tests.warnings}
{If failing_files: list under "### Failing files"}
### Recommended Actions
{Next steps or "All green ✅"}
```

## Related Commands
- `/rforge:r:cycle` — document → test → check
- `/rforge:r:coverage` — which lines the tests miss
````

- [ ] **Step 4: `commands/r/coverage.md`**

````markdown
---
name: rforge:r:coverage
description: Test coverage (covr) — total, per-file, and untested lines
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Coverage

Compute coverage via `covr::package_coverage()` (+ `zero_coverage()` for gaps).
`covr` is optional — if `engine_missing` includes `covr`, report 🟡 + install hint.

## Process
```bash
python3 -m lib.rcmd --kind coverage --path "<path>"
```

## Output Format
```markdown
## Coverage: {package} v{version}
### Total: {coverage.total_pct}%
### Lowest-covered files
{Top 5 ascending from coverage.per_file: "- R/foo.R — 12.0%"}
### Untested lines
{From coverage.untested: "- R/foo.R:12-18"}
### Recommended Actions
{Point at untested ranges ("add tests for R/foo.R:12-18"), or "Healthy ✅"}
```

## Related Commands
- `/rforge:r:test` — run the tests behind the coverage
````

- [ ] **Step 5: `commands/r/build.md`**

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

Build a source tarball via `pkgbuild::build()`.

## Process
```bash
python3 -m lib.rcmd --kind build --path "<path>"
```

## Output Format
```markdown
## Build: {package} v{version}
### Status: {🟢/🔴}
- Artifact: `{build.artifact}`
- Size: {build.bytes / 1024} KB
```

## Related Commands
- `/rforge:r:check` — validate before building
- `/rforge:r:install` — install the built package
````

- [ ] **Step 6: `commands/r/install.md`**

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

Install via `R CMD INSTALL`.

## Process
```bash
python3 -m lib.rcmd --kind install --path "<path>"
```

## Output Format
```markdown
## Install: {package} v{version}
### Status: {🟢 exit 0 / 🔴}
- Installed version: {install.installed_version}
{On error: surface messages (e.g. unmet dependencies)}
```

## Related Commands
- `/rforge:r:build` — build before installing
````

- [ ] **Step 7: `commands/r/site.md`**

````markdown
---
name: rforge:r:site
description: Build the pkgdown website (vignettes→articles); optional preview
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: preview
    description: Open the built site (pkgdown::preview_site)
    required: false
    type: boolean
    default: false
  - name: strict
    description: Fail-fast config check (check_pkgdown) for CI
    required: false
    type: boolean
    default: false
  - name: articles-only
    description: Build only articles/vignettes (reinstalls first)
    required: false
    type: boolean
    default: false
  - name: devel
    description: Fast in-process build via load_all (lower fidelity)
    required: false
    type: boolean
    default: false
---

# R Package Website

Validate (`pkgdown_sitrep`, or `check_pkgdown` with `--strict`) then build the site.
`pkgdown` is optional — if `engine_missing` includes `pkgdown`, report 🟡 + hint.
Needs `pandoc` to render vignettes; if absent, report 🟡 with the pandoc hint.

## Process
```bash
python3 -m lib.rcmd --kind site --path "<path>"   # + --preview / --strict / --articles-only / --devel
```

## Output Format
```markdown
## Website: {package} v{version}
### Status: {🟢 built clean / 🟡 built with problems / 🔴 build failed}
- Checked: {site.checked} · Built: {site.built}
{If status 🔴: "### Vignette/render errors" — point at the failing .Rmd from messages}
{If site.problems: "### Config/index problems" — list each (url, un-indexed topics)}
### Recommended Actions
{Fix problems, or "Site built to docs/ ✅"}
```

## Related Commands
- `/rforge:r:document` — ensure Rd docs exist before building the site
````

- [ ] **Step 8: `commands/r/cycle.md`**

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
### Status: {🟢 all ok / 🟡 warnings / 🔴 failed}
| Stage | Result |
|-------|--------|
| document | {stages[0].status dot} |
| test | {stages[1].status dot} |
| check | {stages[2].status dot} |
{If failed_stage: "Stopped at **{failed_stage}** — {detail summary}"}
### Recommended Actions
{Next steps based on the failing stage}
```

## Related Commands
- `/rforge:r:check`, `/rforge:r:test`, `/rforge:r:document` — individual stages
- `/rforge:thorough` — **ecosystem** rollup (this is **single-package**)
````

- [ ] **Step 9: `commands/r/lint.md`**

````markdown
---
name: rforge:r:lint
description: Static analysis of the package (lintr) — grouped report
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Lint

Run `lintr::lint_package()` (read-only).
`lintr` is optional — if `engine_missing` includes `lintr`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind lint --path "<path>"
```

## Output Format
```markdown
## Lint: {package} v{version}
### Status: {🟢 0 lints / 🟡 {lint.count} lints}
{Group lint.lints by file: "R/foo.R:3 — object_name_linter: <message>"}
### Recommended Actions
{Top offenders to fix, or "Clean ✅"}
```

## Related Commands
- `/rforge:r:style` — auto-format (fixes many style lints)
````

- [ ] **Step 10: `commands/r/spell.md`**

````markdown
---
name: rforge:r:spell
description: Spell-check the package (spelling) and triage typos
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Spell Check

Run `spelling::spell_check_package()`.
`spelling` is optional — if `engine_missing` includes `spelling`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind spell --path "<path>"
```

## Output Format
```markdown
## Spell: {package} v{version}
### Status: {🟢 0 / 🟡 {spell.count} words}
{List spell.misspelled: "- teh (R/foo.R:3)"}
### Recommended Actions
{Real typos to fix vs words to add to `inst/WORDLIST`}
```

## Related Commands
- `/rforge:r:check` — spelling NOTEs also surface in R CMD check
````

- [ ] **Step 11: `commands/r/urlcheck.md`**

````markdown
---
name: rforge:r:urlcheck
description: Check package URLs for breakage/redirects (urlchecker)
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package URL Check

Run `urlchecker::url_check()` — a common CRAN rejection cause.
`urlchecker` is optional — if `engine_missing` includes it, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind urlcheck --path "<path>"
```

## Output Format
```markdown
## URL Check: {package} v{version}
### Status: {🟢 0 / 🟡 {urlcheck.count} URLs}
{List urlcheck.broken: "- http://x — <message> → suggested: <new_url>"}
### Recommended Actions
{Replace redirected URLs with suggestions, fix dead links}
```

## Related Commands
- `/rforge:r:check` — broken URLs also flagged by R CMD check
````

- [ ] **Step 12: `commands/r/style.md`**

````markdown
---
name: rforge:r:style
description: Auto-format the package (styler) and show the diff
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Style

Reformat source via `styler::style_pkg()`. **This rewrites files.**
`styler` is optional — if `engine_missing` includes `styler`, report 🟡 + hint.

## Process
1. `python3 -m lib.rcmd --kind style --path "<path>"`
2. Then show what changed: run `git -C "<path>" diff --stat` via Bash and summarize.

## Output Format
```markdown
## Style: {package} v{version}
### Status: {🟢 reformatted / 🔴}
- Files changed: {style.count}
{git diff --stat summary}
### Recommended Actions
- Review: `git diff` · Undo if unwanted: `git checkout -- <files>`
```

## Related Commands
- `/rforge:r:lint` — find issues that styler does **not** auto-fix
````

- [ ] **Step 13: Verify all parse + uniqueness**

Run: `bash tests/test-all.sh 2>&1 | tail -30`
Expected: frontmatter-valid, **command-name-uniqueness**, skills-valid all PASS.

- [ ] **Step 14: Commit**

```bash
git add commands/r/
git commit -m "feat(r): 12 dev-cycle + quality commands

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Reference docs + CI gen-check

**Files:** Generate `docs/reference/rcmd.md`; maybe modify `scripts/gen_lib_reference.py`

- [ ] **Step 1:** Read `scripts/gen_lib_reference.py`; if its public-module list is hardcoded (currently discovery/deps/status/init), add `rcmd`.
- [ ] **Step 2:** `python3 scripts/gen_lib_reference.py` → writes `docs/reference/rcmd.md`.
- [ ] **Step 3:** `python3 scripts/gen_lib_reference.py --check` → exit 0 (no drift).
- [ ] **Step 4: Commit**

```bash
git add scripts/gen_lib_reference.py docs/reference/rcmd.md
git commit -m "docs(rcmd): generate lib reference page

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Docs tables, nav, CHANGELOG, version bump

**Files:** `README.md`, `docs/index.md`, `docs/REFCARD.md`, `mkdocs.yml`, `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `package.json`, `.STATUS`

- [ ] **Step 1:** Add the 12 commands to every command table (`grep -rn "r:check" README.md docs/index.md docs/REFCARD.md`). Group the four quality commands under a "Quality" heading next to the dev-cycle list. Update any "16 commands" → **"28"**.
- [ ] **Step 2:** `mkdocs.yml` nav — add `docs/reference/rcmd.md` and command pages (mirror how `r:check`/`docs:check` are listed).
- [ ] **Step 3:** CHANGELOG — `[Unreleased]` → `## [2.1.0] - 2026-05-31`, "Added" listing all 12 commands + `lib/rcmd.py`.
- [ ] **Step 4:** Bump version to 2.1.0 in all 4 sources (`plugin.json` `version`; `marketplace.json` `metadata.version` AND `plugins[0].version`; `package.json` `version`) + live-version doc refs per CLAUDE.md (REFCARD header + ASCII box, docs/README.md, README.md tree comments, docs/index.md).
- [ ] **Step 5:** `grep -rn "2\.0\.0" --include='*.md' --include='*.json' . | grep -iv changelog` → no remaining live refs.
- [ ] **Step 6:** `.STATUS` — add "v2.1.0: r: dev-cycle + quality commands"; move Phase 4 (agents) → v2.2.0.
- [ ] **Step 7: Commit**

```bash
git add README.md docs/ mkdocs.yml CHANGELOG.md .claude-plugin/ package.json .STATUS
git commit -m "docs: command tables, nav, CHANGELOG; bump to v2.1.0

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Full gate + lib smoke check

**Files:** Modify `tests/test-all.sh`

- [ ] **Step 1:** Add a `lib.rcmd` CLI smoke line mirroring the existing discovery/deps/status/init smoke lines: assert `python3 -m lib.rcmd --kind check --path tests/fixtures/<pkg>` prints parseable JSON and exits cleanly. Keep CI R-free — with R absent the module emits an `engine_missing`/`error` envelope; assert the JSON parses either way. Create a minimal `tests/fixtures/<pkg>/DESCRIPTION` if none exists.
- [ ] **Step 2:** Run both gates:

```bash
python3 -m pytest tests/ -v          # 65 existing + ~30 new
bash tests/test-all.sh                # prior 29 + new smoke
```
Both green; fix anything red.

- [ ] **Step 3: Commit**

```bash
git add tests/test-all.sh tests/fixtures/
git commit -m "test: lib.rcmd CLI smoke check in test-all.sh

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: Live sanity (optional, needs R) + PR

- [ ] **Step 1:** If R is available, spot-check against a real package:

```bash
python3 -m lib.rcmd --kind check    --path ~/projects/r-packages/<pkg>
python3 -m lib.rcmd --kind test     --path ~/projects/r-packages/<pkg>
python3 -m lib.rcmd --kind coverage --path ~/projects/r-packages/<pkg>
python3 -m lib.rcmd --kind lint     --path ~/projects/r-packages/<pkg>
```
(covr/pkgdown/lintr may report `engine_missing` — expected.)

- [ ] **Step 2:** Final gate + PR to dev:

```bash
git fetch origin dev && git rebase origin/dev
python3 -m pytest tests/ && bash tests/test-all.sh
gh pr create --base dev --title "feat: r: dev-cycle + quality commands (v2.1.0)" \
  --body "Implements docs/specs/SPEC-r-dev-commands-2026-05-31.md. 12 r: commands backed by lib/rcmd.py (structured JSON from rcmdcheck/pkgbuild/roxygen2/testthat/pkgload/covr/pkgdown/lintr/spelling/urlchecker/styler). 16→28 commands. Ships v2.1.0."
```

- [ ] **Step 3:** After merge — delete `ORCHESTRATE-r-dev-commands.md` (per CLAUDE.md), then `git worktree remove ~/.git-worktrees/rforge/feature-r-dev-commands`.

---

## Self-Review (completed by plan author)

- **Spec coverage:** all 12 commands + `r:check` retrofit (Tasks 6-7); `lib/rcmd.py` JSON-not-regex + fallback + cycle + install (Tasks 1-5); coverage untested lines (Tasks 2,4,7); site flags + vignette-error classification (Tasks 4-5,7); quality commands with optional-engine degrade (Tasks 2,4,5,7); dedup boundaries cross-linked in command files (Tasks 6-7); both gates, R-free CI (Tasks 1-5,10); docs/version/.STATUS (Tasks 8-9). ✅
- **Placeholder scan:** no TBD/TODO; every code step shows full code. (One explicit verify-step: `urlchecker` column names in Task 4 — flagged, not a placeholder.) ✅
- **Type consistency:** envelope keys (`check/tests/coverage/build/site/install/lint/spell/urlcheck/style`, `engine_missing`, `messages`, `status`) identical across `normalize` (Task 2), `run` (Task 5), and all command renders (Tasks 6-7). `_invoke_r` is the single test mock seam. `r_snippet` excludes `install` (Python `_install_package`) and includes `load` — consistent across Tasks 4-5. `r:site` kwargs (`strict/articles_only/devel/preview`) threaded identically through `r_snippet`→`run`→`main` (Tasks 4-5). `_run_cycle` reuses `run()` (no duplicated stage logic). ✅
- **No duplicates:** no name collisions (only `r:check` retrofit); functional boundaries cross-linked (check/cycle↔thorough, document↔docs:check); stubs untouched. ✅

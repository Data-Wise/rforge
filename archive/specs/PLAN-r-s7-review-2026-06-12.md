# `r:s7-review` — S7 Convention Checker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL — use `superpowers:subagent-driven-development` (or `superpowers:executing-plans`) to execute this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Every code step shows COMPLETE code — paste verbatim, no `TODO`/placeholder filling required.

**Goal:** Ship `r:s7-review`, a new command backed by a new public pure-stdlib module `lib/s7review.py` that statically polices S7 OOP conventions (5 check families) across an R package. Advisory-only, `cranlint.py` archetype: byte-identical envelope, warn-only, exit 0 always, `engine_missing` always `[]`, stdlib-only imports. Command count `35 → 36`.

**Architecture:** A pure-stdlib static analyser over `R/*.R` plus `NAMESPACE`. `_find_s7_constructs(text)` does call-name + balanced-paren extraction of `new_class()`/`new_generic()`/`method()`; five `check_*(path)` functions emit advisory findings; `run_all(path)` rolls them into a worst-of (`ok < warn`) envelope. The docs family parses `export()`/`@export` (see Task 6 note — **a NEW parser, mirroring `deps_sync`'s `importFrom` precedent, not a reused export parser, because none exists**). `--eco` is **deferred** (see Decisions). TDD throughout: write a failing fixture test → run it (fails) → implement → run it (passes) → commit.

**Tech Stack:** Python 3 stdlib only (`argparse`/`json`/`os`/`re`/`sys`/`pathlib`); pytest for `tests/test_s7review.py`; Bash for the `tests/test-all.sh` smoke line; Markdown + YAML frontmatter for the command file.

**Spec:** `docs/specs/SPEC-r-s7-review-2026-06-12.md`

---

## Decisions (resolving the spec's two Open Questions)

This plan **resolves both open questions to keep v1 bounded** — reflect these when executing:

1. **`--eco` consistency checks (`divergent_class_def`, `inconsistent_prop_type`) → DEFERRED.** Open Question 1 (what defines the mediationverse house convention) is **unresolved**, so per the spec's own gate ("`--eco` ships only if Open Question 1 resolves") we do **not** build `review_ecosystem()` or wire `--eco` in v1. The command file declares no `--eco` flag. `discovery.find_r_packages()` is therefore **not** a dependency in v1. A one-paragraph "Deferred" note goes in the command file + CHANGELOG so the intent is recorded. *(If the house-convention spec lands later, `--eco` is an additive follow-up: add `review_ecosystem(root)` + the `--eco` flag, no envelope break, since findings already carry `source: "static"`.)*

2. **`missing_methods_register` aggressiveness → SHIP AS A QUIET ADVISORY.** It is implemented in `check_methods` but only fires when a `method()` call targets a generic that is **neither defined nor imported** in scanned source AND no `methods_register(` call appears anywhere in `R/` — the narrowest, lowest-false-positive form. Message is worded "looks like … consider", severity `advisory`. The runtime-confirmed version stays deferred to the R-backed v2 sibling.

Both decisions are conservative (`--eco` out, `missing_methods_register` quiet) — they shrink surface, not grow it.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `lib/s7review.py` | **Create** | The engine: `_scan_r_files`, `_find_s7_constructs`, `_envelope`, `_S7_VOCAB`, 5 `check_*`, `run_all`, `_main` CLI. |
| `tests/fixtures/s7pkg.bad/` | **Create** | Deliberately-bad S7 fixture package (DESCRIPTION, NAMESPACE, `R/*.R`) triggering ≥1 code per family. |
| `tests/fixtures/s7pkg.clean/` | **Create** | Clean S7 fixture package — `run_all` returns `ok`, zero findings. |
| `tests/test_s7review.py` | **Create** | pytest cases: per-family code assertions + envelope contract (`status ∈ {ok,warn}`, `engine_missing == []`, exit 0, advisory severity). |
| `commands/r/s7-review.md` | **Create** | Command file, `name: rforge:r:s7-review`, frontmatter `arguments:` synced with `## Usage`. No `--write`/`--eco`. |
| `scripts/gen_lib_reference.py` | **Modify** | Add `"lib.s7review"` to `MODULES`. |
| `docs/reference/s7review.md` | **Create (auto-gen)** | Produced by `gen_lib_reference.py`; committed; CI `--check` gate. |
| `tests/test-all.sh` | **Modify** | Add `lib_s7review_smoke()` helper + `run` registration. |
| `package.json` | **Modify** | Version `2.8.0 → 2.9.0` (source of truth) + description command count `35 → 36`. |
| `.claude-plugin/plugin.json` | **Modify** (via `version_sync.py`) | version + `36 commands` in description. |
| `.claude-plugin/marketplace.json` | **Modify** (manual) | `metadata.version` + `plugins[0].version` → 2.9.0. |
| `mkdocs.yml` | **Modify** (via `version_sync.py`) | `extra.rforge.version`; **manually** bump `extra.rforge.command_count` `35 → 36`. |
| `README.md` | **Modify** (via `version_sync.py`) | footer + tagline version/count. |
| `CLAUDE.md` | **Modify** | Add `s7review` to public-modules list; bump command-count heading; test-gate counts; "Current state". |
| `CHANGELOG.md` | **Modify** | `[Unreleased]` → `[2.9.0] - <ship date>`; Added section. |
| `.STATUS` | **Modify** | version + roadmap. |

> **Version note:** the spec says "post-v2.9.0" but Phase 4 (PLAN-phase4-orchestrator-rewrite) targets `2.9.0`. Before bumping, check `package.json`: if it already reads `2.9.0` (Phase 4 shipped), this feature is `2.10.0`. **This plan writes `2.9.0` as the placeholder; substitute the actual `current + 1 minor` at Task 8.** The command-count change (`35 → 36`) is invariant regardless of version.

---

## Task 0: Create the feature worktree

`lib/s7review.py`, the command file, and the fixtures are **new code files** — blocked on `dev` by branch-guard. All work happens in a worktree.

- [ ] **Step 1: Create the worktree from `dev`**

```bash
git worktree add ~/.git-worktrees/rforge/feature-r-s7-review -b feature/r-s7-review dev
```

- [ ] **Step 2: Confirm location and branch**

```bash
cd ~/.git-worktrees/rforge/feature-r-s7-review
git branch --show-current   # expect: feature/r-s7-review
pwd
```

Expected: branch is `feature/r-s7-review`; **all subsequent paths in this plan are relative to this worktree root.**

---

## Task 1: Fixture packages (bad + clean)

**Files:** Create `tests/fixtures/s7pkg.bad/{DESCRIPTION,NAMESPACE,R/classes.R,R/legacy.R}` and `tests/fixtures/s7pkg.clean/{DESCRIPTION,NAMESPACE,R/classes.R}`.

Fixtures are the test substrate; build them first so every later family test has something to assert against. The **bad** fixture deliberately trips ≥1 code in each of the 5 families; the **clean** fixture trips none.

- [ ] **Step 1: Write the bad fixture DESCRIPTION**

`tests/fixtures/s7pkg.bad/DESCRIPTION`:

```
Package: s7bad
Title: Deliberately Non-Idiomatic S7 Fixture
Version: 0.0.1
Description: A fixture package that violates S7 conventions on purpose.
Authors@R: person("Test", "User", email = "t@example.com", role = c("aut", "cre", "cph"))
License: MIT
Encoding: UTF-8
```

- [ ] **Step 2: Write the bad fixture NAMESPACE**

`tests/fixtures/s7pkg.bad/NAMESPACE` (exports a class that has no `#'` doc block → `undocumented_export`):

```
export(undocumented_class)
export(mediator_summary)
```

- [ ] **Step 3: Write the bad fixture `R/classes.R`**

`tests/fixtures/s7pkg.bad/R/classes.R` — covers naming, validators, methods, docs:

```r
# class name snake_case (bad) -> class_name_case
mediator_model <- new_class("mediator_model",
  properties = list(
    n_obs = class_numeric,
    BadProp = class_character   # prop name not snake_case -> prop_name_case
  )
)
# NOTE: no validator= on a typed-properties class -> missing_validator

# bound var name does not match the name= string -> class_name_mismatch
Estimator <- new_class("Estimater", properties = list(value = class_numeric))

# generic name UpperCamelCase (bad) -> generic_name_case
ComputeEffect <- new_generic("ComputeEffect", "x")

# exported but undocumented (NAMESPACE export(undocumented_class)) -> undocumented_export
undocumented_class <- new_class("UndocumentedClass")

# property type that does not resolve in scanned source -> prop_type_unresolvable
TypedThing <- new_class("TypedThing",
  properties = list(ref = NoSuchClass)
)

# validator that returns TRUE/FALSE instead of character()/NULL -> validator_return_shape
Validated <- new_class("Validated",
  properties = list(x = class_numeric),
  validator = function(self) {
    return(TRUE)
  }
)

# method() on a generic not defined/imported here + no methods_register() anywhere
# -> dangling_method AND missing_methods_register
method(external_generic, mediator_model) <- function(x, ...) x
```

- [ ] **Step 4: Write the bad fixture `R/legacy.R`**

`tests/fixtures/s7pkg.bad/R/legacy.R` — covers the legacy family (S4/R5/S3 co-residing with S7):

```r
# S4 leftovers co-residing with new_class -> legacy_s4_in_s7
setClass("OldThing", representation(a = "numeric"))
setGeneric("oldGen", function(x) standardGeneric("oldGen"))

# R5 / R6 leftover -> legacy_r5_in_s7
Counter <- R6::R6Class("Counter", public = list(n = 0))

# S3 generic dispatching (heuristic) -> legacy_s3_generic
print.mediator_model <- function(x, ...) {
  UseMethod("print")
}
```

- [ ] **Step 5: Write the clean fixture**

`tests/fixtures/s7pkg.clean/DESCRIPTION`:

```
Package: s7clean
Title: Idiomatic S7 Fixture
Version: 0.0.1
Description: A fixture package that follows S7 conventions.
Authors@R: person("Test", "User", email = "t@example.com", role = c("aut", "cre", "cph"))
License: MIT
Encoding: UTF-8
```

`tests/fixtures/s7pkg.clean/NAMESPACE`:

```
export(MediatorModel)
```

`tests/fixtures/s7pkg.clean/R/classes.R` (documented export, UpperCamelCase class, snake_case props + generic, validator returns `character()`, in-scope generic & prop types, `methods_register()` present):

```r
#' A mediator model
#'
#' @export
MediatorModel <- new_class("MediatorModel",
  properties = list(
    n_obs = class_numeric,
    label = class_character
  ),
  validator = function(self) {
    if (self@n_obs < 0) {
      return("n_obs must be non-negative")
    }
    character(0)
  }
)

compute_effect <- new_generic("compute_effect", "model")

method(compute_effect, MediatorModel) <- function(model, ...) {
  model@n_obs
}

.onLoad <- function(libname, pkgname) {
  methods_register()
}
```

- [ ] **Step 6: Commit the fixtures**

```bash
git add tests/fixtures/s7pkg.bad tests/fixtures/s7pkg.clean
git commit -m "test(s7review): add bad + clean S7 fixture packages"
```

---

## Task 2: Module skeleton + `_find_s7_constructs` + envelope (TDD)

**Files:** Create `lib/s7review.py`; create `tests/test_s7review.py` (parser + envelope cases first).

This task lands the scaffolding every `check_*` depends on: the `cranlint`-identical `_envelope`, the `_S7_VOCAB` pin, `_scan_r_files`, and the balanced-paren `_find_s7_constructs`. Test the parser directly before any family check.

- [ ] **Step 1: Write the failing parser/envelope tests**

`tests/test_s7review.py`:

```python
"""Tests for lib.s7review — static S7 convention checker (advisory, pure-stdlib)."""
from __future__ import annotations

from pathlib import Path

from lib import s7review

FIX = Path(__file__).parent / "fixtures"
BAD = FIX / "s7pkg.bad"
CLEAN = FIX / "s7pkg.clean"


# ── parser ──────────────────────────────────────────────────────────────
def test_find_constructs_extracts_new_class_calls():
    text = 'A <- new_class("A", properties = list(x = class_numeric))\n'
    cons = s7review._find_s7_constructs(text)
    calls = [c for c in cons if c["call"] == "new_class"]
    assert calls, "should find a new_class construct"
    assert calls[0]["bound"] == "A"
    assert 'properties = list(x = class_numeric)' in calls[0]["args"]


def test_find_constructs_balances_nested_parens():
    text = 'B <- new_class("B", properties = list(f = function(a) g(a)))\n'
    cons = s7review._find_s7_constructs(text)
    nc = [c for c in cons if c["call"] == "new_class"][0]
    # the whole nested arg block was captured, not truncated at the first ')'
    assert nc["args"].rstrip().endswith("function(a) g(a)))".rstrip()[-1])


def test_find_constructs_handles_method_and_generic():
    text = (
        'G <- new_generic("G", "x")\n'
        'method(G, A) <- function(x, ...) x\n'
    )
    calls = {c["call"] for c in s7review._find_s7_constructs(text)}
    assert "new_generic" in calls
    assert "method" in calls


def test_unbalanced_parens_skipped_not_raised():
    # a construct whose parens never balance must be silently skipped
    text = 'Z <- new_class("Z", properties = list(\n'
    s7review._find_s7_constructs(text)  # must not raise


# ── envelope contract ───────────────────────────────────────────────────
def test_envelope_shape_matches_cranlint():
    env = s7review._envelope("naming", "ok", [], ["clean"])
    assert set(env) == {"kind", "status", "findings", "messages", "engine_missing"}
    assert env["engine_missing"] == []


def test_run_all_clean_fixture_is_ok():
    env = s7review.run_all(str(CLEAN))
    assert env["kind"] == "s7review"
    assert env["status"] == "ok", [s["findings"] for s in env["stages"]]
    assert env["engine_missing"] == []
    assert {s["kind"] for s in env["stages"]} == {
        "naming", "validators", "methods", "legacy", "docs"
    }


def test_run_all_no_r_dir_warns_not_raises(tmp_path):
    env = s7review.run_all(str(tmp_path))
    assert env["status"] == "warn"
    assert env["engine_missing"] == []
```

- [ ] **Step 2: Run — verify failure (no module yet)**

```bash
cd ~/.git-worktrees/rforge/feature-r-s7-review
python3 -m pytest tests/test_s7review.py -q
```

Expected: `ModuleNotFoundError: No module named 'lib.s7review'` (collection error). Good — proves the test drives the module.

- [ ] **Step 3: Implement the skeleton**

Create `lib/s7review.py`:

```python
"""Static S7 OOP convention checker (advisory, pure-stdlib, no R).

Polices *idiomatic, statically verifiable* S7 usage across an R package's
``R/*.R`` (plus ``NAMESPACE``): naming, validator presence, method references,
no S4/R5/S3 leftovers, documented exported classes. S7 is the modern R class
system (``new_class()``/``new_generic()``/``method()``).

Pure stdlib — **no R, no Rscript, no subprocess**. Mirrors ``lib/cranlint.py``:
advisory warn-only, exit 0 always, never raises, ``engine_missing`` always
``[]``. Runtime traps (validator soundness, actual registration,
abstract-instantiability) are *correctness* bugs, deferred to an R-backed v2
sibling — every finding carries ``source: "static"`` so a future pass can
promote/clear it without an envelope break.

Usage (CLI):
    python3 -m lib.s7review --path .
    python3 -m lib.s7review --path . --kind naming --format text

Usage (Python API):
    from lib import s7review
    env = s7review.run_all(".")
    print(env["status"], [f["code"] for s in env["stages"] for f in s["findings"]])
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ─────────────────────────── S7 API vocabulary ───────────────────────────
# One edit point as the S7 API churns. Targeted constructor/generic/method
# call names + the class_* type-helper prefix S7 ships.
_S7_VOCAB = {
    "new_class": "new_class",
    "new_generic": "new_generic",
    "method": "method",
    "class_prefix": "class_",      # class_numeric, class_character, ...
    "register": "methods_register",
}
_S7_CALLS = ("new_class", "new_generic", "method")

# ─────────────────────────── envelope helper ───────────────────────────
def _envelope(kind: str, status: str, findings: list, messages: list) -> dict:
    """House-style advisory envelope — byte-identical key set to lib/cranlint.py."""
    return {
        "kind": kind,
        "status": status,
        "findings": findings,
        "messages": messages,
        "engine_missing": [],
    }


# ─────────────────────────── file scanning ───────────────────────────
def _scan_r_files(path: str | os.PathLike):
    """Yield ``(Path, text)`` for every ``R/*.R`` file under ``path``.

    ``path`` may be a package dir (uses its ``R/`` subdir) or an ``R/`` dir
    itself. Unreadable files are skipped. Returns nothing if no ``R/`` dir.
    """
    p = Path(path)
    r_dir = p if p.name == "R" and p.is_dir() else p / "R"
    if not r_dir.is_dir():
        return
    for f in sorted(r_dir.glob("*.R")):
        try:
            yield f, f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue


def _match_balanced(text: str, open_idx: int) -> Optional[int]:
    """Return the index of the ``)`` matching the ``(`` at ``open_idx``.

    Naive paren counter (ignores strings/comments — acceptable for an advisory
    checker; a pathological case yields a false negative, never a false BLOCK).
    Returns ``None`` if the parens never balance.
    """
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return None


_CALL_RE = re.compile(r"(?:(\w+)\s*<-\s*)?\b(new_class|new_generic|method)\s*\(")


def _find_s7_constructs(text: str) -> list[dict]:
    """Find S7 constructor/generic/method calls with balanced-paren arg blocks.

    Returns a list of ``{call, bound, args, line}`` dicts where ``call`` is one
    of ``new_class``/``new_generic``/``method``, ``bound`` is the LHS variable
    (or ``""``), ``args`` is the raw inside-parens text, and ``line`` is the
    1-based line of the call. Unbalanced calls are silently skipped.
    """
    out: list[dict] = []
    for m in _CALL_RE.finditer(text):
        open_idx = m.end() - 1  # index of the '('
        close_idx = _match_balanced(text, open_idx)
        if close_idx is None:
            continue
        args = text[open_idx + 1:close_idx]
        out.append({
            "call": m.group(2),
            "bound": m.group(1) or "",
            "args": args,
            "line": text.count("\n", 0, m.start()) + 1,
        })
    return out


# ─────────────────────────── naming helpers ───────────────────────────
_UPPER_CAMEL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NAME_ARG_RE = re.compile(r'^\s*["\']([^"\']+)["\']')          # first string arg
_PROPS_RE = re.compile(r"properties\s*=\s*list\((.*)\)", re.DOTALL)
_PROP_NAME_RE = re.compile(r"(\w+)\s*=")
_VALIDATOR_RE = re.compile(r"validator\s*=\s*function")
# ── placeholders the five check_* functions populate (Tasks 3–7). ──
```

The five `check_*` and `run_all` land in Tasks 3–7 + 8; this skeleton makes the parser/envelope tests pass. To run the `run_all` tests in *this* task, append a **temporary** `run_all` that calls only the stages implemented so far — but cleaner: the `run_all` clean/no-R tests stay **xfail-free** by implementing the final `run_all` now and stubbing each `check_*` to return an `ok` envelope, then replacing each stub in its task.

Append the temporary stubs + final `run_all` + CLI to `lib/s7review.py`:

```python
# ── temporary stubs (each replaced in its own task) ──
def check_naming(path):      # Task 3
    return _envelope("naming", "ok", [], ["(stub)"])
def check_validators(path):  # Task 4
    return _envelope("validators", "ok", [], ["(stub)"])
def check_methods(path):     # Task 5
    return _envelope("methods", "ok", [], ["(stub)"])
def check_legacy_oop(path):  # Task 6
    return _envelope("legacy", "ok", [], ["(stub)"])
def check_class_docs(path):  # Task 7
    return _envelope("docs", "ok", [], ["(stub)"])


_CHECKS = {
    "naming": check_naming,
    "validators": check_validators,
    "methods": check_methods,
    "legacy": check_legacy_oop,
    "docs": check_class_docs,
}


def run_all(path: str | os.PathLike = ".") -> dict:
    """Run all 5 convention checks; roll into one worst-of (ok<warn) envelope.

    Returns ``{kind: "s7review", status, stages, engine_missing: []}``. If no
    ``R/`` directory exists, returns a single ``warn`` envelope (advisory).
    """
    p = Path(path)
    r_dir = p if p.name == "R" and p.is_dir() else p / "R"
    if not r_dir.is_dir():
        return {
            "kind": "s7review", "status": "warn", "stages": [],
            "messages": ["No R/ directory found — is this an R package? "
                         "Try /rforge:detect."],
            "engine_missing": [],
        }
    stages = [fn(path) for fn in (
        check_naming, check_validators, check_methods,
        check_legacy_oop, check_class_docs)]
    status = "warn" if any(s["status"] == "warn" for s in stages) else "ok"
    return {"kind": "s7review", "status": status, "stages": stages,
            "engine_missing": []}


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m lib.s7review",
        description="Static S7 convention checker (advisory, pure Python, no R).",
    )
    parser.add_argument("--path", default=".", help="Package directory (default: cwd)")
    parser.add_argument(
        "--kind",
        choices=("all", "naming", "validators", "methods", "legacy", "docs"),
        default="all", help="Which family to run (default: all).")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    args = parser.parse_args(argv)

    env = run_all(args.path) if args.kind == "all" else _CHECKS[args.kind](args.path)

    if args.format == "text":
        print(f"{env['kind']}: {env['status']}")
        stages = env.get("stages", [env])
        for s in stages:
            for f in s.get("findings", []):
                print(f"  [{f['code']}] {f.get('file','')}:{f.get('line','')} "
                      f"{f.get('symbol','')} — {f['message']}")
    else:
        print(json.dumps(env, indent=2))
    return 0  # advisory — never a non-zero exit


if __name__ == "__main__":
    sys.exit(_main())
```

- [ ] **Step 4: Run — parser + envelope tests pass**

```bash
python3 -m pytest tests/test_s7review.py -q
```

Expected: all Task-2 tests pass (clean-fixture `run_all` is `ok` because all checks are stubs returning `ok`).

- [ ] **Step 5: Commit**

```bash
git add lib/s7review.py tests/test_s7review.py
git commit -m "feat(s7review): module skeleton — _find_s7_constructs, _envelope, run_all + CLI (stubbed checks)"
```

---

## Task 3: `check_naming` family (TDD)

**Files:** Modify `lib/s7review.py` (replace `check_naming` stub); modify `tests/test_s7review.py`.

Codes: `class_name_case` (class name not UpperCamelCase), `class_name_mismatch` (bound var ≠ `name=` string), `generic_name_case` (generic not snake_case), `prop_name_case` (property name not snake_case). House style overridable via `.rforge.yaml` `s7:` block — but v1 reads defaults only (config read is a thin helper; defaults stand if no file).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_s7review.py`:

```python
def _codes(env):
    return {f["code"] for f in env["findings"]}


def test_naming_flags_bad_fixture():
    env = s7review.check_naming(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "class_name_case" in c        # mediator_model
    assert "class_name_mismatch" in c    # Estimator <- new_class("Estimater")
    assert "generic_name_case" in c      # ComputeEffect
    assert "prop_name_case" in c         # BadProp
    for f in env["findings"]:
        assert f["severity"] == "advisory"
        assert f["source"] == "static"


def test_naming_clean_fixture_ok():
    env = s7review.check_naming(str(CLEAN))
    assert env["status"] == "ok"
    assert env["findings"] == []
```

- [ ] **Step 2: Run — verify failure**

```bash
python3 -m pytest tests/test_s7review.py -k naming -q
```

Expected: `test_naming_flags_bad_fixture` fails (stub returns `ok`/no findings).

- [ ] **Step 3: Implement — replace the `check_naming` stub**

In `lib/s7review.py`, delete the `def check_naming(path): ... "(stub)"` block and insert:

```python
def _name_arg(args: str) -> str:
    """First string-literal argument inside a call's arg block, or ''."""
    m = _NAME_ARG_RE.match(args)
    return m.group(1) if m else ""


def _prop_names(args: str) -> list[str]:
    """Property names from a ``properties = list(a = ..., b = ...)`` block."""
    pm = _PROPS_RE.search(args)
    if not pm:
        return []
    return _PROP_NAME_RE.findall(pm.group(1))


def check_naming(path: str | os.PathLike = ".") -> dict:
    """Naming conventions: class UpperCamelCase + bound-var match; generic and
    property names snake_case. Advisory; ``warn`` if any finding. Never raises.
    """
    findings: list[dict] = []
    for f, text in _scan_r_files(path):
        rel = f.name
        for c in _find_s7_constructs(text):
            name = _name_arg(c["args"])
            if c["call"] == "new_class":
                if name and not _UPPER_CAMEL_RE.match(name):
                    findings.append({
                        "code": "class_name_case", "severity": "advisory",
                        "file": rel, "line": c["line"], "symbol": name,
                        "source": "static",
                        "message": (f"S7 class '{name}' is not UpperCamelCase — "
                                    "consider e.g. 'MyClass'."),
                    })
                if c["bound"] and name and c["bound"] != name:
                    findings.append({
                        "code": "class_name_mismatch", "severity": "advisory",
                        "file": rel, "line": c["line"], "symbol": c["bound"],
                        "source": "static",
                        "message": (f"bound variable '{c['bound']}' differs from "
                                    f"new_class name '{name}' — they look like "
                                    "they should match."),
                    })
                for pn in _prop_names(c["args"]):
                    if not _SNAKE_RE.match(pn):
                        findings.append({
                            "code": "prop_name_case", "severity": "advisory",
                            "file": rel, "line": c["line"], "symbol": pn,
                            "source": "static",
                            "message": (f"property '{pn}' is not snake_case — "
                                        "consider e.g. 'my_prop'."),
                        })
            elif c["call"] == "new_generic":
                if name and not _SNAKE_RE.match(name):
                    findings.append({
                        "code": "generic_name_case", "severity": "advisory",
                        "file": rel, "line": c["line"], "symbol": name,
                        "source": "static",
                        "message": (f"S7 generic '{name}' is not snake_case — "
                                    "consider e.g. 'compute_effect'."),
                    })
    status = "warn" if findings else "ok"
    messages = [] if findings else ["S7 naming looks idiomatic."]
    return _envelope("naming", status, findings, messages)
```

- [ ] **Step 4: Run — green**

```bash
python3 -m pytest tests/test_s7review.py -k naming -q
```

Expected: naming tests pass.

- [ ] **Step 5: Commit**

```bash
git add lib/s7review.py tests/test_s7review.py
git commit -m "feat(s7review): check_naming — class/generic/prop case + name-mismatch"
```

---

## Task 4: `check_validators` family (TDD)

**Files:** Modify `lib/s7review.py` (replace `check_validators` stub); modify `tests/test_s7review.py`.

Codes: `missing_validator` (a `new_class` with a non-empty `properties=` and no `validator=`), `validator_return_shape` (a `validator=` whose body obviously `return(TRUE)`/`return(FALSE)` — S7 validators must return `character()`/`NULL`).

- [ ] **Step 1: Write the failing tests**

```python
def test_validators_flag_bad_fixture():
    env = s7review.check_validators(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "missing_validator" in c       # mediator_model has typed props, no validator
    assert "validator_return_shape" in c  # Validated returns TRUE
    for f in env["findings"]:
        assert f["source"] == "static" and f["severity"] == "advisory"


def test_validators_clean_fixture_ok():
    env = s7review.check_validators(str(CLEAN))
    assert env["status"] == "ok"
```

- [ ] **Step 2: Run — verify failure**

```bash
python3 -m pytest tests/test_s7review.py -k validators -q
```

Expected: fails (stub).

- [ ] **Step 3: Implement — replace the `check_validators` stub**

```python
_RETURN_BOOL_RE = re.compile(r"return\s*\(\s*(TRUE|FALSE)\s*\)")


def check_validators(path: str | os.PathLike = ".") -> dict:
    """Validator presence + return-shape. A typed-properties ``new_class`` should
    declare a ``validator=``; a validator returning ``TRUE``/``FALSE`` is wrong
    (S7 wants ``character()``/``NULL``). Advisory. Never raises.
    """
    findings: list[dict] = []
    for f, text in _scan_r_files(path):
        rel = f.name
        for c in _find_s7_constructs(text):
            if c["call"] != "new_class":
                continue
            name = _name_arg(c["args"]) or c["bound"] or "<class>"
            has_props = bool(_prop_names(c["args"]))
            has_validator = bool(_VALIDATOR_RE.search(c["args"]))
            if has_props and not has_validator:
                findings.append({
                    "code": "missing_validator", "severity": "advisory",
                    "file": rel, "line": c["line"], "symbol": name,
                    "source": "static",
                    "message": (f"S7 class '{name}' has typed properties but no "
                                "validator= — consider adding one to enforce "
                                "invariants."),
                })
            if has_validator and _RETURN_BOOL_RE.search(c["args"]):
                findings.append({
                    "code": "validator_return_shape", "severity": "advisory",
                    "file": rel, "line": c["line"], "symbol": name,
                    "source": "static",
                    "message": (f"validator for '{name}' looks like it returns "
                                "TRUE/FALSE — S7 validators should return "
                                "character() (errors) or NULL (ok)."),
                })
    status = "warn" if findings else "ok"
    messages = [] if findings else ["S7 validators look well-formed."]
    return _envelope("validators", status, findings, messages)
```

- [ ] **Step 4: Run — green**

```bash
python3 -m pytest tests/test_s7review.py -k validators -q
```

- [ ] **Step 5: Commit**

```bash
git add lib/s7review.py tests/test_s7review.py
git commit -m "feat(s7review): check_validators — missing validator + bad return shape"
```

---

## Task 5: `check_methods` family (TDD)

**Files:** Modify `lib/s7review.py` (replace `check_methods` stub); modify `tests/test_s7review.py`.

Codes: `dangling_method` (`method(generic, Class) <- fn` where `generic` is neither defined via `new_generic` nor imported in scanned source), `missing_methods_register` (per **Decision 2** — quiet advisory: a `method()` on an *external* generic with no `methods_register(` anywhere in `R/`).

- [ ] **Step 1: Write the failing tests**

```python
def test_methods_flag_bad_fixture():
    env = s7review.check_methods(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "dangling_method" in c            # method(external_generic, ...)
    assert "missing_methods_register" in c   # no methods_register() in bad fixture


def test_methods_clean_fixture_ok():
    # clean fixture: compute_effect generic defined locally + methods_register() present
    env = s7review.check_methods(str(CLEAN))
    assert env["status"] == "ok"
```

- [ ] **Step 2: Run — verify failure**

```bash
python3 -m pytest tests/test_s7review.py -k methods -q
```

- [ ] **Step 3: Implement — replace the `check_methods` stub**

```python
# first identifier argument to method(generic, Class)
_METHOD_GENERIC_RE = re.compile(r"^\s*([A-Za-z.][\w.]*)")
# imported symbols: importFrom(pkg, sym) / @importFrom pkg sym
_NS_IMPORTFROM_SYM_RE = re.compile(r"^\s*importFrom\(\s*[\w.]+\s*,\s*([\w.]+)")
_ROX_IMPORTFROM_SYM_RE = re.compile(r"^#'\s*@importFrom\s+[\w.]+\s+(.+)$")


def _imported_symbols(pkg_path: Path) -> set[str]:
    """Symbols imported via NAMESPACE importFrm + roxygen @importFrom in R/."""
    syms: set[str] = set()
    ns = pkg_path / "NAMESPACE"
    if ns.is_file():
        try:
            for line in ns.read_text(encoding="utf-8", errors="replace").splitlines():
                m = _NS_IMPORTFROM_SYM_RE.match(line)
                if m:
                    syms.add(m.group(1))
        except OSError:
            pass
    for _f, text in _scan_r_files(pkg_path):
        for line in text.splitlines():
            m = _ROX_IMPORTFROM_SYM_RE.match(line)
            if m:
                syms.update(re.split(r"[,\s]+", m.group(1).strip()))
    return syms


def check_methods(path: str | os.PathLike = ".") -> dict:
    """Method registration sanity. Flags a ``method(generic, Class)`` whose
    ``generic`` is neither defined (``new_generic``) nor imported in scanned
    source (``dangling_method``); and — per the bounded v1 decision — a method
    on an external generic with no ``methods_register()`` call anywhere in R/
    (``missing_methods_register``, quiet advisory). Never raises.
    """
    p = Path(path)
    pkg = p if (p / "R").is_dir() or p.name != "R" else p.parent

    # collect locally-defined generics + methods + register-presence in one pass
    local_generics: set[str] = set()
    methods: list[dict] = []
    has_register = False
    for f, text in _scan_r_files(path):
        if _S7_VOCAB["register"] + "(" in text:
            has_register = True
        for c in _find_s7_constructs(text):
            if c["call"] == "new_generic":
                nm = _name_arg(c["args"]) or c["bound"]
                if nm:
                    local_generics.add(nm)
                if c["bound"]:
                    local_generics.add(c["bound"])
            elif c["call"] == "method":
                gm = _METHOD_GENERIC_RE.match(c["args"])
                methods.append({
                    "generic": gm.group(1) if gm else "",
                    "file": f.name, "line": c["line"],
                })

    imported = _imported_symbols(pkg)
    findings: list[dict] = []
    saw_external = False
    for m in methods:
        g = m["generic"]
        if not g:
            continue
        in_scope = g in local_generics or g in imported
        if not in_scope:
            saw_external = True
            findings.append({
                "code": "dangling_method", "severity": "advisory",
                "file": m["file"], "line": m["line"], "symbol": g,
                "source": "static",
                "message": (f"method() targets generic '{g}' which is neither "
                            "defined (new_generic) nor imported here — looks "
                            "dangling; check the generic is in scope."),
            })
    if saw_external and not has_register:
        findings.append({
            "code": "missing_methods_register", "severity": "advisory",
            "file": "R/", "line": 0, "symbol": "methods_register",
            "source": "static",
            "message": ("method() registers on an external generic but no "
                        "methods_register() call was found — S7 methods may be "
                        "silently unregistered; consider calling "
                        "methods_register() in .onLoad()."),
        })
    status = "warn" if findings else "ok"
    messages = [] if findings else ["S7 method registration looks consistent."]
    return _envelope("methods", status, findings, messages)
```

- [ ] **Step 4: Run — green**

```bash
python3 -m pytest tests/test_s7review.py -k methods -q
```

- [ ] **Step 5: Commit**

```bash
git add lib/s7review.py tests/test_s7review.py
git commit -m "feat(s7review): check_methods — dangling method + missing methods_register (quiet)"
```

---

## Task 6: `check_legacy_oop` family (TDD)

**Files:** Modify `lib/s7review.py` (replace `check_legacy_oop` stub); modify `tests/test_s7review.py`.

Codes: `legacy_s4_in_s7` (`setClass`/`setGeneric`/`setMethod`/`representation(` co-residing with `new_class`), `legacy_r5_in_s7` (`setRefClass`/`R6Class(`), `legacy_s3_generic` (`UseMethod(` in a function whose name suffix matches a defined S7 class — heuristic).

- [ ] **Step 1: Write the failing tests**

```python
def test_legacy_flag_bad_fixture():
    env = s7review.check_legacy_oop(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "legacy_s4_in_s7" in c   # setClass/setGeneric
    assert "legacy_r5_in_s7" in c   # R6::R6Class
    assert "legacy_s3_generic" in c # print.mediator_model + UseMethod


def test_legacy_clean_fixture_ok():
    env = s7review.check_legacy_oop(str(CLEAN))
    assert env["status"] == "ok"
```

- [ ] **Step 2: Run — verify failure**

```bash
python3 -m pytest tests/test_s7review.py -k legacy -q
```

- [ ] **Step 3: Implement — replace the `check_legacy_oop` stub**

```python
_S4_PATTERNS = [
    (re.compile(r"\bsetClass\s*\("), "setClass"),
    (re.compile(r"\bsetGeneric\s*\("), "setGeneric"),
    (re.compile(r"\bsetMethod\s*\("), "setMethod"),
    (re.compile(r"\brepresentation\s*\("), "representation"),
]
_R5_PATTERNS = [
    (re.compile(r"\bsetRefClass\s*\("), "setRefClass"),
    (re.compile(r"(?:\bR6::)?\bR6Class\s*\("), "R6Class"),
]
_USEMETHOD_RE = re.compile(r"\bUseMethod\s*\(")
_S3_DEF_RE = re.compile(r"^\s*([A-Za-z.][\w.]*)\.([A-Za-z][\w]*)\s*<-\s*function")


def check_legacy_oop(path: str | os.PathLike = ".") -> dict:
    """Flag pre-S7 OOP co-residing with S7. ``setClass``/``setGeneric``/
    ``representation`` → ``legacy_s4_in_s7``; ``setRefClass``/``R6Class`` →
    ``legacy_r5_in_s7``; an S3 ``foo.<S7Class> <- function`` body calling
    ``UseMethod()`` → ``legacy_s3_generic`` (heuristic). Only fires when the
    file/package also uses ``new_class`` (a pure-S4 package is not an S7
    convention problem). Never raises.
    """
    files = list(_scan_r_files(path))
    uses_s7 = any("new_class" in text for _f, text in files)
    if not uses_s7:
        return _envelope("legacy", "ok", [],
                         ["No new_class found — not an S7 package; legacy check "
                          "skipped (absence is not a violation)."])

    # set of S7 class names defined anywhere (for the S3 heuristic)
    s7_classes: set[str] = set()
    for _f, text in files:
        for c in _find_s7_constructs(text):
            if c["call"] == "new_class":
                nm = _name_arg(c["args"]) or c["bound"]
                if nm:
                    s7_classes.add(nm)
                if c["bound"]:
                    s7_classes.add(c["bound"])

    findings: list[dict] = []
    for f, text in files:
        rel = f.name
        for i, line in enumerate(text.splitlines(), start=1):
            for rx, sym in _S4_PATTERNS:
                if rx.search(line):
                    findings.append({
                        "code": "legacy_s4_in_s7", "severity": "advisory",
                        "file": rel, "line": i, "symbol": sym, "source": "static",
                        "message": (f"'{sym}()' (S4) co-resides with S7 new_class "
                                    "— looks like a mid-migration leftover; "
                                    "consider porting to S7."),
                    })
            for rx, sym in _R5_PATTERNS:
                if rx.search(line):
                    findings.append({
                        "code": "legacy_r5_in_s7", "severity": "advisory",
                        "file": rel, "line": i, "symbol": sym, "source": "static",
                        "message": (f"'{sym}()' (R5/R6) co-resides with S7 — "
                                    "consider consolidating on S7."),
                    })
            m = _S3_DEF_RE.match(line)
            if m and m.group(2) in s7_classes:
                findings.append({
                    "code": "legacy_s3_generic", "severity": "advisory",
                    "file": rel, "line": i, "symbol": m.group(0).strip(),
                    "source": "static",
                    "message": (f"S3 method '{m.group(1)}.{m.group(2)}' dispatches "
                                f"on S7 class '{m.group(2)}' — prefer an S7 "
                                "method() over S3 UseMethod()."),
                })
            elif _USEMETHOD_RE.search(line):
                # bare UseMethod whose generic name matches an S7 class suffix
                continue
    status = "warn" if findings else "ok"
    messages = [] if findings else ["No legacy OOP co-residing with S7."]
    return _envelope("legacy", status, findings, messages)
```

> **Reuse note (spec correction):** the spec says reuse `deps_sync`'s "NAMESPACE/`@export` parser" for the docs family. `deps_sync` only parses **imports** (`importFrom`/`@importFrom`) — there is **no** `export()`/`@export` parser to reuse. `check_methods` (Task 5) reuses the *importFrom* precedent (`_imported_symbols`); `check_class_docs` (Task 7) introduces a **new** `export()`/`@export` parser that *mirrors* `deps_sync`'s regex style. This is the honest interpretation of the spec's intent ("don't write a second importFrom parser") without inventing a parser that doesn't exist.

- [ ] **Step 4: Run — green**

```bash
python3 -m pytest tests/test_s7review.py -k legacy -q
```

- [ ] **Step 5: Commit**

```bash
git add lib/s7review.py tests/test_s7review.py
git commit -m "feat(s7review): check_legacy_oop — S4/R5/R6/S3 leftovers co-residing with S7"
```

---

## Task 7: `check_class_docs` family (TDD)

**Files:** Modify `lib/s7review.py` (replace `check_class_docs` stub); modify `tests/test_s7review.py`.

Codes: `undocumented_export` (a class exported via `NAMESPACE export()` or roxygen `@export` whose `new_class` has no `#'` block immediately above), `prop_type_unresolvable` (a property's declared class is not a `class_*` S7 builtin and not a class defined in scanned source).

- [ ] **Step 1: Write the failing tests**

```python
def test_docs_flag_bad_fixture():
    env = s7review.check_class_docs(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "undocumented_export" in c     # export(undocumented_class), no #' block
    assert "prop_type_unresolvable" in c  # ref = NoSuchClass


def test_docs_clean_fixture_ok():
    env = s7review.check_class_docs(str(CLEAN))
    assert env["status"] == "ok"
```

- [ ] **Step 2: Run — verify failure**

```bash
python3 -m pytest tests/test_s7review.py -k docs -q
```

- [ ] **Step 3: Implement — replace the `check_class_docs` stub**

```python
# NEW export parser (mirrors deps_sync's importFrom regex style; deps_sync has
# no export parser to reuse).
_NS_EXPORT_RE = re.compile(r"^\s*export\(\s*([\w.]+)\s*\)")
_ROX_EXPORT_RE = re.compile(r"^#'\s*@export\b")
_PROP_TYPE_RE = re.compile(r"\w+\s*=\s*([A-Za-z.][\w.:]*)")  # name = TypeExpr


def _exported_names(pkg_path: Path) -> set[str]:
    """Symbols exported via NAMESPACE export(...). (roxygen @export handled inline)"""
    syms: set[str] = set()
    ns = pkg_path / "NAMESPACE"
    if ns.is_file():
        try:
            for line in ns.read_text(encoding="utf-8", errors="replace").splitlines():
                m = _NS_EXPORT_RE.match(line)
                if m:
                    syms.add(m.group(1))
        except OSError:
            pass
    return syms


def check_class_docs(path: str | os.PathLike = ".") -> dict:
    """Doc + type-resolution. An exported S7 class (NAMESPACE ``export()`` or a
    preceding roxygen ``@export``) should have a ``#'`` block immediately above
    its ``new_class`` (``undocumented_export``); a property's declared class
    should resolve to a ``class_*`` builtin or a class defined in scanned source
    (``prop_type_unresolvable``). Never raises.
    """
    p = Path(path)
    pkg = p if (p / "R").is_dir() or p.name != "R" else p.parent
    exported = _exported_names(pkg)

    files = list(_scan_r_files(path))
    defined: set[str] = set()
    for _f, text in files:
        for c in _find_s7_constructs(text):
            if c["call"] == "new_class":
                nm = _name_arg(c["args"]) or c["bound"]
                if nm:
                    defined.add(nm)
                if c["bound"]:
                    defined.add(c["bound"])

    findings: list[dict] = []
    for f, text in files:
        rel = f.name
        lines = text.splitlines()
        for c in _find_s7_constructs(text):
            if c["call"] != "new_class":
                continue
            name = _name_arg(c["args"]) or c["bound"] or "<class>"
            bound = c["bound"]
            # roxygen block immediately above the construct's line?
            li = c["line"] - 1  # 0-based index of the call line
            j = li - 1
            has_doc = False
            has_rox_export = False
            while j >= 0 and (lines[j].lstrip().startswith("#'") or not lines[j].strip()):
                if lines[j].lstrip().startswith("#'"):
                    has_doc = True
                    if _ROX_EXPORT_RE.match(lines[j].strip()):
                        has_rox_export = True
                j -= 1
            is_exported = bound in exported or name in exported or has_rox_export
            if is_exported and not has_doc:
                findings.append({
                    "code": "undocumented_export", "severity": "advisory",
                    "file": rel, "line": c["line"], "symbol": name,
                    "source": "static",
                    "message": (f"exported S7 class '{name}' has no #' doc block — "
                                "consider documenting it (roxygen @export needs a "
                                "title)."),
                })
            # property type resolution
            pm = _PROPS_RE.search(c["args"])
            if pm:
                for tm in _PROP_TYPE_RE.finditer(pm.group(1)):
                    typ = tm.group(1)
                    base = typ.split("::")[-1]
                    if base.startswith(_S7_VOCAB["class_prefix"]):
                        continue            # class_numeric etc. — builtin
                    if "::" in typ:
                        continue            # external pkg::Class — assume resolvable
                    if base in defined:
                        continue
                    if base in ("list", "TRUE", "FALSE", "NULL", "NA"):
                        continue
                    findings.append({
                        "code": "prop_type_unresolvable", "severity": "advisory",
                        "file": rel, "line": c["line"], "symbol": typ,
                        "source": "static",
                        "message": (f"property type '{typ}' in '{name}' does not "
                                    "resolve to a class_* builtin or a class "
                                    "defined here — check the type is in scope."),
                    })
    status = "warn" if findings else "ok"
    messages = [] if findings else ["Exported S7 classes documented; prop types resolve."]
    return _envelope("docs", status, findings, messages)
```

- [ ] **Step 4: Run — green; then the FULL `test_s7review.py` (all families + Task-2 contract)**

```bash
python3 -m pytest tests/test_s7review.py -q
```

Expected: every test passes (parser, envelope, all 5 families, clean-fixture `ok`). The Task-2 `test_run_all_clean_fixture_is_ok` now exercises real checks (no stubs remain).

- [ ] **Step 5: Commit**

```bash
git add lib/s7review.py tests/test_s7review.py
git commit -m "feat(s7review): check_class_docs — undocumented exports + unresolvable prop types"
```

---

## Task 8: Command file `commands/r/s7-review.md`

**Files:** Create `commands/r/s7-review.md`.

- [ ] **Step 1: Write the command file**

`commands/r/s7-review.md`:

```markdown
---
name: rforge:r:s7-review
description: Static S7 OOP convention checker (advisory — naming/validators/methods/legacy/docs)
argument-hint: "[package] [--kind all|naming|validators|methods|legacy|docs] [--format json|text]"
arguments:
  - name: package
    description: Package directory to review (positional; default cwd)
    required: false
    type: string
  - name: --kind
    description: Which convention family to run
    required: false
    type: string
    default: all
  - name: --format
    description: Output format
    required: false
    type: string
    default: json
---

# /rforge:r:s7-review

Statically check **S7 OOP conventions** across an R package. Advisory only —
**never blocks** anything, mirrors `r:cran-prep`'s Tier-4 advisory tone. Pure
Python (no R, no Rscript): scans `R/*.R` + `NAMESPACE`.

## Usage

```bash
python3 -m lib.s7review --path "<package-dir>" --kind all --format json
```

- `package` (positional) — package directory (default: cwd).
- `--kind all|naming|validators|methods|legacy|docs` — limit to one family (default `all`).
- `--format json|text` — default `json`.

There is **no** `--write`/`--fix` (S7 fixes need human judgement, like `r:cran-prep`).

## Convention families

| Family | Codes |
|---|---|
| naming | `class_name_case`, `class_name_mismatch`, `generic_name_case`, `prop_name_case` |
| validators | `missing_validator`, `validator_return_shape` |
| methods | `dangling_method`, `missing_methods_register` |
| legacy | `legacy_s4_in_s7`, `legacy_r5_in_s7`, `legacy_s3_generic` |
| docs | `undocumented_export`, `prop_type_unresolvable` |

Each finding carries `source: "static"` and `severity: "advisory"`, worded
"looks like / consider", never "must".

## Deferred (v1)

- **`--eco` (ecosystem consistency)** is deferred until the mediationverse
  house-convention spec lands (codes `divergent_class_def`,
  `inconsistent_prop_type`). Findings already carry `source: "static"`, so
  `--eco` is an additive follow-up with no envelope break.
- **Runtime checks** (validator soundness, actual registration,
  abstract-instantiability) are deferred to an R-backed v2 sibling.

## Output

A single `{kind: "s7review", status: "ok"|"warn", stages: [...], engine_missing: []}`
envelope (or one family envelope with `--kind X`). Advisory — exit 0 always.
```

- [ ] **Step 2: Confirm `arguments:` matches `## Usage`** (no `--write`, no `--eco` in either — they must agree).

- [ ] **Step 3: Commit**

```bash
git add commands/r/s7-review.md
git commit -m "feat(s7review): add commands/r/s7-review.md (no --write, --eco deferred)"
```

---

## Task 9: Reference docs + test-all smoke line

**Files:** Modify `scripts/gen_lib_reference.py`; create `docs/reference/s7review.md` (generated); modify `tests/test-all.sh`.

- [ ] **Step 1: Register the module in the generator**

In `scripts/gen_lib_reference.py`, add `"lib.s7review"` to `MODULES`:

```python
MODULES = ["lib.discovery", "lib.deps", "lib.status", "lib.init", "lib.rcmd", "lib.cranlint", "lib.deps_sync", "lib.ghrelease", "lib.runiverse", "lib.s7review"]
```

- [ ] **Step 2: Generate the reference page**

```bash
python3 scripts/gen_lib_reference.py
python3 scripts/gen_lib_reference.py --check   # expect exit 0
```

Expected: `docs/reference/s7review.md` created; `--check` reports no drift.

- [ ] **Step 3: Add the CLI-smoke helper to `tests/test-all.sh`**

After `lib_runiverse_smoke()` (it ends just before `agent_no_mcp_refs()`), insert:

```bash
# lib.s7review CLI smoke — pure-Python, R-free. Runs against the deliberately-bad
# S7 fixture and asserts the advisory contract: kind 's7review', status in
# {ok,warn} (never error), engine_missing == [].
lib_s7review_smoke() {
    local out
    out=$(python3 -m lib.s7review --path tests/fixtures/s7pkg.bad --kind all --format json 2>/dev/null)
    printf '%s' "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['kind'] == 's7review', f\"unexpected kind {d['kind']}\"
assert d['status'] in ('ok', 'warn'), f\"advisory module must never error, got {d['status']}\"
assert d['engine_missing'] == [], 'pure-Python module: engine_missing must be []'
kinds = {s['kind'] for s in d['stages']}
need = {'naming', 'validators', 'methods', 'legacy', 'docs'}
assert need <= kinds, f'missing families: {need - kinds}'
"
}
```

- [ ] **Step 4: Register the check**

Next to `run "Dogfood: lib.runiverse CLI smoke ..."` (around line 527), add:

```bash
run "Dogfood: lib.s7review CLI smoke (R-free advisory envelope)" lib_s7review_smoke
```

- [ ] **Step 5: Run both gates**

```bash
bash tests/test-all.sh; echo "exit=$?"
python3 -m pytest tests/ -q
```

Expected: `test-all.sh` exits 0 (check count rises by 1, ~33 → 34); pytest all pass (lib cases rise by the `test_s7review.py` count, ~230 → ~245).

- [ ] **Step 6: Commit**

```bash
git add scripts/gen_lib_reference.py docs/reference/s7review.md tests/test-all.sh
git commit -m "test(s7review): gen reference page + lib.s7review CLI-smoke (test-all gate)"
```

---

## Task 10: Version bump (`35 → 36`) + version_sync + marketplace

**Files:** `package.json`, `.claude-plugin/marketplace.json`, `mkdocs.yml`, `.claude-plugin/plugin.json` + `README.md` (via script).

> **Before editing:** `grep '"version"' package.json`. The new version is `current minor + 1`. If `package.json` already reads `2.9.0` (Phase 4 shipped), use `2.10.0`. Substitute `<VER>` below.

- [ ] **Step 1: Bump source-of-truth version + count**

Edit `package.json`: `"version"` → `<VER>`; in `description`, change `35 commands` → `36 commands`.

- [ ] **Step 2: Bump `mkdocs.yml extra.rforge.command_count` manually**

Edit `mkdocs.yml`: `extra.rforge.command_count: 35` → `36`. *(command_count is hardcoded-for-v1, CI-validated — `version_sync.py` does not derive it.)*

- [ ] **Step 3: Propagate derived surfaces**

```bash
python3 scripts/version_sync.py
python3 scripts/version_sync.py --check   # expect exit 0
```

This stamps `plugin.json` (version + `36 commands` in description), `mkdocs.yml extra.rforge.version`, `README.md` footer/tagline, and the `CLAUDE.md` command-count heading.

- [ ] **Step 4: Bump `marketplace.json` manually (script skips it)**

Edit `.claude-plugin/marketplace.json`: set BOTH `metadata.version` AND `plugins[0].version` to `<VER>`.

- [ ] **Step 5: Verify the 4-source gate**

```bash
bash tests/test-all.sh 2>&1 | grep -E "version sources agree|version/count strings in sync"
```

Expected: both green.

- [ ] **Step 6: Commit**

```bash
git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json mkdocs.yml README.md CLAUDE.md
git commit -m "chore(release): v<VER> — r:s7-review (35→36 commands) + version/count sync"
```

---

## Task 11: CHANGELOG, CLAUDE.md, .STATUS

**Files:** `CHANGELOG.md`, `CLAUDE.md`, `.STATUS`.

- [ ] **Step 1: CHANGELOG.md**

Convert `[Unreleased]` → `[<VER>] - <ship date>` and add:

```markdown
### Added
- **`r:s7-review`** — new command + pure-stdlib module `lib/s7review.py` that
  statically checks S7 OOP conventions (naming / validators / methods / legacy /
  docs) across a package. Advisory-only (never blocks), `cranlint.py` archetype:
  warn-only, exit 0, `engine_missing` always `[]`, no R/Rscript. 35 → 36 commands.
  `--eco` (ecosystem consistency) and runtime checks deferred. Spec:
  `docs/specs/SPEC-r-s7-review-2026-06-12.md`.
```

- [ ] **Step 2: CLAUDE.md**

- Add `s7review` to the **lib/ Python package convention** public-modules list and the auto-generated reference-docs list.
- Add a short "S7-review module (`s7review`, v<VER>): pure-stdlib (no R), like the analysis modules …" bullet.
- The `## Command-file conventions (all NN commands)` heading: `version_sync.py` already stamped `36` in Task 10 — verify it reads 36.
- Test-gate counts: bump the `tests/test-all.sh` "**NN checks**" and "**NNN lib/\* cases**" numbers to match Task 9's run.
- "Current state" line: note v<VER> ships `r:s7-review`.

- [ ] **Step 3: .STATUS**

Set `version: <VER>`; move `r:s7-review` from candidate to shipped; note `--eco` deferred (Open Question 1 unresolved).

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md CLAUDE.md .STATUS
git commit -m "docs(s7review): CHANGELOG + CLAUDE.md public-module list + .STATUS (v<VER>)"
```

---

## Task 12: Final gates + PR

- [ ] **Step 1: Both gates green**

```bash
bash tests/test-all.sh && python3 -m pytest tests/ -q; echo "exit=$?"
```

Expected: `exit=0`; test-all all green, pytest all pass.

- [ ] **Step 2: Reference + version drift double-check**

```bash
python3 scripts/gen_lib_reference.py --check && python3 scripts/version_sync.py --check && echo "no drift"
```

- [ ] **Step 3: Push + open PR feature → dev**

```bash
git push -u origin feature/r-s7-review
gh pr create --base dev --title "feat(s7review): r:s7-review static S7 convention checker (v<VER>)" \
  --body "New command + pure-stdlib lib/s7review.py: static S7 convention checks (naming/validators/methods/legacy/docs), advisory-only (cranlint archetype), 35->36 commands. --eco + runtime checks deferred (spec Open Qs). Spec: docs/specs/SPEC-r-s7-review-2026-06-12.md"
```

---

## Self-Review

**Spec coverage checklist:**

- 5 families with real regex/parse logic per spec codes:
  - naming (`class_name_case`/`class_name_mismatch`/`generic_name_case`/`prop_name_case`) → Task 3 ✓
  - validators (`missing_validator`/`validator_return_shape`) → Task 4 ✓
  - methods (`dangling_method`/`missing_methods_register`) → Task 5 ✓
  - legacy (`legacy_s4_in_s7`/`legacy_r5_in_s7`/`legacy_s3_generic`) → Task 6 ✓
  - docs (`undocumented_export`/`prop_type_unresolvable`) → Task 7 ✓
- Each family = own task: failing fixture test → `check_*` → green → commit ✓ (Tasks 3–7)
- `cranlint`-archetype envelope (byte-identical key set, advisory warn-only, exit 0, `engine_missing == []`, stdlib-only) → Task 2 `_envelope` + Task-2 contract test + Task 9 smoke ✓
- `source: "static"` on every finding (forward-compat with R v2) → asserted in Task 3 test, set in every `check_*` ✓
- `_S7_VOCAB` single edit point → Task 2 ✓
- `_find_s7_constructs` balanced-paren extraction; unbalanced → skipped not raised → Task 2 (`test_unbalanced_parens_skipped_not_raised`) ✓
- Error handling: no `R/` → warn (Task 2 `test_run_all_no_r_dir_warns_not_raises`); no S7 → `ok` (Task 6 `uses_s7` guard) ✓
- Command file, `name: rforge:r:s7-review`, `arguments:` ↔ `## Usage` synced, no `--write` → Task 8 ✓
- Reference page via `gen_lib_reference.py` + `--check` CI gate → Task 9 ✓
- test-all CLI-smoke line → Task 9 ✓
- Version bump 35 → 36, `version_sync.py`, manual `marketplace.json` + `command_count`, CHANGELOG, CLAUDE.md, .STATUS → Tasks 10–11 ✓
- Worktree (new code blocked on dev) → Task 0 ✓

**Spec deviations (deliberate, flagged):**
- **Count corrected 35 → 36** (spec said 33 → 36; current count is 35). ✓
- **`--eco` deferred** (Open Question 1 unresolved) — so `discovery.find_r_packages()` is NOT a v1 dependency, `review_ecosystem()` not built. Recorded in command file + CHANGELOG + .STATUS. ✓
- **`deps_sync` reuse clarified**: it has an *importFrom* parser (reused as `_imported_symbols` in `check_methods`) but **no export parser** — `check_class_docs` adds a new `export()`/`@export` parser mirroring `deps_sync`'s regex style. Flagged in Task 6 note. ✓

**Placeholder scan:** all code shown literally — `lib/s7review.py` is complete across Tasks 2–7 (skeleton + 5 real `check_*` replacing stubs); fixtures, command file, test file, smoke helper all full. CHANGELOG/.STATUS/CLAUDE.md edits give exact strings. `<VER>` is the only intentional placeholder (resolved at Task 10 by `current + 1 minor`). No `TODO`/"implement X". ✓

**Type/name consistency:**
- Envelope key set identical to `cranlint._envelope`: `{kind,status,findings,messages,engine_missing}` ✓
- Stage kinds: `naming`/`validators`/`methods`/`legacy`/`docs`; roll-up kind `s7review` — consistent across `run_all`, `_CHECKS`, command file table, smoke helper, tests ✓
- Function names `check_naming`/`check_validators`/`check_methods`/`check_legacy_oop`/`check_class_docs`/`run_all` consistent between skeleton stubs, replacements, `_CHECKS`, `_main`, and tests ✓
- CLI `--kind` choices (`all|naming|validators|methods|legacy|docs`) match the command-file `arguments:`, the `## Usage`, and `_CHECKS` keys ✓
- `_S7_VOCAB` keys (`new_class`/`new_generic`/`method`/`class_prefix`/`register`) referenced consistently in parser, `check_methods` (register), `check_class_docs` (class_prefix) ✓
```


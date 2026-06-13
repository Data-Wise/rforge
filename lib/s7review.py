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

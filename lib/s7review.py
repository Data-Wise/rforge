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


# ── temporary stubs (each replaced in its own task) ──
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


# ── temporary stubs (each replaced in its own task) ──
# first identifier argument to method(generic, Class)
_METHOD_GENERIC_RE = re.compile(r"^\s*([A-Za-z.][\w.]*)")
# imported symbols: importFrom(pkg, sym) / @importFrom pkg sym
_NS_IMPORTFROM_SYM_RE = re.compile(r"^\s*importFrom\(\s*[\w.]+\s*,\s*([\w.]+)")
_ROX_IMPORTFROM_SYM_RE = re.compile(r"^#'\s*@importFrom\s+[\w.]+\s+(.+)$")


def _imported_symbols(pkg_path: Path) -> set[str]:
    """Symbols imported via NAMESPACE importFrom + roxygen @importFrom in R/."""
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


# ── temporary stubs (each replaced in its own task) ──
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


# ── temporary stubs (each replaced in its own task) ──
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

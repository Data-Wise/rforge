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

from . import discovery
from . import rcmd

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


def _mask_strings_and_comments(text: str) -> str:
    """Return ``text`` with string-literal interiors and ``#`` comments blanked.

    Length-, offset- and line-preserving: every masked character becomes a
    single space (newlines are kept verbatim), so indices and line numbers
    computed on the masked text map 1:1 back to the source. The parser and the
    family regexes run on this view so that R comments and the *contents* of
    string literals can never be mistaken for code (the systemic root cause of
    the s7review false positives). String *delimiters* are preserved (only the
    interior is blanked) so ``_name_arg`` can still recognise that a quoted
    argument was present, while ``_name_arg_raw`` recovers the literal value.

    Handles ``"..."`` and ``'...'`` with backslash escapes, and ``#`` comments
    that are not themselves inside a string. R has no block comments.
    """
    out = list(text)
    i = 0
    n = len(text)
    in_str: Optional[str] = None  # the active quote char, or None
    while i < n:
        c = text[i]
        if in_str is not None:
            if c == "\\" and i + 1 < n:
                # blank the escape pair (keep newline if escaped one follows)
                out[i] = " "
                out[i + 1] = "\n" if text[i + 1] == "\n" else " "
                i += 2
                continue
            if c == in_str:
                in_str = None  # closing delimiter kept as-is
            elif c != "\n":
                out[i] = " "
            i += 1
            continue
        if c in ('"', "'"):
            in_str = c  # opening delimiter kept as-is
            i += 1
            continue
        if c == "#":
            # comment to end of line
            j = i
            while j < n and text[j] != "\n":
                out[j] = " "
                j += 1
            i = j
            continue
        i += 1
    return "".join(out)


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

    Parses a **masked** view of ``text`` (R comments and string-literal
    interiors blanked to spaces — see ``_mask_strings_and_comments``) so that a
    commented-out ``new_class(...)`` or a construct mentioned inside a string is
    never picked up. Offsets are preserved by the mask, so ``line`` numbers and
    paren matching stay accurate against the original source.

    Returns a list of ``{call, bound, args, args_raw, line}`` dicts where
    ``call`` is one of ``new_class``/``new_generic``/``method``, ``bound`` is
    the LHS variable (or ``""``), ``args`` is the masked inside-parens text
    (safe for code regexes), ``args_raw`` is the original inside-parens text
    (needed to recover string-literal names), and ``line`` is the 1-based line
    of the call. Unbalanced calls are silently skipped.
    """
    masked = _mask_strings_and_comments(text)
    out: list[dict] = []
    for m in _CALL_RE.finditer(masked):
        open_idx = m.end() - 1  # index of the '('
        close_idx = _match_balanced(masked, open_idx)
        if close_idx is None:
            continue
        out.append({
            "call": m.group(2),
            "bound": m.group(1) or "",
            "args": masked[open_idx + 1:close_idx],
            "args_raw": text[open_idx + 1:close_idx],
            "line": masked.count("\n", 0, m.start()) + 1,
        })
    return out


# ─────────────────────────── naming helpers ───────────────────────────
_UPPER_CAMEL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NAME_ARG_RE = re.compile(r'^\s*["\']([^"\']+)["\']')          # first string arg
_PROPS_OPEN_RE = re.compile(r"properties\s*=\s*list\(")
_PROP_NAME_RE = re.compile(r"(\w+)\s*=")
_VALIDATOR_RE = re.compile(r"validator\s*=\s*function")


def _name_arg(args: str) -> str:
    """First string-literal argument inside a call's arg block, or ''."""
    m = _NAME_ARG_RE.match(args)
    return m.group(1) if m else ""


def _props_block(args: str) -> str:
    """Return the *balanced* inside of a ``properties = list(...)`` block, or ''.

    Uses paren-matching (not a greedy regex) so a sibling ``validator =
    function(...)`` argument is **not** swallowed into the properties block.
    """
    m = _PROPS_OPEN_RE.search(args)
    if not m:
        return ""
    open_idx = m.end() - 1  # index of the '(' after list
    close_idx = _match_balanced(args, open_idx)
    if close_idx is None:
        return ""
    return args[open_idx + 1:close_idx]


def _prop_names(args: str) -> list[str]:
    """Property names from a ``properties = list(a = ..., b = ...)`` block."""
    block = _props_block(args)
    if not block:
        return []
    return _PROP_NAME_RE.findall(block)


def check_naming(path: str | os.PathLike = ".") -> dict:
    """Naming conventions: class UpperCamelCase + bound-var match; generic and
    property names snake_case. Advisory; ``warn`` if any finding. Never raises.
    """
    findings: list[dict] = []
    for f, text in _scan_r_files(path):
        rel = f.name
        for c in _find_s7_constructs(text):
            name = _name_arg(c["args_raw"])
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
            name = _name_arg(c["args_raw"]) or c["bound"] or "<class>"
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
                nm = _name_arg(c["args_raw"]) or c["bound"]
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
_S3_DEF_RE = re.compile(r"^\s*([A-Za-z.][\w.]*)\.([A-Za-z][\w]*)\s*<-\s*function")
# Registered-S3 markers: roxygen @exportS3Method (optionally `generic class`)
# and NAMESPACE S3method(generic, class). A method carrying either is a
# legitimately registered S3 method, not an S7-migration leftover.
_ROX_S3METHOD_RE = re.compile(r"^#'\s*@exportS3Method(?:\s+(.*))?$")
_NS_S3METHOD_RE = re.compile(r"^\s*S3method\(\s*([\w.]+)\s*,\s*([\w.]+)")


def _registered_s3_methods(pkg_path: Path) -> set[str]:
    """``generic.class`` names registered as S3 methods via NAMESPACE
    ``S3method(generic, class)`` or roxygen ``@exportS3Method generic class``.

    Returns the set of fully-qualified ``generic.class`` strings so the S7
    legacy heuristic can exempt genuinely-registered S3 methods. A bare
    ``@exportS3Method`` (no args, roxygen infers from the `.`-name on the next
    def) is recorded specially via the empty-string sentinel ``""`` so the
    caller can fall back to "the tag is present at all".
    """
    reg: set[str] = set()
    ns = pkg_path / "NAMESPACE"
    if ns.is_file():
        try:
            for line in ns.read_text(encoding="utf-8", errors="replace").splitlines():
                m = _NS_S3METHOD_RE.match(line)
                if m:
                    reg.add(f"{m.group(1)}.{m.group(2)}")
        except OSError:
            pass
    return reg


def check_legacy_oop(path: str | os.PathLike = ".") -> dict:
    """Flag pre-S7 OOP co-residing with S7. ``setClass``/``setGeneric``/
    ``representation`` → ``legacy_s4_in_s7``; ``setRefClass``/``R6Class`` →
    ``legacy_r5_in_s7``; an S3 generic definition of the *name shape*
    ``foo.<S7Class> <- function`` → ``legacy_s3_generic`` (a static heuristic on
    the method name; it does **not** inspect the body for ``UseMethod()``).

    A method that is *registered* as a real S3 method — via roxygen
    ``@exportS3Method`` immediately above it, or NAMESPACE
    ``S3method(generic, class)`` — is exempt: it is a deliberately-registered S3
    method, not a migration leftover. Comments and string literals are masked
    before scanning, so commented-out or quoted constructs never fire. Only runs
    when the package also uses ``new_class``. Never raises.
    """
    p = Path(path)
    pkg = p if (p / "R").is_dir() or p.name != "R" else p.parent
    files = list(_scan_r_files(path))
    uses_s7 = any("new_class" in _mask_strings_and_comments(text)
                  for _f, text in files)
    if not uses_s7:
        return _envelope("legacy", "ok", [],
                         ["No new_class found — not an S7 package; legacy check "
                          "skipped (absence is not a violation)."])

    # set of S7 class names defined anywhere (for the S3 heuristic)
    s7_classes: set[str] = set()
    for _f, text in files:
        for c in _find_s7_constructs(text):
            if c["call"] == "new_class":
                nm = _name_arg(c["args_raw"]) or c["bound"]
                if nm:
                    s7_classes.add(nm)
                if c["bound"]:
                    s7_classes.add(c["bound"])

    ns_registered = _registered_s3_methods(pkg)

    findings: list[dict] = []
    for f, text in files:
        rel = f.name
        masked_lines = _mask_strings_and_comments(text).splitlines()
        raw_lines = text.splitlines()
        for i, line in enumerate(masked_lines, start=1):
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
                qualified = f"{m.group(1)}.{m.group(2)}"
                # exempt registered S3 methods: NAMESPACE S3method(...) or a
                # preceding roxygen @exportS3Method tag.
                registered = qualified in ns_registered
                j = i - 2  # 0-based index of the line above the def (raw)
                while not registered and j >= 0 and (
                        raw_lines[j].lstrip().startswith("#'")
                        or not raw_lines[j].strip()):
                    if _ROX_S3METHOD_RE.match(raw_lines[j].strip()):
                        registered = True
                    j -= 1
                if registered:
                    continue
                findings.append({
                    "code": "legacy_s3_generic", "severity": "advisory",
                    "file": rel, "line": i, "symbol": m.group(0).strip(),
                    "source": "static",
                    "message": (f"S3 method '{qualified}' has the name shape of an "
                                f"S3 generic dispatching on S7 class "
                                f"'{m.group(2)}', and is not registered via "
                                "@exportS3Method / S3method() — prefer an S7 "
                                "method() over an S3 method."),
                })
    status = "warn" if findings else "ok"
    messages = [] if findings else ["No legacy OOP co-residing with S7."]
    return _envelope("legacy", status, findings, messages)


# NEW export parser (mirrors deps_sync's importFrom regex style; deps_sync has
# no export parser to reuse).
_NS_EXPORT_RE = re.compile(r"^\s*export\(\s*([\w.]+)\s*\)")
_ROX_EXPORT_RE = re.compile(r"^#'\s*@export\b")
# name = TypeExpr. The trailing ``(?![\w.:(])`` pins the capture to a *whole*
# token (no partial match) AND rejects a token that is immediately a call —
# ``label = new_property(...)``. Idiomatic S7 property wrappers
# (``new_property``/``new_union``/...) are functions whose *return* is the
# type, resolved at runtime — out of scope for a static check, so they must
# not be misread as a property type literally named "new_property". The S7
# type-constructor vocabulary is additionally whitelisted as belt-and-braces.
_PROP_TYPE_RE = re.compile(r"\w+\s*=\s*([A-Za-z.][\w.:]*)(?![\w.:(])")
_S7_TYPE_CTORS = frozenset({"new_property", "new_union", "new_class",
                            "new_S3_class", "as_class"})


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
                nm = _name_arg(c["args_raw"]) or c["bound"]
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
            name = _name_arg(c["args_raw"]) or c["bound"] or "<class>"
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
            block = _props_block(c["args"])
            if block:
                for tm in _PROP_TYPE_RE.finditer(block):
                    typ = tm.group(1)
                    base = typ.split("::")[-1]
                    if base in _S7_TYPE_CTORS:
                        continue            # new_property(...)/new_union(...) call
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


# ─────────────────────────── --eco ecosystem sweep ───────────────────────────
def run_eco(root: str | os.PathLike = ".") -> dict:
    """Run the 5 static families across **every package** in the ecosystem.

    Resolves the package set via ``discovery.detect_ecosystem`` (the single source
    of truth + the curated ``manifest_order``), runs ``run_all`` per package, and
    aggregates one envelope: a per-package breakdown plus an ecosystem roll-up
    (total findings by family, packages clean vs flagged). Ordered by
    ``manifest_order`` when present, else discovery order.

    Pure-stdlib (no R). A package that raises during its sweep is reported as a
    per-package ``warn`` rather than aborting the whole sweep — never raises.
    """
    eco = discovery.detect_ecosystem(root)
    pkgs = list(eco.packages)
    # Order by the curated manifest order when present; unknown packages keep
    # discovery order, appended after the curated ones.
    if eco.manifest_order:
        rank = {name: i for i, name in enumerate(eco.manifest_order)}
        pkgs.sort(key=lambda p: (rank.get(p.name, len(rank)), p.name))

    per_package: list[dict] = []
    by_family: dict[str, int] = {}
    for pkg in pkgs:
        try:
            env = run_all(pkg.path)
            findings = [f for s in env.get("stages", []) for f in s.get("findings", [])]
            for s in env.get("stages", []):
                if s.get("findings"):
                    by_family[s["kind"]] = by_family.get(s["kind"], 0) + len(s["findings"])
            per_package.append({
                "package": pkg.name, "path": pkg.path,
                "status": env["status"], "stages": env.get("stages", []),
                "finding_count": len(findings),
                "messages": env.get("messages", []),
            })
        except Exception as exc:  # noqa: BLE001 — advisory sweep must never abort
            per_package.append({
                "package": pkg.name, "path": pkg.path, "status": "warn",
                "stages": [], "finding_count": 0,
                "messages": [f"s7review skipped for '{pkg.name}': {exc}"],
            })

    flagged = sum(1 for p in per_package if p["status"] == "warn")
    status = "warn" if flagged else "ok"
    return {
        "kind": "s7review-eco", "status": status,
        "packages": per_package,
        "rollup": {
            "by_family": by_family,
            "packages_total": len(per_package),
            "packages_flagged": flagged,
            "packages_clean": len(per_package) - flagged,
        },
        "engine_missing": [],
    }


# ─────────────────────────── --runtime (R-backed) ───────────────────────────
def _runtime_stages(path: str | os.PathLike) -> list[dict]:
    """Run the R-backed ``s7runtime`` engine and map its JSON to the two runtime
    families ``method-dispatch`` + ``validator-runtime``.

    All R goes through ``lib.rcmd`` (this module shells out to nothing). Degrades
    to two ``warn`` stages ("runtime pass skipped: <reason>") when R / S7 is
    unavailable, the engine errors, or ``rcmd.run`` raises — never propagates.
    """
    try:
        env = rcmd.run(kind="s7runtime", path=str(path))
    except Exception as exc:  # noqa: BLE001 — runtime is advisory; never abort
        return _runtime_skipped(f"runtime pass skipped: {exc}")

    if env.get("engine_missing") or env.get("status") == "error":
        reason = "; ".join(env.get("messages", [])) or "R / S7 unavailable"
        return _runtime_skipped(f"runtime pass skipped: {reason}")

    rt = env.get("s7runtime", {})
    md_findings: list[dict] = []
    for gen in rt.get("dead_generics", []):
        md_findings.append({
            "code": "dead_generic", "severity": "advisory",
            "file": "", "line": 0, "symbol": gen, "source": "runtime",
            "message": (f"S7 generic '{gen}' has no registered method at runtime "
                        "— dispatch can never resolve (dead generic)."),
        })
    # NOTE: `method_on_missing_class` is DEFERRED — the registry can't decide it
    # from introspection alone (the R engine returns an empty placeholder list),
    # so we do not build findings for it. Only `dead_generic` is wired here.
    vr_findings: list[dict] = []
    for cls in rt.get("nonenforcing_validators", []):
        vr_findings.append({
            "code": "validator_not_enforcing", "severity": "advisory",
            "file": "", "line": 0, "symbol": cls, "source": "runtime",
            "message": (f"S7 class '{cls}' has a validator but accepted a "
                        "deliberately-invalid property value at runtime — the "
                        "validator is present but not actually enforcing."),
        })

    md = _envelope("method-dispatch",
                   "warn" if md_findings else "ok", md_findings,
                   [] if md_findings else ["S7 generics all resolve at runtime."])
    vr = _envelope("validator-runtime",
                   "warn" if vr_findings else "ok", vr_findings,
                   [] if vr_findings else ["S7 validators enforce at runtime."])
    return [md, vr]


def _runtime_skipped(reason: str) -> list[dict]:
    """Two degraded runtime stages carrying the skip reason (status ok, advisory)."""
    return [
        _envelope("method-dispatch", "ok", [], [reason]),
        _envelope("validator-runtime", "ok", [], [reason]),
    ]


def run_all_with_runtime(path: str | os.PathLike = ".") -> dict:
    """``run_all`` + the two R-backed runtime families, merged into one envelope.

    Never raises: the runtime pass degrades to advisory ``warn`` stages when R is
    unavailable, so the static result is always intact. Worst-of (ok<warn) status.
    """
    static = run_all(path)
    stages = list(static.get("stages", [])) + _runtime_stages(path)
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
    parser.add_argument(
        "--eco", action="store_true",
        help="run the static families across every package in the ecosystem "
             "manifest, aggregated (pure-stdlib; composes with --runtime).")
    parser.add_argument(
        "--runtime", action="store_true",
        help="add an R-backed runtime pass (method-dispatch + validator-runtime) "
             "via lib.rcmd; degrades to advisory warn when R/S7 is unavailable.")
    args = parser.parse_args(argv)

    def _one(path: str) -> dict:
        if args.kind != "all":
            return _CHECKS[args.kind](path)
        return run_all_with_runtime(path) if args.runtime else run_all(path)

    if args.eco:
        if args.runtime:
            # ecosystem sweep + per-package runtime pass.
            eco = run_eco(args.path)
            for pkg in eco["packages"]:
                pkg["stages"] = list(pkg.get("stages", [])) + _runtime_stages(pkg["path"])
                pkg["status"] = ("warn"
                                 if any(s["status"] == "warn" for s in pkg["stages"])
                                 else pkg["status"])
            eco["status"] = ("warn" if any(p["status"] == "warn"
                                           for p in eco["packages"]) else "ok")
            env = eco
        else:
            env = run_eco(args.path)
    else:
        env = _one(args.path)

    if args.format == "text":
        print(f"{env['kind']}: {env['status']}")
        if env.get("kind") == "s7review-eco":
            for pkg in env.get("packages", []):
                print(f"  {pkg['status']:>4}  {pkg['package']} "
                      f"({pkg.get('finding_count', 0)} findings)")
            return 0
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

"""Static documentation-content audit for an R package (pure-stdlib, no R).

Backs `/rforge:docs:check`. Checks the *prose and code in the docs* against what
the package actually exports, which is what a manual doc audit looks for:

- ``signature-named-arg`` (error): a named argument in a documented call to an
  exported function is not one of its formals (e.g. ``BootstrapResult(converged = TRUE)``).
- ``signature-names`` (warn): a signature listing, i.e. a backticked call that is the first cell of a
  Markdown table row (``| `joint_effects(x, theta)` | … |``), names bare arguments that are not formals.
  Spans elsewhere are call examples whose identifiers are variables, so they are not judged.
- ``signature-arity`` (warn): a call passes more positional arguments than the
  function has formals.

All three skip functions whose usage has a ``...`` formal (any name or count is
valid there). The audit is a candidate generator, not an oracle: it only sees
calls to exported functions whose ``man/*.Rd`` usage it can parse, and it reports
how many exports that covers ("checked N of M").

CLI::

    python3 -m lib.docaudit --path <package-dir> [--format text|json]

Run as a package module (``python3 -m lib.docaudit``), never as a script.
"""

from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from .s7review import _mask_strings_and_comments

IMPLEMENTED_CHECKS = frozenset({"signature-named-arg", "signature-names", "signature-arity"})

_SEVERITY_ORDER = {"info": 0, "warn": 1, "error": 2}
_IDENT = r"[A-Za-z.][\w.]*"
_DOC_SUFFIXES = {".md", ".qmd", ".rmd", ".rmarkdown"}
_MAX_REGION = 200_000  # chars; larger blocks are skipped
_WORK_BUDGET = 2_000_000  # chars handed to split_args per region; nested calls rescan their arguments (O(n x depth))


class _BudgetExceeded(Exception):
    pass


def _read(path: Path, notes: list, root: Optional[Path] = None) -> str:
    """File text. An unreadable file yields "" **and a note** (which marks the audit incomplete):
    the audit never raises on a bad file, but it must never read as a clean one either."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        try:
            shown = path.relative_to(root).as_posix() if root else path.name
        except ValueError:
            shown = path.name
        notes.append(f"{shown} unreadable: {type(exc).__name__}: {exc}")
        return ""


_RAW_OPEN = re.compile(r"(?<![\w.])[rR](?P<q>[\"'])(?P<d>-*)(?P<o>[(\[{])")
_RAW_CLOSE = {"(": ")", "[": "]", "{": "}"}


def blank_raw_strings(text: str) -> str:
    """Blank R raw string constants (``r"(...)"``, ``R"---[...]---"``, any quote): their contents are
    text, never code, and the string masker would mistake the embedded quotes for string boundaries."""
    out, pos = [], 0
    for m in _RAW_OPEN.finditer(text):
        if m.start() < pos:
            continue
        closer = _RAW_CLOSE[m.group("o")] + m.group("d") + m.group("q")
        end = text.find(closer, m.end())
        end = len(text) if end == -1 else end + len(closer)
        out.append(text[pos:m.start()])
        out.append("".join(c if c == "\n" else " " for c in text[m.start():end]))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _mask(text: str) -> str:
    return _mask_strings_and_comments(blank_raw_strings(text))


# ───────────────────────── small parsing helpers ─────────────────────────


def _balanced_close(text: str, open_idx: int, open_ch: str = "(", close_ch: str = ")") -> int:
    """Index of the bracket closing the one at `open_idx`, or -1 if unbalanced."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def paren_map(text: str) -> dict[int, int]:
    """Index of each ``(`` -> index of its matching ``)``, in one linear pass. Unmatched ``(`` are absent."""
    stack: list[int] = []
    out: dict[int, int] = {}
    for i, ch in enumerate(text):
        if ch == "(":
            stack.append(i)
        elif ch == ")" and stack:
            out[stack.pop()] = i
    return out


def split_spans(masked: str) -> list[tuple[int, int]]:
    """``(start, end)`` of each top-level comma-separated segment (whitespace-trimmed, empty ones dropped)."""
    bounds, depth, start = [], 0, 0
    for i, ch in enumerate(masked):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            bounds.append((start, i))
            start = i + 1
    bounds.append((start, len(masked)))
    out = []
    for s, e in bounds:
        while s < e and masked[s].isspace():
            s += 1
        while e > s and masked[e - 1].isspace():
            e -= 1
        if s < e:
            out.append((s, e))
    return out


def split_args(masked: str) -> list[str]:
    """Split a masked argument list on top-level commas. Empty segments are kept out."""
    return [masked[s:e] for s, e in split_spans(masked)]


_TAG = re.compile(rf"""\s*(?:"(?P<dq>[^"\\]*)"|'(?P<sq>[^'\\]*)'|`(?P<bt>[^`]*)`|(?P<id>{_IDENT}))\s*=(?!=)""")


def _named(arg: str) -> Optional[str]:
    """Argument name when `arg` (raw, unmasked) is ``name = value``, ``"name" = value`` or
    ```name` = value`` (not ``==``), else None. R accepts quoted and backticked tags."""
    m = _TAG.match(arg)
    return next((v for v in m.groups() if v is not None), None) if m else None


# ───────────────────────── Rd / NAMESPACE ─────────────────────────


@dataclass
class PackageApi:
    formals: dict[str, list[str]]  # exported function -> formals (from Rd \usage)
    exports: set[str]
    methods: set[str]  # `generic.class` names documented via \method
    reexports: set[str]
    export_pattern: bool
    notes: list[str] = field(default_factory=list)  # Rd files skipped for size/work


def _usage_block(rd: str) -> Optional[str]:
    i = rd.find("\\usage{")
    if i == -1:
        return None
    start = i + len("\\usage")
    depth, j = 0, start
    while j < len(rd):
        c = rd[j]
        if c == "\\":
            j += 2  # `\{` and `\}` are escaped, not braces
            continue
        depth += c == "{"
        depth -= c == "}"
        if depth == 0:
            return rd[start + 1:j]
        j += 1
    return None


def parse_rd_usage(rd: str) -> tuple[dict[str, list[str]], set[str]]:
    """Function -> formals from one Rd file's ``\\usage``, plus ``generic.class`` method names."""
    block = _usage_block(rd)
    if block is None:
        return {}, set()
    block = re.sub(r"(?<!\\)%.*", "", block)
    block = block.replace("\\dots", "...").replace("\\ldots", "...")
    if len(block) > _MAX_REGION:
        raise _BudgetExceeded
    methods = {f"{g}.{c}" for g, c in re.findall(r"\\(?:S3)?method\{([^}]*)\}\{([^}]*)\}", block)}
    masked = _mask(block)  # string defaults such as `sep = ")"` must not split or close the call
    funcs: dict[str, list[str]] = {}
    closes = paren_map(masked)
    budget = _WORK_BUDGET
    for m in re.finditer(rf"(?m)^\s*({_IDENT})\(", masked):
        close = closes.get(m.end() - 1, -1)
        if close == -1:
            continue
        budget -= close - m.end()
        if budget < 0:
            raise _BudgetExceeded
        funcs[m.group(1)] = [a.split("=")[0].strip().strip("`'\"") for a in split_args(masked[m.end():close])]
    return funcs, methods


def parse_namespace(text: str) -> tuple[set[str], bool]:
    text = re.sub(r"(?m)#.*$", "", text)
    exports: set[str] = set()
    for body in re.findall(r"\bexport\(([^)]*)\)", text):
        exports.update(n.strip().strip("\"'`") for n in body.split(",") if n.strip())
    return exports, "exportPattern(" in text


def read_api(root: Path) -> PackageApi:
    formals: dict[str, list[str]] = {}
    methods: set[str] = set()
    reexports: set[str] = set()
    notes: list[str] = []
    man = root / "man"
    for rd in sorted(p for p in man.glob("*.Rd") if p.is_file()) if man.is_dir() else []:
        text = _read(rd, notes, root)
        try:
            funcs, meths = parse_rd_usage(text)
        except _BudgetExceeded:
            notes.append(f"man/{rd.name} skipped: usage block too large or too deeply nested to scan")
            continue
        formals.update(funcs)
        methods |= meths
        if rd.name == "reexports.Rd":
            reexports |= set(re.findall(r"\\alias\{([^}]*)\}", text))
    ns = root / "NAMESPACE"
    exports, pattern = parse_namespace(_read(ns, notes, root)) if ns.is_file() else (set(), False)
    if pattern or not ns.is_file():
        exports |= set(formals)  # exports unknown: treat every documented function as exported
    return PackageApi({f: v for f, v in formals.items() if f in exports}, exports, methods, reexports, pattern, notes)


# ───────────────────────── the documentation surface ─────────────────────────


@dataclass
class Region:
    kind: str  # "fence" | "inline"
    line: int  # 1-based line of the region's first character
    text: str
    bare: bool = False  # unlabeled fence: may be console output or a transcript, so findings are warnings
    first_cell: bool = False  # inline span that is the whole first cell of a Markdown table row (a signature column)


def doc_files(root: Path) -> Iterator[Path]:
    for name in ("README.md", "README.Rmd", "README.qmd"):
        if (root / name).is_file():
            yield root / name
    vig = root / "vignettes"
    if vig.is_dir():
        yield from sorted(p for p in vig.rglob("*") if p.is_file() and p.suffix.lower() in _DOC_SUFFIXES)


_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})\s*(.*)$")


def _is_r_fence(info: str) -> bool:
    info = info.strip().strip("{}").strip().lower()
    return info == "" or info == "r" or bool(re.match(r"r\b", info)) or bool(re.match(r"r[,\s]", info))


def extract_regions(text: str) -> list[Region]:
    """R fenced blocks (``r``, ``{r ...}`` or unlabeled) and inline backtick spans."""
    regions: list[Region] = []
    fence: Optional[str] = None
    fence_r = bare = False
    buf: list[str] = []
    start = 0
    # split on \n only: str.splitlines() also breaks on \x0c, \x85 and U+2028, which would shift line numbers
    for n, line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        m = _FENCE_OPEN.match(line)
        if fence is None:
            if m:
                fence, fence_r, buf, start = m.group(1), _is_r_fence(m.group(2)), [], n + 1
                bare = not m.group(2).strip()
                continue
            for span in re.finditer(r"`([^`\n]+)`", line):
                first = bool(re.fullmatch(r"\s*\|\s*", line[:span.start()]) and re.match(r"\s*\|", line[span.end():]))
                regions.append(Region("inline", n, span.group(1), first_cell=first))
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
            if fence_r:
                regions.append(Region("fence", start, "\n".join(buf), bare))
            fence = None
        else:
            buf.append(line)
    if fence is not None and fence_r:  # unterminated fence at EOF: audit what is there
        regions.append(Region("fence", start, "\n".join(buf), bare))
    return regions


_LOCAL_DEF = re.compile(rf"(?m)(?<![\w.$@])({_IDENT})\s*(?:<<-|<-|=)\s*(?:function\b|\\\()")
_ASSIGN_DEF = re.compile(rf"""\bassign\(\s*["'](?P<n>{_IDENT})["']""")


def local_definitions(regions: list[Region]) -> frozenset:
    """Names a doc defines itself (`f <- function(...)`, `assign("f", ...)`); calls to them are not the package's."""
    names: set[str] = set()
    for r in regions:
        if r.kind == "fence" and len(r.text) <= _MAX_REGION:
            names.update(_LOCAL_DEF.findall(_mask(r.text)))
            names.update(m.group("n") for m in _ASSIGN_DEF.finditer(r.text))
    return frozenset(names)


# ───────────────────────── the checks ─────────────────────────


_CALL = re.compile(rf"(?<![\w.$@:])(?:(?P<ns>{_IDENT})\s*::\s*)?(?P<fn>{_IDENT})\(")


def unmatched_named(names: list[str], formals: list[str], dots: bool = False) -> list[tuple[str, str]]:
    """Named arguments R would reject for a function without `...`, as ``(name, reason)`` in call order.

    R argument matching: (1) exact names first, across the whole call; (2) each remaining name is
    matched partially against the formals *left over* by step 1 and must have exactly one candidate;
    (3) two arguments may not claim the same formal (reason ``duplicate``, also for repeated exact names).
    Order of the arguments does not matter. When the call forwards ``...``, the forwarded arguments may
    supply any exact match, so partial names are only rejected if they prefix no formal at all."""
    exact = {n for n in names if n in formals}
    free = [f for f in formals if f not in exact]
    seen: set[str] = set()
    seen_dots: set[str] = set()
    claimed: set[str] = set()
    bad: list[tuple[str, str]] = []
    for n in names:
        if n in exact:
            if n in seen:
                bad.append((n, "duplicate"))
            seen.add(n)
            continue
        if dots:
            if not any(f.startswith(n) for f in formals):
                bad.append((n, "unknown"))
            elif n in seen_dots:  # the same name twice cannot both be absorbed by a forwarded `...`
                bad.append((n, "duplicate"))
            seen_dots.add(n)
            continue
        candidates = [f for f in free if f.startswith(n)]
        if not candidates:
            bad.append((n, "unknown"))
        elif len(candidates) > 1:
            bad.append((n, "ambiguous"))
        elif candidates[0] in claimed:
            bad.append((n, "duplicate"))
        else:
            claimed.add(candidates[0])
    return bad


_UNPARSED = re.compile(r"#|\\|\b[rR][\"']")


def _calls(masked: str, raw: str, pkg: str, api: PackageApi) -> Iterator[tuple[str, int, list[str], list[str], bool]]:
    """Yield ``(function, offset, masked_args, raw_args)`` for each call to an exported documented function.

    Calls qualified by another namespace (``other::f``) or reached through ``$``/``@`` are skipped, with
    whitespace allowed around the operators. Raises `_BudgetExceeded` once the argument text handed to
    `split_spans` exceeds `_WORK_BUDGET`."""
    closes = paren_map(masked)
    budget = _WORK_BUDGET
    for m in _CALL.finditer(masked):
        fn, ns = m.group("fn"), m.group("ns")
        if fn not in api.formals or (ns and ns != pkg):
            continue
        j = m.start() - 1
        while j >= 0 and masked[j].isspace():
            j -= 1
        if j >= 0 and masked[j] in "$@:":
            continue  # obj$ f(...), obj@ f(...)
        close = closes.get(m.end() - 1, -1)
        if close == -1:
            continue
        budget -= close - m.end()
        if budget < 0:
            raise _BudgetExceeded
        base = m.end()
        spans = split_spans(masked[base:close])
        yield (fn, m.start("fn"), [masked[base + s:base + e] for s, e in spans],
               [raw[base + s:base + e] for s, e in spans], bool(_UNPARSED.search(raw[base:close])))


def _finding(check: str, severity: str, file: str, line: int, function: str, arg: Optional[str], message: str) -> dict:
    return {"check": check, "severity": severity, "file": file, "line": line, "function": function,
            "arg": arg, "message": message}


def check_region(region: Region, rel: str, pkg: str, api: PackageApi, local: frozenset = frozenset(),
                 notes: Optional[list] = None) -> list[dict]:
    """Findings for one region. A region skipped for size or work is reported in `notes`, never silently."""
    where = f"{rel}:{region.line}"
    if len(region.text) > _MAX_REGION:
        if notes is not None:
            notes.append(f"region at {where} skipped: {len(region.text):,} characters is over the {_MAX_REGION:,} limit")
        return []
    masked = _mask(region.text)
    newlines = [i for i, ch in enumerate(masked) if ch == "\n"]
    findings: list[dict] = []
    try:
        calls = list(_calls(masked, region.text, pkg, api))
    except _BudgetExceeded:
        if notes is not None:
            notes.append(f"region at {where} skipped: too much nested call text to scan")
        return []
    for fn, off, args, raws, unparsed in calls:
        if fn in local:
            continue
        formals = api.formals[fn]
        if "..." in formals:
            continue  # variadic: any names and any arity are valid
        line = region.line + bisect.bisect_left(newlines, off)
        shown = ", ".join(formals) or "(none)"
        positional = 0
        forwards_dots = any(a == "..." for a in args)
        names = []
        for a, raw in zip(args, raws):
            name = _named(raw)
            if name is not None:
                names.append(name)
            elif a != "...":
                positional += 1
        why = {"unknown": "has no argument `{}`", "ambiguous": "argument `{}` matches more than one formal",
               "duplicate": "argument `{}` is given more than once, or its formal is already matched"}
        for name, reason in unmatched_named(names, formals, forwards_dots):
            note = " (call contains unparsed syntax: comments, escapes or raw strings; check by hand)" if unparsed else ""
            findings.append(_finding("signature-named-arg", "warn" if unparsed else "error", rel, line, fn, name,
                                     f"`{fn}()` {why[reason].format(name)} (formals: {shown}){note}"))
        if not forwards_dots and positional > len(formals):
            findings.append(_finding("signature-arity", "warn", rel, line, fn, None,
                                     f"`{fn}()` takes {len(formals)} argument(s) but the call passes {positional} positionally (formals: {shown})"))
        if region.kind == "inline" and region.first_cell and re.fullmatch(rf"\s*(?:{_IDENT}::)?{re.escape(fn)}\(.*\)\s*", masked, re.S):
            for a in args:
                if re.fullmatch(_IDENT, a) and a not in formals:
                    findings.append(_finding("signature-names", "warn", rel, line, fn, a,
                                             f"listing of `{fn}()` names `{a}`, which is not a formal (formals: {shown})"))
    return findings


def _coverage(api: PackageApi) -> dict:
    reasons = {"no-usage": 0, "method": 0, "re-export": 0, "variadic": 0}
    checked = 0
    for name in sorted(api.exports):
        if name in api.reexports:
            reasons["re-export"] += 1
        elif name in api.formals:
            if "..." in api.formals[name]:
                reasons["variadic"] += 1
            else:
                checked += 1
        elif name in api.methods:
            reasons["method"] += 1
        else:
            reasons["no-usage"] += 1
    return {"exports": len(api.exports), "checked": checked, "unchecked": {k: v for k, v in reasons.items() if v}}


def _summary_line(cov: dict, pattern: bool) -> str:
    why = ", ".join(f"{n} {k}" for k, n in cov["unchecked"].items())
    line = f"checked {cov['checked']} of {cov['exports']} exported functions"
    if why:
        line += f" ({why} not checked)"
    if pattern:
        line += "; NAMESPACE uses exportPattern(), so every documented function was treated as exported"
    return line


# ───────────────────────── entry points ─────────────────────────


def _package_name(root: Path, notes: list) -> str:
    desc = root / "DESCRIPTION"
    if desc.is_file():
        m = re.search(r"(?m)^Package:\s*(\S+)", _read(desc, notes, root))
        if m:
            return m.group(1)
    return ""


def _envelope(findings: list, messages: list, summary: dict, incomplete: bool = False) -> dict:
    top = max((f["severity"] for f in findings), key=_SEVERITY_ORDER.get, default="none")
    return {"kind": "docaudit", "status": "warn" if findings else "ok", "max_severity": top,
            "findings": findings, "messages": messages, "summary": summary, "incomplete": incomplete,
            "engine_missing": []}


def _audit(root: Path) -> tuple[list, PackageApi, list]:
    notes: list[str] = []
    pkg = _package_name(root, notes)
    api = read_api(root)
    findings: list[dict] = []
    for f in doc_files(root):
        rel = f.relative_to(root).as_posix()
        regions = extract_regions(_read(f, notes, root))
        local = local_definitions(regions)
        for region in regions:
            for finding in check_region(region, rel, pkg, api, local, notes):
                if region.bare and finding["severity"] == "error":
                    finding["severity"] = "warn"  # an unlabeled fence may be a console transcript
                findings.append(finding)
    return findings, api, notes + api.notes


def audit_package(path: str | Path = ".") -> dict:
    root = Path(path)
    if not (root / "DESCRIPTION").is_file():
        return _envelope([], [f"not an R package (no DESCRIPTION at {root})"], {})
    try:
        findings, api, notes = _audit(root)
    except Exception as exc:  # advisory tool: never raise, whatever the input
        return {**_envelope([], [f"audit failed: {type(exc).__name__}: {exc}"], {}), "status": "warn", "audit_failed": True}
    seen: set = set()
    unique = []
    for f in sorted(findings, key=lambda f: (f["file"], f["line"], f["check"], f["function"], f["arg"] or "")):
        key = (f["check"], f["file"], f["line"], f["function"], f["arg"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    cov = _coverage(api)
    return _envelope(unique, [_summary_line(cov, api.export_pattern), *notes], cov, incomplete=bool(notes))


def format_text(report: dict) -> str:
    lines = []
    for f in report["findings"]:
        lines.append(f"{f['severity']:<5} {f['check']:<20} {f['file']}:{f['line']}  {f['message']}")
    lines += report["messages"]
    if not report["findings"]:
        lines.append("no findings")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m lib.docaudit", description=__doc__.split("\n")[0])
    ap.add_argument("--path", default=".")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    report = audit_package(args.path)
    print(json.dumps(report, indent=2) if args.format == "json" else format_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

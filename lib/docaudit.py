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
- ``scannability`` (info): a paragraph, an H2 section or a "Next Steps" heading that is hard to scan
  (thresholds are keyword arguments / CLI flags).
- ``coverage`` (warn, only with ``--since TAG``): an export added since the tag that no README/vignette mentions. The export x doc matrix is in ``summary["coverage_matrix"]``.

Findings in a file can be suppressed with ``docs.allowlist`` in ``.rforge.yaml`` (entries ``<relpath>`` or
``<relpath>::<check-id>``).

All three skip functions whose usage has a ``...`` formal (any name or count is
valid there). The audit is a candidate generator, not an oracle: it only sees
calls to exported functions whose ``man/*.Rd`` usage it can parse, and it reports
how many exports that covers ("checked N of M").

CLI::

    python3 -m lib.docaudit [--path <package-dir-or-name>] [--eco] [--detailed] [--since TAG]
        [--fail-on none|warn|error] [--format text|json]

Scope (D0): walks up from --path (default: the cwd) to the nearest DESCRIPTION; with none, sweeps the ecosystem
only if a .rforge.yaml manifest exists or --eco is given. The first output line states the resolved scope.

Run as a package module (``python3 -m lib.docaudit``), never as a script.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

from .discovery import _KIND_DECL_RE, _read_allowlist, detect_ecosystem, find_r_packages
from .s7review import _mask_strings_and_comments

IMPLEMENTED_CHECKS = frozenset({"signature-named-arg", "signature-names", "signature-arity", "scannability", "coverage"})

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


def blank_comments(text: str) -> str:
    """Blank ``#`` comments (to end of line) outside strings and backticks, keeping string contents.
    Length-preserving, so offsets still line up with the masked view; used so a comment between an
    argument's name and its ``=`` cannot hide the tag."""
    out = list(text)
    quote: Optional[str] = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quote:
            if c == "\\" and quote != "`":
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == "#":
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


_QUOTED_TAG = re.compile(r"""\s*(["']).*?\1\s*=(?!=)""", re.S)


def _unparsed_tag(raw_arg: str) -> bool:
    """A quoted tag we could not read (for example one with an escape such as ``"al\\u0070ha" = 1``)."""
    return bool(_QUOTED_TAG.match(raw_arg)) and _named(raw_arg) is None


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
        if _ASSIGNS.match(masked, close + 1):
            continue  # `f(x, how.many) <- value` is the replacement form, not the getter
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
    for rd in _list_files(man, lambda p: p.suffix == ".Rd", notes, root):
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


def _list_files(top: Path, keep, notes: list, root: Path, recursive: bool = False) -> list[Path]:
    """Sorted files under `top` that satisfy `keep`. Unlike `Path.glob`/`rglob`, a directory that cannot be
    listed is **reported** in `notes` (marking the audit incomplete) rather than silently skipped."""
    if not top.is_dir():
        return []

    def problem(exc: OSError) -> None:
        target = Path(getattr(exc, "filename", None) or top)
        try:
            shown = target.relative_to(root).as_posix()
        except ValueError:
            shown = top.name
        notes.append(f"{shown} unreadable: {type(exc).__name__}: {exc}")

    found: list[Path] = []
    if recursive:
        for dirpath, _dirs, files in os.walk(top, onerror=problem):
            found += [Path(dirpath) / f for f in files if keep(Path(f))]
    else:
        try:
            with os.scandir(top) as it:
                found = [Path(e.path) for e in it if e.is_file() and keep(Path(e.name))]
        except OSError as exc:
            problem(exc)
    return sorted(p for p in found if p.is_file())


def doc_files(root: Path, notes: list) -> Iterator[Path]:
    for name in ("README.md", "README.Rmd", "README.qmd"):
        if (root / name).is_file():
            yield root / name
    yield from _list_files(root / "vignettes", lambda p: p.suffix.lower() in _DOC_SUFFIXES, notes, root, recursive=True)


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


_ASSIGNS = re.compile(r"\s*(?:<<-|<-|=(?!=))")  # what follows the `)` of a replacement call
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
        if close == -1 or _ASSIGNS.match(masked, close + 1):
            continue  # unclosed, or a replacement call `f(x) <- v` (judged against a different signature)
        budget -= close - m.end()
        if budget < 0:
            raise _BudgetExceeded
        base = m.end()
        spans = split_spans(masked[base:close])
        raws = [raw[base + s:base + e] for s, e in spans]
        yield (fn, m.start("fn"), [masked[base + s:base + e] for s, e in spans], raws,
               any(_unparsed_tag(r) for r in raws))


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
        calls = list(_calls(masked, blank_comments(blank_raw_strings(region.text)), pkg, api))
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
            note = " (call contains a quoted argument name with escapes that was not parsed: check by hand)" if unparsed else ""
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

# ───────────────────────── scannability ─────────────────────────

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_NOT_PROSE = re.compile(r"^\s*(?:\||>|<|:::|[-*+]\s|\d+[.)]\s|\s{2,}\S|\t)")
_NEXT_STEPS = re.compile(r"next steps?:?")


def scan_prose(text: str, rel: str, max_paragraph_words: int = 110, max_section_words: int = 800,
               min_h3: int = 3) -> list[dict]:
    """``scannability`` findings (all ``info``): paragraphs over `max_paragraph_words`, H2 sections over
    `max_section_words` with fewer than `min_h3` H3 headings, and a "Next Steps" H2 that is not the last H2.

    Fenced code, front matter, tables, lists, quotes and indented text are not paragraphs; headings inside
    fences are not headings. Word counts for a section ignore fenced code."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    findings: list[dict] = []

    def add(line: int, message: str) -> None:
        findings.append(_finding("scannability", "info", rel, line, "", None, message))

    i = 0
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() in ("---", "..."):
                i = k + 1
                break
    fence: Optional[str] = None
    para_start, para_words = 0, 0
    h2s: list[dict] = []  # {"title", "line", "words", "h3"}
    section: Optional[dict] = None

    def end_paragraph() -> None:
        nonlocal para_start, para_words
        if para_start and para_words > max_paragraph_words:
            add(para_start, f"paragraph of {para_words} words (over {max_paragraph_words}): consider splitting or using a list")
        para_start = para_words = 0

    for n in range(i, len(lines)):
        line, lineno = lines[n], n + 1
        m = _FENCE_OPEN.match(line)
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
                fence = None
            continue
        if m:
            end_paragraph()
            fence = m.group(1)
            continue
        h = _HEADING.match(line)
        if h:
            end_paragraph()
            level = len(h.group(1))
            if level <= 2:
                section = None
            if level == 2:
                section = {"title": h.group(2).strip(), "line": lineno, "words": 0, "h3": 0}
                h2s.append(section)
            elif level == 3 and section is not None:
                section["h3"] += 1
            continue
        if not line.strip():
            end_paragraph()
            continue
        count = len(line.split())
        if section is not None:
            section["words"] += count
        if _NOT_PROSE.match(line) and not para_start:
            continue
        if _NOT_PROSE.match(line):  # a list/table/quote line ends the running paragraph
            end_paragraph()
            continue
        if not para_start:
            para_start = lineno
        para_words += count
    end_paragraph()
    for k, s in enumerate(h2s):
        if s["words"] > max_section_words and s["h3"] < min_h3:
            add(s["line"], f"section \"{s['title']}\" is {s['words']} words with {s['h3']} subsection(s) "
                           f"(over {max_section_words} words needs {min_h3}+ H3 headings)")
        if _NEXT_STEPS.fullmatch(s["title"].lower()) and k < len(h2s) - 1:
            add(s["line"], f"\"{s['title']}\" is followed by {len(h2s) - 1 - k} more section(s); put it last")
    return findings


# ───────────────────────── coverage and --since ─────────────────────────


_TOKEN = re.compile(r"[A-Za-z.][\w.]*")


def mention_matrix(exports: set, doc_texts: dict) -> dict:
    """export -> sorted files that mention it as a whole identifier (``my.f`` does not mention ``f``)."""
    matrix: dict[str, list[str]] = {e: [] for e in sorted(exports)}
    for rel in sorted(doc_texts):
        tokens = set(_TOKEN.findall(doc_texts[rel]))
        tokens |= {tok.rstrip(".") for tok in tokens if tok.endswith(".")}  # "call f." at a sentence end
        for e in matrix:
            if e in tokens:
                matrix[e].append(rel)
    return matrix


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)


def exports_added_since(root: Path, tag: str, current: set) -> tuple[Optional[set], Optional[str]]:
    """``(added_exports, None)``, or ``(None, reason)`` when the restriction cannot be computed."""
    if not tag or tag.startswith("-"):
        return None, "not a valid ref"
    try:
        if _git(root, "rev-parse", "--verify", "--quiet", f"{tag}^{{commit}}").returncode != 0:
            return None, "unknown ref (or not a git repository)"
        if _git(root, "cat-file", "-e", f"{tag}:./NAMESPACE").returncode != 0:
            return set(current), None  # NAMESPACE did not exist at the tag: everything is new
        shown = _git(root, "show", f"{tag}:./NAMESPACE")
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git failed: {type(exc).__name__}"
    if shown.returncode != 0:
        return None, "could not read NAMESPACE at the ref"
    old, pattern = parse_namespace(shown.stdout)
    if pattern:
        return None, "NAMESPACE at the ref uses exportPattern(), so its exports are unknown"
    return current - old, None


def _allowlist(root: Path, notes: list) -> tuple[set, set]:
    """``(whole_files, {(file, check)})`` from ``docs.allowlist``; malformed config is ignored with a note."""
    entries, malformed = _read_allowlist(root, "docs")
    if malformed:
        notes.append(".rforge.yaml docs.allowlist is malformed (expected a block list); ignored")
        return set(), set()
    files: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for entry in entries:
        path, sep, check = entry.strip().partition("::")
        path = path.strip().replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        if sep:
            pairs.add((path, check.strip()))
        else:
            files.add(path)
    return files, pairs


# ───────────────────────── entry points ─────────────────────────


def _package_name(root: Path, notes: list) -> str:
    desc = root / "DESCRIPTION"
    if desc.is_file():
        m = re.search(r"(?m)^Package:\s*(\S+)", _read(desc, notes, root))
        if m:
            return m.group(1)
    return ""


def _envelope(findings: list, messages: list, summary: dict, incomplete: bool = False, audited: bool = True) -> dict:
    top = max((f["severity"] for f in findings), key=_SEVERITY_ORDER.get, default="none")
    return {"kind": "docaudit", "status": "warn" if top in ("warn", "error") else "ok", "max_severity": top,
            "findings": findings, "messages": messages, "summary": summary, "incomplete": incomplete, "audited": audited,
            "engine_missing": []}


def _audit(root: Path, scan: dict) -> tuple[list, PackageApi, list, dict]:
    notes: list[str] = []
    pkg = _package_name(root, notes)
    api = read_api(root)
    findings: list[dict] = []
    texts: dict[str, str] = {}
    for f in doc_files(root, notes):
        rel = f.relative_to(root).as_posix()
        texts[rel] = _read(f, notes, root)
        regions = extract_regions(texts[rel])
        local = local_definitions(regions)
        for region in regions:
            for finding in check_region(region, rel, pkg, api, local, notes):
                if region.bare and finding["severity"] == "error":
                    finding["severity"] = "warn"  # an unlabeled fence may be a console transcript
                findings.append(finding)
        findings += scan_prose(texts[rel], rel, **scan)
    return findings, api, notes + api.notes, texts


def audit_package(path: str | Path = ".", *, since: Optional[str] = None, max_paragraph_words: int = 110,
                  max_section_words: int = 800, min_h3: int = 3) -> dict:
    root = Path(path)
    if not (root / "DESCRIPTION").is_file():
        return _envelope([], [f"not an R package (no DESCRIPTION at {root})"], {}, audited=False)
    try:
        findings, api, notes, texts = _audit(root, {"max_paragraph_words": max_paragraph_words,
                                                    "max_section_words": max_section_words, "min_h3": min_h3})
        covered: set = set()  # coverage is a --since report: without a tag it would flag every undocumented export
        if since is not None:
            added, why = exports_added_since(root, since, api.exports - api.reexports)
            if added is None:
                notes.append(f"--since {since}: {why}; coverage skipped")
            else:
                covered = added
        matrix = mention_matrix(covered, texts)
        for name, files in matrix.items():
            if not files:
                findings.append(_finding("coverage", "warn", "NAMESPACE", 0, name, None,
                                         f"`{name}` is exported but no README or vignette mentions it"))
        skip_files, skip_pairs = _allowlist(root, notes)
    except Exception as exc:  # advisory tool: never raise, whatever the input
        return {**_envelope([], [f"audit failed: {type(exc).__name__}: {exc}"], {}, audited=False), "status": "warn", "audit_failed": True}
    seen: set = set()
    unique = []
    suppressed = 0
    for f in sorted(findings, key=lambda f: (f["file"], f["line"], f["check"], f["function"], f["arg"] or "")):
        key = (f["check"], f["file"], f["line"], f["function"], f["arg"])
        if key in seen:
            continue
        seen.add(key)
        if f["file"] in skip_files or (f["file"], f["check"]) in skip_pairs:
            suppressed += 1
            continue
        unique.append(f)
    cov = {**_coverage(api), "suppressed": suppressed, "coverage_matrix": matrix}
    return _envelope(unique, [_summary_line(cov, api.export_pattern), *notes], cov, incomplete=bool(notes))


@dataclass
class Scope:
    """What `audit` looks at (D0). ``mode``: package | hybrid | ecosystem | none."""

    mode: str
    root: str
    packages: list
    how: str = ""  # why this scope: "walked up from X", "--eco", "manifest", ...
    reason: str = ""  # for mode "none"

    def line(self) -> str:
        if self.mode == "none":
            return f"scope: none \u2014 {self.reason}"
        how = f" ({self.how})" if self.how else ""
        if self.mode == "package":
            return f"scope: package {self.packages[0].name} at {self.packages[0]}{how}"
        if self.mode == "hybrid":
            return f"scope: hybrid root {self.packages[0].name} + {len(self.packages) - 1} nested package(s) at {self.root}{how}"
        return f"scope: ecosystem of {len(self.packages)} package(s) under {self.root}{how}"

    def to_dict(self) -> dict:
        return {"mode": self.mode, "root": self.root, "packages": [str(p) for p in self.packages],
                "how": self.how, "line": self.line()}


_NO_SCOPE = "not inside an R package \u2014 pass a package path or `--eco`"


def _nearest_package(start: Path) -> Optional[Path]:
    for d in (start, *start.parents):
        if (d / "DESCRIPTION").is_file():
            return d
    return None


def _hybrid_nested(root: Path) -> list:
    config = root / ".rforge.yaml"
    try:
        if not (config.is_file() and _KIND_DECL_RE.search(config.read_text(encoding="utf-8", errors="replace"))):
            return []
    except OSError:
        return []
    nested: list[Path] = []
    for child in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        nested += [Path(pk.path) for pk in find_r_packages(child, max_depth=2)]
    return nested


def _sweep(base: Path, how: str) -> Scope:
    pkgs = [Path(pk.path) for pk in find_r_packages(base)]
    if not pkgs:
        return Scope("none", str(base), [], reason=f"no R packages found under {base}")
    return Scope("ecosystem", str(base), pkgs, how)


def resolve_scope(path: str | Path = ".", eco: bool = False) -> Scope:
    """D0: walk up from `path` to the nearest DESCRIPTION and audit that package; with no DESCRIPTION, sweep the
    ecosystem only if a `.rforge.yaml` manifest exists or `eco` is set. `path` may also be a package name found
    under the cwd. A `kind: hybrid` root also audits its nested packages."""
    given = Path(path)
    if not given.exists():
        named = [Path(pk.path) for pk in find_r_packages(Path.cwd()) if str(path) in (pk.name, Path(pk.path).name)]
        if not named:
            return Scope("none", str(given), [], reason=f"no package or path named `{path}`")
        given = named[0]
    start = (given if given.is_dir() else given.parent).resolve()
    pkg = _nearest_package(start)
    if eco:
        base = pkg.parent if pkg is not None else start
        return _sweep(base, "--eco")
    if pkg is not None:
        nested = _hybrid_nested(pkg)
        how = "" if pkg == start else f"walked up from {start}"
        if nested:
            return Scope("hybrid", str(pkg), [pkg, *nested], how)
        return Scope("package", str(pkg), [pkg], how)
    try:
        has_manifest = detect_ecosystem(start).manifest_path is not None
    except OSError:
        has_manifest = False
    if has_manifest:
        return _sweep(start, "manifest")
    return Scope("none", str(start), [], reason=_NO_SCOPE)


def _hide_info(report: dict) -> dict:
    """Drop `info` findings (counted in ``summary["info_hidden"]``) and recompute status/max_severity."""
    shown = [f for f in report["findings"] if f["severity"] != "info"]
    summary = {**report["summary"], "info_hidden": len(report["findings"]) - len(shown)}
    top = max((f["severity"] for f in shown), key=_SEVERITY_ORDER.get, default="none")
    status = report["status"] if report.get("audit_failed") else ("warn" if top in ("warn", "error") else "ok")
    return {**report, "findings": shown, "summary": summary, "max_severity": top, "status": status}


def audit(path: str | Path = ".", *, eco: bool = False, detailed: bool = False, since: Optional[str] = None,
          max_paragraph_words: int = 110, max_section_words: int = 800, min_h3: int = 3) -> dict:
    """Audit the package (or packages) D0 resolves `path` to. `info` findings appear only when `detailed`."""
    scope = resolve_scope(path, eco)
    if not scope.packages:
        return {**_envelope([], [scope.reason], {}, audited=False), "scope": scope.to_dict()}
    reports = [(p, audit_package(p, since=since, max_paragraph_words=max_paragraph_words,
                                 max_section_words=max_section_words, min_h3=min_h3)) for p in scope.packages]
    if not detailed:
        reports = [(p, _hide_info(r)) for p, r in reports]
    if len(reports) == 1:
        return {**reports[0][1], "scope": scope.to_dict()}
    findings, messages, packages = [], [], []
    for p, r in reports:
        name = _package_name(p, []) or p.name
        findings += [{**f, "package": name} for f in r["findings"]]
        messages += [f"[{name}] {m}" for m in r["messages"]]
        packages.append({"name": name, "path": str(p), "status": r["status"], "max_severity": r["max_severity"],
                         "incomplete": r["incomplete"], "audited": r["audited"], "summary": r["summary"]})
    top = max((f["severity"] for f in findings), key=_SEVERITY_ORDER.get, default="none")
    summary = {"packages": len(reports),
               **{k: sum(r["summary"].get(k, 0) for _, r in reports) for k in ("exports", "checked", "suppressed", "info_hidden")}}
    return {"kind": "docaudit", "status": "warn" if top in ("warn", "error") or any(r.get("audit_failed") for _, r in reports) else "ok",
            "max_severity": top, "findings": findings, "messages": messages, "summary": summary,
            "incomplete": any(r["incomplete"] for _, r in reports), "audited": all(r["audited"] for _, r in reports),
            "engine_missing": [], "packages": packages, "scope": scope.to_dict()}


def audit_ecosystem(path: str | Path = ".", **kwargs) -> dict:
    """`audit` with the ecosystem sweep forced."""
    return audit(path, eco=True, **kwargs)


def format_json(report: dict) -> str:
    return json.dumps(report, indent=2)


def format_text(report: dict) -> str:
    lines = [report["scope"]["line"]] if "scope" in report else []
    for f in report["findings"]:
        where = f"{f['package']}/{f['file']}" if "package" in f else f["file"]
        lines.append(f"{f['severity']:<5} {f['check']:<20} {where}:{f['line']}  {f['message']}")
    scope_line = report["scope"]["line"] if "scope" in report else ""
    lines += [m for m in report["messages"] if not scope_line.endswith(m)]
    if report.get("audited") is False:
        lines.append("NOT AUDITED: nothing was looked at, so this is not a clean result")
    elif report.get("incomplete"):
        lines.append("INCOMPLETE: part of the package could not be audited (see above); "
                     + ("the findings listed are a lower bound" if report["findings"] else "do not read this as clean"))
    elif not report["findings"]:
        lines.append("no findings")
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m lib.docaudit", description=__doc__.split("\n")[0])
    ap.add_argument("--path", default=".", help="package path or name (default: the cwd; walks up to a DESCRIPTION)")
    ap.add_argument("--eco", action="store_true", help="sweep the whole ecosystem")
    ap.add_argument("--detailed", action="store_true", help="also print `info` findings")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--fail-on", choices=["none", "warn", "error"], default="none",
                    help="exit 1 when a finding at or above this severity exists (default: never)")
    ap.add_argument("--since", metavar="TAG", help="coverage report: exports added since TAG")
    ap.add_argument("--max-paragraph-words", type=int, default=110)
    ap.add_argument("--max-section-words", type=int, default=800)
    ap.add_argument("--min-h3", type=int, default=3, help="H3 headings an over-long H2 section needs")
    args = ap.parse_args(argv)
    report = audit(args.path, eco=args.eco, detailed=args.detailed, since=args.since,
                   max_paragraph_words=args.max_paragraph_words, max_section_words=args.max_section_words,
                   min_h3=args.min_h3)
    print(format_json(report) if args.format == "json" else format_text(report))
    level = {"none": 99, "warn": 1, "error": 2}[args.fail_on]
    return 1 if _SEVERITY_ORDER.get(report["max_severity"], -1) >= level else 0


if __name__ == "__main__":
    sys.exit(main())

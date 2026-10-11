"""Static documentation-content audit for an R package (pure-stdlib, no R).

Backs `/rforge:docs:check`. Checks the *prose and code in the docs* against what
the package actually exports, which is what a manual doc audit looks for:

- ``signature-named-arg`` (error): a named argument in a documented call to an
  exported function is not one of its formals (e.g. ``BootstrapResult(converged = TRUE)``).
- ``signature-names`` (warn): a backticked listing such as ``joint_effects(x, theta)``
  names bare arguments that are not formals.
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
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .s7review import _mask_strings_and_comments

IMPLEMENTED_CHECKS = frozenset({"signature-named-arg", "signature-names", "signature-arity"})

_SEVERITY_ORDER = {"info": 0, "warn": 1, "error": 2}
_IDENT = r"[A-Za-z.][\w.]*"
_DOC_SUFFIXES = {".md", ".qmd", ".rmd", ".rmarkdown"}


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


def split_args(masked: str) -> list[str]:
    """Split a masked argument list on top-level commas. Empty segments are kept out."""
    out, depth, cur = [], 0, []
    for ch in masked:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur).strip())
    return [a for a in out if a]


def _named(arg: str) -> Optional[str]:
    """Argument name when `arg` is ``name = value`` (not ``==``), else None."""
    m = re.match(rf"({_IDENT})\s*=(?!=)", arg)
    return m.group(1) if m else None


# ───────────────────────── Rd / NAMESPACE ─────────────────────────


@dataclass
class PackageApi:
    formals: dict[str, list[str]]  # exported function -> formals (from Rd \usage)
    exports: set[str]
    methods: set[str]  # `generic.class` names documented via \method
    reexports: set[str]
    export_pattern: bool


def _usage_block(rd: str) -> Optional[str]:
    i = rd.find("\\usage{")
    if i == -1:
        return None
    start = i + len("\\usage")
    end = _balanced_close(rd, start, "{", "}")
    return rd[start + 1:end] if end != -1 else None


def parse_rd_usage(rd: str) -> tuple[dict[str, list[str]], set[str]]:
    """Function -> formals from one Rd file's ``\\usage``, plus ``generic.class`` method names."""
    block = _usage_block(rd)
    if block is None:
        return {}, set()
    block = re.sub(r"(?<!\\)%.*", "", block)
    block = block.replace("\\dots", "...").replace("\\ldots", "...")
    methods = {f"{g}.{c}" for g, c in re.findall(r"\\(?:S3)?method\{([^}]*)\}\{([^}]*)\}", block)}
    funcs: dict[str, list[str]] = {}
    for m in re.finditer(rf"(?m)^\s*({_IDENT})\(", block):
        close = _balanced_close(block, m.end() - 1)
        if close == -1:
            continue
        funcs[m.group(1)] = [a.split("=")[0].strip() for a in split_args(block[m.end():close])]
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
    man = root / "man"
    for rd in sorted(man.glob("*.Rd")) if man.is_dir() else []:
        text = rd.read_text(encoding="utf-8", errors="replace")
        funcs, meths = parse_rd_usage(text)
        formals.update(funcs)
        methods |= meths
        if rd.name == "reexports.Rd":
            reexports |= set(re.findall(r"\\alias\{([^}]*)\}", text))
    ns = root / "NAMESPACE"
    exports, pattern = parse_namespace(ns.read_text(encoding="utf-8", errors="replace")) if ns.is_file() else (set(), False)
    if pattern or not ns.is_file():
        exports |= set(formals)  # exports unknown: treat every documented function as exported
    return PackageApi({f: v for f, v in formals.items() if f in exports}, exports, methods, reexports, pattern)


# ───────────────────────── the documentation surface ─────────────────────────


@dataclass
class Region:
    kind: str  # "fence" | "inline"
    line: int  # 1-based line of the region's first character
    text: str


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
    fence_r = False
    buf: list[str] = []
    start = 0
    for n, line in enumerate(text.splitlines(), 1):
        m = _FENCE_OPEN.match(line)
        if fence is None:
            if m:
                fence, fence_r, buf, start = m.group(1), _is_r_fence(m.group(2)), [], n + 1
                continue
            for span in re.finditer(r"`([^`\n]+)`", line):
                regions.append(Region("inline", n, span.group(1)))
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not m.group(2).strip():
            if fence_r:
                regions.append(Region("fence", start, "\n".join(buf)))
            fence = None
        else:
            buf.append(line)
    return regions


# ───────────────────────── the checks ─────────────────────────


_CALL = re.compile(rf"(?<![\w.$@:])(?:(?P<ns>{_IDENT})::)?(?P<fn>{_IDENT})\(")


def _partial_ok(name: str, formals: list[str]) -> bool:
    if name in formals:
        return True
    return sum(f.startswith(name) for f in formals) == 1


def _calls(masked: str, pkg: str, api: PackageApi) -> Iterator[tuple[str, int, list[str]]]:
    """Yield ``(function, offset, args)`` for each call to an exported documented function."""
    for m in _CALL.finditer(masked):
        fn, ns = m.group("fn"), m.group("ns")
        if fn not in api.formals or (ns and ns != pkg):
            continue
        close = _balanced_close(masked, m.end() - 1)
        if close == -1:
            continue
        yield fn, m.start("fn"), split_args(masked[m.end():close])


def _finding(check: str, severity: str, file: str, line: int, function: str, arg: Optional[str], message: str) -> dict:
    return {"check": check, "severity": severity, "file": file, "line": line, "function": function,
            "arg": arg, "message": message}


def check_region(region: Region, rel: str, pkg: str, api: PackageApi) -> list[dict]:
    masked = _mask_strings_and_comments(region.text)
    findings: list[dict] = []
    for fn, off, args in _calls(masked, pkg, api):
        formals = api.formals[fn]
        if "..." in formals:
            continue  # variadic: any names and any arity are valid
        line = region.line + masked.count("\n", 0, off)
        shown = ", ".join(formals) or "(none)"
        positional = 0
        forwards_dots = any(a == "..." for a in args)
        for a in args:
            name = _named(a)
            if name is not None:
                if not _partial_ok(name, formals):
                    findings.append(_finding("signature-named-arg", "error", rel, line, fn, name,
                                             f"`{fn}()` has no argument `{name}` (formals: {shown})"))
            elif a != "...":
                positional += 1
        if not forwards_dots and positional > len(formals):
            findings.append(_finding("signature-arity", "warn", rel, line, fn, None,
                                     f"`{fn}()` takes {len(formals)} argument(s) but the call passes {positional} positionally (formals: {shown})"))
        if region.kind == "inline" and re.fullmatch(rf"\s*(?:{_IDENT}::)?{re.escape(fn)}\(.*\)\s*", masked, re.S):
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


def _package_name(root: Path) -> str:
    desc = root / "DESCRIPTION"
    if desc.is_file():
        m = re.search(r"(?m)^Package:\s*(\S+)", desc.read_text(encoding="utf-8", errors="replace"))
        if m:
            return m.group(1)
    return ""


def _envelope(findings: list, messages: list, summary: dict) -> dict:
    top = max((f["severity"] for f in findings), key=_SEVERITY_ORDER.get, default="none")
    return {"kind": "docaudit", "status": "warn" if findings else "ok", "max_severity": top,
            "findings": findings, "messages": messages, "summary": summary, "engine_missing": []}


def audit_package(path: str | Path = ".") -> dict:
    root = Path(path)
    if not (root / "DESCRIPTION").is_file():
        return _envelope([], [f"not an R package (no DESCRIPTION at {root})"], {})
    pkg = _package_name(root)
    api = read_api(root)
    findings: list[dict] = []
    for f in doc_files(root):
        rel = f.relative_to(root).as_posix()
        for region in extract_regions(f.read_text(encoding="utf-8", errors="replace")):
            findings.extend(check_region(region, rel, pkg, api))
    seen: set = set()
    unique = []
    for f in sorted(findings, key=lambda f: (f["file"], f["line"], f["check"], f["function"], f["arg"] or "")):
        key = (f["check"], f["file"], f["line"], f["function"], f["arg"])
        if key not in seen:
            seen.add(key)
            unique.append(f)
    cov = _coverage(api)
    return _envelope(unique, [_summary_line(cov, api.export_pattern)], cov)


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

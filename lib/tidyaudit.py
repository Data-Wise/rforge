"""
Tidyverse-conventions audit — pure-Python (stdlib-only, no R) checks.

Backs `/rforge:r:tidy`'s two static-analysis stages (issue #65). Follows the
`lib/cranlint.py` archetype: each check degrades to a `warn`-status envelope
on missing/unparseable input and never raises; nothing here is ever a hard
`error` — this is a "how tidy am I?" report, not a CRAN gate.

- **`check_roxygen_completeness()`** — scans `R/*.R` for roxygen blocks
  documenting an exported (`@export`) function and flags missing
  `@examples`/`@return`/`@family` tags.
- **`check_news_header()`** — checks the top `NEWS.md` entry matches the
  `## PackageName X.Y.Z` convention and that the version matches DESCRIPTION.

Usage (CLI, from repo root):
    python3 -m lib.tidyaudit --path .

Usage (Python API):
    from lib import tidyaudit
    env = tidyaudit.check_roxygen_completeness(".")
    print(env["status"], [f["code"] for f in env["findings"]])
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# ───────────────────────── envelope helper (mirrors lib/cranlint.py) ──────


def _envelope(kind: str, status: str, findings: list, messages: list) -> dict:
    return {
        "kind": kind,
        "status": status,
        "findings": findings,
        "messages": messages,
        "engine_missing": [],
    }


# ───────────────────────── roxygen completeness ────────────────────────────

_ROXY_LINE_RE = re.compile(r"^\s*#'(.*)$")
_TAG_RE = re.compile(r"^\s*@(\S+)")
_FUNC_DEF_RE = re.compile(r"^([a-zA-Z._][a-zA-Z0-9._]*)\s*(?:<-|=)\s*function\s*\(")
_REQUIRED_TAGS = ("examples", "return", "family")


def _roxygen_blocks(text: str) -> list[dict]:
    """Extract ``{tags: set, func: str|None, start_line: int}`` per contiguous
    ``#'`` comment block immediately followed by a ``name <- function(...)``
    line (the standard no-blank-line roxygen convention)."""
    lines = text.splitlines()
    blocks: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        m = _ROXY_LINE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        start = i
        tags: set[str] = set()
        while i < n and (bm := _ROXY_LINE_RE.match(lines[i])):
            tm = _TAG_RE.match(bm.group(1))
            if tm:
                tags.add(tm.group(1))
            i += 1
        func = None
        if i < n and (fm := _FUNC_DEF_RE.match(lines[i])):
            func = fm.group(1)
        blocks.append({"tags": tags, "func": func, "start_line": start + 1})
    return blocks


def check_roxygen_completeness(path: str = ".") -> dict:
    """Advisory check: exported functions missing ``@examples``/``@return``/
    ``@family`` roxygen tags (issue #65).

    Only blocks tagged ``@export`` are checked — internal helpers are exempt.
    Returns envelope ``{kind: "roxygen_completeness", status, findings,
    messages, engine_missing: []}``.
    """
    r_dir = Path(path) / "R"
    if not r_dir.is_dir():
        return _envelope("roxygen_completeness", "warn", [],
                         ["No R/ directory found — nothing to scan."])

    findings: list[dict] = []
    for r_file in sorted(r_dir.glob("*.R")):
        try:
            text = r_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for block in _roxygen_blocks(text):
            if "export" not in block["tags"]:
                continue
            missing = [t for t in _REQUIRED_TAGS if t not in block["tags"]]
            if not missing:
                continue
            func = block["func"] or "<unknown>"
            findings.append({
                "code": "roxygen_tags_incomplete",
                "severity": "advisory",
                "file": r_file.name,
                "line": block["start_line"],
                "function": func,
                "missing_tags": missing,
                "message": (
                    f"{r_file.name}:{block['start_line']} `{func}()` is "
                    f"@export'd but missing roxygen tag(s): "
                    f"{', '.join('@' + t for t in missing)}."
                ),
            })

    status = "warn" if findings else "ok"
    messages = [] if findings else ["All exported functions have "
                                    "@examples/@return/@family."]
    return _envelope("roxygen_completeness", status, findings, messages)


# ───────────────────────── NEWS.md header ──────────────────────────────────

_VERSION_FIELD_RE = re.compile(r"^Version\s*:\s*(\S+)", re.MULTILINE)
_NEWS_HEADER_RE = re.compile(r"^#+\s*(\S+)\s+([\d.]+)\s*$")


def check_news_header(path: str = ".") -> dict:
    """Advisory check: top ``NEWS.md`` entry matches ``## Package X.Y.Z`` and
    the version matches DESCRIPTION (issue #65).

    Returns envelope ``{kind: "news_header", status, findings, messages,
    engine_missing: []}``. A missing NEWS.md is advisory, not an error — many
    packages don't keep one.
    """
    desc_path = Path(path) / "DESCRIPTION"
    news_path = Path(path) / "NEWS.md"

    if not news_path.exists():
        return _envelope("news_header", "warn", [], ["No NEWS.md found."])

    try:
        desc_text = desc_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return _envelope("news_header", "warn", [],
                         ["No DESCRIPTION found — cannot verify NEWS.md version."])
    m = _VERSION_FIELD_RE.search(desc_text)
    if not m:
        return _envelope("news_header", "warn", [],
                         ["DESCRIPTION has no Version field."])
    desc_version = m.group(1)

    news_lines = news_path.read_text(encoding="utf-8", errors="replace").splitlines()
    top = next((ln for ln in news_lines if ln.strip()), "")
    hm = _NEWS_HEADER_RE.match(top.strip())

    findings: list[dict] = []
    if not hm:
        findings.append({
            "code": "news_header_format",
            "severity": "advisory",
            "line": top,
            "message": (
                f'Top NEWS.md entry "{top}" does not match the '
                f'"## PackageName X.Y.Z" convention.'
            ),
        })
    elif hm.group(2) != desc_version:
        findings.append({
            "code": "news_header_version_mismatch",
            "severity": "advisory",
            "news_version": hm.group(2),
            "description_version": desc_version,
            "message": (
                f'Top NEWS.md entry is version {hm.group(2)}, but DESCRIPTION '
                f'is {desc_version} — NEWS.md may not have been updated for '
                f'the current release.'
            ),
        })

    status = "warn" if findings else "ok"
    messages = [] if findings else ["NEWS.md header is current and well-formed."]
    return _envelope("news_header", status, findings, messages)


# ───────────────────────── aggregate + CLI ─────────────────────────────────


def run_all(path: str = ".") -> dict:
    """Run both static-analysis stages and roll them into one envelope.

    Returns ``{kind: "tidyaudit", status, stages, engine_missing: []}``.
    Advisory-only — never ``error``.
    """
    stages = [check_roxygen_completeness(path), check_news_header(path)]
    status = "warn" if any(s["status"] == "warn" for s in stages) else "ok"
    return {"kind": "tidyaudit", "status": status, "stages": stages,
            "engine_missing": []}


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m lib.tidyaudit",
        description="Tidyverse-conventions audit (pure Python, no R).",
    )
    parser.add_argument("--path", default=".", help="Package directory (default: cwd)")
    parser.add_argument(
        "--kind",
        choices=("all", "roxygen", "news"),
        default="all",
        help="Which check to run (default: all).",
    )
    args = parser.parse_args(argv)

    if args.kind == "roxygen":
        env = check_roxygen_completeness(args.path)
    elif args.kind == "news":
        env = check_news_header(args.path)
    else:
        env = run_all(args.path)

    print(json.dumps(env, indent=2))
    return 0  # advisory — never a non-zero exit


if __name__ == "__main__":
    raise SystemExit(_main())

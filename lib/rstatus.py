"""
Single R-package session-state reader/differ.

Backs `/rforge:restore` and `/rforge:finish` (SPEC-restore-finish-commands-
2026-07-31.md). Composes existing modules rather than re-parsing what they
already parse:

- `lib.discovery.read_description` — DESCRIPTION (Package/Version/deps)
- this module's own `.STATUS` parser — the `key: value` grammar rforge's
  own `.STATUS`, craft's, and savant's all use. **Not** the same grammar as
  `lib.status.parse_status_file`, which targets an unrelated emoji-box
  format (`📋 NEXT ACTIONS`, `⏰ LAST UPDATED`, `Phase X%`) — verified live
  against rforge's own `.STATUS` during implementation: that parser returns
  empty/`None` for every field on a `key: value` file. This module's parser
  is deliberately separate, not a fork of a working parser.

Pure stdlib, read-only, no R subprocess — same tier as `discovery`/`deps`.

Usage (CLI, from an R package repo root):
    python3 -m lib.rstatus recap --path .
    python3 -m lib.rstatus recap --path . --format json

Usage (Python API):
    from lib.rstatus import build_recap
    recap = build_recap(".")
    print(recap["news"]["has_unreleased"])
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from .discovery import Description, read_description

__all__ = [
    "RStatus",
    "parse_rstatus",
    "read_rstatus",
    "parse_news_header",
    "apply_updates",
    "diff_rstatus",
    "git_snapshot",
    "build_recap",
    "format_text",
    "format_json",
]


# ───────────────────────── .STATUS (key: value grammar) ─────────────────────

# rforge/craft/savant's shared `.STATUS` convention: top-of-file
# `field: value` lines (colon-separated, one per line), distinct from
# lib.status's emoji-box grammar (see module docstring).
_FIELD_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s?(.*)$")

# Fields this module recognizes for the R-package `.STATUS` shape
# (SPEC §"R-package .STATUS scaffold shape"). Anything else in the file is
# preserved verbatim in `raw_fields` but not surfaced as a named attribute.
_KNOWN_FIELDS = (
    "package", "updated", "status", "version", "cran_status",
    "last_check", "last_release", "next", "blockers",
)


@dataclass
class RStatus:
    """Parsed `.STATUS` fields for a single R package."""

    package: Optional[str] = None
    updated: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None
    cran_status: Optional[str] = None
    last_check: Optional[str] = None
    last_release: Optional[str] = None
    next: Optional[str] = None
    blockers: Optional[str] = None
    raw_fields: dict = field(default_factory=dict)


def parse_rstatus(content: str) -> RStatus:
    """Parse `.STATUS` text (the `key: value` grammar) into an `RStatus`.

    Only the first line of a multi-line value is captured — this grammar
    (unlike the plugin-repo `.STATUS`'s multi-line `last_release:` blocks)
    is meant to stay single-line per field for the R-package shape. A
    value that continues past a single line is treated as raw_fields
    overflow rather than silently truncated: the first line goes into the
    named field, full original text stays available via `raw_fields`.
    """
    raw: dict[str, str] = {}
    known: dict[str, str] = {}
    current_key: Optional[str] = None

    for line in content.splitlines():
        if m := _FIELD_RE.match(line):
            current_key = m.group(1)
            raw[current_key] = m.group(2)
            if current_key in _KNOWN_FIELDS:
                known[current_key] = m.group(2)
        elif current_key and line.strip():
            # Continuation line — append to raw, but do not promote into
            # the single-line known-field value (see docstring).
            raw[current_key] = raw[current_key] + "\n" + line
        elif not line.strip():
            # Blank line ends the current field's continuation scope — a
            # trailing freeform notes section below a blank line is not
            # silently absorbed into whatever field happened to be last.
            current_key = None

    return RStatus(
        package=known.get("package"),
        updated=known.get("updated"),
        status=known.get("status"),
        version=known.get("version"),
        cran_status=known.get("cran_status"),
        last_check=known.get("last_check"),
        last_release=known.get("last_release"),
        next=known.get("next"),
        blockers=known.get("blockers"),
        raw_fields=raw,
    )


def read_rstatus(pkg_path: str | Path = ".") -> Optional[RStatus]:
    """Read and parse `<pkg_path>/.STATUS`. Returns None if absent/unreadable."""
    p = Path(pkg_path) / ".STATUS"
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return parse_rstatus(text)


def apply_updates(current: Optional[RStatus], **overrides) -> RStatus:
    """Build an `intended` `RStatus` by carrying every field forward from
    `current` and overriding only what's explicitly passed.

    **Always use this instead of constructing `RStatus(...)` directly** when
    building the `intended` argument to `diff_rstatus`. `RStatus` fields
    default to `None`, and `diff_rstatus` cannot distinguish "this field was
    never mentioned this session" from "this field was intentionally
    cleared" — a plain `RStatus(updated=today, version=...)` call silently
    treats every field it *didn't* set as a real change to `None`, which
    `diff_rstatus`'s redundant-edit guard does **not** catch (it only
    filters a diff whose *only* change is `updated`). That is a genuine
    data-loss bug caught during adversarial review of the very code example
    that used to live in `commands/finish.md` — this helper exists so the
    safe pattern is also the path of least resistance, not just documented
    advice a caller has to remember.
    """
    base = asdict(current) if current is not None else {}
    base.pop("raw_fields", None)
    base.update(overrides)
    return RStatus(**{k: base.get(k) for k in _KNOWN_FIELDS}, raw_fields={})


def diff_rstatus(current: Optional[RStatus], intended: RStatus) -> list[tuple[str, Optional[str], Optional[str]]]:
    """Return `(field, old, new)` for each field that would actually change.

    The redundant-edit guard: if `current` is None (no `.STATUS` file yet),
    every intended field is a change. Otherwise, a field whose only
    difference is the `updated` timestamp with nothing else in the record
    changed is filtered out — a timestamp bump with no real content delta
    is not a genuine change (doc-update-currency-check discipline).
    """
    if current is None:
        return [(k, None, v) for k, v in asdict(intended).items()
                if k != "raw_fields" and v is not None]

    changes = []
    for k in _KNOWN_FIELDS:
        old_v = getattr(current, k)
        new_v = getattr(intended, k)
        if old_v != new_v:
            changes.append((k, old_v, new_v))

    non_timestamp_changes = [c for c in changes if c[0] != "updated"]
    if not non_timestamp_changes:
        return []  # timestamp-only (or no) change — redundant, filtered out
    return changes


# ───────────────────────── NEWS.md ─────────────────────────

_NEWS_HEADER_RE = re.compile(r"^#+[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_UNRELEASED_RE = re.compile(r"unreleased", re.IGNORECASE)


def parse_news_header(pkg_path: str | Path = ".") -> dict:
    """Read the top section of `NEWS.md`. Read-only; never generates content.

    Returns `{"found": bool, "has_unreleased": bool, "top_header": str|None,
    "entries": list[str]}`. `entries` are the bullet lines directly under
    the top header (bare `-`/`*` list items), capped at the first blank
    line or next header — the same "top section only" scope `savant:restore`
    already applies to its own doc-quartet currency checks.
    """
    p = Path(pkg_path) / "NEWS.md"
    if not p.is_file():
        return {"found": False, "has_unreleased": False, "top_header": None, "entries": []}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"found": False, "has_unreleased": False, "top_header": None, "entries": []}

    headers = list(_NEWS_HEADER_RE.finditer(text))
    if not headers:
        return {"found": True, "has_unreleased": False, "top_header": None, "entries": []}

    top = headers[0]
    top_header = top.group(1).strip()
    body_end = headers[1].start() if len(headers) > 1 else len(text)
    body = text[top.end():body_end]

    entries = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*")):
            entries.append(stripped.lstrip("-* ").strip())

    return {
        "found": True,
        "has_unreleased": bool(_UNRELEASED_RE.search(top_header)),
        "top_header": top_header,
        "entries": entries,
    }


# ───────────────────────── git snapshot ─────────────────────────


def git_snapshot(pkg_path: str | Path = ".") -> dict:
    """Cheap read-only git state: branch, last commit, dirty flag.

    Never raises — any git-subprocess failure (not a repo, git missing)
    degrades to a `{"available": False}` envelope, same never-block
    posture every other rforge lib module uses for optional signals.
    """
    def _run(args: list[str]) -> Optional[str]:
        try:
            r = subprocess.run(
                ["git", *args], cwd=str(pkg_path),
                capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    branch = _run(["rev-parse", "--abbrev-ref", "HEAD"])
    if branch is None:
        return {"available": False}

    last_commit = _run(["log", "-1", "--format=%h %s"])
    dirty = _run(["status", "--porcelain"])

    return {
        "available": True,
        "branch": branch,
        "last_commit": last_commit,
        "dirty": bool(dirty),
    }


# ───────────────────────── recap composition ─────────────────────────


def build_recap(pkg_path: str | Path = ".") -> dict:
    """Compose the single-package recap `/rforge:restore` reports.

    One state read, reused for `.STATUS` currency diffing by `/rforge:finish`
    too — never re-derived twice for the same invocation.
    """
    pkg_path = Path(pkg_path)
    description = read_description(pkg_path / "DESCRIPTION")
    news = parse_news_header(pkg_path)
    rstatus = read_rstatus(pkg_path)
    git = git_snapshot(pkg_path)

    version_drift = None
    if description is not None and rstatus is not None and rstatus.version is not None:
        if rstatus.version != description.version:
            version_drift = {"status_version": rstatus.version, "description_version": description.version}

    return {
        "is_r_package": description is not None,
        "description": asdict(description) if description is not None else None,
        "news": news,
        "rstatus": asdict(rstatus) if rstatus is not None else None,
        "git": git,
        "version_drift": version_drift,
    }


_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(value: Optional[str]) -> Optional[str]:
    """Strip terminal control characters (ANSI escapes etc.) from repo-
    controlled text before it's printed. `format_text` interpolates values
    read straight out of NEWS.md/.STATUS in the target repo — content this
    module's caller does not control — so a malicious file could otherwise
    spoof terminal output (overwrite a prior line, fake a status) right
    before a `/rforge:finish --write` confirmation prompt."""
    if value is None:
        return None
    return _CONTROL_CHAR_RE.sub("", value)


def format_text(recap: dict) -> str:
    if not recap["is_r_package"]:
        return "Not an R package (no DESCRIPTION found at this path)."

    lines = []
    desc = recap["description"]
    lines.append(f"RECAP: {_sanitize(desc['package'])} (R package)")
    lines.append(f"  DESCRIPTION: v{_sanitize(desc['version'])}")

    news = recap["news"]
    if news["found"]:
        marker = "[Unreleased]" if news["has_unreleased"] else _sanitize(news["top_header"])
        lines.append(f"  NEWS.md: {marker}, {len(news['entries'])} entries")
    else:
        lines.append("  NEWS.md: not found")

    git = recap["git"]
    if git["available"]:
        dirty = " (dirty)" if git["dirty"] else ""
        lines.append(f"  git: {_sanitize(git['branch'])}{dirty} — {_sanitize(git['last_commit']) or 'no commits'}")
    else:
        lines.append("  git: not a repo, or git unavailable")

    rstatus = recap["rstatus"]
    if rstatus is not None:
        lines.append(
            f"  .STATUS: next={_sanitize(rstatus['next']) or '—'}; "
            f"blockers={_sanitize(rstatus['blockers']) or 'none'}"
        )
    else:
        lines.append("  .STATUS: not found — offer to scaffold one")

    if recap["version_drift"] is not None:
        d = recap["version_drift"]
        lines.append(
            f"  ⚠️ version drift: .STATUS says {d['status_version']}, "
            f"DESCRIPTION says {d['description_version']}"
        )

    return "\n".join(lines)


def format_json(recap: dict) -> str:
    return json.dumps(recap, indent=2, sort_keys=True)


# ───────────────────────── CLI ─────────────────────────


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m lib.rstatus")
    sub = parser.add_subparsers(dest="command", required=True)

    recap_p = sub.add_parser("recap", help="Recap a single R package's state")
    recap_p.add_argument("--path", default=".")
    recap_p.add_argument("--format", choices=["text", "json"], default="text")

    args = parser.parse_args(argv)

    if args.command == "recap":
        recap = build_recap(args.path)
        print(format_json(recap) if args.format == "json" else format_text(recap))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_main())

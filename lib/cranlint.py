"""
CRAN-incoming metadata + structure linter.

Pure-Python (stdlib-only, **no R subprocess**) checks that emulate the
*metadata + structure* scrutiny CRAN applies during its incoming-feasibility
pass — the class of issues a local `R CMD check --as-cran` run does **not**
reliably surface. Implements Tier 4 of
`docs/specs/SPEC-cran-incoming-hardening-2026-06-10.md`:

- **4a — `lint_description()`** — parse the `DESCRIPTION` DCF and emit advisory
  findings (non-`Authors@R` with no copyright holder, weak/echoed `Title`,
  `Description` that is not a complete sentence, stale `Date`). RESEARCH §A.5.
- **4b — `check_build_hygiene()`** — list top-level package entries, compile
  `.Rbuildignore` lines as case-insensitive Perl-ish regexes (matching R's
  `tools:::.Rbuildignore` semantics), and flag planning/dev docs that would
  ship in the tarball — each with the exact `.Rbuildignore` regex to add.
  RESEARCH §A.6.
- **4c — `check_planning_consistency()`** — a *small* advisory staleness /
  dangling-reference scan over in-repo planning docs. RESEARCH §A.7.

All three are **advisory**: they degrade to a `warn`-status envelope on any
missing/unparseable input and **never raise**, and they never block a
`cran-prep` `ready` verdict on their own. Each returns a dict in the rforge
house "envelope" style (mirroring `lib/rcmd.py`): `kind`, `status`
(`"ok"`/`"warn"`), a `findings` list, `messages`, and `engine_missing` (always
`[]` — there is no engine to be missing).

Usage (CLI, from repo root):
    python3 -m lib.cranlint --path .
    python3 -m lib.cranlint --path . --kind description

Usage (Python API):
    from lib import cranlint
    env = cranlint.lint_description(".")
    print(env["status"], [f["code"] for f in env["findings"]])
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ───────────────────────── DCF parsing ─────────────────────────

_FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z0-9@.]*)\s*:\s*(.*)$")


def _parse_dcf(text: str) -> dict[str, str]:
    """Parse a single-record DCF (DESCRIPTION) into a `{field: value}` dict.

    DCF is RFC822-ish: ``Field: value`` lines, with indented continuation
    lines folded onto the preceding field (newlines collapsed to spaces).
    """
    fields: dict[str, str] = {}
    key = ""
    val = ""
    for raw in text.splitlines():
        if raw and not raw[0].isspace() and (m := _FIELD_RE.match(raw)):
            if key:
                fields[key] = val.strip()
            key, val = m.group(1), m.group(2)
        elif raw.startswith((" ", "\t")) and key:
            val += " " + raw.strip()
    if key:
        fields[key] = val.strip()
    return fields


# ───────────────────────── envelope helper ─────────────────────────


def _envelope(kind: str, status: str, findings: list, messages: list) -> dict:
    """Build a house-style advisory envelope.

    Mirrors the keys `lib/rcmd.py` emits so a later integration wave can render
    these rows in `cran-prep` with minimal glue. `engine_missing` is always
    empty — these checks shell out to nothing.
    """
    return {
        "kind": kind,
        "status": status,
        "findings": findings,
        "messages": messages,
        "engine_missing": [],
    }


def _resolve_description(path) -> Optional[Path]:
    """Return the DESCRIPTION path under `path` (or `path` itself if it is one)."""
    p = Path(path)
    if p.is_file() and p.name == "DESCRIPTION":
        return p
    cand = p / "DESCRIPTION"
    return cand if cand.is_file() else None


# ───────────────────────── 4a: DESCRIPTION linter ─────────────────────────

# A title that is "Title Case-ish" has most significant words capitalised.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
# Small words that legitimately stay lower-case in title case.
_TITLE_STOPWORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of",
    "on", "or", "the", "to", "via", "with", "into", "over",
}


def _title_is_titlecaseish(title: str) -> bool:
    words = _WORD_RE.findall(title)
    if not words:
        return False
    significant = [
        w for i, w in enumerate(words)
        if i == 0 or w.lower() not in _TITLE_STOPWORDS
    ]
    if not significant:
        return False
    capped = sum(1 for w in significant if w[0].isupper())
    return capped / len(significant) >= 0.6


def _date_is_stale(value: str, *, today: Optional[datetime.date] = None) -> bool:
    """True if `value` parses to a date clearly in the past (> ~18 months)."""
    today = today or datetime.date.today()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            d = datetime.datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
        return (today - d).days > 547  # ~18 months
    return False


def lint_description(path: str | os.PathLike = ".") -> dict:
    """Lint a package `DESCRIPTION` for CRAN-incoming style nits (Tier 4a).

    Parses the DESCRIPTION DCF (pure stdlib, no R) and emits **advisory**
    findings per RESEARCH §A.5:

    - ``authors_at_r`` — ``Author``/``Maintainer`` present but no ``Authors@R``
      field (and no ``cph`` copyright-holder role anywhere) → CRAN draws an
      incoming-feasibility NOTE.
    - ``title_weak`` — ``Title`` equals the package name, is very short, or is
      not Title-Case-ish.
    - ``description_sentence`` — ``Description`` is not a complete sentence
      (no terminal period, or implausibly short).
    - ``date_stale`` — a parseable ``Date`` field that is clearly old.

    `path` may be a package directory or a DESCRIPTION file. A missing or
    unparseable DESCRIPTION degrades to a ``warn`` envelope with a clear
    message — this function never raises.

    Returns an envelope dict: ``{kind: "description", status, findings,
    messages, engine_missing: []}``. Each finding is
    ``{code, severity, field, message}``.
    """
    desc_path = _resolve_description(path)
    if desc_path is None:
        return _envelope(
            "description", "warn", [],
            ["No DESCRIPTION found — cannot lint metadata "
             "(is this an R package directory?)."],
        )
    try:
        text = desc_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return _envelope(
            "description", "warn", [],
            [f"Could not read {desc_path}: {exc}"],
        )

    fields = _parse_dcf(text)
    if not fields.get("Package"):
        return _envelope(
            "description", "warn", [],
            ["DESCRIPTION has no Package field — unparseable or not a package."],
        )

    findings: list[dict] = []

    # — Authors@R / copyright holder —
    has_authors_at_r = bool(fields.get("Authors@R"))
    has_author_or_maint = bool(fields.get("Author") or fields.get("Maintainer"))
    has_cph = "cph" in fields.get("Authors@R", "").lower()
    if not has_authors_at_r and has_author_or_maint:
        findings.append({
            "code": "authors_at_r",
            "severity": "advisory",
            "field": "Authors@R",
            "message": (
                "Uses Author/Maintainer but no Authors@R field — CRAN prefers "
                "Authors@R naming a copyright holder (role 'cph') and exactly "
                "one maintainer (role 'cre'). Convert via "
                "usethis::use_description() or hand-edit."
            ),
        })
    elif has_authors_at_r and not has_cph:
        findings.append({
            "code": "authors_at_r",
            "severity": "advisory",
            "field": "Authors@R",
            "message": (
                "Authors@R declares no copyright holder — add a person with "
                "role 'cph' (often the same as the 'cre' maintainer)."
            ),
        })

    # — Title —
    pkg = fields.get("Package", "")
    title = fields.get("Title", "")
    if not title:
        findings.append({
            "code": "title_weak", "severity": "advisory", "field": "Title",
            "message": "Title is missing.",
        })
    else:
        reasons = []
        if title.strip().lower() == pkg.strip().lower():
            reasons.append("echoes the package name")
        if len(_WORD_RE.findall(title)) < 3:
            reasons.append("is very short")
        if title.rstrip().endswith("."):
            reasons.append("ends with a period (CRAN forbids a trailing period)")
        if not _title_is_titlecaseish(title):
            reasons.append("is not Title Case")
        if reasons:
            findings.append({
                "code": "title_weak", "severity": "advisory", "field": "Title",
                "message": "Title " + "; ".join(reasons)
                           + ". CRAN's human review targets Title + Description.",
            })

    # — Description prose —
    description = fields.get("Description", "")
    if not description:
        findings.append({
            "code": "description_sentence", "severity": "advisory",
            "field": "Description", "message": "Description is missing.",
        })
    else:
        d = description.strip()
        if not d.endswith((".", "!", "?")):
            findings.append({
                "code": "description_sentence", "severity": "advisory",
                "field": "Description",
                "message": ("Description does not end in a period — it must be "
                            "one or more complete sentences."),
            })
        elif len(d) < 30 or len(_WORD_RE.findall(d)) < 5:
            findings.append({
                "code": "description_sentence", "severity": "advisory",
                "field": "Description",
                "message": ("Description is implausibly short — expand to one or "
                            "more complete, informative sentences."),
            })

    # — Stale Date —
    date_val = fields.get("Date", "")
    if date_val and _date_is_stale(date_val):
        findings.append({
            "code": "date_stale", "severity": "advisory", "field": "Date",
            "message": (f"Date '{date_val}' looks stale — update it at release "
                        "or drop the field (it is optional)."),
        })

    status = "warn" if findings else "ok"
    messages = [] if findings else ["DESCRIPTION metadata looks clean."]
    return _envelope("description", status, findings, messages)


# ───────────────────────── 4b: build hygiene ─────────────────────────

# Top-level entries R allows in a source package (Writing R Extensions /
# r-pkgs §3). Anything else draws the "non-standard top-level files" NOTE
# unless it is .Rbuildignore'd. Compared case-insensitively.
_STANDARD_TOPLEVEL = {
    "description", "namespace", "license", "license.note", "licence",
    "licence.note", "r", "man", "src", "data", "demo", "exec", "inst",
    "po", "tests", "vignettes", "tools", "configure", "configure.win",
    "configure.ac", "cleanup", "cleanup.win", "build", "news", "news.md",
    ".rbuildignore", ".rinstignore",
}

# Planning / dev-doc patterns rforge develops alongside packages — these are
# the entries that should be .Rbuildignore'd before submission.
_PLANNING_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^specs$", re.I), r"^specs$"),
    (re.compile(r"^BRAINSTORM.*\.md$", re.I), r"^BRAINSTORM.*\.md$"),
    (re.compile(r"^PROPOSAL.*\.md$", re.I), r"^PROPOSAL.*\.md$"),
    (re.compile(r"^RESEARCH.*\.md$", re.I), r"^RESEARCH.*\.md$"),
    (re.compile(r"^ORCHESTRATE.*\.md$", re.I), r"^ORCHESTRATE.*\.md$"),
    (re.compile(r"^SPEC.*\.md$", re.I), r"^SPEC.*\.md$"),
    (re.compile(r"^ROADMAP.*", re.I), r"^ROADMAP"),
    (re.compile(r"^TODO.*", re.I), r"^TODO"),
    (re.compile(r"^\.STATUS$", re.I), r"^\.STATUS$"),
    (re.compile(r"^notes$", re.I), r"^notes$"),
    (re.compile(r"^docs$", re.I), r"^docs$"),
    (re.compile(r"^CLAUDE\.md$", re.I), r"^CLAUDE\.md$"),
]


def _compile_rbuildignore(text: str) -> list[re.Pattern]:
    """Compile each non-empty, non-comment line as a case-insensitive regex.

    Matches R's ``tools:::.Rbuildignore`` semantics: each line is a
    Perl-compatible regex, applied case-insensitively against package paths.
    Lines that fail to compile are skipped (R would error, but we degrade
    gracefully — this is an advisory check).
    """
    pats: list[re.Pattern] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            pats.append(re.compile(s, re.I))
        except re.error:
            continue
    return pats


def _suggest_regex(entry: str) -> str:
    """Return the `.Rbuildignore` regex a user should add for `entry`.

    Prefers a known planning pattern (so a family like BRAINSTORM*.md gets a
    single broad rule); otherwise anchors the literal name.
    """
    for rx, suggestion in _PLANNING_PATTERNS:
        if rx.match(entry):
            return suggestion
    return "^" + re.escape(entry) + "$"


def _is_planning_entry(entry: str) -> bool:
    return any(rx.match(entry) for rx, _ in _PLANNING_PATTERNS)


def check_build_hygiene(path: str | os.PathLike = ".") -> dict:
    """Scan a package's top level for planning/dev docs that would ship (Tier 4b).

    Lists the top-level entries of the package directory, compiles each
    ``.Rbuildignore`` line as a case-insensitive Perl-ish regex (R's
    ``tools:::.Rbuildignore`` semantics, RESEARCH §A.6), and flags planning/dev
    docs (``specs/``, ``BRAINSTORM*.md``, ``PROPOSAL*.md``, ``RESEARCH*.md``,
    ``ORCHESTRATE*.md``, ``.STATUS``, ``docs/`` …) that match **neither** a
    standard R package entry **nor** any ``.Rbuildignore`` regex — i.e. files
    that would land in the built tarball and draw CRAN's "non-standard
    top-level files" NOTE.

    Report-only — no auto-fix. Each finding carries the exact ``.Rbuildignore``
    regex line to add (the ``usethis::use_build_ignore()`` equivalent). A
    missing ``.Rbuildignore`` is **not** an error: every planning doc is then
    flagged, and the stage stays a ``warn``. A missing package directory also
    degrades to ``warn``. Never raises.

    Returns an envelope: ``{kind: "build-hygiene", status, findings, messages,
    engine_missing: []}``. Each finding is
    ``{entry, code: "nonstandard_toplevel", suggest, message}``.
    """
    p = Path(path)
    if not p.is_dir():
        return _envelope(
            "build-hygiene", "warn", [],
            [f"Package directory not found: {p} — skipping build-hygiene scan."],
        )

    rbi = p / ".Rbuildignore"
    messages: list[str] = []
    if rbi.is_file():
        try:
            ignore_pats = _compile_rbuildignore(
                rbi.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            ignore_pats = []
            messages.append(f"Could not read .Rbuildignore: {exc}")
    else:
        ignore_pats = []
        messages.append(
            "No .Rbuildignore — planning/dev docs at the top level will ship "
            "in the tarball. Add the suggested lines below.")

    try:
        entries = sorted(e.name for e in p.iterdir())
    except OSError as exc:
        return _envelope(
            "build-hygiene", "warn", [],
            [f"Could not list {p}: {exc}"],
        )

    findings: list[dict] = []
    for entry in entries:
        if entry == ".Rbuildignore":
            continue
        if entry.lower() in _STANDARD_TOPLEVEL:
            continue
        # Already ignored by a .Rbuildignore regex? (R matches against the path;
        # for a top-level entry the name and a trailing-slash form both apply.)
        if any(rx.search(entry) or rx.search(entry + "/") for rx in ignore_pats):
            continue
        # Only *flag* recognised planning/dev docs — leave unknown stray files
        # to R's own NOTE rather than guessing.
        if not _is_planning_entry(entry):
            continue
        findings.append({
            "entry": entry,
            "code": "nonstandard_toplevel",
            "severity": "advisory",
            "suggest": _suggest_regex(entry),
            "message": (
                f"'{entry}' would ship in the tarball (CRAN 'non-standard "
                f"top-level files' NOTE). Add to .Rbuildignore: "
                f"{_suggest_regex(entry)}"),
        })

    status = "warn" if findings else "ok"
    if not findings and not messages:
        messages = ["No un-ignored planning/dev docs at the top level."]
    return _envelope("build-hygiene", status, findings, messages)


# ───────────────────────── 4c: planning consistency ─────────────────────────

# A planning doc whose mtime is older than this is "obviously stale".
_STALE_DAYS = 365
_PLANNING_DOC_RE = re.compile(
    r"^(SPEC|PROPOSAL|RESEARCH|BRAINSTORM|ORCHESTRATE|ROADMAP|TODO|\.STATUS)",
    re.I,
)
# A relative-looking local file/path reference inside a planning doc.
_LOCAL_REF_RE = re.compile(r"\(([A-Za-z0-9_./-]+\.md)\)")


def check_planning_consistency(path: str | os.PathLike = ".") -> dict:
    """Lightweight advisory check on in-repo planning docs (Tier 4c).

    A deliberately *small* hygiene scan over top-level planning docs
    (``SPEC*``/``PROPOSAL*``/``RESEARCH*``/``BRAINSTORM*``/``.STATUS`` …): flags
    (a) docs not touched in over a year (obviously stale) and (b) dangling
    relative ``[text](local.md)`` links that point at a sibling file which does
    not exist. This is rforge-internal hygiene, **not** a CRAN requirement.

    Advisory only — it degrades to ``warn`` on a missing directory and **never
    blocks** a `cran-prep` `ready` verdict.

    Returns an envelope: ``{kind: "docs-consistency", status, findings,
    messages, engine_missing: []}``. Each finding is
    ``{doc, code, message}`` where ``code`` is ``"stale"`` or ``"dangling_ref"``.
    """
    p = Path(path)
    if not p.is_dir():
        return _envelope(
            "docs-consistency", "warn", [],
            [f"Directory not found: {p} — skipping planning-consistency scan."],
        )

    import time

    now = time.time()
    findings: list[dict] = []
    try:
        entries = sorted(e for e in p.iterdir() if e.is_file())
    except OSError as exc:
        return _envelope(
            "docs-consistency", "warn", [],
            [f"Could not list {p}: {exc}"],
        )

    for entry in entries:
        if not _PLANNING_DOC_RE.match(entry.name):
            continue
        try:
            age_days = (now - entry.stat().st_mtime) / 86400
        except OSError:
            age_days = 0
        if age_days > _STALE_DAYS:
            findings.append({
                "doc": entry.name, "code": "stale", "severity": "advisory",
                "message": (f"'{entry.name}' was last modified "
                            f"{int(age_days)} days ago — may be stale."),
            })
        # Dangling local .md references.
        try:
            body = entry.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ref in _LOCAL_REF_RE.findall(body):
            if ref.startswith(("http://", "https://", "#")):
                continue
            target = (entry.parent / ref).resolve()
            if not target.exists():
                findings.append({
                    "doc": entry.name, "code": "dangling_ref",
                    "severity": "advisory",
                    "message": f"'{entry.name}' links to missing file '{ref}'.",
                })

    status = "warn" if findings else "ok"
    messages = [] if findings else ["Planning docs look consistent."]
    return _envelope("docs-consistency", status, findings, messages)


# ───────────────────────── aggregate + CLI ─────────────────────────


def run_all(path: str | os.PathLike = ".") -> dict:
    """Run all three Tier-4 advisory checks and roll them into one envelope.

    Returns ``{kind: "cranlint", status, stages, engine_missing: []}`` where
    ``stages`` is the list of the three per-check envelopes and ``status`` is
    the worst of (`ok` < `warn`). Advisory-only — never ``error``.
    """
    stages = [
        lint_description(path),
        check_build_hygiene(path),
        check_planning_consistency(path),
    ]
    status = "warn" if any(s["status"] == "warn" for s in stages) else "ok"
    return {
        "kind": "cranlint",
        "status": status,
        "stages": stages,
        "engine_missing": [],
    }


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m lib.cranlint",
        description="CRAN-incoming metadata + structure linter (pure Python, no R).",
    )
    parser.add_argument("--path", default=".", help="Package directory (default: cwd)")
    parser.add_argument(
        "--kind",
        choices=("all", "description", "build-hygiene", "docs-consistency"),
        default="all",
        help="Which check to run (default: all).",
    )
    args = parser.parse_args(argv)

    if args.kind == "description":
        env = lint_description(args.path)
    elif args.kind == "build-hygiene":
        env = check_build_hygiene(args.path)
    elif args.kind == "docs-consistency":
        env = check_planning_consistency(args.path)
    else:
        env = run_all(args.path)

    print(json.dumps(env, indent=2))
    return 0  # advisory — never a non-zero exit


if __name__ == "__main__":
    sys.exit(_main())

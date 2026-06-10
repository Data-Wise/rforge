"""
R ecosystem status aggregation.

Walks an ecosystem (via `discovery.py`) and produces a dashboard-style
snapshot: per-package status, ecosystem health score (0-100), and any
blocking issues. Reads each package's `.STATUS` file (if present) for
human-curated progress notes.

Pure Python — no R subprocess. Ported from
`rforge-mcp/dist/tools/discovery/status.js` (Path B Phase B.2). Check
and test statuses are stubbed as ``"unknown"`` for parity with the MCP
server; a future increment will wire them up to actual R CMD check
output.

Usage (CLI, from repo root):
    python3 -m lib.status --path . --format text
    python3 -m lib.status --path /path/to/eco --format json

Usage (Python API):
    from lib.status import aggregate_status
    snapshot = aggregate_status(".")
    print(snapshot.health_score)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .discovery import Drift, detect_ecosystem


__all__ = [
    "EcosystemStatus",
    "PackageStatus",
    "StatusFileSummary",
    "aggregate_status",
    "calculate_health_score",
    "parse_status_file",
    "format_text",
    "format_json",
]


# ───────────────────────── Dataclasses ─────────────────────────


@dataclass
class StatusFileSummary:
    """Parsed summary of a package's `.STATUS` file."""

    current_focus: Optional[str] = None
    progress: Optional[int] = None
    phase: Optional[str] = None
    just_completed: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    last_updated: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "current_focus": self.current_focus,
            "progress": self.progress,
            "phase": self.phase,
            "just_completed": list(self.just_completed),
            "next_actions": list(self.next_actions),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


@dataclass
class PackageStatus:
    """Per-package status snapshot."""

    name: str
    version: str
    path: str
    check_status: str = "unknown"
    test_status: str = "unknown"
    last_updated: Optional[datetime] = None
    status_file: Optional[StatusFileSummary] = None
    role: Optional[str] = None  # from the ecosystem manifest, when matched

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "check_status": self.check_status,
            "test_status": self.test_status,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "status_file": self.status_file.to_dict() if self.status_file else None,
            "role": self.role,
        }


@dataclass
class EcosystemStatus:
    """Aggregated ecosystem status — the public return value of `aggregate_status`.

    `blocking_issues` is `None` when blocker detection isn't implemented yet
    (deferred to v1.4.0 — see the comment in `aggregate_status`). When it
    becomes a real list, `[]` means "checked, found none" and is semantically
    distinct from `None` (not checked).
    """

    ecosystem: str
    packages: list[PackageStatus]
    health_score: int
    blocking_issues: Optional[list[str]]
    last_updated: datetime
    drift: Optional[Drift] = None  # manifest vs. on-disk mismatch, when a manifest is configured

    def to_dict(self) -> dict:
        return {
            "ecosystem": self.ecosystem,
            "packages": [p.to_dict() for p in self.packages],
            "health_score": self.health_score,
            "blocking_issues": list(self.blocking_issues) if self.blocking_issues is not None else None,
            "last_updated": self.last_updated.isoformat() if isinstance(self.last_updated, datetime) else self.last_updated,
            "drift": asdict(self.drift) if self.drift else None,
        }


# ───────────────────────── .STATUS parsing ─────────────────────────
#
# The parser is intentionally regex-only (no YAML/Markdown libs) and is
# tightly coupled to rforge's `.STATUS` template. Expected sections are
# delimited by emoji headers — `🎯 CURRENT STATUS`, `✅ JUST COMPLETED`,
# `📋 NEXT ACTIONS`, `⏰ LAST UPDATED`. Files that deviate from this
# format will parse partially (fields that don't match stay None).


_FOCUS_RE = re.compile(
    r"🎯 CURRENT STATUS\n(.+?)(?=\n[─━═]|\n\n📊|\n\n✅|$)", re.DOTALL
)
_PROGRESS_RE = re.compile(r"(\d+)%")
_PHASE_RE = re.compile(r"Phase\s+([^\n:]+):", re.IGNORECASE)
_COMPLETED_RE = re.compile(
    r"✅ JUST COMPLETED[^\n]*\n([\s\S]*?)(?=\n[─━═]|\n\n📋|\n\n🎯|$)"
)
_NEXT_RE = re.compile(r"📋 NEXT ACTIONS[^\n]*\n([\s\S]*?)(?=\n[─━═]|\n\n|$)")
_DATE_RE = re.compile(r"⏰ LAST UPDATED\s+(\d{4}-\d{2}-\d{2})")
_BULLET_LEADER_RE = re.compile(r"^[-*✅\s]+")
_NEXT_LEADER_RE = re.compile(r"^[A-Z)\d.\-*\s]+")
_NEXT_LINE_RE = re.compile(r"^[A-Z]\)|^\d\)|^[-*]")


def parse_status_file(content: str) -> StatusFileSummary:
    """Parse a `.STATUS` file's text into a `StatusFileSummary`.

    Section anchors are emoji headers (🎯, 📊, ✅, 📋, ⏰). Order is not
    significant. Missing sections leave their corresponding fields unset.
    """
    summary = StatusFileSummary()

    if m := _FOCUS_RE.search(content):
        summary.current_focus = m.group(1).strip()

    percentages = [int(m.group(1)) for m in _PROGRESS_RE.finditer(content)]
    if percentages:
        summary.progress = max(percentages)

    if m := _PHASE_RE.search(content):
        summary.phase = m.group(1).strip()

    if m := _COMPLETED_RE.search(content):
        items = []
        for line in m.group(1).splitlines():
            if "✅" in line or line.lstrip().startswith(("-", "*")):
                cleaned = _BULLET_LEADER_RE.sub("", line).strip()
                if cleaned:
                    items.append(cleaned)
        summary.just_completed = items

    if m := _NEXT_RE.search(content):
        items = []
        for line in m.group(1).splitlines():
            if _NEXT_LINE_RE.match(line):
                cleaned = _NEXT_LEADER_RE.sub("", line).strip()
                if cleaned:
                    items.append(cleaned)
        summary.next_actions = items

    if m := _DATE_RE.search(content):
        try:
            summary.last_updated = datetime.strptime(m.group(1), "%Y-%m-%d")
        except ValueError:
            summary.last_updated = None

    return summary


def _read_status_file(path: Path) -> Optional[tuple[StatusFileSummary, datetime]]:
    """Read and parse a `.STATUS` file. Returns (summary, mtime) or None."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return None
    return parse_status_file(text), mtime


# ───────────────────────── Health score ─────────────────────────


def calculate_health_score(
    packages: list[PackageStatus], now: Optional[datetime] = None
) -> int:
    """Compute the 0-100 ecosystem health score.

    Faithful port of the MCP server's algorithm: each package gets a slice
    of 100/N points, and deductions apply for unknown/failing check or
    test statuses plus a staleness penalty for `.STATUS` files older than
    14 days. Empty ecosystems are perfect (score=100) by convention — the
    MCP server returned 0 here, which conflated "no data" with "broken";
    the orchestrator chose the saner default for B.2.
    """
    if not packages:
        return 100
    when = now or datetime.now()
    per_pkg = 100 / len(packages)
    score = 100.0
    for pkg in packages:
        if pkg.check_status == "errors":
            score -= per_pkg * 0.50
        elif pkg.check_status == "warnings":
            score -= per_pkg * 0.25
        elif pkg.check_status == "notes":
            score -= per_pkg * 0.10
        elif pkg.check_status == "unknown":
            score -= per_pkg * 0.15

        if pkg.test_status == "failing":
            score -= per_pkg * 0.30
        elif pkg.test_status == "unknown":
            score -= per_pkg * 0.10

        if pkg.last_updated is not None:
            days_stale = (when - pkg.last_updated).days
            if days_stale > 14:
                score -= per_pkg * 0.10
    return max(0, round(score))


# ───────────────────────── Aggregation ─────────────────────────


def aggregate_status(ecosystem_path: str | os.PathLike = ".") -> EcosystemStatus:
    """Build an `EcosystemStatus` snapshot for the given path.

    Discovers packages via `detect_ecosystem`, reads each package's
    `.STATUS` (if present), and computes a health score.

    Raises:
        FileNotFoundError / NotADirectoryError: propagated from
            `detect_ecosystem` if `ecosystem_path` is invalid.
    """
    ecosystem = detect_ecosystem(ecosystem_path)
    packages: list[PackageStatus] = []

    for pkg in ecosystem.packages:
        status_path = Path(pkg.path) / ".STATUS"
        parsed = _read_status_file(status_path)
        if parsed is not None:
            summary, mtime = parsed
        else:
            summary, mtime = None, None
        packages.append(
            PackageStatus(
                name=pkg.name,
                version=pkg.version,
                path=pkg.path,
                check_status="unknown",
                test_status="unknown",
                last_updated=mtime,
                status_file=summary,
                role=pkg.manifest.role if pkg.manifest else None,
            )
        )

    # Blocking issues: MCP source populates this from .STATUS content
    # keywords like 'BLOCKED'; deferred until v1.4.0.
    # `None` (not `[]`) signals "not implemented yet" — an actual empty list
    # will mean "checked, found none".
    blocking_issues: Optional[list[str]] = None

    health_score = calculate_health_score(packages)

    return EcosystemStatus(
        ecosystem=ecosystem.root,
        packages=packages,
        health_score=health_score,
        blocking_issues=blocking_issues,
        last_updated=datetime.now(),
        drift=ecosystem.drift,
    )


# ───────────────────────── Formatters ─────────────────────────


def _check_icon(status: str) -> str:
    return {
        "passing": "✅",
        "errors": "❌",
        "warnings": "⚠️ ",
        "notes": "📝",
    }.get(status, "❔")


def _health_verdict(score: int) -> str:
    if score < 50:
        return "⚠️  Ecosystem needs attention"
    if score < 80:
        return "🟡 Some issues to address"
    return "✅ Ecosystem is healthy"


def _truncate(text: str, limit: int) -> str:
    """Clip `text` to `limit` chars with an ellipsis when it overflows."""
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_text(result: EcosystemStatus) -> str:
    """Terminal-friendly rendering of an `EcosystemStatus`."""
    lines: list[str] = []
    lines.append(f"📊 ECOSYSTEM STATUS: {result.ecosystem}")
    lines.append("")
    has_roles = any(p.role for p in result.packages)
    if result.packages:
        header = (
            f"{'Package':<22} {'Version':<10} {'Check':<10} {'Test':<10} {'Progress':<9}"
        )
        if has_roles:
            header += " Role"
        lines.append(header)
        lines.append("─" * (90 if has_roles else 70))
        for pkg in result.packages:
            progress = (
                f"{pkg.status_file.progress}%"
                if pkg.status_file and pkg.status_file.progress is not None
                else "--"
            )
            base = (
                f"{pkg.name:<22} {pkg.version:<10} "
                f"{_check_icon(pkg.check_status)} {pkg.check_status:<7} "
                f"{_check_icon(pkg.test_status)} {pkg.test_status:<7} "
            )
            if has_roles:
                lines.append(f"{base}{progress:<9} {_truncate(pkg.role or '', 36)}".rstrip())
            else:
                lines.append(f"{base}{progress}")
    else:
        lines.append("(no packages discovered)")
    lines.append("")
    if result.drift and (result.drift.manifest_only or result.drift.disk_only):
        lines.append("⚠️  Manifest drift")
        if result.drift.manifest_only:
            lines.append(
                f"  in manifest, not on disk: {', '.join(result.drift.manifest_only)}"
            )
        if result.drift.disk_only:
            lines.append(
                f"  on disk, not in manifest: {', '.join(result.drift.disk_only)}"
            )
        lines.append("")
    if result.blocking_issues:
        lines.append("🔴 BLOCKING ISSUES")
        for issue in result.blocking_issues:
            lines.append(f"  • {issue}")
        lines.append("")
    lines.append(f"Health score: {result.health_score}/100")
    lines.append(_health_verdict(result.health_score))
    lines.append(f"Generated: {result.last_updated.isoformat(timespec='seconds')}")
    return "\n".join(lines)


def format_json(result: EcosystemStatus) -> str:
    # `result.to_dict()` already serializes datetimes via isoformat, so the
    # `default=str` fallback should never fire on a well-formed result.
    return json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str)


# ───────────────────────── CLI ─────────────────────────


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="status",
        description="Aggregate R ecosystem status (health, packages, .STATUS).",
    )
    parser.add_argument("--path", default=".", help="Ecosystem root (default: cwd)")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args(argv)

    try:
        result = aggregate_status(args.path)
    except (FileNotFoundError, NotADirectoryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(format_json(result))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(_main())

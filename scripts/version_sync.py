#!/usr/bin/env python3
"""
Sync version + command-count strings from the canonical source (package.json).

`package.json` `"version"` is the single source of truth. This script stamps
that version — plus the `command_count` carried in `mkdocs.yml extra.rforge` —
into the handful of files that cannot use mkdocs-macros because they are read
raw (GitHub-rendered) or are build config:

  - mkdocs.yml                  extra.rforge.version + extra.rforge.command_count
  - .claude-plugin/plugin.json  "version" + "NN commands" in description
  - package.json                "NN commands" in description (version is the source)
  - README.md                   "**Version:** X.Y.Z" + "— NN commands," tagline
  - CLAUDE.md                   "## Command-file conventions (all NN commands)"

Historical references — "What's new in vX.Y.Z", CHANGELOG entries, dated
"released" notes, SPEC/RESEARCH docs, and tree-diagram "(vX.Y.Z)" comments —
are intentionally NOT touched. Only current-version / current-count strings are.

The canonical `command_count` lives in `mkdocs.yml extra.rforge.command_count`
(hardcoded for v1, CI-validated). It is bumped by hand there; every other count
string is derived from it by this script.

Usage:
    python3 scripts/version_sync.py            # write the synced strings
    python3 scripts/version_sync.py --dry-run  # show what would change, write nothing
    python3 scripts/version_sync.py --check     # exit 1 if anything is out of sync

The --check mode is the CI drift gate, mirroring scripts/gen_lib_reference.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_JSON = REPO_ROOT / "package.json"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"


@dataclass
class Rule:
    """A single regex-anchored substitution applied to one file.

    `pattern` must contain exactly the literal text to replace via two named
    groups: `pre` (kept verbatim) and `val` (the value to overwrite). The
    replacement is `pre` + the computed new value. Anchoring on `pre` keeps the
    edit surgical so historical prose is never touched.
    """

    path: Path
    pattern: str
    new_value: str
    label: str

    def apply(self, text: str) -> tuple[str, bool]:
        """Return (new_text, changed). Raises if the anchor is missing."""
        rx = re.compile(self.pattern, re.MULTILINE)
        if not rx.search(text):
            raise ValueError(
                f"anchor not found for {self.label} in "
                f"{self.path.relative_to(REPO_ROOT)} — pattern: {self.pattern!r}"
            )

        def _sub(m: re.Match) -> str:
            return m.group("pre") + self.new_value + m.group("post")

        new_text = rx.sub(_sub, text, count=1)
        return new_text, (new_text != text)


def read_version() -> str:
    """Canonical version from package.json."""
    data = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))
    return str(data["version"])


def read_command_count() -> int:
    """Canonical command count from mkdocs.yml extra.rforge.command_count."""
    text = MKDOCS_YML.read_text(encoding="utf-8")
    m = re.search(r"^\s*command_count:\s*(\d+)\s*$", text, re.MULTILINE)
    if not m:
        raise ValueError(
            "command_count not found under extra.rforge in mkdocs.yml — "
            "expected a line like `command_count: 35`"
        )
    return int(m.group(1))


def build_rules(version: str, count: int) -> list[Rule]:
    """Declarative sync rules. Each Rule has `pre`/`post` capture groups so the
    value is replaced while the surrounding anchor text is preserved verbatim."""
    n = str(count)
    return [
        # --- mkdocs.yml extra.rforge.version (authoritative render source) ---
        # Anchored on the `rforge:` parent so a future top-level/theme `version:`
        # key elsewhere in mkdocs.yml can't be clobbered by a bare first-match.
        Rule(
            MKDOCS_YML,
            r'(?P<pre>^\s*rforge:[^\n]*\n\s*version:\s*")(?P<val>[^"]*)(?P<post>")',
            version,
            "mkdocs.yml extra.rforge.version",
        ),
        # --- .claude-plugin/plugin.json "version" ---
        Rule(
            REPO_ROOT / ".claude-plugin" / "plugin.json",
            r'(?P<pre>"version":\s*")(?P<val>[^"]*)(?P<post>")',
            version,
            "plugin.json version",
        ),
        # --- .claude-plugin/plugin.json description "NN commands" ---
        Rule(
            REPO_ROOT / ".claude-plugin" / "plugin.json",
            r"(?P<pre>for Claude Code: )(?P<val>\d+)(?P<post> commands for R package)",
            n,
            "plugin.json command count",
        ),
        # --- package.json description "NN commands" (version is the source) ---
        Rule(
            PACKAGE_JSON,
            r"(?P<pre>for Claude Code: )(?P<val>\d+)(?P<post> commands for R package)",
            n,
            "package.json command count",
        ),
        # --- README.md "**Version:** X.Y.Z" footer ---
        Rule(
            REPO_ROOT / "README.md",
            r"(?P<pre>\*\*Version:\*\* )(?P<val>[0-9][0-9A-Za-z.\-]*)(?P<post>)",
            version,
            "README.md **Version:**",
        ),
        # --- README.md "— NN commands," tagline ---
        Rule(
            REPO_ROOT / "README.md",
            r"(?P<pre>orchestrator for Claude Code — )(?P<val>\d+)(?P<post> commands,)",
            n,
            "README.md command-count tagline",
        ),
        # --- CLAUDE.md "## Command-file conventions (all NN commands)" ---
        Rule(
            REPO_ROOT / "CLAUDE.md",
            r"(?P<pre>## Command-file conventions \(all )(?P<val>\d+)(?P<post> commands\))",
            n,
            "CLAUDE.md command-file-conventions heading",
        ),
    ]


def run(rules: list[Rule], *, check: bool, dry_run: bool) -> int:
    """Apply rules. In check/dry-run mode, report drift without writing.

    Returns process exit code (0 ok, 1 drift in --check)."""
    # Group rules by file so each file is read once and written once.
    drift = False
    by_file: dict[Path, list[Rule]] = {}
    for rule in rules:
        by_file.setdefault(rule.path, []).append(rule)

    for path, file_rules in by_file.items():
        original = path.read_text(encoding="utf-8")
        text = original
        changed_labels: list[str] = []
        for rule in file_rules:
            new_text, changed = rule.apply(text)
            if changed:
                changed_labels.append(rule.label)
            text = new_text

        rel = path.relative_to(REPO_ROOT)
        if text == original:
            continue

        drift = True
        if check:
            for label in changed_labels:
                print(f"DRIFT: {rel} ({label})", file=sys.stderr)
        elif dry_run:
            for label in changed_labels:
                print(f"would update: {rel} ({label})")
        else:
            path.write_text(text, encoding="utf-8")
            for label in changed_labels:
                print(f"wrote {rel} ({label})")

    if check and drift:
        print(
            "Version/count strings are stale. Run: python3 scripts/version_sync.py",
            file=sys.stderr,
        )
        return 1
    if dry_run and not drift:
        print("Everything already in sync.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any tracked string is out of sync (CI gate).",
    )
    group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    args = parser.parse_args(argv)

    version = read_version()
    count = read_command_count()
    rules = build_rules(version, count)
    return run(rules, check=args.check, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())

"""Presence gate: `docs/commands.md` must mirror the command files.

Pure stdlib. Two presence checks (no strict prose parsing — that would be
brittle; we only check that things are *present*, not phrased a certain way):

1. **Command coverage** — every non-stub command file (`commands/**/*.md`,
   excluding the v2.0.0 rename stubs doc-check/ecosystem-health/rpkg-check) has
   a section in docs/commands.md, matched on the command's slash-name
   (`/rforge:<path>`, derived from frontmatter `name:`). And every `/rforge:`
   section in commands.md has a backing command file. Both directions reported.

2. **Flag coverage** — for each command, every real CLI flag declared in its
   frontmatter `arguments:` appears as `--<name>` somewhere in that command's
   commands.md section. A frontmatter arg is *positional* (excluded) when its
   bare name is one of the six positional names this plugin uses
   (package/path/context/task_id/function/name) AND the command does not expose
   it as a `--flag` in its own slash-usage/prose (i.e. `--<name>` appears only,
   if at all, inside internal `python3 -m lib.*` invocation lines). Every other
   arg is a real CLI flag. This excludes true positionals like `<function>` /
   `<name>` and lib-only forwarded args, while still catching commands that
   genuinely take e.g. `--package` (impact/quick) or `--format`.

The core logic lives in functions returning lists of problem strings so the
pytest self-test can call them directly on fixtures (proving the gate isn't
vacuous).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = ROOT / "commands"
COMMANDS_DOC = ROOT / "docs" / "commands.md"

# v2.0.0 rename stubs — intentionally have no normal docs section.
STUB_STEMS = {"doc-check", "ecosystem-health", "rpkg-check"}

# The six string-positional argument names used across this plugin's commands.
# Such an arg is treated as a *positional* (excluded from flag coverage) UNLESS
# the command explicitly exposes it as a `--flag` in its own slash-usage/prose
# (outside internal `python3 -m lib.*` lines) — e.g. `/rforge:impact --package`.
POSITIONAL_NAMES = {"package", "path", "context", "task_id", "function", "name"}


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_block, body). Empty frontmatter if none."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def _command_name(frontmatter: str) -> str | None:
    """The `name:` frontmatter value, e.g. 'rforge:r:check'."""
    m = re.search(r"^name:\s*(\S+)", frontmatter, re.MULTILINE)
    return m.group(1) if m else None


def slash_name(frontmatter: str) -> str | None:
    """Slash-command form, e.g. '/rforge:r:check', from frontmatter name:."""
    name = _command_name(frontmatter)
    return f"/{name}" if name else None


def declared_flags(frontmatter: str, body: str) -> list[str]:
    """Bare names of real CLI flags declared in `arguments:`.

    Every declared arg is a flag, EXCEPT a positional: a positional is an arg
    whose bare name is in POSITIONAL_NAMES and that the command does not expose
    as `--<name>` in its own slash-usage/prose. "Slash-usage/prose" = the body
    with internal `python3 -m lib.*` invocation lines removed (those reference
    the lib module's flags, not the slash command's interface).
    """
    block_m = re.search(r"^arguments:\s*\n(.*)", frontmatter, re.DOTALL | re.MULTILINE)
    if not block_m:
        return []
    # Body minus internal lib invocation lines.
    non_lib = "\n".join(
        line for line in body.splitlines() if "python3 -m lib." not in line
    )
    flags: list[str] = []
    for nm in re.finditer(r"^\s*-\s*name:\s*(\S+)", block_m.group(1), re.MULTILINE):
        name = nm.group(1)
        bare = name.lstrip("-")
        if bare in POSITIONAL_NAMES:
            exposed = name.startswith("--") or re.search(
                rf"--{re.escape(bare)}\b", non_lib
            ) is not None
            if not exposed:
                continue  # genuine positional → skip
        if bare not in flags:
            flags.append(bare)
    return flags


def load_commands(commands_dir: Path) -> list[dict]:
    """Parse non-stub command files into {path, slash, flags} dicts."""
    cmds = []
    for p in sorted(commands_dir.rglob("*.md")):
        # Stubs live at commands/<stem>.md (top level), not in subdirs.
        if p.parent == commands_dir and p.stem in STUB_STEMS:
            continue
        fm, body = _split_frontmatter(p.read_text(encoding="utf-8"))
        slash = slash_name(fm)
        if slash is None:
            continue  # no frontmatter name: → can't anchor a doc section
        cmds.append({
            "path": str(p.relative_to(ROOT)),
            "slash": slash,
            "flags": declared_flags(fm, body),
        })
    return cmds


def doc_sections(doc_text: str) -> dict[str, str]:
    """Map each `### /rforge:<name>` section to its text (header → next header)."""
    sections: dict[str, str] = {}
    # Section headers look like '### /rforge:r:check'. Capture body until the
    # next header of the same-or-higher level (## or ###).
    pattern = re.compile(r"^#{2,3}\s+(/rforge:\S+)\s*$", re.MULTILINE)
    matches = list(pattern.finditer(doc_text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc_text)
        sections[m.group(1)] = doc_text[start:end]
    return sections


def find_problems(commands: list[dict], doc_text: str) -> list[str]:
    """Return a list of human-readable drift problems (empty == clean)."""
    sections = doc_sections(doc_text)
    problems: list[str] = []

    cmd_slashes = {c["slash"] for c in commands}

    # 1a. Every command file → has a section.
    for c in commands:
        if c["slash"] not in sections:
            problems.append(
                f"command coverage: {c['path']} ({c['slash']}) has no section in commands.md"
            )

    # 1b. Every /rforge: section → has a backing command file.
    for slash in sorted(sections):
        if slash not in cmd_slashes:
            problems.append(
                f"command coverage: commands.md section {slash} has no backing command file"
            )

    # 2. Flag coverage — each declared flag must appear as --flag in the section.
    for c in commands:
        section = sections.get(c["slash"])
        if section is None:
            continue  # already reported as missing section
        for flag in c["flags"]:
            if re.search(rf"--{re.escape(flag)}\b", section) is None:
                problems.append(
                    f"flag coverage: {c['slash']} --{flag} documented? no "
                    f"(declared in {c['path']})"
                )
    return problems


def main() -> int:
    commands = load_commands(COMMANDS_DIR)
    doc_text = COMMANDS_DOC.read_text(encoding="utf-8")
    problems = find_problems(commands, doc_text)
    if problems:
        print("FAIL: docs/commands.md is out of sync with command files:")
        for p in problems:
            print(f"  - {p}")
        return 1
    total_flags = sum(len(c["flags"]) for c in commands)
    print(
        f"ok: {len(commands)} commands all documented; "
        f"{total_flags} flags all covered in commands.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

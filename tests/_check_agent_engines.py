"""Validate the orchestrator agent's delegation recipes against reality.

Pure stdlib. Three checks, all against agents/orchestrator.md:

1. Every `lib.rcmd --kind X` it names is a real choice (parsed from
   `python3 -m lib.rcmd --help`).
2. Every `--kind X` it names is SAFE to auto-run — read-only, no source writes,
   no network. This enforces the agent's safety boundary structurally: the
   recommend-only commands are named as `/rforge:*` slash commands (no `--kind`
   token), so any `--kind` in the file is, by construction, an auto-run recipe
   and must be in SAFE_AUTORUN. (Catches the v2.9.0-review blockers: `document`
   and `cran-prep` are mutating and must never appear as a `--kind` auto-run.)
3. Every `lib.<module>` it references exists as a file in lib/.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agents" / "orchestrator.md"

# Read-only rcmd engines safe to auto-run: no source writes, no network.
# Excluded (mutating or network — recommend-only): document, build, install,
# site, style, cran-prep, winbuilder, rhub, revdep, goodpractice, urlcheck.
SAFE_AUTORUN = {"load", "test", "check", "coverage", "lint", "spell"}


def rcmd_kinds() -> set[str]:
    out = subprocess.run(
        [sys.executable, "-m", "lib.rcmd", "--help"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    m = re.search(r"--kind \{([^}]+)\}", out)
    if not m:
        print("could not parse --kind choices from lib.rcmd --help")
        sys.exit(1)
    return {k.strip() for k in m.group(1).split(",")}


def agent_kinds(text: str) -> set[str]:
    return set(re.findall(r"--kind\s+([a-z-]+)", text))


def agent_modules(text: str) -> set[str]:
    return set(re.findall(r"\blib\.([a-z_]+)", text))


def main() -> int:
    text = AGENT.read_text(encoding="utf-8")
    valid = rcmd_kinds()
    used_kinds = agent_kinds(text)
    used_mods = agent_modules(text)
    failed = False

    phantom = used_kinds - valid
    if phantom:
        print(f"FAIL: agent names non-existent lib.rcmd kinds: {sorted(phantom)}")
        print(f"      valid kinds: {sorted(valid)}")
        failed = True

    unsafe = used_kinds - SAFE_AUTORUN
    if unsafe:
        print(f"FAIL: agent auto-runs mutating/network kinds (must be recommend-only): {sorted(unsafe)}")
        print(f"      safe-to-auto-run: {sorted(SAFE_AUTORUN)}")
        failed = True

    missing_mods = {m for m in used_mods if not (ROOT / "lib" / f"{m}.py").exists()}
    if missing_mods:
        print(f"FAIL: agent references non-existent lib modules: {sorted(missing_mods)}")
        failed = True

    if failed:
        return 1
    print(f"ok: {len(used_kinds)} --kind tokens (all valid + safe), "
          f"{len(used_mods)} lib modules (all exist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

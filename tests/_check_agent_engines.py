"""Assert every `lib.rcmd --kind X` named in agents/orchestrator.md is a real choice.

Pure stdlib. Reads the rcmd `--kind` choices from `python3 -m lib.rcmd --help`
(the authoritative source) and compares against the `--kind` tokens the agent
prompt names. Fails if the agent references an engine that doesn't exist.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agents" / "orchestrator.md"


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


def agent_kinds() -> set[str]:
    text = AGENT.read_text(encoding="utf-8")
    return set(re.findall(r"--kind\s+([a-z-]+)", text))


def main() -> int:
    valid = rcmd_kinds()
    used = agent_kinds()
    phantom = used - valid
    if phantom:
        print(f"agent names non-existent lib.rcmd kinds: {sorted(phantom)}")
        print(f"valid kinds: {sorted(valid)}")
        return 1
    print(f"ok: {len(used)} agent --kind tokens, all valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

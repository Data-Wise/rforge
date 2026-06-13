"""Assert each use-* command's `arguments:` flags appear in its `## Usage` body."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMDS = ["use-test.md", "use-package.md", "use-vignette.md"]


def check(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    fm = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm:
        return [f"{path.name}: no frontmatter"]
    body = text[fm.end():]
    usage_m = re.search(r"## Usage(.*?)(?=\n## |\Z)", body, re.DOTALL)
    usage = usage_m.group(1) if usage_m else ""
    errs = []
    for name in re.findall(r"^\s*- name:\s*(\w+)", fm.group(1), re.MULTILINE):
        # boolean flags are the ones that must appear as --flag in Usage;
        # the positional arg (function/package/name) need not be a --flag.
        if name in ("write", "force", "article"):
            if f"--{name}" not in usage:
                errs.append(f"{path.name}: --{name} not shown in ## Usage")
    return errs


def main() -> int:
    errs = []
    for c in CMDS:
        errs += check(ROOT / "commands" / "r" / c)
    if errs:
        print("\n".join(errs))
        return 1
    print("ok: use-* arguments↔Usage in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
RForge context initialization.

Ports `rforge_init` from the MCP server (`src/tools/init/index.ts` and
`src/utils/context-manager.ts`) to a pure-Python module. Persists a
per-user JSON state file at `~/.rforge/context.json` that records the
currently-active R package, when it was first detected, and lightweight
workflow metadata that other tools (plan, release, …) read on entry.

The MCP behavior is faithfully replicated, with one deliberate addition:
production callers leave `home=None` and we resolve `$HOME`; tests pass
an explicit `home=` to redirect the state file into `tmp_path`, so the
real `~/.rforge/` is never touched.

Field names match MCP exactly (snake_case): `package`, `version`,
`path`, `detected_at`, `current_workflow`, `last_tool`, `last_plan`,
`initialized`. The `package` key is intentionally the raw name (not
`package_name`) so a context.json produced by the Node MCP server
migrates as-is.

Usage (CLI):
    python3 -m lib.init --path . --format text
    python3 -m lib.init --path /pkg --quick --format json
    python3 -m lib.init --path . --home /tmp/sandbox  # never touches real ~

Usage (API):
    from lib.init import init_context
    result = init_context(".")
    print(result.state_path, result.was_initialized)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .discovery import read_description


__all__ = [
    "InitResult",
    "init_context",
    "format_text",
    "format_json",
]


# ───────────────────────── Dataclass ─────────────────────────


@dataclass(frozen=True)
class InitResult:
    """Outcome of `init_context()`.

    Attributes:
        state_path: absolute path to the context.json that was read/written.
        was_initialized: True iff a context already existed with
            `initialized=True` and matching `path` *before* this call.
        package_name: package name from DESCRIPTION, or None if absent.
        package_version: version from DESCRIPTION, or None.
        quick_mode: True if `quick=True` was passed.
        message: human-readable summary suitable for printing.
    """

    state_path: Path
    was_initialized: bool
    package_name: Optional[str]
    package_version: Optional[str]
    quick_mode: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_path": str(self.state_path),
            "was_initialized": self.was_initialized,
            "package_name": self.package_name,
            "package_version": self.package_version,
            "quick_mode": self.quick_mode,
            "message": self.message,
        }


# ───────────────────────── State file I/O ─────────────────────────


def _resolve_home(home: Optional[str]) -> Path:
    """Resolve the effective home directory.

    `home` is the explicit override (used by tests). Production passes
    None and we fall back to `$HOME`, then `~`.
    """
    if home:
        return Path(home)
    env_home = os.environ.get("HOME") or os.environ.get("USERPROFILE")
    if env_home:
        return Path(env_home)
    return Path(os.path.expanduser("~"))


def _state_path_for(home: Optional[str]) -> Path:
    return _resolve_home(home) / ".rforge" / "context.json"


def _load_context(state_path: Path) -> Optional[dict[str, Any]]:
    """Read context.json. Returns None if missing or unreadable."""
    if not state_path.is_file():
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_context(state_path: Path, context: dict[str, Any]) -> None:
    """Atomically write context.json (write to .tmp, then rename).

    Auto-creates `~/.rforge/` with mode 0o755 if absent.
    """
    state_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(context, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp_path, state_path)


def _now_iso() -> str:
    """UTC timestamp in ISO 8601, second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ───────────────────────── Core ─────────────────────────


def init_context(
    path: str | os.PathLike = ".",
    quick: bool = False,
    home: Optional[str] = None,
) -> InitResult:
    """Initialize (or re-initialize) the rforge context for `path`.

    Args:
        path: package directory (the one containing DESCRIPTION).
        quick: if True, skip the "already initialized" short-circuit and
            re-stamp the state file. Matches MCP's `quick:true`.
        home: testability hook — overrides `$HOME` for the state path.
            Production callers pass None.

    Returns:
        InitResult describing the state file path and detection outcome.

    Raises:
        FileNotFoundError: if `path` does not exist.
        NotADirectoryError: if `path` exists but is not a directory.
            (Matches `discovery.detect_ecosystem` error semantics.)
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"path does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"path is not a directory: {resolved}")
    abs_path = str(resolved)
    state_path = _state_path_for(home)
    existing = _load_context(state_path)

    # Detect package from DESCRIPTION (None-safe — we don't require it).
    desc = read_description(Path(abs_path) / "DESCRIPTION")
    package_name = desc.package if desc else None
    package_version = desc.version if desc else None

    # Short-circuit: existing context matches this path and is initialized.
    # Explicit `is not None` checks let mypy narrow `existing` to dict without
    # the `# type: ignore` workarounds the first draft needed.
    if existing is not None:
        path_matches = existing.get("path") == abs_path
        already_init = existing.get("initialized") is True and path_matches
    else:
        path_matches = False
        already_init = False

    if already_init and not quick and existing is not None:
        return InitResult(
            state_path=state_path,
            was_initialized=True,
            package_name=existing.get("package", package_name),
            package_version=existing.get("version", package_version),
            quick_mode=quick,
            message=_format_already_message(existing),
        )

    # Build/update the context dict. Preserve detected_at across re-inits
    # on the same path; treat path mismatch as a fresh detection.
    if existing is not None and path_matches:
        context: dict[str, Any] = dict(existing)
        context.setdefault("detected_at", _now_iso())
    else:
        context = {"detected_at": _now_iso()}

    context["package"] = package_name
    context["version"] = package_version
    context["path"] = abs_path
    context["initialized"] = True
    context["last_tool"] = "init"
    # Preserve workflow + plan slots if present; default to None.
    context.setdefault("current_workflow", None)
    context.setdefault("last_plan", None)

    _write_context(state_path, context)

    mode_label = "quick" if quick else "full"
    pkg_label = f"{package_name} ({package_version})" if package_name else "(no DESCRIPTION)"
    message = (
        f"✓ rforge initialized\n"
        f"  Package: {pkg_label}\n"
        f"  Path:    {abs_path}\n"
        f"  State:   {state_path}\n"
        f"  Mode:    {mode_label}"
    )

    return InitResult(
        state_path=state_path,
        was_initialized=False,
        package_name=package_name,
        package_version=package_version,
        quick_mode=quick,
        message=message,
    )


def _format_already_message(existing: dict[str, Any]) -> str:
    pkg = existing.get("package") or "(unknown)"
    ver = existing.get("version") or "?"
    return (
        f"✓ Already initialized\n"
        f"  Package: {pkg} ({ver})\n"
        f"  Path:    {existing.get('path')}\n"
    )


# ───────────────────────── Formatters ─────────────────────────


def format_text(result: InitResult) -> str:
    return result.message


def format_json(result: InitResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str)


# ───────────────────────── CLI ─────────────────────────


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="init",
        description="Initialize rforge context for an R package directory.",
    )
    parser.add_argument("--path", default=".", help="Package directory (default: cwd)")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip the already-initialized guard and re-stamp the state file",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--home",
        default=None,
        help="Override $HOME (testability: state file goes under <home>/.rforge/)",
    )
    args = parser.parse_args(argv)

    try:
        result = init_context(path=args.path, quick=args.quick, home=args.home)
    except (FileNotFoundError, NotADirectoryError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        print(format_json(result))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(_main())

"""Shared pytest fixtures for lib/ tests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import pytest

# Make `lib/` importable as top-level (matches CLI: `python3 lib/discovery.py`)
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "lib"))


@pytest.fixture
def make_pkg(tmp_path: Path) -> Callable[..., Path]:
    """Factory: create a minimal R package directory with a DESCRIPTION file.

    Returns the package path.
    """

    def _make(
        name: str,
        version: str = "0.1.0",
        imports: list[str] | None = None,
        depends: list[str] | None = None,
        suggests: list[str] | None = None,
        linking_to: list[str] | None = None,
        parent: Path | None = None,
        extra_fields: dict[str, str] | None = None,
    ) -> Path:
        pkg_dir = (parent or tmp_path) / name
        pkg_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            f"Package: {name}",
            f"Version: {version}",
            f"Title: {name} test package",
            "Description: synthetic package for pytest",
            "License: MIT",
        ]
        for field_name, value in (
            ("Imports", imports),
            ("Depends", depends),
            ("Suggests", suggests),
            ("LinkingTo", linking_to),
        ):
            if value:
                lines.append(f"{field_name}: {', '.join(value)}")
        for k, v in (extra_fields or {}).items():
            lines.append(f"{k}: {v}")
        (pkg_dir / "DESCRIPTION").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return pkg_dir

    return _make

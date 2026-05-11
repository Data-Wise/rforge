"""Tests for lib/discovery.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.discovery import (
    Description,
    detect_ecosystem,
    find_r_packages,
    parse_description,
    read_description,
)


# ───────────────────────── DESCRIPTION parser ─────────────────────────


def test_parse_description_basic():
    content = """Package: mypkg
Version: 1.2.3
Title: My Package
License: MIT
"""
    desc = parse_description(content)
    assert desc is not None
    assert desc.package == "mypkg"
    assert desc.version == "1.2.3"
    assert desc.title == "My Package"
    assert desc.license == "MIT"


def test_parse_description_handles_continuation_lines():
    content = """Package: mypkg
Version: 0.1.0
Description: This is a long description
    that spans multiple lines
    with indented continuations.
"""
    desc = parse_description(content)
    assert desc is not None
    assert desc.description is not None
    assert "spans multiple lines" in desc.description
    assert "indented continuations" in desc.description


def test_parse_description_strips_version_constraints_and_filters_R():
    content = """Package: mypkg
Version: 1.0
Imports: dplyr (>= 1.0.0), ggplot2, R (>= 4.0)
Depends: methods
Suggests: testthat (>= 3.0.0),
    knitr,
    rmarkdown
"""
    desc = parse_description(content)
    assert desc is not None
    assert desc.imports == ["dplyr", "ggplot2"]  # R filtered out
    assert desc.depends == ["methods"]
    assert desc.suggests == ["testthat", "knitr", "rmarkdown"]


def test_parse_description_missing_package_returns_none():
    desc = parse_description("Version: 1.0\nTitle: orphan\n")
    assert desc is None


def test_read_description_returns_none_for_missing_file(tmp_path):
    assert read_description(tmp_path / "nonexistent" / "DESCRIPTION") is None


# ───────────────────────── find_r_packages ─────────────────────────


def test_find_r_packages_in_flat_ecosystem(tmp_path, make_pkg):
    make_pkg("pkgA")
    make_pkg("pkgB")
    make_pkg("pkgC")

    packages = find_r_packages(tmp_path)
    names = sorted(p.name for p in packages)
    assert names == ["pkgA", "pkgB", "pkgC"]


def test_find_r_packages_does_not_descend_into_packages(tmp_path, make_pkg):
    outer = make_pkg("outer")
    # Create a sub-DESCRIPTION inside outer/ — should NOT be picked up.
    (outer / "inner").mkdir()
    (outer / "inner" / "DESCRIPTION").write_text("Package: inner\nVersion: 0.1\n")

    packages = find_r_packages(tmp_path)
    assert [p.name for p in packages] == ["outer"]


def test_find_r_packages_ignores_hidden_directories(tmp_path, make_pkg):
    make_pkg("real")
    hidden_pkg = tmp_path / ".hidden"
    hidden_pkg.mkdir()
    (hidden_pkg / "DESCRIPTION").write_text("Package: hidden\nVersion: 0.1\n")

    packages = find_r_packages(tmp_path)
    assert [p.name for p in packages] == ["real"]


def test_category_inference_from_path(tmp_path, make_pkg):
    archived_dir = tmp_path / "archived"
    archived_dir.mkdir()
    make_pkg("old", parent=archived_dir)

    stable_dir = tmp_path / "cran"
    stable_dir.mkdir()
    make_pkg("steady", parent=stable_dir)

    make_pkg("fresh")  # active by default

    packages = {p.name: p for p in find_r_packages(tmp_path)}
    assert packages["old"].category == "archived"
    assert packages["steady"].category == "stable"
    assert packages["fresh"].category == "active"


# ───────────────────────── detect_ecosystem ─────────────────────────


def test_detect_ecosystem_empty_dir_is_single(tmp_path):
    eco = detect_ecosystem(tmp_path)
    assert eco.kind == "single"
    assert eco.mode == "minimal"
    assert eco.packages == []
    assert eco.config_found is False


def test_detect_ecosystem_single_package(tmp_path, make_pkg):
    make_pkg("solo")
    eco = detect_ecosystem(tmp_path)
    assert eco.kind == "single"
    assert eco.mode == "minimal"
    assert [p.name for p in eco.packages] == ["solo"]


def test_detect_ecosystem_three_packages_is_ecosystem(tmp_path, make_pkg):
    make_pkg("a")
    make_pkg("b")
    make_pkg("c")
    eco = detect_ecosystem(tmp_path)
    assert eco.kind == "ecosystem"
    assert eco.mode == "standard"  # 2-4 packages
    assert len(eco.packages) == 3


def test_detect_ecosystem_five_packages_is_full(tmp_path, make_pkg):
    for letter in "abcde":
        make_pkg(letter)
    eco = detect_ecosystem(tmp_path)
    assert eco.kind == "ecosystem"
    assert eco.mode == "full"  # ≥5 packages


def test_detect_ecosystem_hybrid_requires_config(tmp_path, make_pkg):
    make_pkg("a")
    make_pkg("b")
    (tmp_path / "docs").mkdir()  # non-package sibling — does NOT auto-hybrid

    eco_no_config = detect_ecosystem(tmp_path)
    assert eco_no_config.kind == "ecosystem"  # strict: no config → not hybrid

    (tmp_path / ".rforge.yaml").write_text("kind: hybrid\n")
    eco_with_config = detect_ecosystem(tmp_path)
    assert eco_with_config.kind == "hybrid"
    assert eco_with_config.config_found is True


def test_detect_ecosystem_config_other_kinds_are_ignored(tmp_path, make_pkg):
    """Only 'kind: hybrid' triggers hybrid; other values fall through."""
    make_pkg("a")
    make_pkg("b")
    (tmp_path / ".rforge.yaml").write_text("kind: ecosystem\n")
    eco = detect_ecosystem(tmp_path)
    assert eco.kind == "ecosystem"
    assert eco.config_found is True


def test_ecosystem_to_dict_is_json_serializable(tmp_path, make_pkg):
    import json

    make_pkg("foo", imports=["bar"])
    make_pkg("bar")
    eco = detect_ecosystem(tmp_path)
    payload = json.dumps(eco.to_dict())
    parsed = json.loads(payload)
    assert parsed["kind"] == "ecosystem"
    assert {p["name"] for p in parsed["packages"]} == {"foo", "bar"}


# ───────────────────────── Error paths ─────────────────────────


def test_detect_ecosystem_missing_path_raises(tmp_path):
    """Path that does not exist on disk → FileNotFoundError."""
    missing = tmp_path / "definitely-not-here"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        detect_ecosystem(missing)


def test_detect_ecosystem_file_path_raises(tmp_path, make_pkg):
    """Path that exists but is a file (not a directory) → NotADirectoryError."""
    pkg = make_pkg("solo")
    desc_file = pkg / "DESCRIPTION"  # exists but is a file
    with pytest.raises(NotADirectoryError, match="not a directory"):
        detect_ecosystem(desc_file)


def test_discovery_cli_exits_1_on_missing_path(tmp_path):
    """CLI: missing path → exit 1, error on stderr.

    Invoked via `python3 -m lib.discovery` (lib/ is a Python package).
    """
    import subprocess
    from pathlib import Path as _P

    repo_root = _P(__file__).resolve().parent.parent
    result = subprocess.run(
        ["python3", "-m", "lib.discovery",
         "--path", str(tmp_path / "nope"), "--format", "json"],
        cwd=repo_root, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr
    assert result.stdout == ""  # nothing on stdout

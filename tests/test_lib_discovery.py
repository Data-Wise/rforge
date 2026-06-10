"""Tests for lib/discovery.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.discovery import (
    Description,
    Manifest,
    ManifestEntry,
    detect_ecosystem,
    find_r_packages,
    parse_description,
    parse_manifest,
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


# ───────────────────────── Manifest parser ─────────────────────────


def test_parse_manifest_basic():
    content = """ecosystem: mediationverse
updated: 2026-06-10
packages:
  - name: medfit
    path: ../active/medfit
    role: Foundation engine
    repo: Data-Wise/medfit
    cran: submitted
    status_file: ../active/medfit/.STATUS
"""
    manifest = parse_manifest(content)
    assert manifest is not None
    assert manifest.ecosystem == "mediationverse"
    assert manifest.updated == "2026-06-10"
    assert len(manifest.packages) == 1
    entry = manifest.packages[0]
    assert entry.name == "medfit"
    assert entry.path == "../active/medfit"
    assert entry.role == "Foundation engine"
    assert entry.repo == "Data-Wise/medfit"
    assert entry.cran == "submitted"
    assert entry.status_file == "../active/medfit/.STATUS"


def test_parse_manifest_multiple_packages_and_inline_comments():
    content = """ecosystem: mediationverse
kind: ecosystem            # rforge classification, ignored here
packages:
  - name: medfit
    cran: submitted          # none | submitted | on-cran
  - name: probmed
    role: P_med effect size
"""
    m = parse_manifest(content)
    assert [e.name for e in m.packages] == ["medfit", "probmed"]
    medfit, probmed = m.packages
    assert medfit.cran == "submitted"  # inline comment stripped
    assert medfit.role is None  # optional field absent → None
    assert probmed.role == "P_med effect size"
    assert probmed.cran is None


def test_parse_manifest_empty_content_is_empty_manifest():
    m = parse_manifest("")
    assert m.ecosystem is None
    assert m.packages == []


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


def test_detect_ecosystem_enriches_packages_from_manifest(tmp_path, make_pkg):
    make_pkg("medfit")
    make_pkg("probmed")
    (tmp_path / "hub").mkdir()
    (tmp_path / "hub" / "ECOSYSTEM-MANIFEST.yaml").write_text(
        "ecosystem: testverse\n"
        "packages:\n"
        "  - name: medfit\n"
        "    role: Foundation\n"
        "    cran: submitted\n"
        "  - name: probmed\n"
        "    role: P_med\n",
        encoding="utf-8",
    )
    (tmp_path / ".rforge.yaml").write_text(
        "manifest: hub/ECOSYSTEM-MANIFEST.yaml\n", encoding="utf-8"
    )

    eco = detect_ecosystem(tmp_path)
    by_name = {p.name: p for p in eco.packages}
    assert by_name["medfit"].manifest is not None
    assert by_name["medfit"].manifest.role == "Foundation"
    assert by_name["medfit"].manifest.cran == "submitted"
    assert by_name["probmed"].manifest.role == "P_med"
    assert eco.manifest_path is not None
    assert eco.manifest_path.endswith("ECOSYSTEM-MANIFEST.yaml")
    # full match → no drift
    assert eco.drift.manifest_only == []
    assert eco.drift.disk_only == []


def test_detect_ecosystem_without_manifest_has_no_enrichment(tmp_path, make_pkg):
    """Regression: zero-manifest behavior is unchanged."""
    make_pkg("a")
    make_pkg("b")
    eco = detect_ecosystem(tmp_path)
    assert eco.manifest_path is None
    assert all(p.manifest is None for p in eco.packages)
    assert eco.drift.manifest_only == []
    assert eco.drift.disk_only == []


def test_detect_ecosystem_reports_manifest_drift(tmp_path, make_pkg):
    make_pkg("medfit")
    make_pkg("stray")  # on disk, absent from manifest
    (tmp_path / "ECOSYSTEM-MANIFEST.yaml").write_text(
        "packages:\n  - name: medfit\n  - name: ghost\n",  # ghost: in manifest, not on disk
        encoding="utf-8",
    )
    (tmp_path / ".rforge.yaml").write_text(
        "manifest: ECOSYSTEM-MANIFEST.yaml\n", encoding="utf-8"
    )
    eco = detect_ecosystem(tmp_path)
    assert eco.drift.manifest_only == ["ghost"]
    assert eco.drift.disk_only == ["stray"]


def test_detect_ecosystem_manifest_match_is_case_insensitive(tmp_path, make_pkg):
    make_pkg("rmediation")  # dir/package lowercase
    make_pkg("x")
    make_pkg("y")
    (tmp_path / "ECOSYSTEM-MANIFEST.yaml").write_text(
        "packages:\n  - name: RMediation\n    role: CIs\n",  # manifest uses canonical case
        encoding="utf-8",
    )
    (tmp_path / ".rforge.yaml").write_text(
        "manifest: ECOSYSTEM-MANIFEST.yaml\n", encoding="utf-8"
    )
    eco = detect_ecosystem(tmp_path)
    by_name = {p.name: p for p in eco.packages}
    assert by_name["rmediation"].manifest is not None
    assert by_name["rmediation"].manifest.role == "CIs"
    assert eco.drift.manifest_only == []  # matched case-insensitively, not drift


def test_detect_ecosystem_missing_manifest_file_degrades(tmp_path, make_pkg):
    """Configured manifest path that doesn't exist → no enrichment, no raise."""
    make_pkg("a")
    make_pkg("b")
    (tmp_path / ".rforge.yaml").write_text(
        "manifest: nope/MISSING.yaml\n", encoding="utf-8"
    )
    eco = detect_ecosystem(tmp_path)
    assert eco.manifest_path is None
    assert all(p.manifest is None for p in eco.packages)


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

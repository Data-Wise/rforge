"""Tests for scripts/version_sync.py — the version/count drift gate.

These tests operate on an isolated copy of the real tracked files in a tmp
tree, so they never mutate the working copy. We re-point the script's module
globals (REPO_ROOT and friends) at the tmp tree, run main(), and assert on the
synced output.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "version_sync.py"

# Files version_sync.py reads/writes, copied into the tmp tree.
TRACKED = [
    "package.json",
    "mkdocs.yml",
    ".claude-plugin/plugin.json",
    "README.md",
    "CLAUDE.md",
]


def _load_module():
    """Import scripts/version_sync.py as a standalone module."""
    spec = importlib.util.spec_from_file_location("version_sync", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve field types via sys.modules
    # (required on Python 3.12+/3.14 for from-future annotations).
    sys.modules["version_sync"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def synced_tree(tmp_path: Path):
    """A tmp copy of the real tracked files, with the module re-pointed at it.

    The fixture first runs the script once (write mode) so the tree starts
    fully in sync regardless of the real repo's state.
    """
    mod = _load_module()
    for rel in TRACKED:
        src = REPO_ROOT / rel
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    # Re-point module globals at the tmp tree.
    mod.REPO_ROOT = tmp_path
    mod.PACKAGE_JSON = tmp_path / "package.json"
    mod.MKDOCS_YML = tmp_path / "mkdocs.yml"

    # Normalize the tree to fully-synced first.
    assert mod.main([]) == 0
    return mod, tmp_path


def test_check_passes_on_synced_tree(synced_tree):
    mod, _ = synced_tree
    assert mod.main(["--check"]) == 0


def test_check_fails_on_injected_count_drift(synced_tree):
    mod, tree = synced_tree
    # Inject drift: make package.json description count wrong.
    pkg = tree / "package.json"
    text = pkg.read_text(encoding="utf-8")
    count = mod.read_command_count()
    text = text.replace(f"{count} commands for R package",
                        "99 commands for R package")
    pkg.write_text(text, encoding="utf-8")

    assert mod.main(["--check"]) == 1


def test_check_fails_on_injected_version_drift(synced_tree):
    mod, tree = synced_tree
    # Bump the canonical version; mkdocs/README/plugin.json now lag behind.
    pkg = tree / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    assert mod.main(["--check"]) == 1


def test_dry_run_writes_nothing(synced_tree):
    mod, tree = synced_tree
    # Inject drift, snapshot, dry-run, assert files untouched.
    pkg = tree / "package.json"
    before = pkg.read_text(encoding="utf-8")
    count = mod.read_command_count()
    pkg.write_text(before.replace(f"{count} commands for R package",
                                  "77 commands for R package"),
                   encoding="utf-8")
    snapshot = {rel: (tree / rel).read_text(encoding="utf-8") for rel in TRACKED}

    rc = mod.main(["--dry-run"])
    # dry-run reports drift exists but must not write.
    assert rc == 0
    for rel in TRACKED:
        assert (tree / rel).read_text(encoding="utf-8") == snapshot[rel], rel


def test_write_path_syncs_version_into_targets(synced_tree):
    mod, tree = synced_tree
    pkg = tree / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    assert mod.main([]) == 0  # write

    mkdocs = (tree / "mkdocs.yml").read_text(encoding="utf-8")
    plugin = (tree / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    readme = (tree / "README.md").read_text(encoding="utf-8")

    assert 'version: "9.9.9"' in mkdocs
    assert '"version": "9.9.9"' in plugin
    assert "**Version:** 9.9.9" in readme
    # And re-check now passes.
    assert mod.main(["--check"]) == 0


def test_write_path_syncs_command_count(synced_tree):
    mod, tree = synced_tree
    # Change the canonical count in mkdocs.yml; everything else should follow.
    mkdocs_path = tree / "mkdocs.yml"
    text = mkdocs_path.read_text(encoding="utf-8")
    count = mod.read_command_count()
    text = text.replace(f"command_count: {count}", "command_count: 42")
    mkdocs_path.write_text(text, encoding="utf-8")

    assert mod.main(["--check"]) == 1  # now drifted
    assert mod.main([]) == 0  # write

    pkg = (tree / "package.json").read_text(encoding="utf-8")
    plugin = (tree / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
    readme = (tree / "README.md").read_text(encoding="utf-8")
    claude_md = (tree / "CLAUDE.md").read_text(encoding="utf-8")

    assert "42 commands for R package" in pkg
    assert "42 commands for R package" in plugin
    assert "Claude Code — 42 commands," in readme
    assert "## Command-file conventions (all 42 commands)" in claude_md
    assert mod.main(["--check"]) == 0


def test_read_version_is_canonical_source(synced_tree):
    mod, tree = synced_tree
    # read_version pulls straight from package.json "version" — assert against
    # the file itself so this stays correct across version bumps.
    expected = json.loads((tree / "package.json").read_text(encoding="utf-8"))["version"]
    assert mod.read_version() == expected


def test_version_rule_targets_rforge_not_a_decoy(synced_tree):
    mod, tree = synced_tree
    # A stray top-level `version:` (e.g. a future theme/mike key) must NOT be
    # clobbered — only extra.rforge.version is the render source. Locks the
    # `rforge:`-anchored pattern against a bare first-match regression.
    mkdocs_path = tree / "mkdocs.yml"
    mkdocs_path.write_text(
        'version: "0.0.0-decoy"\n' + mkdocs_path.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    pkg = tree / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    assert mod.main([]) == 0  # write

    out = mkdocs_path.read_text(encoding="utf-8")
    assert 'version: "0.0.0-decoy"' in out  # decoy untouched
    assert 'version: "9.9.9"' in out  # rforge child synced
    assert mod.main(["--check"]) == 0

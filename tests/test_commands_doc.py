"""Self-tests for the docs/commands.md sync-gate checker.

Imports the checker's core logic and feeds it tiny in-memory fixtures so we can
prove the gate detects drift (missing flag, missing section, orphan section) and
that the flag classifier excludes positionals / lib-only args. This guarantees
the gate is not vacuous.
"""
import importlib.util
from pathlib import Path

import pytest

# Load tests/_check_commands_doc.py as a module (underscore-prefixed, not a
# normal pytest test module — same trick the checker uses to stay importable).
_SPEC = importlib.util.spec_from_file_location(
    "_check_commands_doc", Path(__file__).parent / "_check_commands_doc.py"
)
chk = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(chk)


def _cmd(slash, flags):
    return {"path": f"commands/{slash.split(':')[-1]}.md", "slash": slash, "flags": flags}


# --- declared_flags classifier -------------------------------------------------

def test_boolean_arg_is_a_flag():
    fm = "name: rforge:r:foo\narguments:\n  - name: write\n    type: boolean\n"
    assert chk.declared_flags(fm, "body uses --write here") == ["write"]


def test_dashed_name_is_a_flag():
    fm = "name: rforge:r:foo\narguments:\n  - name: --kind\n    type: string\n"
    assert chk.declared_flags(fm, "no usage at all") == ["kind"]


def test_string_positional_is_excluded():
    # `function` is a positional name and never shown as --function → excluded.
    fm = ("name: rforge:r:use-test\narguments:\n"
          "  - name: function\n    type: string\n    required: true\n")
    assert chk.declared_flags(fm, "/rforge:r:use-test <function>") == []


def test_lib_only_dash_usage_does_not_promote_positional():
    # `name` only appears as --name inside a `python3 -m lib.*` line → still
    # positional, not a slash-command flag.
    fm = ("name: rforge:r:use-data\narguments:\n"
          "  - name: name\n    type: string\n    required: true\n")
    body = "/rforge:r:use-data <name>\n```\npython3 -m lib.scaffold data --name foo\n```"
    assert chk.declared_flags(fm, body) == []


def test_positional_promoted_when_exposed_as_flag_in_prose():
    # impact genuinely takes --package: positional name BUT exposed in prose.
    fm = ("name: rforge:impact\narguments:\n"
          "  - name: package\n    type: string\n")
    body = "`--package` is required.\n/rforge:impact --package medfit"
    assert chk.declared_flags(fm, body) == ["package"]


def test_non_positional_string_is_a_flag():
    fm = "name: rforge:r:foo\narguments:\n  - name: format\n    type: string\n"
    assert chk.declared_flags(fm, "anything") == ["format"]


def test_multiline_lib_continuation_does_not_promote_positional():
    # IMPORTANT (feature 1): `name` is positional and appears as `--name` ONLY on
    # a backslash-continuation line of a `python3 -m lib.*` invocation. The whole
    # continued command must be stripped, so `name` stays positional (not a flag).
    fm = ("name: rforge:r:use-data\narguments:\n"
          "  - name: name\n    type: string\n    required: true\n")
    body = (
        "/rforge:r:use-data <name>\n"
        "```\n"
        "python3 -m lib.scaffold data \\\n"
        "    --name foo \\\n"
        "    --dir R/\n"
        "```\n"
    )
    assert chk.declared_flags(fm, body) == []


def test_quoted_name_scalar_is_handled():
    # MINOR (feature 1): a quoted YAML scalar `name: "format"` must be captured
    # as `format`, not `"format"`.
    fm = 'name: rforge:r:foo\narguments:\n  - name: "format"\n    type: string\n'
    assert chk.declared_flags(fm, "anything") == ["format"]


def test_quoted_command_name_scalar_is_handled():
    # MINOR (feature 1): a quoted command name scalar resolves cleanly.
    fm = 'name: "rforge:z"\n'
    assert chk._command_name(fm) == "rforge:z"
    assert chk.slash_name(fm) == "/rforge:z"


def test_flag_prefix_collision_not_satisfied_by_longer_flag():
    # MINOR (feature 1): `--base` documented requirement must NOT be satisfied by
    # `--base-dir` appearing in the section (prefix collision via `\b`).
    commands = [_cmd("/rforge:r:check", ["base"])]
    doc = "### /rforge:r:check\n\nUsage: only --base-dir is mentioned here.\n"
    problems = chk.find_problems(commands, doc)
    assert any("--base documented? no" in p for p in problems)


def test_flag_exact_match_still_passes():
    # Sanity companion: the exact flag still satisfies coverage.
    commands = [_cmd("/rforge:r:check", ["base"])]
    doc = "### /rforge:r:check\n\nUsage: --base dev is supported.\n"
    assert chk.find_problems(commands, doc) == []


# --- find_problems: presence checks -------------------------------------------

def test_clean_when_section_and_flag_present():
    commands = [_cmd("/rforge:r:check", ["strict"])]
    doc = "### /rforge:r:check\n\nUsage: --strict here.\n"
    assert chk.find_problems(commands, doc) == []


def test_detects_missing_flag_in_section():
    commands = [_cmd("/rforge:r:check", ["strict"])]
    doc = "### /rforge:r:check\n\nUsage with no flags documented.\n"
    problems = chk.find_problems(commands, doc)
    assert len(problems) == 1
    assert "--strict documented? no" in problems[0]
    assert "/rforge:r:check" in problems[0]


def test_detects_missing_section_for_command():
    commands = [_cmd("/rforge:r:newcmd", [])]
    doc = "### /rforge:r:other\n\nSomething else.\n"
    problems = chk.find_problems(commands, doc)
    assert any("has no section in commands.md" in p for p in problems)


def test_detects_orphan_section_without_command():
    commands = []  # no backing command files
    doc = "### /rforge:r:ghost\n\nDocs for a command that doesn't exist.\n"
    problems = chk.find_problems(commands, doc)
    assert any("has no backing command file" in p for p in problems)


# --- end-to-end against the real repo -----------------------------------------

def test_real_repo_is_in_sync():
    """The committed docs/commands.md must satisfy the gate (regression guard)."""
    commands = chk.load_commands(chk.COMMANDS_DIR)
    doc = chk.COMMANDS_DOC.read_text(encoding="utf-8")
    assert chk.find_problems(commands, doc) == []


def test_real_repo_has_expected_command_count():
    """Sanity: the loader sees the non-stub commands (catches glob breakage)."""
    commands = chk.load_commands(chk.COMMANDS_DIR)
    # 41 non-stub commands as of v2.12.0; allow growth, never silent collapse.
    assert len(commands) >= 39


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

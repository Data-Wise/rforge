"""Tests for lib.s7review — static S7 convention checker (advisory, pure-stdlib)."""
from __future__ import annotations

from pathlib import Path

from lib import s7review

FIX = Path(__file__).parent / "fixtures"
BAD = FIX / "s7pkg.bad"
CLEAN = FIX / "s7pkg.clean"


# ── parser ──────────────────────────────────────────────────────────────
def test_find_constructs_extracts_new_class_calls():
    text = 'A <- new_class("A", properties = list(x = class_numeric))\n'
    cons = s7review._find_s7_constructs(text)
    calls = [c for c in cons if c["call"] == "new_class"]
    assert calls, "should find a new_class construct"
    assert calls[0]["bound"] == "A"
    assert 'properties = list(x = class_numeric)' in calls[0]["args"]


def test_find_constructs_balances_nested_parens():
    text = 'B <- new_class("B", properties = list(f = function(a) g(a)))\n'
    cons = s7review._find_s7_constructs(text)
    nc = [c for c in cons if c["call"] == "new_class"][0]
    # the whole nested arg block was captured, not truncated at the first ')'
    assert nc["args"].rstrip().endswith("function(a) g(a)))".rstrip()[-1])


def test_find_constructs_handles_method_and_generic():
    text = (
        'G <- new_generic("G", "x")\n'
        'method(G, A) <- function(x, ...) x\n'
    )
    calls = {c["call"] for c in s7review._find_s7_constructs(text)}
    assert "new_generic" in calls
    assert "method" in calls


def test_unbalanced_parens_skipped_not_raised():
    # a construct whose parens never balance must be silently skipped
    text = 'Z <- new_class("Z", properties = list(\n'
    s7review._find_s7_constructs(text)  # must not raise


# ── envelope contract ───────────────────────────────────────────────────
def test_envelope_shape_matches_cranlint():
    env = s7review._envelope("naming", "ok", [], ["clean"])
    assert set(env) == {"kind", "status", "findings", "messages", "engine_missing"}
    assert env["engine_missing"] == []


def test_run_all_clean_fixture_is_ok():
    env = s7review.run_all(str(CLEAN))
    assert env["kind"] == "s7review"
    assert env["status"] == "ok", [s["findings"] for s in env["stages"]]
    assert env["engine_missing"] == []
    assert {s["kind"] for s in env["stages"]} == {
        "naming", "validators", "methods", "legacy", "docs"
    }


def test_run_all_no_r_dir_warns_not_raises(tmp_path):
    env = s7review.run_all(str(tmp_path))
    assert env["status"] == "warn"
    assert env["engine_missing"] == []


# ── naming ──────────────────────────────────────────────────────────────
def _codes(env):
    return {f["code"] for f in env["findings"]}


def test_naming_flags_bad_fixture():
    env = s7review.check_naming(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "class_name_case" in c        # mediator_model
    assert "class_name_mismatch" in c    # Estimator <- new_class("Estimater")
    assert "generic_name_case" in c      # ComputeEffect
    assert "prop_name_case" in c         # BadProp
    for f in env["findings"]:
        assert f["severity"] == "advisory"
        assert f["source"] == "static"


def test_naming_clean_fixture_ok():
    env = s7review.check_naming(str(CLEAN))
    assert env["status"] == "ok"
    assert env["findings"] == []


# ── validators ──────────────────────────────────────────────────────────
def test_validators_flag_bad_fixture():
    env = s7review.check_validators(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "missing_validator" in c       # mediator_model has typed props, no validator
    assert "validator_return_shape" in c  # Validated returns TRUE
    for f in env["findings"]:
        assert f["source"] == "static" and f["severity"] == "advisory"


def test_validators_clean_fixture_ok():
    env = s7review.check_validators(str(CLEAN))
    assert env["status"] == "ok"


# ── methods ─────────────────────────────────────────────────────────────
def test_methods_flag_bad_fixture():
    env = s7review.check_methods(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "dangling_method" in c            # method(external_generic, ...)
    assert "missing_methods_register" in c   # no methods_register() in bad fixture


def test_methods_clean_fixture_ok():
    # clean fixture: compute_effect generic defined locally + methods_register() present
    env = s7review.check_methods(str(CLEAN))
    assert env["status"] == "ok"

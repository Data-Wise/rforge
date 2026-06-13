"""Tests for lib.s7review — static S7 convention checker (advisory, pure-stdlib)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

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


# ── legacy ──────────────────────────────────────────────────────────────
def test_legacy_flag_bad_fixture():
    env = s7review.check_legacy_oop(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "legacy_s4_in_s7" in c   # setClass/setGeneric
    assert "legacy_r5_in_s7" in c   # R6::R6Class
    assert "legacy_s3_generic" in c # print.mediator_model + UseMethod


def test_legacy_clean_fixture_ok():
    env = s7review.check_legacy_oop(str(CLEAN))
    assert env["status"] == "ok"


# ── docs ────────────────────────────────────────────────────────────────
def test_docs_flag_bad_fixture():
    env = s7review.check_class_docs(str(BAD))
    c = _codes(env)
    assert env["status"] == "warn"
    assert "undocumented_export" in c     # export(undocumented_class), no #' block
    assert "prop_type_unresolvable" in c  # ref = NoSuchClass


def test_docs_clean_fixture_ok():
    env = s7review.check_class_docs(str(CLEAN))
    assert env["status"] == "ok"


# ── preprocessing seam (comment strip + string masking) ──────────────────
def _write_pkg(tmp_path, r_src, namespace="export(Foo)\n"):
    """Write a minimal R package skeleton with one R/ file; return its path."""
    (tmp_path / "R").mkdir()
    (tmp_path / "R" / "classes.R").write_text(r_src, encoding="utf-8")
    (tmp_path / "NAMESPACE").write_text(namespace, encoding="utf-8")
    (tmp_path / "DESCRIPTION").write_text(
        "Package: tmppkg\nVersion: 0.0.1\n", encoding="utf-8")
    return tmp_path


def test_new_property_value_not_flagged_as_type(tmp_path):
    """FP #1: `label = new_property(class_character)` must NOT emit
    prop_type_unresolvable for the call name `new_property`."""
    pkg = _write_pkg(tmp_path, (
        "#' Foo\n#' @export\n"
        'Foo <- new_class("Foo",\n'
        "  properties = list(\n"
        '    label = new_property(class_character, default = "x"),\n'
        "    other = new_union(class_numeric, class_character)\n"
        "  )\n"
        ")\n"
    ))
    env = s7review.check_class_docs(str(pkg))
    bad = [f for f in env["findings"]
           if f["code"] == "prop_type_unresolvable"
           and f["symbol"] in ("new_property", "new_union")]
    assert not bad, bad


def test_commented_out_new_class_not_parsed(tmp_path):
    """FP #2: a commented-out new_class line must produce zero findings."""
    pkg = _write_pkg(tmp_path, (
        '# Bar <- new_class("bar_bad_name", properties = list(X = NoSuch),\n'
        "#   validator = function(self) return(TRUE))\n"
        '# print.bar_bad_name <- function(x, ...) UseMethod("print")\n'
        "# setClass('OldThing')\n"
    ), namespace="")
    env = s7review.run_all(str(pkg))
    all_findings = [f for s in env["stages"] for f in s["findings"]]
    assert all_findings == [], all_findings
    assert env["status"] == "ok"


def test_return_bool_in_string_not_flagged(tmp_path):
    """FP #3: a string literal containing return(TRUE) is not a validator."""
    pkg = _write_pkg(tmp_path, (
        "#' Foo\n#' @export\n"
        'Foo <- new_class("Foo",\n'
        "  properties = list(x = class_numeric),\n"
        '  validator = function(self) {\n'
        '    msg <- "see return(TRUE) for details"\n'
        "    character(0)\n"
        "  }\n"
        ")\n"
    ))
    env = s7review.check_validators(str(pkg))
    bad = [f for f in env["findings"] if f["code"] == "validator_return_shape"]
    assert not bad, bad


# ── --eco ecosystem sweep (pure-stdlib) ──────────────────────────────────
def _mk_pkg(root: Path, name: str, r_src: str, namespace: str = "") -> Path:
    """Write a minimal R package under root/<name>; return its dir."""
    p = root / name
    (p / "R").mkdir(parents=True)
    (p / "R" / "classes.R").write_text(r_src, encoding="utf-8")
    (p / "NAMESPACE").write_text(namespace, encoding="utf-8")
    (p / "DESCRIPTION").write_text(
        f"Package: {name}\nVersion: 0.0.1\n", encoding="utf-8")
    return p


def _eco_fixture(tmp_path, *, manifest_order=("beta", "alpha")):
    """2-package ecosystem (alpha clean, beta flagged) + manifest declaring order."""
    _mk_pkg(tmp_path, "alpha",
            '#\' Foo\n#\' @export\n'
            'Foo <- new_class("Foo", properties = list(x = class_numeric),\n'
            '  validator = function(self) character(0))\n',
            namespace="export(Foo)\n")
    # beta: a snake_case class name → naming finding
    _mk_pkg(tmp_path, "beta",
            'bad_name <- new_class("bad_name",\n'
            '  properties = list(y = class_numeric))\n')
    manifest = "packages:\n" + "".join(f"  - name: {n}\n" for n in manifest_order)
    (tmp_path / "eco.yaml").write_text(manifest, encoding="utf-8")
    (tmp_path / ".rforge.yaml").write_text("manifest: eco.yaml\n", encoding="utf-8")
    return tmp_path


def test_run_eco_aggregates_per_package_and_rollup(tmp_path):
    root = _eco_fixture(tmp_path)
    env = s7review.run_eco(str(root))
    assert env["kind"] == "s7review-eco"
    assert env["engine_missing"] == []
    # one entry per discovered package
    names = [pkg["package"] for pkg in env["packages"]]
    assert set(names) == {"alpha", "beta"}
    # beta is flagged (warn), alpha clean (ok)
    by_name = {pkg["package"]: pkg for pkg in env["packages"]}
    assert by_name["alpha"]["status"] == "ok"
    assert by_name["beta"]["status"] == "warn"
    # ecosystem roll-up: total findings by family present, beta contributes naming
    assert env["status"] == "warn"
    assert env["rollup"]["by_family"].get("naming", 0) >= 1
    assert env["rollup"]["packages_flagged"] == 1
    assert env["rollup"]["packages_clean"] == 1


def test_run_eco_orders_by_manifest_order(tmp_path):
    root = _eco_fixture(tmp_path, manifest_order=("beta", "alpha"))
    env = s7review.run_eco(str(root))
    # manifest declares beta before alpha → that order is honored
    assert [pkg["package"] for pkg in env["packages"]] == ["beta", "alpha"]


def test_run_eco_broken_package_warns_without_aborting(tmp_path, monkeypatch):
    root = _eco_fixture(tmp_path)

    real_run_all = s7review.run_all

    def flaky(path):
        if str(path).endswith("beta"):
            raise RuntimeError("boom")
        return real_run_all(path)

    monkeypatch.setattr(s7review, "run_all", flaky)
    env = s7review.run_eco(str(root))
    # sweep continued: both packages still reported
    by_name = {pkg["package"]: pkg for pkg in env["packages"]}
    assert set(by_name) == {"alpha", "beta"}
    # the broken one degrades to a per-package warn (not a crash)
    assert by_name["beta"]["status"] == "warn"
    assert any("parse" in m.lower() or "boom" in m.lower() or "skipped" in m.lower()
               for m in by_name["beta"]["messages"])
    # alpha still ran for real
    assert by_name["alpha"]["status"] == "ok"


# ── --runtime orchestration + merge ──────────────────────────────────────
def _fake_runtime_env(*, dead=("dead_gen",), nonenforcing=("Lax",), missing=(),
                      undeclared=()):
    """Build a fake normalized rcmd s7runtime envelope (as rcmd.run would return)."""
    return {
        "kind": "s7runtime", "status": "warn", "engine_missing": [], "messages": [],
        "s7runtime": {
            "dead_generics": list(dead),
            "methods_on_missing_class": list(missing),
            "methods_undeclared_dependency": list(undeclared),
            "nonenforcing_validators": list(nonenforcing),
        },
    }


def test_runtime_merges_two_families_into_static(tmp_path, monkeypatch):
    pkg = _mk_pkg(tmp_path, "alpha",
                  '#\' Foo\n#\' @export\n'
                  'Foo <- new_class("Foo", properties = list(x = class_numeric),\n'
                  '  validator = function(self) character(0))\n',
                  namespace="export(Foo)\n")
    monkeypatch.setattr(s7review.rcmd, "run",
                        lambda kind, path=".", **kw: _fake_runtime_env())
    env = s7review.run_all_with_runtime(str(pkg))
    stage_kinds = {s["kind"] for s in env["stages"]}
    assert "method-dispatch" in stage_kinds
    assert "validator-runtime" in stage_kinds
    # static families still present
    assert {"naming", "validators", "methods", "legacy", "docs"} <= stage_kinds
    md = next(s for s in env["stages"] if s["kind"] == "method-dispatch")
    vr = next(s for s in env["stages"] if s["kind"] == "validator-runtime")
    assert any(f["code"] == "dead_generic" for f in md["findings"])
    assert any(f["code"] == "validator_not_enforcing" for f in vr["findings"])
    for f in md["findings"] + vr["findings"]:
        assert f["source"] == "runtime"
    assert env["status"] == "warn"


def test_runtime_maps_method_on_missing_class(tmp_path, monkeypatch):
    """methods_on_missing_class engine strings ('<gen> -> <cls>') become
    method_on_missing_class findings in the method-dispatch family."""
    pkg = _mk_pkg(tmp_path, "alpha", 'Foo <- new_class("Foo")\n')
    monkeypatch.setattr(
        s7review.rcmd, "run",
        lambda kind, path=".", **kw: _fake_runtime_env(
            dead=(), nonenforcing=(),
            missing=({"generic": "speak", "class": "Ghost"},)))
    env = s7review.run_all_with_runtime(str(pkg))
    md = next(s for s in env["stages"] if s["kind"] == "method-dispatch")
    miss = [f for f in md["findings"] if f["code"] == "method_on_missing_class"]
    assert len(miss) == 1, md
    assert miss[0]["symbol"] == "Ghost"
    assert "speak" in miss[0]["message"] and "Ghost" in miss[0]["message"]
    assert miss[0]["source"] == "runtime"
    assert md["status"] == "warn"


def test_runtime_maps_method_undeclared_dependency(tmp_path, monkeypatch):
    """methods_undeclared_dependency engine entries ({generic, class, package})
    become method_undeclared_dependency findings in the method-dispatch family."""
    pkg = _mk_pkg(tmp_path, "alpha", 'Foo <- new_class("Foo")\n')
    monkeypatch.setattr(
        s7review.rcmd, "run",
        lambda kind, path=".", **kw: _fake_runtime_env(
            dead=(), nonenforcing=(), missing=(),
            undeclared=({"generic": "speak", "class": "Widget",
                         "package": "otherpkg"},)))
    env = s7review.run_all_with_runtime(str(pkg))
    md = next(s for s in env["stages"] if s["kind"] == "method-dispatch")
    undecl = [f for f in md["findings"]
              if f["code"] == "method_undeclared_dependency"]
    assert len(undecl) == 1, md
    assert undecl[0]["symbol"] == "Widget"
    assert "speak" in undecl[0]["message"]
    assert "otherpkg" in undecl[0]["message"]
    assert undecl[0]["source"] == "runtime"
    assert md["status"] == "warn"


def test_runtime_degrades_when_r_unavailable(tmp_path, monkeypatch):
    """R missing → engine_missing envelope → warn, static intact, never raises."""
    pkg = _mk_pkg(tmp_path, "alpha",
                  'bad_name <- new_class("bad_name",\n'
                  '  properties = list(y = class_numeric))\n')
    monkeypatch.setattr(s7review.rcmd, "run",
                        lambda kind, path=".", **kw: {
                            "kind": "s7runtime", "status": "error",
                            "engine_missing": ["R"],
                            "messages": ["Missing R"]})
    env = s7review.run_all_with_runtime(str(pkg))
    # static families intact (naming flagged the bad class)
    stage_kinds = {s["kind"] for s in env["stages"]}
    assert {"naming", "validators", "methods", "legacy", "docs"} <= stage_kinds
    naming = next(s for s in env["stages"] if s["kind"] == "naming")
    assert any(f["code"] == "class_name_case" for f in naming["findings"])
    # runtime degraded to a warn stage with a "skipped" message
    rt = [s for s in env["stages"] if s["kind"] in ("method-dispatch", "validator-runtime")]
    assert rt, "runtime stages should still appear (degraded)"
    assert any("skipped" in m.lower() for s in rt for m in s.get("messages", []))


def test_runtime_never_raises_on_rcmd_exception(tmp_path, monkeypatch):
    pkg = _mk_pkg(tmp_path, "alpha", 'Foo <- new_class("Foo")\n', namespace="")

    def boom(kind, path=".", **kw):
        raise RuntimeError("rcmd blew up")

    monkeypatch.setattr(s7review.rcmd, "run", boom)
    env = s7review.run_all_with_runtime(str(pkg))  # must not raise
    assert env["kind"] == "s7review"


# ── pure-stdlib guard ────────────────────────────────────────────────────
def test_s7review_is_pure_stdlib_no_direct_r():
    """s7review.py must not shell out to R itself — all R goes via lib.rcmd."""
    src = (Path(s7review.__file__)).read_text(encoding="utf-8")
    # no direct subprocess/Rscript *usage* in this module (mentions in prose
    # docstrings are fine; what matters is no import / call). Check imports.
    assert not re.search(r"^\s*import\s+subprocess", src, re.MULTILINE)
    assert not re.search(r"\bsubprocess\.(run|Popen|call|check_)", src)
    assert not re.search(r'\bshutil\.which\(\s*["\']R', src)
    assert "subprocess.run([" not in src


def test_registered_s3_method_not_flagged_as_legacy(tmp_path):
    """FP #4: an @exportS3Method-tagged format.Foo is a registered S3 method,
    not an S7-migration leftover — do not flag legacy_s3_generic."""
    pkg = _write_pkg(tmp_path, (
        "#' Foo\n#' @export\n"
        'Foo <- new_class("Foo", properties = list(x = class_numeric))\n'
        "\n"
        "#' @exportS3Method base::format\n"
        "format.Foo <- function(x, ...) x@x\n"
    ))
    env = s7review.check_legacy_oop(str(pkg))
    bad = [f for f in env["findings"]
           if f["code"] == "legacy_s3_generic" and "Foo" in f["symbol"]]
    assert not bad, bad


def test_string_masking_preserves_offsets():
    """The masking helper must preserve length, newline positions, and the
    code outside string literals / comments."""
    src = 'x <- "ab#c"  # tail comment\ny <- 1\n'
    masked = s7review._mask_strings_and_comments(src)
    assert len(masked) == len(src)
    assert masked.count("\n") == src.count("\n")
    # code preserved
    assert masked.startswith("x <- ")
    assert "y <- 1" in masked
    # string interior and comment gone (no '#', no 'ab', no 'tail')
    assert "#" not in masked
    assert "ab" not in masked
    assert "tail" not in masked

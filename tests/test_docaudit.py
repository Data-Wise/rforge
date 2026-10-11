"""Unit tests for lib/docaudit.py (signature checks)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import docaudit
from lib.docaudit import PackageApi, Region, check_region, extract_regions, parse_namespace, parse_rd_usage, split_args


def rd(usage: str) -> str:
    return "\\name{x}\n\\usage{\n" + usage + "\n}\n"


def api(**formals) -> PackageApi:
    return PackageApi(formals, set(formals), set(), set(), False)


def fence(code: str) -> Region:
    return Region("fence", 10, code)


def inline(code: str, first_cell: bool = True) -> Region:
    return Region("inline", 10, code, first_cell=first_cell)


def run(region: Region, **formals):
    return check_region(region, "doc.md", "pkg", api(**formals))


def kinds(findings):
    return sorted((f["check"], f["arg"]) for f in findings)


# ───────────────────────── Rd usage ─────────────────────────


def test_rd_usage_defaults_and_multiline():
    funcs, _ = parse_rd_usage(rd('f(a, b = c("x", "y"),\n  d = list(1, 2), e = NULL)'))
    assert funcs == {"f": ["a", "b", "d", "e"]}


def test_rd_usage_dots_macro_and_comments():
    funcs, _ = parse_rd_usage(rd("g(x, \\dots)  % a comment, with commas\nh(y, \\ldots)"))
    assert funcs == {"g": ["x", "..."], "h": ["y", "..."]}


def test_rd_usage_methods_are_recorded_not_parsed_as_functions():
    funcs, methods = parse_rd_usage(rd("\\method{print}{foo}(x, ...)\n\\S3method{summary}{foo}(object)"))
    assert funcs == {} and methods == {"print.foo", "summary.foo"}


def test_rd_without_usage_or_unbalanced():
    assert parse_rd_usage("\\name{x}\n") == ({}, set())
    assert parse_rd_usage("\\usage{\nf(a, b\n}\n")[0] == {}


def test_rd_usage_default_with_braces_and_escaped_percent():
    funcs, _ = parse_rd_usage(rd("f(a = function(x) { x }, b = 100\\%)"))
    assert funcs == {"f": ["a", "b"]}


# ───────────────────────── NAMESPACE ─────────────────────────


def test_namespace_exports_comma_lists_quotes_and_comments():
    ns = 'export(a, b)\nexport("c")\n# export(hidden)\nexport(`d`)\nS3method(print, foo)\nexportClasses(K)\n'
    assert parse_namespace(ns) == ({"a", "b", "c", "d"}, False)


def test_namespace_export_pattern_flag():
    assert parse_namespace('exportPattern("^[^.]")\nexport(a)') == ({"a"}, True)


# ───────────────────────── regions ─────────────────────────


def test_regions_r_fences_only():
    text = "intro `f(a)` here\n```r\nf(a = 1)\n```\n```bash\nf(b = 2)\n```\n```{r, echo=FALSE}\nf(c = 3)\n```\n```\nf(d = 4)\n```\n~~~r\nf(e = 5)\n~~~\n"
    got = [(r.kind, r.line, r.text) for r in extract_regions(text)]
    assert ("inline", 1, "f(a)") in got
    fences = [t for k, _, t in got if k == "fence"]
    assert fences == ["f(a = 1)", "f(c = 3)", "f(d = 4)", "f(e = 5)"]
    assert next(line for k, line, t in got if t == "f(a = 1)") == 3


def test_regions_inline_inside_fence_are_not_spans():
    assert [r.kind for r in extract_regions("```r\nx <- `f(a)`\n```\n")] == ["fence"]


def test_regions_longer_fence_not_closed_by_shorter():
    assert extract_regions("````r\nf(a = 1)\n```\nf(b = 2)\n````\n")[0].text == "f(a = 1)\n```\nf(b = 2)"


def test_split_args_nests_and_skips_empty():
    assert split_args("a, f(b, c), [d, e], g = {h, i},") == ["a", "f(b, c)", "[d, e]", "g = {h, i}"]


# ───────────────────────── signature-named-arg ─────────────────────────


def test_named_arg_not_a_formal_is_an_error():
    f = run(fence("fixed(alpha = 1, gamma = 2)"), fixed=["alpha", "beta"])
    assert kinds(f) == [("signature-named-arg", "gamma")] and f[0]["severity"] == "error"


def test_named_arg_exact_and_unique_prefix_ok_ambiguous_prefix_flagged():
    formals = {"fixed": ["alpha", "alpine"]}
    assert run(fence("fixed(alpha = 1)"), **formals) == []
    assert kinds(run(fence("fixed(alp = 1)"), **formals)) == [("signature-named-arg", "alp")]
    assert run(fence("fixed(alpi = 1)"), **formals) == []  # unique prefix of `alpine`


def test_variadic_functions_are_exempt_from_every_check():
    assert run(fence("vari(1, 2, 3, anything = 1)"), vari=["x", "..."]) == []
    assert run(inline("vari(x, anything)"), vari=["x", "..."]) == []


def test_equality_and_nested_names_are_not_named_args():
    assert run(fence("fixed(alpha == 1, alpha = c(zzz = 1), beta = list(q = 2))"), fixed=["alpha", "beta"]) == []


def test_comments_and_strings_are_masked():
    code = '# fixed(bogus = 1)\nx <- "fixed(bogus = 1)"\nfixed(alpha = "a, bogus = 2")\n'
    assert run(fence(code), fixed=["alpha"]) == []


def test_foreign_namespace_skipped_own_namespace_checked_method_calls_skipped():
    assert run(fence("stats::fixed(zzz = 1)\nobj$fixed(zzz = 1)\nobj@fixed(zzz = 1)"), fixed=["a"]) == []
    assert kinds(run(fence("pkg::fixed(zzz = 1)"), fixed=["a"])) == [("signature-named-arg", "zzz")]


def test_unexported_or_unknown_function_ignored_and_unbalanced_call_is_safe():
    assert run(fence("other(zzz = 1)"), fixed=["a"]) == []
    assert run(fence("fixed(a = 1, b = (2"), fixed=["a"]) == []


def test_finding_line_number_points_at_the_call():
    f = run(Region("fence", 20, "x <- 1\nfixed(zzz = 1)"), fixed=["a"])
    assert f[0]["line"] == 21 and f[0]["file"] == "doc.md" and f[0]["function"] == "fixed"


# ───────────────────────── signature-arity ─────────────────────────


def test_arity_too_many_positionals_is_a_warning():
    f = run(fence('joint(fit, est, "bca")'), joint=["object", "estimates"])
    assert kinds(f) == [("signature-arity", None)] and f[0]["severity"] == "warn"


def test_arity_exact_fewer_and_named_do_not_count():
    assert run(fence("joint(fit, est)\njoint(fit)\njoint(fit, estimates = e)"), joint=["object", "estimates"]) == []


def test_arity_not_judged_when_call_forwards_dots():
    assert run(fence("joint(a, b, c, ...)"), joint=["object", "estimates"]) == []


def test_arity_zero_formals():
    assert kinds(run(fence("nothing(1)"), nothing=[])) == [("signature-arity", None)]
    assert run(fence("nothing()"), nothing=[]) == []


# ───────────────────────── signature-names ─────────────────────────


def test_names_listing_with_non_formals_one_finding_per_name():
    f = run(inline("joint(x, theta)"), joint=["object", "estimates"])
    assert kinds(f) == [("signature-names", "theta"), ("signature-names", "x")]


def test_names_listing_with_formals_or_non_identifiers_is_clean():
    assert run(inline("joint(object, estimates)"), joint=["object", "estimates"]) == []
    assert run(inline('joint(object, "bca")'), joint=["object", "estimates"]) == []


def test_names_only_judged_for_inline_spans_that_are_a_single_call():
    assert run(fence("joint(x, theta)"), joint=["object", "estimates"]) == []
    assert run(inline("see joint(x, theta) for details"), joint=["object", "estimates"]) == []


def test_names_listing_named_arg_reported_by_named_arg_check_only():
    assert kinds(run(inline("joint(object, bogus = 1)"), joint=["object", "estimates"])) == [("signature-named-arg", "bogus")]


# ───────────────────────── whole-package audit ─────────────────────────


def make_pkg(tmp_path: Path, *, ns: str, rds: dict, docs: dict) -> Path:
    (tmp_path / "man").mkdir()
    (tmp_path / "DESCRIPTION").write_text("Package: pkg\nVersion: 0.1.0\n")
    if ns is not None:
        (tmp_path / "NAMESPACE").write_text(ns)
    for name, usage in rds.items():
        (tmp_path / "man" / f"{name}.Rd").write_text(rd(usage) if usage is not None else "\\name{x}\n")
    for rel, text in docs.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text if isinstance(text, bytes) else text.encode())
    return tmp_path


def test_not_an_r_package(tmp_path):
    r = docaudit.audit_package(tmp_path)
    assert r["findings"] == [] and "not an R package" in r["messages"][0] and r["status"] == "ok"


def test_audit_reports_findings_with_envelope_fields(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a, b)"},
             docs={"README.md": "```r\nf(a = 1, z = 2)\n```\n", "vignettes/v.qmd": "| `f(q)` | listing |\n"})
    r = docaudit.audit_package(tmp_path)
    assert r["kind"] == "docaudit" and r["status"] == "warn" and r["max_severity"] == "error"
    assert [(f["file"], f["check"]) for f in r["findings"]] == [("README.md", "signature-named-arg"), ("vignettes/v.qmd", "signature-names")]
    assert r["engine_missing"] == []


def test_clean_package_is_ok_and_max_severity_none(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "`f(a)`\n"})
    r = docaudit.audit_package(tmp_path)
    assert r["status"] == "ok" and r["max_severity"] == "none"


def test_only_exported_functions_are_checked(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)", "g": "g(a)"}, docs={"README.md": "```r\ng(zzz = 1)\n```\n"})
    assert docaudit.audit_package(tmp_path)["findings"] == []


def test_coverage_summary_counts_reasons(tmp_path):
    make_pkg(tmp_path, ns="export(f, v, nousage, m.cls, re)\n",
             rds={"f": "f(a)", "v": "v(x, \\dots)", "nousage": None, "m": "\\method{m}{cls}(x)",
                  "reexports": "\\alias{re}\nre(x)"},
             docs={})
    s = docaudit.audit_package(tmp_path)["summary"]
    assert s == {"exports": 5, "checked": 1, "unchecked": {"no-usage": 1, "method": 1, "re-export": 1, "variadic": 1}}


def test_export_pattern_treats_documented_functions_as_exported(tmp_path):
    make_pkg(tmp_path, ns='exportPattern("^[^.]")\n', rds={"f": "f(a)"}, docs={"README.md": "```r\nf(z = 1)\n```\n"})
    r = docaudit.audit_package(tmp_path)
    assert len(r["findings"]) == 1 and "exportPattern" in r["messages"][0]


def test_missing_namespace_and_man_do_not_crash(tmp_path):
    (tmp_path / "DESCRIPTION").write_text("Package: pkg\nVersion: 1\n")
    (tmp_path / "README.md").write_text("`f(a)`\n")
    assert docaudit.audit_package(tmp_path)["findings"] == []


def test_crlf_and_non_utf8_docs_do_not_crash(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"},
             docs={"README.md": b"```r\r\nf(z = 1)\r\n```\r\n\xff\xfe junk\n"})
    assert [f["arg"] for f in docaudit.audit_package(tmp_path)["findings"]] == ["z"]


def test_duplicate_findings_are_collapsed(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "```r\nf(z = 1, z = 2)\n```\n"})
    assert len(docaudit.audit_package(tmp_path)["findings"]) == 1


def test_format_text_lists_findings_then_summary(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "```r\nf(z = 1)\n```\n"})
    out = docaudit.format_text(docaudit.audit_package(tmp_path)).splitlines()
    assert out[0].startswith("error") and "README.md:2" in out[0] and out[-1].startswith("checked 1 of 1")


def test_implemented_checks_constant():
    assert docaudit.IMPLEMENTED_CHECKS == {"signature-named-arg", "signature-names", "signature-arity"}


# ───────────────────────── adversarial review #2 regressions ─────────────────────────


def test_rd_usage_string_defaults_do_not_break_formals():
    funcs, _ = parse_rd_usage(rd('f(x, sep = ", ", open = "(", close = ")", y = 1)'))
    assert funcs == {"f": ["x", "sep", "open", "close", "y"]}


def test_rd_usage_escaped_braces_do_not_unbalance_the_block():
    funcs, _ = parse_rd_usage(rd('f(x, pat = "a\\{2\\}")'))
    assert funcs == {"f": ["x", "pat"]}


def test_string_default_does_not_cause_false_named_arg_error(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": 'f(x, sep = ")", y = 1)'}, docs={"README.md": "```r\nf(1, y = 2)\n```\n"})
    assert docaudit.audit_package(tmp_path)["findings"] == []


def test_directory_or_dangling_symlink_named_rd_does_not_raise(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "`f(a)`\n"})
    (tmp_path / "man" / "dir.Rd").mkdir()
    (tmp_path / "man" / "dead.Rd").symlink_to(tmp_path / "nowhere")
    assert docaudit.audit_package(tmp_path)["findings"] == []


def test_unreadable_files_are_skipped_not_raised(tmp_path):
    import os
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "```r\nf(z = 1)\n```\n"})
    (tmp_path / "NAMESPACE").chmod(0)
    try:
        if os.access(tmp_path / "NAMESPACE", os.R_OK):
            pytest.skip("running as a user that can read mode-000 files")
        assert docaudit.audit_package(tmp_path)["status"] in ("ok", "warn")
    finally:
        (tmp_path / "NAMESPACE").chmod(0o644)


def test_audit_package_never_raises(tmp_path, monkeypatch):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={})
    monkeypatch.setattr(docaudit, "read_api", lambda root: (_ for _ in ()).throw(RuntimeError("boom")))
    r = docaudit.audit_package(tmp_path)
    assert r["status"] == "warn" and "boom" in r["messages"][0]


def test_unterminated_fence_at_eof_is_still_audited():
    assert [r.text.strip() for r in extract_regions("```r\nfixed(zzz = 1)\n")] == ["fixed(zzz = 1)"]


def test_form_feed_does_not_shift_line_numbers():
    regions = extract_regions("a\x0cb\n`f(a)`\n")
    assert regions[0].line == 2


def test_huge_region_is_skipped_quickly():
    import time
    t = time.time()
    assert run(fence("f(" * 300_000), f=["a"]) == []
    assert time.time() - t < 2


def test_function_defined_in_the_doc_is_not_the_packages():
    from lib.docaudit import local_definitions
    regions = [fence("f <- function(q) q\nf(zz = 1)")]
    assert local_definitions(regions) == {"f"}
    assert check_region(regions[0], "d.md", "pkg", api(f=["x", "a"]), local_definitions(regions)) == []
    for code in ('f = function(q) q', 'f <<- \\(q) q', 'assign("f", function(q) q)'):
        assert local_definitions([fence(code)]) == {"f"}
    assert local_definitions([fence('x <- "f <- function() 1"')]) == frozenset()  # inside a string


def test_unlabeled_fence_findings_are_downgraded_to_warn(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(x, a = 1)"},
             docs={"README.md": "```\nError in f(x, foo = 1) : unused argument\n```\n\n```r\nf(x, bar = 1)\n```\n"})
    sev = {f["arg"]: f["severity"] for f in docaudit.audit_package(tmp_path)["findings"]}
    assert sev == {"foo": "warn", "bar": "error"}


def test_local_definition_in_one_block_covers_the_whole_file(tmp_path):
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(x, a = 1)"},
             docs={"README.md": "```r\nf <- function(q) q\n```\n\n```r\nf(zz = 1)\n```\n"})
    assert docaudit.audit_package(tmp_path)["findings"] == []


# ───────────────────────── signature-names: signature columns only (triage H1) ─────────────────────────


def test_names_ignores_call_examples_outside_a_table_first_cell():
    """`fit_sem(syntax, data)` in a Routes cell: `syntax` is a variable, not a formal (medfit model-native.qmd)."""
    assert run(inline("fit_sem(syntax, data)", first_cell=False), fit_sem=["model", "data"]) == []


def test_extract_regions_marks_only_whole_first_cell_spans():
    text = ("| `joint(x, theta)` | desc `other(a)` |\n"
            "| **Routes** | `fit_sem(syntax, data)`, or `g(model = syntax)` |\n"
            "Prose `prose(x, theta)` here.\n"
            "|`tight(a)`| no spaces |\n"
            "| `part(a)` more text | cell |\n")
    got = {r.text: r.first_cell for r in extract_regions(text)}
    assert got == {"joint(x, theta)": True, "other(a)": False, "fit_sem(syntax, data)": False,
                   "g(model = syntax)": False, "prose(x, theta)": False, "tight(a)": True, "part(a)": False}


def test_audit_flags_the_refcard_row_but_not_the_routes_row(tmp_path):
    make_pkg(tmp_path, ns="export(joint, fit_sem)\n", rds={"joint": "joint(object, estimates)", "fit_sem": "fit_sem(model, data)"},
             docs={"vignettes/refcard.qmd": "| `joint(x, theta)` | Joint effects |\n",
                   "vignettes/native.qmd": "| **Routes** | `fit_sem(syntax, data)`, or `fit_mediation(model = syntax)` |\n"})
    assert [(f["file"], f["function"]) for f in docaudit.audit_package(tmp_path)["findings"]] == [("vignettes/refcard.qmd", "joint")] * 2


# ───────────────────────── F1: R argument matching (Codex review #3) ─────────────────────────


@pytest.mark.parametrize("call", ["f(alpha = 1, al = 2)", "f(al = 2, alpha = 1)"])
def test_partial_match_uses_the_formal_left_after_exact_matches(call):
    assert run(fence(call), f=["alpha", "alpine"]) == []


def test_genuinely_ambiguous_partial_is_still_flagged():
    assert kinds(run(fence("f(al = 1)"), f=["alpha", "alpine"])) == [("signature-named-arg", "al")]


def test_two_partials_cannot_claim_the_same_formal():
    assert kinds(run(fence("f(alp = 1, alpi = 2)"), f=["alpha", "alpine"])) == [("signature-named-arg", "alp")]
    # R matches partials independently of order: `alp` still sees two candidates (alpha, alpine)
    assert kinds(run(fence("f(alpi = 1, alp = 2)"), f=["alpha", "alpine"])) == [("signature-named-arg", "alp")]
    # two args whose only candidate is the same formal also clash
    assert len(run(fence("f(alpi = 1, alpin = 2)"), f=["alpha", "alpine"])) == 1


def test_partial_of_an_already_exact_formal_is_flagged():
    assert kinds(run(fence("f(alpha = 1, alph = 2)"), f=["alpha", "beta"])) == [("signature-named-arg", "alph")]


def test_unique_partial_among_unrelated_formals_still_ok():
    assert run(fence("f(be = 1, alp = 2)"), f=["alpha", "beta"]) == []


# ───────────────────────── F4: linear scans and a work budget (Codex review #3) ─────────────────────────


def _timed(region, **formals):
    import time
    t = time.perf_counter()
    notes: list = []
    out = check_region(region, "d.md", "pkg", api(**formals), notes=notes)
    return out, notes, time.perf_counter() - t


def test_many_unclosed_calls_just_under_the_size_limit_are_fast():
    out, _, secs = _timed(fence("f(" * 99_000), f=["a"])
    assert out == [] and secs < 3


def test_deeply_nested_balanced_calls_hit_the_budget_not_the_clock():
    out, notes, secs = _timed(fence("f(" * 40_000 + ")" * 40_000), f=["a"])
    assert secs < 5 and any("too much nested call text" in n for n in notes)


def test_oversized_region_is_reported_not_silent():
    out, notes, _ = _timed(fence("x" * 200_001), f=["a"])
    assert out == [] and "over the 200,000 limit" in notes[0] and notes[0].startswith("region at d.md:10")


def test_small_shapes_stay_correct():
    assert run(fence("f(a = 1, f("), f=["a"]) == []  # unclosed outer call ignored, inner too
    f = run(Region("fence", 5, "x <- 1\nf(f(f(zz = 1)))"), f=["a"])
    assert kinds(f) == [("signature-named-arg", "zz")] and f[0]["line"] == 6


def test_budget_note_reaches_the_envelope(tmp_path, monkeypatch):
    monkeypatch.setattr(docaudit, "_WORK_BUDGET", 50)
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "```r\nf(f(f(f(f(zz = 1)))))\n```\n"})
    r = docaudit.audit_package(tmp_path)
    assert any("README.md:2 skipped" in m for m in r["messages"])


# ───────────────────────── Codex re-review: G1 tags/dots, G5 whitespace, G6 duplicates, G2/G3 completeness ─────────────────────────

AA = {"f": ["alpha", "alpine"]}


@pytest.mark.parametrize("call", ['f("alpha"=1, al=2)', "f(`alpha`=1, al=2)", "f('alpha' = 1, al = 2)", "f(al = 2, `alpha` = 1)"])
def test_quoted_and_backticked_tags_count_as_exact_matches(call):
    assert run(fence(call), **AA) == []


def test_quoted_unknown_tag_is_still_flagged_by_its_real_name():
    assert kinds(run(fence('f("zzz" = 1)'), **AA)) == [("signature-named-arg", "zzz")]


def test_forwarded_dots_can_supply_exact_matches_so_partials_are_not_judged():
    assert run(fence("f(..., al = 2)"), **AA) == []
    assert kinds(run(fence("f(..., zzz = 1)"), **AA)) == [("signature-named-arg", "zzz")]  # no formal starts with it


@pytest.mark.parametrize("call", ["other :: f(gamma = 1)", "other\n  ::\n  f(gamma = 1)", "obj$ f(gamma = 1)",
                                  "obj $ f(gamma = 1)", "obj@\nf(gamma = 1)"])
def test_whitespace_does_not_defeat_foreign_call_exclusion(call):
    assert run(fence(call), **AA) == []


def test_whitespace_around_the_packages_own_namespace_is_still_checked():
    assert kinds(run(fence("pkg :: f(gamma = 1)"), **AA)) == [("signature-named-arg", "gamma")]


@pytest.mark.parametrize("call,arg", [("f(alpi = 1, alpi = 2)", "alpi"), ("f(alpha = 1, alpha = 2)", "alpha"),
                                      ("f(alpi = 1, alpin = 2)", "alpin")])
def test_two_arguments_cannot_claim_the_same_formal(call, arg):
    found = run(fence(call), **AA)
    assert kinds(found) == [("signature-named-arg", arg)]
    assert "more than once" in found[0]["message"]


def test_audit_marks_skipped_regions_as_incomplete(tmp_path, monkeypatch):
    monkeypatch.setattr(docaudit, "_WORK_BUDGET", 50)
    make_pkg(tmp_path, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "```r\nf(f(f(f(f(zz = 1)))))\n```\n"})
    assert docaudit.audit_package(tmp_path)["incomplete"] is True
    make_pkg_ok = tmp_path / "ok"
    make_pkg_ok.mkdir()
    make_pkg(make_pkg_ok, ns="export(f)\n", rds={"f": "f(a)"}, docs={"README.md": "`f(a)`\n"})
    assert docaudit.audit_package(make_pkg_ok)["incomplete"] is False


def test_nested_rd_usage_is_budgeted_and_reported(tmp_path):
    import time
    nested = "\\usage{\n" + "f(\n" * 8000 + ")\n" * 8000 + "}\n"
    make_pkg(tmp_path, ns="export(f)\n", rds={}, docs={"README.md": "`f(a)`\n"})
    (tmp_path / "man" / "f.Rd").write_text("\\name{f}\n" + nested)
    t = time.perf_counter()
    r = docaudit.audit_package(tmp_path)
    assert time.perf_counter() - t < 3
    assert r["incomplete"] is True and any("f.Rd" in m and "skipped" in m for m in r["messages"])

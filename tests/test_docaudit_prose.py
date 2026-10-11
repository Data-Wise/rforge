"""T7-T9: scannability, coverage/--since, docs.allowlist for lib/docaudit.py."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import docaudit
from lib.docaudit import scan_prose


def words(n: int) -> str:
    return " ".join(["word"] * n)


def nocov(findings):
    return [f for f in findings if f["check"] != "coverage"]


def checks(findings, check="scannability"):
    return [f for f in findings if f["check"] == check]


# ───────────────────────── T7 scannability ─────────────────────────


def test_long_paragraph_is_info_and_threshold_is_exclusive():
    text = f"# T\n\n{words(111)}\n\n{words(110)}\n"
    f = checks(scan_prose(text, "a.md"))
    assert [(x["line"], x["severity"]) for x in f] == [(3, "info")]


def test_paragraph_threshold_is_configurable():
    text = f"# T\n\n{words(60)}\n"
    assert checks(scan_prose(text, "a.md")) == []
    assert len(checks(scan_prose(text, "a.md", max_paragraph_words=50))) == 1


def test_code_fences_tables_lists_and_front_matter_are_not_paragraphs():
    text = ("---\ntitle: x\n---\n\n```r\n" + words(300) + "\n```\n\n| a | b |\n|---|---|\n| " + words(200)
            + " | x |\n\n- " + words(200) + "\n")
    assert checks(scan_prose(text, "a.md")) == []


def test_long_h2_without_h3_flagged_and_h3s_exempt_it():
    body = "\n\n".join(words(50) for _ in range(17))  # 850 words, no paragraph over limit
    assert len(checks(scan_prose(f"## Big\n\n{body}\n", "a.md"))) == 1
    with_h3 = f"## Big\n\n{body}\n\n### a\n\nx\n\n### b\n\nx\n\n### c\n\nx\n"
    assert checks(scan_prose(with_h3, "a.md")) == []
    assert len(checks(scan_prose(f"## Big\n\n{body}\n\n### a\n\nx\n\n### b\n\nx\n", "a.md"))) == 1


def test_h2_word_count_ignores_code_and_stops_at_next_h2():
    text = f"## A\n\n```r\n{words(900)}\n```\n\n## B\n\n{words(50)}\n"
    assert checks(scan_prose(text, "a.md")) == []


def test_next_steps_not_last_is_flagged_and_last_is_fine():
    mid = "## Next Steps\n\nx\n\n## Later\n\ny\n"
    f = checks(scan_prose(mid, "a.md"))
    assert [(x["line"], x["severity"]) for x in f] == [(1, "info")]
    assert checks(scan_prose("## Later\n\ny\n\n## Next steps\n\nx\n", "a.md")) == []


def test_headings_inside_fences_are_ignored():
    assert checks(scan_prose("```\n## Next Steps\n```\n\n## Later\n\ny\n", "a.md")) == []


def test_crlf_and_unterminated_fence_do_not_crash():
    scan_prose("## A\r\n\r\n```r\r\ncode", "a.md")


def test_scannability_alone_never_makes_status_warn(tmp_path):
    pkg = _pkg(tmp_path)
    (pkg / "README.md").write_text(f"# T\n\nf(1) g(1)\n\n{words(200)}\n")
    r = docaudit.audit_package(pkg)
    assert [f["severity"] for f in r["findings"]] == ["info"]
    assert r["status"] == "ok" and r["max_severity"] == "info"


# ───────────────────────── helpers ─────────────────────────


def _pkg(tmp_path: Path, exports=("f", "g"), docs=None) -> Path:
    pkg = tmp_path / "pkg"
    (pkg / "man").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text("Package: pkg\nVersion: 1.0\n")
    (pkg / "NAMESPACE").write_text("".join(f"export({e})\n" for e in exports))
    for e in exports:
        (pkg / "man" / f"{e}.Rd").write_text(f"\\name{{{e}}}\n\\usage{{\n{e}(x)\n}}\n")
    (pkg / "README.md").write_text(docs or "")
    return pkg


# ───────────────────────── T9 allowlist ─────────────────────────


def bad_call_pkg(tmp_path):
    pkg = _pkg(tmp_path, docs="```r\nf(nope = 1)\ng(1)\n```\n")
    (pkg / "vignettes").mkdir()
    (pkg / "vignettes" / "v.qmd").write_text("```r\nf(nope = 2)\n```\n")
    return pkg


def test_allowlist_file_suppresses_all_findings_in_that_file(tmp_path):
    pkg = bad_call_pkg(tmp_path)
    (pkg / ".rforge.yaml").write_text("docs:\n  allowlist:\n    - README.md\n")
    r = docaudit.audit_package(pkg)
    assert {f["file"] for f in r["findings"]} == {"vignettes/v.qmd"}
    assert r["summary"]["suppressed"] == 1


def test_allowlist_file_check_entry_suppresses_only_that_check(tmp_path):
    pkg = bad_call_pkg(tmp_path)
    (pkg / ".rforge.yaml").write_text("docs:\n  allowlist:\n    - vignettes/v.qmd::scannability\n"
                                      "    - README.md::signature-named-arg\n")
    r = docaudit.audit_package(pkg)
    assert {f["file"] for f in r["findings"]} == {"vignettes/v.qmd"}


def test_allowlist_entry_for_other_check_does_not_suppress(tmp_path):
    pkg = bad_call_pkg(tmp_path)
    (pkg / ".rforge.yaml").write_text("docs:\n  allowlist:\n    - README.md::scannability\n")
    assert len(docaudit.audit_package(pkg)["findings"]) == 2


def test_allowlist_malformed_is_ignored_with_a_message(tmp_path):
    pkg = bad_call_pkg(tmp_path)
    (pkg / ".rforge.yaml").write_text("docs:\n  allowlist: README.md\n")
    r = docaudit.audit_package(pkg)
    assert len(r["findings"]) == 2
    assert any("docs.allowlist" in m and "malformed" in m for m in r["messages"])


def test_allowlist_absent_or_site_only_is_silent(tmp_path):
    pkg = bad_call_pkg(tmp_path)
    (pkg / ".rforge.yaml").write_text("site:\n  allowlist:\n    - README.md\n")
    r = docaudit.audit_package(pkg)
    assert len(r["findings"]) == 2 and not any("allowlist" in m for m in r["messages"])


def test_allowlist_normalizes_leading_dot_slash_and_backslashes(tmp_path):
    pkg = bad_call_pkg(tmp_path)
    (pkg / ".rforge.yaml").write_text("docs:\n  allowlist:\n    - ./vignettes/v.qmd\n")
    assert {f["file"] for f in docaudit.audit_package(pkg)["findings"]} == {"README.md"}


# ───────────────────────── T8 coverage ─────────────────────────


def test_unmentioned_export_is_warn_and_mentioned_is_not(tmp_path):
    pkg = _pkg(tmp_path, docs="Call `f(1)` to start.\n")
    f = checks(docaudit.audit_package(pkg)["findings"], "coverage")
    assert [(x["function"], x["severity"], x["file"]) for x in f] == [("g", "warn", "NAMESPACE")]


def test_mention_is_a_whole_token_not_a_substring(tmp_path):
    pkg = _pkg(tmp_path, exports=("f", "ff"), docs="use ff(1) and my.f here\n")
    assert [x["function"] for x in checks(docaudit.audit_package(pkg)["findings"], "coverage")] == ["f"]


def test_coverage_matrix_in_summary_lists_files(tmp_path):
    pkg = _pkg(tmp_path, docs="f(1)\n")
    (pkg / "vignettes").mkdir()
    (pkg / "vignettes" / "v.Rmd").write_text("g(1) and f(2)\n")
    m = docaudit.audit_package(pkg)["summary"]["coverage_matrix"]
    assert m == {"f": ["README.md", "vignettes/v.Rmd"], "g": ["vignettes/v.Rmd"]}


def test_reexports_and_unexported_are_not_covered(tmp_path):
    pkg = _pkg(tmp_path, docs="nothing\n")
    (pkg / "man" / "reexports.Rd").write_text("\\alias{g}\n")
    assert [x["function"] for x in checks(docaudit.audit_package(pkg)["findings"], "coverage")] == ["f"]


def git(pkg, *a):
    subprocess.run(["git", "-C", str(pkg), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True,
                   capture_output=True)


def test_since_restricts_to_exports_added_after_the_tag(tmp_path):
    pkg = _pkg(tmp_path, exports=("f",), docs="")
    git(pkg, "init", "-q")
    git(pkg, "add", "-A")
    git(pkg, "commit", "-qm", "one")
    git(pkg, "tag", "v1")
    (pkg / "NAMESPACE").write_text("export(f)\nexport(g)\n")
    (pkg / "man" / "g.Rd").write_text("\\name{g}\n\\usage{\ng(x)\n}\n")
    git(pkg, "add", "-A")
    git(pkg, "commit", "-qm", "two")
    r = docaudit.audit_package(pkg, since="v1")
    assert [x["function"] for x in checks(r["findings"], "coverage")] == ["g"]
    assert not r["incomplete"]


def test_since_unknown_ref_is_a_message_skips_coverage_and_marks_incomplete(tmp_path):
    pkg = _pkg(tmp_path, docs="")
    git(pkg, "init", "-q")
    git(pkg, "add", "-A")
    git(pkg, "commit", "-qm", "one")
    r = docaudit.audit_package(pkg, since="nope")
    assert checks(r["findings"], "coverage") == []
    assert r["incomplete"] and any("--since nope" in m for m in r["messages"])


def test_since_outside_a_git_repo_does_not_crash(tmp_path):
    pkg = _pkg(tmp_path, docs="")
    r = docaudit.audit_package(pkg, since="v1")
    assert r["incomplete"] and any("--since v1" in m for m in r["messages"])


def test_since_tag_without_namespace_treats_all_exports_as_new(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "x").write_text("1")
    git(pkg, "init", "-q")
    git(pkg, "add", "-A")
    git(pkg, "commit", "-qm", "zero")
    git(pkg, "tag", "v0")
    _pkg(tmp_path, exports=("f",), docs="")
    git(pkg, "add", "-A")
    git(pkg, "commit", "-qm", "one")
    assert [x["function"] for x in checks(docaudit.audit_package(pkg, since="v0")["findings"], "coverage")] == ["f"]


def test_since_rejects_option_like_refs(tmp_path):
    pkg = _pkg(tmp_path, docs="")
    git(pkg, "init", "-q")
    r = docaudit.audit_package(pkg, since="--output=/tmp/x")
    assert r["incomplete"] and any("--since" in m for m in r["messages"])


def test_cli_since_flag_and_threshold_flags(tmp_path, capsys):
    pkg = _pkg(tmp_path, docs=f"# T\n\n{words(60)}\n")
    docaudit.main(["--path", str(pkg), "--format", "json", "--max-paragraph-words", "50"])
    out = capsys.readouterr().out
    assert '"scannability"' in out


def test_mention_at_the_end_of_a_sentence_counts(tmp_path):
    pkg = _pkg(tmp_path, exports=("f",), docs="Start with f.\n")
    assert checks(docaudit.audit_package(pkg)["findings"], "coverage") == []

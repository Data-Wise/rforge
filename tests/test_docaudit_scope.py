"""T10: D0 scope resolution, --fail-on, --detailed, audit_ecosystem, formatters for lib/docaudit.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from lib import docaudit

ROOT = Path(__file__).resolve().parent.parent
BAD = "```r\nf(nope = 1)\n```\n"


def mkpkg(d: Path, name="pkg", docs=BAD, exports=("f",)) -> Path:
    (d / "man").mkdir(parents=True)
    (d / "DESCRIPTION").write_text(f"Package: {name}\nVersion: 1.0\n")
    (d / "NAMESPACE").write_text("".join(f"export({e})\n" for e in exports))
    for e in exports:
        (d / "man" / f"{e}.Rd").write_text(f"\\name{{{e}}}\n\\usage{{\n{e}(x)\n}}\n")
    (d / "README.md").write_text(docs)
    return d


def run_cli(*args, cwd, home):
    return subprocess.run([sys.executable, "-m", "lib.docaudit", *args], cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, "HOME": str(home), "PYTHONPATH": str(ROOT)})


# ───────────────────────── D0 scope ─────────────────────────


def test_subdirectory_walks_up_to_the_package(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    (pkg / "vignettes" / "sub").mkdir(parents=True)
    s = docaudit.resolve_scope(pkg / "vignettes" / "sub")
    assert s.mode == "package" and s.packages == [pkg.resolve()]
    assert "walked up" in s.line() and s.line().startswith("scope: package pkg")


def test_package_itself_is_not_described_as_walked_up(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    assert "walked up" not in docaudit.resolve_scope(pkg).line()


def test_no_description_and_no_manifest_is_none_with_hint(tmp_path):
    (tmp_path / "x").mkdir()
    s = docaudit.resolve_scope(tmp_path / "x")
    assert s.mode == "none" and "not inside an R package" in s.line() and "--eco" in s.line()


def test_eco_flag_sweeps_siblings_from_inside_a_package(tmp_path):
    a, b = mkpkg(tmp_path / "a", "a"), mkpkg(tmp_path / "b", "b")
    s = docaudit.resolve_scope(a, eco=True)
    assert s.mode == "ecosystem" and s.packages == [a.resolve(), b.resolve()] and "--eco" in s.line()


def test_eco_flag_on_a_non_package_root_sweeps_below(tmp_path):
    a, b = mkpkg(tmp_path / "a", "a"), mkpkg(tmp_path / "b", "b")
    assert docaudit.resolve_scope(tmp_path, eco=True).packages == [a.resolve(), b.resolve()]


def test_manifest_without_flag_sweeps(tmp_path):
    mkpkg(tmp_path / "a", "a"), mkpkg(tmp_path / "b", "b")
    (tmp_path / ".rforge.yaml").write_text("manifest: m.yaml\n")
    (tmp_path / "m.yaml").write_text("ecosystem: x\npackages:\n  - name: a\n  - name: b\n")
    s = docaudit.resolve_scope(tmp_path)
    assert s.mode == "ecosystem" and len(s.packages) == 2 and "manifest" in s.line()


def test_config_without_manifest_does_not_sweep(tmp_path):
    mkpkg(tmp_path / "a", "a")
    (tmp_path / ".rforge.yaml").write_text("kind: single\n")
    assert docaudit.resolve_scope(tmp_path).mode == "none"


def test_one_package_ecosystem_root_with_eco_audits_that_package(tmp_path):
    a = mkpkg(tmp_path / "only", "only")
    s = docaudit.resolve_scope(tmp_path, eco=True)
    assert s.mode == "ecosystem" and s.packages == [a.resolve()]


def test_hybrid_root_audits_root_and_nested(tmp_path):
    root = mkpkg(tmp_path / "root", "root")
    nested = mkpkg(root / "tools" / "inner", "inner")
    (root / ".rforge.yaml").write_text("kind: hybrid\n")
    s = docaudit.resolve_scope(root)
    assert s.mode == "hybrid" and s.packages == [root.resolve(), nested.resolve()]
    assert "hybrid" in s.line()


def test_non_hybrid_package_does_not_audit_nested(tmp_path):
    root = mkpkg(tmp_path / "root", "root")
    mkpkg(root / "tools" / "inner", "inner")
    assert docaudit.resolve_scope(root).packages == [root.resolve()]


def test_package_given_by_name_is_found_under_cwd(tmp_path, monkeypatch):
    a, b = mkpkg(tmp_path / "a", "alpha"), mkpkg(tmp_path / "b", "beta")
    monkeypatch.chdir(tmp_path)
    assert docaudit.resolve_scope("beta").packages == [b.resolve()]


def test_unknown_name_is_none_not_a_crash(tmp_path, monkeypatch):
    mkpkg(tmp_path / "a", "alpha")
    monkeypatch.chdir(tmp_path)
    s = docaudit.resolve_scope("nosuch")
    assert s.mode == "none" and "nosuch" in s.line()


# ───────────────────────── audit() ─────────────────────────


def test_audit_single_package_carries_scope_and_findings(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    r = docaudit.audit(pkg)
    assert r["scope"]["mode"] == "package" and r["scope"]["root"] == str(pkg.resolve())
    assert r["max_severity"] == "error" and r["status"] == "warn"


def test_audit_none_scope_is_an_unaudited_envelope(tmp_path):
    r = docaudit.audit(tmp_path)
    assert r["audited"] is False and r["findings"] == [] and "not inside an R package" in r["messages"][0]


def test_audit_ecosystem_rolls_up_and_tags_packages(tmp_path):
    mkpkg(tmp_path / "a", "a")
    mkpkg(tmp_path / "b", "b", docs="fine\n")
    r = docaudit.audit_ecosystem(tmp_path)
    assert r["scope"]["mode"] == "ecosystem" and r["max_severity"] == "error" and r["audited"]
    assert [f["package"] for f in r["findings"]] == ["a"]
    assert [p["name"] for p in r["packages"]] == ["a", "b"]
    assert r["packages"][1]["max_severity"] == "none"


def test_ecosystem_rollup_incomplete_and_unaudited_propagate(tmp_path):
    a = mkpkg(tmp_path / "a", "a")
    mkpkg(tmp_path / "b", "b")
    (a / "README.md").write_text("```r\n" + "f(" * 5 + "\n" + "x" * 250_000 + "\n```\n")
    assert docaudit.audit_ecosystem(tmp_path)["incomplete"] is True


def test_info_hidden_unless_detailed_and_counted(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="word " * 200 + "\n")
    hidden = docaudit.audit(pkg)
    assert hidden["findings"] == [] and hidden["summary"]["info_hidden"] == 1
    assert hidden["status"] == "ok" and hidden["max_severity"] == "none"
    shown = docaudit.audit(pkg, detailed=True)
    assert [f["severity"] for f in shown["findings"]] == ["info"] and shown["max_severity"] == "info"


def test_coverage_only_runs_with_since(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="nothing here\n")
    assert [f for f in docaudit.audit(pkg, detailed=True)["findings"] if f["check"] == "coverage"] == []
    assert docaudit.audit(pkg)["summary"]["coverage_matrix"] == {}


# ───────────────────────── formatters and CLI ─────────────────────────


def test_text_output_first_line_is_the_scope(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    out = docaudit.format_text(docaudit.audit(pkg))
    assert out.splitlines()[0].startswith("scope: package pkg")
    assert "signature-named-arg" in out


def test_json_roundtrips(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    assert json.loads(docaudit.format_json(docaudit.audit(pkg)))["scope"]["mode"] == "package"


@pytest.mark.parametrize("level,code", [("none", 0), ("warn", 1), ("error", 1)])
def test_fail_on_sets_only_the_exit_code(tmp_path, level, code):
    pkg = mkpkg(tmp_path / "pkg")
    p = run_cli("--path", str(pkg), "--fail-on", level, cwd=ROOT, home=tmp_path)
    assert p.returncode == code and "signature-named-arg" in p.stdout


def test_fail_on_error_ignores_warnings_and_info(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="```\nf(nope = 1)\n```\n")  # bare fence: downgraded to warn
    assert run_cli("--path", str(pkg), "--fail-on", "error", cwd=ROOT, home=tmp_path).returncode == 0
    assert run_cli("--path", str(pkg), "--fail-on", "warn", cwd=ROOT, home=tmp_path).returncode == 1


def test_default_is_fail_on_none_even_with_errors(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    assert run_cli("--path", str(pkg), cwd=ROOT, home=tmp_path).returncode == 0


def test_cli_default_path_is_cwd_with_walk_up(tmp_path):
    pkg = mkpkg(tmp_path / "pkg")
    (pkg / "vignettes").mkdir()
    p = run_cli("--format", "json", cwd=pkg / "vignettes", home=tmp_path)
    assert json.loads(p.stdout)["scope"]["root"] == str(pkg.resolve())


def test_cli_eco_flag_and_detailed_flag(tmp_path):
    mkpkg(tmp_path / "a", "a", docs="word " * 200 + "\n")
    mkpkg(tmp_path / "b", "b")
    p = run_cli("--path", str(tmp_path), "--eco", "--detailed", "--format", "json", cwd=ROOT, home=tmp_path)
    r = json.loads(p.stdout)
    assert {(f["package"], f["check"]) for f in r["findings"]} == {("a", "scannability"), ("b", "signature-named-arg")}


def test_cli_not_in_a_package_exits_zero_with_hint(tmp_path):
    p = run_cli("--path", str(tmp_path), cwd=ROOT, home=tmp_path)
    assert p.returncode == 0 and p.stdout.splitlines()[0].startswith("scope: none")


# ───────────────────────── text must not read as clean (Checkpoint D trial) ─────────────────────────


def test_text_never_says_no_findings_for_an_unaudited_run(tmp_path):
    out = docaudit.format_text(docaudit.audit(tmp_path))
    assert "no findings" not in out and "NOT AUDITED" in out


def test_text_never_says_no_findings_for_an_incomplete_audit(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="fine\n")
    (pkg / "vignettes").mkdir()
    real = os.scandir

    def deny(path):
        if str(path).endswith("vignettes"):
            raise PermissionError(13, "denied", str(path))
        return real(path)

    import unittest.mock as mock
    with mock.patch("os.scandir", deny):
        out = docaudit.format_text(docaudit.audit(pkg))
    assert "no findings" not in out and "INCOMPLETE" in out


def test_text_says_no_findings_only_for_a_complete_clean_audit(tmp_path):
    out = docaudit.format_text(docaudit.audit(mkpkg(tmp_path / "pkg", docs="fine\n")))
    assert "no findings" in out and "INCOMPLETE" not in out and "NOT AUDITED" not in out


def test_text_for_an_ecosystem_rollup_flags_incomplete_members(tmp_path):
    report = {"findings": [], "messages": [], "audited": True, "incomplete": True}
    assert "INCOMPLETE" in docaudit.format_text(report)


# ───────────────────────── Codex review #4 regressions ─────────────────────────


def test_callback_parameter_shadowing_an_export_is_not_judged(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="```r\nlapply(xs, function(f) f(zzz = 1))\nsapply(xs, \\(f) f(zzz = 2))\n```\n")
    assert [f for f in docaudit.audit_package(pkg)["findings"] if f["check"].startswith("signature-")] == []


def test_parameter_names_only_exempt_their_own_names(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="```r\nlapply(xs, function(g) g(1))\nf(nope = 1)\n```\n")
    assert [f["arg"] for f in docaudit.audit_package(pkg)["findings"] if f["check"].startswith("signature-")] == ["nope"]


def test_sweep_reports_a_package_whose_description_cannot_be_read(tmp_path):
    mkpkg(tmp_path / "a", "a")
    b = mkpkg(tmp_path / "b", "b")
    real = docaudit.read_description
    import unittest.mock as mock
    with mock.patch.object(docaudit, "read_description", lambda path: None if Path(path).parent == b.resolve() else real(path)):
        r = docaudit.audit_ecosystem(tmp_path)
    assert r["incomplete"] is True and any("b" in m and "DESCRIPTION" in m for m in r["messages"])
    assert r["scope"]["packages"] == [str((tmp_path / "a").resolve())]  # b is named as omitted, not silently dropped
    assert "INCOMPLETE" in docaudit.format_text(r)


def test_sweep_reports_an_unlistable_directory(tmp_path):
    mkpkg(tmp_path / "a", "a")
    (tmp_path / "locked").mkdir()
    real = Path.iterdir

    def deny(self):
        if self.name == "locked":
            raise PermissionError(13, "denied", str(self))
        return real(self)

    import unittest.mock as mock
    with mock.patch.object(Path, "iterdir", deny):
        r = docaudit.audit_ecosystem(tmp_path)
    assert r["incomplete"] is True and any("locked" in m for m in r["messages"])


def test_hybrid_nested_discovery_failures_are_reported(tmp_path):
    root = mkpkg(tmp_path / "root", "root")
    (root / ".rforge.yaml").write_text("kind: hybrid\n")
    nested = root / "tools" / "inner"
    nested.mkdir(parents=True)
    (nested / "DESCRIPTION").write_text("not a description\n")  # present but unparseable
    r = docaudit.audit(root)
    assert r["incomplete"] is True and any("inner" in m for m in r["messages"])


def test_fail_on_exits_2_when_the_audit_failed(tmp_path, monkeypatch):
    pkg = mkpkg(tmp_path / "pkg")
    monkeypatch.setattr(docaudit, "read_api", lambda root: (_ for _ in ()).throw(PermissionError("denied")))
    assert docaudit.main(["--path", str(pkg), "--fail-on", "error", "--format", "json"]) == 2
    assert docaudit.main(["--path", str(pkg)]) == 0  # default fail-on none is unchanged


def test_fail_on_exits_2_when_nothing_was_audited(tmp_path):
    assert docaudit.main(["--path", str(tmp_path), "--fail-on", "warn"]) == 2
    assert docaudit.main(["--path", str(tmp_path)]) == 0


def test_fail_on_exits_2_for_an_incomplete_audit_with_no_findings(tmp_path):
    pkg = mkpkg(tmp_path / "pkg", docs="fine\n")
    assert docaudit.main(["--path", str(pkg), "--fail-on", "error", "--since", "no-such-ref"]) == 2


def test_fail_on_finding_severity_still_wins_with_exit_1(tmp_path):
    assert docaudit.main(["--path", str(mkpkg(tmp_path / "pkg")), "--fail-on", "error"]) == 1


def test_ecosystem_rollup_carries_audit_failed(tmp_path, monkeypatch):
    mkpkg(tmp_path / "a", "a")
    mkpkg(tmp_path / "b", "b")
    monkeypatch.setattr(docaudit, "read_api", lambda root: (_ for _ in ()).throw(PermissionError("denied")))
    r = docaudit.audit_ecosystem(tmp_path)
    assert r.get("audit_failed") is True and r["audited"] is False


def test_rollup_with_two_survivors_is_still_incomplete_when_a_third_is_unreadable(tmp_path):
    mkpkg(tmp_path / "a", "a")
    mkpkg(tmp_path / "b", "b")
    c = mkpkg(tmp_path / "c", "c")
    real = docaudit.read_description
    import unittest.mock as mock
    with mock.patch.object(docaudit, "read_description", lambda path: None if Path(path).parent == c.resolve() else real(path)):
        r = docaudit.audit_ecosystem(tmp_path)
    assert [p["name"] for p in r["packages"]] == ["a", "b"] and r["incomplete"] is True
    assert any("c" in m and "DESCRIPTION" in m for m in r["messages"])

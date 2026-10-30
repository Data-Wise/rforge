"""Real-R regression for loaded-session masking; never installs dependencies."""

import json
import os
import shutil
import subprocess

import pytest

from lib import rcmd


@pytest.mark.parametrize("user_library_only", [False, True], ids=["default", "user-library"])
def test_unloaded_lint_catches_helper_namespace_and_qualified_fix(
    tmp_path, monkeypatch, user_library_only
):
    if not shutil.which("Rscript") or not shutil.which("R"):
        pytest.skip("R is unavailable")
    for key in ("R_PROFILE_USER", "R_ENVIRON_USER"):
        monkeypatch.setenv(key, str(tmp_path / "absent-startup-file"))
    probe = subprocess.run(
        ["Rscript", "-e", 'if (!all(vapply(c("lintr", "jsonlite", '
         '"testthat"), requireNamespace, logical(1), quietly=TRUE))) quit(status=1); '
         'cat(jsonlite::toJSON(.libPaths()))'],
        capture_output=True, text=True, timeout=30,
    )
    if probe.returncode:
        pytest.skip("lintr/jsonlite/testthat are unavailable")
    dependency_libraries = json.loads(probe.stdout)
    if user_library_only:
        # Model dependencies available through the user library, not a site library.
        empty_site = tmp_path / "empty site library"
        empty_site.mkdir()
        monkeypatch.delenv("R_LIBS", raising=False)
        monkeypatch.setenv("R_LIBS_SITE", str(empty_site))
        monkeypatch.setenv("R_LIBS_USER", os.pathsep.join(dependency_libraries))

    package = tmp_path / "package with spaces"
    library = tmp_path / "library with spaces"
    for directory in (package / "R", package / "tests/testthat", library):
        directory.mkdir(parents=True)
    (package / "DESCRIPTION").write_text(
        "Package: lintfixture\nVersion: 0.0.1\nTitle: Lint Fixture\n"
        "Description: A local lint environment fixture.\nLicense: MIT\n"
        "Author: Test\nMaintainer: Test <test@example.org>\nSuggests: testthat\n"
    )
    (package / "NAMESPACE").write_text("export(identity_value)\n")
    (package / "R/identity.R").write_text("identity_value <- function(x) x\n")
    (package / ".lintr").write_text(
        "linters: lintr::linters_with_defaults(defaults = list(), "
        "object_usage_linter = lintr::object_usage_linter())\n"
    )
    helper = package / "tests/testthat/helper-check.R"
    helper.write_text("check_value <- function(x) {\n  expect_true(x)\n}\n")
    # R_LIBS prepends the fixture without hiding user/site dependency libraries.
    monkeypatch.setenv("R_LIBS", os.pathsep.join([str(library), *dependency_libraries]))
    install = subprocess.run(
        ["R", "CMD", "INSTALL", f"--library={library}", str(package)],
        capture_output=True, text=True, timeout=60,
    )
    assert install.returncode == 0, install.stderr
    selected = subprocess.run(
        ["Rscript", "-e", 'cat(find.package("lintfixture"))'],
        capture_output=True, text=True, timeout=30,
    )
    assert selected.returncode == 0, selected.stderr
    assert os.path.realpath(selected.stdout.strip()) == str((library / "lintfixture").resolve())

    bad = rcmd.run("lint", str(package))
    assert not bad["engine_missing"]
    assert bad["status"] == "warn"
    assert bad["lint"]["count"] == 1
    finding = bad["lint"]["lints"][0]
    assert finding["linter"] == "object_usage_linter"
    assert finding["line"] == 2
    assert "expect_true" in finding["message"]

    loaded = subprocess.run(
        ["Rscript", "-e", "library(testthat); cat(length(lintr::lint_package("
         + json.dumps(str(package)) + ")))"],
        capture_output=True, text=True, timeout=30,
    )
    assert loaded.returncode == 0, loaded.stderr
    assert loaded.stdout.strip() == "0"

    helper.write_text("check_value <- function(x) {\n  testthat::expect_true(x)\n}\n")
    good = rcmd.run("lint", str(package))
    assert not good["engine_missing"]
    assert good["status"] == "ok"
    assert good["lint"] == {"count": 0, "lints": []}

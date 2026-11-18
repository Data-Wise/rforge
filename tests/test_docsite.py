"""#111: `--site` supports Quarto articles and pkgdown development-mode routes (SPEC-site-audit-quarto-devmode).

Deliberately outside `tests/a2`: a test there becomes a required, no-skip A2 node. Offline apart from a
loopback HTTP server; the pkgdown differential tests live in `tests/differential/`.
"""
import functools
import http.server
import json
import subprocess
import threading
from contextlib import contextmanager

import pytest

from lib import _docsite as site
from lib import docaudit

DESC = "Package: fixture\nVersion: {version}\nTitle: Fixture\nDescription: Test fixture.\nLicense: MIT\n"
SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
DEFAULT_QUARTO = "project:\n  render: ['*.qmd']\n"


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@contextmanager
def server(web):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web))
    handler.log_message = lambda *a: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}/"
    finally:
        srv.shutdown(); srv.server_close(); thread.join()


def commit(pkg, files, message="fixture", init=False):
    for name, text in files.items():
        file = pkg / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)
    if init:
        git(pkg, "init", "-b", "main"); git(pkg, "config", "user.email", "f@example.org"); git(pkg, "config", "user.name", "F")
    git(pkg, "add", "-A"); git(pkg, "commit", "-m", message)


def make(tmp_path, *, version="0.0.1", config=None, files=None, rd=True):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    base = {"DESCRIPTION": DESC.format(version=version), "NAMESPACE": ""}
    if rd:
        base["man/internal.Rd"] = "\\name{internal}\n"
    if config is not None:
        base["_pkgdown.yml"] = config
    base.update(files or {})
    commit(pkg, base, init=True)
    return pkg


def sitemap_xml(prefix, routes):
    return f'<urlset xmlns="{SITEMAP_NS}">' + "".join(f"<url><loc>{prefix}{r}</loc></url>" for r in routes) + "</urlset>"


def publish(web, subdir, prefix, routes):
    folder = web / subdir if subdir else web
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "sitemap.xml").write_text(sitemap_xml(prefix, routes))


def no_network(monkeypatch):
    monkeypatch.setattr(site, "sitemap", lambda *a: pytest.fail("a pre-network block reached the network"))


# ---------------------------------------------------------------------------------------------------------
# Mode resolution: expected values are pkgdown 2.2.1's own `dev_mode_auto` output (generated with R).
# ---------------------------------------------------------------------------------------------------------
ORACLE = [
    ("1.2", "release"), ("1.0.0", "release"), ("1.0.8999", "release"), ("1.0.9000", "devel"), ("1.0.9001", "devel"),
    ("0.0.0", "release"), ("0.0.0.9000", "unreleased"), ("0.0.0.1", "unreleased"), ("1.2.3.4", "devel"),
    ("1.0.0-9000", "devel"), ("1.0-9000", "devel"), ("1.2-3-4", "devel"), ("0.0.0-1", "unreleased"),
    ("0.0.0.9000-1", "unreleased"), ("01.02.9000", "devel"), ("1.2.3.0", "devel"), ("1.0.9000.1.2", "devel"),
    ("1", None), ("1.0.1234567890123", None), ("", None), ("abc", None), ("1.2.x", None), ("1..2", None),
    ("1.2.", None), ("1.2-", None), ("-1", None), ("1,2", None),
]


@pytest.mark.parametrize("version,expected", ORACLE)
def test_dev_mode_auto_matches_pkgdown(version, expected):
    if expected is None:
        with pytest.raises(ValueError):
            site.dev_mode_auto(version)
    else:
        assert site.dev_mode_auto(version) == expected


@pytest.mark.parametrize("config,version,mode,prefix", [
    ({}, "0.0.1", "default", ""),
    ({"development": {"mode": "release"}}, "1.0.9000", "release", ""),
    ({"development": {"mode": "default"}}, "1.0.9000", "default", ""),
    ({"development": {"mode": "devel"}}, "1.0.0", "devel", "dev/"),
    ({"development": {"mode": "devel", "destination": "preview"}}, "1.0.0", "devel", "preview/"),
    ({"development": {"mode": "unreleased"}}, "1.0.0", "unreleased", ""),
    ({"development": {"mode": "auto"}}, "0.15.0", "release", ""),
    ({"development": {"mode": "auto"}}, "0.15.0.9000", "devel", "dev/"),
    ({"development": {"mode": "auto"}}, "0.15-9000", "devel", "dev/"),
    ({"development": {"mode": "auto", "destination": "next"}}, "1.0.9000", "devel", "next/"),
    ({"development": {"destination": "dev"}}, "1.0.9000", "default", ""),
    ({"development": None}, "1.0.0", "default", ""),
])
def test_resolve_development(config, version, mode, prefix):
    resolved = site.resolve_development(config, version)
    assert resolved["mode"] == mode and resolved["prefix"] == prefix
    assert resolved["in_dev"] is (mode == "devel") and resolved["pkgdown_rule"] == "2.2.1"


@pytest.mark.parametrize("config,version", [
    ({"development": {"mode": "preview"}}, "1.0.0"), ({"development": {"mode": 3}}, "1.0.0"),
    ({"development": {"mode": ["devel"]}}, "1.0.0"), ({"development": "devel"}, "1.0.0"),
    ({"development": {"mode": "devel", "destination": "a/b"}}, "1.0.0"),
    ({"development": {"mode": "devel", "destination": ".."}}, "1.0.0"),
    ({"development": {"mode": "devel", "destination": ""}}, "1.0.0"),
    ({"development": {"mode": "devel", "destination": 5}}, "1.0.0"),
    ({"development": {"mode": "auto"}}, None), ({"development": {"mode": "auto"}}, "weird"),
    ({"development": {"mode": "auto"}}, "1"),
])
def test_resolve_development_refuses_what_it_cannot_resolve(config, version):
    with pytest.raises(ValueError):
        site.resolve_development(config, version)


@pytest.mark.parametrize("config,version", [({}, None), ({"development": {"mode": "devel"}}, "garbage")])
def test_version_is_only_needed_for_auto(config, version):
    assert site.resolve_development(config, version)["mode"] in ("default", "devel")


# ---------------------------------------------------------------------------------------------------------
# Strict base match: the nine-row matrix (SPEC decision 1). `devel` rows use bs>3.
# ---------------------------------------------------------------------------------------------------------
ROOT, DEV = "https://x.example/pkg/", "https://x.example/pkg/dev/"
MATRIX = [
    ("https://x.example/pkg", ROOT, False, True), ("https://x.example/pkg/", DEV, True, True),
    ("https://x.example/pkg/", ROOT, True, "lacks the dev prefix"), ("https://x.example/pkg/", DEV, False, "mode resolves to the root"),
    ("https://x.example/pkg/", "https://x.example/other/", False, "source url disagrees"),
    ("https://x.example/pkg/", "https://x.example/other/", True, "source url disagrees"),
    (None, DEV, True, True), (None, ROOT, True, "lacks the dev prefix"),
    (None, DEV, False, "mode resolves to the root"), (None, ROOT, False, True),
]


@pytest.mark.parametrize("url,requested,devel,expected", MATRIX)
def test_base_match_matrix(url, requested, devel, expected):
    resolved = site.resolve_development({"development": {"mode": "devel" if devel else "release"}}, "1.0.0")
    if expected is True:
        site.match_base(requested, url, resolved)
    else:
        with pytest.raises(ValueError, match=expected):
            site.match_base(requested, url, resolved)


def test_base_match_uses_the_configured_destination():
    resolved = site.resolve_development({"development": {"mode": "devel", "destination": "preview"}}, "1.0.0")
    site.match_base("https://x.example/pkg/preview/", "https://x.example/pkg", resolved)
    with pytest.raises(ValueError, match="source url disagrees"):
        site.match_base("https://x.example/pkg/dev/", "https://x.example/pkg", resolved)
    with pytest.raises(ValueError):
        site.match_base("https://x.example/pkg/dev/", None, resolved)


def test_wrong_dev_prefix_is_caught_end_to_end(tmp_path, monkeypatch):
    with server(tmp_path / "web") as root:
        pkg = make(tmp_path, version="1.0.0.9000", config=f"url: {root}pkg\ntemplate:\n  bootstrap: 5\ndevelopment:\n  mode: devel\n")
        no_network(monkeypatch)
        r = site.audit(pkg, url=root + "pkg/devel/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]
    assert any("source url disagrees" in x for x in r["reasons"])


# ---------------------------------------------------------------------------------------------------------
# End-to-end mode handling through audit().
# ---------------------------------------------------------------------------------------------------------
ROUTES = ["reference/internal.html"]


@pytest.mark.parametrize("mode,version", [("devel", "1.0.0"), ("auto", "1.0.0.9000"), ("auto", "1.0.9000"), ("auto", "1.0-9000")])
def test_devel_site_audits_under_the_dev_prefix(tmp_path, mode, version):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version=version, config=f"url: {root}pkg\ntemplate:\n  bootstrap: 5\ndevelopment:\n  mode: {mode}\n")
        publish(web, "pkg/dev", root + "pkg/dev/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/dev/", ref="main")
    assert r["state"] == "complete" and r["counts"]["checked"] == 1 and not r["findings"], r
    assert r["development"] == {"mode": "devel", "prefix": "dev/", "destination": "dev", "pkgdown_rule": "2.2.1"}


def test_devel_with_a_removed_page_is_still_a_missing_page(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="1.0.0.9000", config=f"url: {root}pkg\ntemplate:\n  bootstrap: 5\ndevelopment:\n  mode: auto\n")
        publish(web, "pkg/dev", root + "pkg/dev/", [])
        publish(web, "pkg/dev", root + "pkg/dev/", ["articles/other.html"])
        r = site.audit(pkg, url=root + "pkg/dev/", ref="main")
    assert [f["check"] for f in r["findings"]] == ["site-missing-page", "site-extra-page"]
    assert r["findings"][0]["file"] == "man/internal.Rd" and r["findings"][0]["message"].startswith(root + "pkg/dev/reference/")


@pytest.mark.parametrize("requested_suffix,case", [("pkg/", "root URL on a dev site"), ("pkg/devel/", "wrong prefix"), ("elsewhere/", "other path")])
def test_devel_site_with_wrong_requested_base_is_incomplete(tmp_path, monkeypatch, requested_suffix, case):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="1.0.9000", config=f"url: {root}pkg\ntemplate:\n  bootstrap: 5\ndevelopment:\n  mode: auto\n")
        no_network(monkeypatch)
        r = site.audit(pkg, url=root + requested_suffix, ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"], case
    assert r["reasons"]


def test_dev_url_with_a_release_resolving_version_is_incomplete(tmp_path, monkeypatch):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="0.15.0", config=f"url: {root}pkg\ndevelopment:\n  mode: auto\n")
        no_network(monkeypatch)
        r = site.audit(pkg, url=root + "pkg/dev/", ref="main")
    assert r["state"] == "incomplete" and any("mode resolves to the root" in x for x in r["reasons"])


def test_release_site_with_auto_and_a_release_version_audits_the_root(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="0.15.0", config=f"url: {root}pkg\ndevelopment:\n  mode: auto\n")
        publish(web, "pkg", root + "pkg/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
    assert r["state"] == "complete" and r["development"]["mode"] == "release" and r["development"]["prefix"] == ""


@pytest.mark.parametrize("version", ["", "garbage", "1"])
def test_auto_with_an_unparseable_or_missing_version_is_incomplete(tmp_path, monkeypatch, version):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=f"url: {root}pkg\ndevelopment:\n  mode: auto\n")
        commit(pkg, {"DESCRIPTION": DESC.replace("Version: {version}\n", f"Version: {version}\n" if version else "").format(version=version)}, "bad version")
        no_network(monkeypatch)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]
    assert any("Version" in x for x in r["reasons"])


@pytest.mark.parametrize("config_tail", ["", "development:\n  mode: release\n", "development:\n  mode: default\n",
                                         "development:\n  mode: devel\n", "development:\n  mode: unreleased\n"])
@pytest.mark.parametrize("version", [None, "", "garbage", "1", "1.2.", "1..2", "-1"])
def test_every_mode_requires_a_parseable_pinned_version(tmp_path, monkeypatch, config_tail, version):
    """SPEC: a DESCRIPTION without a parseable Version is incomplete, never defaulted: also for explicit modes."""
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=f"url: {root}pkg\ntemplate:\n  bootstrap: 5\n{config_tail}")
        line = "" if version is None else f"Version: {version}\n"
        commit(pkg, {"DESCRIPTION": DESC.replace("Version: {version}\n", line)}, "bad version")
        no_network(monkeypatch)
        base = root + "pkg/dev/" if "devel" in config_tail else root + "pkg/"
        r = site.audit(pkg, url=base, ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]
    assert any("Version" in x for x in r["reasons"])


def test_a_missing_description_is_incomplete_before_the_network(tmp_path, monkeypatch):
    pkg = make(tmp_path, config="development:\n  mode: release\n")
    git(pkg, "rm", "-q", "DESCRIPTION"); git(pkg, "-c", "user.email=a@b", "-c", "user.name=n", "commit", "-qm", "rm")
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0


@pytest.mark.parametrize("version", ["0.0.1", "1.2", "1.0.0-9000", "0.15.0"])
def test_a_parseable_version_does_not_change_an_explicit_mode(tmp_path, version):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version=version, config=f"url: {root}pkg\ndevelopment:\n  mode: release\n")
        publish(web, "pkg", root + "pkg/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
    assert r["state"] == "complete" and r["development"]["mode"] == "release"


@pytest.mark.parametrize("config", ["development:\n  mode: preview\n", "development:\n  mode: devel\n  destination: a/b\n"])
def test_unknown_mode_or_bad_destination_is_incomplete_before_the_network(tmp_path, monkeypatch, config):
    pkg = make(tmp_path, config=config)
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]


@pytest.mark.parametrize("bootstrap,ok", [
    ("template:\n  bootstrap: 5\n", True), ("template:\n  bslib:\n    version: 5\n", True), ("template:\n  bootstrap: 4\n", True),
    ("", False), ("template:\n  bootstrap: 3\n", False), ("template:\n  bslib:\n    version: 3\n", False),
    ("template:\n  bootstrap: 5\n  bslib:\n    version: 5\n", False), ("template:\n  package: tpl\n", False),
    ("template:\n  bootstrap: seven\n", False),
])
def test_bootstrap_version_gates_devel(tmp_path, monkeypatch, bootstrap, ok):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="1.0.0.9000", config=f"url: {root}pkg\n{bootstrap}development:\n  mode: auto\n")
        publish(web, "pkg/dev", root + "pkg/dev/", ROUTES)
        if not ok:
            no_network(monkeypatch)
        r = site.audit(pkg, url=root + "pkg/dev/", ref="main")
    if ok:
        assert r["state"] == "complete" or r["reasons"] == ["custom template mapping unsupported"]
    else:
        assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]


def test_bootstrap_3_devel_gives_a_specific_reason(tmp_path, monkeypatch):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="1.0.9000", config=f"url: {root}pkg\ndevelopment:\n  mode: auto\n")
        no_network(monkeypatch)
        r = site.audit(pkg, url=root + "pkg/dev/", ref="main")
    assert any("Bootstrap 3" in x for x in r["reasons"])


def test_bootstrap_3_release_is_unaffected(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="1.0.0", config=f"url: {root}pkg\n")
        publish(web, "pkg", root + "pkg/", ROUTES)
        assert site.audit(pkg, url=root + "pkg/", ref="main")["state"] == "complete"


def test_no_config_url_rows(tmp_path, monkeypatch):
    """Without a config `url` the requested base is taken as given but must carry the dev prefix iff devel."""
    web = tmp_path / "web"
    with server(web) as root:
        config = "template:\n  bootstrap: 5\ndevelopment:\n  mode: devel\n"
        pkg = make(tmp_path, version="1.0.0", config=config)
        publish(web, "pkg/dev", root + "pkg/dev/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/dev/", ref="main")
        assert r["state"] == "complete"
        no_network(monkeypatch)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
        assert r["state"] == "incomplete" and any("lacks the dev prefix" in x for x in r["reasons"])


def test_no_config_url_release_with_a_dev_looking_url_is_incomplete(tmp_path, monkeypatch):
    pkg = make(tmp_path, version="1.0.0")
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/dev/", ref="main")
    assert r["state"] == "incomplete" and any("mode resolves to the root" in x for x in r["reasons"])


# ---------------------------------------------------------------------------------------------------------
# Config discovery.
# ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("where", ["inst/_pkgdown.yml", "inst/_pkgdown.yaml"])
def test_inst_config_is_read_not_ignored(tmp_path, monkeypatch, where):
    """A devel config only under inst/ must not resolve to release (a false complete on a root URL)."""
    pkg = make(tmp_path, version="1.0.0", files={where: "url: https://x.example/pkg/\ntemplate:\n  bootstrap: 5\ndevelopment:\n  mode: devel\n"})
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0
    assert any("lacks the dev prefix" in x for x in r["reasons"]) and any("overlays" in x for x in r["reasons"])


def test_inst_config_alone_is_incomplete_but_still_audited(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files={"inst/_pkgdown.yml": f"url: {root}pkg\n"})
        publish(web, "pkg", root + "pkg/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 1 and any("overlays" in x for x in r["reasons"])


def test_first_existing_config_wins_without_merging(tmp_path, monkeypatch):
    """pkgdown reads only the first existing candidate: the devel setting in the lower-priority file is ignored."""
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, version="1.0.0", config=f"url: {root}pkg\n", files={"inst/_pkgdown.yml": "development:\n  mode: devel\n"})
        publish(web, "pkg", root + "pkg/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 1 and any("overlays" in x for x in r["reasons"])
    assert r["development"]["mode"] == "default"


def test_two_root_configs_report_overlay(tmp_path, monkeypatch):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=f"url: {root}pkg\n", files={"_pkgdown.yaml": f"url: {root}pkg\n"})
        publish(web, "pkg", root + "pkg/", ROUTES)
        r = site.audit(pkg, url=root + "pkg/", ref="main")
    assert r["state"] == "incomplete" and any("overlays" in x for x in r["reasons"])


# ---------------------------------------------------------------------------------------------------------
# Workflows at the pinned SHA.
# ---------------------------------------------------------------------------------------------------------
WORKFLOW_DEV = "on:\n  push:\n    branches: [main]\nenv:\n  PKGDOWN_DEV_MODE: devel\njobs:\n  build:\n    steps:\n      - run: pkgdown::build_site()\n"


def test_pkgdown_dev_mode_workflow_at_the_pinned_sha_blocks(tmp_path, monkeypatch):
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": WORKFLOW_DEV})
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x for x in r["reasons"]) and not r["findings"]


def test_dev_mode_workflow_hidden_behind_an_older_ref_still_blocks(tmp_path, monkeypatch):
    """The variable lives at the pinned SHA, not in the working tree: the working tree is clean of it."""
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": WORKFLOW_DEV})
    old = git(pkg, "rev-parse", "HEAD")
    commit(pkg, {".github/workflows/pkgdown.yaml": "on: push\njobs:\n  build:\n    steps:\n      - run: pkgdown::build_site()\n"}, "drop it")
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref=old)
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x for x in r["reasons"])


def test_a_workflow_only_in_the_working_tree_is_not_the_pinned_source(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path)
        folder = pkg / ".github/workflows"; folder.mkdir(parents=True)
        (folder / "pkgdown.yaml").write_text(WORKFLOW_DEV)
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert r["state"] == "complete"


@pytest.mark.parametrize("ref_given", [True, False])
def test_reusable_workflow_job_is_unverifiable_with_or_without_ref(tmp_path, monkeypatch, ref_given):
    body = "on:\n  push:\n    branches: [main]\njobs:\n  build:\n    uses: owner/shared/.github/workflows/pkgdown.yml@main\n"
    pkg = make(tmp_path, files={".github/workflows/site.yaml": body})
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main" if ref_given else None)
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]
    assert any("reusable" in x for x in r["reasons"])


def test_step_level_uses_does_not_block(tmp_path):
    """Every real pkgdown workflow has step-level `uses:` (checkout, r-lib/actions); only job-level `uses:` is unverifiable."""
    web = tmp_path / "web"
    body = ("on:\n  push:\n    branches: [main]\njobs:\n  pkgdown:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: actions/checkout@v4\n      - uses: r-lib/actions/setup-r@v2\n      - run: pkgdown::build_site_github_pages()\n")
    with server(web) as root:
        pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": body})
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert r["state"] == "complete"


@pytest.mark.parametrize("name,body", [
    ("ci.yaml", "on: pull_request\njobs:\n  check:\n    uses: r-lib/actions/.github/workflows/check-standard.yaml@v2\n"),
    ("release.yml", "on:\n  push:\n    branches: [main]\njobs:\n  go:\n    uses: ./.github/workflows/shared.yml\n"),
    ("a.yaml", "on: workflow_dispatch\njobs:\n  one:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n  two:\n    uses: org/repo/.github/workflows/w.yml@v1\n"),
])
def test_any_reusable_workflow_job_blocks_even_without_pkgdown_words(tmp_path, monkeypatch, name, body):
    """SPEC decision 2: ANY job-level `uses:` is unverifiable (a generically named reusable workflow can deploy the site)."""
    pkg = make(tmp_path, files={".github/workflows/" + name: body})
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 0 and not r["findings"]
    assert any("reusable workflow job" in x and name in x for x in r["reasons"])


def test_a_reusable_workflow_hidden_from_the_working_tree_still_blocks(tmp_path, monkeypatch):
    body = "on: push\njobs:\n  go:\n    uses: org/shared/.github/workflows/deploy.yml@v1\n"
    pkg = make(tmp_path, files={".github/workflows/deploy.yaml": body})
    old = git(pkg, "rev-parse", "HEAD")
    commit(pkg, {".github/workflows/deploy.yaml": "on: push\njobs:\n  go:\n    steps:\n      - run: echo hi\n"}, "inline it")
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref=old)
    assert r["state"] == "incomplete" and any("reusable workflow job" in x for x in r["reasons"])


def test_step_level_uses_only_workflows_do_not_block(tmp_path):
    web = tmp_path / "web"
    body = "on: pull_request\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
    with server(web) as root:
        pkg = make(tmp_path, files={".github/workflows/check.yaml": body})
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


def test_monorepo_workflow_is_read_from_the_repo_root(tmp_path, monkeypatch):
    repo = tmp_path / "mono"; pkg = repo / "packages" / "p"
    pkg.mkdir(parents=True)
    commit(repo, {"packages/p/DESCRIPTION": DESC.format(version="1.0.0"), "packages/p/man/internal.Rd": "x",
                  ".github/workflows/pkgdown.yaml": WORKFLOW_DEV}, init=True)
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x for x in r["reasons"])


def test_a_development_named_article_does_not_suppress_the_network_call(tmp_path):
    """The old early return matched the substring 'development' in unrelated reasons."""
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files={"vignettes/development.Rmd": "---\noutput: custom::format\n---\n", "vignettes/ok.Rmd": "# ok"})
        publish(web, "", root, ROUTES)
        calls = []
        real = site.sitemap
        site.sitemap = lambda *a: (calls.append(a), real(*a))[1]
        try:
            r = site.audit(pkg, url=root, ref="main")
        finally:
            site.sitemap = real
    assert calls and r["state"] == "incomplete" and r["counts"]["checked"] == 2
    assert any("development.Rmd" in x for x in r["reasons"])
    assert {f["file"] for f in r["findings"] if f["check"] == "site-missing-page"} == {"vignettes/ok.Rmd"}


# ---------------------------------------------------------------------------------------------------------
# Article mapping.
# ---------------------------------------------------------------------------------------------------------
def test_qmd_rmd_and_rmd_map_like_rmd():
    paths = ["vignettes/a.Rmd", "vignettes/b.rmd", "vignettes/c.qmd", "vignettes/articles/d.qmd", "vignettes/n/e/f.qmd", "vignettes/articles/n/g.rmd"]
    routes, reasons, counts = site.routes(paths, {})
    assert routes == {"articles/a.html": paths[0], "articles/b.html": paths[1], "articles/c.html": paths[2], "articles/d.html": paths[3],
                      "articles/n/e/f.html": paths[4], "articles/n/g.html": paths[5]}
    assert not reasons and counts == {"excluded": 0, "unsupported": 0}


@pytest.mark.parametrize("path", ["vignettes/notes.md", "vignettes/x.Rmarkdown", "vignettes/x.RMD", "vignettes/x.Qmd", "vignettes/img.png", "vignettes/x.R"])
def test_non_article_suffixes_are_ignored_not_unsupported(path):
    routes, reasons, counts = site.routes([path], {})
    assert not routes and not reasons and counts["unsupported"] == 0


@pytest.mark.parametrize("path,route", [
    ("vignettes/tutorials/g.Rmd", None), ("vignettes/tutorials-old/h.Rmd", None), ("vignettes/tutorials/sub/g.qmd", None),
    ("vignettes/tutorialsX/a.rmd", None),
    ("vignettes/articles/tutorials/f.Rmd", "articles/tutorials/f.html"), ("vignettes/tutorials.Rmd", "articles/tutorials.html"),
    ("vignettes/_priv/i.Rmd", "articles/_priv/i.html"), ("vignettes/_child.Rmd", None), ("vignettes/sub/_child.qmd", None),
    ("vignettes/mytutorials/j.Rmd", "articles/mytutorials/j.html"),
])
def test_tutorials_is_a_directory_prefix_rule(path, route):
    routes, reasons, counts = site.routes([path], {})
    assert (list(routes) == [route]) if route else (not routes and counts["excluded"] == 1)
    assert not reasons


def test_collision_across_suffixes():
    _, reasons, _ = site.routes(["vignettes/a.Rmd", "vignettes/a.qmd"], {})
    assert any("route collision" in r for r in reasons)


def test_routes_accepts_development_configs_it_cannot_resolve_alone():
    """`routes()` has no version: any valid mode (incl. auto/devel) and any destination keeps the same route shapes."""
    for config in ({"development": {"mode": "devel"}}, {"development": {"mode": "auto"}}, {"development": {"destination": "dev"}}):
        routes, reasons, _ = site.routes(["man/private.Rd"], config)
        assert routes == {"reference/private.html": "man/private.Rd"} and not reasons
    _, reasons, _ = site.routes(["man/private.Rd"], {"development": {"mode": "preview"}})
    assert reasons


# ---------------------------------------------------------------------------------------------------------
# Article front matter: output extension, route-changing overrides, Quarto format.
# ---------------------------------------------------------------------------------------------------------
def article_site(tmp_path, name, text, sitemap_routes=None, extra=None):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files={"vignettes/" + name: text, **(extra or {})})
        stem = name.rsplit(".", 1)[0]
        publish(web, "", root, ROUTES + (sitemap_routes if sitemap_routes is not None else [f"articles/{stem}.html"]))
        return site.audit(pkg, url=root, ref="main")


COMPLETE = [
    ("a.Rmd", "# no front matter"), ("a.Rmd", "---\ntitle: x\n---\n"), ("a.Rmd", "---\noutput: html_document\n---\n"),
    ("a.Rmd", "---\ntitle: x\npkgdown:\n  extension: html\n---\n"), ("a.rmd", "---\ntitle: x\n---\n"),
    ("a.Rmd", "---\noutput:\n  html_vignette:\n    toc: true\n---\n"),
    ("a.qmd", "---\ntitle: x\n---\n"), ("a.qmd", "# no front matter"), ("a.qmd", "---\nformat: html\n---\n"),
    ("a.qmd", "---\nformat:\n  html:\n    toc: true\n---\n"), ("a.qmd", "---\nformat: [html]\n---\n"),
]


@pytest.mark.parametrize("name,text", COMPLETE)
def test_default_articles_map_to_html_and_complete(tmp_path, name, text):
    r = article_site(tmp_path, name, text)
    assert r["state"] == "complete" and r["counts"]["checked"] == 2 and not r["findings"], r


REFUSED = [
    ("a.Rmd", "---\npkgdown:\n  extension: pdf\n---\n", "extension"),
    ("a.Rmd", "---\npkgdown:\n  extension: 5\n---\n", "extension"),
    ("a.Rmd", "---\npkgdown:\n  extension: [html]\n---\n", "extension"),
    ("a.Rmd", "---\npkgdown: 5\n---\n", "extension"),
    ("a.Rmd", "---\noutput_file: other.html\n---\n", "output_file"),
    ("a.Rmd", "---\nknit: custom::knit\n---\n", "knit"),
    ("a.Rmd", "---\noutput:\n  html_document:\n    output_file: x.html\n---\n", "output_file"),
    ("a.qmd", "---\noutput-file: other.html\n---\n", "output-file"),
    ("a.qmd", "---\noutput-ext: pdf\n---\n", "output-ext"),
    ("a.qmd", "---\noutput-dir: x\n---\n", "output-dir"),
    ("a.qmd", "---\nformat:\n  html:\n    output-file: x.html\n---\n", "output-file"),
    ("a.qmd", "---\nformat:\n  html:\n    output_ext: pdf\n---\n", "output_ext"),
    ("a.qmd", "---\nformat: pdf\n---\n", "format"),
    ("a.qmd", "---\nformat:\n  pdf: default\n---\n", "format"),
    ("a.qmd", "---\nformat: [html, pdf]\n---\n", "format"),
    ("a.qmd", "---\nformat:\n  html: default\n  docx: default\n---\n", "format"),
    ("a.qmd", "---\nformat: 5\n---\n", "format"),
    ("a.Rmd", "---\noutput: custom::format\n---\n", "output"),
]


@pytest.mark.parametrize("name,text,key", REFUSED)
def test_route_changing_or_non_html_articles_are_refused_never_invented(tmp_path, name, text, key):
    """Negative fixture keeps the default `.html` route in the sitemap: it must still be incomplete."""
    r = article_site(tmp_path, name, text)
    assert r["state"] == "incomplete" and r["counts"]["unsupported"] == 1 and r["counts"]["checked"] == 1
    assert any(f"vignettes/{name}" in x and key in x for x in r["reasons"]), r["reasons"]
    assert not any(f["file"] == f"vignettes/{name}" and f["check"] == "site-missing-page" for f in r["findings"])


@pytest.mark.parametrize("name,text", [("a.Rmd", "---\npkgdown:\n  extension: pdf\n---\n"), ("a.qmd", "---\nformat: pdf\n---\n"),
                                       ("a.qmd", "---\noutput-file: x.pdf\n---\n")])
def test_non_html_article_never_yields_a_false_missing_page(tmp_path, name, text):
    """A correctly published PDF article is not in the sitemap (html only): expecting its route would be a false finding."""
    r = article_site(tmp_path, name, text, sitemap_routes=[])
    assert r["state"] == "incomplete" and r["counts"]["unsupported"] == 1
    assert not [f for f in r["findings"] if f["check"] == "site-missing-page"]
    assert not any(f["file"] == f"vignettes/{name}" for f in r["findings"])


def test_an_override_scan_is_the_whole_front_matter(tmp_path):
    r = article_site(tmp_path, "a.qmd", "---\ntitle: x\nauthor:\n  - name: y\nextra:\n  deep:\n    - output-file: z\n---\n")
    assert r["state"] == "incomplete" and any("output-file" in x for x in r["reasons"])


def test_unterminated_front_matter_is_incomplete(tmp_path):
    r = article_site(tmp_path, "a.qmd", "---\ntitle: x\n")
    assert r["state"] == "incomplete" and any("unterminated" in x for x in r["reasons"])


# ---------------------------------------------------------------------------------------------------------
# vignettes/_quarto.yaml (SPEC decision 5).
# ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("files,ok", [
    ({}, True),
    ({"vignettes/_quarto.yaml": DEFAULT_QUARTO}, True),
    ({"vignettes/_quarto.yml": DEFAULT_QUARTO}, True),
    ({"vignettes/_quarto.yaml": DEFAULT_QUARTO, "vignettes/_quarto.yml": DEFAULT_QUARTO}, False),
    ({"vignettes/_quarto.yaml": "project:\n  render: ['*.qmd', '!skip.qmd']\n"}, False),
    ({"vignettes/_quarto.yaml": "project:\n  render: ['*.qmd']\n  output-dir: out\n"}, False),
    ({"vignettes/_quarto.yaml": "project:\n  render: ['*.qmd']\nformat: pdf\n"}, False),
    ({"vignettes/_quarto.yaml": "project:\n  type: website\n  render: ['*.qmd']\n"}, False),
    ({"vignettes/_quarto.yaml": "- not\n- a mapping\n"}, False),
])
def test_quarto_project_file_default_is_supported_anything_else_is_not(tmp_path, files, ok):
    r = article_site(tmp_path, "a.qmd", "---\ntitle: x\n---\n", extra=files)
    assert (r["state"] == "complete") is ok, r["reasons"]
    if not ok:
        assert any("_quarto" in x for x in r["reasons"]) and r["counts"]["checked"] == 2


def test_quarto_project_file_is_irrelevant_without_qmd_articles(tmp_path):
    r = article_site(tmp_path, "a.Rmd", "# x", extra={"vignettes/_quarto.yaml": "project:\n  render: ['*.qmd', 'x.md']\n"})
    assert r["state"] == "complete"


# ---------------------------------------------------------------------------------------------------------
# The medfit shape: auto + 0.15.0 + bs5 + a default _quarto.yaml + many .qmd articles (issue #111).
# ---------------------------------------------------------------------------------------------------------
def test_medfit_shape_resolves_to_root_routes(tmp_path):
    web = tmp_path / "web"
    names = [f"vignettes/art{i}.qmd" for i in range(37)] + ["vignettes/articles/nested.qmd", "vignettes/_quarto.yaml", "vignettes/_child.qmd"]
    with server(web) as root:
        files = {n: ("---\ntitle: t\n---\n" if n.endswith(".qmd") else DEFAULT_QUARTO) for n in names}
        pkg = make(tmp_path, version="0.15.0", files=files, config=f"url: {root}medfit/\ntemplate:\n  bootstrap: 5\n  bootswatch: litera\ndevelopment:\n  mode: auto\n")
        routes = ROUTES + [f"articles/art{i}.html" for i in range(37)] + ["articles/nested.html", "articles/extra-quarto-asset.html"]
        publish(web, "medfit", root + "medfit/", routes)
        r = site.audit(pkg, url=root + "medfit/", ref="main")
    assert r["state"] == "complete" and r["counts"]["checked"] == 39 and r["counts"]["missing"] == 0 and r["counts"]["excluded"] == 1
    assert r["counts"]["unsupported"] == 0 and r["development"]["mode"] == "release"
    assert [f["check"] for f in r["findings"]] == ["site-extra-page"]


def test_a_deliberately_removed_qmd_page_is_missing(tmp_path):
    r = article_site(tmp_path, "a.qmd", "---\ntitle: x\n---\n", sitemap_routes=[])
    assert [f["check"] for f in r["findings"]] == ["site-missing-page"] and r["findings"][0]["file"] == "vignettes/a.qmd"


# ---------------------------------------------------------------------------------------------------------
# Freshness marker.
# ---------------------------------------------------------------------------------------------------------
def test_stage_marks_content_freshness_unverified_on_every_path(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path)
        publish(web, "", root, ROUTES)
        ok = site.audit(pkg, url=root, ref="main")
        down = site.audit(pkg, url=root + "missing/", ref="main")
    assert ok["state"] == "complete" and ok["content_freshness"] == "unverified"
    assert down["state"] == "incomplete" and down["content_freshness"] == "unverified"
    assert ok["deploy_layout"] == "unverified" and down["deploy_layout"] == "unverified"


def test_text_verdict_says_content_freshness_unverified(tmp_path, capsys):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path)
        publish(web, "", root, ROUTES)
        code = docaudit.main(["--path", str(pkg), "--package-only", "--site", root, "--ref", "main"])
        out = capsys.readouterr().out
        docaudit.main(["--path", str(pkg), "--package-only", "--site", root, "--ref", "main", "--format", "json"])
        report = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out.rstrip().splitlines()[-1] == "no findings; site content freshness and deploy layout unverified"
    assert report["stages"]["site"]["content_freshness"] == "unverified"
    assert report["stages"]["site"]["deploy_layout"] == "unverified"


def test_text_verdict_is_unchanged_without_a_site_stage(tmp_path, capsys):
    pkg = make(tmp_path)
    docaudit.main(["--path", str(pkg), "--package-only"])
    out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1] == "no findings" and "freshness" not in out


def test_text_verdict_for_an_incomplete_site_stage_stays_incomplete(tmp_path, capsys):
    pkg = make(tmp_path)
    docaudit.main(["--path", str(pkg), "--package-only", "--site", "http://127.0.0.1:9/", "--ref", "main"])
    out = capsys.readouterr().out
    assert "INCOMPLETE" in out and "no findings" not in out



# ---------------------------------------------------------------------------------------------------------
# Review round 4 (#111): seven false-complete paths found by the engine adversarial review. Each fixture below
# reported `complete` (or raised) before its fix.
# ---------------------------------------------------------------------------------------------------------
def audit_args(pkg, **kw):
    return site.audit(pkg, url=kw.pop("url", "https://x.example/pkg/"), ref=kw.pop("ref", "main"))


def link(pkg, name, target):
    """Commit a symlink (`git ls-tree` mode 120000) at `name` pointing at `target`."""
    import os
    path = pkg / name
    path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, path)
    git(pkg, "add", "-A"); git(pkg, "commit", "-m", "link " + name)


# 1. `git ls-tree` C-quotes non-ASCII paths unless -z is used: such files vanished from the expected set.
def test_non_ascii_article_is_expected_and_its_absence_is_a_missing_page(tmp_path):
    r = article_site(tmp_path, "café.Rmd", "# x", sitemap_routes=[])
    assert r["state"] == "complete" and r["counts"]["checked"] == 2, r
    assert [f["file"] for f in r["findings"] if f["check"] == "site-missing-page"] == ["vignettes/café.Rmd"]


def test_non_ascii_article_published_is_complete_and_clean(tmp_path):
    r = article_site(tmp_path, "café.Rmd", "# x", sitemap_routes=["articles/café.html"])
    assert r["state"] == "complete" and r["counts"]["checked"] == 2 and not r["findings"], r


def test_a_package_in_a_non_ascii_subdirectory_is_not_complete_with_nothing_checked(tmp_path):
    web = tmp_path / "web"
    repo = tmp_path / "mono"; pkg = repo / "packages" / "café"
    pkg.mkdir(parents=True)
    commit(repo, {"packages/café/DESCRIPTION": DESC.format(version="1.0.0"), "packages/café/man/internal.Rd": "x"}, init=True)
    with server(web) as root:
        publish(web, "", root, [])
        r = site.audit(pkg, url=root, ref="main")
    assert r["counts"]["checked"] == 1, r
    assert [f["file"] for f in r["findings"] if f["check"] == "site-missing-page"] == ["man/internal.Rd"]


# 2. The old `source.split("---", 2)` split on any `---`, not on the delimiter lines.
@pytest.mark.parametrize("text", [
    "---\ntitle: A --- B\noutput-file: other.html\n---\n# body\n",
    "---\ntitle: x\noutput-file: other.html\n...\n# body\n",
    "---  \noutput-file: other.html\n---  \n",
    "\n\n---\noutput-file: other.html\n---\n",
])
def test_front_matter_is_parsed_by_delimiter_lines_not_by_substring(tmp_path, text):
    r = article_site(tmp_path, "a.qmd", text)
    assert r["state"] == "incomplete" and r["counts"]["unsupported"] == 1
    assert any("output-file" in x and "vignettes/a.qmd" in x for x in r["reasons"]), r["reasons"]


def test_a_dots_terminator_is_valid_front_matter_not_invalid_yaml(tmp_path):
    r = article_site(tmp_path, "a.qmd", "---\ntitle: x\n...\n# body\n")
    assert r["state"] == "complete", r["reasons"]


def test_a_rule_in_the_body_is_not_front_matter(tmp_path):
    r = article_site(tmp_path, "a.qmd", "# body\n\n---\noutput-file: other.html\n---\n")
    assert r["state"] == "complete", r["reasons"]


# 3. `git show` of a symlink returns the link text, never the file: a symlinked article skipped the override check.
def symlink_site(tmp_path, build):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files={"vignettes/real.txt": "---\noutput_file: x.html\n---\n"})
        build(pkg)
        publish(web, "", root, ROUTES + ["articles/a.html"])
        return site.audit(pkg, url=root, ref="main")


def test_a_symlinked_article_is_unsupported_and_its_link_text_is_never_read(tmp_path):
    r = symlink_site(tmp_path, lambda pkg: link(pkg, "vignettes/a.Rmd", "real.txt"))
    assert r["state"] == "incomplete" and r["counts"]["unsupported"] == 1
    assert any("symlink" in x and "vignettes/a.Rmd" in x for x in r["reasons"]), r["reasons"]
    assert not any("output_file" in x for x in r["reasons"])  # the target text was not parsed as front matter
    assert not [f for f in r["findings"] if f["file"] == "vignettes/a.Rmd"]


def test_a_symlinked_vignette_directory_is_unsupported(tmp_path):
    def build(pkg):
        commit(pkg, {"other/b.Rmd": "# b"}, "other")
        link(pkg, "vignettes/sub", "../other")
    r = symlink_site(tmp_path, build)
    assert r["state"] == "incomplete" and any("symlink" in x and "vignettes/sub" in x for x in r["reasons"]), r["reasons"]


def test_a_symlinked_quarto_project_file_is_unsupported(tmp_path):
    def build(pkg):
        commit(pkg, {"vignettes/q.txt": DEFAULT_QUARTO, "vignettes/a.qmd": "# a"}, "qmd")
        link(pkg, "vignettes/_quarto.yml", "q.txt")
    r = symlink_site(tmp_path, build)
    assert r["state"] == "incomplete" and any("symlink" in x and "_quarto.yml" in x for x in r["reasons"]), r["reasons"]


# 4. Directory-level Quarto / R Markdown configuration. pkgdown's real behavior for these files was NOT rendered
#    (no pkgdown fixture build): any such file that could change a format or route is refused, never guessed.
@pytest.mark.parametrize("article,files", [
    ("a.qmd", {"vignettes/_metadata.yml": "format: pdf\n"}),
    ("a.qmd", {"vignettes/_metadata.yaml": "output-dir: out\n"}),
    ("a.qmd", {"vignettes/sub/_metadata.yml": "format: pdf\n"}),
    ("a.qmd", {"vignettes/_quarto-prod.yml": "project:\n  output-dir: out\n"}),
    ("a.qmd", {"vignettes/_quarto-prod.yaml": "format: pdf\n"}),
    ("a.qmd", {"vignettes/sub/_quarto.yml": DEFAULT_QUARTO}),
    ("a.Rmd", {"vignettes/_output.yml": "pdf_document: default\n"}),
    ("a.Rmd", {"vignettes/_output.yaml": "html_document:\n  output_file: x.html\n"}),
    ("a.Rmd", {"vignettes/sub/_output.yml": "pdf_document: default\n"}),
])
def test_directory_level_output_configuration_is_refused(tmp_path, article, files):
    r = article_site(tmp_path, article, "# x", extra=files)
    assert r["state"] == "incomplete" and r["counts"]["checked"] == 2, r
    assert any("directory-level" in x and next(iter(files)).rsplit("/", 1)[1] in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("article,files", [
    ("a.Rmd", {"vignettes/_metadata.yml": "format: pdf\n", "vignettes/_quarto-prod.yml": "x: 1\n"}),  # Quarto-only files, no .qmd
    ("a.qmd", {"vignettes/_output.yml": "pdf_document: default\n"}),                                    # R Markdown-only file, no .Rmd
    ("a.qmd", {"vignettes/_quarto.yml": DEFAULT_QUARTO}),                                                 # the supported default
])
def test_directory_level_files_for_the_other_engine_do_not_block(tmp_path, article, files):
    r = article_site(tmp_path, article, "# x", extra=files)
    assert r["state"] == "complete", r["reasons"]


# 5. PKGDOWN_DEV_MODE and deploy transforms outside `.github/workflows/*` text.
@pytest.mark.parametrize("name,text", [
    (".Renviron", "PKGDOWN_DEV_MODE=devel\n"),
    (".Rprofile", 'Sys.setenv(PKGDOWN_DEV_MODE = "devel")\n'),
    (".Renviron.site", "PKGDOWN_DEV_MODE=devel\n"),
])
def test_dev_mode_in_an_r_startup_file_blocks(tmp_path, monkeypatch, name, text):
    pkg = make(tmp_path, files={name: text})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x and name in x for x in r["reasons"]), r["reasons"]


def test_dev_mode_in_a_repo_root_startup_file_blocks_a_monorepo_package(tmp_path, monkeypatch):
    repo = tmp_path / "mono"; pkg = repo / "packages" / "p"
    pkg.mkdir(parents=True)
    commit(repo, {"packages/p/DESCRIPTION": DESC.format(version="1.0.0"), "packages/p/man/internal.Rd": "x",
                  ".Renviron": "PKGDOWN_DEV_MODE=devel\n"}, init=True)
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x and ".Renviron" in x for x in r["reasons"])


def local_action_workflow(path="./.github/actions/b"):
    return f"on:\n  push:\n    branches: [main]\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: {path}\n"


def test_dev_mode_set_by_a_local_composite_action_blocks(tmp_path, monkeypatch):
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": local_action_workflow(),
                                ".github/actions/b/action.yml": "runs:\n  using: composite\n  steps:\n    - run: echo PKGDOWN_DEV_MODE=devel >> $GITHUB_ENV\n      shell: bash\n"})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x and ".github/actions/b" in x for x in r["reasons"]), r["reasons"]


def test_a_local_action_that_cannot_be_read_is_unresolvable_not_clean(tmp_path, monkeypatch):
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": local_action_workflow()})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("local action" in x and ".github/actions/b" in x for x in r["reasons"]), r["reasons"]


def test_a_clean_local_composite_action_does_not_block(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": local_action_workflow(),
                                    ".github/actions/b/action.yaml": "runs:\n  using: composite\n  steps:\n    - run: echo hi\n      shell: bash\n"})
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


def test_a_local_action_nested_in_a_local_action_is_followed(tmp_path, monkeypatch):
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": local_action_workflow(),
                                ".github/actions/b/action.yml": "runs:\n  using: composite\n  steps:\n    - uses: ./.github/actions/c\n      shell: bash\n",
                                ".github/actions/c/action.yml": "runs:\n  using: composite\n  steps:\n    - run: export PKGDOWN_DEV_MODE=devel\n      shell: bash\n"})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("PKGDOWN_DEV_MODE" in x and ".github/actions/c" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("step", [
    'Rscript -e \'pkgdown::deploy_to_branch(subdir = "v1")\'',
    "Rscript -e 'pkgdown::deploy_to_branch(new_process = FALSE, subdir=\"v1\")'",
])
def test_deploying_to_a_subdirectory_blocks(tmp_path, monkeypatch, step):
    body = f"on:\n  push:\n    branches: [main]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {step}\n"
    pkg = make(tmp_path, files={".github/workflows/deploy.yaml": body})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("subdirectory" in x and "deploy.yaml" in x for x in r["reasons"]), r["reasons"]


def test_a_pages_deploy_action_with_a_target_folder_blocks(tmp_path, monkeypatch):
    body = ("on:\n  push:\n    branches: [main]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - run: Rscript -e 'pkgdown::build_site()'\n"
            "      - uses: JamesIves/github-pages-deploy-action@v4\n        with:\n          folder: docs\n          target-folder: v1\n")
    pkg = make(tmp_path, files={".github/workflows/deploy.yaml": body})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("subdirectory" in x and "deploy.yaml" in x for x in r["reasons"]), r["reasons"]


def test_deploy_to_branch_without_a_subdirectory_does_not_block(tmp_path):
    web = tmp_path / "web"
    body = "on:\n  push:\n    branches: [main]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript -e 'pkgdown::deploy_to_branch()'\n"
    with server(web) as root:
        pkg = make(tmp_path, files={".github/workflows/deploy.yaml": body})
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


# 6. Malformed structure must return an incomplete stage with a specific reason, not raise.
def nested(depth):
    return "[" * depth + "]" * depth


@pytest.mark.parametrize("where,files", [
    ("config", {"_pkgdown.yml": "x: " + nested(5000) + "\n"}),
    ("article", {"vignettes/a.qmd": "---\nx: " + nested(5000) + "\n---\n"}),
    ("workflow", {".github/workflows/w.yaml": "on: push\njobs:\n  b:\n    steps: " + nested(5000) + "\n"}),
])
def test_deeply_nested_yaml_is_incomplete_not_a_crash(tmp_path, monkeypatch, where, files):
    pkg = make(tmp_path, files=files)
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("nested" in x for x in r["reasons"]), r["reasons"]


WORKFLOW_HEAD = "on:\n  push:\n    branches: [main]\n"


@pytest.mark.parametrize("body", [
    "jobs:\n  build:\n",                                                   # null job
    "jobs:\n",                                                             # null jobs
    "jobs:\n  - build\n",                                                  # list jobs
    "jobs:\n  build:\n    steps:\n      - echo hi\n",                      # string step
    "jobs:\n  build:\n    steps:\n",                                      # null steps
    "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v4\n        with:\n",   # `with: null`
    "jobs:\n  build:\n    steps:\n      -\n",                              # null step
])
@pytest.mark.parametrize("ref_given", [True, False])
def test_malformed_workflow_structure_is_incomplete_with_a_reason(tmp_path, monkeypatch, body, ref_given):
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": WORKFLOW_HEAD + "# pkgdown::build_site()\n" + body})
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main" if ref_given else None)
    assert r["state"] == "incomplete" and any("malformed workflow" in x and "pkgdown.yaml" in x for x in r["reasons"]), r["reasons"]


def test_an_alias_bomb_in_front_matter_is_bounded(tmp_path):
    import time
    anchors = ["l0: &l0 [x, x, x, x, x, x, x, x, x]"] + [
        f"l{i}: &l{i} [" + ", ".join([f"*l{i - 1}"] * 9) + "]" for i in range(1, 9)]
    start = time.monotonic()
    r = article_site(tmp_path, "a.qmd", "---\n" + "\n".join(anchors) + "\n---\n")
    assert time.monotonic() - start < 5, "alias expansion was walked as a tree"
    assert r["state"] in ("complete", "incomplete")


def test_a_target_folder_in_a_repository_with_no_pkgdown_workflow_does_not_block(tmp_path):
    web = tmp_path / "web"
    body = ("on:\n  push:\n    branches: [main]\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n"
            "      - uses: JamesIves/github-pages-deploy-action@v4\n        with:\n          folder: cov\n          target-folder: coverage\n")
    with server(web) as root:
        pkg = make(tmp_path, files={".github/workflows/coverage.yaml": body})
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


# ---------------------------------------------------------------------------------------------------------
# Sitemap parsing (Codex round 5): only `loc` that is a direct child of a sitemap-namespace `url` is a page.
# Decision: a urlset outside the sitemaps.org 0.9 namespace (absent or different) is refused with a specific
# reason, never silently counted; a sitemapindex stays refused through its own explicit message.
# ---------------------------------------------------------------------------------------------------------
IMAGE_NS = "http://www.google.com/schemas/sitemap-image/1.1"


def raw_sitemap_audit(tmp_path, build_xml):
    """Audit a package whose deployed sitemap is exactly `build_xml(root)`."""
    web = tmp_path / "web"
    web.mkdir()
    with server(web) as root:
        pkg = make(tmp_path, files={"vignettes/a.qmd": "---\ntitle: x\n---\n"})
        (web / "sitemap.xml").write_text(build_xml(root))
        return site.audit(pkg, url=root, ref="main")


def urlset(*urls, ns=f' xmlns="{SITEMAP_NS}"', extra_ns=""):
    return f"<urlset{ns}{extra_ns}>" + "".join(urls) + "</urlset>"


def ext_url(root, page, ext):
    return f"<url><loc>{root}{page}</loc>{ext}</url>"


def test_a_normal_sitemap_is_still_complete(tmp_path):
    r = raw_sitemap_audit(tmp_path, lambda root: urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES + ["articles/a.html"])))
    assert r["state"] == "complete" and r["counts"]["missing"] == 0 and not r["findings"], r


def test_a_route_present_only_in_an_extension_loc_is_reported_missing(tmp_path):
    """`image:loc` is an image URL, not a page: it must not satisfy the expected article route."""
    def xml(root):
        image = f'<image:image><image:loc>{root}articles/a.html</image:loc></image:image>'
        return urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES), ext_url(root, "", image), extra_ns=f' xmlns:image="{IMAGE_NS}"')
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["counts"]["missing"] == 1 and any(f["check"] == "site-missing-page" for f in r["findings"]), r


def test_an_extension_loc_in_the_default_namespace_under_url_is_not_a_page(tmp_path):
    """A `loc` nested inside another element (even in the sitemap namespace) is not a direct child of `url`."""
    def xml(root):
        nested = f"<wrapper><loc>{root}articles/a.html</loc></wrapper>"
        return urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES), ext_url(root, "", nested))
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["counts"]["missing"] == 1, r


def test_a_loc_outside_a_url_element_is_not_a_page(tmp_path):
    def xml(root):
        return urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES), f"<loc>{root}articles/a.html</loc>")
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["counts"]["missing"] == 1, r


def test_a_url_in_another_namespace_is_not_a_page(tmp_path):
    def xml(root):
        other = f'<x:url xmlns:x="urn:other"><x:loc>{root}articles/a.html</x:loc></x:url>'
        return urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES), other)
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["counts"]["missing"] == 1, r


@pytest.mark.parametrize("ns", ["", ' xmlns="urn:not-a-sitemap"', ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.8"'])
def test_a_sitemap_outside_the_sitemaps_namespace_is_incomplete_with_a_specific_reason(tmp_path, ns):
    r = raw_sitemap_audit(tmp_path, lambda root: urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES + ["articles/a.html"]), ns=ns))
    assert r["state"] == "incomplete" and any("namespace" in x for x in r["reasons"]), r
    assert r["counts"]["missing"] == 0 and not r["findings"]


def test_a_sitemap_index_stays_refused_through_its_own_message(tmp_path):
    r = raw_sitemap_audit(tmp_path, lambda root: f'<sitemapindex xmlns="{SITEMAP_NS}"><sitemap><loc>{root}sitemap2.xml</loc></sitemap></sitemapindex>')
    assert r["state"] == "incomplete" and any("index" in x for x in r["reasons"]), r
    assert not any("namespace" in x for x in r["reasons"])


def test_the_sitemap_reader_counts_only_url_children_for_the_unit_case(tmp_path):
    web = tmp_path / "web"; web.mkdir()
    with server(web) as root:
        image = f'<image:image><image:loc>{root}articles/ext.html</image:loc></image:image>'
        (web / "sitemap.xml").write_text(urlset(f"<url><loc>{root}reference/a.html</loc>{image}</url>", extra_ns=f' xmlns:image="{IMAGE_NS}"'))
        paths, foreign = site.sitemap(root)
    assert paths == {"reference/a.html"} and foreign == 0


# ---------------------------------------------------------------------------------------------------------
# Codex round 6: "this is a pkgdown package" comes from a pkgdown config at the pinned SHA for the package
# directory under audit, not from workflow wording. Build and deploy can sit in different workflows, and the
# build can hide in a local composite action, so neither workflow need contain the word "pkgdown".
# ---------------------------------------------------------------------------------------------------------
BUILD_WORKFLOW = local_action_workflow("./.github/actions/site")
SITE_ACTION = "runs:\n  using: composite\n  steps:\n    - run: ./scripts/site.sh\n      shell: bash\n"   # no pkgdown wording
TARGET_FOLDER_DEPLOY = (WORKFLOW_HEAD + "jobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n"
                        "      - uses: JamesIves/github-pages-deploy-action@v4\n        with:\n          folder: docs\n          target-folder: v1\n")
SUBDIR_DEPLOY = (WORKFLOW_HEAD + "jobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n"
                 "      - run: Rscript -e 'deploy_to_branch(subdir = \"v1\")'\n")
CONFIG = "home:\n  title: Fixture\n"
TWO_WORKFLOWS = {".github/workflows/build.yaml": BUILD_WORKFLOW, ".github/actions/site/action.yml": SITE_ACTION,
                 ".github/workflows/deploy.yaml": TARGET_FOLDER_DEPLOY}


def test_the_two_workflow_fixture_never_mentions_the_word_pkgdown():
    assert not any("pkgdown" in text.lower() for text in TWO_WORKFLOWS.values())


@pytest.mark.parametrize("config_path", ["_pkgdown.yml", "_pkgdown.yaml", "pkgdown/_pkgdown.yml", "pkgdown/_pkgdown.yaml",
                                         "inst/_pkgdown.yml", "inst/_pkgdown.yaml"])
def test_a_target_folder_deploy_blocks_when_a_pkgdown_config_exists_at_the_pinned_sha(tmp_path, monkeypatch, config_path):
    pkg = make(tmp_path, files={**TWO_WORKFLOWS, config_path: CONFIG})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("subdirectory" in x and "deploy.yaml" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("deploy", [SUBDIR_DEPLOY, TARGET_FOLDER_DEPLOY])
def test_either_subdirectory_signal_blocks_with_a_config_and_no_pkgdown_wording(tmp_path, monkeypatch, deploy):
    pkg = make(tmp_path, config=CONFIG, files={".github/workflows/deploy.yaml": deploy})
    assert "pkgdown" not in deploy.lower()
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("subdirectory" in x for x in r["reasons"]), r["reasons"]


def test_a_target_folder_inside_a_local_composite_action_blocks_with_a_config(tmp_path, monkeypatch):
    action = ("runs:\n  using: composite\n  steps:\n    - uses: JamesIves/github-pages-deploy-action@v4\n"
              "      with:\n        folder: docs\n        target-folder: v1\n")
    pkg = make(tmp_path, config=CONFIG, files={".github/workflows/deploy.yaml": local_action_workflow("./.github/actions/d"),
                                               ".github/actions/d/action.yml": action})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("subdirectory" in x and ".github/actions/d" in x for x in r["reasons"]), r["reasons"]


def test_a_config_that_exists_only_in_the_working_tree_does_not_trigger(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files=TWO_WORKFLOWS)
        (pkg / "_pkgdown.yml").write_text(CONFIG)            # untracked: not at the pinned SHA
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert r["state"] == "complete" and not any("subdirectory" in x for x in r["reasons"]), r


def test_a_config_added_after_the_pinned_ref_does_not_trigger(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files=TWO_WORKFLOWS)
        git(pkg, "branch", "pinned")
        commit(pkg, {"_pkgdown.yml": CONFIG}, message="add config after the pin")
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="pinned")
    assert r["state"] == "complete" and not any("subdirectory" in x for x in r["reasons"]), r


def test_a_config_for_a_different_package_in_a_monorepo_does_not_trigger(tmp_path):
    web = tmp_path / "web"
    repo = tmp_path / "mono"; pkg = repo / "packages" / "ours"
    pkg.mkdir(parents=True)
    commit(repo, {"packages/ours/DESCRIPTION": DESC.format(version="1.0.0"), "packages/ours/man/internal.Rd": "x",
                  "packages/other/_pkgdown.yml": CONFIG, ".github/workflows/deploy.yaml": TARGET_FOLDER_DEPLOY}, init=True)
    with server(web) as root:
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert r["state"] == "complete" and not any("subdirectory" in x for x in r["reasons"]), r


def test_this_packages_config_in_a_monorepo_triggers(tmp_path, monkeypatch):
    repo = tmp_path / "mono"; pkg = repo / "packages" / "ours"
    pkg.mkdir(parents=True)
    commit(repo, {"packages/ours/DESCRIPTION": DESC.format(version="1.0.0"), "packages/ours/man/internal.Rd": "x",
                  "packages/ours/_pkgdown.yml": CONFIG, ".github/workflows/deploy.yaml": TARGET_FOLDER_DEPLOY}, init=True)
    no_network(monkeypatch)
    r = site.audit(pkg, url="https://x.example/pkg/", ref="main")
    assert r["state"] == "incomplete" and any("subdirectory" in x for x in r["reasons"]), r["reasons"]


def test_a_repository_with_no_pkgdown_config_and_no_pkgdown_wording_is_unaffected(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, files=TWO_WORKFLOWS)
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


def test_a_pkgdown_repository_with_no_target_folder_stays_complete(tmp_path):
    web = tmp_path / "web"
    plain_deploy = WORKFLOW_HEAD + "jobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo deploy\n"
    with server(web) as root:
        # the action runs ./scripts/site.sh: since round 8 a pkgdown repository must have that script readable at the pinned ref
        pkg = make(tmp_path, config=CONFIG, files={".github/workflows/build.yaml": BUILD_WORKFLOW, ".github/actions/site/action.yml": SITE_ACTION,
                                                   ".github/workflows/deploy.yaml": plain_deploy, "scripts/site.sh": "#!/bin/sh\necho build\n"})
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


def test_the_workflow_text_detection_still_covers_a_pkgdown_repo_with_no_config_file(tmp_path, monkeypatch):
    """Kept: pkgdown builds without a config file, so a workflow that builds it is still evidence of a pkgdown site."""
    pkg = make(tmp_path, files={".github/workflows/deploy.yaml": TARGET_FOLDER_DEPLOY.replace("docs", "pkgdown_out") + "# pkgdown\n"})
    no_network(monkeypatch)
    r = audit_args(pkg)
    assert r["state"] == "incomplete" and any("subdirectory" in x for x in r["reasons"]), r["reasons"]


def test_the_reason_the_engine_gives_is_a_recognized_unsupported_layout_for_the_limit_site_rule():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import verify_a2_release as verifier
    reasons = ["deploy to a subdirectory (.github/workflows/deploy.yaml); the deployed routes cannot be verified",
               "deploy to a subdirectory in local action .github/actions/d; the deployed routes cannot be verified"]
    for reason in reasons:
        assert verifier.limit_run_is_unsupported_layout({"state": "incomplete", "deploy_layout": "unverified", "reasons": [reason]}), reason


# ---------------------------------------------------------------------------------------------------------
# Codex round 7 sweep: every raw-text detection on a YAML input is matched against the plausible spellings.
# Each test names the variant; a variant the old text match missed is marked RED-BEFORE in its comment.
# ---------------------------------------------------------------------------------------------------------
def yaml_ok(text):
    try:
        site.yaml_data(text)
        return True
    except ValueError:
        return False


def wf(body, head=WORKFLOW_HEAD):
    return head + body


def deploy_wf(with_block):
    return wf("jobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: JamesIves/github-pages-deploy-action@v4\n" + with_block)


def run_wf(script):
    indented = "\n".join("          " + line for line in script.split("\n"))
    return wf("jobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n" + indented + "\n")


def blocked(tmp_path, monkeypatch, files, config=CONFIG):
    pkg = make(tmp_path, config=config, files=files)
    no_network(monkeypatch)
    return audit_args(pkg)


def has(r, *words):
    return r["state"] == "incomplete" and any(all(w in x for w in words) for x in r["reasons"])


TARGET_FOLDER_SPELLINGS = [
    pytest.param("        with:\n          folder: docs\n          target-folder: v1\n", id="plain"),
    pytest.param("        with:\n          folder: docs\n          target_folder: v1\n", id="underscore"),
    pytest.param("        with:\n          folder: docs\n          \"target-folder\": v1\n", id="double-quoted-key"),          # RED-BEFORE
    pytest.param("        with:\n          folder: docs\n          'target-folder': v1\n", id="single-quoted-key"),          # RED-BEFORE
    pytest.param("        with: {folder: docs, target-folder: v1}\n", id="flow-mapping"),
    pytest.param("        with: {folder: docs, \"target-folder\": v1}\n", id="flow-mapping-quoted-key"),                     # RED-BEFORE
    pytest.param("        with:\n          folder: docs\n          target-folder: |\n            v1\n", id="block-scalar-value"),
    pytest.param("        with:\n          folder: docs\n          \"target\\x2dfolder\": v1\n", id="yaml-escape-in-key"),     # RED-BEFORE
    pytest.param("        with:\n          folder: docs\n          Target-Folder: v1\n", id="case-variant"),                    # RED-BEFORE
    pytest.param("        with: &w\n          folder: docs\n          \"target-folder\": v1\n      - uses: other/x@v1\n        with: *w\n", id="anchor-and-alias"),  # RED-BEFORE
    pytest.param("        with:\n          folder: docs\n          destination_dir: v1\n", id="peaceiris-destination-dir"),    # RED-BEFORE (same class, new input)
    pytest.param("        with:\n          folder: docs\n          destination-dir: v1\n", id="peaceiris-destination-dir-dashed"),  # RED-BEFORE
]


@pytest.mark.parametrize("with_block", TARGET_FOLDER_SPELLINGS)
def test_every_spelling_of_a_pages_subdirectory_input_blocks_in_a_workflow(tmp_path, monkeypatch, with_block):
    assert yaml_ok(deploy_wf(with_block)), "the fixture must be valid YAML"
    r = blocked(tmp_path, monkeypatch, {".github/workflows/deploy.yaml": deploy_wf(with_block)})
    assert has(r, "subdirectory", "deploy.yaml"), r["reasons"]


@pytest.mark.parametrize("with_block", TARGET_FOLDER_SPELLINGS)
def test_every_spelling_of_a_pages_subdirectory_input_blocks_in_a_local_action(tmp_path, monkeypatch, with_block):
    step = "    - uses: JamesIves/github-pages-deploy-action@v4\n" + "\n".join(line[2:] if line.startswith("  ") else line for line in with_block.split("\n"))
    action = "runs:\n  using: composite\n  steps:\n" + step
    assert yaml_ok(action), action   # the fixture itself must be valid YAML, or only the raw-text net is being tested
    r = blocked(tmp_path, monkeypatch, {".github/workflows/deploy.yaml": local_action_workflow("./.github/actions/d"),
                                        ".github/actions/d/action.yml": action})
    assert has(r, "subdirectory", ".github/actions/d"), (r["reasons"], action)


def test_a_subdirectory_input_set_through_env_blocks(tmp_path, monkeypatch):      # RED-BEFORE for the upper-case spelling
    body = wf("env:\n  TARGET_FOLDER: v1\njobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n")
    assert has(blocked(tmp_path, monkeypatch, {".github/workflows/deploy.yaml": body}), "subdirectory")


@pytest.mark.parametrize("script", [
    "Rscript -e 'pkgdown::deploy_to_branch(subdir = \"v1\")'",
    "Rscript -e 'pkgdown::deploy_to_branch(subdir=\"v1\")'",
    "Rscript -e 'pkgdown::deploy_to_branch(\n  new_process = FALSE,\n  subdir\n    = \"v1\")'",
    "Rscript -e 'pkgdown::deploy_to_branch(new_process = FALSE, \\\n  subdir = \"v1\")'",
    "Rscript -e 'do.call(pkgdown::deploy_to_branch, list(subdir = \"v1\"))'",
    "Rscript -e 'pkgdown::deploy_to_branch(\"subdir\" = \"v1\")'",                  # RED-BEFORE: quoted argument name
    "Rscript -e 'pkgdown::deploy_to_branch(`subdir` = \"v1\")'",                    # RED-BEFORE: backticked argument name
    "Rscript -e 'pkgdown::deploy_to_branch(subdir = NULL)'",                         # conservative: still blocks
], ids=["spaces", "no-spaces", "newline-before-equals", "shell-continuation", "do-call", "quoted-name", "backtick-name", "explicit-null"])
def test_every_spelling_of_deploy_to_branch_subdir_blocks(tmp_path, monkeypatch, script):
    r = blocked(tmp_path, monkeypatch, {".github/workflows/deploy.yaml": run_wf(script)})
    assert has(r, "subdirectory", "deploy.yaml"), r["reasons"]


def test_a_subdir_deploy_is_found_in_a_yaml_escaped_run_string(tmp_path, monkeypatch):   # RED-BEFORE: \\x64 decodes to d
    body = wf("jobs:\n  d:\n    runs-on: ubuntu-latest\n    steps:\n      - run: \"Rscript -e 'pkgdown::\\x64eploy_to_branch(subdir = 1)'\"\n")
    assert has(blocked(tmp_path, monkeypatch, {".github/workflows/deploy.yaml": body}), "subdirectory")


def test_the_pkgdown_wording_heuristic_is_case_insensitive(tmp_path, monkeypatch):       # RED-BEFORE
    body = deploy_wf("        with:\n          folder: docs\n          target-folder: v1\n") + "# PKGDOWN site\n"
    r = blocked(tmp_path, monkeypatch, {".github/workflows/deploy.yaml": body}, config=None)
    assert has(r, "subdirectory"), r["reasons"]


DEV_MODE_SPELLINGS = [
    pytest.param("env:\n  PKGDOWN_DEV_MODE: devel\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n", id="workflow-env"),
    pytest.param("env:\n  \"PKGDOWN_DEV_MODE\": true\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n", id="workflow-env-quoted-key"),
    pytest.param("env:\n  'PKGDOWN_DEV_MODE': devel\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n", id="workflow-env-single-quoted"),
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    env:\n      PKGDOWN_DEV_MODE: devel\n    steps:\n      - run: echo\n", id="job-env"),
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n        env:\n          PKGDOWN_DEV_MODE: devel\n", id="step-env"),
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n        env: {PKGDOWN_DEV_MODE: devel}\n", id="flow-env"),
    pytest.param("x: &e {PKGDOWN_DEV_MODE: devel}\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n        env: *e\n", id="anchor-alias"),
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n          echo \"PKGDOWN_DEV_MODE=devel\" >> $GITHUB_ENV\n", id="github-env-echo"),
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo \"PKGDOWN_DEV_MODE=devel\" >> \"$GITHUB_ENV\"\n", id="github-env-echo-inline"),
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    env:\n      \"PKGDOWN\\x5fDEV_MODE\": devel\n    steps:\n      - run: echo\n", id="yaml-escape"),   # RED-BEFORE
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    env:\n      pkgdown_dev_mode: devel\n    steps:\n      - run: echo\n", id="lower-case-name"),   # RED-BEFORE
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript -e 'Sys.setenv(paste0(\"PKGDOWN_DEV_\", \"MODE\") = \"devel\")'\n", id="r-paste0-split"),   # RED-BEFORE
    pytest.param("jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript -e 'Sys.setenv(paste(\"PKGDOWN\", \"DEV\", \"MODE\", sep = \"_\") = \"devel\")'\n", id="r-paste-sep"),   # RED-BEFORE
]


@pytest.mark.parametrize("body", DEV_MODE_SPELLINGS)
def test_every_spelling_of_the_dev_mode_variable_blocks_in_a_workflow(tmp_path, monkeypatch, body):
    r = blocked(tmp_path, monkeypatch, {".github/workflows/pkgdown.yaml": WORKFLOW_HEAD + body}, config=None)
    assert has(r, "PKGDOWN_DEV_MODE", "pkgdown.yaml"), r["reasons"]


@pytest.mark.parametrize("step", [
    "    - run: echo \"PKGDOWN_DEV_MODE=devel\" >> $GITHUB_ENV\n      shell: bash\n",
    "    - run: echo hi\n      shell: bash\n      env:\n        \"PKGDOWN_DEV_MODE\": devel\n",                         # quoted key
    "    - run: echo hi\n      shell: bash\n      env: {'PKGDOWN_DEV_MODE': devel}\n",                                # flow, single quoted
    "    - run: echo hi\n      shell: bash\n      env:\n        \"PKGDOWN\\x5fDEV_MODE\": devel\n",                  # RED-BEFORE: escape
    "    - run: Rscript -e 'Sys.setenv(paste0(\"PKGDOWN_DEV_\", \"MODE\") = 1)'\n      shell: bash\n",              # RED-BEFORE: split
], ids=["github-env", "quoted-key", "flow-single-quoted", "yaml-escape", "r-paste0-split"])
def test_every_spelling_of_the_dev_mode_variable_blocks_in_a_local_action(tmp_path, monkeypatch, step):
    action = "runs:\n  using: composite\n  steps:\n" + step
    r = blocked(tmp_path, monkeypatch, {".github/workflows/pkgdown.yaml": local_action_workflow("./.github/actions/b"),
                                        ".github/actions/b/action.yml": action}, config=None)
    assert has(r, "PKGDOWN_DEV_MODE", ".github/actions/b"), r["reasons"]


@pytest.mark.parametrize("name,text", [
    (".Renviron", "PKGDOWN_DEV_MODE=devel\n"),
    (".Renviron", "PKGDOWN_DEV_MODE = \"devel\"\n"),
    (".Rprofile", "Sys.setenv(PKGDOWN_DEV_MODE = \"devel\")\n"),
    (".Rprofile", "Sys.setenv(\"PKGDOWN_DEV_MODE\" = \"devel\")\n"),
    (".Rprofile", "Sys.setenv(`PKGDOWN_DEV_MODE` = \"devel\")\n"),
    (".Rprofile", "Sys.setenv(pkgdown_dev_mode = \"devel\")\n"),                                       # RED-BEFORE: case
    (".Rprofile", "Sys.setenv(paste0(\"PKGDOWN_DEV_\", \"MODE\") = \"devel\")\n"),                      # RED-BEFORE: split name
    (".Rprofile", "do.call(Sys.setenv, setNames(list(\"devel\"), paste(\"PKGDOWN\", \"DEV\", \"MODE\", sep = \"_\")))\n"),  # RED-BEFORE
    (".Renviron.site", "PKGDOWN_DEV_MODE=devel\n"),
    (".Rprofile.site", "Sys.setenv(PKGDOWN_DEV_MODE = 'devel')\n"),
], ids=["renviron", "renviron-spaced", "rprofile", "rprofile-quoted", "rprofile-backtick", "rprofile-lower", "rprofile-paste0", "rprofile-setnames-paste", "renviron-site", "rprofile-site"])
def test_every_spelling_of_the_dev_mode_variable_blocks_in_a_startup_file(tmp_path, monkeypatch, name, text):
    r = blocked(tmp_path, monkeypatch, {name: text}, config=None)
    assert has(r, "PKGDOWN_DEV_MODE", name), r["reasons"]


@pytest.mark.parametrize("uses", ["./.github/actions/b", "./.github/actions/b/", "./.github/actions/../actions/b", "\"./.github/actions/b\"", "'./.github/actions/b'"],
                         ids=["plain", "trailing-slash", "dotdot-normalized", "double-quoted", "single-quoted"])
def test_every_spelling_of_a_local_action_reference_is_resolved_and_scanned(tmp_path, monkeypatch, uses):
    wfile = (WORKFLOW_HEAD + f"jobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: {uses}\n")
    action = "runs:\n  using: composite\n  steps:\n    - run: echo PKGDOWN_DEV_MODE=devel >> $GITHUB_ENV\n      shell: bash\n"
    r = blocked(tmp_path, monkeypatch, {".github/workflows/pkgdown.yaml": wfile, ".github/actions/b/action.yml": action}, config=None)
    assert has(r, "PKGDOWN_DEV_MODE", ".github/actions/b"), r["reasons"]


def test_a_local_action_reference_through_a_yaml_alias_is_resolved(tmp_path, monkeypatch):
    wfile = (WORKFLOW_HEAD + "x: &a ./.github/actions/b\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: *a\n")
    action = "runs:\n  using: composite\n  steps:\n    - run: echo PKGDOWN_DEV_MODE=devel >> $GITHUB_ENV\n      shell: bash\n"
    r = blocked(tmp_path, monkeypatch, {".github/workflows/pkgdown.yaml": wfile, ".github/actions/b/action.yml": action}, config=None)
    assert has(r, "PKGDOWN_DEV_MODE", ".github/actions/b"), r["reasons"]


@pytest.mark.parametrize("front", [
    "---\nOutput-File: x.html\n---\n",                 # RED-BEFORE: case
    "---\nOUTPUT_DIR: x\n---\n",                       # RED-BEFORE: case
    "---\n\"output-file\": x.html\n---\n",             # quoted key
    "---\n'output_ext': pdf\n---\n",                   # single-quoted key
    "---\nformat:\n  html:\n    \"output-file\": x.html\n---\n",
    "---\nx: &o {output-file: a.html}\ny: *o\n---\n",  # anchor
    "---\nas-is: true\n---\n",                         # RED-BEFORE: hyphenated spelling
    "---\npkgdown:\n  as-is: true\n---\n",             # RED-BEFORE
    "---\npkgdown: {as_is: true}\n---\n",              # flow mapping
], ids=["case-output-file", "case-output-dir", "double-quoted", "single-quoted", "nested-quoted", "anchor", "as-is-hyphen", "pkgdown-as-is-hyphen", "flow-pkgdown"])
def test_every_spelling_of_a_route_changing_article_key_is_refused(tmp_path, front):
    r = article_site(tmp_path, "a.qmd", front + "# body\n")
    assert r["state"] == "incomplete" and any("a.qmd" in x for x in r["reasons"]), r["reasons"]


def test_select_ref_reads_an_escaped_dev_mode_name_in_a_workflow_job(tmp_path):         # guard: str(job) already decodes
    body = ("on:\n  push:\n    branches: [main]\njobs:\n  b:\n    runs-on: ubuntu-latest\n    env:\n      \"PKGDOWN\\x5fDEV_MODE\": devel\n"
            "    steps:\n      - run: pkgdown::build_site()\n")
    pkg = make(tmp_path, files={".github/workflows/pkgdown.yaml": body})
    with pytest.raises(ValueError, match="development workflow unsupported"):
        site.select_ref(pkg, None)


def test_select_ref_notices_a_deployment_workflow_that_only_uses_the_setup_action(tmp_path):   # RED-BEFORE
    body = "on:\n  push:\n    branches: [release]\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: r-lib/actions/setup-pkgdown@v2\n"
    pkg = make(tmp_path, files={".github/workflows/site.yaml": body})
    git(pkg, "branch", "release")
    assert site.select_ref(pkg, None)["selection"] == "literal workflow branch"


# ---------------------------------------------------------------------------------------------------------
# Codex round 8: route-moving behavior can live in a file a `run:` step executes. Scripts are read at the pinned
# SHA, followed transitively (cycle guard, depth and file caps), and scanned with the same detections as run
# bodies. An unscannable reference fails closed, but only in a pkgdown repository (config at the pinned ref, or
# workflow wording); a readable script with none of the signals never blocks.
# ---------------------------------------------------------------------------------------------------------
DEPLOY_R = "pkgdown::deploy_to_branch(subdir = \"v1\")\n"
CLEAN_R = "cat('hello')\n"
DEPLOY_SH_BODY = "#!/bin/sh\nRscript -e 'pkgdown::deploy_to_branch(subdir = \"v1\")'\n"
SCRIPT_WORKFLOW = ".github/workflows/site.yaml"


def step_workflow(cmd, step_extra="", job_extra="", top=None):
    if top is None:  # tier 1 evidence, so the workflow is strict whatever the destination
        top = "permissions:\n  pages: write\n"
    body = "\n".join("          " + line for line in cmd.split("\n"))
    return (WORKFLOW_HEAD + top + "jobs:\n  site:\n    runs-on: ubuntu-latest\n" + job_extra + "    steps:\n      - run: |\n" + body + "\n" + step_extra)


def script_audit(tmp_path, files, cmd, config=CONFIG, **kw):
    """Audit a package whose workflow runs `cmd` and whose sitemap holds EVERY expected route (the old false-complete)."""
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=config, files={SCRIPT_WORKFLOW: step_workflow(cmd, **kw), **files})
        publish(web, "", root, ROUTES)
        return site.audit(pkg, url=root, ref="main")


def reached(r, *words):
    return r["state"] == "incomplete" and any(all(w in x for w in words) for x in r["reasons"])


def test_the_exact_codex_fixture_is_incomplete_not_complete(tmp_path):
    r = script_audit(tmp_path, {"scripts/deploy.R": DEPLOY_R}, "Rscript scripts/deploy.R", config=None)
    assert reached(r, "subdirectory", "scripts/deploy.R"), r


SUBDIR_REACHED = [
    ("Rscript scripts/deploy.R", {"scripts/deploy.R": DEPLOY_R}),
    ("Rscript --vanilla scripts/deploy.R arg1", {"scripts/deploy.R": DEPLOY_R}),
    ("Rscript -e \"source('scripts/deploy.R')\"", {"scripts/deploy.R": DEPLOY_R}),
    ("Rscript -e 'sys.source(\"scripts/deploy.R\", envir = globalenv())'", {"scripts/deploy.R": DEPLOY_R}),
    ("Rscript -e 'source(file = \"scripts/deploy.R\")'", {"scripts/deploy.R": DEPLOY_R}),
    ("R -f scripts/deploy.R", {"scripts/deploy.R": DEPLOY_R}),
    ("R --file=scripts/deploy.R", {"scripts/deploy.R": DEPLOY_R}),
    ("R --file scripts/deploy.R", {"scripts/deploy.R": DEPLOY_R}),
    ("R CMD BATCH scripts/deploy.R", {"scripts/deploy.R": DEPLOY_R}),
    ("R CMD BATCH --no-save scripts/deploy.R out.Rout", {"scripts/deploy.R": DEPLOY_R}),
    ("bash scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    ("bash -e -x scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    ("sh scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    ("zsh scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    ("source scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    (". scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    ("./scripts/deploy.sh", {"scripts/deploy.sh": DEPLOY_SH_BODY}),
    ("python3 scripts/deploy.py", {"scripts/deploy.py": "import subprocess\nsubprocess.run(['Rscript', '-e', 'pkgdown::deploy_to_branch(subdir=\"v1\")'])\n"}),
    ("cd scripts && Rscript deploy.R", {"scripts/deploy.R": DEPLOY_R}),
    ("echo start\nRscript scripts/deploy.R\necho done", {"scripts/deploy.R": DEPLOY_R}),
    ("Rscript -e \"system('Rscript scripts/deploy.R')\"", {"scripts/deploy.R": DEPLOY_R}),
    ("make deploy", {"Makefile": "deploy:\n\tRscript -e 'pkgdown::deploy_to_branch(subdir = \"v1\")'\n"}),
    ("make -f build/Makefile deploy", {"build/Makefile": "deploy:\n\tRscript -e 'pkgdown::deploy_to_branch(subdir = \"v1\")'\n"}),
    ("make -C scripts deploy", {"scripts/Makefile": "deploy:\n\tRscript -e 'pkgdown::deploy_to_branch(subdir = \"v1\")'\n"}),
    ("make deploy", {"Makefile": "deploy:\n\tRscript scripts/deploy.R\n", "scripts/deploy.R": DEPLOY_R}),
]


@pytest.mark.parametrize("cmd,files", SUBDIR_REACHED)
def test_a_subdirectory_deploy_in_a_script_the_run_step_reaches_is_incomplete(tmp_path, cmd, files):
    r = script_audit(tmp_path, files, cmd)
    assert reached(r, "subdirectory") and not any("deploy_to_branch(subdir" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("cmd,files", [
    ("Rscript scripts/a.R", {"scripts/a.R": "source('scripts/b.R')\n", "scripts/b.R": DEPLOY_R}),
    ("Rscript scripts/a.R", {"scripts/a.R": "sys.source(\"scripts/b.R\", envir = environment())\n", "scripts/b.R": DEPLOY_R}),
    ("Rscript scripts/a.R", {"scripts/a.R": "system(\"bash scripts/b.sh\")\n", "scripts/b.sh": DEPLOY_SH_BODY}),
    ("Rscript scripts/a.R", {"scripts/a.R": "system2('Rscript', c('scripts/b.R'))\n", "scripts/b.R": DEPLOY_R}),
    ("bash scripts/a.sh", {"scripts/a.sh": "#!/bin/sh\nbash scripts/b.sh\n", "scripts/b.sh": DEPLOY_SH_BODY}),
    ("bash scripts/a.sh", {"scripts/a.sh": "#!/bin/sh\nsource ./scripts/b.sh\n", "scripts/b.sh": DEPLOY_SH_BODY}),
    ("bash scripts/a.sh", {"scripts/a.sh": "#!/bin/sh\nRscript scripts/b.R\n", "scripts/b.R": DEPLOY_R}),
    ("make all", {"Makefile": "all:\n\tbash scripts/b.sh\n", "scripts/b.sh": DEPLOY_SH_BODY}),
], ids=["source", "sys-source", "system-bash", "system2", "sh-calls-sh", "sh-sources-sh", "sh-calls-rscript", "make-calls-script"])
def test_a_script_that_reaches_another_script_with_the_signal_is_followed(tmp_path, cmd, files):
    assert reached(script_audit(tmp_path, files, cmd), "subdirectory")


@pytest.mark.parametrize("kw,files,cmd", [
    ({"step_extra": "        working-directory: scripts\n"}, {"scripts/deploy.R": DEPLOY_R}, "Rscript deploy.R"),
    ({"job_extra": "    defaults:\n      run:\n        working-directory: scripts\n"}, {"scripts/deploy.R": DEPLOY_R}, "Rscript deploy.R"),
    ({"top": "defaults:\n  run:\n    working-directory: scripts\n"}, {"scripts/deploy.R": DEPLOY_R}, "Rscript deploy.R"),
    ({"step_extra": "        working-directory: ./scripts/\n"}, {"scripts/deploy.R": DEPLOY_R}, "Rscript deploy.R"),
], ids=["step", "job-defaults", "workflow-defaults", "dot-slash"])
def test_the_working_directory_is_honored_when_resolving_a_script(tmp_path, kw, files, cmd):
    assert reached(script_audit(tmp_path, files, cmd, **kw), "subdirectory", "scripts/deploy.R")


def test_a_script_cycle_terminates_and_clean_scripts_stay_complete(tmp_path):
    files = {"scripts/a.R": "source('scripts/b.R')\n" + CLEAN_R, "scripts/b.R": "source('scripts/a.R')\n"}
    r = script_audit(tmp_path, files, "Rscript scripts/a.R")
    assert r["state"] == "complete", r["reasons"]


def test_a_cycle_whose_second_script_holds_the_signal_is_still_found(tmp_path):
    files = {"scripts/a.R": "source('scripts/b.R')\n", "scripts/b.R": "source('scripts/a.R')\n" + DEPLOY_R}
    assert reached(script_audit(tmp_path, files, "Rscript scripts/a.R"), "subdirectory", "scripts/b.R")


def test_a_chain_deeper_than_the_cap_fails_closed(tmp_path):
    files = {f"s/{i}.R": f"source('s/{i + 1}.R')\n" for i in range(9)}
    files["s/9.R"] = DEPLOY_R
    r = script_audit(tmp_path, files, "Rscript s/0.R")
    assert reached(r, "script reference unsupported", "deep"), r["reasons"]


def test_more_scripts_than_the_file_cap_fail_closed(tmp_path):
    files = {f"s/{i}.R": CLEAN_R for i in range(60)}
    files["s/main.R"] = "".join(f"source('s/{i}.R')\n" for i in range(60))
    r = script_audit(tmp_path, files, "Rscript s/main.R")
    assert reached(r, "script reference unsupported", "too many"), r["reasons"]



UNSCANNABLE = [
    ("Rscript scripts/missing.R", {}, "missing"),
    ("bash scripts/missing.sh", {}, "missing"),
    ("Rscript ../outside.R", {}, "outside the repository"),
    ("Rscript /opt/deploy.R", {}, "absolute"),
    ("Rscript scripts/$NAME.R", {}, "dynamic"),
    ("Rscript \"scripts/${NAME}.R\"", {}, "dynamic"),
    ("Rscript \"scripts/${{ matrix.target }}.R\"", {}, "dynamic"),
    ("bash $(cat which.txt)", {}, "dynamic"),
    ("Rscript `cat which.txt`", {}, "dynamic"),
    ("bash <(curl -s https://example.org/deploy.sh)", {}, "dynamic"),
    ("Rscript -e 'source(paste0(\"scripts/\", f))'", {}, "dynamic"),
    ("Rscript -e 'source(f)'", {}, "dynamic"),
    ("Rscript -e 'system(cmd)'", {}, "dynamic"),
    ("Rscript scripts/bin.R", {"scripts/bin.R": "x\0y"}, "binary"),
    ("Rscript scripts/huge.R", {"scripts/huge.R": "# " + "x" * (1 << 20 + 1)}, "too large"),
]


@pytest.mark.parametrize("cmd,files,why", UNSCANNABLE, ids=[f"{c[:34]}|{w}" for c, _, w in UNSCANNABLE])
def test_an_unscannable_script_reference_fails_closed_in_a_pkgdown_repository(tmp_path, cmd, files, why):
    r = script_audit(tmp_path, files, cmd)           # CONFIG: a pkgdown config exists at the pinned ref
    assert reached(r, "script reference unsupported", why), r["reasons"]


@pytest.mark.parametrize("cmd,files,why", UNSCANNABLE, ids=[f"{c[:34]}|{w}" for c, _, w in UNSCANNABLE])
def test_the_same_unscannable_reference_is_ignored_when_the_repository_is_not_pkgdown(tmp_path, cmd, files, why):
    r = script_audit(tmp_path, files, cmd, config=None)
    assert r["state"] == "complete" and not any("script reference" in x for x in r["reasons"]), r["reasons"]


def test_a_symlinked_script_fails_closed_in_a_pkgdown_repository(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: step_workflow("Rscript scripts/deploy.R"), "scripts/real.R": DEPLOY_R})
        link(pkg, "scripts/deploy.R", "real.R")
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert reached(r, "script reference unsupported", "symlink"), r["reasons"]


def test_a_symlinked_script_is_ignored_when_the_repository_is_not_pkgdown(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=None, files={SCRIPT_WORKFLOW: step_workflow("Rscript scripts/deploy.R"), "scripts/real.R": CLEAN_R})
        link(pkg, "scripts/deploy.R", "real.R")
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


def test_a_script_only_in_the_working_tree_is_not_read(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: step_workflow("Rscript scripts/deploy.R")})
        (pkg / "scripts").mkdir()
        (pkg / "scripts/deploy.R").write_text(DEPLOY_R)       # untracked: not at the pinned SHA
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert reached(r, "script reference unsupported", "missing") and not any("subdirectory" in x for x in r["reasons"]), r["reasons"]


def test_a_script_changed_after_the_pinned_ref_is_not_read(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: step_workflow("Rscript scripts/deploy.R"), "scripts/deploy.R": CLEAN_R})
        git(pkg, "branch", "pinned")
        commit(pkg, {"scripts/deploy.R": DEPLOY_R}, message="move the deploy after the pin")
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="pinned")
    assert r["state"] == "complete", r["reasons"]


def test_a_pkgdown_repository_whose_scripts_are_clean_stays_complete(tmp_path):
    files = {"scripts/coverage.R": "covr::codecov()\n", "scripts/lint.sh": "#!/bin/sh\nRscript -e 'lintr::lint_package()'\n"}
    r = script_audit(tmp_path, files, "Rscript scripts/coverage.R\nbash scripts/lint.sh\nmake -v")
    assert r["state"] == "complete", r["reasons"]


@pytest.mark.parametrize("script", [
    "Sys.setenv(PKGDOWN_DEV_MODE = \"devel\")\n",
    "Sys.setenv(paste0(\"PKGDOWN_DEV_\", \"MODE\") = \"devel\")\n",
    "Sys.setenv(pkgdown_dev_mode = \"devel\")\n",
    "Sys.setenv(`PKGDOWN_DEV_MODE` = 'devel')\n",
], ids=["plain", "paste0-split", "lower-case", "backtick"])
def test_dev_mode_set_inside_a_reached_script_is_detected(tmp_path, script):
    assert reached(script_audit(tmp_path, {"scripts/deploy.R": script}, "Rscript scripts/deploy.R"), "PKGDOWN_DEV_MODE", "scripts/deploy.R")


def test_a_signal_only_inside_an_r_comment_still_blocks_conservatively(tmp_path):
    r = script_audit(tmp_path, {"scripts/deploy.R": "# was: pkgdown::deploy_to_branch(subdir = \"v1\")\n" + CLEAN_R}, "Rscript scripts/deploy.R")
    assert reached(r, "subdirectory"), r["reasons"]


def test_a_pages_target_folder_in_a_script_blocks_in_a_pkgdown_repository(tmp_path):
    files = {"scripts/deploy.sh": "#!/bin/sh\nnpx gh-pages --dest v1 # target-folder: v1\n"}
    assert reached(script_audit(tmp_path, files, "bash scripts/deploy.sh"), "subdirectory", "scripts/deploy.sh")
    (tmp_path / "other").mkdir()
    assert script_audit(tmp_path / "other", files, "bash scripts/deploy.sh", config=None)["state"] == "complete"


def test_a_script_run_from_a_local_composite_action_is_followed(tmp_path):
    action = "runs:\n  using: composite\n  steps:\n    - run: Rscript scripts/deploy.R\n      shell: bash\n"
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: local_action_workflow("./.github/actions/d"), ".github/actions/d/action.yml": action,
                                                   "scripts/deploy.R": DEPLOY_R})
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert reached(r, "subdirectory", "scripts/deploy.R"), r["reasons"]


def test_a_composite_action_working_directory_is_honored(tmp_path):
    action = "runs:\n  using: composite\n  steps:\n    - run: Rscript deploy.R\n      shell: bash\n      working-directory: scripts\n"
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: local_action_workflow("./.github/actions/d"), ".github/actions/d/action.yml": action,
                                                   "scripts/deploy.R": DEPLOY_R})
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert reached(r, "subdirectory", "scripts/deploy.R"), r["reasons"]


def test_the_script_reasons_are_recognized_by_the_limit_site_rule():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import verify_a2_release as verifier
    for reason in ("deploy to a subdirectory in script scripts/deploy.R; the deployed routes cannot be verified",
                   "PKGDOWN_DEV_MODE set in script scripts/deploy.R; development mode mapping unsupported",
                   "script reference unsupported (missing at the pinned ref): scripts/x.R; the deployed routes cannot be verified"):
        assert verifier.limit_run_is_unsupported_layout({"state": "incomplete", "deploy_layout": "unverified", "reasons": [reason]}), reason


UNRELATED_DYNAMIC = "gates <- 'scripts/gate.R'\nsource(file.path('scripts', 'common.R'))\nsystem2(Sys.which('git'), 'status')\n"
QC_WORKFLOW = ".github/workflows/qc.yaml"


def two_workflows(site_text, tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        # round 9: a workflow is relaxed only when it shows no ability to publish, so the unrelated QC workflow is read-only
        pkg = make(tmp_path, config=CONFIG, files={
            SCRIPT_WORKFLOW: site_text, QC_WORKFLOW: step_workflow("Rscript scripts/qc.R", top="permissions: read-all\n"),
            "scripts/qc.R": UNRELATED_DYNAMIC, "scripts/site.R": CLEAN_R})
        publish(web, "", root, ROUTES)
        return site.audit(pkg, url=root, ref="main")


def test_dynamic_script_code_in_an_unrelated_workflow_does_not_block_a_pkgdown_repository(tmp_path):
    """Real repositories run QC and simulation scripts full of source(file.path(...)); only site workflows fail closed."""
    r = two_workflows(step_workflow("Rscript -e 'pkgdown::build_site()'\nRscript scripts/site.R"), tmp_path)
    assert r["state"] == "complete", r["reasons"]


def test_the_same_dynamic_script_code_in_a_workflow_that_names_pkgdown_does_block(tmp_path):
    r = two_workflows(step_workflow("Rscript -e 'pkgdown::build_site()'\nRscript scripts/qc.R"), tmp_path)
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]


def test_a_read_only_workflow_stays_relaxed_even_when_no_workflow_names_pkgdown(tmp_path):
    r = two_workflows(step_workflow("Rscript scripts/site.R", top="permissions: read-all\n"), tmp_path)
    assert r["state"] == "complete", r["reasons"]


def test_with_no_workflow_naming_pkgdown_a_pages_write_workflow_is_strict(tmp_path):
    r = two_workflows(step_workflow("Rscript scripts/qc.R"), tmp_path)
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]


def test_with_no_workflow_naming_pkgdown_a_workflow_without_permissions_is_relaxed_when_the_destination_is_untracked(tmp_path):
    r = two_workflows(step_workflow("Rscript scripts/qc.R", top=""), tmp_path)
    assert r["state"] == "complete", r["reasons"]


def test_a_signal_in_a_script_reached_only_from_an_unrelated_workflow_still_blocks(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={
            SCRIPT_WORKFLOW: step_workflow("Rscript -e 'pkgdown::build_site()'"), QC_WORKFLOW: step_workflow("Rscript scripts/qc.R"),
            "scripts/qc.R": DEPLOY_R})
        publish(web, "", root, ROUTES)
        assert reached(site.audit(pkg, url=root, ref="main"), "subdirectory", "scripts/qc.R")


def test_an_rscript_shell_step_body_is_read_as_r_code(tmp_path):
    """The r-lib pkgdown template runs R directly with `shell: Rscript {0}`."""
    step = "        shell: Rscript {0}\n"
    r = script_audit(tmp_path, {"scripts/deploy.R": DEPLOY_R}, "source('scripts/deploy.R')", step_extra=step)
    assert reached(r, "subdirectory", "scripts/deploy.R"), r["reasons"]
    clean = script_audit(tmp_path / "c", {}, "pkgdown::build_site_github_pages(new_process = FALSE, install = FALSE)", step_extra=step) if (tmp_path / "c").mkdir() is None else None
    assert clean["state"] == "complete", clean["reasons"]


# ---------------------------------------------------------------------------------------------------------
# Codex round 9, medium: `include`/`-include`/`sinclude` in a Makefile are followed (literal paths, under the same
# depth/file caps and visited set). A non-literal or missing include cannot be scanned and fails closed.
# ---------------------------------------------------------------------------------------------------------
SITE_MK = "site:\n\tRscript scripts/deploy.R\n"


@pytest.mark.parametrize("directive", ["include", "-include", "sinclude"])
def test_an_included_makefile_recipe_that_runs_a_route_moving_script_is_found(tmp_path, directive):
    files = {"Makefile": f"{directive} build/site.mk\n", "build/site.mk": SITE_MK, "scripts/deploy.R": DEPLOY_R}
    assert reached(script_audit(tmp_path, files, "make site"), "subdirectory", "scripts/deploy.R")


def test_a_subdirectory_deploy_written_directly_in_an_included_recipe_is_found(tmp_path):
    files = {"Makefile": "include build/site.mk\n", "build/site.mk": "site:\n\tRscript -e 'pkgdown::deploy_to_branch(subdir = \"v1\")'\n"}
    assert reached(script_audit(tmp_path, files, "make site"), "subdirectory", "build/site.mk")


def test_a_nested_include_is_followed(tmp_path):
    files = {"Makefile": "include a.mk\n", "a.mk": "include b.mk\n", "b.mk": SITE_MK, "scripts/deploy.R": DEPLOY_R}
    assert reached(script_audit(tmp_path, files, "make site"), "subdirectory", "scripts/deploy.R")


def test_several_files_on_one_include_line_are_all_followed(tmp_path):
    files = {"Makefile": "include a.mk b.mk\n", "a.mk": "x = 1\n", "b.mk": SITE_MK, "scripts/deploy.R": DEPLOY_R}
    assert reached(script_audit(tmp_path, files, "make site"), "subdirectory", "scripts/deploy.R")


def test_an_include_resolves_from_the_make_directory_and_from_the_makefile_directory(tmp_path):
    # `make -C build` runs recipes in build/, so the recipe reaches the script as ../scripts/deploy.R
    files = {"build/Makefile": "include site.mk\n", "build/site.mk": "site:\n\tRscript ../scripts/deploy.R\n", "scripts/deploy.R": DEPLOY_R}
    assert reached(script_audit(tmp_path, files, "make -C build site"), "subdirectory", "scripts/deploy.R")
    (tmp_path / "other").mkdir()
    files = {"build/Makefile": "include site.mk\n", "build/site.mk": SITE_MK, "scripts/deploy.R": DEPLOY_R}
    assert reached(script_audit(tmp_path / "other", files, "make -f build/Makefile site"), "subdirectory", "scripts/deploy.R")


def test_an_include_cycle_terminates_and_a_clean_include_stays_complete(tmp_path):
    files = {"Makefile": "include a.mk\n", "a.mk": "include Makefile\ninclude b.mk\n", "b.mk": "include a.mk\nclean:\n\trm -f x\n"}
    r = script_audit(tmp_path, files, "make clean")
    assert r["state"] == "complete", r["reasons"]


def test_a_cycle_whose_last_file_holds_the_signal_is_still_found(tmp_path):
    files = {"Makefile": "include a.mk\n", "a.mk": "include b.mk\n", "b.mk": "include a.mk\n" + SITE_MK, "scripts/deploy.R": DEPLOY_R}
    assert reached(script_audit(tmp_path, files, "make site"), "subdirectory")


@pytest.mark.parametrize("directive,target,why", [
    ("include", "missing.mk", "missing"),
    ("-include", "missing.mk", "missing"),
    ("sinclude", "missing.mk", "missing"),
    ("include", "build/*.mk", "dynamic"),
    ("include", "$(DIR)/site.mk", "dynamic"),
    ("-include", "$(wildcard build/*.mk)", "dynamic"),
    ("include", "`ls`", "dynamic"),
    ("include", "../outside.mk", "outside the repository"),
], ids=["missing", "dash-missing", "sinclude-missing", "wildcard", "variable", "wildcard-function", "backtick", "escapes"])
def test_an_include_that_cannot_be_scanned_fails_closed_in_a_pkgdown_repository(tmp_path, directive, target, why):
    r = script_audit(tmp_path, {"Makefile": f"{directive} {target}\nsite:\n\techo hi\n"}, "make site")
    assert reached(r, "script reference unsupported", why), r["reasons"]


def test_an_unscannable_include_is_ignored_when_the_repository_is_not_pkgdown(tmp_path):
    r = script_audit(tmp_path, {"Makefile": "include missing.mk\ninclude $(DIR)/x.mk\nsite:\n\techo hi\n"}, "make site", config=None)
    assert r["state"] == "complete", r["reasons"]


def test_an_include_of_a_symlink_fails_closed(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: step_workflow("make site"), "Makefile": "include site.mk\n", "real.mk": "x = 1\n"})
        link(pkg, "site.mk", "real.mk")
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert reached(r, "script reference unsupported", "symlink"), r["reasons"]


def test_makefile_text_that_only_mentions_include_in_a_recipe_or_comment_is_not_an_include(tmp_path):
    files = {"Makefile": "# include missing.mk\nsite:\n\t@echo 'include missing.mk'\n"}
    assert script_audit(tmp_path, files, "make site")["state"] == "complete"


# ---------------------------------------------------------------------------------------------------------
# Codex round 9, high: a workflow is relaxed (unscannable script references do not fail closed) only when it shows NO
# ability to publish. Default is strict for every workflow and local action in a pkgdown repository. Decision on
# permissions: a missing `permissions:` key (workflow and job) means the default token scope is unknown, so it counts as
# capable; `permissions: {}`, `read-all` or a mapping without pages/contents/id-token write is read-only.
# ---------------------------------------------------------------------------------------------------------
DYNAMIC_SITE_R = "root <- Sys.getenv('ROOT')\nsource(file.path(root, 'x.R'))\n"
SITE_A = step_workflow("Rscript -e 'pkgdown::build_site()'", top="permissions: read-all\n")


def workflow_b(top="", job_extra="", steps="", cmd="Rscript scripts/site.R"):
    return (WORKFLOW_HEAD + top + "jobs:\n  qc:\n    runs-on: ubuntu-latest\n" + job_extra +
            "    steps:\n      - uses: actions/checkout@v4\n" + steps + "      - run: " + cmd + "\n")


def pair(tmp_path, b, files=None, a=SITE_A, tracked=False, config=CONFIG):
    """Audit workflow A (names pkgdown, read-only) beside workflow B. `tracked` commits a file under the destination docs/."""
    web = tmp_path / "web"
    extra = {"docs/index.html": "<html></html>"} if tracked else {}
    with server(web) as root:
        pkg = make(tmp_path, config=config, files={SCRIPT_WORKFLOW: a, QC_WORKFLOW: b, "scripts/site.R": DYNAMIC_SITE_R, **extra, **(files or {})})
        publish(web, "", root, ROUTES)
        return site.audit(pkg, url=root, ref="main")


TIER1 = [
    pytest.param(workflow_b(top="permissions:\n  pages: write\n"), id="workflow-pages-write"),
    pytest.param(workflow_b(top="permissions:\n  id-token: write\n"), id="workflow-id-token-write"),
    pytest.param(workflow_b(top="permissions: write-all\n"), id="write-all"),
    pytest.param(workflow_b(top="permissions: read-all\n", job_extra="    permissions:\n      pages: write\n"), id="job-level-pages-write"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: JamesIves/github-pages-deploy-action@v4\n        with:\n          folder: docs\n"), id="deploy-action-in-a-later-step"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: peaceiris/actions-gh-pages@v4\n"), id="peaceiris"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: actions/deploy-pages@v4\n"), id="deploy-pages"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: actions/upload-pages-artifact@v3\n"), id="upload-pages-artifact"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: actions/configure-pages@v5\n"), id="configure-pages"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: \"JamesIves/github-pages-deploy-action@v4\"\n"), id="quoted-uses"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="Rscript -e 'pkgdown::deploy_to_branch()'\n      - run: Rscript scripts/site.R"), id="deploy-to-branch-text"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="git worktree add gh-pages\n      - run: Rscript scripts/site.R"), id="gh-pages-text"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: actions/checkout@v4\n        with:\n          token: ${{ secrets.PAT }}\n"), id="checkout-with-a-pat"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: actions/checkout@v4\n        with:\n          ssh-key: ${{ secrets.DEPLOY_KEY }}\n"), id="checkout-with-a-deploy-key"),
    pytest.param(workflow_b(top="permissions: read-all\n", job_extra="    env:\n      NOTE: pkgdown\n"), id="names-pkgdown"),
    # round 10: a remote publish target is tier one (these three were tier two in round 9)
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="rsync -a docs/ host:/var/www/\n      - run: Rscript scripts/site.R"), id="rsync-to-a-remote"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="aws s3 sync docs s3://bucket\n      - run: Rscript scripts/site.R"), id="aws-s3-sync"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="netlify deploy --dir docs\n      - run: Rscript scripts/site.R"), id="netlify-deploy"),
]
TIER2 = [
    pytest.param(workflow_b(top="permissions:\n  contents: write\n"), id="workflow-contents-write"),
    pytest.param(workflow_b(top="permissions: read-all\n", job_extra="    permissions:\n      contents: write\n"), id="job-level-contents-write-only"),
    pytest.param(workflow_b(), id="missing-permissions-key"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="git push origin HEAD:main\n      - run: Rscript scripts/site.R"), id="git-push-in-a-run-body"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="rsync -a out/ copy/\n      - run: Rscript scripts/site.R"), id="rsync-to-a-local-directory"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="aws s3 ls\n      - run: Rscript scripts/site.R"), id="aws-s3-without-a-target"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="netlify status\n      - run: Rscript scripts/site.R"), id="netlify-without-deploy"),
]


@pytest.mark.parametrize("tracked", [False, True], ids=["destination-untracked", "destination-tracked"])
@pytest.mark.parametrize("b", TIER1)
def test_a_tier_one_publish_signal_is_capable_whatever_the_destination(tmp_path, b, tracked):
    r = pair(tmp_path, b, tracked=tracked)
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("b", TIER2)
def test_a_tier_two_signal_with_a_tracked_destination_is_capable_and_the_reason_names_it(tmp_path, b):
    r = pair(tmp_path, b, tracked=True, a=NO_BUILD)     # no build workflow beside it: the cross-workflow rule would make a push action tier 1
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 2" in x and "destination docs/ is tracked" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("b", TIER2)
def test_a_tier_two_signal_with_an_untracked_destination_stays_relaxed(tmp_path, b):
    """The destination is not committed, so pushing to the default branch cannot publish site files (medfit deploys via gh-pages)."""
    r = pair(tmp_path, b, tracked=False, a=NO_BUILD)
    assert r["state"] == "complete", r["reasons"]


def test_the_medfit_qc_shaped_workflow_stays_complete_while_docs_is_untracked(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n  issues: write\n", cmd="Rscript scripts/site.R\n      - run: |\n          git add reports\n          git commit -m report\n          git push")
    clean = {"scripts/site.R": CLEAN_R}   # a dynamic script is an unresolved reference: named stage + default-branch push + unresolved is tier one (round 13)
    assert pair(tmp_path, qc, tracked=False, files=clean)["state"] == "complete"
    r = pair(tmp_path / "t", qc, tracked=True) if (tmp_path / "t").mkdir() is None else None
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]
    assert strict_tier_one(pair(fresh(tmp_path, "u"), qc, tracked=False))[0]


def test_a_missing_permissions_key_is_a_tier_two_signal_decided_both_ways(tmp_path):
    b = workflow_b()
    assert pair(tmp_path, b, tracked=False)["state"] == "complete"
    (tmp_path / "t").mkdir()
    r = pair(tmp_path / "t", b, tracked=True)
    assert reached(r, "may publish: tier 2", "no permissions: key"), r["reasons"]


def test_a_destination_tracked_only_in_the_working_tree_is_not_counted(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: workflow_b(top="permissions:\n  contents: write\n"), "scripts/site.R": DYNAMIC_SITE_R})
        (pkg / "docs").mkdir()
        (pkg / "docs/index.html").write_text("x")          # untracked: not at the pinned SHA
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "complete"


def test_a_destination_committed_after_the_pinned_ref_is_not_counted(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: workflow_b(top="permissions:\n  contents: write\n"), "scripts/site.R": DYNAMIC_SITE_R})
        git(pkg, "branch", "pinned")
        commit(pkg, {"docs/index.html": "x"}, message="track docs after the pin")
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="pinned")["state"] == "complete"


@pytest.mark.parametrize("config,files,expected", [
    ("destination: site\n", {"site/index.html": "x"}, "incomplete"),
    ("destination: site\n", {"docs/index.html": "x"}, "complete"),          # the default dir is tracked, but it is not the destination
    ("destination: docs\n", {"docs/index.html": "x"}, "incomplete"),
    ("destination: ./site/\n", {"site/a/b.html": "x"}, "incomplete"),
    ("destination: $OUT\n", {}, "incomplete"),                               # dynamic: fail closed
    ("destination: [a, b]\n", {}, "incomplete"),                             # not a string: fail closed
    ("destination: ../out\n", {}, "incomplete"),                             # outside the package: fail closed
    ("destination: /abs\n", {}, "incomplete"),
    ("destination: .\n", {}, "incomplete"),                                  # the package root itself is tracked
    ("destination: ''\n", {}, "incomplete"),
], ids=["custom-tracked", "custom-untracked-default-tracked", "docs-tracked", "dot-slash", "dynamic", "list", "dotdot", "absolute", "dot", "empty"])
def test_the_destination_comes_from_the_config_and_fails_closed_when_it_cannot_be_resolved(tmp_path, config, files, expected):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    assert pair(tmp_path, qc, files=files, config=CONFIG + config)["state"] == expected


def test_an_unparseable_config_makes_the_destination_tracked(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    r = pair(tmp_path, qc, config=CONFIG + "x: [unclosed\n")
    assert r["state"] == "incomplete"


def test_a_package_in_a_monorepo_uses_its_own_destination_directory(tmp_path):
    def run(files, base):
        web = tmp_path / base
        repo = tmp_path / (base + "-repo"); pkg = repo / "packages" / "ours"
        pkg.mkdir(parents=True)
        commit(repo, {"packages/ours/DESCRIPTION": DESC.format(version="1.0.0"), "packages/ours/man/internal.Rd": "x", "packages/ours/_pkgdown.yml": CONFIG,
                      ".github/workflows/qc.yaml": workflow_b(top="permissions:\n  contents: write\n", cmd="Rscript packages/ours/s.R"),
                      "packages/ours/s.R": DYNAMIC_SITE_R, **files}, init=True)
        with server(web) as root:
            publish(web, "", root, ROUTES)
            return site.audit(pkg, url=root, ref="main")["state"]
    assert run({"docs/index.html": "x", "packages/other/docs/index.html": "x"}, "a") == "complete"   # tracked elsewhere, not for this package
    assert run({"packages/ours/docs/index.html": "x"}, "b") == "incomplete"


def test_the_two_workflow_codex_fixture_with_a_tier_one_signal_is_incomplete(tmp_path):
    b = workflow_b(top="permissions: read-all\n", steps="      - uses: JamesIves/github-pages-deploy-action@v4\n        with:\n          folder: docs\n")
    assert "pkgdown" not in b.lower()
    r = pair(tmp_path, b)
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]


READ_ONLY = [
    pytest.param(workflow_b(top="permissions: read-all\n"), id="read-all"),
    pytest.param(workflow_b(top="permissions:\n  contents: read\n  issues: write\n"), id="contents-read-issues-write"),
    pytest.param(workflow_b(top="permissions: {}\n"), id="empty-permissions"),
    pytest.param(workflow_b(top="permissions:\n  contents: read\n", job_extra="    permissions:\n      contents: read\n      pull-requests: write\n"), id="job-level-read-only"),
    pytest.param(workflow_b(job_extra="    permissions: read-all\n"), id="job-only-read-all"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: r-lib/actions/setup-r@v2\n      - uses: actions/upload-artifact@v4\n"), id="setup-and-artifact-actions"),
    pytest.param(workflow_b(top="permissions: read-all\n", steps="      - uses: actions/checkout@v4\n        with:\n          token: ${{ secrets.GITHUB_TOKEN }}\n"), id="checkout-with-the-default-token"),
    pytest.param(workflow_b(top="permissions: read-all\n", cmd="git status\n      - run: Rscript scripts/site.R"), id="git-without-push"),
]


@pytest.mark.parametrize("b", READ_ONLY)
def test_a_workflow_that_shows_no_ability_to_publish_stays_relaxed(tmp_path, b):
    """Modeled on medfit's QC and gate workflows: read-only token, no deploy action, a script full of source(file.path(...))."""
    r = pair(tmp_path, b)
    assert r["state"] == "complete", r["reasons"]


def test_a_tier_one_signal_inside_a_reached_script_makes_the_workflow_strict(tmp_path):
    script = "system('git worktree add gh-pages')\n" + DYNAMIC_SITE_R
    r = pair(tmp_path, workflow_b(top="permissions: read-all\n"), files={"scripts/site.R": script})
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x and "scripts/site.R" in x for x in r["reasons"]), r["reasons"]


def test_a_tier_two_signal_inside_a_reached_script_needs_a_tracked_destination(tmp_path):
    script = "system('git push origin HEAD:main')\n" + DYNAMIC_SITE_R
    assert pair(tmp_path, workflow_b(top="permissions: read-all\n"), files={"scripts/site.R": script}, tracked=False)["state"] == "complete"
    (tmp_path / "t").mkdir()
    r = pair(tmp_path / "t", workflow_b(top="permissions: read-all\n"), files={"scripts/site.R": script}, tracked=True)
    assert reached(r, "script reference unsupported", "dynamic") and any("tier 2" in x and "scripts/site.R" in x for x in r["reasons"]), r["reasons"]


def test_a_deploy_step_inside_a_local_composite_action_makes_the_calling_workflow_strict(tmp_path):
    action = "runs:\n  using: composite\n  steps:\n    - uses: JamesIves/github-pages-deploy-action@v4\n      with:\n        folder: docs\n"
    b = workflow_b(top="permissions: read-all\n", steps="      - uses: ./.github/actions/ship\n")
    r = pair(tmp_path, b, files={".github/actions/ship/action.yml": action})
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]


def test_a_read_only_workflow_that_calls_a_clean_local_action_stays_relaxed(tmp_path):
    action = "runs:\n  using: composite\n  steps:\n    - run: echo hi\n      shell: bash\n"
    b = workflow_b(top="permissions: read-all\n", steps="      - uses: ./.github/actions/note\n")
    assert pair(tmp_path, b, files={".github/actions/note/action.yml": action})["state"] == "complete"


def test_a_publish_capable_workflow_with_a_clean_readable_script_never_blocks(tmp_path):
    r = pair(tmp_path, workflow_b(top="permissions:\n  contents: write\n"), files={"scripts/site.R": CLEAN_R})
    assert r["state"] == "complete", r["reasons"]


def test_the_publish_reason_names_the_evidence_and_is_allow_listed():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import verify_a2_release as verifier
    reason = ("script reference unsupported (dynamic path): source() with a non-literal argument; "
              "the deployed routes cannot be verified (workflow .github/workflows/qc.yaml may publish: tier 2: permissions contents: write (workflow); "
              "destination docs/ is tracked)")
    assert verifier.limit_run_is_unsupported_layout({"state": "incomplete", "deploy_layout": "unverified", "reasons": [reason]})


def test_the_predicate_returns_tier_labeled_evidence(tmp_path):
    data = site.yaml_data(workflow_b(top="permissions:\n  contents: write\n", steps="      - uses: actions/deploy-pages@v4\n"))
    evidence = site.workflow_may_publish(data, "", tracked=True, destination="destination docs/")
    assert any(e.startswith("tier 1:") and "deploy-pages" in e for e in evidence)
    assert any(e.startswith("tier 2:") and "contents" in e and "destination docs/ is tracked" in e for e in evidence)
    untracked = site.workflow_may_publish(data, "", tracked=False, destination="destination docs/")
    assert untracked and all(e.startswith("tier 1:") for e in untracked)           # tier two is dropped, tier one stays
    only_two = site.yaml_data(workflow_b(top="permissions:\n  contents: write\n"))
    assert site.workflow_may_publish(only_two, "", tracked=False) == []
    assert site.workflow_may_publish(site.yaml_data(workflow_b(top="permissions: read-all\n")), "") == []


# ---------------------------------------------------------------------------------------------------------
# Codex round 10. Tier one now also covers explicit-branch pushes and remote publish targets; the destination check
# also sees a destination named in a build call; a reusable workflow shares capability with its caller; a directory
# holding only placeholders is not a tracked destination.
# ---------------------------------------------------------------------------------------------------------
def fresh(tmp_path, name):
    folder = tmp_path / str(name)
    folder.mkdir()
    return folder


def tiers(text):
    return {tier for tier, _ in site.text_publish_evidence(text, "x")}


PUSH_TIER_ONE = [
    "git push origin HEAD:site", "git push origin site", "git push -u origin site", "git push --set-upstream origin site",
    "git push --force origin HEAD:site", "git push -f origin site", "git push --force-with-lease origin HEAD:site",
    "git push --force-with-lease=site origin HEAD:site", "git push origin HEAD:refs/heads/site", "git push origin +HEAD:site",
    "git push origin HEAD:gh-pages", 'git push origin "HEAD:site"', "git push origin 'site'", "git push origin HEAD:$BRANCH",
    "git push origin HEAD:${{ inputs.branch }}", "git push origin HEAD:$(cat branch.txt)", "git push origin `cat branch.txt`",
    "git push $REMOTE", "git push origin \\\n  HEAD:site", "git push --all origin", "git push --mirror origin",
    "git -C out push origin site", "git push origin main site", "git push https://example.org/r.git HEAD:site",
    "git push origin HEAD:refs/heads/docs-site", "git push -o ci.skip origin site", "git push origin HEAD:main && git push origin HEAD:site",
]
PUSH_TIER_TWO = [
    "git push", "git push origin", "git push origin HEAD", "git push origin main", "git push origin master", "git push origin HEAD:main",
    "git push origin HEAD:refs/heads/main", "git push -u origin main", "git push --force-with-lease origin main", "git push --tags",
    "git push origin refs/tags/v1", "git push --follow-tags origin main", "git push origin HEAD:master", "git push -u origin HEAD",
    "git push origin \\\n  main", "git push && echo done",
]


@pytest.mark.parametrize("command", PUSH_TIER_ONE)
def test_an_explicit_branch_push_is_tier_one(command):
    assert 1 in tiers(command), site.text_publish_evidence(command, "x")


@pytest.mark.parametrize("command", PUSH_TIER_TWO)
def test_a_push_to_the_default_branch_or_with_no_refspec_is_tier_two(command):
    found = site.text_publish_evidence(command, "x")
    assert tiers(command) == {2}, found


def test_other_text_that_mentions_push_is_no_evidence():
    for text in ("git pull --rebase", "echo 'do not git push here'", "git status", "pre-push hook", "# git push origin site\ngit status\n"):
        assert 2 not in tiers(text) or "echo" in text or text.startswith("#"), text
    assert tiers("git commit -m 'git push'") <= {2}


TARGET_TIER_ONE = [
    "rsync -av docs/ user@host:/var/www/", "rsync -av out/ host:/site", "rsync -a docs rsync://h/module/", "scp -r docs host:/var/www",
    "aws s3 sync docs s3://bucket", "aws s3 cp x s3://b/x", "gsutil rsync -r docs gs://b", "netlify deploy --dir docs", "npx netlify deploy --prod",
    "firebase deploy --only hosting", "surge docs example.surge.sh", "npx surge ./docs", "vercel --prod", "vercel deploy docs",
    "wrangler pages deploy docs", "ghp-import -n -p docs", "rsync -av docs/ $DEST", "aws s3 sync docs $BUCKET",
]
TARGET_TIER_TWO = ["rsync -av out/ docs/", "scp a b", "aws s3 ls", "netlify status", "rsync --version"]


@pytest.mark.parametrize("command", TARGET_TIER_ONE)
def test_a_command_that_names_a_remote_publish_target_is_tier_one(command):
    assert 1 in tiers(command), site.text_publish_evidence(command, "x")


@pytest.mark.parametrize("command", TARGET_TIER_TWO)
def test_a_publish_style_command_without_a_remote_target_is_tier_two(command):
    assert tiers(command) == {2}, site.text_publish_evidence(command, "x")


def test_r_system2_git_push_is_fail_closed_tier_one():
    assert 1 in tiers('system2("git", c("push", "origin", "HEAD:site"))')


PUSH_FORMS = [
    pytest.param("      - run: git push origin HEAD:site\n", id="run-line"),
    pytest.param('      - run: "git push origin HEAD:site"\n', id="quoted-run"),
    pytest.param("      - run: |\n          git add -A\n          git push \\\n            origin HEAD:site\n", id="block-with-continuation"),
    pytest.param("      - run: bash -c \"git push origin HEAD:site\"\n", id="bash-c"),
    pytest.param("      - env:\n          BRANCH: site\n        run: git push origin HEAD:$BRANCH\n", id="env-variable"),
    pytest.param("      - run: git push origin HEAD:${{ inputs.branch }}\n", id="expression"),
    pytest.param("      - run: git push origin HEAD:$(cat branch.txt)\n", id="command-substitution"),
]


@pytest.mark.parametrize("step", PUSH_FORMS)
@pytest.mark.parametrize("tracked", [False, True], ids=["destination-untracked", "destination-tracked"])
def test_an_explicit_branch_push_in_a_workflow_makes_it_strict_whatever_the_destination(tmp_path, step, tracked):
    b = WORKFLOW_HEAD + "permissions:\n  contents: write\njobs:\n  qc:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n" + step + "      - run: Rscript scripts/site.R\n"
    r = pair(tmp_path, b, tracked=tracked)
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x for x in r["reasons"]), r["reasons"]


def test_the_codex_fixture_a_push_to_a_site_branch_with_an_untracked_docs_and_a_dynamic_source_is_incomplete(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n", cmd="git push origin HEAD:site\n      - run: Rscript scripts/site.R")
    r = pair(tmp_path, qc, tracked=False)
    assert reached(r, "script reference unsupported", "dynamic") and any("tier 1" in x and "git push origin HEAD:site" in x for x in r["reasons"]), r["reasons"]


def test_the_same_fixture_with_a_plain_git_push_and_an_untracked_docs_stays_complete(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n", cmd="git push\n      - run: Rscript scripts/site.R")
    assert pair(tmp_path, qc, tracked=False)["state"] == "complete"


def test_an_explicit_branch_push_inside_a_reached_script_is_tier_one(tmp_path):
    script = "system('git push origin HEAD:site')\n" + DYNAMIC_SITE_R
    r = pair(tmp_path, workflow_b(top="permissions: read-all\n"), files={"scripts/site.R": script})
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x and "scripts/site.R" in x for x in r["reasons"]), r["reasons"]


def test_a_push_inside_a_local_composite_action_is_classified_like_one_in_a_workflow(tmp_path):
    action = "runs:\n  using: composite\n  steps:\n    - run: git push origin HEAD:site\n      shell: bash\n"
    b = workflow_b(top="permissions: read-all\n", steps="      - uses: ./.github/actions/ship\n")
    r = pair(tmp_path, b, files={".github/actions/ship/action.yml": action})
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x for x in r["reasons"]), r["reasons"]


# --- a destination named in a build call is an additional destination for the tracked check ---------------
BUILD_CALLS = [
    pytest.param("pkgdown::build_site(override = list(destination = \"public\"))\n", id="override-double-quoted"),
    pytest.param("pkgdown::build_site(override = list(destination = 'public'))\n", id="override-single-quoted"),
    pytest.param("pkgdown::build_site_github_pages(dest_dir = \"public\")\n", id="github-pages-dest-dir"),
    pytest.param("pkgdown::build_reference(override = list(destination = \"./public/\"))\n", id="build-reference-dot-slash"),
    pytest.param("system(\"Rscript -e 'pkgdown::build_site()' --destination public\")\n", id="cli-flag"),
    pytest.param("cat('destination: public\\n', file = '_pkgdown.yml', append = TRUE)\npkgdown::build_site()\n", id="config-written-by-the-script"),
]


@pytest.mark.parametrize("call", BUILD_CALLS)
def test_a_build_destination_that_is_tracked_makes_a_tier_two_workflow_capable(tmp_path, call):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    script = call + DYNAMIC_SITE_R
    r = pair(tmp_path, qc, files={"scripts/site.R": script, "public/index.html": "<html></html>"})
    assert reached(r, "script reference unsupported", "dynamic") and any("tier 2" in x and "destination public/ is tracked" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("call", BUILD_CALLS)
def test_a_build_destination_that_is_not_tracked_leaves_the_workflow_relaxed(tmp_path, call):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    assert pair(tmp_path, qc, files={"scripts/site.R": call + DYNAMIC_SITE_R})["state"] == "complete"


def test_a_build_destination_equal_to_the_config_destination_adds_nothing(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    script = "pkgdown::build_site(override = list(destination = \"docs\"))\n" + DYNAMIC_SITE_R
    assert pair(tmp_path, qc, files={"scripts/site.R": script})["state"] == "complete"


@pytest.mark.parametrize("argument", ["out_dir", "file.path(root, 'site')", "Sys.getenv('OUT')", "\"$OUT\""])
def test_a_build_destination_that_is_not_a_literal_fails_closed(tmp_path, argument):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    script = f"pkgdown::build_site(override = list(destination = {argument}))\n" + DYNAMIC_SITE_R
    r = pair(tmp_path, qc, files={"scripts/site.R": script})
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]


def test_a_destination_argument_in_text_that_has_nothing_to_do_with_pkgdown_is_ignored(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n")
    script = "file.copy(from = 'a', destination = 'public')\n" + DYNAMIC_SITE_R
    assert pair(tmp_path, qc, files={"scripts/site.R": script, "public/index.html": "x"})["state"] == "complete"


# --- reusable workflows share capability with their caller ---------------------------------------------------
CALLEE = ".github/workflows/build.yml"
CALLEE_BODY = "on: workflow_call\npermissions: read-all\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript scripts/site.R\n"


def caller(job_uses="./.github/workflows/build.yml", top="", extra_job=""):
    return (WORKFLOW_HEAD + top + "jobs:\n  call:\n" + extra_job + f"    uses: {job_uses}\n" +
            "  qc:\n    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript scripts/site.R\n")


def test_a_callee_with_no_signal_inherits_the_callers_job_permissions(tmp_path):
    b = caller(top="permissions: read-all\n", extra_job="    permissions:\n      pages: write\n")
    r = pair(tmp_path, b, files={CALLEE: CALLEE_BODY})
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x for x in r["reasons"]), r["reasons"]
    assert any("reusable workflow job unsupported" in x for x in r["reasons"])


def test_a_caller_with_no_signal_inherits_the_callees_capability(tmp_path):
    callee = "on: workflow_call\npermissions:\n  pages: write\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo harmless\n"
    b = caller(top="permissions: read-all\n")
    r = pair(tmp_path, b, files={CALLEE: callee})
    # only the caller's sibling job runs the dynamic script; the callee's capability makes the whole caller strict
    assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x and ".github/workflows/qc.yaml" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("uses,why", [
    ("./.github/workflows/gone.yml", "missing"),
    ("octo/repo/.github/workflows/build.yml@v1", "other repository"),
    ("./.github/workflows/${{ inputs.which }}.yml", "dynamic"),
    ("./.github/workflows/../../outside.yml", "outside"),
])
def test_an_unresolvable_callee_counts_as_capable(tmp_path, uses, why):
    r = pair(tmp_path, caller(job_uses=uses, top="permissions: read-all\n"))
    assert any("may publish: tier 1" in x and "reusable workflow" in x and ".github/workflows/qc.yaml" in x for x in r["reasons"]), (why, r["reasons"])


def test_a_workflow_call_cycle_terminates_and_is_incomplete(tmp_path):
    a = ".github/workflows/a.yml"
    b_ = ".github/workflows/b.yml"
    files = {a: "on: workflow_call\npermissions: read-all\njobs:\n  x:\n    uses: ./.github/workflows/b.yml\n",
             b_: "on: workflow_call\npermissions:\n  pages: write\njobs:\n  y:\n    uses: ./.github/workflows/a.yml\n"}
    r = pair(tmp_path, workflow_b(top="permissions: read-all\n"), files=files)
    assert r["state"] == "incomplete"


def test_a_clean_callee_called_from_a_read_only_caller_adds_no_capability_of_its_own(tmp_path):
    b = caller(top="permissions: read-all\n")
    r = pair(tmp_path, b, files={CALLEE: CALLEE_BODY})
    assert not any("may publish" in x for x in r["reasons"]), r["reasons"]
    assert any("reusable workflow job unsupported" in x for x in r["reasons"])


# --- a placeholder-only directory is not a tracked destination -------------------------------------------------
def qc_with_tier_two():
    return workflow_b(top="permissions:\n  contents: write\n")


@pytest.mark.parametrize("files,expected", [
    ({"docs/.gitkeep": ""}, "complete"),
    ({"docs/.keep": ""}, "complete"),
    ({"docs/.gitignore": "*\n"}, "complete"),
    ({"docs/.gitattributes": "* -diff\n"}, "complete"),
    ({"docs/.gitkeep": "", "docs/.gitignore": "*\n"}, "complete"),
    ({"docs/sub/.gitkeep": ""}, "complete"),
    ({"docs/a/b/.gitkeep": "", "docs/c/.gitignore": "x"}, "complete"),
    ({"docs/.gitkeep": "", "docs/index.html": "x"}, "incomplete"),
    ({"docs/.nojekyll": ""}, "incomplete"),
    ({"docs/.gitkeep": "", "docs/sub/page.html": "x"}, "incomplete"),
    ({"docs/.GitKeep": ""}, "incomplete"),              # git paths are case-sensitive: .GitKeep is not the placeholder name
    ({"Docs/index.html": "x"}, "complete"),             # and Docs/ is not docs/
    ({"docs": "a file named docs"}, "incomplete"),      # the destination path itself is a tracked entry
    ({"docs/CNAME": "example.org"}, "incomplete"),
], ids=["gitkeep", "keep", "gitignore", "gitattributes", "two-placeholders", "nested-placeholder", "nested-placeholders", "gitkeep-plus-page",
        "nojekyll", "gitkeep-plus-nested-page", "case-sensitive-gitkeep", "case-sensitive-directory", "destination-is-a-file", "cname"])
def test_placeholder_only_entries_do_not_make_the_destination_tracked(tmp_path, files, expected):
    r = pair(tmp_path, qc_with_tier_two(), files=files)
    assert r["state"] == expected, r["reasons"]


def test_a_submodule_at_the_destination_counts_as_tracked(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: qc_with_tier_two(), "scripts/site.R": DYNAMIC_SITE_R})
        git(pkg, "update-index", "--add", "--cacheinfo", "160000," + "a" * 40 + ",docs")
        git(pkg, "commit", "-m", "submodule at docs")
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert reached(r, "script reference unsupported", "dynamic") and any("destination docs/ is tracked" in x for x in r["reasons"]), r["reasons"]


def test_a_gitlink_inside_the_destination_counts_as_tracked(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: qc_with_tier_two(), "scripts/site.R": DYNAMIC_SITE_R, "docs/.gitkeep": ""})
        git(pkg, "update-index", "--add", "--cacheinfo", "160000," + "b" * 40 + ",docs/vendor")
        git(pkg, "commit", "-m", "gitlink below docs")
        publish(web, "", root, ROUTES)
        assert reached(site.audit(pkg, url=root, ref="main"), "script reference unsupported", "dynamic")


@pytest.mark.parametrize("config", ["destination: ../x\n", "destination: /abs\n", "destination: $OUT\n"], ids=["dotdot", "absolute", "dynamic"])
def test_a_destination_outside_the_package_or_dynamic_stays_tracked_even_with_only_placeholders(tmp_path, config):
    r = pair(tmp_path, qc_with_tier_two(), files={"docs/.gitkeep": ""}, config=CONFIG + config)
    assert reached(r, "script reference unsupported", "dynamic"), r["reasons"]


def test_the_medfit_qc_shape_with_a_gitkeep_only_docs_stays_complete(tmp_path):
    qc = workflow_b(top="permissions:\n  contents: write\n  issues: write\n", cmd="Rscript scripts/site.R\n      - run: |\n          git add reports\n          git commit -m report\n          git push")
    assert pair(tmp_path, qc, files={"docs/.gitkeep": "", "scripts/site.R": CLEAN_R})["state"] == "complete"


# --- the opt-out key: `docs.site.nonpublishing-branches` in the pinned `.rforge.yaml` -------------------------------
# medfit's qc-monthly workflow pushes a CSV history to `qc-results`. The classifier cannot tell that from a site branch,
# so a repository declares it. A declared branch is tier two (counts only when the destination is tracked), never tier one.
KEY = "docs:\n  site:\n    nonpublishing-branches:\n      - qc-results\n"


def qc_push(branch_spec="origin qc-results"):
    return workflow_b(top="permissions:\n  contents: write\n", cmd=f"git push {branch_spec}\n      - run: Rscript scripts/site.R")


def test_a_push_to_an_undeclared_explicit_branch_is_tier_one_without_the_key(tmp_path):
    r = pair(tmp_path, qc_push())
    assert reached(r, "script reference unsupported", "dynamic") and any("tier 1" in x for x in r["reasons"]), r["reasons"]


@pytest.mark.parametrize("spec", ["origin qc-results", "origin HEAD:qc-results", "origin HEAD:refs/heads/qc-results", "-u origin qc-results",
                                  "--force-with-lease origin +HEAD:qc-results", "origin 'qc-results'", "origin \"HEAD:qc-results\""])
def test_a_declared_branch_is_tier_two_so_an_untracked_destination_leaves_the_workflow_relaxed(tmp_path, spec):
    assert pair(tmp_path, qc_push(spec), files={".rforge.yaml": KEY})["state"] == "complete"


def test_a_declared_branch_still_counts_when_the_destination_is_tracked(tmp_path):
    r = pair(tmp_path, qc_push(), files={".rforge.yaml": KEY}, tracked=True)
    assert reached(r, "script reference unsupported", "dynamic") and any("tier 2" in x and "destination docs/ is tracked" in x for x in r["reasons"]), r["reasons"]


def test_the_key_exempts_only_the_branches_it_names(tmp_path):
    for n, spec in enumerate(["origin site", "origin HEAD:gh-pages", "origin qc-results site", "origin HEAD:qc-results-2", "origin HEAD:$BRANCH", "--all origin"]):
        r = pair(fresh(tmp_path, n), qc_push(spec), files={".rforge.yaml": KEY})
        assert reached(r, "script reference unsupported", "dynamic") and any("tier 1" in x for x in r["reasons"]), (spec, r["reasons"])


def test_a_listed_gh_pages_is_still_tier_one_through_the_deploy_text_signal(tmp_path):
    key = "docs:\n  site:\n    nonpublishing-branches: [gh-pages]\n"
    r = pair(tmp_path, qc_push("origin gh-pages"), files={".rforge.yaml": key})
    assert reached(r, "script reference unsupported", "dynamic")


@pytest.mark.parametrize("key", [
    "docs:\n  site:\n    nonpublishing-branches: qc-results\n",                  # a string, not a list
    "docs:\n  site:\n    nonpublishing-branches: [\"*\"]\n",                       # a glob
    "docs:\n  site:\n    nonpublishing-branches: ['$BRANCH']\n",                  # not a literal
    "docs:\n  site:\n    nonpublishing-branches: [{a: b}]\n",                      # not a string
    "docs:\n  site:\n    nonpublishing-branches: [1]\n",
    "docs:\n  site: [qc-results]\n",
    "docs: [site]\n",
    "docs:\n  site:\n    nonpublishing-branches: [unclosed\n",                    # unparseable
    "docs:\n  site:\n    nonpublishing_branches: [qc-results]\n",                  # a different spelling is a different key
], ids=["string", "glob", "variable", "mapping", "number", "site-list", "docs-list", "unparseable", "underscore"])
def test_a_malformed_key_exempts_nothing(tmp_path, key):
    r = pair(tmp_path, qc_push(), files={".rforge.yaml": key})
    assert reached(r, "script reference unsupported", "dynamic") and any("tier 1" in x for x in r["reasons"]), r["reasons"]


def test_a_malformed_entry_does_not_spoil_the_valid_ones(tmp_path):
    key = "docs:\n  site:\n    nonpublishing-branches: ['*', qc-results, 3]\n"
    assert pair(tmp_path, qc_push(), files={".rforge.yaml": key})["state"] == "complete"


def test_the_key_is_read_at_the_pinned_ref_not_the_working_tree(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: qc_push(), "scripts/site.R": DYNAMIC_SITE_R})
        (pkg / ".rforge.yaml").write_text(KEY)                    # uncommitted
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="main")["state"] == "incomplete"


def test_a_key_committed_after_the_pinned_ref_is_not_honored(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: qc_push(), "scripts/site.R": DYNAMIC_SITE_R})
        git(pkg, "branch", "pinned")
        commit(pkg, {".rforge.yaml": KEY}, message="declare after the pin")
        publish(web, "", root, ROUTES)
        assert site.audit(pkg, url=root, ref="pinned")["state"] == "incomplete"


def test_a_monorepo_reads_the_package_key_and_the_repository_root_key(tmp_path):
    def run(base, files):
        repo = tmp_path / (base + "-repo"); pkg = repo / "packages" / "ours"
        pkg.mkdir(parents=True)
        commit(repo, {"packages/ours/DESCRIPTION": DESC.format(version="1.0.0"), "packages/ours/man/internal.Rd": "x", "packages/ours/_pkgdown.yml": CONFIG,
                      ".github/workflows/qc.yaml": workflow_b(top="permissions:\n  contents: write\n", cmd="git push origin qc-results\n      - run: Rscript packages/ours/s.R"),
                      "packages/ours/s.R": DYNAMIC_SITE_R, **files}, init=True)
        web = tmp_path / base
        with server(web) as root:
            publish(web, "", root, ROUTES)
            return site.audit(pkg, url=root, ref="main")["state"]
    assert run("none", {}) == "incomplete"
    assert run("pkgkey", {"packages/ours/.rforge.yaml": KEY}) == "complete"
    assert run("rootkey", {".rforge.yaml": KEY}) == "complete"
    assert run("other", {"packages/other/.rforge.yaml": KEY}) == "incomplete"


def test_the_exemption_applies_to_a_push_inside_a_reached_script_and_a_local_action(tmp_path):
    script = "system('git push origin qc-results')\n" + DYNAMIC_SITE_R
    assert pair(tmp_path, workflow_b(top="permissions:\n  contents: write\n"), files={"scripts/site.R": script, ".rforge.yaml": KEY})["state"] == "complete"
    action = "runs:\n  using: composite\n  steps:\n    - run: git push origin qc-results\n      shell: bash\n"
    b = workflow_b(top="permissions:\n  contents: write\n", steps="      - uses: ./.github/actions/ship\n")
    assert pair(fresh(tmp_path, "a"), b, files={".github/actions/ship/action.yml": action, ".rforge.yaml": KEY})["state"] == "complete"
    r = pair(fresh(tmp_path, "b"), b, files={".github/actions/ship/action.yml": action})
    assert reached(r, "script reference unsupported", "dynamic")


def test_the_exempt_parameter_changes_only_the_classification_of_the_named_branch():
    assert {t for t, _ in site.text_publish_evidence("git push origin qc-results", "x")} == {1}
    assert {t for t, _ in site.text_publish_evidence("git push origin qc-results", "x", exempt=("qc-results",))} == {2}
    assert {t for t, _ in site.text_publish_evidence("git push origin site", "x", exempt=("qc-results",))} == {1}
    labels = [label for _, label in site.text_publish_evidence("git push origin qc-results", "x", exempt=("qc-results",))]
    assert any("declared non-publishing branch qc-results" in label for label in labels)


# ---------------------------------------------------------------------------------------------------------
# Codex round 11, finding 1. A workflow that builds or stages the destination before it pushes can publish site files
# whether or not the pinned tree tracks the destination yet, so that evidence is tier one regardless of tracking.
# ---------------------------------------------------------------------------------------------------------
def staged(text, names=("docs",), build=False):
    texts = [("the workflow", text)] + ([("scripts/build.R", "pkgdown::build_site()")] if build else [])
    return site.stage_evidence(texts, names)


STAGE_NAMES_DESTINATION = [
    "git add -f docs", "git add docs", "git add docs/", "git add docs/index.html", "git add -f ./docs", "git add -A docs",
    "git add --force docs/*", "git add pkg/docs", "git -C pkg add docs", "git commit -m x docs", "git commit -am x -- docs",
    "git subtree push --prefix docs origin main", "git subtree push --prefix=docs origin site", "git subtree push --prefix site origin main",
    "git worktree add docs gh-pages", "git worktree add -B site docs origin/main", "git worktree add ./docs main",
    "cp -r _site/. docs/", "cp -R _site docs", "mv _site docs", "rsync -a _site/ docs/", "rsync -a _site/ ./docs",
    "ln -s _site docs",
]
STAGE_AFTER_BUILD = ["git add .", "git add -A", "git add --all", "git add -u", "git commit -a -m x", "git commit -am x", "git add -A ."]
STAGE_NEGATIVE = [
    "git add data/history.csv", "git add qc-history.csv", "git add .", "git add -A", "git commit -m x", "git commit -am x",
    "git add docs-archive/a.md", "git add mydocs", "git add docsets/x", "git add notes/docs.txt", "git worktree add ../tmp main",
    "cp a.csv data/", "mv a.csv history/", "rsync -a a.csv data/", "git push origin main",
]


@pytest.mark.parametrize("command", STAGE_NAMES_DESTINATION)
def test_a_command_that_stages_the_destination_is_tier_one(command):
    found = staged(command)
    assert {t for t, _ in found} == {1}, (command, found)
    assert "stages the site destination" in found[0][1]


@pytest.mark.parametrize("command", STAGE_AFTER_BUILD)
def test_staging_everything_after_a_build_step_is_tier_one(command):
    assert {t for t, _ in staged(command, build=True)} == {1}, command
    # The same command in a text with no pkgdown build anywhere stages no site files.
    assert staged(command) == [], command


@pytest.mark.parametrize("command", STAGE_NEGATIVE)
def test_staging_something_else_is_not_stage_evidence(command):
    assert staged(command) == [], (command, staged(command))


def test_a_destination_named_in_a_build_call_is_a_stage_name():
    assert {t for t, _ in staged("git add public", names=("docs", "public"))} == {1}
    assert staged("git add public", names=("docs",)) == []
    assert staged("git add docs", names=()) == []


def test_generated_and_pushed_site_files_are_strict_even_when_the_tree_has_no_destination(tmp_path):
    # The Codex fixture: docs/ is absent from the pinned tree; the workflow builds it, force-adds, commits and pushes to main.
    push = workflow_b(top="permissions:\n  contents: write\n", cmd="git add -f docs\n      - run: git commit -m site\n      - run: git push origin main\n      - run: Rscript scripts/site.R")
    r = pair(tmp_path, push)
    assert reached(r, "script reference unsupported", "tier 1"), r["reasons"]
    assert any("stages" in x and "docs" in x for x in r["reasons"]), r["reasons"]


def test_add_everything_after_a_build_step_in_a_reached_script_is_strict(tmp_path):
    build = "pkgdown::build_site()\n"
    push = workflow_b(top="permissions:\n  contents: write\n",
                      cmd="Rscript scripts/build.R\n      - run: git add -A\n      - run: git commit -m site\n      - run: git push origin main\n      - run: Rscript scripts/site.R")
    r = pair(tmp_path, push, files={"scripts/build.R": build})
    assert reached(r, "script reference unsupported", "tier 1"), r["reasons"]
    # The same workflow with no build step and no build workflow anywhere stays relaxed while the destination is untracked.
    quiet = workflow_b(top="permissions:\n  contents: write\n",
                       cmd="git add data/history.csv\n      - run: git commit -m x\n      - run: git push origin main\n      - run: Rscript scripts/site.R")
    # (A resolved script: a dynamic one would be an unresolved reference, which makes a stage-and-push workflow tier one.)
    assert pair(fresh(tmp_path, "quiet"), quiet, a=NO_BUILD, files={"scripts/site.R": CLEAN_R})["state"] == "complete"
    assert site.handoff_evidence({"w": [[(0, "stage"), (0, "push")], []]}) == {}


def test_a_staging_command_inside_a_reached_script_or_a_local_action_is_strict(tmp_path):
    script = "system('git add -f docs')\n" + DYNAMIC_SITE_R
    b = workflow_b(top="permissions:\n  contents: write\n")
    assert reached(pair(tmp_path, b, files={"scripts/site.R": script}), "script reference unsupported", "tier 1")
    action = "runs:\n  using: composite\n  steps:\n    - run: git add -f docs\n      shell: bash\n"
    b = workflow_b(top="permissions:\n  contents: write\n", steps="      - uses: ./.github/actions/ship\n")
    r = pair(fresh(tmp_path, "act"), b, files={".github/actions/ship/action.yml": action})
    assert reached(r, "script reference unsupported", "tier 1")


def test_a_destination_named_by_the_config_or_a_build_call_is_the_stage_name(tmp_path):
    config = "destination: public\n"
    push = workflow_b(top="permissions:\n  contents: write\n", cmd="git add -f public\n      - run: git push origin main\n      - run: Rscript scripts/site.R")
    assert reached(pair(tmp_path, push, config=config), "script reference unsupported", "tier 1")
    # With the default destination, `git add public` stages something unrelated.
    assert pair(fresh(tmp_path, "d"), push, a=NO_BUILD, files={"scripts/site.R": CLEAN_R})["state"] == "complete"
    build = "pkgdown::build_site(destination = 'out')\n"
    out = workflow_b(top="permissions:\n  contents: write\n", cmd="Rscript scripts/build.R\n      - run: git add -f out\n      - run: git push origin main\n      - run: Rscript scripts/site.R")
    assert reached(pair(fresh(tmp_path, "e"), out, files={"scripts/build.R": build}), "script reference unsupported", "tier 1")


def test_a_csv_history_push_stays_tier_two_and_relaxed_when_the_destination_is_untracked(tmp_path):
    csv = workflow_b(top="permissions:\n  contents: write\n",
                     cmd="git add data/history.csv\n      - run: git commit -m history\n      - run: git push origin main\n      - run: Rscript scripts/site.R")
    clean = {"scripts/site.R": CLEAN_R}
    assert pair(tmp_path, csv, files=clean)["state"] == "complete"
    # With a tracked destination the evidence counts as before; with a dynamic script the named stage + push is tier one (round 13).
    assert pair(fresh(tmp_path, "c"), csv, tracked=True, files=clean)["state"] == "complete"
    assert reached(pair(fresh(tmp_path, "t"), csv, tracked=True), "script reference unsupported", "tier 1")


# ---------------------------------------------------------------------------------------------------------
# Codex round 11, finding 2 (rejected as a verification request, accepted as visibility): the key is an unverified
# maintainer declaration, so a reader must be able to see when it was applied.
# ---------------------------------------------------------------------------------------------------------
def rendered(stage):
    return docaudit.format_text({"findings": [], "messages": [], "stages": {"site": stage}})


def test_an_applied_declaration_is_reported_in_the_stage_and_the_text_report(tmp_path):
    r = pair(tmp_path, qc_push(), files={".rforge.yaml": KEY})
    assert r["state"] == "complete"
    assert r["nonpublishing_branches_honored"] == ["qc-results"]
    line = next(x for x in rendered(r).splitlines() if x.startswith("info"))
    assert "nonpublishing-branches" in line and "qc-results" in line and "unverified" in line


def test_the_field_is_an_empty_list_and_there_is_no_report_line_when_nothing_was_honored(tmp_path):
    for n, (workflow, files) in enumerate([
            (qc_push(), {}),                                                # push to a branch the repository did not declare
            (qc_push("origin main"), {".rforge.yaml": KEY}),                # declared, but nothing pushes to it
            (workflow_b(top="permissions: read-all\n"), {".rforge.yaml": KEY})]):
        r = pair(fresh(tmp_path, n), workflow, files=files)
        assert r["nonpublishing_branches_honored"] == [], (n, r)
        assert not any(x.startswith("info") for x in rendered(r).splitlines()), n


def test_only_the_branches_the_declaration_actually_exempted_are_listed(tmp_path):
    key = "docs:\n  site:\n    nonpublishing-branches:\n      - qc-results\n      - unused\n"
    r = pair(tmp_path, qc_push(), files={".rforge.yaml": key})
    assert r["nonpublishing_branches_honored"] == ["qc-results"]


def test_the_field_is_present_on_an_incomplete_stage(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: SITE_A, QC_WORKFLOW: qc_push(), "scripts/site.R": DYNAMIC_SITE_R, ".rforge.yaml": KEY})
        early = site.audit(pkg, url="ftp://example.invalid/", ref="main")          # refused before the workflows are read
        late = site.audit(pkg, url=root + "wrong/", ref="main")                    # workflows read, sitemap absent
    assert early["state"] == "incomplete" and early["nonpublishing_branches_honored"] == []
    assert late["state"] == "incomplete" and late["nonpublishing_branches_honored"] == ["qc-results"]


# ---------------------------------------------------------------------------------------------------------
# Codex round 12. Build output can reach the staging workflow from another workflow (an artifact, a downloaded
# release, a `workflow_run` trigger), so neither workflow alone shows both halves.
# ---------------------------------------------------------------------------------------------------------
NO_BUILD = step_workflow("echo hello", top="permissions: read-all\n")
STAGE_PUSH = "git add -f out\n      - run: git commit -m site\n      - run: git push origin main\n      - run: Rscript scripts/site.R"
DOWNLOAD_STEP = "      - uses: actions/download-artifact@v4\n        with:\n          name: site\n"


def handoff_b(cmd=STAGE_PUSH, steps="", head=WORKFLOW_HEAD, top="permissions:\n  contents: write\n"):
    return (head + top + "jobs:\n  publish:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
            + steps + "      - run: " + cmd + "\n")


def handoff(tmp_path, b, a=SITE_A, files=None, tracked=False):
    return pair(tmp_path, b, files=files, a=a, tracked=tracked)


def strict_tier_one(r):
    return reached(r, "script reference unsupported", "dynamic") and any("tier 1" in x for x in r["reasons"]), r["reasons"]


def test_an_artifact_handoff_to_a_staging_workflow_is_tier_one_even_when_the_destination_is_untracked(tmp_path):
    ok, why = strict_tier_one(handoff(tmp_path, handoff_b(steps=DOWNLOAD_STEP), a=NO_BUILD))   # the download alone, no build workflow
    assert ok, why
    ok, why = strict_tier_one(handoff(fresh(tmp_path, "a"), handoff_b(steps=DOWNLOAD_STEP)))
    assert ok, why


@pytest.mark.parametrize("fetch", ["gh run download 123 -n site", "gh release download v1 --pattern '*.zip'", "curl -sL https://example.org/site.tar.gz -o s.tgz",
                                   "wget https://example.org/site.zip", "curl -L -o site.tar.xz https://example.org/x"])
def test_other_ways_to_pull_build_output_make_a_staging_workflow_tier_one(tmp_path, fetch):
    b = handoff_b(cmd=fetch + "\n      - run: " + STAGE_PUSH)
    ok, why = strict_tier_one(handoff(tmp_path, b, a=NO_BUILD))
    assert ok, (fetch, why)


def test_a_workflow_run_trigger_is_a_pull_of_another_workflows_output(tmp_path):
    head = "on:\n  workflow_run:\n    workflows: [build]\n    types: [completed]\n"
    ok, why = strict_tier_one(handoff(tmp_path, handoff_b(head=head), a=NO_BUILD))
    assert ok, why


@pytest.mark.parametrize("flag_command", ["git add .", "git add -A", "git add --all", "git add -f docs", "git add -f out", "git commit -am x"])
def test_the_staging_half_covers_add_all_force_add_and_commit_all(tmp_path, flag_command):
    b = handoff_b(cmd=flag_command + "\n      - run: git commit -m site\n      - run: git push origin main\n      - run: Rscript scripts/site.R", steps=DOWNLOAD_STEP)
    ok, why = strict_tier_one(handoff(tmp_path, b, a=NO_BUILD))
    assert ok, (flag_command, why)


def test_any_build_workflow_makes_a_stage_and_push_workflow_tier_one(tmp_path):
    # Cross-workflow handoff: A builds (names pkgdown), B stages everything and pushes main; B itself shows no build or download.
    ok, why = strict_tier_one(handoff(tmp_path, handoff_b()))
    assert ok, why
    assert any("builds the site" in x for x in why), why
    for n, cmd in enumerate(["git commit -am site\n      - run: git push origin main\n      - run: Rscript scripts/site.R",
                             "git add -u\n      - run: git push\n      - run: Rscript scripts/site.R"]):
        ok, why = strict_tier_one(handoff(fresh(tmp_path, n), handoff_b(cmd=cmd)))
        assert ok, (cmd, why)


def test_a_build_signal_in_a_reached_script_or_an_upload_of_the_destination_counts_as_a_build_workflow(tmp_path):
    builder = step_workflow("Rscript scripts/build.R", top="permissions: read-all\n")
    ok, why = strict_tier_one(handoff(tmp_path, handoff_b(), a=builder, files={"scripts/build.R": "pkgdown::build_site()\n"}))
    assert ok, why
    upload = step_workflow("echo hi", top="permissions: read-all\n", step_extra="      - uses: actions/upload-artifact@v4\n        with:\n          path: docs\n")
    ok, why = strict_tier_one(handoff(fresh(tmp_path, "u"), handoff_b(), a=upload))
    assert ok, why


def test_a_staging_workflow_with_no_build_or_download_relationship_stays_tier_two(tmp_path):
    clean = {"scripts/site.R": CLEAN_R}        # a dynamic script would be an unresolved reference, which is tier one on its own
    assert site.handoff_evidence({"w": [[(0, "stage"), (0, "push"), (2, "push action x")], []]}) == {}
    assert handoff(tmp_path, handoff_b(), a=NO_BUILD, files=clean)["state"] == "complete"
    # ... and the tier-two evidence counts as before once the destination is tracked.
    assert handoff(fresh(tmp_path, "t"), handoff_b(), a=NO_BUILD, files=clean, tracked=True)["state"] == "complete"
    found = [(2, "push action x")]
    assert site.classify_evidence(found, tracked=False) == [] and site.classify_evidence(found, tracked=True) != []


@pytest.mark.parametrize("cmd", ["git add data/history.csv\n      - run: git commit -m h\n      - run: git push origin main\n      - run: Rscript scripts/site.R",
                                 "git add qc-history.csv\n      - run: git commit -m h\n      - run: git push origin main\n      - run: Rscript scripts/site.R"])
def test_a_named_data_file_push_stays_tier_two_even_beside_a_build_workflow_or_a_download(tmp_path, cmd):
    clean = {"scripts/site.R": CLEAN_R}      # (a dynamic script would be an unresolved reference: tier one since round 13)
    assert handoff(tmp_path, handoff_b(cmd=cmd), a=SITE_A, files=clean)["state"] == "complete"
    assert handoff(fresh(tmp_path, "d"), handoff_b(cmd=cmd, steps=DOWNLOAD_STEP), a=NO_BUILD, files=clean)["state"] == "complete"
    assert strict_tier_one(handoff(fresh(tmp_path, "u"), handoff_b(cmd=cmd), a=NO_BUILD))[0]       # ... and with the dynamic script it is


def test_a_declared_branch_push_beside_a_build_workflow_stays_tier_two(tmp_path):
    # The qc-monthly shape: stage a file, push a branch the repository declares non-publishing.
    b = handoff_b(cmd="git add -A\n      - run: git commit -m h\n      - run: git push origin qc-results\n      - run: Rscript scripts/site.R")
    assert handoff(tmp_path, b, files={".rforge.yaml": KEY})["state"] == "complete"
    assert strict_tier_one(handoff(fresh(tmp_path, "u"), b))[0]      # undeclared: an explicit-branch push is tier one already


def test_a_push_alone_or_a_stage_alone_is_not_a_handoff(tmp_path):
    push_only = handoff_b(cmd="git push origin main\n      - run: Rscript scripts/site.R")
    stage_only = handoff_b(cmd="git add -A\n      - run: Rscript scripts/site.R")
    assert handoff(tmp_path, push_only)["state"] == "complete"
    assert handoff(fresh(tmp_path, "s"), stage_only)["state"] == "complete"



# ---------------------------------------------------------------------------------------------------------
# Codex round 13. A workflow that stages and pushes is publish-capable whenever it reaches a reference the scan could
# not resolve (the build may hide behind it). The class is pinned entry by entry: every way ScriptScan fails, every cap,
# every opaque executable.
# ---------------------------------------------------------------------------------------------------------
def stage_push_workflow(*commands, push=True, steps=""):
    lines = list(commands) + (["git add data/history.csv", "git commit -m site", "git push origin main"] if push else [])   # a named pathspec
    body = "\n".join("          " + line for line in lines)
    return (WORKFLOW_HEAD + "permissions:\n  contents: write\njobs:\n  publish:\n    runs-on: ubuntu-latest\n    steps:\n"
            + steps + "      - run: |\n" + body + "\n")


def unresolved_audit(tmp_path, *commands, files=None, push=True, steps="", tracked=False):
    return pair(tmp_path, stage_push_workflow(*commands, push=push, steps=steps), files=files, a=NO_BUILD, tracked=tracked)


def fails_closed(r, why=None):
    ok = r["state"] == "incomplete" and any("script reference unsupported" in x and (why is None or why in x) and "tier 1" in x for x in r["reasons"])
    return ok, r["reasons"]


@pytest.mark.parametrize("cmd,files,why", UNSCANNABLE, ids=[f"{c[:34]}|{w}" for c, _, w in UNSCANNABLE])
def test_every_unscannable_reference_makes_a_stage_and_push_workflow_fail_closed(tmp_path, cmd, files, why):
    ok, reasons = fails_closed(unresolved_audit(tmp_path, cmd, files=files), why)
    assert ok, reasons
    # The same reference with no stage-and-push (and the destination untracked) leaves the workflow relaxed.
    assert unresolved_audit(fresh(tmp_path, "relaxed"), cmd, files=files, push=False)["state"] == "complete"


DYNAMIC_R = [
    ("source-getenv", "source(Sys.getenv('BUILD'))\n"),
    ("source-file-path", "root <- Sys.getenv('ROOT')\nsource(file.path(root, 'x.R'))\n"),
    ("system-paste", "system(paste('Rscript', Sys.getenv('F')))\n"),
]


@pytest.mark.parametrize("name,code", DYNAMIC_R, ids=[n for n, _ in DYNAMIC_R])
def test_a_dynamic_reference_inside_a_reached_r_script_fails_closed_for_stage_and_push(tmp_path, name, code):
    ok, reasons = fails_closed(unresolved_audit(tmp_path, "Rscript scripts/build.R", files={"scripts/build.R": code}), "dynamic")
    assert ok, reasons
    assert unresolved_audit(fresh(tmp_path, "r"), "Rscript scripts/build.R", files={"scripts/build.R": code}, push=False)["state"] == "complete"


OPAQUE_R = [
    ("eval-parse-text", "eval(parse(text = Sys.getenv('X')))\n"),
    ("eval-parse-file", "eval(parse(file = 'scripts/other.R'))\n"),
    ("do-call-source", "do.call(source, list('x.R'))\n"),
    ("do-call-quoted-source", "do.call('source', list(f))\n"),
    ("rmarkdown-render", "rmarkdown::render('a.Rmd')\n"),
    ("knitr-knit", "knitr::knit('a.Rmd')\n"),
    ("quarto-render-r", "quarto::quarto_render('.')\n"),
]
OPAQUE_SHELL = ["quarto render", "node build.js", "npm run build", "npx hugo", "julia build.jl", "ruby build.rb", "perl build.pl", "docker run builder", "hugo", "mkdocs build",
                "sphinx-build -b html . out", "bash -c 'quarto render'"]


@pytest.mark.parametrize("name,code", OPAQUE_R, ids=[n for n, _ in OPAQUE_R])
def test_an_opaque_r_call_in_a_reached_script_fails_closed_for_stage_and_push_only(tmp_path, name, code):
    ok, reasons = fails_closed(unresolved_audit(tmp_path, "Rscript scripts/build.R", files={"scripts/build.R": code}))
    assert ok, reasons
    assert unresolved_audit(fresh(tmp_path, "r"), "Rscript scripts/build.R", files={"scripts/build.R": code}, push=False)["state"] == "complete"


@pytest.mark.parametrize("cmd", OPAQUE_SHELL)
def test_an_opaque_executable_fails_closed_for_stage_and_push_only(tmp_path, cmd):
    ok, reasons = fails_closed(unresolved_audit(tmp_path, cmd))
    assert ok, (cmd, reasons)
    assert unresolved_audit(fresh(tmp_path, "r"), cmd, push=False)["state"] == "complete"


def test_an_opaque_call_in_a_script_reached_by_a_strict_workflow_first_still_blocks_the_stage_and_push_workflow(tmp_path):
    # The visited set must not hide the script: the stage-and-push workflow is scanned first.
    strict = stage_push_workflow("Rscript scripts/build.R", push=False).replace("contents: write", "pages: write")
    r = pair(tmp_path, stage_push_workflow("Rscript scripts/build.R"), a=strict, files={"scripts/build.R": "quarto::quarto_render('.')\n"})
    assert fails_closed(r)[0], r["reasons"]


def test_a_symlinked_script_fails_closed_for_stage_and_push(tmp_path):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path, config=CONFIG, files={SCRIPT_WORKFLOW: NO_BUILD, QC_WORKFLOW: stage_push_workflow("Rscript scripts/deploy.R"), "scripts/real.R": CLEAN_R})
        link(pkg, "scripts/deploy.R", "real.R")
        publish(web, "", root, ROUTES)
        r = site.audit(pkg, url=root, ref="main")
    assert fails_closed(r, "symlink")[0], r["reasons"]


def test_the_depth_and_file_caps_fail_closed_for_stage_and_push(tmp_path):
    chain = {f"s/{i}.R": f"source('s/{i + 1}.R')\n" for i in range(9)}
    chain["s/9.R"] = CLEAN_R
    assert fails_closed(unresolved_audit(tmp_path, "Rscript s/0.R", files=chain), "deep")[0]
    many = {f"m/{i}.R": CLEAN_R for i in range(60)}
    many["m/main.R"] = "".join(f"source('m/{i}.R')\n" for i in range(60))
    assert fails_closed(unresolved_audit(fresh(tmp_path, "m"), "Rscript m/main.R", files=many), "too many")[0]


def test_a_missing_or_dynamic_make_include_fails_closed_for_stage_and_push(tmp_path):
    for n, include in enumerate(["include nothere.mk", "-include $(DIR)/x.mk"]):
        r = unresolved_audit(fresh(tmp_path, n), "make", files={"Makefile": include + "\nall:\n\t@echo hi\n"})
        assert fails_closed(r)[0], (include, r["reasons"])


@pytest.mark.parametrize("uses,files,why", [
    ("./.github/actions/nope", {}, "no action.yml"),
    ("./.github/actions/js", {".github/actions/js/action.yml": "runs:\n  using: node20\n  main: index.js\n"}, "not a composite"),
    ("./../outside", {}, "unresolvable"),
    ("./.github/actions/broken", {".github/actions/broken/action.yml": "runs: [\n"}, "malformed"),
])
def test_an_unresolvable_local_action_fails_closed_for_stage_and_push(tmp_path, uses, files, why):
    r = unresolved_audit(tmp_path, "echo done", files=files, steps=f"      - uses: {uses}\n")
    assert r["state"] == "incomplete" and any(why in x for x in r["reasons"]), r["reasons"]
    # The reason carries the stage-and-push classification, not only the action's own message.
    assert any("tier 1" in x for x in r["reasons"]) or any(why in x for x in r["reasons"])


def test_a_local_action_with_a_dynamic_script_fails_closed_for_stage_and_push_and_not_otherwise(tmp_path):
    action = "runs:\n  using: composite\n  steps:\n    - run: Rscript scripts/site.R\n      shell: bash\n"
    steps = "      - uses: ./.github/actions/build\n"
    assert fails_closed(unresolved_audit(tmp_path, "echo done", files={".github/actions/build/action.yml": action}, steps=steps), "dynamic")[0]
    assert unresolved_audit(fresh(tmp_path, "x"), "echo done", files={".github/actions/build/action.yml": action}, steps=steps, push=False)["state"] == "complete"


def test_a_dynamic_working_directory_fails_closed_for_stage_and_push(tmp_path):
    r = unresolved_audit(tmp_path, "cd $DIR && Rscript scripts/site.R")
    assert fails_closed(r, "dynamic working directory")[0], r["reasons"]


NEGATIVE_RESOLVED = [
    ("Rscript scripts/clean.R", {"scripts/clean.R": CLEAN_R}),
    ("Rscript scripts/clean.R", {"scripts/clean.R": "source('scripts/helper.R')\n", "scripts/helper.R": CLEAN_R}),
    ("bash scripts/ok.sh", {"scripts/ok.sh": "echo hello\nls\n"}),
    ("make", {"Makefile": "all:\n\t@echo hi\n"}),
    ("python3 scripts/tally.py", {"scripts/tally.py": "print(1)\n"}),
    ("echo done", {}),
]


@pytest.mark.parametrize("cmd,files", NEGATIVE_RESOLVED)
def test_stage_and_push_with_only_fully_resolved_non_build_scripts_stays_tier_two(tmp_path, cmd, files):
    assert unresolved_audit(tmp_path, cmd, files=files)["state"] == "complete"
    # ... and counts as before once the destination is tracked, and nothing else changes.
    r = unresolved_audit(fresh(tmp_path, "t"), cmd, files=files, tracked=True)
    assert r["state"] == "complete" or all("tier 1" not in x for x in r["reasons"]), r["reasons"]


def test_the_qc_monthly_shape_stays_tier_two_with_unresolved_references_when_it_pushes_a_declared_branch(tmp_path):
    qc = stage_push_workflow("Rscript scripts/site.R", "node build.js", push=False).rstrip("\n") + "\n          git add qc-history.csv\n          git commit -m h\n          git push origin qc-results\n"
    assert pair(tmp_path, qc, a=NO_BUILD, files={".rforge.yaml": KEY})["state"] == "complete"
    # Staging everything and pushing the default branch beside the same references is the stage-and-push case.
    assert fails_closed(pair(fresh(tmp_path, "d"), qc.replace("qc-results", "main").replace("git add qc-history.csv", "git add -A"), a=NO_BUILD, files={".rforge.yaml": KEY}))[0]


def test_a_push_to_a_declared_branch_is_not_a_stage_and_push_even_with_add_all(tmp_path):
    b = stage_push_workflow("Rscript scripts/site.R", push=False).rstrip("\n") + "\n          git add -A\n          git commit -m h\n          git push origin qc-results\n"
    assert pair(tmp_path, b, a=NO_BUILD, files={".rforge.yaml": KEY})["state"] == "complete"
    assert fails_closed(pair(fresh(tmp_path, "u"), b, a=NO_BUILD))[0]        # undeclared: explicit-branch push, tier one


def test_an_unresolved_reference_in_a_reusable_callee_reaches_a_stage_and_push_caller(tmp_path):
    # Job-level `uses:` is itself unsupported, so the stage is incomplete either way; the facts must still travel.
    callee = "on:\n  workflow_call:\npermissions:\n  contents: write\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: Rscript scripts/site.R\n"
    caller = stage_push_workflow("echo hi").replace("jobs:\n  publish:", "jobs:\n  call:\n    uses: ./.github/workflows/callee.yml\n  publish:")
    r = pair(tmp_path, caller, a=NO_BUILD, files={".github/workflows/callee.yml": callee})
    assert r["state"] == "incomplete" and any("reusable workflow job unsupported" in x for x in r["reasons"]), r["reasons"]


PUSH_ACTION_B = workflow_b(top="permissions: read-all\n", steps="      - uses: ad-m/github-push-action@v0.8.0\n")


def test_a_push_action_stages_and_pushes_so_an_unresolved_reference_makes_it_tier_one(tmp_path):
    # It was a tier-two fixture before round 13; the dynamic indicator script is now itself an unresolved reference.
    for n, tracked in enumerate((False, True)):
        r = pair(fresh(tmp_path, n), PUSH_ACTION_B, a=NO_BUILD, tracked=tracked)
        assert reached(r, "script reference unsupported", "dynamic") and any("may publish: tier 1" in x for x in r["reasons"]), (tracked, r["reasons"])
    # Since round 15 a push action (it adds, commits and pushes) is publish capable on its own, resolved scripts or not.
    clean = {"scripts/site.R": CLEAN_R}
    for n, tracked in enumerate((False, True)):
        r = pair(fresh(tmp_path, f"c{n}"), PUSH_ACTION_B, a=NO_BUILD, files=clean, tracked=tracked)
        assert r["state"] == "incomplete" and any(PUBLISH_CAPABLE in x for x in r["reasons"]), r["reasons"]


# ---------------------------------------------------------------------------------------------------------
# Codex round 14. The opaque list was a denylist and kept missing executables (python -m, ...). It is now an
# allowlist: any executable the scan neither follows nor knows to be benign is opaque.
# ---------------------------------------------------------------------------------------------------------
OPAQUE_NOW = [
    "python -m site_generator", "python3 -m site_generator build", "python -c 'import gen; gen.run()'", "python3 -c \"$CODE\"", "python -m pytest",
    "uv run site-generator", "uv run --with x python -m gen", "uv run pytest", "uv tool run gen", "mytool build", "gen-site --out docs", "scripts/gen",
    "bash -c \"$X\"", "sh -c \"$BUILD\"", "bash -c 'mytool build'", "sh -c 'mytool'", "pip run-something", "apt-get source foo", "brew services start x",
    "find . -name '*.md' -exec mytool {} +", "xargs mytool", "sudo mytool", "env FOO=1 mytool", "if true; then mytool; fi", "for f in a b; do mytool $f; done",
    "(cd out && mytool)", "/opt/tools/mytool", "ghostscript x", "R2 build",
]
BENIGN_NOW = [
    "git status", "echo hi", "printf '%s' x", "cat README.md", "ls -la", "pwd", "mkdir -p out", "rm -rf tmp", "cp a b", "mv a b", "touch x", "test -f x",
    "[ -f x ]", "[[ -f x ]]", "true", "false", "exit 0", "export A=1", "set -e", "sleep 1", "date -u", "env", "which R", "grep -r x .", "sed -i s/a/b/ f",
    "awk '{print}' f", "head -1 f", "tail -1 f", "tee out.txt", "sort f", "uniq f", "wc -l f", "tr a b", "cut -d, -f1 f", "find . -name '*.csv'", "xargs rm",
    "jq . f.json", "curl -sS https://example.org/x", "wget -q https://example.org/x", "sudo apt-get install -y libxml2-dev", "sudo apt install pandoc", "brew install pandoc",
    "pip install -r requirements.txt", "pip3 install pandas", "python -m pip install pandas", "python3 -m pip install -U pip", "uv pip install pandas", "uv sync",
    "gh run list", "gh pr view 1", "sh -c 'echo hi'", "bash -c 'ls && pwd'", "Rscript -e 'cat(1)'", "R CMD INSTALL .", "R CMD build .", "R CMD check pkg.tar.gz",
    "if true; then echo hi; fi", "for f in a b; do echo $f; done", "cd subdir", "echo hi | tee out.txt", "FOO=1 echo hi", "uv run python scripts/tally.py", "python3 scripts/tally.py",
]


@pytest.mark.parametrize("cmd", OPAQUE_NOW)
def test_an_unlisted_executable_fails_closed_for_stage_and_push_only(tmp_path, cmd):
    ok, reasons = fails_closed(unresolved_audit(tmp_path, cmd, files={"scripts/tally.py": "print(1)\n"}))
    assert ok, (cmd, reasons)
    assert unresolved_audit(fresh(tmp_path, "r"), cmd, push=False, files={"scripts/tally.py": "print(1)\n"})["state"] == "complete"


@pytest.mark.parametrize("cmd", BENIGN_NOW)
def test_an_allowlisted_command_leaves_a_stage_and_push_workflow_tier_two(tmp_path, cmd):
    files = {"scripts/tally.py": "print(1)\n"}
    r = unresolved_audit(tmp_path, cmd, files=files)
    assert r["state"] == "complete", (cmd, r["reasons"])


def test_a_python_script_with_a_dynamic_path_or_that_runs_other_code_is_unresolved(tmp_path):
    assert fails_closed(unresolved_audit(tmp_path, "python3 $SCRIPT"), "dynamic")[0]
    assert fails_closed(unresolved_audit(fresh(tmp_path, "s"), "python3 scripts/run.py", files={"scripts/run.py": "import subprocess\nsubprocess.run(['mytool'])\n"}))[0]
    assert fails_closed(unresolved_audit(fresh(tmp_path, "o"), "python3 scripts/run.py", files={"scripts/run.py": "import os\nos.system('mytool')\n"}))[0]
    # A plain python script that only computes is read and is benign; its text is not parsed as shell.
    assert unresolved_audit(fresh(tmp_path, "p"), "python3 scripts/run.py", files={"scripts/run.py": "import json\nprint(json.dumps({}))\nmytool build\n"})["state"] == "complete"


def test_a_makefile_variable_or_target_line_is_not_a_command(tmp_path):
    makefile = "CC = gcc\nall: build\n\t@echo hi\nbuild:\n\tmytool build\n"
    assert fails_closed(unresolved_audit(tmp_path, "make", files={"Makefile": makefile}))[0]       # the recipe runs an unlisted tool
    assert unresolved_audit(fresh(tmp_path, "m"), "make", files={"Makefile": "CC = gcc\nall: build\nbuild:\n\t@echo hi\n"})["state"] == "complete"


def test_a_resolved_script_that_calls_an_unlisted_executable_is_unresolved_through_the_script(tmp_path):
    assert fails_closed(unresolved_audit(tmp_path, "bash scripts/b.sh", files={"scripts/b.sh": "echo hi\nmytool build\n"}))[0]
    assert unresolved_audit(fresh(tmp_path, "b"), "bash scripts/b.sh", files={"scripts/b.sh": "echo hi\nls\ngit status\n"})["state"] == "complete"
    assert fails_closed(unresolved_audit(fresh(tmp_path, "r"), "Rscript scripts/b.R", files={"scripts/b.R": "system('mytool build')\n"}))[0]


def test_the_qc_monthly_shape_with_only_allowlisted_commands_stays_tier_two(tmp_path):
    qc = ("git config user.name bot\ngit fetch --depth 1 origin qc-results\ngit show FETCH_HEAD:qc-history.csv > prev.csv || rm -f prev.csv\n"
          "Rscript scripts/site.R\ngit add qc-history.csv\ngit commit -m h\ngit push origin qc-results")
    assert pair(tmp_path, stage_push_workflow(*qc.split("\n"), push=False), a=NO_BUILD, files={".rforge.yaml": KEY, "scripts/site.R": CLEAN_R})["state"] == "complete"


# ---------------------------------------------------------------------------------------------------------
# Codex round 15. The audit no longer tries to prove that a stage-and-push workflow builds no site: a workflow that
# stages everything (or names the destination, or a pathspec that can match it) and pushes the default branch is publish
# capable, whatever its scripts do.
# ---------------------------------------------------------------------------------------------------------
PUBLISH_CAPABLE = "stages everything and pushes the default branch"
WRITER_PY = "from pathlib import Path\nPath('docs').mkdir(exist_ok=True)\nPath('docs/sitemap.xml').write_text('<urlset/>')\n"
WRITER_R = "dir.create('docs')\nwriteLines('<urlset/>', 'docs/sitemap.xml')\n"


def capable(r):
    return r["state"] == "incomplete" and any(PUBLISH_CAPABLE in x or "stages the site destination" in x for x in r["reasons"]), r["reasons"]


def push_workflow(*commands, add="git add -A", commit="git commit -m site", push="git push origin main"):
    lines = list(commands) + [x for x in (add, commit, push) if x]
    return stage_push_workflow(*lines, push=False)


def audit_push(tmp_path, *commands, files=None, tracked=False, **kw):
    return pair(tmp_path, push_workflow(*commands, **kw), files={"scripts/site.R": CLEAN_R, **(files or {})}, a=NO_BUILD, tracked=tracked)


ALL_FORMS = ["git add -A", "git add --all", "git add .", "git add -u", "git add --update", "git add -f .", "git add -A .", "git add ./", "git add ':/'",
             "git add '*'", "git add $DIR", "git add \"$f\"", "git add -A $PATHSPEC"]


@pytest.mark.parametrize("add", ALL_FORMS)
@pytest.mark.parametrize("tracked", [False, True], ids=["untracked", "tracked"])
def test_staging_everything_and_pushing_the_default_branch_is_publish_capable(tmp_path, add, tracked):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=add, tracked=tracked))
    assert ok, (add, why)


@pytest.mark.parametrize("commit", ["git commit -a -m site", "git commit -am site", "git commit --all -m site"])
def test_commit_all_and_a_push_is_publish_capable(tmp_path, commit):
    ok, why = capable(audit_push(tmp_path, "echo hello", add="git status", commit=commit))
    assert ok, (commit, why)


@pytest.mark.parametrize("push", ["git push origin main", "git push", "git push origin HEAD", "git push origin master", "git push -u origin main"])
def test_every_default_branch_or_refspecless_push_counts(tmp_path, push):
    ok, why = capable(audit_push(tmp_path, "echo hello", push=push))
    assert ok, (push, why)


def test_an_add_and_commit_or_auto_commit_action_is_publish_capable(tmp_path):
    for n, action in enumerate(["stefanzweifel/git-auto-commit-action@v5", "endbug/add-and-commit@v9", "ad-m/github-push-action@v0.8.0", "actions-js/push@master"]):
        b = stage_push_workflow("echo hi", push=False, steps=f"      - uses: {action}\n")
        ok, why = capable(pair(fresh(tmp_path, n), b, files={"scripts/site.R": CLEAN_R}, a=NO_BUILD))
        assert ok, (action, why)


def test_a_utility_that_writes_the_destination_is_caught_without_enumerating_it(tmp_path):
    for n, cmd in enumerate(["printf x | tee docs/sitemap.xml", "echo '<urlset/>' > docs/sitemap.xml", "curl -sL https://example.org/s.xml -o docs/sitemap.xml",
                             "tar -xzf site.tgz -C docs", "unzip -q site.zip -d docs", "cp -r _site docs", "sed 's/a/b/' in.xml > docs/out.xml"]):
        ok, why = capable(audit_push(fresh(tmp_path, n), cmd))
        assert ok, (cmd, why)


def test_a_followed_script_that_writes_the_destination_directly_is_caught(tmp_path):
    ok, why = capable(audit_push(tmp_path, "python3 scripts/w.py", files={"scripts/w.py": WRITER_PY}))
    assert ok, why
    ok, why = capable(audit_push(fresh(tmp_path, "r"), "Rscript scripts/w.R", files={"scripts/w.R": WRITER_R}))
    assert ok, why


@pytest.mark.parametrize("add", ["git add -f docs", "git add docs", "git add docs/", "git add 'docs*'", "git add d*", "git add '*/sitemap.xml'", "git add -A docs", "git add docs/sitemap.xml",
                                 "git add --force ./docs"])
def test_a_pathspec_that_is_or_can_match_the_destination_is_publish_capable(tmp_path, add):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=add))
    assert ok, (add, why)


def test_a_pathspec_that_is_a_parent_of_the_destination_is_publish_capable(tmp_path):
    ok, why = capable(pair(tmp_path, push_workflow("echo hello", add="git add pkgsub"), a=NO_BUILD, files={"scripts/site.R": CLEAN_R}, config="destination: pkgsub/out\n"))
    assert ok, why


@pytest.mark.parametrize("add", ["git add data/history.csv", "git add qc-history.csv", "git add data/ reports/", "git add -A data/", "git add docs-archive/x.md", "git add R/foo.R man/foo.Rd",
                                 "git add 'data/*.csv'", "git add -f data/history.csv", "git add NEWS.md"])
def test_a_named_pathspec_outside_the_destination_stays_tier_two(tmp_path, add):
    for n, tracked in enumerate((False, True)):
        r = audit_push(fresh(tmp_path, n), "echo hello", add=add, tracked=tracked)
        assert r["state"] == "complete", (add, tracked, r["reasons"])


def test_the_negatives_of_the_rule(tmp_path):
    # add-everything with no push
    assert audit_push(tmp_path, "echo hello", push=None)["state"] == "complete"
    # a push to a branch the repository declares non-publishing is not a push
    r = audit_push(fresh(tmp_path, "d"), "echo hello", push="git push origin qc-results", files={".rforge.yaml": KEY})
    assert r["state"] == "complete", r["reasons"]
    # ... but the same push undeclared is an explicit-branch push (tier one already), and with add-everything it is reported
    assert audit_push(fresh(tmp_path, "u"), "Rscript scripts/site.R", push="git push origin qc-results", files={"scripts/site.R": "source(Sys.getenv('X'))\n"})["state"] == "incomplete"
    # a push with nothing staged
    assert audit_push(fresh(tmp_path, "p"), "echo hello", add="git status", commit="git commit --allow-empty -m x")["state"] == "complete"


def test_stage_everything_and_push_in_a_repository_that_is_not_pkgdown_is_relaxed(tmp_path):
    r = pair(tmp_path, push_workflow("echo hello"), a=NO_BUILD, config=None, files={"scripts/site.R": CLEAN_R})
    assert r["state"] == "complete", r["reasons"]


def test_the_reason_states_the_rule_plainly(tmp_path):
    r = audit_push(tmp_path, "echo hello")
    text = next(x for x in r["reasons"] if PUBLISH_CAPABLE in x)
    assert "publish capable" in text and "does not try to prove" in text and ".github/workflows/qc.yaml" in text


def test_the_named_pathspec_with_an_unresolved_or_opaque_reference_is_still_tier_one(tmp_path):
    # The round 13 and 14 rules still apply on top: named stage + push + an unresolved reference.
    for n, cmd in enumerate(["Rscript scripts/site.R", "mytool build", "python3 -m gen"]):
        files = {"scripts/site.R": "source(Sys.getenv('X'))\n"}
        r = audit_push(fresh(tmp_path, n), cmd, add="git add -f data/history.csv", files=files)
        assert fails_closed(r)[0], (cmd, r["reasons"])


def test_the_pull_request_push_action_is_not_a_default_branch_push(tmp_path):
    # r-lib/actions/pr-push (the /document and /style bots in glue) pushes the PR branch; named pathspecs beside it stay tier two.
    b = stage_push_workflow("git add man/\\* NAMESPACE", "git commit -m Document", push=False, steps="      - uses: r-lib/actions/pr-push@v2\n")
    assert pair(tmp_path, b, a=NO_BUILD, files={"scripts/site.R": CLEAN_R})["state"] == "complete"


# ---------------------------------------------------------------------------------------------------------
# Codex round 16. A stage is NAMED (tier two) only when every pathspec is a plain literal path outside the destination.
# Pathspec magic, pathspec files and index-changing git plumbing stage everything, and unknown forms fail closed.
# ---------------------------------------------------------------------------------------------------------
MAGIC_FORMS = ["git add -A -- ':(top)docs'", "git add ':/docs'", "git add ':(glob)do*'", "git add ':(icase)DOCS'", "git add ':!data'", "git add ':^data'",
               "git add -- docs", "git add -- ':(top)docs/sitemap.xml'", "git add ../docs", "git add /abs/docs", "git add ~/docs", "git add {docs,data}",
               "git add 'docs\\x'"]


@pytest.mark.parametrize("add", MAGIC_FORMS)
def test_pathspec_magic_and_unreadable_forms_stage_everything(tmp_path, add):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=add))
    assert ok, (add, why)


@pytest.mark.parametrize("add", ["git add --pathspec-from-file=files.txt", "git add --pathspec-from-file files.txt", "git add --pathspec-from-file=- --pathspec-file-nul",
                                 "git add --pathspec-from-file=$LIST"])
def test_a_pathspec_file_stages_everything_whether_or_not_it_can_be_read(tmp_path, add):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=add, files={"files.txt": "docs\n"}))
    assert ok, (add, why)


@pytest.mark.parametrize("add", ["git update-index --add docs/x", "git read-tree HEAD", "git checkout-index -a", "git apply site.patch", "git am site.mbox", "git stash",
                                 "git write-tree"])
def test_index_changing_git_plumbing_stages_everything(tmp_path, add):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=add, commit="git commit -m x"))
    assert ok, (add, why)


def test_commit_tree_plumbing_stages_everything(tmp_path):
    ok, why = capable(audit_push(tmp_path, "T=$(git write-tree)", add="git commit-tree $T -m x", commit=None))
    assert ok, why


@pytest.mark.parametrize("commit", ["git commit -m x docs", "git commit -m x -- ':(top)docs'", "git commit -m x ':/docs'", "git commit -m x 'docs*'"])
def test_a_commit_that_names_a_path_that_is_not_plain_counts(tmp_path, commit):
    ok, why = capable(audit_push(tmp_path, "echo hello", add="git status", commit=commit))
    assert ok, (commit, why)


@pytest.mark.parametrize("cmd", ["git rm -r docs", "git rm --cached ':(top)docs'", "git mv _site docs", "git mv a.csv docs/a.csv"])
def test_rm_and_mv_of_the_destination_or_an_unplain_path_count(tmp_path, cmd):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=cmd))
    assert ok, (cmd, why)


@pytest.mark.parametrize("add", ["git add data/history.csv", "git add -- qc-history.csv", "git add -- data/history.csv reports/q.csv", "git add 'data/*.csv'", "git add man/*.Rd NAMESPACE",
                                 "git add -f data/history.csv", "git add --verbose data/history.csv", "git rm old-notes.md", "git mv a.csv b.csv"])
def test_plain_literal_pathspecs_outside_the_destination_stay_named(tmp_path, add):
    for n, tracked in enumerate((False, True)):
        r = audit_push(fresh(tmp_path, n), "echo hello", add=add, tracked=tracked)
        assert r["state"] == "complete", (add, tracked, r["reasons"])


def test_the_qc_monthly_shape_and_the_declared_branch_stay_tier_two(tmp_path):
    r = audit_push(tmp_path, "echo hello", add="git add qc-history.csv", commit="git commit -m qc", push="git push origin qc-results", files={".rforge.yaml": KEY})
    assert r["state"] == "complete", r["reasons"]
    r = audit_push(fresh(tmp_path, "m"), "echo hello", add="git add -A -- ':(top)docs'", push="git push origin qc-results", files={".rforge.yaml": KEY})
    assert r["state"] == "complete", r["reasons"]


def test_a_magic_pathspec_without_a_push_is_relaxed(tmp_path):
    assert audit_push(tmp_path, "echo hello", add="git add -A -- ':(top)docs'", push=None)["state"] == "complete"


def test_plain_literal_path_unit():
    from lib._docsite import plain_literal_path
    names = ["docs"]
    for good in ("data/history.csv", "qc-history.csv", "R/foo.R", "docs-archive/x.md", "man/*.Rd", "data/*.csv", "NEWS.md"):
        assert plain_literal_path(good, names), good
    for bad in (":(top)docs", ":/docs", ":!data", "docs", "docs/x", "./docs", "..", "../docs", "/x", "~/x", "$X", "{a,b}", ".", "./", "*", "d*", "*.html", "-A", "a\\b", "", "**/foo.html", "**/*.html", "*.Rd", "*/x", "?ocs/x", "[d]ocs/x", "*/sitemap.xml", "docs*/x"):
        assert not plain_literal_path(bad, names), bad


def test_a_rootless_or_recursive_glob_stages_everything_when_it_can_match_the_destination(tmp_path):
    for n, add in enumerate(["git add '**/foo.html'", "git add '**/*.html'", "git add '*.xml'", "git add '?ocs/index.html'", "git add '[d]ocs/x'", "git add '*/index.html'"]):
        ok, why = capable(audit_push(fresh(tmp_path, n), "echo hello", add=add))
        assert ok, (add, why)


# Codex round 18. A push the scan cannot read (`$(command -v git) push origin main`) must not hide behind a missing push fact:
# a workflow that stages everything and reaches an unresolved or opaque command may push, so it is publish capable.
@pytest.mark.parametrize("push", ["$(command -v git) push origin main", "$GIT push origin main", "\"$(which git)\" push origin main", "sudo $GITBIN push"])
def test_an_opaque_push_after_staging_everything_is_publish_capable(tmp_path, push):
    ok, why = capable_or_unresolved(audit_push(tmp_path, "echo hello", push=push))
    assert ok, (push, why)


def capable_or_unresolved(r):
    return r["state"] == "incomplete" and any(("cannot resolve" in x or PUBLISH_CAPABLE in x) for x in r["reasons"]), r["reasons"]


def test_staging_everything_with_nothing_opaque_and_no_push_stays_relaxed(tmp_path):
    assert audit_push(tmp_path, "echo hello", push=None)["state"] == "complete"


def test_stage_everything_beside_an_unreadable_script_or_a_named_unknown_binary_stays_relaxed_without_a_push(tmp_path):
    # Only a computed program name may be a hidden push; a dynamic script reference or a named binary is not.
    dynamic_script = audit_push(tmp_path, "Rscript scripts/site.R", push=None, files={"scripts/site.R": "source(Sys.getenv('X'))\n"})
    assert dynamic_script["state"] == "complete", dynamic_script["reasons"]
    named = audit_push(fresh(tmp_path, "b"), "mytool build", push=None)
    assert named["state"] == "complete", named["reasons"]


# Codex round 19. An earlier unresolved reference must not hide a computed program that may push.
@pytest.mark.parametrize("push", ["$GIT push origin main", "$(command -v git) push origin main"])
def test_a_missing_script_before_a_computed_push_does_not_hide_it(tmp_path, push):
    ok, why = capable_or_unresolved(audit_push(tmp_path, "Rscript scripts/missing.R", push=push))
    assert ok, (push, why)
    ok, why = capable_or_unresolved(audit_push(fresh(tmp_path, "d"), "python3 $SCRIPT", push=push))
    assert ok, (push, why)


# Codex round 20. Only a computed PROGRAM name may be a hidden push: a fixed unknown executable with a dynamic argument is not.
@pytest.mark.parametrize("cmd", ["mytool $ARG", "mytool --out \"$DIR\"", "mytool $(date +%s)", "python3 -m mymod $X"])
def test_a_fixed_executable_with_a_dynamic_argument_is_not_a_computed_program(tmp_path, cmd):
    r = audit_push(tmp_path, cmd, push=None)
    assert r["state"] == "complete", (cmd, r["reasons"])


# Codex round 21. A computed executable PATH (`$BIN/git`) must be judged on the raw token, not on its allowed basename.
@pytest.mark.parametrize("push", ["$BIN/git push origin main", "\"$BIN/git\" push origin main", "${GIT_DIR}/git push", "$(dirname $(which git))/git push origin main"])
def test_a_computed_executable_path_that_ends_in_git_is_a_hidden_push(tmp_path, push):
    ok, why = capable_or_unresolved(audit_push(tmp_path, "echo hello", push=push))
    assert ok, (push, why)


def test_a_computed_path_to_an_allowlisted_name_is_still_opaque_but_a_fixed_one_is_not(tmp_path):
    fixed = audit_push(tmp_path, "/usr/bin/git status", push=None)
    assert fixed["state"] == "complete", fixed["reasons"]
    computed = audit_push(fresh(tmp_path, "c"), "$BIN/ls", push="$BIN/git push origin main")
    assert capable_or_unresolved(computed)[0], computed["reasons"]


# Codex round 22. A literal path to the executable (`/usr/bin/git`) is the same program as `git`.
@pytest.mark.parametrize("git", ["/usr/bin/git", "/opt/homebrew/bin/git", "./bin/git", "bin/git", "~/bin/git"])
def test_a_literal_path_to_git_is_detected_for_staging_and_pushing(tmp_path, git):
    ok, why = capable(audit_push(tmp_path, "echo hello", add=f"{git} add -A", commit=f"{git} commit -m site", push=f"{git} push origin main"))
    assert ok, (git, why)


def test_a_literal_path_to_git_keeps_the_named_stage_negative_and_the_pathspec_rule(tmp_path):
    named = audit_push(tmp_path, "echo hello", add="/usr/bin/git add data/history.csv", commit="/usr/bin/git commit -m x", push="/usr/bin/git push origin main")
    assert named["state"] == "complete", named["reasons"]
    ok, why = capable(audit_push(fresh(tmp_path, "m"), "echo hello", add="/usr/bin/git add -A -- ':(top)docs'", push="/usr/bin/git push origin main"))
    assert ok, why
    declared = audit_push(fresh(tmp_path, "d"), "echo hello", add="/usr/bin/git add -A", push="/usr/bin/git push origin qc-results", files={".rforge.yaml": KEY})
    assert declared["state"] == "complete", declared["reasons"]


def test_a_literal_path_to_a_publish_command_or_downloader_is_detected(tmp_path):
    for n, (bare, prefixed) in enumerate([("rsync -a _site/ deploy@host:/var/www/", "/usr/bin/rsync -a _site/ deploy@host:/var/www/"),
                                          ("rsync -a _site/ docs/", "/usr/bin/rsync -a _site/ docs/")]):
        a = audit_push(fresh(tmp_path, f"b{n}"), bare, add="git add data/history.csv")
        b = audit_push(fresh(tmp_path, f"p{n}"), prefixed, add="git add data/history.csv")
        assert (a["state"], a["reasons"]) == (b["state"], b["reasons"]), (bare, a["reasons"], b["reasons"])
    ok, why = capable_or_unresolved(audit_push(fresh(tmp_path, "c"), "/usr/bin/curl -sL https://example.org/site.tgz -o site.tgz", add="/usr/bin/git add -A", push="/usr/bin/git push origin main"))
    assert ok, why


# Codex round 23. An opaque build in ANY workflow that may publish (a Pages deploy included) is an incomplete reason; in a
# workflow that cannot publish it stays documented as not detected.
PAGES = "      - uses: actions/deploy-pages@v4\n"


@pytest.mark.parametrize("build", ["python -m site_generator", "python -c 'import gen; gen.run()'", "node build.js", "mytool build --site", "$BUILDER run"])
def test_an_opaque_build_before_a_pages_deploy_is_incomplete(tmp_path, build):
    r = pair(tmp_path, stage_push_workflow(build, push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert r["state"] == "incomplete", (build, r["reasons"])
    assert any(build.split()[0].strip("$") in x or "opaque" in x or "cannot be verified" in x for x in r["reasons"]), r["reasons"]


def test_a_pages_deploy_with_nothing_opaque_stays_complete_and_an_opaque_build_without_a_deploy_is_not_detected(tmp_path):
    clean = pair(tmp_path, stage_push_workflow("echo hello", push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert clean["state"] == "complete", clean["reasons"]
    quiet = pair(fresh(tmp_path, "q"), stage_push_workflow("python -m site_generator", push=False), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert quiet["state"] == "complete", quiet["reasons"]


# Codex round 24. Wrapper options must be parsed before the executable is classified, and a repo-relative path must be read
# even when its basename is an allowlisted name.
@pytest.mark.parametrize("push", ["env -- \"$GIT\" push origin main", "sudo -E \"$GIT\" push", "env -u HOME $GIT push", "nice -n 5 $GIT push origin main",
                                  "sudo -u runner -- $GIT push", "env -i -- $GIT push"])
def test_a_wrapped_computed_push_is_not_hidden_by_the_wrapper_options(tmp_path, push):
    ok, why = capable_or_unresolved(audit_push(tmp_path, "echo hello", push=push))
    assert ok, (push, why)


@pytest.mark.parametrize("push", ["env -- git push origin main", "sudo -E git push", "nice -n 5 git push origin main", "/usr/bin/env -- /usr/bin/git push origin main"])
def test_a_wrapped_literal_push_is_still_a_push(tmp_path, push):
    ok, why = capable(audit_push(tmp_path, "echo hello", push=push))
    assert ok, (push, why)


def test_command_dash_v_is_a_lookup_not_a_run(tmp_path):
    r = audit_push(tmp_path, "command -v git", push=None)
    assert r["state"] == "complete", r["reasons"]


def test_a_repo_relative_path_with_an_allowlisted_basename_is_read(tmp_path):
    def run(files, n):
        return pair(fresh(tmp_path, n), stage_push_workflow("tools/echo publish", push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R, **files}, a=NO_BUILD, tracked=False)
    assert run({}, "missing")["state"] == "incomplete"                                              # unreadable: fails closed
    assert run({"tools/echo": "#!/bin/sh\npython -m gen\n"}, "opaque")["state"] == "incomplete"      # reads the file, finds an opaque build
    assert run({"tools/echo": "#!/bin/sh\necho ok\n"}, "clean")["state"] == "complete"


def test_a_literal_absolute_path_outside_the_system_bin_directories_is_opaque_in_a_publishing_workflow(tmp_path):
    for n, cmd in enumerate(["/home/runner/tools/echo publish", "~/bin/echo publish", "/opt/custom/ls ."]):
        r = pair(fresh(tmp_path, n), stage_push_workflow(cmd, push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
        assert r["state"] == "incomplete", (cmd, r["reasons"])
    ok = pair(fresh(tmp_path, "ok"), stage_push_workflow("/usr/bin/echo publish", push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert ok["state"] == "complete", ok["reasons"]


# Codex round 25. Wrapper options that change what runs (`env -S`) or where (`env -C`, `sudo -D`) fail closed in a publishing workflow.
@pytest.mark.parametrize("cmd", ["env -S 'python -m site_generator'", "env --split-string='python -m gen'", "env -C site ./tools/echo", "env --chdir=site ./tools/echo",
                                 "env -Csite ./tools/echo", "sudo -D site ./tools/echo", "sudo --chdir=site tools/echo", "sudo -i", "sudo -s 'python -m gen'"])
def test_a_wrapper_that_rewrites_the_command_or_its_directory_is_opaque_in_a_publishing_workflow(tmp_path, cmd):
    r = pair(tmp_path, stage_push_workflow(cmd, push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R, "tools/echo": "#!/bin/sh\necho ok\n"}, a=NO_BUILD, tracked=False)
    assert r["state"] == "incomplete", (cmd, r["reasons"])


@pytest.mark.parametrize("cmd", ["env -i echo hi", "env -u HOME echo hi", "sudo -E echo hi", "nice -n 5 echo hi", "env FOO=bar echo hi", "sudo -u runner echo hi"])
def test_wrappers_that_only_set_the_environment_or_user_stay_transparent(tmp_path, cmd):
    r = pair(tmp_path, stage_push_workflow(cmd, push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert r["state"] == "complete", (cmd, r["reasons"])


# Codex round 26. `gh` is allowlisted for reads, but a write through `gh api` (or a deploy trigger) can change the site with a
# separate token, so it is a publish signal and an opaque call.
GH_WRITES = ["gh api -X PUT repos/o/r/contents/docs/index.html --input payload.json", "gh api --method POST repos/o/r/git/refs -f ref=refs/heads/gh-pages",
             "gh api repos/o/r/contents/docs/x.html -f message=m -f content=Zg==", "gh api -XPUT repos/o/r/contents/docs/a", "gh api $ENDPOINT",
             "gh workflow run deploy.yaml", "gh pr merge 12 --squash", "gh release upload v1 site.zip"]


@pytest.mark.parametrize("cmd", GH_WRITES)
def test_a_gh_command_that_writes_is_a_publish_signal_and_incomplete(tmp_path, cmd):
    r = pair(tmp_path, stage_push_workflow(cmd, push=False), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert r["state"] == "incomplete", (cmd, r["reasons"])


@pytest.mark.parametrize("cmd", ["gh api repos/o/r", "gh api -X GET repos/o/r/contents/docs", "gh run download 123", "gh pr view 12", "gh pr comment 12 --body hi", "gh release download v1",
                                 "gh workflow list", "gh issue create --title t"])
def test_a_gh_read_stays_benign(tmp_path, cmd):
    r = pair(tmp_path, stage_push_workflow(cmd, push=False, steps=PAGES), files={"scripts/site.R": CLEAN_R}, a=NO_BUILD, tracked=False)
    assert r["state"] == "complete", (cmd, r["reasons"])


# ---------------------------------------------------------------------------------------------------------
# Deploy-layout marker. The workflow and script scan that decides whether CI could deploy a different layout is best effort
# and cannot be exhaustive (Codex rounds 11-27 kept finding another command or setting it treats as harmless), so a complete
# stage never claims the deploy layout is verified: the stage carries `deploy_layout: "unverified"` and a clean text report
# says so. The marker is a fixed property of the stage, not a result of the scan.
# ---------------------------------------------------------------------------------------------------------
def test_the_deploy_layout_marker_is_on_every_stage_whatever_the_scan_concludes(tmp_path):
    # complete, with a workflow the scan classifies as quiet
    r = audit_push(tmp_path, "echo hello", push=None)
    assert r["state"] == "complete" and r["deploy_layout"] == "unverified", r
    # incomplete
    r = audit_push(fresh(tmp_path, "i"), "echo hello")
    assert r["state"] == "incomplete" and r["deploy_layout"] == "unverified", r
    # a hidden route the scan cannot see (an allowlisted `awk -f` script) still reports complete, and says it is unverified
    hidden = pair(fresh(tmp_path, "h"), stage_push_workflow("awk -f tools/publish.awk", push=False, steps=PAGES),
                  files={"scripts/site.R": CLEAN_R, "tools/publish.awk": "BEGIN { system(\"python -m gen\") }\n"}, a=NO_BUILD, tracked=False)
    assert hidden["deploy_layout"] == "unverified", hidden


def test_a_clean_text_verdict_names_the_deploy_layout(tmp_path, capsys):
    web = tmp_path / "web"
    with server(web) as root:
        pkg = make(tmp_path)
        publish(web, "", root, ROUTES)
        docaudit.main(["--path", str(pkg), "--package-only", "--site", root, "--ref", "main"])
        out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1].endswith("deploy layout unverified")


def test_the_marker_is_absent_from_a_run_with_no_site_stage(tmp_path, capsys):
    pkg = make(tmp_path)
    docaudit.main(["--path", str(pkg), "--package-only", "--format", "json"])
    report = json.loads(capsys.readouterr().out)
    assert "site" not in report.get("stages", {}) and "deploy layout" not in json.dumps(report)


# Codex executed review. Each sitemap `url` carries exactly one nonempty `loc`: a `url` with two cannot let an unrelated page stand in
# for an expected route, and a `url` with none or an empty one is not a page, so the sitemap is refused (incomplete), not guessed at.
def test_a_url_with_two_locs_cannot_satisfy_an_expected_route(tmp_path):
    def xml(root):
        pages = [f"<url><loc>{root}{p}</loc></url>" for p in ROUTES if p != "articles/a.html"]
        both = f"<url><loc>{root}index.html</loc><loc>{root}articles/a.html</loc></url>"
        return urlset(*pages, both)
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["state"] == "incomplete" and any("malformed sitemap entry" in x for x in r["reasons"]), r


@pytest.mark.parametrize("entry", ["<url></url>", "<url><loc></loc></url>", "<url><loc>   </loc></url>", "<url><lastmod>2026-01-01</lastmod></url>"])
def test_a_url_without_exactly_one_nonempty_loc_refuses_the_sitemap(tmp_path, entry):
    def xml(root):
        return urlset(*(f"<url><loc>{root}{p}</loc></url>" for p in ROUTES), entry)
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["state"] == "incomplete" and any("malformed sitemap entry" in x for x in r["reasons"]), (entry, r)


def test_a_url_with_one_loc_and_other_children_is_still_a_page(tmp_path):
    def xml(root):
        return urlset(*(f"<url><loc>{root}{p}</loc><lastmod>2026-01-01</lastmod></url>" for p in ROUTES + ["articles/a.html"]))
    r = raw_sitemap_audit(tmp_path, xml)
    assert r["state"] == "complete" and r["counts"]["missing"] == 0, r

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
    assert out.rstrip().splitlines()[-1] == "no findings; site content freshness unverified"
    assert report["stages"]["site"]["content_freshness"] == "unverified"


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
        pkg = make(tmp_path, config=CONFIG, files={".github/workflows/build.yaml": BUILD_WORKFLOW, ".github/actions/site/action.yml": SITE_ACTION,
                                                   ".github/workflows/deploy.yaml": plain_deploy})
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
        assert verifier.limit_run_is_unsupported_layout({"state": "incomplete", "reasons": [reason]}), reason

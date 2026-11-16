"""Pin the pure-Python mapper to pkgdown 2.2.1: `package_vignettes()`, `dev_mode_auto()` and `meta_development()`."""
import functools
import http.server
import subprocess
import threading

import pytest
import yaml

from lib import _docsite as site

# (path, front matter) pairs: default mapping, plus the divergences the SPEC pins.
ARTICLES = [
    ("a.Rmd", ""), ("b.rmd", ""), ("articles/c.Rmd", ""), ("articles/d.qmd", ""), ("nested/deep/e.qmd", ""), ("q.qmd", ""),
    ("tutorials/g.Rmd", ""), ("tutorials-old/h.Rmd", ""), ("articles/tutorials/f.Rmd", ""), ("tutorials.Rmd", ""),
    ("_priv/i.Rmd", ""), ("_x.Rmd", ""), ("n.md", ""), ("m.Rmarkdown", ""), ("U.RMD", ""), ("V.Qmd", ""),
    ("ext_html.Rmd", "pkgdown:\n  extension: html\n"), ("ext_pdf.Rmd", "pkgdown:\n  extension: pdf\n"),
    ("fmt_html.qmd", "format: html\n"), ("fmt_pdf.qmd", "format: pdf\n"),
]
REFUSED_PDF = {"vignettes/ext_pdf.Rmd", "vignettes/fmt_pdf.qmd"}
REFUSED_PDF_ROUTES = {"articles/ext_pdf.html", "articles/fmt_pdf.html"}  # `routes()` maps them; the audit refuses them


def test_package_vignettes_matches_the_mapper(tmp_path, r_json):
    pkg = tmp_path / "pkg"
    (pkg / "vignettes").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text("Package: fixture\nVersion: 0.0.1\nTitle: F\nDescription: F.\nLicense: MIT\n")
    for name, front in ARTICLES:
        file = pkg / "vignettes" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"---\ntitle: T\n{front}---\n\nbody\n")
    rows = r_json('o <- pkgdown:::package_vignettes(commandArgs(TRUE)[[1]]); as.list(setNames(o$file_out, o$file_in))', str(pkg))
    ours, reasons, counts = site.routes(["vignettes/" + n for n, _ in ARTICLES], {})
    assert not reasons
    # Everything pkgdown builds as html is exactly what the mapper expects (the PDF ones are refused later, in audit()).
    pkgdown_html = {k: v for k, v in rows.items() if v.endswith(".html")}
    assert {v: k for k, v in ours.items() if k not in REFUSED_PDF_ROUTES} == pkgdown_html
    # The output-extension divergences: pkgdown writes a PDF (never in the html-only sitemap); the audit refuses these.
    assert {k for k, v in rows.items() if v.endswith(".pdf")} == REFUSED_PDF
    assert not REFUSED_PDF & {k for k, v in pkgdown_html.items()}
    # pkgdown ignores .md/.Rmarkdown/.RMD/.Qmd and excludes ^tutorials directories and _-prefixed names.
    for ignored in ("n.md", "m.Rmarkdown", "U.RMD", "V.Qmd", "tutorials/g.Rmd", "tutorials-old/h.Rmd", "_x.Rmd"):
        assert "vignettes/" + ignored not in rows and "vignettes/" + ignored not in ours.values()
    assert counts["excluded"] == 3


@pytest.mark.parametrize("front,refused", [("", False), ("pkgdown:\n  extension: pdf\n", True)])
def test_audit_refuses_exactly_what_pkgdown_writes_outside_html(tmp_path, r_json, front, refused):
    """An article whose pkgdown output is not html is refused by the audit and never expected in the sitemap."""
    pkg = tmp_path / "pkg"
    (pkg / "vignettes").mkdir(parents=True)
    (pkg / "DESCRIPTION").write_text("Package: fixture\nVersion: 0.0.1\nTitle: F\nDescription: F.\nLicense: MIT\n")
    (pkg / "vignettes" / "p.Rmd").write_text(f"---\ntitle: T\n{front}---\n\nbody\n")
    out = r_json('o <- pkgdown:::package_vignettes(commandArgs(TRUE)[[1]]); o$file_out', str(pkg))
    for cmd in (["init", "-b", "main"], ["add", "-A"], ["-c", "user.email=a@b", "-c", "user.name=n", "commit", "-qm", "x"]):
        subprocess.run(["git", *cmd], cwd=pkg, check=True, capture_output=True)
    web = tmp_path / "web"; web.mkdir()
    (web / "sitemap.xml").write_text("<urlset/>")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = site.audit(pkg, url=f"http://127.0.0.1:{srv.server_port}/", ref="main")
    finally:
        srv.shutdown(); srv.server_close()
    assert out.endswith(".pdf") is refused
    missing = [f for f in r["findings"] if f["file"] == "vignettes/p.Rmd" and f["check"] == "site-missing-page"]
    if refused:
        assert r["state"] == "incomplete" and r["counts"]["unsupported"] == 1 and not missing
    else:
        assert len(missing) == 1


VERSIONS = ["1.2", "1.0.0", "1.0.8999", "1.0.9000", "1.0.9001", "0.0.0", "0.0.0.9000", "0.0.0.1", "1.2.3.4", "1.0.0-9000",
            "1.0-9000", "1.2-3-4", "0.0.0-1", "0.0.0.9000-1", "01.02.9000", "1.2.3.0", "1.0.9000.1.2",
            "1", "1.0.1234567890123", "", "abc", "1.2.x", "1..2", "1.2.", "1.2-", "-1", "1,2", "٠.٢.٣"]


def test_dev_mode_auto_table_matches_pkgdown(r_json):
    table = r_json('v <- commandArgs(TRUE); as.list(setNames(vapply(v, function(x) tryCatch(pkgdown:::dev_mode_auto(x), error = function(e) "ERROR", warning = function(w) "ERROR"), ""), v))', *[v or "<empty>" for v in VERSIONS])
    for version in VERSIONS:
        expected = table[version or "<empty>"] if version else "ERROR"
        if expected == "ERROR":
            with pytest.raises(ValueError):
                site.dev_mode_auto(version)
        else:
            assert site.dev_mode_auto(version) == expected, version


DEV_CONFIGS = [
    ("", "0.15.0"), ("development:\n  mode: release\n", "1.0.9000"), ("development:\n  mode: default\n", "1.0.9000"),
    ("development:\n  mode: devel\n", "1.0.0"), ("development:\n  mode: devel\n  destination: preview\n", "1.0.0"),
    ("development:\n  mode: unreleased\n", "1.0.0"), ("development:\n  mode: auto\n", "0.15.0"),
    ("development:\n  mode: auto\n", "0.15.0.9000"), ("development:\n  mode: auto\n", "0.0.0.9000"),
    ("development:\n  mode: auto\n  destination: next\n", "1.0.9000"), ("development:\n  mode: auto\n", "1.0-9000"),
    ("template:\n  bootstrap: 5\ndevelopment:\n  mode: devel\n", "1.0.0"),
    ("template:\n  bootstrap: 4\n", "1.0.0"), ("template:\n  bslib:\n    version: 5\n", "1.0.0"),
]


@pytest.mark.parametrize("config,version", DEV_CONFIGS)
def test_resolution_and_bootstrap_match_pkgdown(tmp_path, r_json, config, version):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "DESCRIPTION").write_text(f"Package: fixture\nVersion: {version}\nTitle: F\nDescription: F.\nLicense: MIT\n")
    (pkg / "_pkgdown.yml").write_text(config)
    got = r_json('p <- suppressWarnings(pkgdown:::as_pkgdown(commandArgs(TRUE)[[1]])); list(mode = p$development$mode, prefix = p$development$prefix, destination = p$development$destination, bs = p$bs_version)', str(pkg))
    parsed = yaml.safe_load(config) or {}
    ours = site.resolve_development(parsed, version)
    assert (ours["mode"], ours["prefix"], ours["destination"]) == (got["mode"], got["prefix"], got["destination"])
    assert site.bootstrap_version(parsed) == got["bs"]

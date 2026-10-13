import functools
import http.server
import subprocess
import threading
from contextlib import contextmanager

import pytest
from lib import _docsite as site
from .helpers import package


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@contextmanager
def server(root):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True); thread.start()
    try:
        yield f"http://127.0.0.1:{srv.server_port}/pkg/"
    finally:
        srv.shutdown(); srv.server_close(); thread.join()


def fixture(tmp_path):
    pkg = package(tmp_path / "source")
    (pkg / "man").mkdir(); (pkg / "man" / "internal.Rd").write_text("\\name{internal}\n")
    (pkg / "vignettes" / "pizza").mkdir(parents=True)
    (pkg / "vignettes" / "pizza" / "slice.Rmd").write_text("# article")
    git(pkg,"init","-b","main");git(pkg,"config","user.email","fixture@example.org");git(pkg,"config","user.name","Fixture")
    git(pkg,"add",".");git(pkg,"commit","-m","fixture")
    web = tmp_path / "web"; (web / "pkg").mkdir(parents=True)
    return pkg,web


def test_missing_extra_and_unreleased_severity(tmp_path):
    pkg,web=fixture(tmp_path)
    (pkg/"man"/"new.Rd").write_text("new")
    with server(web) as url:
        (web/"pkg"/"sitemap.xml").write_text(f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{url}articles/pizza/slice.html</loc></url><url><loc>{url}reference/old.html</loc></url></urlset>')
        report=site.audit(pkg,url=url,ref="main")
    assert report["state"]=="complete"
    assert {f["check"] for f in report["findings"]}=={"site-missing-page","site-extra-page","site-unreleased-page"}
    missing=next(f for f in report["findings"] if f["check"]=="site-missing-page")
    assert missing["severity"]=="warn" and missing["file"]=="man/internal.Rd"
    assert missing["message"] == url + "reference/internal.html absent from the sitemap"
    assert any("dirty" in f["message"] for f in report["findings"] if f["check"]=="site-unreleased-page")


@pytest.mark.parametrize("xml", ["<sitemapindex/>","not xml","<urlset><url><loc>https://foreign.org/other.html</loc></url></urlset>"])
def test_invalid_sitemap_never_missing_pages(tmp_path,xml):
    pkg,web=fixture(tmp_path)
    (web/"pkg"/"sitemap.xml").write_text(xml)
    with server(web) as url: report=site.audit(pkg,url=url,ref="main")
    assert report["state"]=="incomplete" and not report["findings"]


@pytest.mark.parametrize("url",["file:///etc/passwd","https://user:pass@example.org/","https://example.org/?q=1","https://example.org/#x"])
def test_url_rejects_unsafe_or_ambiguous_base(url):
    with pytest.raises(ValueError):site.base_url(url)


def test_routes_and_collisions():
    paths=["man/private.Rd","vignettes/a.Rmd","vignettes/articles/b.Rmd","vignettes/pizza/slice.Rmd","vignettes/_child.Rmd","vignettes/tutorials/t.Rmd"]
    routes,reasons,counts=site.routes(paths,{})
    assert set(routes)=={"reference/private.html","articles/a.html","articles/b.html","articles/pizza/slice.html"}
    assert counts["excluded"]==2 and not reasons
    _,reasons,_=site.routes(["vignettes/a.Rmd","vignettes/articles/a.Rmd"],{})
    assert reasons


def test_nested_package_immutable_routes(tmp_path):
    repo=tmp_path/'monorepo';repo.mkdir()
    pkg=package(repo/'packages'/'fixture')
    (pkg/'man').mkdir();(pkg/'man'/'private.Rd').write_text('private')
    (repo/'.github/workflows').mkdir(parents=True)
    (repo/'.github/workflows/site.yml').write_text('on:\n  push:\n    branches: [release]\njobs:\n  deploy:\n    steps:\n      - run: pkgdown::build_site()\n')
    git(repo,'init','-b','release');git(repo,'config','user.email','fixture@example.org');git(repo,'config','user.name','Fixture');git(repo,'add','.');git(repo,'commit','-m','fixture')
    web=tmp_path/'web';(web/'pkg').mkdir(parents=True)
    with server(web) as url:
        (web/'pkg'/'sitemap.xml').write_text('<urlset/>')
        report=site.audit(pkg,url=url)
    assert report['state']=='complete' and report['counts']['checked']==1
    assert report['provenance']['ref']=='release'
    assert [f['check'] for f in report['findings']]==['site-missing-page']
    assert report['findings'][0]['file']=='man/private.Rd'


@pytest.mark.parametrize('header',['output: custom::format','pkgdown:\n  as_is: true'])
def test_custom_article_frontmatter_not_invented(tmp_path,header):
    pkg,web=fixture(tmp_path)
    (pkg/'vignettes/pizza/slice.Rmd').write_text('---\n'+header+'\n---\n')
    git(pkg,'add','.');git(pkg,'commit','-m','custom output')
    (web/'pkg/sitemap.xml').write_text('<urlset/>')
    with server(web) as url:r=site.audit(pkg,url=url,ref='main')
    assert r['state']=='incomplete' and r['counts']['unsupported']==1
    assert not any(f['file']=='vignettes/pizza/slice.Rmd' and f['check']=='site-missing-page' for f in r['findings'])


@pytest.mark.parametrize('case', ['clean','missing','offline','unsupported'])
@pytest.mark.parametrize('threshold', ['none','warn','error'])
def test_site_cli_thresholds(tmp_path, capsys, case, threshold):
    import json
    from lib import docaudit
    pkg, web = fixture(tmp_path)
    if case == 'unsupported':
        (pkg/'vignettes'/'custom.qmd').write_text('# Unsupported source')
        git(pkg,'add','.'); git(pkg,'commit','-m','Quarto source')
    with server(web) as url:
        if case != 'offline':
            paths = ['articles/pizza/slice.html']
            if case != 'missing': paths.append('reference/internal.html')
            xml = '<urlset>'+''.join(f'<url><loc>{url}{p}</loc></url>' for p in paths)+'</urlset>'
            (web/'pkg'/'sitemap.xml').write_text(xml)
        code = docaudit.main(['--path',str(pkg),'--site',url,'--ref','main','--format','json','--fail-on',threshold])
    report = json.loads(capsys.readouterr().out)
    stage = report['stages']['site']
    expected = 0 if threshold=='none' or case=='clean' else 2 if case in ('offline','unsupported') else 1 if threshold=='warn' else 0
    assert code == expected
    assert stage['state'] == ('incomplete' if case in ('offline','unsupported') else 'complete')
    if case == 'missing':
        assert [f['check'] for f in stage['findings']] == ['site-missing-page']


def test_no_build_crawl_fetch_or_deploy(tmp_path, monkeypatch):
    pkg, web = fixture(tmp_path)
    calls = []
    original_run = subprocess.run
    def readonly_process(command, *args, **kwargs):
        calls.append(command)
        assert command[0] == 'git' and command[1] in ('rev-parse','show','ls-tree')
        return original_run(command, *args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', readonly_process)
    requests = []
    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            super().do_GET()
    handler = functools.partial(Handler, directory=str(web))
    srv = http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    thread = threading.Thread(target=srv.serve_forever,daemon=True); thread.start()
    try:
        url = f'http://127.0.0.1:{srv.server_port}/pkg/'
        (web/'pkg'/'sitemap.xml').write_text(f'<urlset><url><loc>{url}reference/internal.html</loc></url></urlset>')
        report = site.audit(pkg,url=url,ref='main')
    finally:
        srv.shutdown(); srv.server_close(); thread.join()
    assert report['state']=='complete' and calls
    assert requests == ['/pkg/sitemap.xml']


def test_selected_ref_config_requires_yaml_reader(tmp_path,monkeypatch):
    import builtins
    pkg,_=fixture(tmp_path)
    (pkg/'_pkgdown.yml').write_text('development:\n  mode: release\n')
    git(pkg,'add','.');git(pkg,'commit','-m','config')
    original=builtins.__import__
    def without_yaml(name,*a,**kw):
        if name=='yaml':raise ImportError('unavailable')
        return original(name,*a,**kw)
    monkeypatch.setattr(builtins,'__import__',without_yaml)
    monkeypatch.setattr(site,'sitemap',lambda *a:pytest.fail('missing config reader requested network'))
    r=site.audit(pkg,url='https://example.org/pkg/',ref='main')
    assert r['state']=='incomplete' and r['counts']['checked']==0 and not r['findings']
    assert any('YAML reader unavailable' in reason for reason in r['reasons'])
    assert r['provenance']['sha']==git(pkg,'rev-parse','HEAD')


@pytest.mark.parametrize('case',['quarto','extension','overlay'])
def test_unsupported_layout_retains_supported_routes(tmp_path,case):
    pkg,web=fixture(tmp_path)
    if case in ('quarto','extension'):
        (pkg/'vignettes'/('custom.qmd' if case=='quarto' else 'custom.Rmarkdown')).write_text('# unsupported')
    else:
        (pkg/'_pkgdown.yml').write_text('development:\n  mode: release\n')
        (pkg/'pkgdown').mkdir();(pkg/'pkgdown'/'extra.yml').write_text('template:\n  bootstrap: 5\n')
    git(pkg,'add','.');git(pkg,'commit','-m','unsupported layout')
    (web/'pkg'/'sitemap.xml').write_text('<urlset/>')
    with server(web) as url:r=site.audit(pkg,url=url,ref='main')
    assert r['state']=='incomplete' and r['counts']['checked']==2 and r['counts']['missing']==2
    assert {f['file'] for f in r['findings'] if f['check']=='site-missing-page'}=={'man/internal.Rd','vignettes/pizza/slice.Rmd'}
    assert any(('overlays' if case=='overlay' else 'unsupported article source') in reason for reason in r['reasons'])


@pytest.mark.parametrize('case',['destination','workflow-dev'])
def test_destination_and_workflow_mode_integration(tmp_path,monkeypatch,case):
    pkg,web=fixture(tmp_path)
    if case=='destination':
        (pkg/'_pkgdown.yml').write_text('destination: public-output\n')
        git(pkg,'add','.');git(pkg,'commit','-m','local destination')
        with server(web) as url:
            (web/'pkg'/'sitemap.xml').write_text('<urlset>'+''.join(f'<url><loc>{url}{p}</loc></url>' for p in ['reference/internal.html','articles/pizza/slice.html'])+'</urlset>')
            r=site.audit(pkg,url=url,ref='main')
        assert r['state']=='complete' and r['counts']['checked']==2 and r['counts']['missing']==0 and not r['findings']
    else:
        (pkg/'.github/workflows').mkdir(parents=True)
        (pkg/'.github/workflows/pkgdown.yml').write_text('env:\n  PKGDOWN_DEV_MODE: devel\n')
        monkeypatch.setattr(site,'sitemap',lambda *a:pytest.fail('development transform requested comparison'))
        r=site.audit(pkg,url='https://example.org/pkg/',ref='main')
        assert r['state']=='incomplete' and r['counts']['checked']==0 and not r['findings']
        assert any('PKGDOWN_DEV_MODE' in reason for reason in r['reasons'])

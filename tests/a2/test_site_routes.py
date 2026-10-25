import json
import subprocess
from lib import _docsite as site
from .test_examples_r import fixture


def test_pinned_pkgdown_article_routes(tmp_path):
    pkg=fixture(tmp_path,"# fixture")
    for name in ("foo.Rmd","articles/bar.Rmd","pizza/slice.Rmd"):
        file=pkg/"vignettes"/name;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text('---\ntitle: Fixture\noutput: html_document\n---\n\nA fixture.\n')
    for name in ('_child.Rmd','_private/nested.Rmd','tutorials/lesson.Rmd'):
        file=pkg/'vignettes'/name;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text('---\ntitle: Excluded\noutput: html_document\n---\n\nExcluded fixture.\n')
    code='args <- commandArgs(TRUE); stopifnot(as.character(packageVersion("pkgdown")) == "2.2.1"); pkgdown::build_articles(args[[1]], quiet=TRUE)'
    run=subprocess.run(["Rscript","--vanilla","-e",code,str(pkg)],capture_output=True,text=True,timeout=90)
    assert run.returncode==0,run.stderr
    assert not any((pkg/'docs'/route).exists() for route in ('articles/_child.html','articles/tutorials/lesson.html'))
    routes,reasons,counts=site.routes([p.relative_to(pkg).as_posix() for p in (pkg/'vignettes').rglob('*.Rmd')],{})
    assert counts['excluded']==2 and not reasons
    provenance={'engine':'pkgdown::build_articles','pkgdown':'2.2.1','source_sha256':{p.relative_to(pkg).as_posix():__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in (pkg/'vignettes').rglob('*.Rmd')},'actual_routes':sorted(p.relative_to(pkg/'docs').as_posix() for p in (pkg/'docs'/'articles').rglob('*.html'))}
    (tmp_path/'pkgdown-build-provenance.json').write_text(json.dumps(provenance))
    assert 'articles/_private/nested.html' in routes and 'articles/_private/nested.html' in provenance['actual_routes']
    assert set(routes)<=set(provenance['actual_routes']) and len(provenance['source_sha256'])==6
    assert all((pkg/"docs"/route).exists() for route in ("articles/foo.html","articles/bar.html","articles/pizza/slice.html"))


def test_rd_routes_keep_internal_topics():
    routes,reasons,counts=site.routes(['man/private.Rd','man/index.Rd','README.md'],{'reference':[{'contents':['private']}],'articles':[{'contents':['https://external.example/tutorial']}]})
    assert routes=={'reference/private.html':'man/private.Rd','reference/index.html':'man/index.Rd'} and not reasons


import pytest
@pytest.mark.parametrize('config,supported',[
 ({},True),({'development':{'mode':'release'}},True),
 ({'template':{'bootstrap':5,'bootswatch':'litera','bslib':{'base_font':'Roboto'}}},True),
 ({'development':{'mode':'devel'}},False),({'development':{'destination':'dev'}},False),
 ({'template':{'path':'custom'}},False),({'as_is':True},False),({'build':{'extra_packages':['pkg']}},False),
])
def test_release_mode_and_destination(config,supported):
    routes,reasons,counts=site.routes(['man/private.Rd'],config)
    assert bool(reasons)!=supported and routes=={'reference/private.html':'man/private.Rd'}

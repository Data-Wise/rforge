import pytest
from lib import _docsite as site
from .test_site_integration import fixture,git


def test_explicit_ref_immutable_tree(tmp_path):
    pkg,_=fixture(tmp_path)
    sha=git(pkg,"rev-parse","HEAD")
    assert site.select_ref(pkg,"main")["sha"]==sha
    (pkg/"man/internal.Rd").write_text("dirty")
    assert site.select_ref(pkg,"main")["sha"]==sha


def workflow(pkg,body):
    folder=pkg/".github/workflows";folder.mkdir(parents=True)
    (folder/"pkgdown.yaml").write_text(body)


def test_workflow_inference_and_fallback(tmp_path):
    pkg,_=fixture(tmp_path)
    assert site.select_ref(pkg,None)["selection"]=="fallback assumption"
    workflow(pkg,"on:\n  push:\n    branches: [main]\njobs:\n  build:\n    steps:\n      - run: Rscript -e 'pkgdown::build_site()'\n")
    assert site.select_ref(pkg,None)["selection"]=="literal workflow branch"


@pytest.mark.parametrize("branches",["[main, dev]","['*']","['${{ github.ref }}']"])
def test_unsupported_workflows_require_ref(tmp_path,branches):
    pkg,_=fixture(tmp_path)
    workflow(pkg,"on:\n  push:\n    branches: "+branches+"\njobs:\n  build:\n    steps:\n      - run: pkgdown::build_site()\n")
    with pytest.raises(ValueError):site.select_ref(pkg,None)
    assert site.select_ref(pkg,"main")["ref"]=="main"


def test_missing_yaml_reader_requires_explicit_ref(tmp_path, monkeypatch):
    import builtins
    pkg, _ = fixture(tmp_path)
    workflow(pkg, "on:\n  push:\n    branches: [main]\njobs:\n  build:\n    steps:\n      - run: pkgdown::build_site()\n")
    real_import = builtins.__import__
    def without_yaml(name, *args, **kwargs):
        if name == 'yaml':
            raise ImportError('deliberately unavailable')
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', without_yaml)
    with pytest.raises(ValueError, match='YAML reader unavailable'):
        site.select_ref(pkg, None)
    assert site.select_ref(pkg, 'main')['selection'] == 'explicit local ref'

@pytest.mark.parametrize('inferred',[False,True])
def test_remote_tracking_ref_preferred(tmp_path,inferred):
    pkg,_=fixture(tmp_path);remote=git(pkg,'rev-parse','HEAD')
    git(pkg,'update-ref','refs/remotes/origin/main',remote)
    (pkg/'README.md').write_text('local branch moved');git(pkg,'add','.');git(pkg,'commit','-m','local only')
    if inferred:workflow(pkg,"on:\n  push:\n    branches: [main]\njobs:\n  build:\n    steps:\n      - run: pkgdown::build_site()\n")
    r=site.select_ref(pkg,None)
    assert r['ref']=='origin/main' and r['sha']==remote
    assert r['sha']!=git(pkg,'rev-parse','HEAD')
    assert r['selection']==('literal workflow branch' if inferred else 'fallback assumption')


@pytest.mark.parametrize('case',['checkout','reusable','multiple','missing-ref','missing-git'])
def test_unsupported_source_selection_no_network(tmp_path,monkeypatch,case):
    pkg,_=fixture(tmp_path)
    base="on:\n  push:\n    branches: [main]\njobs:\n  build:\n"
    if case=='checkout':workflow(pkg,base+"    steps:\n      - uses: actions/checkout@v4\n        with:\n          ref: dev\n      - run: pkgdown::build_site()\n")
    elif case=='reusable':workflow(pkg,base+"    uses: owner/pkgdown/.github/workflows/build.yml@main\n")
    elif case=='multiple':
        workflow(pkg,base+"    steps:\n      - run: pkgdown::build_site()\n")
        (pkg/'.github/workflows/second.yml').write_text((pkg/'.github/workflows/pkgdown.yaml').read_text())
    elif case=='missing-ref':git(pkg,'branch','-m','other')
    else:monkeypatch.setattr(site,'git',lambda *a:(_ for _ in ()).throw(ValueError('git unavailable')))
    monkeypatch.setattr(site,'sitemap',lambda *a:pytest.fail('source failure requested network'))
    r=site.audit(pkg,url='https://example.org/pkg/')
    assert r['state']=='incomplete' and r['counts']['checked']==0 and not r['findings'] and r['reasons']

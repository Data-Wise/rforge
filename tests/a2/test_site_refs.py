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

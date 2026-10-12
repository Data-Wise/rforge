import json
import pytest
from lib import docaudit
from .helpers import package


def test_a1_default_unchanged(tmp_path, monkeypatch):
    pkg = package(tmp_path)
    before = docaudit.audit(pkg)
    monkeypatch.setattr(docaudit, "_optional_stages", lambda *a, **k: pytest.fail("optional stage ran"))
    assert docaudit.audit(pkg) == before
    assert "stages" not in before


@pytest.mark.parametrize("args", [["--ref", "main"], ["--examples-budget-seconds", "1"], ["--run-examples", "--examples-budget-seconds", "0"], ["--run-examples", "--examples-budget-seconds", "1.5"]])
def test_cli_scope_validation(args):
    with pytest.raises(SystemExit) as e:
        docaudit.main(args)
    assert e.value.code == 2


def test_stage_state_preserves_static_findings(tmp_path, monkeypatch):
    pkg = package(tmp_path)
    monkeypatch.setattr(docaudit, "_optional_stages", lambda *a, **k: {"examples": {"state":"unavailable", "counts":{"checked":0}, "reasons":["missing R"], "engine_missing":["Rscript"], "findings":[]}})
    report = docaudit.audit(pkg, run_examples=True)
    assert report["incomplete"]
    assert report["stages"]["examples"]["counts"]["checked"] == 0
    assert report["engine_missing"] == ["Rscript"]


@pytest.mark.parametrize("threshold, incomplete, severity, expected", [("none",True,"warn",0),("warn",True,"warn",2),("error",True,"warn",2),("warn",False,"warn",1),("error",False,"warn",0),("error",False,"error",1),("warn",False,"none",0)])
def test_threshold_matrix(threshold, incomplete, severity, expected):
    assert docaudit.exit_code({"audited":True,"incomplete":incomplete,"max_severity":severity}, threshold) == expected


def test_text_json_diagnostics(tmp_path, monkeypatch, capsys):
    pkg = package(tmp_path)
    monkeypatch.setattr(docaudit, "_optional_stages", lambda *a, **k: {"examples": {"state":"incomplete", "counts":{"unverified":2}, "reasons":["rendered-unpaired"], "engine_missing":[], "findings":[]}})
    assert docaudit.main(["--path",str(pkg),"--run-examples","--format","json"]) == 0
    out = capsys.readouterr()
    assert json.loads(out.out)["stages"]["examples"]["counts"]["unverified"] == 2
    assert "incomplete" in out.err
    text = docaudit.format_text(docaudit.audit(pkg, run_examples=True))
    assert text.splitlines()[0].startswith("scope:")
    assert "rendered-unpaired" in text and "INCOMPLETE" in text and "no findings" not in text


def test_engine_union_and_package_reasons(tmp_path, monkeypatch):
    package(tmp_path/"a",name="a");package(tmp_path/"b",name="b")
    monkeypatch.setattr(docaudit, "_optional_stages", lambda p, **k: {"examples":{"state":"unavailable","counts":{},"reasons":[p.name],"engine_missing":[p.name,"Rscript"],"findings":[]}})
    r = docaudit.audit(tmp_path, eco=True,run_examples=True)
    assert r["engine_missing"] == ["Rscript","a","b"]
    assert all(p["stages"]["examples"]["reasons"] == [p["name"]] for p in r["packages"])


def test_allowlist_preserves_incomplete(tmp_path,monkeypatch):
    pkg=package(tmp_path)
    (pkg/'.rforge.yaml').write_text('docs:\n  allowlist:\n    - README.md\n')
    finding={'check':'examples-shape','severity':'warn','file':'README.md','line':1,'message':'uncertain'}
    extra={'check':'site-extra-page','severity':'info','file':'','line':1,'message':'extra URL'}
    monkeypatch.setattr(docaudit,'_optional_stages',lambda *a,**k:{'examples':{'state':'incomplete','counts':{'unverified':1},'reasons':['unverified'],'engine_missing':[],'findings':[finding,extra]}})
    r=docaudit.audit(pkg,run_examples=True,detailed=True)
    assert r['incomplete'] and r['stages']['examples']['counts']['unverified']==1
    assert docaudit.exit_code(r,'error')==2
    assert not any(f['check']=='examples-shape' for f in r['findings'])
    assert any(f['check']=='site-extra-page' for f in r['findings'])


@pytest.mark.parametrize('detailed',[False,True])
def test_detailed_info_visibility_does_not_change_coverage(tmp_path,monkeypatch,detailed):
    pkg=package(tmp_path)
    info={'check':'examples-stochastic','severity':'info','file':'README.md','line':1,'message':'uncertain'}
    monkeypatch.setattr(docaudit,'_optional_stages',lambda *a,**k:{'examples':{'state':'incomplete','counts':{'unverified':1},'reasons':['uncertain'],'engine_missing':[],'findings':[info]}})
    r=docaudit.audit(pkg,run_examples=True,detailed=detailed)
    assert r['incomplete'] and r['stages']['examples']['counts']['unverified']==1
    assert bool(r['stages']['examples']['findings'])==detailed
    assert bool([f for f in r['findings'] if f['check']=='examples-stochastic'])==detailed

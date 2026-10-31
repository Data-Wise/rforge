from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[2]/"scripts/verify_a2_release.py"
spec=importlib.util.spec_from_file_location("a2_verifier",path)
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


def records():
    manifest={"status":"ready","groups":[{"id":"fixture","status":"ready","nodes":["test[x]","test[y]"]}]}
    evidence={"candidate_sha":"sha","lock_hash":"lock","manifest_hash":"manifest","run_id":"run","collection_run_id":"run","python":"3.12.15","collected":["test[x]","test[y]"],"outcomes":{"test[x]":"passed","test[y]":"passed"},"reported_r_checked":1,"reported_http_checked":1,"fixture_executions":[{"engine":"R","expected_assertion_ids":["a"],"observed_assertion_ids":["a"],"sentinel":"real-R","expected_findings":[],"actual_findings":[]},{"engine":"HTTP","expected_routes":["route"],"observed_routes":["route"],"sentinel":"server-request","expected_findings":[],"actual_findings":[]}]}
    return manifest,evidence


@pytest.mark.parametrize("outcome",[None,"skipped","xfailed","xpassed","failed","deselected"])
def test_required_outcomes_no_vacuous_pass(outcome):
    m,e=records();e["outcomes"]["test[y]"]=outcome
    with pytest.raises(v.VerificationError):v.validate_run(m,e,candidate_sha="sha",lock_hash="lock",manifest_hash="manifest")


def test_expected_findings_exactness():
    m,e=records();e["fixture_executions"][0]["actual_findings"]=[{"check":"unexpected"}]
    with pytest.raises(v.VerificationError):v.validate_run(m,e,candidate_sha="sha",lock_hash="lock",manifest_hash="manifest")


@pytest.mark.parametrize("field",["candidate_sha","lock_hash","manifest_hash","collection_run_id","reported_r_checked"])
def test_evidence_identity_and_versions(field):
    m,e=records();e[field]="wrong"
    with pytest.raises(v.VerificationError):v.validate_run(m,e,candidate_sha="sha",lock_hash="lock",manifest_hash="manifest")


def test_manifest_mapping_and_collection():
    m,e=records()
    assert v.validate_run(m,e,candidate_sha="sha",lock_hash="lock",manifest_hash="manifest")["verified"]
    m["status"]="pending"
    with pytest.raises(v.VerificationError):v.validate_run(m,e,candidate_sha="sha",lock_hash="lock",manifest_hash="manifest")


@pytest.mark.parametrize('python,accepted', [('3.15.0',True),('3.16.1',True),('3.12.15',True),('3.9.9',False),('3.16.0rc1',False),('3.16.0a1',False),('latest',False),(None,False)])
def test_stable_python_evidence(python,accepted):
    m,e=records();e['python']=python
    if accepted:
        assert v.validate_run(m,e,candidate_sha='sha',lock_hash='lock',manifest_hash='manifest')['verified']
    else:
        with pytest.raises(v.VerificationError,match='Stable Python'):
            v.validate_run(m,e,candidate_sha='sha',lock_hash='lock',manifest_hash='manifest')


def test_removed_normative_paragraph_or_table_row_rejected():
    source='## Contract\n\nMust supervise.\n\n| Case | Obligation |\n|---|---|\n| Native | Must terminate |\n'
    obligations=v.spec_obligations(source)
    ledger={'review':'complete','requirements':[{**r,'review':'complete','inventory_ids':['fixture']} for r in obligations]}
    manifest={'groups':[{'id':'fixture'}]}
    v.validate_requirements(ledger,manifest,source)
    for index in range(len(obligations)):
        bad=deepcopy(ledger);del bad['requirements'][index]
        with pytest.raises(v.VerificationError):v.validate_requirements(bad,manifest,source)


def test_developer_and_release_modes(monkeypatch):
    from tests.a2 import conftest
    import pytest
    monkeypatch.setattr(conftest,'runtime',lambda:None)
    class Config:
        def __init__(self,release):self.release=release
        def getoption(self,name):return self.release
    class Item:
        originalname='test_working_tree_load_identity'
        def __init__(self):self.markers=[]
        def add_marker(self,marker):self.markers.append(marker)
    item=Item()
    conftest.pytest_collection_modifyitems(Config(False),[item])
    assert item.markers and item.markers[0].name=='skip'
    with pytest.raises(pytest.UsageError,match='exact fixture-lock'):
        conftest.pytest_collection_modifyitems(Config(True),[Item()])


def test_removed_inventory_group_even_with_rewritten_ledger():
    source='## Contract\n\nMust verify all scope.\n'
    obligations=v.spec_obligations(source)
    ledger={'review':'complete','requirements':[{**r,'review':'complete','inventory_ids':['C01','C02']} for r in obligations]}
    manifest={'groups':[{'id':'C01'},{'id':'C02'}]}
    inventory='| C01 / T02 | first |\n| C02 / T02 | second |\n'
    v.validate_requirements(ledger,manifest,source,inventory)
    manifest['groups'].pop()
    for r in ledger['requirements']:r['inventory_ids']=['C01']
    with pytest.raises(v.VerificationError,match='inventory group'):v.validate_requirements(ledger,manifest,source,inventory)


@pytest.mark.parametrize('defect',['none','R','packages','platform','source-hash','expected-hash','missing-fixture','duplicate-fixture'])
def test_main_runtime_platform_fixture_binding(tmp_path,capsys,defect):
    import json,hashlib
    m,e=records();m['groups'][0]['id']='F01'
    source='## Contract\n\nVerify fixtures.\n'
    sha=hashlib.sha256(source.encode()).hexdigest();m['spec_sha256']=sha
    ledger={'review':'complete','spec_sha256':sha,'requirements':[{**r,'review':'complete','inventory_ids':['F01']} for r in v.spec_obligations(source)]}
    expected={'status':'ready','fixtures':{}}
    for index,execution in enumerate(e['fixture_executions']):
        execution.update(fixture=str(index),source_hash='0'*64)
        expected['fixtures'][str(index)]={'findings':[], 'assertion_ids':execution.get('observed_assertion_ids',[]),'routes':execution.get('observed_routes',[])}
    lock={'platforms':['macos-15','ubuntu-24.04'],'R':'4.6.1','R_packages':{'evaluate':'1.0.5'}}
    e.update(R=lock['R'],R_packages=lock['R_packages'],platform='macos-15')
    files={'manifest':m,'requirements':ledger,'expected':expected,'lock':lock}
    for name,data in files.items():(tmp_path/name).write_text(json.dumps(data))
    (tmp_path/'spec').write_text(source);(tmp_path/'inventory').write_text('| F01 / T23 | required |\n')
    e.update(lock_hash=v.digest(tmp_path/'lock'),manifest_hash=v.digest(tmp_path/'manifest'),expected_findings_hash=v.digest(tmp_path/'expected'))
    if defect=='R':e['R']='wrong'
    elif defect=='packages':e['R_packages']={}
    elif defect=='platform':e['platform']='windows'
    elif defect=='source-hash':e['fixture_executions'][0]['source_hash']='bad'
    elif defect=='expected-hash':e['expected_findings_hash']='wrong'
    elif defect=='missing-fixture':e['fixture_executions'].pop()
    elif defect=='duplicate-fixture':e['fixture_executions'].append(deepcopy(e['fixture_executions'][0]))
    (tmp_path/'evidence').write_text(json.dumps(e))
    args=[argument for name in (*files,'spec','inventory','evidence') for argument in ('--'+name,str(tmp_path/name))]+['--candidate-sha','sha']
    assert v.main(args)==(0 if defect=='none' else 2)
    assert json.loads(capsys.readouterr().out)['verified']==(defect=='none')

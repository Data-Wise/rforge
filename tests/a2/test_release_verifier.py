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

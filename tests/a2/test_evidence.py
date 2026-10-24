import pytest
from .test_release_ci import records
from .test_release_verifier import v


@pytest.mark.parametrize('name',['live_smoke','package_triage'])
@pytest.mark.parametrize('status',['failed','incomplete','unavailable','pending'])
def test_live_site_smoke_evidence(name,status,tmp_path):
    from .test_final_gates import evidence_records
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    observations[name]['status']=status
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)


def test_package_coverage_triage(tmp_path):
    from .test_final_gates import evidence_records
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    assert v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)['verified']
    observations['package_triage']['provenance']=''
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)


def test_committed_defect_replay():
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    root=Path(__file__).resolve().parents[2]
    environment=dict(os.environ, PYTHONPATH=str(root))
    run=subprocess.run([sys.executable,str(root/'scripts/a2_fixture_oracles.py')],cwd=root,env=environment,capture_output=True,text=True,check=True,timeout=45)
    evidence=json.loads(run.stdout)
    assert evidence['reported_r_checked']==2 and evidence['reported_http_checked']==4
    fixtures={record['fixture']:record for record in evidence['fixture_executions']}
    assert set(fixtures)=={'examples-clean','examples-planted','site-clean','site-planted'}
    for clean in ('examples-clean','site-clean'):
        assert fixtures[clean]['actual_findings']==[]
    assert fixtures['examples-planted']['actual_findings']==[{'check':'examples-output','severity':'warn','file':'README.md','assertion_id':'README.md:4'}]
    assert fixtures['site-planted']['actual_findings']==[{'check':'site-missing-page','severity':'warn','file':'man/private.Rd'}]
    assert all(record['sentinel'] and len(record['source_hash'])==64 for record in fixtures.values())


def _a2_manifest_rows():
    import json
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'fixtures/docaudit/defects.json'
    return [r for r in json.loads(path.read_text())['defects'] if r.get('release')=='A2']


def test_a2_replay_rows_are_accounted():
    """Every A2-owned defect row is either replayable from a real ref or pending with an honest substitute."""
    rows=_a2_manifest_rows()
    assert {r['id'] for r in rows}=={'readme-nie-output','site-missing-models-page'}
    for row in rows:
        if row['ref'] is not None:
            assert row['status']=='firm' and row['fix'], row['id']
        else:
            sub=row['substitute']
            assert sub['history']=='pending' and sub['kind']=='synthetic' and sub['provenance_backed'] is False, row['id']
            assert 'does not claim to reproduce' in sub['note']


def test_a2_recall_without_history_is_pending_not_green_or_failed():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'harness'))
    import replay
    import json
    manifest=json.loads((Path(__file__).resolve().parents[1]/'fixtures/docaudit/defects.json').read_text())
    summary=replay.run_recall(manifest,'a2',overrides={'medfit':'/nonexistent'},allow_unavailable=True)
    outcomes={row['id']:row['outcome'] for row in summary['rows']}
    assert outcomes=={'readme-nie-output':replay.UNAVAILABLE,'site-missing-models-page':replay.UNAVAILABLE}
    assert summary['ok'] and summary['firm_caught']==0 and summary['conditional_caught']==0


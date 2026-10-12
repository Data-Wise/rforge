import pytest
from .test_release_ci import records
from .test_release_verifier import v


@pytest.mark.parametrize('name',['live_smoke','package_triage'])
@pytest.mark.parametrize('status',['failed','incomplete','unavailable','pending'])
def test_live_site_smoke_evidence(name,status):
    platforms,observations=records();observations[name]['status']=status
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha')


def test_package_coverage_triage():
    platforms,observations=records()
    assert v.validate_aggregate(platforms,observations,candidate_sha='sha')['verified']
    observations['package_triage']['provenance']=''
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha')


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

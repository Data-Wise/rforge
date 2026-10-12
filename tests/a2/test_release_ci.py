from copy import deepcopy
from pathlib import Path
import pytest
from .test_release_verifier import v


def records():
    platforms=[{'platform':p,'candidate_sha':'sha','uploaded':True,'retrieved':True,'verified':True} for p in ('ubuntu-24.04','macos-14')]
    observations={name:{'candidate_sha':'sha','status':'passed','provenance':'actual completed observation'} for name in ('live_smoke','package_triage','full_gates','rendered_review','adversarial_review','requirement_mapping')}
    return platforms,observations


@pytest.mark.parametrize('defect',['missing','upload-failed','stale','unretrieved','unverified','duplicate'])
def test_artifact_failure_blocks_acceptance(defect):
    platforms,observations=records()
    if defect=='missing':platforms.pop()
    elif defect=='duplicate':platforms.append(deepcopy(platforms[0]))
    elif defect=='stale':platforms[0]['candidate_sha']='old'
    else:platforms[0][{'upload-failed':'uploaded','unretrieved':'retrieved','unverified':'verified'}[defect]]=False
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha')


def test_both_platforms_locked_runtime():
    root=Path(__file__).resolve().parents[2]
    import yaml,json
    workflow=yaml.safe_load((root/'.github/workflows/a2-release.yml').read_text())
    lock=json.loads((root/'tests/a2/fixture-lock.json').read_text())
    assert workflow['jobs']['a2-release']['strategy']['matrix']['os']==lock['platforms']
    steps=workflow['jobs']['a2-release']['steps']
    assert next(s for s in steps if s.get('uses','').startswith('actions/setup-python'))['with']['python-version']==lock['python']
    assert next(s for s in steps if s.get('uses','').startswith('r-lib/actions/setup-r'))['with']['r-version']=='${{ steps.lock.outputs.R }}'
    assert any('scripts/run_a2_release.py' in s.get('run','') for s in steps)
    assert workflow['jobs']['aggregate']['needs']=='a2-release'


def test_unsupported_platform_diagnostic(tmp_path,monkeypatch):
    import time
    from lib import _docexamples as examples
    from .helpers import package
    p=package(tmp_path,'```r\nprint(1)\n#> [1] 1\n```')
    monkeypatch.setattr(examples,'sys_platform_unavailable',lambda:True)
    r=examples.audit(p,deadline=time.monotonic_ns()+1000000000)
    assert r['state']=='unavailable' and r['counts']['blocked']==1 and 'Windows' in r['reasons'][-1]


def test_candidate_observations_do_not_require_self_referential_commit():
    import yaml
    root=Path(__file__).resolve().parents[2]
    workflow=yaml.safe_load((root/'.github/workflows/a2-release.yml').read_text())
    trigger=workflow.get('on',workflow.get(True))
    assert 'acceptance-observations' in trigger['workflow_dispatch']['inputs']
    steps=workflow['jobs']['aggregate']['steps']
    step=next(s for s in steps if s.get('env',{}).get('A2_OBSERVATIONS'))
    assert 'json.loads' in step['run'] and '${{' not in step['run']
    verification=steps[-1]['run']
    assert 'a2-acceptance-observations.json' in verification and 'tests/a2/evidence/acceptance.json' not in verification

import pytest
from .test_release_ci import records
from .test_release_verifier import v


@pytest.mark.parametrize('name',['full_gates','rendered_review','adversarial_review','requirement_mapping'])
@pytest.mark.parametrize('defect',['missing','failed','stale','no-provenance'])
def test_gate_record_validation(name,defect,tmp_path):
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    if defect=='missing':observations.pop(name)
    elif defect=='failed':observations[name]['status']='failed'
    elif defect=='stale':observations[name]['candidate_sha']='old'
    else:observations[name]['provenance']=''
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)


def test_review_record_validation(tmp_path):
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    assert v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)['verified']
    observations['adversarial_review']['status']='findings-unresolved'
    with pytest.raises(v.VerificationError):v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)


def triage_facts():
    """A valid per-package triage record set (partial README scope, one triaged finding)."""
    def package(name):
        return {'package':name,'commit':'a'*40,'source_sha256':{'README.md':'b'*64},'state':'incomplete','scope':'partial',
                'counts':{'discovered':6,'eligible':4,'checked':2,'excluded':0,'unverified':4,'blocked':0},
                'reasons':['assertions outside supported R fences'],
                'findings':[{'check':'examples-shape','severity':'warn','file':'README.md','assertion_id':'README.md:85',
                             'triage':{'class':'true-positive','rationale':'documented output shape differs from the real result'}}],
                'reviewed':True,'disposition':'reviewed; partial scope recorded as incomplete'}
    return {'packages':{name:package(name) for name in ('medfit','probmed','medrobust')}}


def evidence_records(observations, root):
    import json
    facts = {
        'live_smoke': {'url':'https://example.org/pkg/','source_ref':'abc','requests':1,'checked':2},
        'package_triage': triage_facts(),
        'full_gates': {'pytest_passed':1151,'test_all_passed':47,'version_sync':True,'reference_sync':True,'command_sync':True,'mkdocs_strict':True},
        'rendered_review': {'pages':[{'inspected':True,'sha256':'a'*64}]},
        'adversarial_review': {'job_id':'review-job','unresolved_findings':0,'coverage_reviewed':True},
        'requirement_mapping': {'review':'complete','unmapped':0,'requirements':118},
    }
    for name,item in observations.items():
        path=root/(name+'.json')
        path.write_text(json.dumps({'candidate_sha':'sha','kind':name,'status':'passed','producer_run_id':'123','facts':facts[name]}))
        item['provenance']={'path':path.name,'sha256':v.digest(path),'run_id':'123'}


@pytest.mark.parametrize('defect',['bare-claim','missing-file','wrong-hash','escaping-path','wrong-candidate','wrong-producer','empty-facts','unresolved-review'])
def test_observation_artifact_validation(tmp_path,defect):
    import json
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    item=observations['adversarial_review']; path=tmp_path/item['provenance']['path']
    if defect=='bare-claim':item['provenance']='passed'
    elif defect=='missing-file':path.unlink()
    elif defect=='wrong-hash':item['provenance']['sha256']='0'*64
    elif defect=='escaping-path':item['provenance']['path']='../outside.json'
    else:
        record=json.loads(path.read_text())
        if defect=='wrong-candidate':record['candidate_sha']='old'
        elif defect=='wrong-producer':record['producer_run_id']='456'
        elif defect=='empty-facts':record['facts']={}
        else:record['facts']['unresolved_findings']=1
        path.write_text(json.dumps(record));item['provenance']['sha256']=v.digest(path)
    with pytest.raises(v.VerificationError):
        v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)

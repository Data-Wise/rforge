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


GATE_COMMANDS=('pytest','test-all','version-sync','reference-sync','command-sync','mkdocs-strict')


def gate_facts():
    """A valid full-gate record: every required gate ran in the candidate tree and left a hashed log."""
    return {'source_commit':'sha','tree_clean':True,'pytest_passed':1460,'pytest_failed':0,'test_all_passed':47,'test_all_failed':0,
            'version_sync':True,'reference_sync':True,'command_sync':True,'mkdocs_strict':True,
            'commands':[{'name':n,'command':'run '+n,'exit_code':0,'log_sha256':'c'*64} for n in GATE_COMMANDS]}


def review_facts():
    """A valid finalized review record: executed (not static), candidate-bound, every finding dispositioned."""
    return {'job_id':'review-job','reviewed_commit':'sha','mode':'executed','executed_tests':120,'coverage_reviewed':True,
            'unresolved_findings':0,
            'findings':[{'id':'F1','disposition':'fixed','evidence':'commit cb05e02 plus failing-first test'},
                        {'id':'F2','disposition':'rejected','evidence':'premise contradicted by lib/_docexamples.py:210'}]}


def evidence_records(observations, root):
    import json
    facts = {
        'live_smoke': {'url':'https://example.org/pkg/','source_ref':'abc','requests':1,'checked':2},
        'package_triage': triage_facts(),
        'full_gates': gate_facts(),
        'rendered_review': {'pages':[{'inspected':True,'sha256':'a'*64}]},
        'adversarial_review': review_facts(),
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


def _tamper(tmp_path,name,mutate):
    import json
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    item=observations[name]; path=tmp_path/item['provenance']['path']
    record=json.loads(path.read_text()); mutate(record['facts'])
    path.write_text(json.dumps(record)); item['provenance']['sha256']=v.digest(path)
    with pytest.raises(v.VerificationError):
        v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)


GATE_DEFECTS={
    'wrong-source-commit':lambda f:f.update(source_commit='old'),
    'dirty-tree':lambda f:f.update(tree_clean=False),
    'pytest-failures':lambda f:f.update(pytest_failed=1),
    'test-all-failures':lambda f:f.update(test_all_failed=2),
    'missing-command':lambda f:f.update(commands=f['commands'][1:]),
    'nonzero-exit':lambda f:f['commands'][0].update(exit_code=1),
    'missing-log-hash':lambda f:f['commands'][2].pop('log_sha256'),
    'bad-log-hash':lambda f:f['commands'][2].update(log_sha256='xyz'),
    'duplicate-command':lambda f:f['commands'].append(dict(f['commands'][0])),
    'unknown-command':lambda f:f['commands'].append({'name':'extra','command':'x','exit_code':0,'log_sha256':'c'*64}),
    'flag-without-command':lambda f:f.pop('commands'),
}


@pytest.mark.parametrize('defect',sorted(GATE_DEFECTS))
def test_full_gate_record_rejects(tmp_path,defect):
    _tamper(tmp_path,'full_gates',GATE_DEFECTS[defect])


REVIEW_DEFECTS={
    'static-review':lambda f:f.update(mode='static'),
    'no-executed-tests':lambda f:f.update(executed_tests=0),
    'wrong-reviewed-commit':lambda f:f.update(reviewed_commit='old'),
    'finding-without-disposition':lambda f:f['findings'][0].pop('disposition'),
    'deferred-finding':lambda f:f['findings'][0].update(disposition='deferred'),
    'finding-without-evidence':lambda f:f['findings'][1].update(evidence=''),
    'count-disagrees':lambda f:f.update(unresolved_findings=1),
    'duplicate-finding-id':lambda f:f['findings'][1].update(id='F1'),
    'coverage-unreviewed':lambda f:f.update(coverage_reviewed=False),
}


@pytest.mark.parametrize('defect',sorted(REVIEW_DEFECTS))
def test_finalized_review_record_rejects(tmp_path,defect):
    _tamper(tmp_path,'adversarial_review',REVIEW_DEFECTS[defect])


def test_review_with_no_findings_is_accepted_only_when_executed(tmp_path):
    import json
    platforms,observations=records()
    evidence_records(observations,tmp_path)
    path=tmp_path/observations['adversarial_review']['provenance']['path']
    record=json.loads(path.read_text()); record['facts']['findings']=[]
    path.write_text(json.dumps(record)); observations['adversarial_review']['provenance']['sha256']=v.digest(path)
    assert v.validate_aggregate(platforms,observations,candidate_sha='sha',evidence_root=tmp_path)['verified']


def _gates():
    import importlib.util, pathlib
    spec=importlib.util.spec_from_file_location('gate_record',pathlib.Path(__file__).resolve().parents[2]/'scripts/a2_gate_record.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def _fake_runner(failing=()):
    def run(command,cwd):
        text=' '.join(command)
        if 'pytest' in text: return (1 if 'pytest' in failing else 0),'1460 passed, 5 skipped in 160s\n'
        if 'test-all' in text: return 0,'Total: 47  |  Passed: 47  |  Failed: 0\n'
        name=next(n for n in ('version_sync','gen_lib_reference','_check_commands_doc','mkdocs') if n in text)
        return (1 if name in failing else 0),name+' output\n'
    return run


def test_gate_producer_record_is_accepted_by_the_validator(tmp_path):
    import subprocess
    mod=_gates()
    facts=mod.produce(runner=_fake_runner())
    commit=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    facts['source_commit']=commit; facts['tree_clean']=True
    assert facts['pytest_passed']==1460 and facts['test_all_passed']==47 and facts['test_all_failed']==0
    v.validate_full_gates(facts,commit)


def test_gate_producer_records_failures_and_the_validator_rejects_them():
    mod=_gates()
    facts=mod.produce(runner=_fake_runner(failing=('mkdocs',)))
    assert facts['mkdocs_strict'] is False
    with pytest.raises(v.VerificationError): v.validate_full_gates(facts,facts['source_commit'])


def test_gate_producer_dirty_tree_is_flagged(monkeypatch):
    mod=_gates(); real=mod.subprocess.run
    def fake(cmd,*a,**k):
        if 'status' in cmd:
            class R: stdout=' M file.py\n'; returncode=0
            return R()
        return real(cmd,*a,**k)
    monkeypatch.setattr(mod.subprocess,'run',fake)
    facts=mod.produce(runner=_fake_runner())
    assert facts['tree_clean'] is False
    with pytest.raises(v.VerificationError): v.validate_full_gates(facts,facts['source_commit'])

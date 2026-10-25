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



def _triage(mutate=None):
    import copy
    from .test_final_gates import triage_facts
    facts=copy.deepcopy(triage_facts())
    if mutate:mutate(facts['packages']['medfit'],facts)
    return facts


def test_triage_schema_accepts_a_complete_record():
    v.validate_package_triage(_triage())


@pytest.mark.parametrize('defect,mutate',[
    ('missing-package',lambda p,f:f['packages'].pop('probmed')),
    ('unreviewed',lambda p,f:p.update(reviewed=False)),
    ('no-disposition',lambda p,f:p.update(disposition='')),
    ('short-commit',lambda p,f:p.update(commit='abc123')),
    ('no-readme-hash',lambda p,f:p.update(source_sha256={})),
    ('bad-hash',lambda p,f:p.update(source_sha256={'README.md':'xyz'})),
    ('missing-count',lambda p,f:p['counts'].pop('blocked')),
    ('negative-count',lambda p,f:p['counts'].update(excluded=-1)),
    ('non-integer-count',lambda p,f:p['counts'].update(checked='2')),
    ('counts-do-not-sum',lambda p,f:p['counts'].update(unverified=1)),
    ('eligible-exceeds-discovered',lambda p,f:p['counts'].update(eligible=9)),
    ('checked-exceeds-eligible',lambda p,f:p['counts'].update(checked=5,unverified=1)),
    ('partial-without-reason',lambda p,f:p.update(reasons=[])),
    ('partial-claims-complete',lambda p,f:p.update(scope='complete')),
    ('incomplete-state-claims-complete',lambda p,f:p.update(state='complete')),
    ('unknown-state',lambda p,f:p.update(state='green')),
    ('finding-untriaged',lambda p,f:p['findings'][0].pop('triage')),
    ('finding-no-rationale',lambda p,f:p['findings'][0]['triage'].update(rationale='')),
    ('unknown-triage-class',lambda p,f:p['findings'][0]['triage'].update(**{'class':'ignored'})),
    ('false-positive-unresolved',lambda p,f:p['findings'][0]['triage'].update(**{'class':'false-positive-class','class_id':'shape-width','resolved':False,'scoped_out':False})),
    ('false-positive-no-class-id',lambda p,f:p['findings'][0]['triage'].update(**{'class':'false-positive-class','resolved':True})),
    # Exact schema: nothing may hide in an unchecked key, an unseverity'd finding, or an extra package.
    ('finding-without-severity',lambda p,f:p['findings'][0].pop('severity')),
    ('finding-unknown-severity',lambda p,f:p['findings'][0].update(severity='low')),
    ('finding-without-check',lambda p,f:p['findings'][0].pop('check')),
    ('extra-count-key',lambda p,f:p['counts'].update(extra=-1)),
    ('extra-package-key',lambda p,f:p.update(secret='x')),
    ('extra-package',lambda p,f:f['packages'].update(extra=dict(p))),
    ('package-name-mismatch',lambda p,f:p.update(package='probmed')),
    ('hash-for-non-readme-key',lambda p,f:p['source_sha256'].update({'../../etc/passwd':'c'*64})),
])
def test_triage_schema_rejects_defects(defect,mutate):
    with pytest.raises(v.VerificationError):v.validate_package_triage(_triage(mutate))


def test_triage_false_positive_class_may_be_scoped_out_only_with_partial_scope():
    def scope_out(p,f):
        p['findings'][0]['triage'].update(**{'class':'false-positive-class','class_id':'shape-width','resolved':False,'scoped_out':True})
    v.validate_package_triage(_triage(scope_out))
    def scope_out_complete(p,f):
        scope_out(p,f);p.update(state='complete',scope='complete',reasons=[],counts={'discovered':6,'eligible':6,'checked':6,'excluded':0,'unverified':0,'blocked':0})
    with pytest.raises(v.VerificationError):v.validate_package_triage(_triage(scope_out_complete))


def test_triage_complete_scope_requires_nothing_unverified():
    def complete(p,f):
        p.update(state='complete',scope='complete',reasons=[],counts={'discovered':6,'eligible':6,'checked':6,'excluded':0,'unverified':0,'blocked':0})
    v.validate_package_triage(_triage(complete))
    def hidden(p,f):
        complete(p,f);p['counts'].update(checked=5,unverified=1)
    with pytest.raises(v.VerificationError):v.validate_package_triage(_triage(hidden))


def _triage_script():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/'scripts/a2_package_triage.py'
    spec=importlib.util.spec_from_file_location('a2_package_triage',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def _source_repo(path,readme):
    import subprocess
    path.mkdir(parents=True)
    env={'GIT_AUTHOR_NAME':'t','GIT_AUTHOR_EMAIL':'t@t','GIT_COMMITTER_NAME':'t','GIT_COMMITTER_EMAIL':'t@t','HOME':str(path),'PATH':'/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin'}
    def git(*args):return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,text=True,env=env).stdout.strip()
    git('init','-q','-b','main');(path/'DESCRIPTION').write_text('Package: demo\nVersion: 0.1.0\n');(path/'README.md').write_text(readme)
    git('add','-A');git('commit','-qm','init')
    return path,git


CANNED_REPORT={'stages':{'examples':{'state':'incomplete','counts':{'discovered':6,'eligible':4,'checked':2,'excluded':0,'unverified':4,'blocked':0,'matched':1,'mismatched':1},
                                      'reasons':['assertions outside supported R fences']}},
               'findings':[{'check':'examples-shape','severity':'warn','file':'README.md','line':85,'assertion_id':'README.md:85','message':'shape'},
                           {'check':'signature-names','severity':'warn','file':'README.md','line':3}]}


def test_triage_producer_audits_a_clone_and_never_goes_green_unreviewed(tmp_path):
    import hashlib
    script=_triage_script()
    repos={name:_source_repo(tmp_path/name,f'# {name}\n') for name in ('medfit','probmed','medrobust')}
    medfit,git=repos['medfit']
    (medfit/'README.md').write_text('# uncommitted edit\n')  # dirty working tree must not leak into the clone
    head_before=git('rev-parse','HEAD');status_before=git('status','--porcelain')
    audited=[]
    def stub(tree,budget):
        audited.append(tree);assert tree!=medfit and (tree/'DESCRIPTION').is_file();return CANNED_REPORT
    result=script.produce({name:path for name,(path,_) in repos.items()},60,audit=stub)
    assert git('rev-parse','HEAD')==head_before and git('status','--porcelain')==status_before  # source untouched
    record=result['packages']['medfit']
    assert record['commit']==head_before and record['source_dirty'] is True
    assert record['source_sha256']['README.md']==hashlib.sha256(b'# medfit\n').hexdigest()  # committed content, not the edit
    assert record['counts']['discovered']==6 and record['scope']=='partial' and record['state']=='incomplete'
    assert [f['check'] for f in record['findings']]==['examples-shape']  # only A2 example findings are triaged here
    with pytest.raises(v.VerificationError):v.validate_package_triage(result)  # generated != reviewed
    for item in result['packages'].values():
        item['findings'][0]['triage']={'class':'true-positive','rationale':'documented shape differs from the real result'}
        item['reviewed']=True;item['disposition']='reviewed; partial scope recorded as incomplete'
    v.validate_package_triage(result)


def test_triage_not_applicable_is_vacuous_but_never_silent():
    zero={'discovered':0,'eligible':0,'checked':0,'excluded':0,'unverified':0,'blocked':0}
    def vacuous(p,f):p.update(state='not-applicable',scope='not-applicable',counts=dict(zero),reasons=['README has no documented output'],findings=[])
    v.validate_package_triage(_triage(vacuous))
    for defect in (lambda p,f:p.update(reasons=[]),lambda p,f:p.update(scope='partial'),lambda p,f:p['counts'].update(discovered=1,unverified=1),
                   lambda p,f:p.update(scope='complete')):
        def mutated(p,f,defect=defect):
            vacuous(p,f);defect(p,f)
        with pytest.raises(v.VerificationError):v.validate_package_triage(_triage(mutated))
    def scope_only(p,f):p.update(scope='not-applicable')  # partial counts cannot hide behind a vacuous scope
    with pytest.raises(v.VerificationError):v.validate_package_triage(_triage(scope_only))


@pytest.mark.parametrize('defect,entry',[
    ('no-status',{'class_id':'x','rationale':'r'}),
    ('no-rationale',{'class_id':'x','status':'scoped-out','rationale':''}),
    ('fixed-without-commit',{'class_id':'x','status':'fixed','rationale':'r'}),
    ('fixed-short-commit',{'class_id':'x','status':'fixed','rationale':'r','fix_commit':'abc'}),
    ('unknown-status',{'class_id':'x','status':'ignored','rationale':'r'}),
])
def test_triaged_class_record_is_strict(defect,entry):
    def add(p,f):p['triaged_classes']=[entry]
    with pytest.raises(v.VerificationError):v.validate_package_triage(_triage(add))


def test_triaged_class_fixed_with_commit_is_accepted():
    def add(p,f):p['triaged_classes']=[{'class_id':'tibble-type-row','status':'fixed','rationale':'r','fix_commit':'c'*40}]
    v.validate_package_triage(_triage(add))

import json
import sys
import time
from pathlib import Path
import pytest
from .test_final_gates import live_facts, review_facts, triage_facts, gate_facts
from .test_release_ci import records
from .test_release_verifier import v

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import a2_observations as obs  # noqa: E402


LIVE_DEFECTS = {
    'no-supported-site': lambda f: f.pop('supported_site'),
    'site-incomplete': lambda f: f['supported_site'].update(state='incomplete'),
    'no-requests': lambda f: (f['supported_site'].update(requests=0), f.update(requests=0)),
    'bool-requests': lambda f: (f['supported_site'].update(requests=True), f.update(requests=True)),
    'nothing-checked': lambda f: (f['supported_site'].update(checked=0), f.update(checked=0)),
    'summary-disagrees': lambda f: f.update(checked=99),
    'url-disagrees': lambda f: f.update(url='https://elsewhere.example/'),
    'no-limit-runs': lambda f: f.update(unsupported_real_runs=[]),
    'limit-run-without-reasons': lambda f: f['unsupported_real_runs'][0].update(reasons=[]),
    'limit-run-complete': lambda f: f['unsupported_real_runs'][0].update(state='complete'),
}


def test_live_smoke_record_accepted():
    v.validate_live_smoke(live_facts())


@pytest.mark.parametrize('defect', sorted(LIVE_DEFECTS))
def test_live_smoke_record_rejects(defect):
    facts = live_facts()
    LIVE_DEFECTS[defect](facts)
    with pytest.raises(v.VerificationError):
        v.validate_live_smoke(facts)


def _audit_for(states):
    def audit(path, url, ref):
        state, checked, reasons = states[url]
        return {'stage': {'state': state, 'counts': {'checked': checked}, 'reasons': reasons}, 'requests': 1}
    return audit


def _clone_stub(repo, dest):
    dest.mkdir(parents=True)
    import subprocess
    subprocess.run(['git', 'init', '-q', str(dest)], check=True)
    subprocess.run(['git', '-C', str(dest), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x'], check=True)
    return subprocess.run(['git', '-C', str(dest), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()


SITES = {'sup': {'name': 'sup', 'repo': 'r', 'url': v.SUPPORTED_SITE_URL}, 'lim': ({'name': 'lim', 'repo': 'r', 'url': 'https://l/'},)}


def test_live_smoke_observation_passes_with_a_complete_site_and_an_honest_limit(tmp_path):
    states = {v.SUPPORTED_SITE_URL: ('complete', 4, []), 'https://l/': ('incomplete', 0, ['development mode/destination mapping unsupported'])}
    facts, status = obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'], limits=SITES['lim'])
    assert status == 'passed'
    v.validate_live_smoke(facts)


@pytest.mark.parametrize('states', [
    {v.SUPPORTED_SITE_URL: ('incomplete', 4, ['x']), 'https://l/': ('incomplete', 0, ['y'])},
    {v.SUPPORTED_SITE_URL: ('complete', 0, []), 'https://l/': ('incomplete', 0, ['y'])},
    {v.SUPPORTED_SITE_URL: ('complete', 4, []), 'https://l/': ('incomplete', 0, [])},
])
def test_live_smoke_observation_fails(tmp_path, states):
    _, status = obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'], limits=SITES['lim'])
    assert status == 'failed'


def test_request_counter_counts_opener_calls(monkeypatch, tmp_path):
    from lib import _docsite, docaudit

    class FakeOpener:
        def open(self, *a, **k):
            return 'ok'

    fake_builder = lambda *h: FakeOpener()
    monkeypatch.setattr(_docsite.request, 'build_opener', fake_builder)

    def fake_audit(path, **kwargs):
        opener = _docsite.request.build_opener()
        opener.open('u'); opener.open('v')
        return {'stages': {'site': {'state': 'complete', 'counts': {'checked': 2}}}}
    monkeypatch.setattr(docaudit, 'audit', fake_audit)
    result = obs.counting_audit(tmp_path, v.SUPPORTED_SITE_URL, 'main')
    assert result['requests'] == 2 and result['stage']['counts']['checked'] == 2
    assert _docsite.request.build_opener is fake_builder


def _fresh(reviewed):
    return json.loads(json.dumps(reviewed['facts']))


def test_triage_observation_passes_when_fresh_run_matches():
    reviewed = {'facts': triage_facts()}
    facts, status = obs.observe_package_triage(reviewed, _fresh(reviewed))
    assert status == 'passed' and set(facts) == {'packages'}


@pytest.mark.parametrize('mutate', [
    lambda p: p['medfit']['counts'].update(checked=0),
    lambda p: p['medfit'].update(state='complete'),
    lambda p: p['probmed']['source_sha256'].update({'README.md': 'e' * 64}),
    lambda p: p['medrobust'].update(findings=[]) if False else p['probmed']['findings'].append({'check': 'examples-shape', 'severity': 'warn'}),
])
def test_triage_observation_fails_on_drift(mutate):
    reviewed = {'facts': triage_facts()}
    fresh = _fresh(reviewed)
    mutate(fresh['packages'])
    _, status = obs.observe_package_triage(reviewed, fresh)
    assert status == 'failed'


def test_triage_observation_rejects_a_reviewed_commit_that_is_not_the_fresh_one():
    reviewed = {'facts': triage_facts()}
    fresh = _fresh(reviewed)
    fresh['packages']['medfit']['commit'] = 'f' * 40
    _, status = obs.observe_package_triage(reviewed, fresh)
    assert status == 'failed'


@pytest.mark.parametrize('mutate', [
    lambda p: p['probmed']['findings'][0].update(check='examples-error'),
    lambda p: p['probmed']['findings'][0].update(severity='error'),
    lambda p: p['probmed']['findings'][0].update(assertion_id='README.md:99'),
    lambda p: p['medfit'].update(scope='complete'),
    lambda p: p['medfit'].update(reasons=['a different reason']),
])
def test_triage_drift_covers_finding_identity_scope_and_reasons(mutate):
    reviewed = {'facts': triage_facts()}
    fresh = _fresh(reviewed)
    mutate(fresh['packages'])
    _, status = obs.observe_package_triage(reviewed, fresh)
    assert status == 'failed'


def _site(root, pages):
    for page, body in pages.items():
        d = root / page
        d.mkdir(parents=True)
        (d / 'index.html').write_text(f'<html><article>{body}</article></html>')


def _all_pages(**override):
    pages = {p: ' '.join(t) + ' rest' for p, t in obs.RENDERED_PAGES.items()}
    pages.update(override)
    return pages


def test_page_inspection_passes_a_complete_site(tmp_path):
    _site(tmp_path, _all_pages())
    assert all(p['inspected'] for p in obs.inspect_pages(tmp_path))


@pytest.mark.parametrize('override,why', [
    ({'REFCARD': 'nothing useful'}, 'missing term'),
    ({'REFCARD': '--site --run-examples ```raw fence'}, 'raw markdown'),
    ({'REFCARD': '--site --run-examples <a href="gone/">x</a>'}, 'broken link'),
])
def test_page_inspection_fails(tmp_path, override, why):
    _site(tmp_path, _all_pages(**override))
    result = {p['page']: p['inspected'] for p in obs.inspect_pages(tmp_path)}
    assert result['REFCARD'] is False and sum(result.values()) == len(result) - 1


def test_page_inspection_missing_page_fails(tmp_path):
    pages = _all_pages(); pages.pop('commands')
    _site(tmp_path, pages)
    assert {p['page']: p['inspected'] for p in obs.inspect_pages(tmp_path)}['commands'] is False


def test_rendered_observation_status(tmp_path):
    def build(site):
        _site(site, _all_pages())
    facts, status = obs.observe_rendered(tmp_path, build=build)
    assert status == 'passed' and facts['pages']


def test_review_observation_binds_candidate():
    facts, status = obs.observe_review(review_facts(), 'sha')
    assert status == 'passed' and facts['attested'] is True
    assert obs.observe_review(review_facts(), 'other')[1] == 'failed'


def _repo(tmp_path):
    import subprocess
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x'], check=True)


def _ok_runner(command, cwd):
    return 0, '1460 passed in 1s\nTotal: 47  |  Passed: 47  |  Failed: 0\n'


def test_gate_observation_passes_on_a_clean_committed_tree(tmp_path):
    _repo(tmp_path)
    facts, status = obs.observe_full_gates(tmp_path, runner=_ok_runner)
    assert status == 'passed' and facts['tree_clean'] is True


def test_gate_observation_fails_when_a_gate_dirties_the_tree(tmp_path):
    _repo(tmp_path)
    def dirtying(command, cwd):
        (tmp_path / 'generated.txt').write_text('x')
        return _ok_runner(command, cwd)
    facts, status = obs.observe_full_gates(tmp_path, runner=dirtying)
    assert status == 'failed' and facts['tree_clean'] is False


def test_mapping_observation_on_the_real_ledger():
    root = Path(__file__).resolve().parents[2]
    facts, status = obs.observe_mapping(root)
    assert status == 'passed' and facts['requirements'] == 118 and facts['unmapped'] == 0


def test_written_records_and_index_pass_the_aggregate_validator(tmp_path):
    platforms, _ = records()
    facts = {'live_smoke': live_facts(), 'package_triage': triage_facts(), 'full_gates': gate_facts(),
             'rendered_review': {'pages': [{'inspected': True, 'sha256': 'a' * 64}]}, 'adversarial_review': review_facts(),
             'requirement_mapping': {'review': 'complete', 'unmapped': 0, 'requirements': 118}}
    index = {k: obs.write_record(tmp_path, k, 'passed', 'sha', '123', f) for k, f in facts.items()}
    assert v.validate_aggregate(platforms, index, candidate_sha='sha', evidence_root=tmp_path)['verified']


def test_failed_status_is_never_accepted(tmp_path):
    platforms, _ = records()
    facts = {'live_smoke': live_facts(), 'package_triage': triage_facts(), 'full_gates': gate_facts(),
             'rendered_review': {'pages': [{'inspected': True, 'sha256': 'a' * 64}]}, 'adversarial_review': review_facts(),
             'requirement_mapping': {'review': 'complete', 'unmapped': 0, 'requirements': 118}}
    index = {k: obs.write_record(tmp_path, k, 'failed' if k == 'live_smoke' else 'passed', 'sha', '123', f) for k, f in facts.items()}
    with pytest.raises(v.VerificationError):
        v.validate_aggregate(platforms, index, candidate_sha='sha', evidence_root=tmp_path)


def test_a_limit_site_that_becomes_supported_is_an_improvement_not_a_failure(tmp_path):
    states = {v.SUPPORTED_SITE_URL: ('complete', 4, []), 'https://l/': ('complete', 3, [])}
    sites = ({'name': 'a', 'repo': 'r', 'url': 'https://l/'}, {'name': 'b', 'repo': 'r', 'url': 'https://l2/'})
    states['https://l2/'] = ('incomplete', 0, ['development mode/destination mapping unsupported'])
    facts, status = obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'], limits=sites)
    assert status == 'passed' and [r['name'] for r in facts['unsupported_real_runs']] == ['b'] and facts['other_real_runs'][0]['name'] == 'a'


def test_supported_site_is_pinned_to_a_commit_and_url():
    assert len(obs.SUPPORTED_SITE['commit']) == 40 and obs.SUPPORTED_SITE['url'] == v.SUPPORTED_SITE_URL


def test_live_smoke_rejects_a_site_other_than_the_pinned_one():
    facts = live_facts()
    facts['url'] = facts['supported_site']['url'] = 'https://elsewhere.example/'
    with pytest.raises(v.VerificationError):
        v.validate_live_smoke(facts)


def test_clone_is_retried_on_a_transient_failure(monkeypatch, tmp_path):
    calls = {'n': 0}
    import subprocess as sp
    real = sp.run
    def flaky(cmd, *a, **k):
        if cmd[:2] == ['git', 'clone']:
            calls['n'] += 1
            if calls['n'] < 3:
                raise sp.CalledProcessError(128, cmd)
            real(['git', 'init', '-q', cmd[-1]], check=True)
            return real(['git', '-C', cmd[-1], '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x'], check=True)
        return real(cmd, *a, **k)
    monkeypatch.setattr(obs.subprocess, 'run', flaky)
    monkeypatch.setattr(obs.time, 'sleep', lambda s: None)
    obs._clone('https://example.invalid/x', tmp_path / 'x')
    assert calls['n'] == 3


def test_a_crashing_observation_becomes_a_failed_record_not_a_crash():
    facts, status = obs.guarded('x', lambda: (_ for _ in ()).throw(RuntimeError('boom')))
    assert status == 'failed' and 'boom' in facts['error']
    assert obs.guarded('x', lambda: ({'ok': 1}, 'passed')) == ({'ok': 1}, 'passed')


def test_malformed_review_input_is_rejected_before_any_work(tmp_path):
    bad = tmp_path / 'review.json'
    bad.write_text('["not", "an", "object"]')
    with pytest.raises(SystemExit):
        obs.main(['--workdir', str(tmp_path / 'w'), '--output', str(tmp_path / 'o'), '--run-id', '1', '--candidate-sha', 'x', '--review-record', str(bad)])
    assert not (tmp_path / 'o').exists()

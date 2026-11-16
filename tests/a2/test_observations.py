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
    # the verifier holds the primary and both named pinned sites to the producer's predicate (one shared function)
    'primary-missing-routes': lambda f: f['supported_site'].update(missing=3),
    'primary-missing-count-none': lambda f: f['supported_site'].update(missing=None),
    'primary-missing-count-bool': lambda f: f['supported_site'].update(missing=False),
    'primary-warn-finding': lambda f: f['supported_site'].update(finding_severities=['warn']),
    'primary-error-finding': lambda f: f['supported_site'].update(finding_severities=['info', 'error']),
    'primary-severities-not-a-list': lambda f: f['supported_site'].update(finding_severities='warn'),
    'primary-lacks-missing': lambda f: f['supported_site'].pop('missing'),
    'primary-lacks-severities': lambda f: f['supported_site'].pop('finding_severities'),
    'pinned-missing-routes': lambda f: f['pinned_real_runs'][0].update(missing=9),
    'pinned-missing-count-none': lambda f: f['pinned_real_runs'][1].update(missing=None),
    'pinned-warn-finding': lambda f: f['pinned_real_runs'][1].update(finding_severities=['warn']),
    'pinned-error-finding': lambda f: f['pinned_real_runs'][0].update(finding_severities=['error']),
    'pinned-incomplete': lambda f: f['pinned_real_runs'][0].update(state='incomplete'),
    'pinned-no-requests': lambda f: f['pinned_real_runs'][1].update(requests=0),
    'pinned-nothing-checked': lambda f: f['pinned_real_runs'][0].update(checked=0),
    'pinned-lacks-missing': lambda f: f['pinned_real_runs'][0].pop('missing'),
    'pinned-lacks-severities': lambda f: f['pinned_real_runs'][1].pop('finding_severities'),
    'pinned-list-absent': lambda f: f.pop('pinned_real_runs'),
    'pinned-list-empty': lambda f: f.update(pinned_real_runs=[]),
    'pinned-list-not-a-list': lambda f: f.update(pinned_real_runs={'medfit': {}}),
    'pinned-probmed-absent': lambda f: f.update(pinned_real_runs=f['pinned_real_runs'][:1]),
    'pinned-medfit-absent': lambda f: f.update(pinned_real_runs=f['pinned_real_runs'][1:]),
    'pinned-duplicate-medfit': lambda f: f.update(pinned_real_runs=[f['pinned_real_runs'][0]] * 2),
    'pinned-extra-unnamed-site': lambda f: f['pinned_real_runs'].append(dict(f['pinned_real_runs'][0], name='other')),
    'pinned-wrong-name': lambda f: f['pinned_real_runs'][0].update(name='medfit-fork'),
    'pinned-wrong-url': lambda f: f['pinned_real_runs'][1].update(url='https://elsewhere.example/probmed/'),
    'pinned-entry-not-a-dict': lambda f: f['pinned_real_runs'].__setitem__(0, 'medfit'),
    # a limit site must be incomplete for an UNSUPPORTED-LAYOUT reason, never because the site could not be read
    'limit-http-503': lambda f: f['unsupported_real_runs'][0].update(reasons=['HTTP Error 503: Service Unavailable']),
    'limit-timeout': lambda f: f['unsupported_real_runs'][0].update(reasons=['sitemap read exceeded 10-second budget']),
    'limit-dns-error': lambda f: f['unsupported_real_runs'][0].update(reasons=['<urlopen error [Errno 8] nodename nor servname provided, or not known>']),
    'limit-transport-word-unsupported': lambda f: f['unsupported_real_runs'][0].update(reasons=['HTTP Error 415: Unsupported Media Type']),
    'limit-sitemap-content-refused': lambda f: f['unsupported_real_runs'][0].update(reasons=['DTD/entity sitemap unsupported']),
    'limit-mixed-layout-and-transport': lambda f: f['unsupported_real_runs'][0].update(reasons=['custom template mapping unsupported', 'HTTP Error 503: Service Unavailable']),
    'limit-reasons-not-a-list': lambda f: f['unsupported_real_runs'][0].update(reasons='custom template mapping unsupported'),
    'limit-reason-not-a-string': lambda f: f['unsupported_real_runs'][0].update(reasons=[None]),
    'limit-reasons-absent': lambda f: f['unsupported_real_runs'][0].pop('reasons'),
    'limit-state-absent': lambda f: f['unsupported_real_runs'][0].pop('state'),
    'limit-second-run-transport': lambda f: f['unsupported_real_runs'].append(dict(f['unsupported_real_runs'][0], name='x', reasons=['HTTP Error 503'])),
    # every run is bound to the reviewed identity: name, deployed URL and full commit (one table, owned by the verifier)
    'primary-wrong-sha': lambda f: f['supported_site'].update(source_ref='1' * 40),
    'medfit-wrong-sha': lambda f: f['pinned_real_runs'][0].update(source_ref='2' * 40),
    'probmed-wrong-sha': lambda f: f['pinned_real_runs'][1].update(source_ref='3' * 40),
    'glue-wrong-sha': lambda f: f['unsupported_real_runs'][0].update(source_ref='4' * 40),
    'primary-short-sha': lambda f: f['supported_site'].update(source_ref=f['supported_site']['source_ref'][:7]),
    'medfit-short-sha': lambda f: f['pinned_real_runs'][0].update(source_ref=f['pinned_real_runs'][0]['source_ref'][:12]),
    'probmed-short-sha': lambda f: f['pinned_real_runs'][1].update(source_ref=f['pinned_real_runs'][1]['source_ref'][:7]),
    'glue-short-sha': lambda f: f['unsupported_real_runs'][0].update(source_ref=f['unsupported_real_runs'][0]['source_ref'][:7]),
    'glue-uppercase-sha': lambda f: f['unsupported_real_runs'][0].update(source_ref=f['unsupported_real_runs'][0]['source_ref'].upper()),
    'primary-lacks-source-ref': lambda f: f['supported_site'].pop('source_ref'),
    'medfit-lacks-source-ref': lambda f: f['pinned_real_runs'][0].pop('source_ref'),
    'probmed-source-ref-none': lambda f: f['pinned_real_runs'][1].update(source_ref=None),
    'glue-lacks-source-ref': lambda f: f['unsupported_real_runs'][0].pop('source_ref'),
    'summary-source-ref-disagrees': lambda f: f.update(source_ref='5' * 40),
    'primary-wrong-name': lambda f: f['supported_site'].update(name='someone-else'),
    'primary-lacks-name': lambda f: f['supported_site'].pop('name'),
    'glue-wrong-name': lambda f: f['unsupported_real_runs'][0].update(name='dplyr'),
    'glue-lacks-name': lambda f: f['unsupported_real_runs'][0].pop('name'),
    'glue-wrong-url': lambda f: f['unsupported_real_runs'][0].update(url='https://glue.tidyverse.org/'),
    'glue-lacks-url': lambda f: f['unsupported_real_runs'][0].pop('url'),
    'substitute-limit-site': lambda f: f['unsupported_real_runs'][0].update(name='dplyr', url='https://dplyr.tidyverse.org/dev/'),
    'substitute-limit-site-keeping-glue-identity-fields-blank': lambda f: f.update(unsupported_real_runs=[{'state': 'incomplete', 'reasons': ['custom template mapping unsupported']}]),
    'extra-limit-run': lambda f: f['unsupported_real_runs'].append(dict(f['unsupported_real_runs'][0], name='dplyr', url='https://dplyr.tidyverse.org/dev/')),
    'duplicate-glue-run': lambda f: f['unsupported_real_runs'].append(dict(f['unsupported_real_runs'][0])),
    'limit-entry-not-a-dict': lambda f: f['unsupported_real_runs'].append('glue'),
    # an old-shape record (before the pinned sites existed) has none of the new fields and must not default to a pass
    'old-shape-record': lambda f: ([f['supported_site'].pop(k) for k in ('missing', 'finding_severities')], f.pop('pinned_real_runs')),
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
        state, checked, reasons, *rest = states[url]
        requests, missing, findings = (list(rest) + [1, 0, []][len(rest):])[:3]
        return {'stage': {'state': state, 'counts': {'checked': checked, 'missing': missing}, 'reasons': reasons,
                          'findings': [{'check': 'site-missing-page' if sev == 'warn' else 'site-extra-page', 'severity': sev} for sev in findings]},
                'requests': requests}
    return audit


def _clone_stub(repo, dest):
    dest.mkdir(parents=True)
    import subprocess
    subprocess.run(['git', 'init', '-q', str(dest)], check=True)
    subprocess.run(['git', '-C', str(dest), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-q', '--allow-empty', '-m', 'x'], check=True)
    return subprocess.run(['git', '-C', str(dest), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()


SITES = {'sup': {'name': 'sup', 'repo': 'r', 'url': v.SUPPORTED_SITE_URL}, 'lim': ({'name': 'lim', 'repo': 'r', 'url': 'https://l/'},)}


def test_live_smoke_observation_passes_with_a_complete_site_and_an_honest_limit(tmp_path):
    states = {v.SUPPORTED_SITE_URL: ('complete', 4, []), 'https://l/': ('incomplete', 0, ['custom template mapping unsupported'])}
    facts, status = obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'], limits=SITES['lim'], pinned_supported=())
    assert status == 'passed'  # no pinned sites configured here; the verifier requires medfit and probmed (see below)


@pytest.mark.parametrize('states', [
    {v.SUPPORTED_SITE_URL: ('incomplete', 4, ['x']), 'https://l/': ('incomplete', 0, ['y'])},
    {v.SUPPORTED_SITE_URL: ('complete', 0, []), 'https://l/': ('incomplete', 0, ['y'])},
    {v.SUPPORTED_SITE_URL: ('complete', 4, []), 'https://l/': ('incomplete', 0, [])},
])
def test_live_smoke_observation_fails(tmp_path, states):
    _, status = obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'], limits=SITES['lim'], pinned_supported=())
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
    lambda p: p['probmed']['findings'].append({'check': 'examples-shape', 'severity': 'warn'}),
    lambda p: p['medfit'].update(source_dirty=True),
    lambda p: p.update(extra=dict(p['medfit'])),
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
    states['https://l2/'] = ('incomplete', 0, ['custom template mapping unsupported'])
    facts, status = obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'], limits=sites, pinned_supported=())
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


def test_triage_drift_is_recorded_in_the_failed_observation():
    reviewed = {'facts': triage_facts()}
    fresh = _fresh(reviewed)
    fresh['packages']['medfit']['counts']['checked'] = 0
    facts, status = obs.observe_package_triage(reviewed, fresh)
    assert status == 'failed' and facts['fresh_run_drift'] == ['medfit.counts']
    clean, ok = obs.observe_package_triage(reviewed, _fresh(reviewed))
    assert ok == 'passed' and 'fresh_run_drift' not in clean


PINNED = ({'name': 'medfit', 'repo': 'r', 'url': v.PINNED_SUPPORTED_URLS['medfit']},
          {'name': 'probmed', 'repo': 'r', 'url': v.PINNED_SUPPORTED_URLS['probmed']})
BASE = {v.SUPPORTED_SITE_URL: ('complete', 4, []), 'https://l/': ('incomplete', 0, ['custom template mapping unsupported']),
        v.PINNED_SUPPORTED_URLS['medfit']: ('complete', 66, []), v.PINNED_SUPPORTED_URLS['probmed']: ('complete', 107, [])}


def _live(tmp_path, **changes):
    states = {**BASE, **changes}
    return obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=_clone_stub, supported=SITES['sup'],
                                  limits=SITES['lim'], pinned_supported=PINNED)


def _live_reviewed(tmp_path, monkeypatch, **changes):
    """Run the producer on the four REAL site identities; each clone stub stands in for the reviewed commit.

    The stub repo's HEAD plays the part of the reviewed SHA, so the verifier's table is patched to it (the table is
    otherwise the real one). The record that comes back is exactly what the producer writes.
    """
    sites = {n: {'name': n, 'repo': 'r', 'url': e['url']} for n, e in v.REVIEWED_LIVE_SITES.items()}
    glue_url = v.REVIEWED_LIVE_SITES['glue']['url']
    states = {**BASE, glue_url: ('incomplete', 0, ['custom template mapping unsupported']), **changes}
    states.pop('https://l/', None)

    def clone(repo, dest):
        sha = _clone_stub(repo, dest)
        monkeypatch.setitem(v.REVIEWED_LIVE_SITES, dest.name, {**v.REVIEWED_LIVE_SITES[dest.name], 'commit': sha})
        sites[dest.name]['commit'] = sha
        return sha
    return obs.observe_live_smoke(tmp_path, audit=_audit_for(states), clone=clone, supported=sites['cranlogs'],
                                  limits=(sites['glue'],), pinned_supported=(sites['medfit'], sites['probmed']))


def test_pinned_real_sites_must_be_complete_and_are_recorded(tmp_path, monkeypatch):
    facts, status = _live_reviewed(tmp_path, monkeypatch)
    assert status == 'passed' and [r['name'] for r in facts['pinned_real_runs']] == ['medfit', 'probmed']
    assert [r['name'] for r in facts['unsupported_real_runs']] == ['glue']
    v.validate_live_smoke(facts)


@pytest.mark.parametrize('change', [
    {v.PINNED_SUPPORTED_URLS['medfit']: ('incomplete', 0, ['unsupported article source: vignettes/x.qmd'])},
    {v.PINNED_SUPPORTED_URLS['probmed']: ('incomplete', 107, ['development mapping'])},
    {v.PINNED_SUPPORTED_URLS['medfit']: ('complete', 0, [])},
    {v.PINNED_SUPPORTED_URLS['probmed']: ('complete', 107, [], 0)},
    {v.PINNED_SUPPORTED_URLS['medfit']: ('unavailable', 0, ['crashed'])},
])
def test_a_failing_pinned_real_site_fails_the_observation_even_when_the_limit_site_is_incomplete(tmp_path, change):
    """Glue-style limit sites must not mask a regression in the sites that are supposed to be supported."""
    _, status = _live(tmp_path, **change)
    assert status == 'failed'


@pytest.mark.parametrize('reasons', [
    ['HTTP Error 503: Service Unavailable'],
    ['<urlopen error timed out>'],
    ['sitemap read exceeded 10-second budget'],
    [],
    ['custom template mapping unsupported', 'HTTP Error 503: Service Unavailable'],
])
def test_a_limit_site_that_is_incomplete_only_because_it_was_unreachable_does_not_count(tmp_path, reasons):
    """An outage on the limit site proves nothing about the unsupported-layout contract."""
    facts, status = _live(tmp_path, **{'https://l/': ('incomplete', 0, reasons)})
    assert status == 'failed'
    assert facts['unsupported_real_runs'] == [] or any(r in str(facts['unsupported_real_runs']) for r in reasons)


@pytest.mark.parametrize('reason', [
    'custom template mapping unsupported', 'custom layout/build configuration unsupported',
    'pkgdown configuration overlays unsupported', 'unsupported Quarto project configuration: _quarto.yml',
    'unsupported article format (format): vignettes/a.qmd', 'development.mode unsupported: \'weird\'',
    'template Bootstrap version unsupported: \'3\'', 'PKGDOWN_DEV_MODE set in .github/workflows/p.yaml; development mode mapping unsupported',
    'reusable workflow job unsupported (.github/workflows/p.yaml); the deployed routes cannot be verified',
])
def test_every_unsupported_layout_reason_the_engine_emits_is_recognized(reason):
    assert v.limit_run_is_unsupported_layout({'state': 'incomplete', 'reasons': [reason]})


def test_the_producer_and_the_verifier_share_one_limit_site_predicate():
    import inspect
    assert obs.limit_run_is_unsupported_layout.__module__ == 'verify_a2_release'
    assert inspect.getsource(obs.limit_run_is_unsupported_layout) == inspect.getsource(v.limit_run_is_unsupported_layout)


def test_the_real_glue_pin_still_fails_for_a_recognized_layout_reason():
    """Run the engine on glue's pinned layout (template.package) and feed its actual reasons to the shared predicate."""
    from lib import docaudit  # noqa: F401  (engine under test)
    from lib import _docsite
    reasons = _docsite.routes([], {'template': {'package': 'tidytemplate'}})[1]
    assert reasons == ['custom template mapping unsupported']
    assert v.limit_run_is_unsupported_layout({'state': 'incomplete', 'reasons': reasons})


def test_the_limit_site_must_still_be_incomplete_when_the_pinned_sites_pass(tmp_path):
    _, status = _live(tmp_path, **{'https://l/': ('complete', 3, [])})
    assert status == 'failed'


def test_default_pinned_sites_are_the_real_medfit_and_probmed_commits():
    assert [s['name'] for s in obs.PINNED_SUPPORTED_SITES] == ['medfit', 'probmed']
    assert [s['name'] for s in obs.LIMIT_SITES] == ['glue']
    for site in (*obs.PINNED_SUPPORTED_SITES, *obs.LIMIT_SITES):
        assert len(site['commit']) == 40


@pytest.mark.parametrize('change', [
    {v.PINNED_SUPPORTED_URLS['medfit']: ('complete', 66, [], 1, 9, ['warn'] * 9)},   # published routes lost: complete, but missing > 0
    {v.PINNED_SUPPORTED_URLS['probmed']: ('complete', 107, [], 1, 0, ['warn'])},      # a warn finding without a missing count
    {v.PINNED_SUPPORTED_URLS['probmed']: ('complete', 107, [], 1, 0, ['error'])},
    {v.PINNED_SUPPORTED_URLS['medfit']: ('complete', 66, [], 1, None, [])},          # missing count absent: unknown, never zero
    {v.SUPPORTED_SITE_URL: ('complete', 4, [], 1, 1, ['warn'])},  # the primary supported site is held to the same rule
    {v.SUPPORTED_SITE_URL: ('complete', 4, [], 1, 0, ['warn'])},
])
def test_pinned_and_primary_sites_must_have_no_missing_routes_or_warn_findings(tmp_path, change):
    _, status = _live(tmp_path, **change)
    assert status == 'failed'


def test_info_findings_do_not_fail_the_observation_and_are_recorded(tmp_path, monkeypatch):
    facts, status = _live_reviewed(tmp_path, monkeypatch, **{v.PINNED_SUPPORTED_URLS['medfit']: ('complete', 66, [], 1, 0, ['info', 'info'])})
    assert status == 'passed'
    run = facts['pinned_real_runs'][0]
    assert run['missing'] == 0 and run['finding_severities'] == ['info']
    assert facts['supported_site']['missing'] == 0 and facts['supported_site']['finding_severities'] == []
    v.validate_live_smoke(facts)


# The reviewed pins. Changing one is a deliberate act: re-audit the site at the new commit, then update it here.
EXPECTED_PINS = {
    'cranlogs': 'c02280c7b4c6d77ff5500f80e15118edad5d94dc',
    'medfit': '6d226fb1d4ce0b46cf297c2e88154d685a337dee',   # 40f82c8 predates the live native-* to sem-* rename: 9 missing pages
    'probmed': 'ab411df7f083e169dd4b56f264e867e4fd51e1c4',
    'glue': 'da9c73f7a3de6a27f3103cb5bb2355820a4c3a6a',
}


def _every_site():
    return (obs.SUPPORTED_SITE, *obs.PINNED_SUPPORTED_SITES, *obs.LIMIT_SITES)


def test_pinned_supported_sites_are_pinned_to_the_reviewed_full_commit_shas():
    import re
    pins = {s['name']: s.get('commit') for s in _every_site()}
    assert pins == EXPECTED_PINS
    # one table: the verifier's REVIEWED_LIVE_SITES is the source the producer pins from, never a second copy
    assert pins == {n: e['commit'] for n, e in v.REVIEWED_LIVE_SITES.items()}
    assert {n: e['url'] for n, e in v.REVIEWED_LIVE_SITES.items()} == {s['name']: s['url'] for s in _every_site()}
    for name, commit in pins.items():
        assert isinstance(commit, str) and re.fullmatch(r'[0-9a-f]{40}', commit), f'{name} is not a full lowercase 40-hex SHA'
        assert commit.upper() not in ('HEAD', 'MAIN', 'MASTER') and commit != '0' * 40, f'{name} is a floating or null ref'
    assert pins['medfit'] != '40f82c85fdad0979949bee389afe2c7301660315'  # the superseded pin


def test_the_producer_holds_no_second_copy_of_the_reviewed_identities():
    import inspect
    import re
    source = inspect.getsource(obs)
    assert not re.findall(r'\b[0-9a-f]{40}\b', source), 'a commit SHA is hard-coded in the producer; pin it in verify_a2_release.REVIEWED_LIVE_SITES'
    assert obs.REVIEWED_LIVE_SITES == v.REVIEWED_LIVE_SITES
    assert {e['role'] for e in v.REVIEWED_LIVE_SITES.values()} == {'primary', 'pinned', 'limit'}
    assert [n for n, e in v.REVIEWED_LIVE_SITES.items() if e['role'] == 'limit'] == ['glue']


def test_the_pinned_site_urls_match_the_verifier_and_every_pin_is_distinct():
    assert {s['name']: s['url'] for s in obs.PINNED_SUPPORTED_SITES} == v.PINNED_SUPPORTED_URLS
    assert obs.SUPPORTED_SITE['url'] == v.SUPPORTED_SITE_URL
    commits = [s['commit'] for s in _every_site()]
    assert len(set(commits)) == len(commits)


def test_the_live_smoke_audits_the_pinned_commit_not_whatever_the_default_branch_holds(tmp_path):
    """A clone lands on a newer default-branch commit; the observation must check out the pin, audit it and record it."""
    import subprocess as sp
    site = {'name': 'lim', 'repo': 'r', 'url': 'https://l/'}
    seen = {}

    def clone(repo, dest):
        dest.mkdir(parents=True)
        git = lambda *a: sp.run(['git', '-C', str(dest), '-c', 'user.name=t', '-c', 'user.email=t@t', *a], check=True, capture_output=True, text=True).stdout.strip()
        sp.run(['git', 'init', '-q', str(dest)], check=True)
        git('commit', '-q', '--allow-empty', '-m', 'pinned')
        site['commit'] = seen['pin'] = git('rev-parse', 'HEAD')  # the pin is read after the clone, as the producer does
        git('commit', '-q', '--allow-empty', '-m', 'newer')
        seen['head'] = git('rev-parse', 'HEAD')
        return seen['head']

    def audit(path, url, ref):
        seen['audited'] = sp.run(['git', '-C', str(path), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        return {'stage': {'state': 'incomplete', 'counts': {'checked': 0, 'missing': 0}, 'reasons': ['custom template mapping unsupported'], 'findings': []}, 'requests': 0}

    facts, _ = obs.observe_live_smoke(tmp_path, audit=audit, clone=clone, supported={'name': 'sup', 'repo': 'r', 'url': v.SUPPORTED_SITE_URL},
                                      limits=(site,), pinned_supported=())
    run = facts['unsupported_real_runs'][0]
    assert seen['pin'] != seen['head']
    assert seen['audited'] == seen['pin'] and run['source_ref'] == seen['pin']


def test_the_producer_and_the_verifier_share_one_soundness_predicate_and_one_pin_list():
    import inspect
    # `v` is loaded by file path under another module name, so compare the producer's imported function by source
    assert obs.site_run_is_sound.__module__ == 'verify_a2_release'
    assert inspect.getsource(obs.site_run_is_sound) == inspect.getsource(v.site_run_is_sound)
    assert {s['name']: s['url'] for s in obs.PINNED_SUPPORTED_SITES} == v.PINNED_SUPPORTED_URLS


def test_a_record_from_the_real_producer_is_accepted_by_the_verifier(tmp_path, monkeypatch):
    facts, status = _live_reviewed(tmp_path, monkeypatch)
    assert status == 'passed'
    v.validate_live_smoke(facts)
    facts['pinned_real_runs'][0]['missing'] = 1  # the same drift the producer rejects must be rejected downstream
    with pytest.raises(v.VerificationError):
        v.validate_live_smoke(facts)

import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import verify_a2_producer_run as pr  # noqa: E402

GOOD = {'id': 4242, 'head_sha': 'abc', 'path': '.github/workflows/a2-observations.yml', 'status': 'completed',
        'conclusion': 'success', 'event': 'workflow_dispatch'}


def test_genuine_producer_run_accepted():
    pr.verify_producer_run(GOOD, candidate_sha='abc', run_id='4242')


@pytest.mark.parametrize('field,value', [
    ('head_sha', 'old'), ('path', '.github/workflows/evil.yml'), ('path', ''), ('status', 'in_progress'),
    ('conclusion', 'failure'), ('conclusion', None), ('event', 'push'), ('id', 1),
])
def test_forged_or_wrong_producer_run_rejected(field, value):
    run = dict(GOOD, **{field: value})
    with pytest.raises(pr.ProducerRunError):
        pr.verify_producer_run(run, candidate_sha='abc', run_id='4242')


def test_missing_fields_rejected():
    with pytest.raises(pr.ProducerRunError):
        pr.verify_producer_run({}, candidate_sha='abc', run_id='4242')


def test_workflow_path_suffix_is_tolerated_but_prefix_confusion_is_not():
    pr.verify_producer_run(dict(GOOD, path='.github/workflows/a2-observations.yml@refs/heads/x'), candidate_sha='abc', run_id='4242')
    with pytest.raises(pr.ProducerRunError):
        pr.verify_producer_run(dict(GOOD, path='.github/workflows/a2-observations.yml.evil'), candidate_sha='abc', run_id='4242')


def test_cli_exit_codes(tmp_path):
    good = tmp_path / 'good.json'; good.write_text(json.dumps(GOOD))
    bad = tmp_path / 'bad.json'; bad.write_text(json.dumps(dict(GOOD, head_sha='old')))
    assert pr.main(['--run', str(good), '--candidate-sha', 'abc', '--run-id', '4242']) == 0
    assert pr.main(['--run', str(bad), '--candidate-sha', 'abc', '--run-id', '4242']) == 2
    assert pr.main(['--run', str(tmp_path / 'missing.json'), '--candidate-sha', 'abc', '--run-id', '4242']) == 2
    assert pr.main(['--run', str(good), '--candidate-sha', 'abc', '--run-id', 'nope']) == 2


def test_release_workflow_verifies_the_producer_run_before_downloading_it():
    import yaml
    root = Path(__file__).resolve().parents[2]
    steps = yaml.safe_load((root / '.github/workflows/a2-release.yml').read_text())['jobs']['aggregate']['steps']
    names = [s.get('name', s.get('uses', '')) for s in steps]
    verify = next(i for i, s in enumerate(steps) if 'verify_a2_producer_run.py' in s.get('run', ''))
    download = next(i for i, s in enumerate(steps) if s.get('with', {}).get('name') == 'a2-acceptance-evidence')
    assert verify < download, names
    assert '${{' not in steps[verify]['run'] and steps[verify]['env']['GH_TOKEN'] == '${{ github.token }}'

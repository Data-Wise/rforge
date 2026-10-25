"""The required manifest must describe exactly what pytest collects: the release run needs every listed node collected."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def manifest():
    return json.loads((ROOT / 'tests/a2/required.json').read_text())


@pytest.fixture(scope='module')
def collected():
    out = subprocess.run([sys.executable, '-m', 'pytest', 'tests/a2', '--collect-only', '-q', '-p', 'no:cacheprovider'],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if '::' in line]


def test_manifest_nodes_are_exactly_the_collection(manifest, collected):
    required = [n for g in manifest['groups'] for n in g['nodes']]
    assert len(required) == len(set(required)), 'duplicate required node'
    assert not [n for n in required if n not in set(collected)], 'manifest lists nodes pytest does not collect'
    assert not [n for n in collected if n not in set(required)], 'collected nodes missing from the manifest'
    assert manifest['collected_nodes'] == len(collected) == len(required)


def test_every_group_hashes_every_test_file_it_references(manifest):
    for group in manifest['groups']:
        files = {n.split('::')[0] for n in group['nodes']}
        assert files <= set(group['test_sources']), (group['id'], sorted(files - set(group['test_sources'])))
        for name, digest in group['test_sources'].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, (group['id'], name)


def test_ready_manifest_has_no_pending_group(manifest):
    assert manifest['status'] == 'ready' and all(g['status'] == 'ready' and g['nodes'] for g in manifest['groups'])


def test_refresh_drops_phantoms_adds_new_nodes_and_rehashes(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import refresh_a2_manifest as refresh
    src = 'tests/a2/test_manifest.py'
    manifest = {'groups': [
        {'id': 'A', 'nodes': [f'{src}::test_gone', f'{src}::test_ready_manifest_has_no_pending_group'], 'test_sources': {src: 'stale'}},
        {'id': 'B', 'nodes': [f'{src}::test_every_group_hashes_every_test_file_it_references'], 'test_sources': {}}]}
    collected = [f'{src}::test_manifest_nodes_are_exactly_the_collection', f'{src}::test_every_group_hashes_every_test_file_it_references',
                 f'{src}::test_ready_manifest_has_no_pending_group']
    out = refresh.refresh(manifest, collected, 'B')
    assert out['_refresh']['dropped'] == [f'{src}::test_gone'] and out['_refresh']['added'] == [collected[0]]
    assert collected[0] in out['groups'][1]['nodes'] and f'{src}::test_gone' not in out['groups'][0]['nodes']
    assert out['groups'][0]['test_sources'][src] == hashlib.sha256((ROOT / src).read_bytes()).hexdigest()
    assert out['collected_nodes'] == 3

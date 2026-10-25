"""The installed-runtime probe must report exactly the packages the lock pins, or release preflight can never pass."""
import json
import re
import subprocess
from pathlib import Path
import pytest
from . import runtime_probe

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads((ROOT / 'tests/a2/fixture-lock.json').read_text())


def test_probe_code_names_every_locked_package_once():
    code = runtime_probe.probe_code(LOCK['R_packages'])
    for package in LOCK['R_packages']:
        assert code.count(f'"{package}"') == 2, package  # once to query, once to name
    assert 'rsconnect' in code


def test_probe_code_follows_the_lock_not_a_fixed_list():
    assert '"zzz"' in runtime_probe.probe_code({'zzz': '1.0'}) and '"pkgload"' not in runtime_probe.probe_code({'zzz': '1.0'})


def test_installed_reports_the_same_keys_as_the_lock():
    reported = {'R': LOCK['R'], 'R_packages': dict(LOCK['R_packages'])}
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(reported), stderr='')
    got = runtime_probe.installed(LOCK, rscript='Rscript', run=fake_run)
    assert got == {'R': LOCK['R'], 'R_packages': LOCK['R_packages']}


def test_installed_is_none_when_r_fails():
    def broken(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)
    assert runtime_probe.installed(LOCK, rscript='Rscript', run=broken) is None


@pytest.mark.parametrize('path', ['scripts/run_a2_release.py', 'tests/a2/conftest.py'])
def test_no_hardcoded_package_list_remains(path):
    text = (ROOT / path).read_text()
    assert not re.search(r'"pkgload"\s*,\s*"evaluate"', text), f'{path} must derive the package list from the lock'

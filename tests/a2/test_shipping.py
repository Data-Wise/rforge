import json
import shutil
import subprocess
import tarfile
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


def test_no_new_public_module_dependency():
    source=(ROOT/'scripts/gen_lib_reference.py').read_text()
    assert '_docsite' not in source and '_docexamples' not in source and '_docguardian' not in source
    manifest=json.loads((ROOT/'package.json').read_text())
    assert 'lib/' in manifest['files'] and 'tests/' not in manifest['files']
    result=subprocess.run([__import__('sys').executable,'-m','lib.docaudit','--help'],cwd=ROOT,capture_output=True,text=True)
    assert result.returncode==0 and '--run-examples' in result.stdout


def test_r_script_packaged_and_parses(tmp_path):
    if not shutil.which('npm'):pytest.skip('Developer npm unavailable; release shipping gate requires it')
    result=subprocess.run(['npm','pack','--json','--ignore-scripts','--pack-destination',str(tmp_path)],cwd=ROOT,capture_output=True,text=True,timeout=30,env={**__import__('os').environ,'npm_config_cache':str(tmp_path/'cache')})
    assert result.returncode==0,result.stderr
    archive=tmp_path/json.loads(result.stdout)[0]['filename']
    with tarfile.open(archive) as packed:
        names=packed.getnames()
        assert 'package/lib/r/docexamples.R' in names and not any('/tests/harness/' in n for n in names)
        # A shipped source path is resolved from the module, never the working directory.
        packed.extractall(tmp_path,filter='data')
        member=packed.getmember('package/lib/r/docexamples.R')
        (tmp_path/'docexamples.R').write_bytes(packed.extractfile(member).read())
    parsed=subprocess.run(['Rscript','--vanilla','-e','invisible(parse(commandArgs(TRUE)[[1]]))',str(tmp_path/'docexamples.R')],capture_output=True,text=True,timeout=20)
    assert parsed.returncode==0,parsed.stderr
    from .test_examples_r import fixture
    pkg=fixture(tmp_path/"target", "```r\nprint(1)\n#> [1] 1\n```")
    installed=tmp_path/"package"
    replay=subprocess.run([__import__("sys").executable,"-m","lib.docaudit","--path",str(pkg),"--run-examples","--format","json"],cwd=installed,env={**__import__("os").environ,"PYTHONPATH":str(installed)},capture_output=True,text=True,timeout=30)
    assert replay.returncode==0,replay.stderr
    stage=json.loads(replay.stdout)["stages"]["examples"]
    assert stage["state"]=="complete" and stage["counts"]["checked"]==1

import sys
import time
from lib import _docguardian as guardian


def test_native_output_does_not_deadlock(tmp_path):
    code="import os;os.write(1,b'x'*200000);os.write(2,b'y'*200000)"
    r=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+5_000_000_000,cwd=tmp_path)
    assert r['reason']=='completed' and r['group_disappeared']
    assert (tmp_path/'stdout').stat().st_size==200000
    assert (tmp_path/'stderr').stat().st_size==200000


def test_shared_text_output_threshold(tmp_path):
    code="import os,time;os.write(1,b'x'*6000000);os.write(2,b'y'*6000000);time.sleep(30)"
    r=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+5_000_000_000,cwd=tmp_path)
    assert r['reason']=='output-limit' and r['observed_output_bytes']>guardian.OUTPUT_LIMIT
    assert r['direct_child_reaped']


def test_checkpoint_and_marker_integrity(tmp_path):
    guardian.atomic(tmp_path/'result.json',{'records':[{'id':'earlier','text':['ok']}]})
    r=guardian.run([sys.executable,'-c','import time;time.sleep(30)'],tmp_path,time.monotonic_ns()+200_000_000,cwd=tmp_path)
    assert r['reason']=='deadline'
    assert guardian.read(tmp_path/'result.json')['records'][0]['id']=='earlier'
    marker=guardian.read(tmp_path/'marker.json')
    assert marker['state']=='interrupted' and marker['run_id']==r['run_id']


def test_bounded_finalization_and_artifacts(tmp_path, monkeypatch):
    from lib import _docexamples as examples
    from .helpers import package
    p=package(tmp_path/'package','```r\nprint(1)\n#> [1] 1\n```\n```r\nprint(2)\n#> [1] 2\n```')
    (p/'README.Rmd').write_text('```r\nprint(1)\n#> [1] 1\n```')
    directories=[]
    def replay(command,directory,deadline,**kwargs):
        directories.append(directory)
        guardian.atomic(directory/'result.json',{'records':[{'id':'README.Rmd:3','text':['[1] 1\n']}]})
        clock=iter([0,6*guardian.NS])
        monkeypatch.setattr(examples.time,'monotonic_ns',lambda:next(clock))
        return {'reason':'completed'}
    monkeypatch.setattr(guardian,'run',replay)
    monkeypatch.setattr(examples.shutil,'which',lambda name:'/fixture/Rscript')
    report=examples.audit(p,deadline=20*guardian.NS)
    assert report['state']=='incomplete'
    counts=report['counts']
    assert counts['discovered']==3 and counts['unverified']==2 and counts['blocked']==1 and counts['checked']==0
    assert 'report assembly exceeded 5-second allowance' in report['reasons']
    assert directories and all(not directory.exists() for directory in directories)


def test_output_overshoot_with_parent_loss(tmp_path):
    import os
    import signal
    import subprocess
    from pathlib import Path
    code='import os,time;time.sleep(.4);os.write(1,b"x"*12000000);time.sleep(30)'
    invocation=f'from lib import _docguardian as g;import sys,time;g.run([sys.executable,"-c",{code!r}],{str(tmp_path)!r},time.monotonic_ns()+8*g.NS,cwd={str(tmp_path)!r})'
    parent=subprocess.Popen([sys.executable,'-c',invocation],cwd=Path(guardian.__file__).resolve().parents[1],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    armed={};terminal=None
    try:
        until=time.monotonic()+3
        while time.monotonic()<until:
            armed=guardian.read(tmp_path/'armed.json') or {}
            if armed.get('child_pid'):break
            time.sleep(.02)
        assert armed.get('child_pid')
        parent.kill();parent.wait(timeout=2)
        until=time.monotonic()+6
        while time.monotonic()<until:
            terminal=guardian.read(tmp_path/'terminal.json')
            if terminal:break
            time.sleep(.02)
        assert terminal and terminal['reason']=='output-limit'
        assert terminal['observed_output_bytes']>guardian.OUTPUT_LIMIT and terminal['direct_child_reaped']
        assert guardian.read(tmp_path/'marker.json')['state']=='started'
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=2)
        if not terminal and armed.get('child_pid'):
            try:os.killpg(armed['child_pid'],signal.SIGKILL)
            except ProcessLookupError:pass
        if not terminal and armed.get('guardian_pid'):
            try:os.kill(armed['guardian_pid'],signal.SIGKILL)
            except ProcessLookupError:pass

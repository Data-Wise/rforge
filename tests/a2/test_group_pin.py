"""Native ownership prototype evidence; does not certify production replay."""
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
from lib import _docguardian as guardian
from lib._docgroup_pin import GroupPin, spawn_in_group

ROOT = Path(guardian.__file__).resolve().parents[1]


def launch(group, code):
    with open(os.devnull, 'wb') as output:
        return spawn_in_group(group.pgid, [sys.executable, '-c', code], group.directory,
                              group.run_id, time.monotonic_ns()+30*guardian.NS,
                              ROOT, dict(os.environ), output, output)


def await_file(path, seconds=3):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if path.exists():return
        time.sleep(.02)
    pytest.fail('missing process fixture checkpoint: '+str(path))


def test_pin_holds_identity_after_workload_reap(tmp_path,monkeypatch):
    group=GroupPin(tmp_path,uuid.uuid4().hex,time.monotonic_ns()+5*guardian.NS)
    child=None;unrelated=None
    try:
        child=launch(group, 'pass');assert child.wait(timeout=3)==0
        # The guardian has reaped its workload, but the parent's pin remains live.
        unrelated=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
        guardian.atomic(tmp_path/'armed.json',{'child_pid':unrelated.pid})
        original=os.killpg;signals=[]
        def observed(pgid,number):
            assert pgid==group.pgid and pgid!=unrelated.pid
            assert group.process.returncode is None
            signals.append((pgid,number));return original(pgid,number)
        monkeypatch.setattr(os,'killpg',observed)
        group.signal_group(signal.SIGKILL)
        assert unrelated.poll() is None and signals==[(group.pgid,signal.SIGKILL)]
        group.finish();assert group.process.returncode is not None
        with pytest.raises(RuntimeError):group.signal_group(signal.SIGKILL)
        assert len(signals)==1
    finally:
        group.finish()
        if child and child.poll() is None:child.kill();child.wait(timeout=2)
        if unrelated and unrelated.poll() is None:unrelated.kill();unrelated.wait(timeout=2)


def test_pin_retains_exited_child_without_poll(tmp_path,monkeypatch):
    group=GroupPin(tmp_path,uuid.uuid4().hex,time.monotonic_ns()+5*guardian.NS)
    try:
        group.signal_group(signal.SIGKILL)
        until=time.monotonic()+2
        while not guardian.exited_unreaped(group.process) and time.monotonic()<until:time.sleep(.01)
        assert guardian.exited_unreaped(group.process)
        assert group.process.returncode is None
        # macOS hides zombie process groups from getpgid; the unreaped PID is
        # still reserved, so a new process cannot create that group number.
        try:assert os.getpgid(group.pgid)==group.pgid
        except ProcessLookupError:pass
        result=subprocess.run([sys.executable,'-c',f'import os;os.setpgid(0,{group.pgid})'],capture_output=True,text=True)
        # Linux can still expose the existing zombie group; neither platform
        # permits creation of a new unrelated leader with the reserved PID.
        if result.returncode==0:
            assert guardian.exited_unreaped(group.process)
        else:assert "PermissionError" in result.stderr or "ProcessLookupError" in result.stderr
        # macOS can deny signals to a zombie-only group. Keep that failure
        # explicit; neither EPERM nor ESRCH permits signalling a different PID.
        try:group.signal_group(signal.SIGKILL)
        except PermissionError:pass
        group.finish()
        calls=[];monkeypatch.setattr(os,'killpg',lambda *args:calls.append(args))
        with pytest.raises(RuntimeError):group.signal_group(signal.SIGKILL)
        assert not calls
    finally:group.finish()


@pytest.mark.parametrize('reaped',[False,True])
def test_guardian_crash_uses_owned_pin(tmp_path,reaped):
    group=GroupPin(tmp_path,uuid.uuid4().hex,time.monotonic_ns()+8*guardian.NS)
    wrapper=None
    marker=tmp_path/'guardian-crash.json'
    code=f"""import os,signal,subprocess,sys,json
from pathlib import Path
from lib._docgroup_pin import spawn_in_group
import time
with open(os.devnull,'wb') as output:
 child=spawn_in_group({group.pgid},[sys.executable,'-c',{'pass' if reaped else 'import time;time.sleep(30)'!r}],{str(tmp_path)!r},{group.run_id!r},time.monotonic_ns()+30_000_000_000,os.getcwd(),dict(os.environ),output,output)
if {reaped!r}:child.wait(timeout=3)
Path({str(marker)!r}).write_text(json.dumps({{'child_pid':child.pid,'reaped':{reaped!r}}}))
os.kill(os.getpid(),signal.SIGKILL)
"""
    started=time.monotonic()
    try:
        wrapper=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT)
        await_file(marker);assert wrapper.wait(timeout=3)==-signal.SIGKILL
        assert group.process.returncode is None
        group.signal_group(signal.SIGKILL)
        group.finish()
        # Orphan workload death is asynchronous; observe it within a bound.
        until=time.monotonic()+2
        while guardian.live_group_members(group.pgid) and time.monotonic()<until:time.sleep(.02)
        assert not guardian.live_group_members(group.pgid)
        assert time.monotonic()-started<5
    finally:
        if wrapper and wrapper.poll() is None:wrapper.kill();wrapper.wait(timeout=2)
        if not group.closed:group.signal_group(signal.SIGKILL);group.finish()


def test_pin_ignores_term_during_guardian_grace(tmp_path):
    group=GroupPin(tmp_path,uuid.uuid4().hex,time.monotonic_ns()+5*guardian.NS)
    child=None
    try:
        child=launch(group,'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)')
        time.sleep(.2)
        group.signal_group(signal.SIGTERM);time.sleep(.1)
        assert not guardian.exited_unreaped(group.process) and child.poll() is None
        group.signal_group(signal.SIGKILL);child.wait(timeout=2);group.finish()
        assert not guardian.live_group_members(group.pgid)
    finally:
        if not group.closed:group.signal_group(signal.SIGKILL);group.finish()
        if child and child.poll() is None:child.kill();child.wait(timeout=2)


def test_expired_pin_never_releases_workload(tmp_path):
    with pytest.raises(TimeoutError):GroupPin(tmp_path,uuid.uuid4().hex,time.monotonic_ns()-1)
    assert not (tmp_path/'workload-started').exists()



def prototype_supervise(directory,pgid,deadline,heartbeat_deadline):
    """Isolated guardian fixture: retain workload until the last group signal."""
    directory=Path(directory)
    with open(os.devnull,'wb') as output:
        child=spawn_in_group(pgid,[sys.executable,'-c','import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'],directory,'prototype',deadline,ROOT,dict(os.environ),output,output)
    guardian.atomic(directory/'prototype-armed.json',{'child_pid':child.pid,'guardian_pid':os.getpid(),'pgid':pgid,'deadline':deadline})
    try:
        while time.monotonic_ns()<min(deadline,heartbeat_deadline):time.sleep(.02)
        now=time.monotonic_ns();reason='deadline' if now>=deadline else 'parent-loss'
        os.killpg(pgid,signal.SIGTERM)
        time.sleep(.2)  # Shortened fixture grace, not the production two-second grace.
        os.killpg(pgid,signal.SIGKILL)
        child.wait(timeout=2)
        guardian.atomic(directory/'prototype-terminal.json',{'reason':reason,'deadline':deadline,'direct_child_reaped':True,'enforced_ns':now,'pgid':pgid})
    finally:
        if child.poll() is None:child.kill();child.wait(timeout=2)


@pytest.mark.parametrize('budget,reason',[(.8,'deadline'),(8,'parent-loss')])
def test_parent_loss_retains_original_deadline(tmp_path,budget,reason):
    owner=None;armed={};guard_pid=None
    owner_code=f"""import subprocess,sys,time,uuid
from lib._docgroup_pin import GroupPin
from lib import _docguardian as g
from pathlib import Path
p=Path({str(tmp_path)!r});deadline=time.monotonic_ns()+int({budget}*g.NS)
group=GroupPin(p,uuid.uuid4().hex,deadline)
g.atomic(p/"startup-release.json",{{"run_id":group.run_id}})
command='from tests.a2.test_group_pin import prototype_supervise;prototype_supervise('+repr(str(p))+','+str(group.pgid)+','+str(deadline)+','+str(time.monotonic_ns()+5*g.NS)+')'
worker=subprocess.Popen([sys.executable,'-c',command])
worker.wait();group.finish()
"""
    started=time.monotonic()
    try:
        owner=subprocess.Popen([sys.executable,'-c',owner_code],cwd=ROOT)
        await_file(tmp_path/'prototype-armed.json')
        armed=guardian.read(tmp_path/'prototype-armed.json');guard_pid=armed['guardian_pid']
        assert os.getpgid(guard_pid)!=armed['pgid']
        owner.kill();owner.wait(timeout=2)
        await_file(tmp_path/'prototype-terminal.json',seconds=9)
        terminal=guardian.read(tmp_path/'prototype-terminal.json')
        assert terminal['reason']==reason and terminal['direct_child_reaped']
        assert terminal['deadline']==armed['deadline']
        assert time.monotonic()-started<10
        until=time.monotonic()+2
        while guardian.live_group_members(armed['pgid']) and time.monotonic()<until:time.sleep(.02)
        assert not guardian.live_group_members(armed['pgid'])
    finally:
        if owner and owner.poll() is None:owner.kill();owner.wait(timeout=2)
        if armed.get('pgid') and guardian.live_group_members(armed['pgid']):
            # Fixture-only cleanup while a known live member still holds the group.
            try:os.killpg(armed['pgid'],signal.SIGKILL)
            except ProcessLookupError:pass


def test_pin_stays_armed_past_deadline_until_owner_releases(tmp_path):
    group=GroupPin(tmp_path,uuid.uuid4().hex,time.monotonic_ns()+guardian.NS)
    try:
        time.sleep(1.2)
        assert not guardian.exited_unreaped(group.process)
        group.finish()
        assert group.closed and group.process.returncode==0
    finally:group.finish()



def test_parent_loss_before_startup_release_has_no_orphan_pin(tmp_path):
    code=f"""import time,uuid
from lib._docgroup_pin import GroupPin
from lib import _docguardian as g
GroupPin({str(tmp_path)!r},uuid.uuid4().hex,time.monotonic_ns()+5*g.NS)
time.sleep(30)
"""
    parent=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT)
    ready={}
    try:
        await_file(tmp_path/'pin-ready.json')
        ready=guardian.read(tmp_path/'pin-ready.json')
        assert not (tmp_path/'startup-release.json').exists()
        parent.kill();parent.wait(timeout=2)
        until=time.monotonic()+2
        while guardian.live_group_members(ready['pgid']) and time.monotonic()<until:time.sleep(.02)
        assert not guardian.live_group_members(ready['pgid'])
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=2)
        if ready and guardian.live_group_members(ready['pgid']):
            try:os.killpg(ready['pgid'],signal.SIGKILL)
            except ProcessLookupError:pass

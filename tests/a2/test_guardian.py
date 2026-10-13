import os
import sys
import time
from pathlib import Path
from lib import _docguardian as guardian


def test_native_deadline_and_direct_child_reap(tmp_path):
    command=[sys.executable,"-c","import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"]
    started=time.monotonic()
    result=guardian.run(command,tmp_path,time.monotonic_ns()+150_000_000,cwd=tmp_path)
    assert result["reason"]=="deadline" and result["direct_child_reaped"]
    assert result["kill_sent"] and time.monotonic()-started < 8


def test_handshake_before_package_code(tmp_path):
    command=[sys.executable,"-c","print('hello')"]
    result=guardian.run(command,tmp_path,time.monotonic_ns()+5_000_000_000,cwd=tmp_path)
    assert result["reason"]=="completed" and result["direct_child_reaped"]
    assert result["armed_ns"] < result["completed_ns"]
    assert (tmp_path/"stdout").read_text().strip()=="hello"


def test_expired_budget_no_launch(tmp_path):
    result=guardian.run(["missing-command"],tmp_path,time.monotonic_ns()-1,cwd=tmp_path)
    assert result["reason"]=="deadline" and not result.get("child_pid")


def test_phase_arm_ack_sequence(tmp_path):
    code='''import json,time
from pathlib import Path
p=Path('.')
def write(name,data):
 t=p/(name+'.tmp');t.write_text(json.dumps(data));t.replace(p/name)
for sequence in (1,2):
 write('phase-request.json',{'run_id':json.loads((p/'initial.json').read_text())['run_id'],'sequence':sequence,'phase':'same-chunk','chunk':1})
 while True:
  try:r=json.loads((p/'phase-release.json').read_text())
  except (OSError,ValueError):r={}
  if r.get('sequence')==sequence:break
  time.sleep(.01)
 print(r['deadline_ns'],flush=True)
 time.sleep(.45)
'''
    r=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+5_000_000_000,cwd=tmp_path,chunk_budget=.7)
    assert r['reason']=='deadline'
    deadlines=(tmp_path/'stdout').read_text().splitlines()
    assert len(deadlines)==2 and deadlines[0]==deadlines[1]


def test_parent_loss_preserves_deadline(tmp_path):
    import subprocess
    import signal
    root=Path(guardian.__file__).resolve().parents[1]
    code=f"from lib import _docguardian as g;import time,sys;g.run([sys.executable,'-c','import time;time.sleep(30)'],{str(tmp_path)!r},time.monotonic_ns()+1000000000,cwd={str(tmp_path)!r})"
    parent=subprocess.Popen([sys.executable,'-c',code],cwd=root)
    try:
        limit=time.monotonic()+3
        while time.monotonic()<limit:
            armed=guardian.read(tmp_path/'armed.json') or {}
            if armed.get('child_pid'):break
            time.sleep(.02)
        assert armed.get('child_pid')
        parent.kill();parent.wait(timeout=2)
        limit=time.monotonic()+5
        while time.monotonic()<limit and not (tmp_path/'terminal.json').exists():time.sleep(.02)
        terminal=guardian.read(tmp_path/'terminal.json')
        assert terminal['reason']=='deadline' and terminal['direct_child_reaped']
        assert terminal['global_deadline_ns']==armed['global_deadline_ns']
    finally:
        if parent.poll() is None:parent.kill();parent.wait()
        if armed.get('child_pid'):
            try:os.killpg(armed['child_pid'],signal.SIGKILL)
            except ProcessLookupError:pass


def supervisor(tmp_path,budget,command):
    import subprocess
    import uuid
    run_id=uuid.uuid4().hex;now=time.monotonic_ns()
    guardian.atomic(tmp_path/'initial.json',{'run_id':run_id,'deadline_ns':now+int(budget*guardian.NS),'file_started_ns':now,'file_budget_ns':int(budget*guardian.NS),'chunk_budget_ns':guardian.NS,'command':command,'cwd':str(tmp_path),'env':dict(os.environ)})
    process=subprocess.Popen([sys.executable,'-m','lib._docguardian',str(tmp_path)],cwd=Path(guardian.__file__).resolve().parents[1])
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':run_id})
    return process,run_id


import pytest
@pytest.mark.parametrize('budget,expected',[(.25,'deadline'),(6,'parent-loss')])
def test_heartbeat_age_and_stale_records(tmp_path,budget,expected):
    process,run_id=supervisor(tmp_path,budget,[sys.executable,'-c','import time;time.sleep(30)'])
    guardian.atomic(tmp_path/'heartbeat.json',{'run_id':run_id,'sequence':1,'timestamp':time.monotonic_ns()+100*guardian.NS})
    try:
        process.wait(timeout=9)
        terminal=guardian.read(tmp_path/'terminal.json')
        assert terminal['reason']==expected and terminal['direct_child_reaped']
    finally:
        if process.poll() is None:process.kill();process.wait()


def test_stale_phase_request_does_not_execute(tmp_path):
    guardian.atomic(tmp_path/'phase-request.json',{'run_id':'old-run','sequence':1,'phase':'chunk'})
    result=guardian.run([sys.executable,'-c','import time;time.sleep(.15)'],tmp_path,time.monotonic_ns()+2*guardian.NS,cwd=tmp_path)
    assert result['reason']=='completed' and not (tmp_path/'phase-release.json').exists()


def test_guardian_failure_emergency_cleanup(tmp_path,monkeypatch):
    # Failure before child launch cannot reuse an old run PID.
    guardian.atomic(tmp_path/'armed.json',{'run_id':'old','child_pid':os.getpid()})
    result=guardian.run(['nonexistent-a2-command'],tmp_path,time.monotonic_ns()+guardian.NS,cwd=tmp_path)
    assert result['reason']=='guardian-failure' and not result.get('direct_child_reaped')


def test_deadline_completion_collision(tmp_path):
    result=guardian.run([sys.executable,'-c','import time;time.sleep(.15)'],tmp_path,time.monotonic_ns()+100_000_000,cwd=tmp_path)
    assert result['reason']=='deadline'
    result=guardian.run([sys.executable,'-c','pass'],tmp_path/'fast',time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    assert result['reason']=='completed'


def test_monotonic_clock_and_scheduler_delay(tmp_path):
    result=guardian.run([sys.executable,'-c','import time;time.sleep(30)'],tmp_path,time.monotonic_ns()+150000000,cwd=tmp_path)
    assert result['reason']=='deadline' and result['enforcement_delay_ns']>=0
    assert result['effective_deadline_ns']==result['global_deadline_ns']
    assert result['guardian_pid']!=result['child_pid']


def test_single_termination_owner_idempotence(tmp_path):
    code='''import json,time
from pathlib import Path
p=Path('.')
r=json.loads((p/'initial.json').read_text())['run_id']
t=p/'terminate.tmp';t.write_text(json.dumps({'run_id':r,'reason':'requested'}));t.replace(p/'terminate.json')
time.sleep(30)
'''
    result=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    termination=guardian.read(tmp_path/'termination.json')
    assert result['reason']=='requested' and result['direct_child_reaped']
    assert termination['termination_id']==result['termination_id']
    assert termination['guardian_pid']==result['guardian_pid']


def test_detached_child_and_total_host_loss(tmp_path):
    import subprocess
    import signal
    detached = tmp_path/'detached.pid'
    code = f'import subprocess,sys;from pathlib import Path;p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],start_new_session=True);Path({str(detached)!r}).write_text(str(p.pid))'
    pid = None
    try:
        result = guardian.run([sys.executable,'-c',code],tmp_path/'detached',time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
        pid = int(detached.read_text())
        assert result['reason']=='completed' and result['group_disappeared']
        os.kill(pid,0)  # Detachment is expressly outside the observed group guarantee.
    finally:
        if pid:
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass
    killed = tmp_path/'host-loss'; killed.mkdir()
    process,run_id = supervisor(killed,10,[sys.executable,'-c','import time;time.sleep(30)'])
    guardian.atomic(killed/'marker.json',{'run_id':run_id,'state':'started'})
    armed = {}
    try:
        until = time.monotonic()+3
        while time.monotonic()<until:
            armed = guardian.read(killed/'armed.json') or {}
            if armed.get('child_pid'): break
            time.sleep(.02)
        assert armed.get('child_pid')
        process.kill(); process.wait(timeout=2)
        assert not (killed/'terminal.json').exists()
        assert guardian.read(killed/'marker.json')['state']=='started'
    finally:
        if process.poll() is None: process.kill(); process.wait(timeout=2)
        if armed.get('child_pid'):
            try: os.killpg(armed['child_pid'],signal.SIGKILL)
            except ProcessLookupError: pass


def test_no_exception_signal_after_direct_child_reap(tmp_path, monkeypatch):
    import signal
    import uuid
    run_id=uuid.uuid4().hex; now=time.monotonic_ns()
    guardian.atomic(tmp_path/'initial.json',{'run_id':run_id,'deadline_ns':now+3*guardian.NS,'file_started_ns':now,'file_budget_ns':3*guardian.NS,'chunk_budget_ns':guardian.NS,'command':[sys.executable,'-c','pass'],'cwd':str(tmp_path),'env':dict(os.environ)})
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':run_id})
    original=guardian.live_group_members; probe_failed=False; late_signals=[]
    def members(pid):
        return True if probe_failed else original(pid)
    def signal_group(pid, number):
        nonlocal probe_failed
        if number==0:
            probe_failed=True
            raise PermissionError('simulated group probe failure after reap')
        late_signals.append(number)
    monkeypatch.setattr(guardian,'live_group_members',members)
    monkeypatch.setattr(guardian.os,'killpg',signal_group)
    result=guardian.supervise(tmp_path)
    assert result['reason']=='guardian-failure' and result['direct_child_reaped']
    assert late_signals==[]


def test_lost_phase_ack_never_releases_code(tmp_path,monkeypatch):
    original=guardian.read
    monkeypatch.setattr(guardian,'read',lambda path:None if path.name=='arm-ack.json' else original(path))
    code='''import json,time
from pathlib import Path
p=Path('.')
r=json.loads((p/'initial.json').read_text())['run_id']
t=p/'request.tmp';t.write_text(json.dumps({'run_id':r,'sequence':1,'phase':'chunk','chunk':1}));t.replace(p/'phase-request.json')
while not (p/'phase-release.json').exists():time.sleep(.01)
(p/'executed').write_text('forbidden')
'''
    result=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+guardian.NS,cwd=tmp_path,chunk_budget=.25)
    assert result['reason']=='deadline' and result['direct_child_reaped']
    assert not (tmp_path/'executed').exists() and not (tmp_path/'phase-release.json').exists()


def test_ordinary_group_child_cleanup(tmp_path):
    code='''import subprocess,sys,time
from pathlib import Path
p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
Path('ordinary-child.pid').write_text(str(p.pid))
time.sleep(30)
'''
    result=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+guardian.NS,cwd=tmp_path)
    assert (tmp_path/'ordinary-child.pid').is_file()
    assert result['reason']=='deadline' and result['direct_child_reaped']
    assert result['group_disappeared'] and not guardian.live_group_members(result['child_pid'])

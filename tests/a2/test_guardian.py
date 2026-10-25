import os
import sys
import time
from pathlib import Path
import pytest
from lib import _docguardian as guardian


def test_native_deadline_and_direct_child_reap(tmp_path):
    command=[sys.executable,"-c","import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"]
    started=time.monotonic()
    # Generous deadline: a slow runner must start the child before the deadline fires.
    result=guardian.run(command,tmp_path,time.monotonic_ns()+3_000_000_000,cwd=tmp_path)
    assert result["reason"]=="deadline" and result["direct_child_reaped"]
    assert result["kill_sent"] and time.monotonic()-started < 20


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
 time.sleep(2.0)
'''
    r=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+30_000_000_000,cwd=tmp_path,chunk_budget=3)
    assert r['reason']=='deadline'
    deadlines=(tmp_path/'stdout').read_text().splitlines()
    assert len(deadlines)==2 and deadlines[0]==deadlines[1]


@pytest.mark.parametrize('budget,expected',[(1,'deadline'),(8,'parent-loss')])
def test_parent_loss_preserves_deadline(tmp_path,budget,expected):
    import subprocess
    import signal
    root=Path(guardian.__file__).resolve().parents[1]
    code=f"from lib import _docguardian as g;import time,sys;g.run([sys.executable,'-c','import time;time.sleep(30)'],{str(tmp_path)!r},time.monotonic_ns()+{budget}*g.NS,cwd={str(tmp_path)!r})"
    parent=subprocess.Popen([sys.executable,'-c',code],cwd=root)
    try:
        limit=time.monotonic()+3
        while time.monotonic()<limit:
            armed=guardian.read(tmp_path/'armed.json') or {}
            if armed.get('child_pid'):break
            time.sleep(.02)
        assert armed.get('child_pid')
        parent.kill();parent.wait(timeout=2)
        limit=time.monotonic()+8
        while time.monotonic()<limit and not (tmp_path/'terminal.json').exists():time.sleep(.02)
        terminal=guardian.read(tmp_path/'terminal.json')
        assert terminal['reason']==expected and terminal['direct_child_reaped']
        assert terminal['global_deadline_ns']==armed['global_deadline_ns']
    finally:
        if parent.poll() is None:parent.kill();parent.wait()
        if armed.get('child_pid'):
            try:os.killpg(armed.get('group_pgid',armed['child_pid']),signal.SIGKILL)
            except ProcessLookupError:pass


def supervisor(tmp_path,budget,command):
    import subprocess
    import uuid
    run_id=uuid.uuid4().hex;now=time.monotonic_ns()
    guardian.atomic(tmp_path/'initial.json',{'run_id':run_id,'deadline_ns':now+int(budget*guardian.NS),'file_started_ns':now,'file_budget_ns':int(budget*guardian.NS),'chunk_budget_ns':guardian.NS,'command':command,'cwd':str(tmp_path),'env':dict(os.environ)})
    process=subprocess.Popen([sys.executable,'-m','lib._docguardian',str(tmp_path)],cwd=Path(guardian.__file__).resolve().parents[1])
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':run_id})
    return process,run_id


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
    # Exec failure reaps the trusted launcher and cannot reuse an old run PID.
    guardian.atomic(tmp_path/'armed.json',{'run_id':'old','child_pid':os.getpid()})
    result=guardian.run(['nonexistent-a2-command'],tmp_path,time.monotonic_ns()+guardian.NS,cwd=tmp_path)
    assert result['reason']=='guardian-failure' and result['direct_child_reaped'] and result['pin_reaped']


def test_deadline_completion_collision(tmp_path):
    result=guardian.run([sys.executable,'-c','import time;time.sleep(.15)'],tmp_path,time.monotonic_ns()+100_000_000,cwd=tmp_path)
    assert result['reason']=='deadline'
    result=guardian.run([sys.executable,'-c','pass'],tmp_path/'fast',time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    assert result['reason']=='completed'


def test_monotonic_clock_and_scheduler_delay(tmp_path):
    result=guardian.run([sys.executable,'-c','import time;time.sleep(30)'],tmp_path,time.monotonic_ns()+3_000_000_000,cwd=tmp_path)
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
            try: os.killpg(armed.get('group_pgid',armed['child_pid']),signal.SIGKILL)
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


@pytest.mark.parametrize('fault_sequence',[1,2])
def test_wrong_sequence_ack_blocks_transition(tmp_path,monkeypatch,fault_sequence):
    original=guardian.read
    def stale_ack(path):
        record=original(path)
        if path.name=='arm-ack.json' and record and record.get('sequence')==fault_sequence:
            return {**record,'sequence':record['sequence']+100}
        return record
    monkeypatch.setattr(guardian,'read',stale_ack)
    code='''import json,time
from pathlib import Path
p=Path('.')
r=json.loads((p/'initial.json').read_text())['run_id']
for sequence in (1,2):
 t=p/'request.tmp';t.write_text(json.dumps({'run_id':r,'sequence':sequence,'phase':'chunk','chunk':sequence}));t.replace(p/'phase-request.json')
 while True:
  try:ack=json.loads((p/'phase-release.json').read_text())
  except (OSError,ValueError):ack={}
  if ack.get('run_id')==r and ack.get('sequence')==sequence:break
  time.sleep(.01)
 (p/('executed-'+str(sequence))).write_text('executed')
'''
    result=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+30*guardian.NS,cwd=tmp_path,chunk_budget=3)
    assert result['reason']=='deadline' and result['direct_child_reaped']
    assert not (tmp_path/f'executed-{fault_sequence}').exists()
    if fault_sequence==2:assert (tmp_path/'executed-1').exists()
    request=original(tmp_path/'arm-request.json');ack=original(tmp_path/'arm-ack.json')
    assert request['sequence']==ack['sequence']==fault_sequence
    assert request['run_id']==ack['run_id']==result['run_id']


def local_supervise(tmp_path,command,budget=1):
    import uuid
    now=time.monotonic_ns();run_id=uuid.uuid4().hex
    guardian.atomic(tmp_path/'initial.json',{'run_id':run_id,'deadline_ns':now+int(budget*guardian.NS),'file_started_ns':now,'file_budget_ns':int(budget*guardian.NS),'chunk_budget_ns':guardian.NS,'command':command,'cwd':str(tmp_path),'env':dict(os.environ)})
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':run_id})
    return guardian.supervise(tmp_path)


def test_repeated_requests_record_before_single_term(tmp_path,monkeypatch):
    import signal
    original=guardian.os.killpg;signals=[]
    def observed_signal(pid,number):
        if number in (signal.SIGTERM,signal.SIGKILL):
            record=guardian.read(tmp_path/'termination.json')
            assert record and record['child_pid']==pid and record['termination_id']
            signals.append((number,record['termination_id']))
        return original(pid,number)
    monkeypatch.setattr(guardian.os,'killpg',observed_signal)
    code='''import json,time
from pathlib import Path
p=Path('.')
r=json.loads((p/'initial.json').read_text())['run_id']
for i in range(100):
 t=p/'request.tmp';t.write_text(json.dumps({'run_id':r,'reason':'requested','request':i}));t.replace(p/'terminate.json');time.sleep(.001)
time.sleep(30)
'''
    result=local_supervise(tmp_path,[sys.executable,'-c',code],budget=3)
    assert result['reason']=='requested' and result['direct_child_reaped'] and result['group_disappeared']
    assert signals==[(signal.SIGTERM,result['termination_id'])]


@pytest.mark.parametrize('delay',[0,.15])
def test_wall_clock_and_delayed_poll_do_not_reset_deadline(tmp_path,monkeypatch,delay):
    original=guardian.time.sleep
    monkeypatch.setattr(guardian.time,'time',lambda:(_ for _ in ()).throw(AssertionError('wall clock used')))
    if delay:monkeypatch.setattr(guardian.time,'sleep',lambda seconds:original(max(seconds,delay)))
    result=local_supervise(tmp_path,[sys.executable,'-c','import time;time.sleep(30)'],budget=.2)
    assert result['reason']=='deadline' and result['direct_child_reaped']
    assert result['effective_deadline_ns']==result['global_deadline_ns']
    assert result['enforcement_delay_ns']>=0
    if delay:assert result['enforcement_delay_ns']>0


def test_heartbeat_cadence_and_sequence(tmp_path,monkeypatch):
    original=guardian.atomic;beats=[]
    def observed(path,record):
        if path.name=='heartbeat.json':beats.append((time.monotonic_ns(),record.copy()))
        return original(path,record)
    monkeypatch.setattr(guardian,'atomic',observed)
    result=guardian.run([sys.executable,'-c','import time;time.sleep(1.6)'],tmp_path,time.monotonic_ns()+4*guardian.NS,cwd=tmp_path)
    assert result['reason']=='completed' and result['direct_child_reaped']
    assert len(beats)>=3
    assert [record['sequence'] for _,record in beats]==list(range(1,len(beats)+1))
    assert all(record['run_id']==result['run_id'] for _,record in beats)
    assert all(0<later-earlier<=guardian.NS for (earlier,_),(later,_) in zip(beats,beats[1:]))


def test_simultaneous_heartbeat_and_deadline_expiry(tmp_path,monkeypatch):
    ticks=iter([0]*5)
    monkeypatch.setattr(guardian.time,'monotonic_ns',lambda:next(ticks,5*guardian.NS))
    result=local_supervise(tmp_path,[sys.executable,'-c','import time;time.sleep(30)'],budget=5)
    assert result['reason']=='deadline' and result['direct_child_reaped']
    assert result['global_deadline_ns']==result['effective_deadline_ns']==5*guardian.NS
    assert result['enforcement_delay_ns']==0


def test_live_guardian_death_emergency_owner(tmp_path,monkeypatch):
    import signal
    original_read=guardian.read;original_killpg=guardian.os.killpg
    killed=[];signals=[]
    def lose_guardian(path):
        record=original_read(path)
        if path.name=='armed.json' and record and record.get('child_pid') and not killed:
            os.kill(record['guardian_pid'],signal.SIGKILL);killed.append(record)
        return record
    def emergency(pid,number):
        if number==0:return original_killpg(pid,number)
        assert killed and pid==killed[0]['group_pgid'] and number==signal.SIGKILL
        # run() has reaped its guardian before emergency group signalling.
        import subprocess
        probe=subprocess.run(['ps','-o','stat=','-p',str(killed[0]['guardian_pid'])],capture_output=True,text=True)
        assert not probe.stdout.strip()
        signals.append(pid);return original_killpg(pid,number)
    monkeypatch.setattr(guardian,'read',lose_guardian)
    monkeypatch.setattr(guardian.os,'killpg',emergency)
    result=guardian.run([sys.executable,'-c','import time;time.sleep(30)'],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    assert result['reason']=='guardian-failure' and not result.get('direct_child_reaped')
    assert signals==[killed[0]['group_pgid']]
    assert result['pin_reaped']
    until=time.monotonic()+10
    while guardian.live_group_members(signals[0]) and time.monotonic()<until:time.sleep(.02)
    assert not guardian.live_group_members(signals[0])


@pytest.mark.parametrize('corrupt_checkpoint',[False,True])
def test_guardian_crash_after_reap_keeps_pin_owned(tmp_path,monkeypatch,corrupt_checkpoint):
    import signal
    import subprocess
    original_popen=subprocess.Popen;original_killpg=os.killpg
    unrelated=original_popen([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True)
    pins=[];signals=[]
    def faulting_guardian(command,*args,**kwargs):
        if command[1:3]==['-m','lib._docgroup_pin'] and command[3]=='pin':
            process=original_popen(command,*args,**kwargs);pins.append(process);return process
        if command[1:3]==['-m','lib._docguardian']:
            code=f"""import os,signal
from pathlib import Path
from lib import _docguardian as g
original=g.atomic
p=Path({str(tmp_path)!r})
def write(path,data):
 if path.name=='terminal.json' and data.get('direct_child_reaped'):
  original(p/'reap-before-crash.json',data)
  if {corrupt_checkpoint!r}:
   armed=g.read(p/'armed.json');armed['child_pid']={unrelated.pid};armed['group_pgid']={unrelated.pid};original(p/'armed.json',armed)
  os.kill(os.getpid(),signal.SIGKILL)
 return original(path,data)
g.atomic=write
g.supervise(p)
"""
            return original_popen([sys.executable,'-c',code],*args,**kwargs)
        return original_popen(command,*args,**kwargs)
    def observed(pgid,number):
        if number!=0:
            assert pins and pins[0].returncode is None
            assert pgid==pins[0].pid and pgid!=unrelated.pid
            signals.append((pgid,number))
        return original_killpg(pgid,number)
    monkeypatch.setattr(subprocess,'Popen',faulting_guardian)
    monkeypatch.setattr(os,'killpg',observed)
    try:
        result=guardian.run([sys.executable,'-c','pass'],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
        assert guardian.read(tmp_path/'reap-before-crash.json')['direct_child_reaped']
        assert result['reason']=='guardian-failure' and not result.get('direct_child_reaped')
        assert result['pin_reaped'] and result['group_disappeared']
        assert signals==[(pins[0].pid,signal.SIGKILL)] and unrelated.poll() is None
    finally:
        if unrelated.poll() is None:unrelated.kill();unrelated.wait(timeout=2)



def test_join_launcher_ignores_decoy_lib_in_workload_cwd(tmp_path):
    decoy=tmp_path/'lib';decoy.mkdir()
    (decoy/'__init__.py').write_text("from pathlib import Path;Path('decoy-executed').write_text('unsafe')")
    (decoy/'_docgroup_pin.py').write_text('raise SystemExit(99)')
    result=guardian.run([sys.executable,'-c',"print('safe-workload')"],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    assert result['reason']=='completed'
    assert not (tmp_path/'decoy-executed').exists()
    assert (tmp_path/'stdout').read_text().strip()=='safe-workload'


def test_deadline_before_join_never_executes_workload(tmp_path,monkeypatch):
    import subprocess
    original=subprocess.Popen
    def delayed_guardian(command,*args,**kwargs):
        if command[1:3]==['-m','lib._docguardian']:
            code=f"""from lib import _docguardian as g
import os
original=os.posix_spawn
def launch(path,command,*args,**kwargs):
 command=list(command)
 command[4]={('import time;from pathlib import Path;Path('+repr(str(tmp_path/'prejoin-entered'))+').write_text("entered");time.sleep(3)'+chr(10))!r}+command[4]
 return original(path,command,*args,**kwargs)
os.posix_spawn=launch
g.supervise({str(tmp_path)!r})
"""
            return original([sys.executable,'-c',code],*args,**kwargs)
        return original(command,*args,**kwargs)
    monkeypatch.setattr(subprocess,'Popen',delayed_guardian)
    started=time.monotonic()
    result=guardian.run([sys.executable,'-c',"from pathlib import Path;Path('workload-executed').write_text('unsafe');import time;time.sleep(30)"],tmp_path,time.monotonic_ns()+1.5*guardian.NS,cwd=tmp_path)
    assert (tmp_path/'prejoin-entered').exists()
    assert not (tmp_path/'workload-executed').exists()
    assert result['reason']=='deadline' and result['direct_child_reaped'] and result['group_disappeared']
    assert time.monotonic()-started<8


@pytest.mark.parametrize('target',['pin','guardian'])
def test_interrupt_after_launch_tracks_and_reaps_child(tmp_path,monkeypatch,target):
    import signal
    import subprocess
    # A background job inherits SIGINT as SIG_IGN, which would stop Python raising KeyboardInterrupt.
    monkeypatch.setattr(signal,'getsignal',signal.getsignal)
    signal.signal(signal.SIGINT,signal.default_int_handler)
    original=subprocess.Popen
    children=[]
    def interrupt(command,*args,**kwargs):
        process=original(command,*args,**kwargs)
        if command[1:3] in (['-m','lib._docgroup_pin'],['-m','lib._docguardian']):
            children.append(process)
            matched=command[2]==('lib._docgroup_pin' if target=='pin' else 'lib._docguardian')
            if matched:os.kill(os.getpid(),signal.SIGINT)
        return process
    monkeypatch.setattr(subprocess,'Popen',interrupt)
    with pytest.raises(KeyboardInterrupt):
        guardian.run([sys.executable,'-c',"from pathlib import Path;Path('unexpected-workload').touch()"],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    assert children and all(child.poll() is not None for child in children)
    assert not (tmp_path/'unexpected-workload').exists()



def test_parent_absent_repeated_probe_failure_still_kills_and_reaps(tmp_path):
    import signal
    import subprocess
    root=Path(guardian.__file__).resolve().parents[1]
    code=f"""import subprocess,sys,time
from lib import _docguardian as g
original=subprocess.Popen
def launch(command,*args,**kwargs):
 if command[1:3]==['-m','lib._docguardian']:
  replacement="from lib import _docguardian as g;import subprocess;g.live_group_members=lambda *a,**k:(_ for _ in ()).throw(subprocess.CalledProcessError(1,'ps'));g.supervise("+repr(command[3])+")"
  command=[sys.executable,'-c',replacement]
 return original(command,*args,**kwargs)
subprocess.Popen=launch
g.run([sys.executable,'-c',"from pathlib import Path;import time;Path('workload-live').touch();time.sleep(30)"],{str(tmp_path)!r},time.monotonic_ns()+2*g.NS,cwd={str(tmp_path)!r})
"""
    parent=subprocess.Popen([sys.executable,'-c',code],cwd=root)
    armed={}
    try:
        until=time.monotonic()+3
        while not (tmp_path/'workload-live').exists() and time.monotonic()<until:time.sleep(.02)
        assert (tmp_path/'workload-live').exists()
        armed=guardian.read(tmp_path/'armed.json')
        parent.kill();parent.wait(timeout=2)
        until=time.monotonic()+8
        while not (tmp_path/'terminal.json').exists() and time.monotonic()<until:time.sleep(.02)
        terminal=guardian.read(tmp_path/'terminal.json')
        assert terminal['reason'] in ('guardian-failure','cleanup-unverified')
        assert terminal['global_deadline_ns']==armed['global_deadline_ns']
        assert terminal['direct_child_reaped'] and terminal['kill_sent']
        until=time.monotonic()+2
        while guardian.live_group_members(armed['group_pgid']) and time.monotonic()<until:time.sleep(.02)
        assert not guardian.live_group_members(armed['group_pgid'])
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=2)
        if armed and guardian.live_group_members(armed['group_pgid']):
            try:os.killpg(armed['group_pgid'],signal.SIGKILL)
            except ProcessLookupError:pass


def test_pending_workload_sigint_retains_direct_child_handle(tmp_path,monkeypatch):
    import signal
    from lib._docgroup_pin import GroupPin
    group=GroupPin(tmp_path,'interrupt-workload',time.monotonic_ns()+5*guardian.NS)
    now=time.monotonic_ns();children=[]
    guardian.atomic(tmp_path/'initial.json',{'run_id':group.run_id,'parent_pid':os.getppid(),'group_pgid':group.pgid,'deadline_ns':now+3*guardian.NS,'file_started_ns':now,'file_budget_ns':3*guardian.NS,'chunk_budget_ns':guardian.NS,'command':[sys.executable,'-c','import time;time.sleep(30)'],'cwd':str(tmp_path),'env':dict(os.environ)})
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':group.run_id})
    original=os.posix_spawn
    def interrupt(*args,**kwargs):
        assert signal.SIGINT not in kwargs["setsigmask"]
        pid=original(*args,**kwargs);children.append(pid)
        os.kill(os.getpid(),signal.SIGINT)
        return pid
    monkeypatch.setattr(os,'posix_spawn',interrupt)
    try:
        result=guardian.supervise(tmp_path)
        assert result['reason']=='guardian-failure' and result['direct_child_reaped']
        with pytest.raises(ChildProcessError):os.waitpid(children[0],os.WNOHANG)
    finally:
        group.finish()
        for pid in children:
            try:os.waitpid(pid,0)
            except ChildProcessError:pass


def test_interrupt_after_pin_constructor_enters_cleanup(tmp_path):
    from lib._docgroup_pin import GroupPin
    pins=[]
    def interrupt(frame,event,arg):
        if frame.f_code is guardian.run.__code__ and event=='line':
            pin=frame.f_locals.get('pin')
            if isinstance(pin,GroupPin) and not pins:
                pins.append(pin)
                raise KeyboardInterrupt
        return interrupt
    previous=sys.gettrace()
    try:
        sys.settrace(interrupt)
        with pytest.raises(KeyboardInterrupt):
            guardian.run([sys.executable,'-c','pass'],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    finally:
        sys.settrace(previous)
        for pin in pins:
            leaked=not pin.closed
            pin.finish()
    assert pins and not leaked and pins[0].process.returncode is not None


def test_nul_command_fails_before_bootstrap_without_success(tmp_path):
    result=guardian.run(['invalid\x00command'],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    assert result['reason']=='guardian-failure' and not result.get('child_pid')
    assert result['pin_reaped'] and not (tmp_path/'launch-error.json').exists()


def test_prestart_interrupt_never_signals_reaped_pin(tmp_path, monkeypatch):
    import signal
    from lib._docgroup_pin import GroupPin
    group = GroupPin(tmp_path, 'prestart', time.monotonic_ns()+5*guardian.NS)
    pgid = group.pgid
    group.finish()
    now = time.monotonic_ns()
    guardian.atomic(tmp_path/'initial.json', {'run_id':'prestart','parent_pid':os.getppid(),
        'group_pgid':pgid,'deadline_ns':now+guardian.NS,'file_started_ns':now,
        'file_budget_ns':guardian.NS})
    original = guardian.read
    signals = []
    def interrupt(path):
        if path.name == 'heartbeat.json':
            os.kill(os.getpid(), signal.SIGINT)
        return original(path)
    monkeypatch.setattr(guardian, 'read', interrupt)
    monkeypatch.setattr(os, 'killpg', lambda *args: signals.append(args))
    result = guardian.supervise(tmp_path)
    assert result['reason'] == 'guardian-failure'
    assert not result['direct_child_reaped'] and not signals


def test_handle_allocation_failure_precedes_spawn(tmp_path, monkeypatch):
    from lib import _docgroup_pin as pin
    calls = []
    def fail(pid):
        raise MemoryError('handle allocation')
    monkeypatch.setattr(pin, 'SpawnedProcess', fail)
    monkeypatch.setattr(os, 'posix_spawn', lambda *a, **kw: calls.append(a) or 123)
    with (tmp_path/'out').open('wb') as stream:
        with pytest.raises(MemoryError):
            pin.spawn_in_group(123, [sys.executable, '-c', 'pass'], tmp_path,
                'allocation', time.monotonic_ns()+guardian.NS, tmp_path,
                dict(os.environ), stream, stream)
    assert not calls


@pytest.mark.parametrize('code,expected',[("import os,signal;os.kill(os.getpid(),signal.SIGKILL)",'killed'),("import sys;sys.exit(3)",'exited-nonzero')])
def test_workload_that_dies_or_fails_is_not_reported_completed(tmp_path,code,expected):
    result=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+10*guardian.NS,cwd=tmp_path)
    assert result['reason']==f'workload-{expected}'
    assert guardian.read(tmp_path/'marker.json')['state']=='interrupted'


def test_clean_exit_is_still_completed(tmp_path):
    result=guardian.run([sys.executable,'-c','pass'],tmp_path,time.monotonic_ns()+10*guardian.NS,cwd=tmp_path)
    assert result['reason']=='completed' and guardian.read(tmp_path/'marker.json')['state']=='completed'


def test_parent_interrupt_leaves_an_interrupted_marker(tmp_path,monkeypatch):
    import signal
    import subprocess
    signal.signal(signal.SIGINT,signal.default_int_handler)
    original=subprocess.Popen
    def interrupt(command,*args,**kwargs):
        process=original(command,*args,**kwargs)
        if command[1:3]==['-m','lib._docguardian']:os.kill(os.getpid(),signal.SIGINT)
        return process
    monkeypatch.setattr(subprocess,'Popen',interrupt)
    with pytest.raises(KeyboardInterrupt):
        guardian.run([sys.executable,'-c','pass'],tmp_path,time.monotonic_ns()+3*guardian.NS,cwd=tmp_path)
    marker=guardian.read(tmp_path/'marker.json')
    assert marker and marker['state']=='interrupted'


def _initial(tmp_path,command,budget):
    import uuid
    now=time.monotonic_ns();run_id=uuid.uuid4().hex
    guardian.atomic(tmp_path/'initial.json',{'run_id':run_id,'deadline_ns':now+int(budget*guardian.NS),'file_started_ns':now,'file_budget_ns':int(budget*guardian.NS),'chunk_budget_ns':guardian.NS,'command':command,'cwd':str(tmp_path),'env':dict(os.environ)})
    return run_id


def test_stale_startup_release_never_starts_the_workload(tmp_path):
    _initial(tmp_path,[sys.executable,'-c',"from pathlib import Path;Path('started').touch()"],1)
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':'someone-elses-run'})
    guardian.supervise(tmp_path)
    assert not (tmp_path/'started').exists()


def test_stale_terminate_record_is_ignored(tmp_path):
    run_id=_initial(tmp_path,[sys.executable,'-c','import time;time.sleep(1)'],20)
    guardian.atomic(tmp_path/'startup-release.json',{'run_id':run_id})
    guardian.atomic(tmp_path/'terminate.json',{'run_id':'someone-elses-run','reason':'requested'})
    assert guardian.supervise(tmp_path)['reason']=='completed'


def test_probe_timeouts_tolerate_a_loaded_runner():
    import inspect
    source=inspect.getsource(guardian)
    assert 'timeout=1)' not in source and 'timeout=1,' not in source


@pytest.mark.parametrize('forge',['wrong-run-id','wrong-sequence'])
def test_forged_phase_ack_never_releases_code(tmp_path,monkeypatch,forge):
    # Only the parent-side comparison can reject this: the real guardian's own (correct) ack is hidden from the parent.
    original=guardian.read
    def read(path):
        if path.name!='arm-ack.json':return original(path)
        initial=original(path.parent/'initial.json')
        if initial is None:return None
        run_id=initial['run_id'] if forge=='wrong-sequence' else 'not-'+initial['run_id']
        return {'run_id':run_id,'sequence':99 if forge=='wrong-sequence' else 1,'deadline_ns':time.monotonic_ns()+60*guardian.NS}
    monkeypatch.setattr(guardian,'read',read)
    code='''import json,time
from pathlib import Path
p=Path('.')
r=json.loads((p/'initial.json').read_text())['run_id']
t=p/'request.tmp';t.write_text(json.dumps({'run_id':r,'sequence':1,'phase':'chunk','chunk':1}));t.replace(p/'phase-request.json')
while not (p/'phase-release.json').exists():time.sleep(.01)
(p/'executed').write_text('forbidden')
'''
    result=guardian.run([sys.executable,'-c',code],tmp_path,time.monotonic_ns()+guardian.NS,cwd=tmp_path,chunk_budget=.25)
    assert result['reason']=='deadline'
    assert not (tmp_path/'executed').exists() and not (tmp_path/'phase-release.json').exists()


def test_completed_run_with_live_group_fails_closed(tmp_path,monkeypatch):
    original=guardian.os.killpg
    monkeypatch.setattr(guardian.os,'killpg',lambda pgid,number:None if number==0 else original(pgid,number))
    result=guardian.run([sys.executable,'-c','pass'],tmp_path,time.monotonic_ns()+5*guardian.NS,cwd=tmp_path)
    assert result['group_disappeared'] is False
    assert result['reason']=='cleanup-unverified'
    assert guardian.read(tmp_path/'terminal.json')['reason']=='cleanup-unverified'
    assert guardian.read(tmp_path/'marker.json')['state']=='interrupted'


def test_live_guardian_pin_is_retained_unreaped(tmp_path,monkeypatch):
    import signal
    class LiveGuardian:
        def poll(self):return None
        def wait(self,timeout=None):return None
        def kill(self):pass
    original=guardian.read
    def read(path):
        if path.name=='armed.json':raise RuntimeError('simulated parent failure')
        return original(path)
    pins=[]
    monkeypatch.setattr(guardian,'_UNREAPED_PINS',pins)
    popen=guardian.subprocess.Popen
    monkeypatch.setattr(guardian.subprocess,'Popen',lambda args,*a,**k:LiveGuardian() if 'lib._docguardian' in args else popen(args,*a,**k))
    monkeypatch.setattr(guardian,'read',read)
    try:
        with pytest.raises(RuntimeError,match='simulated parent failure'):
            guardian.run([sys.executable,'-c','pass'],tmp_path,time.monotonic_ns()+5*guardian.NS,cwd=tmp_path)
        assert len(pins)==1 and pins[0].process.returncode is None
    finally:
        for pin in pins:
            pin.signal_group(signal.SIGKILL); pin.finish()

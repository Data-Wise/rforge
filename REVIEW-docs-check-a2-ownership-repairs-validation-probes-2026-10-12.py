"""Reproduce review boundaries without production edits or actual PGID reuse."""
import os,signal,subprocess,sys,time,uuid
from pathlib import Path
import pytest
from lib import _docguardian as g, _docgroup_pin as pinmod, _docexamples as examples, docaudit
from tests.a2.helpers import package


def initial(directory,run_id,pgid=None):
    now=time.monotonic_ns()
    data=dict(run_id=run_id,deadline_ns=now+g.NS,file_started_ns=now,file_budget_ns=g.NS,chunk_budget_ns=g.NS,command=[sys.executable,'-c','pass'],cwd=str(directory),env=dict(os.environ))
    if pgid is not None:data.update(group_pgid=pgid,parent_pid=os.getppid())
    g.atomic(directory/'initial.json',data)


def test_pre_spawn_exception_attempts_signal_after_pin_reap(tmp_path,monkeypatch):
    run_id=uuid.uuid4().hex
    pin=pinmod.GroupPin(tmp_path,run_id,time.monotonic_ns()+3*g.NS)
    pgid=pin.pgid
    pin.finish()
    assert pin.closed and pin.process.returncode is not None
    initial(tmp_path,run_id,pgid)
    original=g.read;signals=[]
    def fault(path):
        if path.name=='heartbeat.json':os.kill(os.getpid(),signal.SIGINT)
        return original(path)
    monkeypatch.setattr(g,'read',fault)
    # Observe the unsafe request; do not signal a possibly reused numeric group.
    monkeypatch.setattr(g.os,'killpg',lambda pgid,number:signals.append((pgid,number)))
    result=g.supervise(tmp_path)
    assert result['reason']=='guardian-failure' and not result.get('child_pid')
    assert signals==[(pgid,signal.SIGKILL)]


def test_single_post_reap_probe_failure_is_incomplete_without_survivors(tmp_path,monkeypatch):
    run_id=uuid.uuid4().hex
    pin=pinmod.GroupPin(tmp_path,run_id,time.monotonic_ns()+3*g.NS)
    initial(tmp_path,run_id,pin.pgid)
    g.atomic(tmp_path/'startup-release.json',{'run_id':run_id})
    real_members=g.live_group_members;real_kill=g.os.killpg;calls=[];probes=[]
    def members(*a,**k):
        probes.append(real_members(*a,**k))
        if len(probes)==2:raise subprocess.CalledProcessError(1,'ps')
        return probes[-1]
    def observe(pgid,number):calls.append(number);return real_kill(pgid,number)
    monkeypatch.setattr(g,'live_group_members',members)
    monkeypatch.setattr(g.os,'killpg',observe)
    try:
        result=g.supervise(tmp_path)
        assert probes==[False,False]
        assert result['reason']=='guardian-failure' and result['direct_child_reaped']
        assert not calls and not real_members(pin.pgid,exclude_pid=pin.pgid)
    finally:pin.finish()


@pytest.mark.parametrize('interruption',[False,True])
def test_production_boundary_loses_lifecycle_and_known_counts(tmp_path,monkeypatch,interruption):
    root=package(tmp_path/'pkg',readme='```r\n1\n#> [1] 1\n```\n')
    segments,_,_,_=examples.extract(root/"README.md")
    assert sum(bool(s["expected"]) and s["execute"] and s["visible"] for s in segments)==1
    directories=[]
    monkeypatch.setattr(examples.shutil,'which',lambda name:sys.executable)
    def fail(command,directory,*a,**k):
        directories.append(Path(directory))
        g.atomic(Path(directory)/'terminal.json',{'reason':'cleanup-unverified','cleanup_error':'probe-failed'})
        if interruption:raise KeyboardInterrupt
        raise OSError('controlled run failure')
    monkeypatch.setattr(g,'run',fail)
    if interruption:
        with pytest.raises(KeyboardInterrupt):docaudit.audit(root,run_examples=True)
    else:
        result=docaudit.audit(root,run_examples=True)
        stage=result['stages']['examples']
        assert result['incomplete'] and stage['state']=='unavailable'
        assert stage['counts']=={} and 'provenance' not in stage
        assert docaudit.exit_code(result,'warn')==docaudit.exit_code(result,'error')==2
    assert directories and not directories[0].exists()


def test_pin_ready_interrupt_is_deferred_bounded_and_never_launches_workload(tmp_path,monkeypatch):
    real_popen=subprocess.Popen;children=[]
    monkeypatch.setattr(pinmod,'read',lambda path:None)
    def interrupt(command,*a,**k):
        child=real_popen(command,*a,**k);children.append(child)
        os.kill(os.getpid(),signal.SIGINT)
        return child
    monkeypatch.setattr(subprocess,'Popen',interrupt)
    started=time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        g.run([sys.executable,'-c',"from pathlib import Path;Path('executed').touch()"],tmp_path,time.monotonic_ns()+.3*g.NS,cwd=tmp_path)
    elapsed=time.monotonic()-started
    assert .25<=elapsed<2
    assert len(children)==1 and children[0].poll() is not None
    assert not (tmp_path/'executed').exists()

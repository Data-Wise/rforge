"""Independent POSIX guardian: sole normal group-termination and direct-child owner."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

NS = 1_000_000_000
OUTPUT_LIMIT = 10 * 1024 * 1024
# Retain ownership if an uninterruptible guardian cannot be observed dead.
_UNREAPED_PINS = []


def atomic(path, data):
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def exited_unreaped(process):
    """Observe exit without releasing the leader PID before group signalling."""
    if hasattr(os, "waitid"):
        return os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    # macOS Python omits waitid; ps exposes zombie state without reaping it.
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(process.pid)],
                            capture_output=True, text=True, timeout=1)
    state = result.stdout.strip()
    if not state:
        raise RuntimeError("owned child lifetime could not be verified")
    return state.startswith("Z")


def live_group_members(pgid, exclude_pid=None):
    result = subprocess.run(["ps", "-e", "-o", "pgid=", "-o", "pid=", "-o", "stat="],
                            capture_output=True, text=True, timeout=1, check=True)
    return any(fields[0] == str(pgid) and fields[1] != str(exclude_pid) and not fields[2].startswith("Z")
               for line in result.stdout.splitlines() if len(fields := line.split()) >= 3)


def supervise(directory):
    directory = Path(directory)
    initial = read(directory / "initial.json")
    if "signal_mask" in initial:
        signal.pthread_sigmask(signal.SIG_SETMASK, initial["signal_mask"])
    run_id = initial["run_id"]
    deadline = initial["deadline_ns"]
    phase_deadline = min(deadline, initial["file_started_ns"] + initial["file_budget_ns"])
    status = {"run_id":run_id,"armed_ns":time.monotonic_ns(),"global_deadline_ns":deadline,
              "guardian_pid":os.getpid(),"effective_deadline_ns":phase_deadline,"reason":"deadline","direct_child_reaped":False,"kill_sent":False,"phase":"startup"}
    atomic(directory / "armed.json", status)
    process = None
    pgid = initial.get("group_pgid")
    if pgid is not None: status["group_pgid"] = pgid
    def workload_alive():
        return live_group_members(pgid, exclude_pid=pgid) if pgid is not None else live_group_members(process.pid)
    streams = []
    heartbeat_sequence = None
    heartbeat_time = time.monotonic_ns()
    request_sequence = None
    chunk_deadlines = {}
    release = None
    try:
        while time.monotonic_ns() < phase_deadline:
            heartbeat = read(directory / "heartbeat.json")
            if heartbeat and heartbeat.get("run_id") == run_id and heartbeat.get("sequence") != heartbeat_sequence:
                heartbeat_sequence = heartbeat["sequence"]; heartbeat_time = time.monotonic_ns()
            release = read(directory / "startup-release.json")
            if release and release.get("run_id") == run_id:
                break
            if time.monotonic_ns() - heartbeat_time >= 5 * NS:
                status["reason"] = "parent-loss"
                break
            time.sleep(0.05)
        if release and release.get("run_id") == run_id and time.monotonic_ns() < phase_deadline:
            for name in ("stdout", "stderr"):
                streams.append((directory / name).open("wb"))
            command = initial["command"]
            if pgid is not None:
                from ._docgroup_pin import spawn_in_group, defer_launch_signals
                with defer_launch_signals() as previous:
                    process = spawn_in_group(pgid, command, directory, run_id, phase_deadline,
                                             initial["cwd"], initial["env"], *streams, signal_mask=previous)
            else:
                process = subprocess.Popen(command, cwd=initial["cwd"], env=initial["env"],
                                           stdout=streams[0], stderr=streams[1], start_new_session=True)
            status["child_pid"] = process.pid
            atomic(directory / "armed.json", status)
        while process is not None:
            now = time.monotonic_ns()
            heartbeat = read(directory / "heartbeat.json")
            if heartbeat and heartbeat.get("run_id") == run_id and heartbeat.get("sequence") != heartbeat_sequence:
                heartbeat_sequence = heartbeat["sequence"]; heartbeat_time = now
            payload = read(directory / "payload.json") or {}
            native = sum((directory/name).stat().st_size for name in ("stdout","stderr"))
            spool = directory / "evaluate-text"
            total = native + (spool.stat().st_size if spool.exists() else 0) + max(0, int(payload.get("bytes",0)))
            # Deadline always wins over observing a completion in the same poll.
            if now >= phase_deadline:
                status.update(reason="deadline",enforcement_delay_ns=max(0,now-phase_deadline)); break
            if now - heartbeat_time >= 5 * NS:
                status["reason"] = "parent-loss"; break
            if total > OUTPUT_LIMIT:
                status.update(reason="output-limit", observed_output_bytes=total); break
            termination = read(directory/"terminate.json")
            if termination and termination.get("run_id") == run_id:
                status["reason"] = termination.get("reason","requested"); break
            req = read(directory/"arm-request.json")
            if req and req.get("run_id") == run_id and req.get("sequence") != request_sequence:
                request_sequence = req["sequence"]
                chunk = req.get("chunk", req["phase"])
                if req["phase"] == "loading":
                    phase_deadline = min(deadline, initial["file_started_ns"]+initial["file_budget_ns"])
                else:
                    chunk_deadlines.setdefault(chunk, now + initial["chunk_budget_ns"])
                    phase_deadline = min(deadline, initial["file_started_ns"]+initial["file_budget_ns"], chunk_deadlines[chunk])
                status["phase"] = req["phase"]
                status["effective_deadline_ns"] = phase_deadline
                atomic(directory/"marker.json",{"run_id":run_id,"state":"started","phase":req["phase"]})
                atomic(directory/"arm-ack.json", {"run_id":run_id,"sequence":request_sequence,"start_ns":now,"deadline_ns":phase_deadline})
            if exited_unreaped(process):
                completed = time.monotonic_ns()
                status.update(reason="deadline" if completed >= phase_deadline else "completed", completed_ns=completed)
                break
            time.sleep(0.05)
        if process is not None:
            group_alive = workload_alive()
            if group_alive:
                status.update(termination_id=uuid.uuid4().hex,termination_ns=time.monotonic_ns())
                atomic(directory/"termination.json", status)
                try:
                    os.killpg(pgid or process.pid,signal.SIGTERM)
                except ProcessLookupError:
                    pass
                grace = time.monotonic() + 2
                while time.monotonic() < grace:
                    if not workload_alive():
                        break
                    time.sleep(0.05)
                try:
                    if workload_alive():
                        os.killpg(pgid or process.pid,signal.SIGKILL);status["kill_sent"] = True
                except ProcessLookupError:
                    pass
            # Direct-child reap and group disappearance are separate observations.
            try:
                status["returncode"] = process.wait(timeout=5);status["direct_child_reaped"] = True
            except subprocess.TimeoutExpired:
                status["reason"] = "cleanup-unverified"
            launch_error = read(directory / "launch-error.json")
            if launch_error and launch_error.get("run_id") == run_id:
                status.update(reason="guardian-failure", error=launch_error["error"])
            if pgid is not None:
                status["workload_disappeared"] = not workload_alive()
            if pgid is not None:
                # The parent still owns the pin; only it can finalize this probe
                # after reaping that child. macOS may return EPERM for zombies.
                status["group_disappeared"] = False
            else:
                try:
                    os.killpg(process.pid,0);status["group_disappeared"] = False
                except ProcessLookupError:
                    status["group_disappeared"] = True
            if pgid is None and not status["group_disappeared"] or pgid is not None and not status.get("workload_disappeared"):
                status["reason"] = "cleanup-unverified"
    except BaseException as exc:
        status.update(reason="guardian-failure",error=str(exc))
        # Before spawn, a checkpoint PGID is not an owned signal capability.
        if process is not None and not status.get("direct_child_reaped"):
            try:
                # The direct child is still unreaped: its PID reserves identity.
                # A failed probe must not disable cleanup when the parent is gone.
                os.killpg(pgid or process.pid,signal.SIGKILL)
                status["kill_sent"] = True
            except OSError as cleanup_error:
                status["cleanup_error"] = str(cleanup_error)
            try:
                process.wait(timeout=5)
                status["direct_child_reaped"] = True
            except (OSError,subprocess.SubprocessError) as cleanup_error:
                status["cleanup_error"] = str(cleanup_error)
    finally:
        for stream in streams:
            stream.close()
        if pgid is not None:
            # No destructive group signal is allowed beyond this ownership release.
            atomic(directory / "pin-release.json", {"run_id": run_id})
            if os.getppid() != initial["parent_pid"]:
                until = time.monotonic() + 2
                while time.monotonic() < until:
                    try:os.killpg(pgid, 0)
                    except ProcessLookupError:
                        status["group_disappeared"] = True; break
                    except PermissionError:
                        pass  # Not evidence of disappearance; await the orphan reap.
                    time.sleep(.02)
                if not status.get("group_disappeared"):status["reason"] = "cleanup-unverified"
        atomic(directory/"terminal.json",status)
    return status


def run(command, directory, deadline, *, cwd, env=None, file_budget=300, chunk_budget=60):
    directory = Path(directory); directory.mkdir(parents=True,exist_ok=True)
    run_id = uuid.uuid4().hex
    inherited = dict(os.environ) if env is None else dict(env)
    package_root = str(Path(__file__).resolve().parent.parent)
    inherited["PYTHONPATH"] = package_root + os.pathsep + inherited.get("PYTHONPATH", "")
    initial = {"run_id":run_id,"deadline_ns":deadline,"file_started_ns":time.monotonic_ns(),"file_budget_ns":int(file_budget*NS),
               "chunk_budget_ns":int(chunk_budget*NS),"command":command,"cwd":str(cwd),"env":inherited}
    input_data=read(directory/"input.json")
    if input_data is not None:
        input_data["run_id"]=run_id
        atomic(directory/"input.json",input_data)
    atomic(directory/"marker.json",{"run_id":run_id,"state":"started"})
    startup_deadline = min(deadline, initial["file_started_ns"] + initial["file_budget_ns"])
    startup_status = {"run_id":run_id,"reason":"deadline","phase":"startup",
                      "global_deadline_ns":deadline,"effective_deadline_ns":startup_deadline,
                      "direct_child_reaped":False,"kill_sent":False}
    atomic(directory/"initial.json",initial)
    if time.monotonic_ns() >= startup_deadline:
        terminal = dict(startup_status)
        atomic(directory/"marker.json",{"run_id":run_id,"state":"interrupted"})
        return terminal
    from ._docgroup_pin import GroupPin, defer_launch_signals
    pin = None; guardian = None; terminal = None
    sequence = 0; last_heartbeat = 0; phase_sequence = None
    try:
        try:
            with defer_launch_signals() as previous:
                pin = GroupPin(directory, run_id, startup_deadline, signal_mask=previous)
        except TimeoutError as exc:
            terminal = dict(startup_status, reason="deadline" if time.monotonic_ns() >= startup_deadline else "guardian-failure", error=str(exc), pin_reaped=True)
            atomic(directory/"marker.json",{"run_id":run_id,"state":"interrupted"})
            return terminal
        initial.update(group_pgid=pin.pgid, parent_pid=os.getpid())
        atomic(directory/"initial.json",initial)
        from ._docgroup_pin import defer_launch_signals
        with defer_launch_signals() as previous:
            initial["signal_mask"] = list(previous)
            atomic(directory/"initial.json",initial)
            guardian = subprocess.Popen([sys.executable,"-m","lib._docguardian",str(directory)],cwd=package_root,
                                        env=inherited,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        while guardian.poll() is None:
            now = time.monotonic_ns()
            if now-last_heartbeat >= NS//2:
                sequence += 1;last_heartbeat = now
                atomic(directory/"heartbeat.json",{"run_id":run_id,"sequence":sequence})
            armed = read(directory/"armed.json")
            if armed and armed.get("run_id") == run_id:
                atomic(directory/"startup-release.json", {"run_id":run_id})
            phase = read(directory/"phase-request.json")
            if phase and phase.get("run_id") == run_id and phase.get("sequence") != phase_sequence:
                phase_sequence = phase["sequence"]
                atomic(directory/"arm-request.json",{"run_id":run_id,"sequence":phase_sequence,"phase":phase["phase"],"chunk":phase.get("chunk",phase["phase"])})
            ack = read(directory/"arm-ack.json")
            if ack and ack.get("run_id") == run_id and ack.get("sequence") == phase_sequence:
                if now < ack["deadline_ns"]:
                    atomic(directory/"phase-release.json",ack)
                else:
                    atomic(directory/"terminate.json",{"run_id":run_id,"reason":"deadline"})
            if now > deadline + 12*NS:
                guardian.kill();break
            time.sleep(0.05)
        guardian.wait(timeout=5)
        terminal = read(directory/"terminal.json")
        if not isinstance(terminal, dict) or terminal.get("run_id") != run_id:
            terminal = {"reason":"guardian-failure","run_id":run_id}
        if terminal.get("reason") in ("guardian-failure", "cleanup-unverified"):
            # The guardian is observed dead; use our unreaped direct pin child,
            # never the integer child_pid read from a checkpoint.
            try:pin.signal_group(signal.SIGKILL)
            except OSError as exc:terminal["cleanup_error"] = str(exc)
    finally:
        try:
            if guardian is not None and guardian.poll() is None:
                try:
                    atomic(directory/"terminate.json", {"run_id":run_id,"reason":"parent-interrupted"})
                except OSError:
                    guardian.kill()
                try:
                    guardian.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    guardian.kill();guardian.wait(timeout=5)
                    try:pin.signal_group(signal.SIGKILL)
                    except OSError:pass
            if terminal is None and guardian is not None and guardian.poll() is not None:
                try:pin.signal_group(signal.SIGKILL)
                except OSError:pass
        finally:
            if guardian is not None and guardian.poll() is None:
                # Do not release/reap while a guardian can still issue signals.
                _UNREAPED_PINS.append(pin)
            elif pin is not None:
                pin.finish()
    if terminal is not None:
        terminal.update(group_pgid=pin.pgid, pin_reaped=pin.process.returncode is not None)
        try:
            os.killpg(pin.pgid,0); terminal["group_disappeared"] = False
        except ProcessLookupError:
            terminal["group_disappeared"] = True
        except PermissionError:
            terminal["group_disappeared"] = False
        if not terminal["group_disappeared"] and terminal["reason"] == "completed":
            terminal["reason"] = "cleanup-unverified"
        atomic(directory/"terminal.json",terminal)
        atomic(directory/"marker.json",{"run_id":run_id,"state":"completed" if terminal["reason"]=="completed" else "interrupted","phase":terminal.get("phase")})
    return terminal


if __name__ == "__main__":
    supervise(sys.argv[1])

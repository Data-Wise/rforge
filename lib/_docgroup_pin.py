"""A2 process-group ownership pin for parent emergency cleanup.

The parent retains its direct pin child unreaped until all group signals finish.
The guardian remains the workload parent and normal termination owner. Assign the group atomically in
a POSIX spawn launcher to support Python 3.10 without preexec_fn in a threaded caller.
"""
from __future__ import annotations

import os
import json
from contextlib import contextmanager
import signal
import subprocess
import sys
import time
from pathlib import Path

from ._docguardian import NS, atomic, read



@contextmanager
def defer_launch_signals():
    """Assign child ownership before delivering a pending interruption."""
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM, signal.SIGHUP})
    try:
        yield previous
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, previous)


_LAUNCH = """import os,sys,time,json
cwd,directory,run_id,deadline=sys.argv[1:5]
try:
 os.chdir(cwd)
 if time.monotonic_ns() >= int(deadline):sys.exit(124)
 os.execvpe(sys.argv[5],sys.argv[5:],os.environ)
except OSError as exc:
 path=os.path.join(directory,'launch-error.json')
 temporary=path+'.'+str(os.getpid())+'.tmp'
 with open(temporary,'w',encoding='utf-8') as stream:json.dump({'run_id':run_id,'error':str(exc)},stream)
 os.replace(temporary,path)
 sys.exit(126)
"""


class SpawnedProcess:
    """Direct-child handle for an atomically grouped POSIX spawn."""
    def __init__(self, pid):
        self.pid = pid
        self.returncode = None

    def poll(self):
        if self.returncode is None:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def wait(self, timeout=None):
        until = None if timeout is None else time.monotonic() + timeout
        while self.poll() is None:
            if until is not None and time.monotonic() >= until:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(.01)
        return self.returncode

    def kill(self):
        os.kill(self.pid, signal.SIGKILL)


def spawn_in_group(pgid, command, directory, run_id, deadline_ns, cwd, env, stdout, stderr, *, signal_mask=None):
    # Kernel group assignment precedes every instruction in the isolated launcher.
    argv = [sys.executable, '-I', '-S', '-c', _LAUNCH, str(cwd), str(directory),
            run_id, str(deadline_ns), *command]
    with defer_launch_signals() as previous:
        process = SpawnedProcess(os.posix_spawn(sys.executable, argv, env, setpgroup=pgid,
            setsigmask=previous if signal_mask is None else signal_mask, setsigdef=(signal.SIGPIPE,), file_actions=[
                (os.POSIX_SPAWN_DUP2, stdout.fileno(), 1),
                (os.POSIX_SPAWN_DUP2, stderr.fileno(), 2)]))
    return process


class GroupPin:
    """Own a PGID through its unreaped direct child; never use checkpoint PIDs."""

    def __init__(self, directory, run_id, deadline_ns, *, signal_mask=None):
        self.directory = Path(directory)
        self.run_id = run_id
        self.closed = False
        self.process = None
        root = Path(__file__).resolve().parent.parent
        env = dict(os.environ)
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        ready_deadline = min(deadline_ns, time.monotonic_ns() + 5 * NS)
        try:
            with defer_launch_signals() as previous:
                self.process = subprocess.Popen(
                    [sys.executable, "-m", "lib._docgroup_pin", "pin", str(self.directory),
                     run_id, str(os.getpid()), json.dumps(list(previous if signal_mask is None else signal_mask))], cwd=root, env=env,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            while time.monotonic_ns() < ready_deadline:
                ready = read(self.directory / "pin-ready.json")
                if ready == {"run_id": run_id, "pgid": self.process.pid}:
                    return
                # Do not poll/wait the pin: even an exited child reserves its PID.
                time.sleep(.01)
            raise TimeoutError("group pin did not arm before startup deadline")
        except BaseException:
            self.finish()
            raise

    @property
    def pgid(self):
        return self.process.pid

    def signal_group(self, number):
        if self.closed:
            raise RuntimeError("group pin ownership already released")
        try:
            os.killpg(self.pgid, number)
        except ProcessLookupError:
            pass

    def finish(self, timeout=2):
        """Release the pin only after the caller has finished all group signals."""
        if self.closed:
            return
        if self.process is None:
            self.closed = True
            return
        # Close the signal capability before wait can release the PID.
        self.closed = True
        try:
            atomic(self.directory / "pin-release.json", {"run_id": self.run_id})
        finally:
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # A direct-child kill is safe; no group signal can follow this reap.
                self.process.kill()
                self.process.wait(timeout=1)


def pin(directory, run_id, parent_pid, previous=()):
    signal.pthread_sigmask(signal.SIG_SETMASK, previous)
    directory = Path(directory)
    os.setpgid(0, 0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    atomic(directory / "pin-ready.json", {"run_id": run_id, "pgid": os.getpid()})
    # No self-expiry: a delayed guardian must never outlive its group reservation.
    # Total parent+guardian loss remains outside the cleanup guarantee.
    while True:
        # Check permanent parent loss before reading startup release: a dead
        # parent cannot publish it after this check. Without release, guardian
        # startup cannot execute a workload or issue destructive group signals.
        if os.getppid() != parent_pid:
            startup = read(directory / "startup-release.json")
            if not startup or startup.get("run_id") != run_id:
                return
        release = read(directory / "pin-release.json")
        if release == {"run_id": run_id}:
            return
        time.sleep(.02)


if __name__ == "__main__":
    if sys.argv[1] == "pin":
        pin(sys.argv[2], sys.argv[3], int(sys.argv[4]), json.loads(sys.argv[5]) if len(sys.argv)>5 else ())
    else:
        raise SystemExit("expected pin")

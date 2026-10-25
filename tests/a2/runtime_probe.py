"""Read the installed R runtime back in the shape fixture-lock.json pins it (R version plus the locked packages)."""
import json
import subprocess


def probe_code(packages):
    names = ','.join(f'"{p}"' for p in packages)
    return ('cat(jsonlite::toJSON(list(R=as.character(getRversion()),'
            f'R_packages=setNames(lapply(c({names}),function(p)as.character(packageVersion(p))),c({names}))),auto_unbox=TRUE))')


def installed(lock, rscript, run=subprocess.run):
    try:
        out = run([rscript, '--vanilla', '-e', probe_code(lock['R_packages'])], capture_output=True, text=True, timeout=20, check=True).stdout
        return json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None

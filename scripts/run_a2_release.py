"""Collect actual pytest identities/outcomes; pending manifests fail before execution."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv);args.output.mkdir(parents=True,exist_ok=True)
    evidence={'run_id':uuid.uuid4().hex,'python':platform.python_version(),'platform':os.environ.get('A2_PLATFORM',platform.system()),'verified':False}
    try:
        manifest_path=Path('tests/a2/required.json');lock_path=Path('tests/a2/fixture-lock.json')
        manifest=json.loads(manifest_path.read_text())
        evidence.update(candidate_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),manifest_hash=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),lock_hash=hashlib.sha256(lock_path.read_bytes()).hexdigest())
        if manifest.get('status')!='ready' or not manifest.get('groups') or any(not g.get('nodes') or g.get('status')!='ready' for g in manifest['groups']):
            raise ValueError('Required manifest is pending; incomplete contract coverage cannot produce release acceptance')
        result=subprocess.run([sys.executable,'-m','pytest','tests/a2','--a2-release','-p','tests.a2.release_capture','-q'],env={**os.environ,'A2_EVIDENCE_DIR':str(args.output.resolve()),'A2_RUN_ID':evidence['run_id']},capture_output=True,text=True)
        (args.output/'pytest.log').write_text(result.stdout+result.stderr)
        evidence.update(json.loads((args.output/'pytest-records.json').read_text()))
        evidence['pytest_exit']=result.returncode
        # This separate process owns its real fixtures and emits only an allowlisted schema.
        oracle_run=subprocess.run([sys.executable,"scripts/a2_fixture_oracles.py"],env={**os.environ,"PYTHONPATH":str(Path.cwd())},capture_output=True,text=True,timeout=120,check=True)
        (args.output/'fixture-oracles.log').write_text(oracle_run.stderr)
        oracle=json.loads(oracle_run.stdout)
        allowed={"fixture_executions","reported_r_checked","reported_http_checked"}
        if set(oracle)!=allowed:raise ValueError("unexpected fixture oracle schema")
        evidence.update({key:oracle[key] for key in allowed})
        (args.output/'fixture-executions.json').write_text(json.dumps(oracle,indent=2)+'\n')
        runtime_code='cat(jsonlite::toJSON(list(R=as.character(getRversion()),R_packages=setNames(lapply(c("pkgload","evaluate","knitr","pkgdown","jsonlite"),function(p)as.character(packageVersion(p))),c("pkgload","evaluate","knitr","pkgdown","jsonlite"))),auto_unbox=TRUE))'
        runtime=json.loads(subprocess.check_output(["Rscript","--vanilla","-e",runtime_code],text=True,timeout=20))
        if set(runtime)!={"R","R_packages"}:raise ValueError("unexpected runtime evidence schema")
        evidence.update(runtime)
        evidence["expected_findings_hash"]=hashlib.sha256(Path("tests/a2/expected-findings.json").read_bytes()).hexdigest()
        (args.output/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
        verification=subprocess.run([sys.executable,'scripts/verify_a2_release.py','--candidate-sha',evidence['candidate_sha'],'--evidence',str(args.output/'evidence.json')],capture_output=True,text=True)
        (args.output/'verification.json').write_text(verification.stdout)
        if verification.returncode:raise ValueError("A2 requirement/runtime/evidence verifier failed")
        validation=json.loads(verification.stdout)
        if result.returncode:raise ValueError('Required pytest run failed')
        evidence.update(validation)
        return 0
    except (OSError,ValueError,subprocess.SubprocessError) as exc:
        evidence['reason']=str(exc);return 2
    finally:
        (args.output/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':raise SystemExit(main())

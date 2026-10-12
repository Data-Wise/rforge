"""Verify both retrieved platform artifacts and completed external observations."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from verify_a2_release import VerificationError, require, validate_aggregate


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--observations',type=Path,required=True)
    parser.add_argument('--candidate-sha',required=True)
    args=parser.parse_args(argv)
    try:
        platforms=[]
        for platform in ('ubuntu-24.04','macos-14'):
            file=args.artifacts/('a2-release-evidence-'+platform)/'evidence.json'
            require(file.is_file(),'missing retrieved artifact: '+platform)
            evidence=json.loads(file.read_text())
            require(evidence.get('platform')==platform,'wrong artifact platform')
            verification=subprocess.run([sys.executable,'scripts/verify_a2_release.py','--evidence',str(file),'--candidate-sha',args.candidate_sha],capture_output=True,text=True)
            require(verification.returncode==0,'retrieved platform verification failed: '+platform)
            platforms.append({'platform':platform,'candidate_sha':evidence['candidate_sha'],'uploaded':True,'retrieved':True,'verified':True})
        result=validate_aggregate(platforms,json.loads(args.observations.read_text()),candidate_sha=args.candidate_sha)
        print(json.dumps(result));return 0
    except (OSError,ValueError,KeyError,VerificationError) as exc:
        print(json.dumps({'verified':False,'reason':str(exc)}));return 2


if __name__=='__main__':raise SystemExit(main())

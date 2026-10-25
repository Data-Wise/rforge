#!/usr/bin/env python3
"""Check that the run supplying the a2-acceptance-evidence artifact is the genuine observations run for the candidate.

The aggregate verifier trusts the downloaded artifact's own JSON, which any workflow could write. This binds the
run itself to the candidate: same head commit, the a2-observations workflow file, a manual dispatch, and a
successful completion. The input is the JSON from `gh api repos/OWNER/REPO/actions/runs/RUN_ID`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WORKFLOW_PATH = ".github/workflows/a2-observations.yml"


class ProducerRunError(ValueError):
    pass


def verify_producer_run(run: dict, *, candidate_sha: str, run_id: str) -> None:
    def require(condition: bool, reason: str) -> None:
        if not condition:
            raise ProducerRunError(reason)
    require(isinstance(run, dict), "run record must be an object")
    require(str(run.get("id")) == str(run_id), "run ID mismatch")
    require(bool(candidate_sha) and run.get("head_sha") == candidate_sha, "producer run is for a different commit")
    path = run.get("path")
    require(isinstance(path, str) and (path == WORKFLOW_PATH or path.startswith(WORKFLOW_PATH + "@")),
            "producer run is not the a2-observations workflow")
    require(run.get("event") == "workflow_dispatch", "producer run was not a manual dispatch")
    require(run.get("status") == "completed" and run.get("conclusion") == "success", "producer run did not complete successfully")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        if not args.run_id.isdigit():
            raise ProducerRunError("numeric run ID required")
        verify_producer_run(json.loads(args.run.read_text()), candidate_sha=args.candidate_sha, run_id=args.run_id)
    except (OSError, ValueError) as exc:
        print(json.dumps({"verified": False, "reason": str(exc)}))
        return 2
    print(json.dumps({"verified": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

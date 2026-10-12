"""Record expanded collection and actual pytest calls from the same invocation."""
import json
import os
from pathlib import Path

record={'collected':[],'outcomes':{},'collection_run_id':os.environ.get('A2_RUN_ID')}


def pytest_collection_finish(session):
    record['collected']=[item.nodeid for item in session.items]


def pytest_runtest_logreport(report):
    if report.when=='call' or report.failed or report.skipped:
        outcome='xpassed' if hasattr(report,'wasxfail') and report.passed else 'xfailed' if hasattr(report,'wasxfail') else report.outcome
        record['outcomes'][report.nodeid]=outcome


def pytest_sessionfinish(session,exitstatus):
    directory=os.environ.get('A2_EVIDENCE_DIR')
    if directory:Path(directory,'pytest-records.json').write_text(json.dumps(record,indent=2)+'\n')

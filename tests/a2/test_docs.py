"""Shipped command, guide, and generated-reference contracts."""
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('path', ['commands/docs/check.md', 'docs/commands.md', 'docs/guides/docs-audit.md', 'docs/tutorials/fix-a-docs-check-finding.md'])
def test_optional_flags_documented(path):
    text = (ROOT / path).read_text()
    assert '--site' in text and '--run-examples' in text


def test_command_sync():
    subprocess.run([sys.executable, str(ROOT / 'tests/_check_commands_doc.py')], cwd=ROOT, check=True, capture_output=True)


def test_generated_reference_sync():
    subprocess.run([sys.executable, str(ROOT / 'scripts/gen_lib_reference.py'), '--check'], cwd=ROOT, check=True, capture_output=True)


def test_version_and_agent_mirror():
    subprocess.run([sys.executable, str(ROOT / 'scripts/version_sync.py'), '--check'], cwd=ROOT, check=True, capture_output=True)
    claude = (ROOT / 'CLAUDE.md').read_text()
    agents = (ROOT / 'AGENTS.md').read_text()
    assert claude[claude.index('## Current state'):] == agents[agents.index('## Current state'):]


@pytest.mark.parametrize('path,terms',[
 ('docs/guides/docs-audit.md',['--site','--run-examples','unverified','sandbox','--fail-on error']),
 ('docs/tutorials/fix-a-docs-check-finding.md',['--site','--run-examples','INCOMPLETE','figure']),
 ('docs/workflows/index.md',['--run-examples','unknown','15 seconds']),
 ('docs/quickstart.md',['--site','--run-examples','incomplete']),
])
def test_walkthroughs_and_site_content(path,terms):
    text=' '.join((ROOT/path).read_text().lower().split())
    assert all(term.lower() in text for term in terms)

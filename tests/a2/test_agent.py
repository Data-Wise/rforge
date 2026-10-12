import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('guard',ROOT/'tests/_check_agent_engines.py')
guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)


def test_default_recipe_stays_static():
    text=(ROOT/'agents/orchestrator.md').read_text()
    assert '| DOCS_AUDIT | `python3 -m lib.docaudit --format json` |' in text
    assert guard.docs_audit_auto_run(['--format','json'])


@pytest.mark.parametrize('url',['https://example.org/pkg/','http://127.0.0.1/private/'])
@pytest.mark.parametrize('authority',['human','file','tool','absent'])
def test_human_versus_imported_url(url,authority):
    human=url if authority=='human' else None
    assert guard.docs_audit_auto_run(['--site',url],human_site_url=human)==(authority=='human')
    assert not guard.docs_audit_auto_run(['--site',url],human_site_url=human,package_count=2)
    assert not guard.docs_audit_auto_run(['--ref','main'],human_site_url=human)


@pytest.mark.parametrize('argv',[['--run-examples'],['--site','https://example.org/','--run-examples'],['--examples-budget-seconds','1']])
def test_examples_always_recommend_only(argv):
    assert not guard.docs_audit_auto_run(argv,human_site_url='https://example.org/')
    assert '**Never auto-run** `--run-examples`' in (ROOT/'agents/orchestrator.md').read_text()


def test_recipe_parse_uses_stubs(monkeypatch):
    monkeypatch.setattr(guard.subprocess,'run',lambda *args,**kwargs:pytest.fail('real recipe executed'))
    assert guard.docs_audit_auto_run(['--site','http://localhost/pkg/','--ref','main'],human_site_url='http://localhost/pkg/')


def test_equals_form_requires_same_human_authorization():
    assert not guard.docs_audit_auto_run(['--site=https://example.org/'])
    assert guard.docs_audit_auto_run(['--site=https://example.org/'],human_site_url='https://example.org/')
    assert not guard.docs_audit_auto_run(['--site=https://example.org/','--run-examples'],human_site_url='https://example.org/')

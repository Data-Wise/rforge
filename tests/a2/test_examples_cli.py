import time
import pytest
from lib import docaudit
from .test_examples_r import fixture


def test_native_chunk_deadline(tmp_path):
    p=fixture(tmp_path,"```r\nSys.sleep(30)\nprint(1)\n#> [1] 1\n```")
    r=docaudit.audit(p,run_examples=True,examples_budget_seconds=1)
    assert r["incomplete"] and r["stages"]["examples"]["provenance"]["lifecycle"]["reason"]=="deadline"
    assert docaudit.exit_code(r,"warn")==2 and docaudit.exit_code(r,"error")==2


def test_one_upstream_failure(tmp_path):
    p=fixture(tmp_path,"```r\nstop('upstream')\n#> expected\n```\n```r\nstop('later')\n#> later\n```")
    r=docaudit.audit(p,run_examples=True)
    assert r["incomplete"] and len([f for f in r["findings"] if f["check"]=="examples-error"])==1
    assert r["stages"]["examples"]["counts"]["blocked"]==2


def test_file_loading_deadline(tmp_path):
    p = fixture(tmp_path, '```r\nprint(1)\n#> [1] 1\n```')
    (p/'R'/'load.R').write_text('.onLoad <- function(libname, pkgname) Sys.sleep(30)\n')
    r = docaudit.audit(p, run_examples=True, examples_budget_seconds=1)
    stage = r['stages']['examples']
    assert stage['state'] == 'incomplete' and stage['counts']['checked'] == 0
    assert stage['provenance']['lifecycle']['reason'] == 'deadline'


def test_global_budget_across_packages(tmp_path):
    from .helpers import package
    a = package(tmp_path/'a', name='a', readme='```r\nSys.sleep(30)\nprint(1)\n#> [1] 1\n```')
    b = package(tmp_path/'b', name='b', readme='```r\nprint(2)\n#> [1] 2\n```')
    for p in (a,b):
        (p/'R').mkdir(); (p/'R'/'f.R').write_text('f <- function() 1\n')
    r = docaudit.audit(tmp_path, eco=True, run_examples=True, examples_budget_seconds=1)
    stages = [p['stages']['examples'] for p in r['packages']]
    assert all(s['state']=='incomplete' for s in stages)
    assert all(s['counts']['checked']==0 for s in stages)
    lifecycle = stages[1]['provenance']['lifecycle']
    assert lifecycle['reason'] == 'deadline' and lifecycle['phase'] == 'startup'
    assert not lifecycle['direct_child_reaped']
    assert lifecycle['global_deadline_ns'] == stages[0]['provenance']['lifecycle']['global_deadline_ns']


@pytest.mark.parametrize('format', ['json', 'text'])
@pytest.mark.parametrize('threshold,expected', [('none',0),('warn',2),('error',2)])
def test_partial_cli_report_thresholds(tmp_path, capsys, format, threshold, expected):
    import json
    p = fixture(tmp_path, '```r\nprint(1)\n#> [1] 1\n```\n```r\nSys.sleep(30)\nprint(2)\n#> [1] 2\n```')
    result = docaudit.main(['--path',str(p),'--run-examples','--examples-budget-seconds','2','--format',format,'--fail-on',threshold])
    captured = capsys.readouterr()
    assert result == expected and captured.err
    if format == 'json':
        stage = json.loads(captured.out)['stages']['examples']
        assert stage['state']=='incomplete' and stage['counts']['checked']==1 and stage['counts']['blocked']==1
    else:
        assert 'INCOMPLETE' in captured.out and 'no findings' not in captured.out


@pytest.mark.parametrize('failed_stage',['site','examples'])
def test_combined_stage_and_eco_partial_results(tmp_path, failed_stage):
    from .test_site_integration import fixture as site_fixture,server
    p,web=site_fixture(tmp_path)
    (p/'R').mkdir();(p/'R'/'f.R').write_text('f <- function() 1\n')
    code='stop("upstream")' if failed_stage=='examples' else 'print(1)'
    (p/'README.md').write_text(f'```r\n{code}\n#> [1] 1\n```')
    with server(web) as url:
        if failed_stage!='site':
            (web/'pkg'/'sitemap.xml').write_text(f'<urlset><url><loc>{url}reference/internal.html</loc></url><url><loc>{url}articles/pizza/slice.html</loc></url></urlset>')
        report=docaudit.audit(p,site=url,ref='main',run_examples=True)
    stages=report['stages']
    assert report['incomplete'] and set(stages)=={'site','examples'}
    successful=stages['examples' if failed_stage=='site' else 'site']
    assert successful['state']=='complete' and successful['counts']['checked']>0
    assert stages[failed_stage]['state']=='incomplete'
    assert docaudit.exit_code(report,'error')==2


def test_wrapper_lifetime_and_interruption():
    import json
    from pathlib import Path
    import subprocess
    import sys
    root=Path(__file__).resolve().parents[2]
    recipe=' '.join((root/'commands/docs/check.md').read_text().split())
    for phrase in ('budget plus 15 seconds','lifetime is unknown','shorter known host limit','reduce the requested budget','Poll/yield timeouts are not host lifetime limits','Missing stdout','interruption, never a clean audit or recovered JSON'):
        assert phrase in recipe
    wrapper=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        wrapper.kill()
        stdout,_=wrapper.communicate(timeout=2)
        assert wrapper.returncode != 0 and not stdout
        with pytest.raises(json.JSONDecodeError):json.loads(stdout)
    finally:
        if wrapper.poll() is None:wrapper.kill();wrapper.wait(timeout=2)

import time
import pytest
from lib import _docexamples as examples
from .helpers import package


def fixture(tmp_path, text):
    p=package(tmp_path,text)
    (p/"R").mkdir();(p/"R"/"f.R").write_text("f <- function() 1\n")
    return p


@pytest.mark.parametrize("documented,expected",[("0.19","complete"),("0.80","complete")])
def test_clean_and_planted_stale_output(tmp_path,documented,expected):
    p=fixture(tmp_path,f"```r\nprint(0.19)\n#> [1] {documented}\n```\n")
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r["state"]==expected, r
    assert r["counts"]["checked"]==1
    assert r["provenance"]["package"]["path"]==str(p.resolve())
    assert len(r["findings"])==(documented!="0.19")
    if r["findings"]: assert r["findings"][0]["check"]=="examples-output" and r["findings"][0]["severity"]=="warn"


def test_fresh_ordered_hidden_setup(tmp_path):
    p=fixture(tmp_path, "```{r setup, include=FALSE}\nx <- 3\n```\n```r\nprint(x)\n#> [1] 3\n```\n")
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r["state"]=="complete" and r["counts"]["checked"]==1, r


def test_source_success_does_not_clear_rendered(tmp_path):
    p=fixture(tmp_path,"```r\nprint(1)\n#> [1] 1\n```")
    (p/"README.Rmd").write_text("```r\nprint(1)\n#> [1] 1\n```")
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r["state"]=="incomplete" and r["counts"]["checked"]==1 and r["counts"]["unverified"]==1
    assert "rendered-unpaired" in r["reasons"]


def test_no_assertions_never_start_r(tmp_path,monkeypatch):
    p=fixture(tmp_path,"```r\nstop('must not execute')\n```")
    monkeypatch.setattr(examples.guardian,"run",lambda *a,**k:pytest.fail("R launched"))
    assert examples.audit(p,deadline=0)["state"]=="not-applicable"


def test_unsupported_defaults_block_before_r(tmp_path,monkeypatch):
    p=fixture(tmp_path,"")
    (p/"README.qmd").write_text('```{r}\nknitr::opts_chunk$set(fig.path="plots/")\n```\n```r\nprint(1)\n#> [1] 1\n```')
    monkeypatch.setattr(examples.guardian,"run",lambda *a,**k:pytest.fail("R launched"))
    r=examples.audit(p,deadline=0)
    assert r["state"]=="incomplete" and r["counts"]["checked"]==0 and any("fig.path" in s for s in r["reasons"])


@pytest.mark.parametrize("documented,actual,verdict",[("0.19","0.20","match"),("0.19","0.2001","output"),("1e-04","0.0001","match"),("p < 0.001","p = 2.2e-16","match"),("p < 0.001","p = 0.002","output"),("55%","36 %","output"),("55%","0.55","shape"),("1,234","1234","shape"),("NA","NA","match")])
def test_normative_precision(documented,actual,verdict):
    assert examples.compare(documented,actual)==verdict


def test_expression_subsequence_no_reuse(tmp_path):
    p=fixture(tmp_path,'```r\nprint(1)\nprint(9)\n#> [1] 1\n```')
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state']=='complete' and r['counts']['checked']==1
    assert [f['check'] for f in r['findings']]==['examples-output']


def test_one_upstream_failure_stops_same_chunk(tmp_path):
    sentinel=tmp_path/'must-not-exist'
    p=fixture(tmp_path,f'```r\nstop("first error")\nwriteLines("bad", {str(sentinel)!r})\n#> unwanted\n```')
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state']=='incomplete' and not sentinel.exists()
    assert [f['check'] for f in r['findings']]==['examples-error']


@pytest.mark.parametrize('expression,documented', [('packageVersion("evaluate")', '[1] 999'), ('Sys.Date()', '[1] "1900-01-01"'), ('runif(1)', '[1] 999')])
def test_unstable_output_remains_unverified(tmp_path, expression, documented):
    p = fixture(tmp_path, f'```r\n{expression}\n#> {documented}\n```')
    r = examples.audit(p, deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state'] == 'incomplete', r
    assert r['counts']['checked'] == 0 and r['counts']['unverified'] == 1
    assert r['findings'] and all(f['severity'] == 'info' for f in r['findings'])


def test_hidden_warning_does_not_hide_stdout(tmp_path):
    p = fixture(tmp_path, '```{r, warning=FALSE}\n{ warning("hidden"); print(3) }\n#> [1] 3\n```')
    r = examples.audit(p, deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state'] == 'complete' and r['counts']['checked'] == 1, r
    assert not r['findings']


def test_medfit_layout_counts_and_release_gates(tmp_path):
    from lib import docaudit
    text = '\n'.join(f'```r\nprint({i})\n#> [1] {i}\n```' for i in range(1,5))
    text += '\n```\n#> first unsupported transcript\n```\n```\n#> second unsupported transcript\n```'
    p = fixture(tmp_path,text)
    report = docaudit.audit(p,run_examples=True)
    stage = report['stages']['examples']
    counts = stage['counts']
    assert stage['state']=='incomplete' and counts['discovered']==6 and counts['eligible']==4
    assert counts['checked']==counts['matched']==4 and counts['unverified']==2
    assert counts['excluded']==counts['blocked']==counts['mismatched']==0
    assert counts['discovered']==sum(counts[k] for k in ('checked','excluded','unverified','blocked'))
    assert docaudit.exit_code(report,'warn')==docaudit.exit_code(report,'error')==2
    assert docaudit.exit_code(report,'none')==0


def test_visibility_and_conditions_channels(tmp_path):
    p=fixture(tmp_path,'```r\n{ print(3); warning("warn"); message("Message: hello") }\n#> [1] 3\n#> Warning: warn\n#> Message: hello\n```')
    report=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert report['state']=='complete' and report['counts']['matched']==1, report


def test_dependency_preflight_no_install(tmp_path):
    p=fixture(tmp_path,'```r\nprint(1)\n#> [1] 1\n```')
    with (p/'DESCRIPTION').open('a') as file:
        file.write('Imports: A2DeliberatelyUnavailableDependency\n')
    report=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert report['state']=='unavailable' and report['counts']['checked']==0
    assert report['engine_missing']==['A2DeliberatelyUnavailableDependency']


def test_working_tree_load_identity(tmp_path, monkeypatch):
    import subprocess
    import shutil
    p=fixture(tmp_path/'checkout','```r\ndata(values, package="fixture")\nstopifnot(f()==1, identical(values,7), getOption("width")==80)\nprint(f())\n#> [1] 1\n```')
    (p/'NAMESPACE').write_text('export(f)\n')
    (p/'data').mkdir()
    rscript=shutil.which('Rscript')
    subprocess.run([rscript,'--vanilla','-e',f'values <- 7; save(values, file={str(p/"data"/"values.rda")!r})'],check=True,capture_output=True)
    installed=fixture(tmp_path/'installed-source','')
    (installed/'DESCRIPTION').write_text((installed/'DESCRIPTION').read_text().replace('Version: 0.0.1','Version: 9.9.9'))
    (installed/'R'/'f.R').write_text('f <- function() 99\n')
    (installed/'NAMESPACE').write_text('export(f)\n')
    library=tmp_path/'library';library.mkdir()
    subprocess.run([rscript,'--vanilla','-e',f'install.packages({str(installed)!r}, repos=NULL, type="source", lib={str(library)!r})'],check=True,capture_output=True,timeout=30)
    monkeypatch.setenv('R_LIBS_USER',str(library))
    report=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert report['state']=='complete' and report['counts']['matched']==1, report
    identity=report['provenance']['package']
    assert identity['path']==str(p.resolve()) and identity['version']=='0.0.1'
    assert report['provenance']['versions']['R']


@pytest.mark.parametrize('source_assertion',[False,True])
@pytest.mark.parametrize('allowlist',[False,True])
def test_rendered_unpaired_counts(tmp_path, monkeypatch, source_assertion, allowlist):
    from lib import docaudit
    p=fixture(tmp_path,'```r\nprint(1)\n#> [1] 1\n```')
    (p/'README.Rmd').write_text('```r\nprint(1)\n'+('#> [1] 1\n' if source_assertion else '')+'```')
    if allowlist:(p/'.rforge.yaml').write_text('docs:\n  allowlist:\n    - README.md\n    - README.Rmd\n')
    if not source_assertion:
        monkeypatch.setattr(examples.guardian,'run',lambda *a,**k:pytest.fail('setup-only execution'))
    report=docaudit.audit(p,run_examples=True)
    stage=report['stages']['examples']
    assert stage['state']=='incomplete' and stage['counts']['unverified']==1
    assert stage['counts']['checked']==int(source_assertion)
    assert 'rendered-unpaired' in stage['reasons']
    assert docaudit.exit_code(report,'warn')==docaudit.exit_code(report,'error')==2


def test_running_evaluate_output_limit(tmp_path):
    p = fixture(tmp_path, '```r\nprint(1)\n#> [1] 1\n```\n```r\nfor (i in 1:100000) { cat(strrep("x", 8192), "\\n"); Sys.sleep(.001) }\n#> never completed\n```')
    started = time.monotonic()
    report = examples.audit(p, deadline=time.monotonic_ns()+20_000_000_000)
    assert report['state'] == 'incomplete', report
    assert any('output-limit' in reason for reason in report['reasons']), report
    assert report['counts']['checked'] == 1
    assert time.monotonic()-started < 15


def test_evaluate_spool_counts_text_once(tmp_path):
    p = fixture(tmp_path, '```{r setup, include=FALSE}\ncat(strrep("x", 6*1024*1024))\n```\n```r\nprint(1)\n#> [1] 1\n```')
    report = examples.audit(p, deadline=time.monotonic_ns()+20_000_000_000)
    assert report['state'] == 'complete' and report['counts']['checked'] == 1, report
    assert not report['findings']


def test_source_hidden_state_and_rendered_assertion(tmp_path):
    p=fixture(tmp_path,'```r\nprint(hidden)\n#> [1] 7\n```')
    (p/'README.Rmd').write_text('```{r include=FALSE}\nhidden <- 7\n```\n```r\nprint(hidden)\n#> [1] 7\n```')
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state']=='incomplete' and r['counts']['matched']==r['counts']['checked']==1 and r['counts']['unverified']==1
    assert r['provenance']['source']=='README.Rmd' and 'rendered-unpaired' in r['reasons']


def test_repeated_expected_line_cannot_reuse_output(tmp_path):
    p=fixture(tmp_path,'```r\nprint(1)\n#> [1] 1\n#> [1] 1\n```')
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state']=='incomplete' and r['counts']['checked']==0 and r['counts']['unverified']==1
    assert [f['check'] for f in r['findings']]==['examples-shape']


@pytest.mark.parametrize('seed_before',[False,True])
def test_seed_order_does_not_retroactively_verify(tmp_path,seed_before):
    setup='```{r include=FALSE}\nset.seed(1)\n```\n'
    assertion='```r\nprint(runif(1))\n#> [1] 0.2655087\n```\n'
    p=fixture(tmp_path,(setup+assertion) if seed_before else (assertion+setup))
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r['counts']['checked']==int(seed_before) and r['counts']['unverified']==int(not seed_before)


def test_excluded_only_has_no_side_effect(tmp_path):
    sentinel=tmp_path/'forbidden'
    p=fixture(tmp_path,f'```{{r eval=FALSE}}\nwriteLines("bad", "{sentinel}")\n#> ignored\n```')
    r=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    assert r['state']=='not-applicable' and r['counts']['excluded']==1 and r['counts']['checked']==0
    assert not sentinel.exists() and 'lifecycle' not in r['provenance']


def test_package_sessions_and_eval_false_isolation(tmp_path):
    p=fixture(tmp_path/'first','```{r include=FALSE}\nshared <- 9\n```\n```r\nprint(shared)\n#> [1] 9\n```')
    q=fixture(tmp_path/'second','```{r eval=FALSE}\nshared <- 8\n#> [1] 8\n```\n```r\nprint(exists("shared", envir=.GlobalEnv))\n#> [1] FALSE\n```')
    first=examples.audit(p,deadline=time.monotonic_ns()+20_000_000_000)
    second=examples.audit(q,deadline=time.monotonic_ns()+20_000_000_000)
    assert first['counts']['matched']==second['counts']['matched']==1
    assert first['provenance']['lifecycle']['child_pid']!=second['provenance']['lifecycle']['child_pid']
    assert second['counts']['excluded']==1 and second['state']=='complete'

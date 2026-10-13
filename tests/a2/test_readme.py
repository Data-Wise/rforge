import time
import pytest
from lib import _docexamples as e
from .helpers import package


@pytest.mark.parametrize("fence",["```r","~~~r","```{r label, eval=FALSE}","```{r label, include=FALSE}"])
def test_explicit_closed_fences(tmp_path,fence):
    p=package(tmp_path, fence+"\nprint(1)\n#> [1] 1\n"+fence[:3]+"\n")
    segments,reasons,unverified,discovered=e.extract(p/"README.md")
    assert discovered==1 and not reasons and not unverified
    assert segments[0]["line"]==3
    if "eval=FALSE" in fence:assert not segments[0]["execute"]
    if "include=FALSE" in fence:assert not segments[0]["visible"]


@pytest.mark.parametrize("marker",["# docs-check: skip","#| docs-check: skip","<!-- docs-check: skip -->"])
def test_all_located_skip_markers(tmp_path,marker):
    text=(marker+"\n```r\n" if marker.startswith("<") else "```r\n"+marker+"\n")+"stop('no')\n#> ignored\n```"
    p=package(tmp_path,text);segments,_,_,_=e.extract(p/"README.md")
    assert not segments[0]["execute"]


@pytest.mark.parametrize("option",["error=TRUE","fig.path='plots/'","eval=variable","child='x.Rmd'","results='asis'"])
def test_unsupported_options_preflight(tmp_path,option):
    p=package(tmp_path,"```{r label, "+option+"}\nprint(1)\n#> [1] 1\n```")
    assert e.extract(p/"README.md")[1]


def test_body_precedence_and_conflicts(tmp_path):
    p=package(tmp_path,"```{r label, eval=TRUE}\n#| eval: false\nprint(1)\n#> [1] 1\n```")
    assert not e.extract(p/"README.md")[0][0]["execute"]
    (p/"README.md").write_text("```{r eval=TRUE, eval=FALSE}\nprint(1)\n#> [1] 1\n```")
    assert e.extract(p/"README.md")[1]


def test_real_readme_shape_regressions(tmp_path,monkeypatch):
    monkeypatch.setattr(e.guardian,"run",lambda *a,**k:pytest.fail("ineligible/preflight source executed"))
    p=package(tmp_path,"```\n#> output\n```")
    r=e.audit(p,deadline=0)
    assert r["state"]=="incomplete" and r["counts"]["unverified"]==1
    (p/"README.qmd").write_text('```{r}\n#| include: false\nknitr::opts_chunk$set(fig.path="plots/", out.width="100%")\n```\n```r\nprint(1)\n#> [1] 1\n```')
    r=e.audit(p,deadline=0)
    assert r["state"]=="incomplete" and r["counts"]["checked"]==0 and "rendered-unpaired" in r["reasons"]
    (p/"README.Rmd").write_text("# source")
    assert "ambiguous README sources" in e.audit(p,deadline=0)["reasons"]
    (p/"README.Rmd").unlink();(p/"README.qmd").unlink();(p/"README.md").write_text("```\nplain output 1\n```")
    assert e.audit(p,deadline=0)["state"]=="not-applicable"


def test_install_detection_ignores_strings_comments(tmp_path):
    p=package(tmp_path,'```r\n# install.packages("x")\nprint("install.packages")\n#> [1] "install.packages"\n```')
    assert e.extract(p/"README.md")[0][0]["execute"]
    (p/"README.md").write_text('```r\ninstall.packages("x")\n#> installed\n```')
    assert not e.extract(p/"README.md")[0][0]["execute"]


def test_multiline_string_is_not_pasted_output(tmp_path):
    from lib import _docexamples as examples
    p=tmp_path/'README.Rmd'
    p.write_text('```r\nx <- "first\n#> quoted text\nlast"\nprint(1)\n#> [1] 1\n```')
    segments,reasons,unverified,discovered=examples.extract(p)
    assert not reasons and unverified==0 and discovered==1
    assert len([s for s in segments if s['expected']])==1
    assert '#> quoted text' in segments[0]['code']


def test_unsupported_assertions_preserve_supported_comparison(tmp_path,monkeypatch):
    from lib import _docexamples as examples
    from .helpers import package
    p=package(tmp_path,'```r\nprint(1)\n#> [1] 1\n```\n```\n#> unsupported output\n```')
    def replay(command,directory,deadline,**kwargs):
        examples.guardian.atomic(directory/'result.json',{'records':[{'id':'README.md:3','text':['[1] 1\n'],'error':None}]})
        return {'reason':'completed'}
    monkeypatch.setattr(examples.guardian,'run',replay)
    monkeypatch.setattr(examples.shutil,'which',lambda name:'/fixture/Rscript')
    report=examples.audit(p,deadline=1)
    assert report['state']=='incomplete' and report['counts']['checked']==1 and report['counts']['unverified']==1


@pytest.mark.parametrize('channel,options,output',[('warning','warning=FALSE','Warning: hidden'),('message','message=FALSE','Message: hidden'),('stdout','results="hide"','[1] 1')])
def test_supported_visibility_options(tmp_path,channel,options,output):
    from lib import _docexamples as examples
    p=tmp_path/'README.Rmd';p.write_text(f'```{{r, {options}}}\nprint(1)\n#> {output}\n```')
    segments,reasons,unverified,count=examples.extract(p)
    assert not reasons and not segments[0]['visible']
    assert segments[0]['excluded_reason']=='hidden-'+channel


def test_conflicting_global_defaults_fail_preflight(tmp_path):
    from lib import _docexamples as examples
    p=tmp_path/'README.Rmd';p.write_text('```r\nknitr::opts_chunk$set(eval=TRUE)\nknitr::opts_chunk$set(eval=FALSE)\nprint(1)\n#> [1] 1\n```')
    assert 'conflicting global chunk defaults' in examples.extract(p)[1]


def test_all_unsupported_options_are_reported():
    with pytest.raises(ValueError) as failure:
        e.assignments('fig.path="plots/", out.width="100%", error=TRUE')
    assert all(option in str(failure.value) for option in ('fig.path', 'out.width', 'error=TRUE'))


def test_quarto_defaults_report_all_unsupported_options(tmp_path):
    p=tmp_path/'README.qmd'
    p.write_text('---\nexecute:\n  fig-width: 8\n  out-width: "100%"\n---\n```r\nprint(1)\n#> [1] 1\n```')
    _,reasons,_,_=e.extract(p)
    assert any('fig-width' in reason for reason in reasons)
    assert any('out-width' in reason for reason in reasons)


@pytest.mark.parametrize('source',['README.Rmd','README.qmd','both','md-only'])
def test_source_selection_and_ambiguity(tmp_path,monkeypatch,source):
    p=package(tmp_path,'```r\nprint(1)\n#> [1] 1\n```')
    if source!='md-only':
        (p/('README.Rmd' if source=='both' else source)).write_text('# source without assertions')
    if source=='both':(p/'README.qmd').write_text('# second source')
    monkeypatch.setattr(e.shutil,'which',lambda name:None)
    monkeypatch.setattr(e.guardian,'run',lambda *a,**k:pytest.fail('unavailable or ineligible replay launched'))
    report=e.audit(p,deadline=0)
    if source=='both':
        assert report['state']=='incomplete' and 'ambiguous README sources' in report['reasons']
    elif source=='md-only':
        assert report['state']=='unavailable' and report['provenance']['source']=='README.md'
        assert any('omitted setup' in reason for reason in report['reasons'])
    else:
        assert report['provenance']['source']==source and report['counts']['unverified']==1
        assert report['provenance']['coverage_sources']['README.md']['selection']=='rendered-unpaired'


@pytest.mark.parametrize('excluded_only',[False,True])
def test_coverage_partition_and_exclusions(tmp_path,monkeypatch,excluded_only):
    text='\n'.join('```{r eval=FALSE}\nstop("excluded")\n#> excluded\n```' for _ in range(5))
    if not excluded_only:text+='\n```r\nprint(1)\n#> [1] 1\n```'
    p=package(tmp_path,text)
    def replay(command,directory,deadline,**kwargs):
        segments=e.extract(p/'README.md')[0]
        eligible=[seg for seg in segments if seg['execute'] and seg['visible'] and seg['expected']]
        e.guardian.atomic(directory/'result.json',{'records':[{'id':seg['id'],'text':['[1] 1\n']} for seg in eligible]})
        return {'reason':'completed'}
    monkeypatch.setattr(e.guardian,'run',lambda *a,**k:pytest.fail('excluded-only setup launched') if excluded_only else replay(*a,**k))
    monkeypatch.setattr(e.shutil,'which',lambda name:'/fixture/Rscript')
    report=e.audit(p,deadline=1)
    c=report['counts']
    assert report['state']==('not-applicable' if excluded_only else 'complete')
    assert c['checked']==c['eligible']==int(not excluded_only) and c['excluded']==5
    assert c['discovered']==sum(c[k] for k in ('checked','excluded','unverified','blocked'))
    assert len(report['provenance']['exclusions'])==5


@pytest.mark.parametrize('fence',['```','```python','```r'])
def test_unsupported_or_unterminated_fences_never_execute(tmp_path,monkeypatch,fence):
    p=package(tmp_path,fence+'\nstop("forbidden")\n#> expected\n'+('' if fence=='```r' else '```'))
    (p/'vignettes').mkdir();(p/'vignettes/example.Rmd').write_text('```r\nstop("vignette forbidden")\n#> expected\n```')
    monkeypatch.setattr(e.guardian,'run',lambda *a,**k:pytest.fail('unsupported README executed'))
    r=e.audit(p,deadline=time.monotonic_ns()+10**9)
    assert r['state']=='incomplete' and r['counts']['discovered']==r['counts']['unverified']==1 and r['counts']['checked']==0


@pytest.mark.parametrize('between',['\n','\nintervening prose\n'])
def test_html_skip_prior_nonblank_boundary(tmp_path,between):
    p=package(tmp_path,'<!-- docs-check: skip -->\n'+between+'```r\nprint(1)\n#> [1] 1\n```')
    segments,reasons,_,_=e.extract(p/'README.md')
    assert not reasons and segments[0]['execute']==('prose' in between)


@pytest.mark.parametrize('source,defaults',[('README.Rmd','```r\nknitr::opts_chunk$set(eval=TRUE, include=TRUE, echo=FALSE, warning=FALSE, message=FALSE, results="markup", comment="#>", error=FALSE, engine="R")\n```\n'),('README.qmd','---\nexecute:\n  eval: true\n  echo: false\n  warning: false\n  message: false\n---\n')])
def test_literal_global_defaults_and_supported_options(tmp_path,source,defaults):
    p=tmp_path/source;p.write_text(defaults+'```r\nprint(1)\n#> [1] 1\n```')
    segments,reasons,_,_=e.extract(p);assert not reasons
    s=next(s for s in segments if s['expected'])
    assert s['execute'] and s['visible'] and s['stdout'] and s['warning'] is False and s['message'] is False


@pytest.mark.parametrize('option',['error=1','eval=variable','fig.path="x"','child="x.Rmd"','results="asis"','engine=FALSE','template="x"'])
def test_unsupported_family_never_replays(tmp_path,monkeypatch,option):
    p=package(tmp_path,'```{r '+option+'}\nprint(1)\n#> [1] 1\n```')
    monkeypatch.setattr(e.guardian,'run',lambda *a,**k:pytest.fail('unsupported option replayed'))
    r=e.audit(p,deadline=time.monotonic_ns()+10**9)
    assert r['state']=='incomplete' and r['counts']['unverified']==1 and r['counts']['checked']==0 and r['reasons']


@pytest.mark.parametrize('text',['```r\nknitr::opts_chunk$set(eval=variable)\n```\n','---\nexecute: "{{ dynamic }}"\n---\n'])
def test_dynamic_defaults_never_replay(tmp_path,monkeypatch,text):
    p=package(tmp_path);(p/'README.qmd').write_text(text+'```r\nprint(1)\n#> [1] 1\n```')
    monkeypatch.setattr(e.guardian,'run',lambda *a,**k:pytest.fail('dynamic defaults replayed'))
    r=e.audit(p,deadline=time.monotonic_ns()+10**9)
    assert r['state']=='incomplete' and r['counts']['checked']==0 and r['reasons']


@pytest.mark.parametrize('missing',['pkgload','evaluate','knitr'])
def test_engine_preflight_exact_missing_list(tmp_path,monkeypatch,missing):
    text=('```r\nknitr::opts_chunk$set(eval=TRUE)\n```\n' if missing=='knitr' else '')+'```r\nprint(1)\n#> [1] 1\n```'
    p=package(tmp_path,text)
    def replay(command,directory,deadline,**kwargs):
        import json
        incoming=json.loads((directory/'input.json').read_text())
        assert incoming['dependencies']==(['knitr'] if missing=='knitr' else [])
        e.guardian.atomic(directory/'result.json',{'records':[],'engine_missing':[missing],'error':'required engine unavailable'})
        return {'reason':'completed'}
    monkeypatch.setattr(e.guardian,'run',replay);monkeypatch.setattr(e.shutil,'which',lambda *a:'/fixture/Rscript')
    r=e.audit(p,deadline=time.monotonic_ns()+10**9)
    assert r['state']=='unavailable' and r['engine_missing']==[missing] and r['counts']['blocked']==1 and not r['findings']

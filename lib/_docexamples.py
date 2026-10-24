"""Conservative root-README transcript extraction and supervised working-tree replay."""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import _docguardian as guardian

BOOLEANS = {"eval","include","echo","warning","message","collapse"}
DEFAULTS = {"eval":True,"include":True,"echo":True,"warning":True,"message":True,"collapse":False,"results":"markup","comment":"#>","error":False}
NUMBER = re.compile(r"(?<![\w])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|(?<![\w])(?:NA|NaN|[-+]?Inf)(?![\w])")


def assertion_lines(text):
    """Recognize pasted comments without treating multiline R strings as output."""
    found = set(); quote = None; fence = None; in_r = False
    for n, line in enumerate(text.splitlines(), 1):
        opening = re.match(r"^\s*(`{3,}|~{3,})\s*(.*)$", line)
        if opening:
            if fence and opening[1][0] == fence[0] and len(opening[1]) >= len(fence) and not opening[2]:
                fence = None; in_r = False; quote = None
            elif fence is None:
                fence = opening[1]; in_r = bool(re.fullmatch(r"r|\{r(?:[ ,].*)?\}", opening[2]))
            continue
        if line.startswith("#>") and (not in_r or quote is None):
            found.add(n)
        if in_r:
            escaped = False
            for char in line:
                if escaped: escaped = False; continue
                if quote:
                    if char == "\\": escaped = True
                    elif char == quote: quote = None
                elif char == "#": break
                elif char in ("'", '"', "`"): quote = char
    return found


def output_groups(text):
    groups = []; active = None; assertions = assertion_lines(text)
    for n,line in enumerate(text.splitlines(),1):
        if n in assertions:
            if active is None:
                active = {"line":n,"lines":[]};groups.append(active)
            active["lines"].append(line[2:].lstrip())
        else:
            active = None
    return groups


def literal(key, value):
    value = value.strip()
    if key in BOOLEANS or key == "error":
        if value.lower() not in ("true", "false"):
            raise ValueError(f"dynamic option {key}: {value}")
        result = value.lower() == "true"
        if key == "error" and result:
            raise ValueError("unsupported option error=TRUE")
        return result
    if key == "engine" and value.strip("\"' ") in ("R","r"):
        return "R"
    if key == "results" and value.strip("\"'") in ("hide","markup"):
        return value.strip("\"'")
    if key == "comment" and value.strip("\"'") == "#>":
        return "#>"
    raise ValueError(f"unsupported option {key}: {value}")


def assignments(text, *, body=False):
    options = {}; errors = []
    for match in re.finditer(r"([\w.-]+)\s*[:=]\s*([^,\n]+)",text):
        key,value = match.groups()
        try:
            value = literal(key,value)
            if key in options and options[key] != value:
                raise ValueError(f"conflicting option {key}")
            options[key] = value
        except ValueError as exc:
            errors.append(str(exc))
    # Unknown residue cannot be treated as a chunk label or ignored expression.
    residue = re.sub(r"([\w.-]+)\s*[:=]\s*([^,\n]+)","",text).strip(" ,\n")
    if residue and not re.fullmatch(r"[\w.-]+",residue):
        errors.append(f"unsupported option syntax: {residue}")
    if errors:
        raise ValueError("; ".join(errors))
    return options


# Calls that install, update, or restore packages. README replay never installs dependencies, so a chunk
# containing any of them is skipped. The lookbehind rejects longer identifiers and member access
# (`my_pak::pak`, `x$install_github`); strings and comments are removed before matching.
INSTALL_CALL = re.compile(r"""
    (?<![\w.$@])
    (?:
        (?:[A-Za-z][\w.]*::)?(?:install|update)\.packages
      | (?:remotes|devtools|pak|pkgdepends|renv|BiocManager)::
            (?:install[\w.]*|restore|hydrate|pak|pkg_install|local_install\w*|pkg_upgrade)
      | install_(?:github|gitlab|bitbucket|git|svn|url|local|cran|version|bioc|deps|dev_deps)
    )\s*\(""", re.X)


def extract(file):
    text=file.read_text(); lines=text.splitlines(); segments=[]; reasons=[]; defaults=dict(DEFAULTS)
    all_groups=output_groups(text); assertion_set=assertion_lines(text); supported_lines=set(); i=0; sequence=0
    # Resolve document/global defaults before executing anything.
    global_values={}
    for match in re.finditer(r"knitr::opts_chunk\$set\s*\((.*?)\)",text,re.S):
        try:
            values=assignments(match.group(1))
            if any(key in global_values and global_values[key]!=value for key,value in values.items()):
                raise ValueError("conflicting global chunk defaults")
            global_values.update(values);defaults.update(values)
        except ValueError as exc: reasons.append(str(exc))
    if file.suffix == ".qmd" and text.startswith("---"):
        try:
            from ._docsite import yaml_data
            front=yaml_data(text.split("---",2)[1])
            execute=front.get("execute",{})
            if execute and not isinstance(execute,dict): raise ValueError("dynamic Quarto execute defaults")
            for key,value in execute.items():
                try: defaults[key]=literal(key,str(value))
                except ValueError as exc: reasons.append(str(exc))
        except (ValueError,IndexError) as exc: reasons.append(str(exc))
    while i<len(lines):
        match=re.match(r"^\s*(`{3,}|~{3,})\s*(r|\{r(?:[ ,].*)?\})\s*$",lines[i])
        if not match: i+=1;continue
        start=i; fence=match.group(1); header=match.group(2);i+=1;content=[]
        while i<len(lines) and not re.fullmatch(r"\s*"+re.escape(fence[0])+"{"+str(len(fence))+r",}\s*",lines[i]):
            content.append((i+1,lines[i]));i+=1
        if i==len(lines): reasons.append(f"unterminated R fence at {start+1}");break
        try:
            options=dict(defaults)
            if header.startswith("{"): options.update(assignments(header[2:-1]))
            body="\n".join(line[2:].lstrip() for _,line in content if line.startswith("#|"))
            if body:options.update(assignments(body.replace("docs-check: skip", "")))
        except ValueError as exc:
            reasons.append(f"line {start+1}: {exc}");options=dict(defaults)
        preceding=next((s.strip() for s in reversed(lines[:start]) if s.strip()),"")
        code="\n".join(line for _,line in content)
        skip=any(re.match(r"^\s*#(?:\|)?\s*docs-check:\s*skip\s*$",line) for _,line in content) or preceding=="<!-- docs-check: skip -->"
        # Remove strings and comments before recognizing actual installation calls.
        tokens=re.sub(r"\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|#[^\n]*", "",code)
        install=bool(INSTALL_CALL.search(tokens))
        execute=options["eval"] and not skip and not install
        visible=options["include"] and options["results"]!="hide"
        buffer=[];j=0
        while j<len(content):
            line_no,line=content[j]
            if line.startswith("#>") and line_no in assertion_set:
                expected=[];begin=line_no
                while j<len(content) and content[j][0] in assertion_set:
                    supported_lines.add(content[j][0]);expected.append(content[j][1][2:].lstrip());j+=1
                channel = "warning" if expected and expected[0].startswith("Warning") else "message" if expected and expected[0].startswith("Message:") else "stdout"
                channel_visible = options["include"] and (options[channel] if channel in ("warning","message") else options["results"]!="hide")
                sequence+=1
                segments.append({"id":f"{file.name}:{begin}","line":begin,"chunk":start+1,"code":"\n".join(buffer),"expected":expected,"execute":execute,"visible":channel_visible,"stdout":options["include"] and options["results"]!="hide","warning":options["warning"],"message":options["message"],"excluded_reason":"explicit-skip" if skip else "installation" if install else "eval-false" if not options["eval"] else "hidden-"+channel if not channel_visible else None})
                buffer=[]
            else:
                if not line.startswith("#|"):buffer.append(line)
                j+=1
        if buffer:
            sequence+=1;segments.append({"id":f"{file.name}:setup:{sequence}","line":start+1,"chunk":start+1,"code":"\n".join(buffer),"expected":[],"execute":execute,"visible":visible,"stdout":options["include"] and options["results"]!="hide","warning":options["warning"],"message":options["message"]})
        i+=1
    unverified=sum(1 for group in all_groups if group["line"] not in supported_lines)
    if unverified:reasons.append("assertions outside supported R fences")
    return segments,reasons,unverified,len(all_groups)


def compare(expected,actual):
    def normalize(value):
        value=re.sub(r"\s+"," ",value.strip())
        return re.sub(r"(?<=[^\w])\s+|\s+(?=[^\w])","",value)
    expected=normalize(expected);actual=normalize(actual)
    # A bare numeric bound (`<2e-16`) has no label to compare; a tibble type row (`<chr> <dbl>`) is not one.
    if re.match(r"^(?:<=|<|>=|>)\s*[-+.\d]",expected):return "shape"
    if expected==actual:return "match"
    inequality=re.fullmatch(r"(.+?)(<=|<|>=|>)([-+\d.eE]+)",expected)
    if inequality:
        other=re.fullmatch(r"(.+?)(<=|<|>=|>|=)([-+\d.eE]+)",actual)
        if not other or other[1]!=inequality[1]:return "shape"
        lhs,op,bound=inequality.groups();_,aop,value=other.groups()
        try:b=Decimal(bound);v=Decimal(value)
        except InvalidOperation:return "shape"
        if aop=="=":return "match" if {"<":v<b,"<=":v<=b,">":v>b,">=":v>=b}[op] else "output"
        if op in ("<","<=") and aop in ("<","<=") and (v<b or v==b and (op=="<=" or aop=="<")):return "match"
        if op in (">",">=") and aop in (">",">=") and (v>b or v==b and (op==">=" or aop==">")):return "match"
        return "unverified"
    x=list(NUMBER.finditer(expected));y=list(NUMBER.finditer(actual))
    if len(x)!=len(y) or NUMBER.sub("@",expected)!=NUMBER.sub("@",actual):return "shape"
    verdict="match"
    for a,b in zip(x,y):
        token=a.group();other=b.group()
        if token in ("NA","NaN","Inf","+Inf","-Inf") or other in ("NA","NaN","Inf","+Inf","-Inf"):
            if token!=other:verdict="output"
            continue
        mantissa,_,exponent=token.lower().partition("e")
        digits=len(mantissa.split(".",1)[1]) if "." in mantissa else 0
        tolerance=Decimal(10)**(int(exponent or 0)-digits)
        if abs(Decimal(token)-Decimal(other))>tolerance:verdict="output"
    return verdict


def audit(root:Path, *, deadline):
    counts={k:0 for k in ("discovered","eligible","checked","excluded","unverified","blocked","matched","mismatched")}
    stage={"state":"not-applicable","counts":counts,"reasons":[],"engine_missing":[],"findings":[],"provenance":{}}
    sources=[root/f for f in ("README.Rmd","README.qmd") if (root/f).is_file()]
    md=root/"README.md";files=sources+([md] if md.is_file() else [])
    if not files:return stage
    counts["discovered"]=sum(len(output_groups(f.read_text())) for f in files)
    if not counts["discovered"]:return stage
    if len(sources)>1:
        counts["unverified"]=counts["discovered"];stage.update(state="incomplete");stage["reasons"].append("ambiguous README sources");return stage
    selected=sources[0] if sources else md
    stage["provenance"]={"source":selected.name,"package_path":str(root.resolve()),"normalization":"UTF-8 width 80; decimal displayed-precision tolerance"}
    if sources and md.is_file():
        rendered=len(output_groups(md.read_text()));counts["unverified"]+=rendered
        if rendered:stage["reasons"].append("rendered-unpaired")
    if not sources:stage["reasons"].append("standalone markdown: omitted setup cannot be reconstructed")
    stage["provenance"]["coverage_sources"]={f.name:{"discovered":len(output_groups(f.read_text())),"selection":"selected" if f==selected else "rendered-unpaired"} for f in files}
    segments,reasons,unverified,_=extract(selected)
    counts["unverified"]+=unverified;stage["reasons"].extend(reasons)
    eligible=[s for s in segments if s["expected"] and s["execute"] and s["visible"]]
    counts["eligible"]=len(eligible)
    counts["excluded"]=sum(bool(s["expected"]) and (not s["execute"] or not s["visible"]) for s in segments)
    stage["provenance"]["exclusions"]=[{"assertion_id":s["id"],"reason":s.get("excluded_reason")} for s in segments if s["expected"] and (not s["execute"] or not s["visible"])]
    if any(reason != "assertions outside supported R fences" for reason in reasons):
        counts["unverified"]+=len(eligible);stage["state"]="incomplete";return stage
    if not eligible:
        stage["state"]="incomplete" if counts["unverified"] else "not-applicable";return stage
    if sys_platform_unavailable():
        stage.update(state="unavailable");counts["blocked"]=len(eligible);stage["reasons"].append("Windows example process-tree execution unavailable");return stage
    rscript=shutil.which("Rscript")
    if rscript is None:
        stage.update(state="unavailable");stage["engine_missing"]=["Rscript"];counts["blocked"]=len(eligible);stage["reasons"].append("Rscript unavailable");return stage
    dependencies=["knitr"] if "knitr::" in selected.read_text() else []
    with tempfile.TemporaryDirectory(prefix="rforge-examples-") as temp:
        directory=Path(temp)
        try:
            guardian.atomic(directory/"input.json",{"package":str(root.resolve()),"dependencies":dependencies,"segments":segments})
            script=Path(__file__).parent/"r/docexamples.R"
            print(f"docaudit: replay {root} / {selected.name}; remaining budget {max(0,(deadline-time.monotonic_ns())/1_000_000_000):.1f}s; file 300s, chunk 60s; executable package code, not a sandbox", file=sys.stderr)
            terminal=guardian.run([rscript,"--vanilla",str(script),str(directory)],directory,deadline,cwd=directory)
        except Exception as exc:
            # Recover before TemporaryDirectory removes partial replay evidence.
            initial = guardian.read(directory/"initial.json")
            saved = guardian.read(directory/"terminal.json")
            terminal = dict(saved) if isinstance(saved, dict) and isinstance(initial, dict) and initial.get("run_id") and saved.get("run_id") == initial["run_id"] else {}
            terminal["boundary_error"] = f"{type(exc).__name__}: {exc}"
            # Even a completed checkpoint cannot make a failed boundary complete.
            if terminal.get("reason") in (None, "completed"):
                terminal["reason"] = "guardian-failure"
            stage["reasons"].append(terminal["boundary_error"])
        final_started=time.monotonic_ns()
        result=guardian.read(directory/"result.json")
        checkpoint_invalid = result is not None and not isinstance(result, dict)
        result = result if isinstance(result, dict) else {}
        raw_records = result.get("records", [])
        if not isinstance(raw_records, list):
            checkpoint_invalid = True; raw_records = []
        records = {}; duplicates = set()
        for record in raw_records:
            if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not isinstance(record.get("text"), list) or not all(isinstance(line, str) for line in record["text"]) or record.get("error") is not None and not isinstance(record["error"], str):
                checkpoint_invalid = True; continue
            if record["id"] in records:
                duplicates.add(record["id"]); checkpoint_invalid = True
            records[record["id"]] = record
        for identity in duplicates: records.pop(identity, None)
        if checkpoint_invalid: stage["reasons"].append("invalid checkpoint records ignored")
        stage["provenance"].update(lifecycle=terminal,versions=result.get("versions",{}),package=result.get("package",{}))
        for stream in ("stdout","stderr"):
            if (directory/stream).exists():
                with (directory/stream).open("rb") as diagnostic:
                    diagnostic.seek(max(0,(directory/stream).stat().st_size-1024*1024))
                    stage["provenance"][stream]=diagnostic.read(1024*1024).decode("utf-8",errors="replace").encode("utf-8")[-1024*1024:].decode("utf-8",errors="ignore")
        stage["engine_missing"]=sorted(result.get("engine_missing",[]))
        failed=checkpoint_invalid
        eligible_unverified=0
        seeded=False
        for seg in segments:
            seed = re.search(r"\bset\.seed\s*\(", seg["code"])
            rng = re.search(r"\b(?:rnorm|runif|rbinom|sample|sample.int|rpois|rexp)\s*\(", seg["code"])
            seg["stochastic_uncertain"] = bool(rng) and not (seeded or seed and seed.start()<rng.start())
            seg["unstable"] = bool(re.search(r"\b(?:packageVersion|sessionInfo|Sys\.time|Sys\.Date|date)\s*\(",seg["code"]))
            if seg["execute"] and seed:seeded=True
        for seg in eligible:
            if time.monotonic_ns()-final_started > 5_000_000_000:
                stage["reasons"].append("report assembly exceeded 5-second allowance")
                failed=True
                break
            record=records.get(seg["id"])
            if record is None or record.get("error"):
                counts["blocked"]+=1;failed=True;continue
            if seg["stochastic_uncertain"] or seg["unstable"]:
                counts["unverified"]+=1;eligible_unverified+=1
                stage["findings"].append({"check":"examples-stochastic" if seg["stochastic_uncertain"] else "examples-unstable","severity":"info","file":selected.name,"line":seg["line"],"assertion_id":seg["id"],"message":"uncertain stochastic or unstable version/time output is unverified; a seed alone does not establish determinism"})
                continue
            actual="".join(record.get("text",[])).splitlines();cursor=0;verdict="match"
            for expected in seg["expected"]:
                if not expected.strip():continue
                candidates=[(i,compare(expected,line)) for i,line in enumerate(actual[cursor:],cursor)]
                aligned=next(((i,v) for i,v in candidates if v in ("match","output","unverified")),None)
                if aligned is None:verdict="shape";break
                cursor=aligned[0]+1
                if aligned[1]!="match":verdict=aligned[1]
            if verdict in ("shape","unverified"):
                counts["unverified"]+=1;eligible_unverified+=1
            else:
                counts["checked"]+=1
                counts["matched" if verdict=="match" else "mismatched"]+=1
            if verdict!="match":
                stage["findings"].append({"check":"examples-output" if verdict=="output" else "examples-shape","severity":"warn","file":selected.name,"line":seg["line"],"assertion_id":seg["id"],"message":f"documented output comparison: {verdict}"})
        if terminal.get("reason")!="completed" or result.get("error") or failed:
            counts["blocked"]=max(counts["blocked"],len(eligible)-counts["checked"]-eligible_unverified)
            stage["reasons"].append(result.get("error") or terminal.get("reason","missing checkpoint"))
            if result.get("error") and not stage["engine_missing"]:
                stage["findings"].append({"check":"examples-error","severity":"warn","file":selected.name,"line":1,"message":result["error"]})
            stage["state"]="unavailable" if stage["engine_missing"] else "incomplete"
        else:stage["state"]="incomplete" if counts["unverified"] else "complete"
    return stage


def sys_platform_unavailable():
    import os
    return os.name != "posix"

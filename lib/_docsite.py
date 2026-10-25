"""Bounded sitemap comparison against an immutable, locally available git tree."""
from __future__ import annotations

import posixpath
import re
import subprocess
import time
import urllib.parse as urlparse
import urllib.request as request
import xml.etree.ElementTree as ET
from pathlib import Path

TIMEOUT = 10
MAX_BYTES = 5 * 1024 * 1024


def base_url(url):
    u = urlparse.urlsplit(url)
    if u.scheme not in ("http", "https") or not u.hostname or u.username is not None or u.password is not None or u.query or u.fragment:
        raise ValueError("site requires HTTP(S) without credentials, query or fragment")
    port = u.port
    host = u.hostname.lower()
    if ":" in host:
        host = "[" + host + "]"
    authority = host + (":" + str(port) if port and port != {"http":80,"https":443}[u.scheme] else "")
    path = posixpath.normpath(u.path or "/")
    if not path.startswith("/"):
        path = "/" + path
    path = re.sub(r"%[a-fA-F0-9]{2}", lambda m:m.group().upper(), path)
    return urlparse.urlunsplit((u.scheme, authority, path.rstrip("/") + "/", "", ""))


def origin(url):
    u = urlparse.urlsplit(base_url(urlparse.urlunsplit((*urlparse.urlsplit(url)[:3], "", ""))))
    return u.scheme, u.netloc


class Redirects(request.HTTPRedirectHandler):
    def __init__(self, base):
        self.base = base
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 3 or origin(newurl) != origin(self.base):
            raise ValueError(f"redirect rejected: {newurl}; select canonical base in a fresh invocation")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def sitemap(base):
    deadline = time.monotonic() + TIMEOUT
    opener = request.build_opener(Redirects(base))
    with opener.open(base + "sitemap.xml", timeout=TIMEOUT) as response:
        content = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError("sitemap read exceeded 10-second budget")
            # read1 avoids waiting for a full large buffer on a trickling peer.
            sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
            if sock is not None:
                sock.settimeout(remaining)
            block = response.read1(min(65536, MAX_BYTES + 1 - len(content)))
            if not block:
                break
            content.extend(block)
            if len(content) > MAX_BYTES:
                raise ValueError("sitemap exceeds 5 MiB")
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("DTD/entity sitemap unsupported")
    tree = ET.fromstring(content)
    if tree.tag.rsplit("}",1)[-1] != "urlset":
        raise ValueError("only one urlset sitemap is supported; index is incomplete")
    entries = [n.text.strip() for n in tree.iter() if n.tag.rsplit("}",1)[-1] == "loc" and n.text]
    paths = set(); foreign = 0
    b = urlparse.urlsplit(base)
    for entry in entries:
        u = urlparse.urlsplit(entry)
        if origin(entry) != origin(base) or not u.path.startswith(b.path):
            foreign += 1
            continue
        path = re.sub(r"%[a-fA-F0-9]{2}", lambda m:m.group().upper(), u.path[len(b.path):])
        paths.add(path + ("?" + u.query if u.query else ""))
    if entries and not paths:
        raise ValueError("nonempty sitemap has zero entries in the requested base")
    return paths, foreign


def git(root, *args):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=20)
    if r.returncode:
        raise ValueError(r.stderr.strip() or "local git inspection failed")
    return r.stdout.strip()


def yaml_data(text):
    try:
        import yaml
    except ImportError as exc:
        raise ValueError("optional YAML reader unavailable for relevant configuration") from exc
    try:
        value = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML configuration") from exc
    if not isinstance(value, dict):
        raise ValueError("YAML configuration must be a mapping")
    return value


def select_ref(root, ref):
    repository = Path(git(root,"rev-parse","--show-toplevel"))
    selection = "explicit local ref"
    if ref is None:
        candidates = []
        for file in sorted((repository / ".github/workflows").glob("*.y*ml")):
            text = file.read_text()
            if not re.search(r"pkgdown(?:::|/)|deploy_to_branch|build_site", text):
                continue
            data = yaml_data(text)
            on = data.get("on", data.get(True, {}))
            push = on.get("push", {}) if isinstance(on, dict) else {}
            branches = push.get("branches", []) if isinstance(push, dict) else []
            if isinstance(branches, str):
                branches = [branches]
            if len(branches) != 1 or not isinstance(branches[0], str) or re.search(r"[*?\[${]", branches[0]):
                raise ValueError("ambiguous deployment workflow; supply --ref")
            for job in data.get("jobs", {}).values():
                if "uses" in job or "PKGDOWN_DEV_MODE" in str(job):
                    raise ValueError("reusable/development workflow unsupported; supply --ref and verify routes")
                for step in job.get("steps", []):
                    if "checkout" in str(step.get("uses", "")) and step.get("with", {}).get("ref") is not None:
                        raise ValueError("alternate checkout ref; supply --ref")
            candidates.append(branches[0])
        if len(candidates) > 1:
            raise ValueError("multiple deployment candidates; supply --ref")
        branch = candidates[0] if candidates else "main"
        selection = "literal workflow branch" if candidates else "fallback assumption"
        for candidate in ("origin/" + branch, branch):
            try:
                git(root, "rev-parse", "--verify", candidate + "^{commit}")
                ref = candidate; break
            except ValueError:
                pass
        if ref is None:
            raise ValueError("deployment ref not available locally; no fetch performed")
    sha = git(root, "rev-parse", "--verify", ref + "^{commit}")
    return {"ref":ref,"sha":sha,"timestamp":git(root,"show","-s","--format=%cI",sha),"selection":selection,"local_ref":True,"workflow_snapshot":"current local checkout; remote freshness unverified"}


def routes(paths, config):
    found = {}; reasons = []; counts = {"excluded":0,"unsupported":0}
    development = config.get("development", {})
    if isinstance(development, dict) and (development.get("mode", "release") != "release" or "destination" in development):
        reasons.append("development mode/destination mapping unsupported")
    if any(key in config for key in ("as_is", "build", "includes")):
        reasons.append("custom layout/build configuration unsupported")
    template = config.get("template", {})
    if isinstance(template, dict) and any(key in template for key in ("path", "package", "includes", "assets")):
        reasons.append("custom template mapping unsupported")
    for file in paths:
        path = Path(file); route = None
        if file.startswith("man/") and path.suffix == ".Rd" and len(path.parts) == 2:
            route = "reference/" + path.stem + ".html"
        elif file.startswith("vignettes/"):
            parts = list(path.parts[1:])
            if path.name.startswith("_") or "tutorials" in parts:
                counts["excluded"] += 1; continue
            if path.suffix != ".Rmd":
                if path.suffix in (".qmd", ".md", ".Rmarkdown"):
                    counts["unsupported"] += 1; reasons.append(f"unsupported article source: {file}")
                continue
            if parts[0] == "articles":
                parts = parts[1:]
            route = "articles/" + str(Path(*parts).with_suffix(".html"))
        if route:
            if route in found:
                reasons.append(f"route collision: {route}")
            else:
                found[route] = file
    return found, reasons, counts


def audit(root: Path, *, url, ref=None):
    stage = {"state":"incomplete","counts":{"checked":0,"missing":0,"extra":0,"unreleased":0},"provenance":{},"reasons":[],"engine_missing":[],"findings":[]}
    try:
        base = base_url(url)
        provenance = select_ref(root,ref); stage["provenance"] = {**provenance,"requested_base":base}
        top = Path(git(root,"rev-parse","--show-toplevel"))
        # Git owns package-relative casing on case-insensitive filesystems.
        prefix = git(root,"rev-parse","--show-prefix")
        tree = git(root,"ls-tree","--full-tree","-r","--name-only",provenance["sha"]).splitlines()
        paths = [p[len(prefix):] for p in tree if p.startswith(prefix)]
        config = {}
        configs = [p for p in paths if p in ("_pkgdown.yml","_pkgdown.yaml") or p.startswith("pkgdown/") and p.endswith((".yml",".yaml"))]
        if len(configs) > 1 or any(p.startswith("pkgdown/") for p in configs):
            stage["reasons"].append("pkgdown configuration overlays unsupported")
        for config_file in configs:
            config.update(yaml_data(git(root,"show",provenance["sha"] + ":" + prefix + config_file)))
        if config.get("url") and base_url(config["url"]) != base:
            raise ValueError("source url disagrees; select canonical URL in a fresh invocation")
        expected, reasons, counts = routes(paths,config)
        stage["reasons"].extend(reasons); stage["counts"].update(counts)
        for route,file in list(expected.items()):
            if not file.endswith(".Rmd"):continue
            source=git(root,"show",provenance["sha"]+":"+prefix+file)
            if not source.startswith("---"):continue
            parts=source.split("---",2)
            if len(parts)!=3:
                stage["reasons"].append("unterminated article frontmatter: "+file);continue
            metadata=yaml_data(parts[1])
            output=metadata.get("output")
            formats=list(output) if isinstance(output,dict) else [output] if output else []
            custom=any(format not in ("html_document","html_vignette","rmarkdown::html_document","rmarkdown::html_vignette") for format in formats)
            settings=metadata.get("pkgdown",{})
            if custom or isinstance(settings,dict) and settings.get("as_is") or metadata.get("as_is"):
                stage["reasons"].append("unsupported article output/as_is: "+file)
                stage["counts"]["unsupported"]+=1
                del expected[route]
        # Even explicit ref cannot certify development workflow transforms.
        for workflow in (top/".github/workflows").glob("*.y*ml"):
            if "PKGDOWN_DEV_MODE" in workflow.read_text():
                stage["reasons"].append("workflow PKGDOWN_DEV_MODE mapping unsupported")
        if any("development" in r or "PKGDOWN_DEV_MODE" in r for r in stage["reasons"]):
            return stage
        observed, foreign = sitemap(base)
        stage["counts"].update(checked=len(expected), foreign=foreign)
        if foreign:
            stage["reasons"].append(f"excluded {foreign} foreign sitemap entries")
        def finding(check,severity,file,message):
            stage["findings"].append({"check":check,"severity":severity,"file":file,"line":1,"message":message})
        for route,file in expected.items():
            if route not in observed:
                stage["counts"]["missing"] += 1
                finding("site-missing-page","warn",file,f"{base}{route} absent from the sitemap")
        for route in sorted(observed - expected.keys()):
            if route.startswith(("articles/","reference/")) and route not in ("articles/index.html","reference/index.html"):
                stage["counts"]["extra"] += 1
                finding("site-extra-page","info","",f"extra supported-surface sitemap route: {base}{route}")
        working = [p.relative_to(root).as_posix() for folder in ("man","vignettes") for p in (root/folder).rglob("*") if p.is_file()]
        current,_,_ = routes(working,config)
        head_paths = git(root,"ls-tree","--full-tree","-r","--name-only","HEAD").splitlines()
        for route,file in current.items():
            if route not in expected:
                stage["counts"]["unreleased"] += 1
                dirty = prefix + file not in head_paths
                finding("site-unreleased-page","info",file,f"{'dirty-tree' if dirty else 'checkout-only'} unreleased route: {base}{route}")
        blocking = [r for r in stage["reasons"] if not r.startswith("excluded ")]
        stage["state"] = "incomplete" if blocking else "complete"
    except (ValueError,OSError,subprocess.SubprocessError,ET.ParseError) as exc:
        stage["reasons"].append(str(exc))
    return stage

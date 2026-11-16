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


# pkgdown 2.2.1 rules mirrored here (differentially tested in tests/differential/; see SPEC-site-audit-quarto-devmode).
PKGDOWN_RULE = "2.2.1"
VALID_MODES = ("auto", "default", "release", "devel", "unreleased")
CONFIG_CANDIDATES = ("_pkgdown.yml", "_pkgdown.yaml", "pkgdown/_pkgdown.yml", "pkgdown/_pkgdown.yaml",
                     "inst/_pkgdown.yml", "inst/_pkgdown.yaml")
ARTICLE_SUFFIXES = (".Rmd", ".rmd", ".qmd")  # pkgdown globs `\.[Rrq]md$`: not .md, .Rmarkdown, .RMD or .Qmd
HTML_OUTPUTS = ("html_document", "html_vignette", "rmarkdown::html_document", "rmarkdown::html_vignette")
OVERRIDE_KEY = re.compile(r"^output[-_](file|ext|dir)$")
DEFAULT_QUARTO_PROJECT = {"project": {"render": ["*.qmd"]}}
INT_MAX = 2 ** 31 - 1


def dev_mode_auto(version):
    """pkgdown 2.2.1 `dev_mode_auto`; an unparseable version raises (R's `package_version` errors too)."""
    text = version.strip() if isinstance(version, str) else ""
    if not re.fullmatch(r"[0-9]+(?:[.-][0-9]+)+", text):
        raise ValueError(f"unparseable DESCRIPTION Version: {version!r}")
    parts = [int(x) for x in re.split(r"[.-]", text)]
    if any(x > INT_MAX for x in parts):
        raise ValueError(f"unparseable DESCRIPTION Version: {version!r}")
    if len(parts) < 3:
        return "release"
    if len(parts) == 3:
        return "devel" if parts[2] >= 9000 else "release"
    return "unreleased" if parts[:3] == [0, 0, 0] else "devel"


def resolve_development(config, version=None):
    """Resolve `development.mode`/`destination` the way pkgdown does; never guess (raises ValueError).

    `version` (or a callable returning it) is only consulted for `mode: auto`.
    """
    development = config.get("development")
    if development is None:
        development = {}
    if not isinstance(development, dict):
        raise ValueError("development configuration must be a mapping")
    mode = development.get("mode", "default")
    if not isinstance(mode, str) or mode not in VALID_MODES:
        raise ValueError(f"development.mode unsupported: {mode!r}")
    destination = development.get("destination", "dev")
    if not isinstance(destination, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", destination):
        raise ValueError(f"development.destination unsupported: {destination!r}")
    if mode == "auto":
        mode = dev_mode_auto(version() if callable(version) else version)
    in_dev = mode == "devel"
    return {"mode": mode, "destination": destination, "in_dev": in_dev,
            "prefix": destination + "/" if in_dev else "", "pkgdown_rule": PKGDOWN_RULE}


def bootstrap_version(config):
    """pkgdown's Bootstrap version (unset means 3); anything it would reject or take from a template package raises."""
    template = config.get("template")
    if template is None:
        template = {}
    if not isinstance(template, dict):
        raise ValueError("template configuration must be a mapping")
    bslib = template.get("bslib")
    bslib_version = bslib.get("version") if isinstance(bslib, dict) else None
    if template.get("bootstrap") is not None and bslib_version is not None:
        raise ValueError("template.bootstrap and template.bslib.version are both set")
    value = template.get("bootstrap") if template.get("bootstrap") is not None else bslib_version
    if value is None:
        if "package" in template:
            raise ValueError("Bootstrap version may come from template.package and cannot be resolved")
        return 3
    try:
        number = float(value) if not isinstance(value, bool) else None
    except (TypeError, ValueError):
        number = None
    if number not in (3.0, 4.0, 5.0):
        raise ValueError(f"template Bootstrap version unsupported: {value!r}")
    return int(number)  # pkgdown keeps a configured 4 (with a warning); only `== 3` matters here


def match_base(requested, config_url, resolved):
    """Strict base match: `requested` must equal `config.url + prefix` (never appended on the caller's behalf)."""
    requested = base_url(requested)
    destination = resolved["destination"]
    if config_url:
        root = base_url(config_url)
        dev = root + destination + "/"
        if resolved["in_dev"]:
            if requested == dev:
                return
            if requested == root:
                raise ValueError(f"requested base lacks the dev prefix: development mode is devel, so audit {dev}")
        else:
            if requested == root:
                return
            if requested == dev:
                raise ValueError(f"requested base is the dev URL but development.mode resolves to the root: audit {root}")
        raise ValueError("source url disagrees; select canonical URL in a fresh invocation")
    ends = requested.endswith("/" + destination + "/")
    if resolved["in_dev"] and not ends:
        raise ValueError(f"requested base lacks the dev prefix: development mode is devel, so the URL must end in /{destination}/")
    if not resolved["in_dev"] and ends:
        raise ValueError(f"requested base ends in /{destination}/ but development.mode resolves to the root")


def routes(paths, config):
    found = {}; reasons = []; counts = {"excluded":0,"unsupported":0}
    try:
        resolve_development(config, "1.0.0")  # shape and value checks only; `auto` needs the pinned DESCRIPTION
    except ValueError as exc:
        reasons.append(str(exc))
    if any(key in config for key in ("as_is", "build", "includes")):
        reasons.append("custom layout/build configuration unsupported")
    template = config.get("template", {})
    if isinstance(template, dict) and any(key in template for key in ("path", "package", "includes", "assets")):
        reasons.append("custom template mapping unsupported")
    for file in paths:
        path = Path(file); route = None
        if file.startswith("man/") and path.suffix == ".Rd" and len(path.parts) == 2:
            route = "reference/" + path.stem + ".html"
        elif file.startswith("vignettes/") and path.suffix in ARTICLE_SUFFIXES:
            relative = file[len("vignettes/"):]
            # pkgdown: `^_` on the file name and the regex `^tutorials` on the directory part only.
            if path.name.startswith("_") or posixpath.dirname(relative).startswith("tutorials"):
                counts["excluded"] += 1; continue
            parts = list(Path(relative).parts)
            if parts[0] == "articles":
                parts = parts[1:]
            route = "articles/" + str(Path(*parts).with_suffix(".html"))
        if route:
            if route in found:
                reasons.append(f"route collision: {route}")
            else:
                found[route] = file
    return found, reasons, counts


def override_key(node):
    """First route-changing key anywhere in a front-matter structure, else None."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and OVERRIDE_KEY.match(key):
                return key
            found = override_key(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = override_key(item)
            if found:
                return found
    return None


def non_html_format(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value != "html"
    if isinstance(value, dict):
        return any(key != "html" for key in value)
    if isinstance(value, list):
        return any(non_html_format(item) for item in value)
    return True


def article_problem(file, metadata):
    """Why an article's output route cannot be inferred statically, else None. `.Rmd`/`.rmd` and `.qmd` differ."""
    key = override_key(metadata)
    if key is None and "knit" in metadata:
        key = "knit"
    if key:
        return f"route-changing article override ({key}): {file}"
    settings = metadata.get("pkgdown")
    if file.endswith(".qmd"):
        if non_html_format(metadata.get("format")):
            return f"unsupported article format (format): {file}"
    else:
        output = metadata.get("output")
        formats = list(output) if isinstance(output, dict) else [output] if output else []
        if any(format not in HTML_OUTPUTS for format in formats):
            return f"unsupported article output/as_is: {file}"
        if settings is not None and not isinstance(settings, dict):
            return f"unsupported article output extension (pkgdown): {file}"
        if isinstance(settings, dict) and "extension" in settings and settings["extension"] != "html":
            return f"unsupported article output extension (pkgdown.extension): {file}"
    if isinstance(settings, dict) and settings.get("as_is") or metadata.get("as_is"):
        return f"unsupported article output/as_is: {file}"
    return None


def workflow_blocks(root, sha, tree):
    """Reasons the workflows at the pinned SHA make a static route mapping unverifiable (read via `git show`)."""
    reasons = []
    for path in tree:
        if not re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", path):
            continue
        text = git(root, "show", sha + ":" + path)
        if "PKGDOWN_DEV_MODE" in text:
            reasons.append("workflow PKGDOWN_DEV_MODE mapping unsupported")
        elif re.search(r"(?i)pkgdown|deploy_to_branch|build_site", text):
            jobs = yaml_data(text).get("jobs", {})
            if isinstance(jobs, dict) and any(isinstance(job, dict) and "uses" in job for job in jobs.values()):
                reasons.append(f"reusable workflow job unsupported ({path}); the deployed routes cannot be verified")
    return list(dict.fromkeys(reasons))


def audit(root: Path, *, url, ref=None):
    stage = {"state":"incomplete","counts":{"checked":0,"missing":0,"extra":0,"unreleased":0},"provenance":{},"reasons":[],"engine_missing":[],"findings":[],"content_freshness":"unverified"}
    try:
        base = base_url(url)
        provenance = select_ref(root,ref); stage["provenance"] = {**provenance,"requested_base":base}
        sha = provenance["sha"]
        # Git owns package-relative casing on case-insensitive filesystems.
        prefix = git(root,"rev-parse","--show-prefix")
        tree = git(root,"ls-tree","--full-tree","-r","--name-only",sha).splitlines()
        paths = [p[len(prefix):] for p in tree if p.startswith(prefix)]
        # pkgdown reads the first existing candidate and never merges; any other config-like file is an overlay.
        present = [p for p in CONFIG_CANDIDATES if p in paths]
        if len(present) > 1 or any("/" in p for p in present) or any(p.startswith("pkgdown/") and p.endswith((".yml",".yaml")) for p in paths):
            stage["reasons"].append("pkgdown configuration overlays unsupported")
        config = yaml_data(git(root,"show",sha + ":" + prefix + present[0])) if present else {}
        def pinned_version():
            description = git(root,"show",sha + ":" + prefix + "DESCRIPTION")
            match = re.search(r"^Version:[ \t]*(\S.*?)[ \t]*$", description, re.M)
            if not match:
                raise ValueError("DESCRIPTION has no Version field")
            return match.group(1)
        development = resolve_development(config, pinned_version)
        stage["development"] = {k: development[k] for k in ("mode","prefix","destination","pkgdown_rule")}
        if development["in_dev"] and bootstrap_version(config) == 3:
            raise ValueError("development mode with Bootstrap 3 writes an unprefixed sitemap; unsupported")
        source_url = config.get("url")
        if source_url is not None and not isinstance(source_url, str):
            raise ValueError("pkgdown url must be a string")
        match_base(base, source_url, development)
        expected, reasons, counts = routes(paths,config)
        stage["reasons"].extend(reasons); stage["counts"].update(counts)
        quarto = [p for p in ("vignettes/_quarto.yaml","vignettes/_quarto.yml") if p in paths]
        if quarto and any(f.endswith(".qmd") for f in expected.values()):
            try:
                if len(quarto) > 1:
                    raise ValueError("both present")
                if yaml_data(git(root,"show",sha + ":" + prefix + quarto[0])) != DEFAULT_QUARTO_PROJECT:
                    raise ValueError("not the pkgdown default")
            except ValueError:
                stage["reasons"].append("unsupported Quarto project configuration: " + ", ".join(quarto))
        refused=set()
        for route,file in list(expected.items()):
            if not file.endswith(ARTICLE_SUFFIXES):continue
            source=git(root,"show",sha+":"+prefix+file)
            if not source.startswith("---"):continue
            parts=source.split("---",2)
            if len(parts)!=3:
                stage["reasons"].append("unterminated article frontmatter: "+file);continue
            problem=article_problem(file,yaml_data(parts[1]))
            if problem:
                stage["reasons"].append(problem)
                stage["counts"]["unsupported"]+=1
                refused.add(file)
                del expected[route]
        # Even an explicit ref cannot certify workflow transforms: read them at the pinned SHA, not the working tree.
        blocked = workflow_blocks(root, sha, tree)
        if blocked:
            stage["reasons"].extend(blocked)
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
            if route not in expected and file not in refused:
                stage["counts"]["unreleased"] += 1
                dirty = prefix + file not in head_paths
                finding("site-unreleased-page","info",file,f"{'dirty-tree' if dirty else 'checkout-only'} unreleased route: {base}{route}")
        blocking = [r for r in stage["reasons"] if not r.startswith("excluded ")]
        stage["state"] = "incomplete" if blocking else "complete"
    except (ValueError,OSError,subprocess.SubprocessError,ET.ParseError) as exc:
        stage["reasons"].append(str(exc))
    return stage

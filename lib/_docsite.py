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


SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


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
    local = tree.tag.rsplit("}", 1)[-1]
    if local == "urlset" and tree.tag != SITEMAP_NS + "urlset":
        # A urlset outside the sitemaps.org 0.9 namespace (absent or different) is not a sitemap this audit can read
        # safely: counting its `loc` elements anyway is what let extension elements stand in for pages.
        raise ValueError(f"sitemap urlset is not in the {SITEMAP_NS[1:-1]} namespace")
    if tree.tag != SITEMAP_NS + "urlset":
        raise ValueError("only one urlset sitemap is supported; index is incomplete")
    # A page is a `loc` that is a direct child of a `url` that is a direct child of the urlset, all in the sitemap
    # namespace. An extension `loc` (image/video/xhtml) or one nested elsewhere is not a page.
    entries = [loc.text.strip() for url in tree.findall(SITEMAP_NS + "url") for loc in url.findall(SITEMAP_NS + "loc") if loc.text]
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


def git(root, *args, strip=True):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    if r.returncode:
        raise ValueError(r.stderr.strip() or "local git inspection failed")
    return r.stdout.strip() if strip else r.stdout


def tree_modes(root, rev):
    """`{path: mode}` for the whole tree at `rev`. NUL-separated (`-z`): without it git C-quotes non-ASCII paths."""
    r = subprocess.run(["git", "ls-tree", "-z", "--full-tree", "-r", rev], cwd=root, capture_output=True, timeout=20)
    if r.returncode:
        raise ValueError(r.stderr.decode("utf-8", "replace").strip() or "local git inspection failed")
    modes = {}
    for entry in r.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if entry:
            meta, _, path = entry.partition("\t")
            modes[path] = meta.split(" ", 1)[0]
    return modes


def yaml_data(text):
    try:
        import yaml
    except ImportError as exc:
        raise ValueError("optional YAML reader unavailable for relevant configuration") from exc
    try:
        value = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML configuration") from exc
    except RecursionError as exc:
        raise ValueError("YAML configuration is too deeply nested") from exc
    if not isinstance(value, dict):
        raise ValueError("YAML configuration must be a mapping")
    return value


def workflow_jobs(data, name):
    """`(job name, job, steps)` for every job; any structure GitHub itself would reject raises ValueError naming the file."""
    def bad(what):
        return ValueError(f"malformed workflow structure ({name}): {what}")
    jobs = data["jobs"] if "jobs" in data else {}
    if not isinstance(jobs, dict):
        raise bad("jobs must be a mapping")
    out = []
    for key, job in jobs.items():
        if not isinstance(job, dict):
            raise bad(f"job {key} must be a mapping")
        steps = job["steps"] if "steps" in job else []
        if not isinstance(steps, list):
            raise bad(f"job {key} steps must be a list")
        for step in steps:
            if not isinstance(step, dict):
                raise bad(f"a step of job {key} must be a mapping")
            if "uses" in step and not isinstance(step["uses"], str):
                raise bad(f"a step of job {key} has a non-string uses")
            if "with" in step and not isinstance(step["with"], dict):
                raise bad(f"a step of job {key} has a non-mapping with")
        out.append((key, job, steps))
    return out


def select_ref(root, ref):
    repository = Path(git(root,"rev-parse","--show-toplevel"))
    selection = "explicit local ref"
    if ref is None:
        candidates = []
        for file in sorted((repository / ".github/workflows").glob("*.y*ml")):
            text = file.read_text()
            if not re.search(r"pkgdown|deploy_to_branch|build_site", text, re.I):
                continue
            try:
                data = yaml_data(text)
            except ValueError as exc:
                raise ValueError(f"malformed workflow ({file.name}): {exc}") from exc
            on = data.get("on", data.get(True, {}))
            push = on.get("push", {}) if isinstance(on, dict) else {}
            branches = push.get("branches", []) if isinstance(push, dict) else []
            if isinstance(branches, str):
                branches = [branches]
            if len(branches) != 1 or not isinstance(branches[0], str) or re.search(r"[*?\[${]", branches[0]):
                raise ValueError("ambiguous deployment workflow; supply --ref")
            for _, job, steps in workflow_jobs(data, file.name):
                if "uses" in job or mentions_dev_mode(*(value for _, value in yaml_walk(job))):
                    raise ValueError("reusable/development workflow unsupported; supply --ref and verify routes")
                for step in steps:
                    if "checkout" in str(step.get("uses", "")) and (step.get("with") or {}).get("ref") is not None:
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
OVERRIDE_KEY = re.compile(r"^output[-_](file|ext|dir)$", re.I)
DEFAULT_QUARTO_PROJECT = {"project": {"render": ["*.qmd"]}}
INT_MAX = 2 ** 31 - 1


def parse_version(version):
    """R's `package_version` components (`.` or `-` separated, at least two); anything else raises ValueError."""
    text = version.strip() if isinstance(version, str) else ""
    if not re.fullmatch(r"[0-9]+(?:[.-][0-9]+)+", text):
        raise ValueError(f"unparseable DESCRIPTION Version: {version!r}")
    parts = [int(x) for x in re.split(r"[.-]", text)]
    if any(x > INT_MAX for x in parts):
        raise ValueError(f"unparseable DESCRIPTION Version: {version!r}")
    return parts


def dev_mode_auto(version):
    """pkgdown 2.2.1 `dev_mode_auto`; an unparseable version raises (R's `package_version` errors too)."""
    parts = parse_version(version)
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


def override_key(node, seen=None):
    """First route-changing key anywhere in a front-matter structure, else None.

    YAML aliases share nodes: each container is visited once, so an alias bomb or a self-referencing anchor is cheap.
    """
    seen = set() if seen is None else seen
    if isinstance(node, (dict, list)):
        if id(node) in seen:
            return None
        seen.add(id(node))
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and OVERRIDE_KEY.match(key):
                return key
            found = override_key(value, seen)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = override_key(item, seen)
            if found:
                return found
    return None


def non_html_format(value, seen=None):
    seen = set() if seen is None else seen
    if value is None:
        return False
    if isinstance(value, str):
        return value != "html"
    if isinstance(value, dict):
        return any(key != "html" for key in value)
    if isinstance(value, list):
        if id(value) in seen:
            return False
        seen.add(id(value))
        return any(non_html_format(item, seen) for item in value)
    return True


def front_matter(source):
    """`(yaml text, terminated)`; `(None, True)` when there is no front matter. rmarkdown's rule, by delimiter lines:
    the first non-blank line is `---`, closed by the next line that is exactly `---` or `...` (never a substring)."""
    lines = source.lstrip("\ufeff").splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start == len(lines) or not re.fullmatch(r"---\s*", lines[start]):
        return None, True
    for end in range(start + 1, len(lines)):
        if re.fullmatch(r"(---|\.\.\.)\s*", lines[end]):
            return "\n".join(lines[start + 1:end]), True
    return None, False


def article_problem(file, metadata):
    """Why an article's output route cannot be inferred statically, else None. `.Rmd`/`.rmd` and `.qmd` differ."""
    key = override_key(metadata)
    if key is None and mapping_key(metadata, "knit") is not None:
        key = "knit"
    if key:
        return f"route-changing article override ({key}): {file}"
    settings = mapping_key(metadata, "pkgdown")
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
    if isinstance(settings, dict) and mapping_key(settings, "as_is") or mapping_key(metadata, "as_is"):
        return f"unsupported article output/as_is: {file}"
    return None


def yaml_walk(node):
    """Yield `("key", text)` and `("str", text)` for every string key and string value in a parsed YAML structure.

    Parsed, so YAML spellings that hide a name from a raw-text match (quoted keys, `\\x5f` escapes, folded scalars,
    flow mappings, anchors and merge keys) are seen as the strings they are. Iterative with a visited set: aliases
    share nodes, so an alias bomb is walked once and very deep nesting cannot exhaust the Python stack.
    """
    stack, seen = [node], set()
    while stack:
        item = stack.pop()
        if isinstance(item, (dict, list, tuple)):
            if id(item) in seen:
                continue
            seen.add(id(item))
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(key, str):
                        yield "key", key
                    stack.append(key)
                    stack.append(value)
            else:
                stack.extend(item)
        elif isinstance(item, str):
            yield "str", item


def source_text(text, data=None):
    """The raw text plus every parsed string of the same YAML document: what a text match must scan."""
    return text if data is None else text + "\n" + "\n".join(value for _, value in yaml_walk(data))


def mentions_dev_mode(*texts):
    """`PKGDOWN_DEV_MODE` spelled any plausible way: any case, with quotes, backticks, commas, `+`, parentheses,
    underscores or whitespace between its parts, so `paste0("PKGDOWN_DEV_", "MODE")` and `paste("PKGDOWN", "DEV", "MODE",
    sep = "_")` count. A name built any other way (from a variable, a file, a decoded string) is not detected."""
    return any("PKGDOWNDEVMODE" in re.sub(r"[\s\"'`,+()_\\]", "", text).upper() for text in texts)


def mapping_key(mapping, name):
    """The value of `name` in a front-matter mapping, matching case-insensitively with `-` and `_` interchangeable."""
    for key, value in mapping.items():
        if isinstance(key, str) and key.lower().replace("-", "_") == name:
            return value
    return None


DEV_MODE_VARIABLE = "PKGDOWN_DEV_MODE"
STARTUP_FILES = (".Renviron", ".Rprofile", ".Renviron.site", ".Rprofile.site")
MAX_LOCAL_ACTIONS = 25


PAGES_SUBDIR_INPUTS = ("target-folder", "destination-dir")   # JamesIves/github-pages-deploy-action, peaceiris/actions-gh-pages


def deploy_subdirectory(text, pkgdown_repo=True, data=None):
    """A deploy that publishes below the site root moves every route.

    Two signals. `deploy_to_branch(subdir = )` is R code, so it is matched as text (on the raw text plus the parsed YAML
    strings): the argument name may be quoted or backticked and the call may span lines or continuations, and since
    `subdir` follows `...` in the signature it can only be named. A Pages `target-folder` / `destination-dir` input in a
    pkgdown repository (`pkgdown_repo`: a pkgdown config at the pinned SHA, or a workflow naming pkgdown; build and
    deploy may be separate files) is read from the PARSED YAML keys at any depth (so quoted, escaped, flow, aliased and
    merged spellings count), with a quote-tolerant text match as a second net. An unrelated input of that name in such a
    repository also blocks. A deploy done by a script the workflow merely runs is not detected.
    """
    haystack = source_text(text, data)
    if "deploy_to_branch" in haystack and re.search(r"\bsubdir[\"'`]?\s*=", haystack):
        return True
    if not pkgdown_repo:
        return False
    if re.search(r"\b(?:target[-_]folder|destination[-_]dir)[\"']?\s*:", haystack, re.I):
        return True
    return data is not None and any(kind == "key" and value.lower().replace("_", "-") in PAGES_SUBDIR_INPUTS for kind, value in yaml_walk(data))


def local_action_reasons(root, sha, files, uses, seen, pkgdown_repo=True):
    """Scan a local composite action (`uses: ./path`, relative to the repository root) and the local actions it calls."""
    target = posixpath.normpath(uses[2:] or ".")
    if target.startswith("..") or target in seen:
        return [f"local action {uses} unresolvable at the pinned ref; the deployed routes cannot be verified"] if target.startswith("..") else []
    seen.add(target)
    if len(seen) > MAX_LOCAL_ACTIONS:
        return ["too many local actions to scan; the deployed routes cannot be verified"]
    names = [n for n in ("action.yml", "action.yaml") if posixpath.normpath(posixpath.join(target, n)) in files]
    if not names:
        return [f"local action {target} unresolvable at the pinned ref (no action.yml); the deployed routes cannot be verified"]
    path = posixpath.normpath(posixpath.join(target, names[0]))
    text = git(root, "show", sha + ":" + path, strip=False)
    reasons = []
    try:
        data = yaml_data(text)
    except ValueError:
        data = None   # reported as malformed below; the raw text is still scanned
    if mentions_dev_mode(source_text(text, data)):
        reasons.append(f"{DEV_MODE_VARIABLE} set in local action {path}; development mode mapping unsupported")
    if deploy_subdirectory(text, pkgdown_repo, data):
        reasons.append(f"deploy to a subdirectory in local action {path}; the deployed routes cannot be verified")
    try:
        data = yaml_data(text)
        runs = data.get("runs")
        if not isinstance(runs, dict) or runs.get("using") != "composite":
            reasons.append(f"local action {path} is not a composite action and cannot be scanned; the deployed routes cannot be verified")
        else:
            steps = runs.get("steps")
            if not isinstance(steps, list) or not all(isinstance(x, dict) and isinstance(x.get("uses", ""), str) for x in steps):
                raise ValueError("steps must be a list of mappings")
            for step in steps:
                if step.get("uses", "").startswith("./"):
                    reasons.extend(local_action_reasons(root, sha, files, step["uses"], seen, pkgdown_repo))
    except ValueError as exc:
        reasons.append(f"malformed local action ({path}): {exc}")
    return reasons


def workflow_blocks(root, sha, tree, prefix=""):
    """Reasons the pinned tree makes a static route mapping unverifiable (everything is read via `git show` at the SHA).

    Scanned: workflows (`PKGDOWN_DEV_MODE`, any job-level `uses:`, local composite actions, deploys below the site
    root, malformed structure) and the R startup files at the repository root and the package directory. Names built
    dynamically or set inside scripts the workflow merely runs are not detected.
    """
    reasons = []
    files = set(tree)
    workflows = sorted(p for p in files if re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", p))
    texts = {p: git(root, "show", sha + ":" + p, strip=False) for p in workflows}
    # "This is a pkgdown package" comes from the repository, not from workflow wording: a pkgdown config for the package
    # directory under audit at the pinned SHA (the same candidates the config reader uses). Build and deploy can sit in
    # different workflows and the build can hide in a local action, so neither need contain the word. Text detection is
    # kept only for what a config misses: pkgdown builds without a config file, so a workflow that names it still counts.
    parsed, errors = {}, {}
    for path, text in texts.items():
        try:
            parsed[path] = yaml_data(text)
        except ValueError as exc:
            errors[path] = exc   # reported as malformed below; the raw text is still scanned
    pkgdown_repo = (any(prefix + candidate in files for candidate in CONFIG_CANDIDATES)
                    or any("pkgdown" in source_text(t, parsed.get(p)).lower() for p, t in texts.items()))
    startup_dirs = {"", prefix.rstrip("/")}
    for path in sorted(files):
        if posixpath.basename(path) in STARTUP_FILES and posixpath.dirname(path) in startup_dirs:
            if mentions_dev_mode(git(root, "show", sha + ":" + path, strip=False)):
                reasons.append(f"{DEV_MODE_VARIABLE} set in {path}; development mode mapping unsupported")
    for path, text in texts.items():
        if mentions_dev_mode(source_text(text, parsed.get(path))):
            reasons.append(f"workflow PKGDOWN_DEV_MODE mapping unsupported ({path})")
        if deploy_subdirectory(text, pkgdown_repo, parsed.get(path)):
            reasons.append(f"deploy to a subdirectory ({path}); the deployed routes cannot be verified")
        try:
            if path in errors:
                raise errors[path]
            jobs = workflow_jobs(parsed[path], path)
        except ValueError as exc:
            reasons.append(str(exc) if str(exc).startswith("malformed workflow") else f"malformed workflow ({path}): {exc}")
            continue
        seen = set()
        for _, job, steps in jobs:
            # SPEC decision 2: ANY job-level `uses:` is unverifiable. A reusable workflow can build or deploy the
            # site without ever naming pkgdown, so no keyword gate; step-level `uses:` (actions) is unaffected.
            if "uses" in job:
                reasons.append(f"reusable workflow job unsupported ({path}); the deployed routes cannot be verified")
            for step in steps:
                if step.get("uses", "").startswith("./"):
                    reasons.extend(local_action_reasons(root, sha, files, step["uses"], seen, pkgdown_repo))
    return list(dict.fromkeys(reasons))


def audit(root: Path, *, url, ref=None):
    stage = {"state":"incomplete","counts":{"checked":0,"missing":0,"extra":0,"unreleased":0},"provenance":{},"reasons":[],"engine_missing":[],"findings":[],"content_freshness":"unverified"}
    try:
        base = base_url(url)
        provenance = select_ref(root,ref); stage["provenance"] = {**provenance,"requested_base":base}
        sha = provenance["sha"]
        # Git owns package-relative casing on case-insensitive filesystems.
        prefix = git(root,"rev-parse","--show-prefix")
        modes = tree_modes(root, sha)
        tree = list(modes)
        package_modes = {p[len(prefix):]: m for p, m in modes.items() if p.startswith(prefix)}
        paths = list(package_modes)
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
        version = pinned_version()  # every mode: an absent or unparseable Version is incomplete, never defaulted
        parse_version(version)
        development = resolve_development(config, version)
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
        # `git show` of a symlink returns the link text, never the file: a symlinked article cannot be read statically.
        for link in sorted(p for p, m in package_modes.items() if m == "120000" and p.startswith("vignettes/")):
            stage["reasons"].append(f"symlinked vignette entry unsupported (not read as article content): {link}")
            for route, file in list(expected.items()):
                if file == link:
                    stage["counts"]["unsupported"] += 1
                    refused.add(file)
                    del expected[route]
        # Directory-level output configuration. pkgdown's behavior for these files was not rendered, so any that
        # could change a format or route is refused rather than guessed.
        names = {"qmd": [], "rmd": []}
        for p in paths:
            if not p.startswith("vignettes/") or not re.search(r"\.ya?ml$", p):
                continue
            name = posixpath.basename(p)
            nested_project = re.fullmatch(r"_quarto\.ya?ml", name) and p.count("/") > 1
            if re.fullmatch(r"_metadata\.ya?ml|_quarto-.+\.ya?ml", name) or nested_project:
                names["qmd"].append(p)
            elif re.fullmatch(r"_output\.ya?ml", name):
                names["rmd"].append(p)
        for kind, suffixes in (("qmd", (".qmd",)), ("rmd", (".Rmd", ".rmd"))):
            if names[kind] and any(f.endswith(suffixes) for f in expected.values()):
                stage["reasons"].append("directory-level article configuration unsupported ("
                                        + ", ".join(names[kind]) + "); it can change the output format or route")
        for route,file in list(expected.items()):
            if not file.endswith(ARTICLE_SUFFIXES):continue
            text,terminated=front_matter(git(root,"show",sha+":"+prefix+file,strip=False))
            if not terminated:
                stage["reasons"].append("unterminated article frontmatter: "+file);continue
            if text is None:continue
            problem=article_problem(file,yaml_data(text))
            if problem:
                stage["reasons"].append(problem)
                stage["counts"]["unsupported"]+=1
                refused.add(file)
                del expected[route]
        # Even an explicit ref cannot certify workflow transforms: read them at the pinned SHA, not the working tree.
        blocked = workflow_blocks(root, sha, tree, prefix)
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
        head_paths = tree_modes(root, "HEAD")
        for route,file in current.items():
            if route not in expected and file not in refused:
                stage["counts"]["unreleased"] += 1
                dirty = prefix + file not in head_paths
                finding("site-unreleased-page","info",file,f"{'dirty-tree' if dirty else 'checkout-only'} unreleased route: {base}{route}")
        blocking = [r for r in stage["reasons"] if not r.startswith("excluded ")]
        stage["state"] = "incomplete" if blocking else "complete"
    except (ValueError,OSError,subprocess.SubprocessError,ET.ParseError) as exc:
        stage["reasons"].append(str(exc))
    except (RecursionError,TypeError,AttributeError,KeyError) as exc:  # fail closed on a structure no guard anticipated
        stage["reasons"].append(f"unexpected input structure ({type(exc).__name__}); the audit cannot complete")
    return stage

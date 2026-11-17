"""Bounded sitemap comparison against an immutable, locally available git tree."""
from __future__ import annotations

import posixpath
import fnmatch
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


MAX_SCRIPT_DEPTH = 5
MAX_SCRIPT_FILES = 40
MAX_SCRIPT_BYTES = 1 << 20
DYNAMIC_PATH = re.compile(r"[$`*?\[{]|<\(")      # variable, command/process substitution, expression or glob: not a literal path
R_SOURCE = re.compile(r"""\b(?:source|sys\.source)\s*\(\s*(?:(?:file|exprs)\s*=\s*)?(?:"([^"]*)"|'([^']*)'|(\S))""")
R_SYSTEM = re.compile(r"""\b(system2?|shell)\s*\(\s*(?:(?:command|intern)\s*=\s*)?(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|(\S))""")
SHELL_PROGRAMS = ("bash", "sh", "zsh", "dash")
# The scan follows `Rscript`/`R`, `bash`/`sh`/`zsh`/`dash`, `python <script>`, `make`, `source`, `eval` and `./x`. Every other
# executable is opaque (`ScriptScan.opaque`) unless it is listed here: commands that cannot produce site files, or that
# other detections already cover (`git` and `cp`/`mv`/`rsync`/`ln` by `stage_evidence`, `curl`/`wget` and `gh` as downloads).
# A workflow that stages and pushes and runs anything else is publish-capable, so the list stays short and is not extended
# for each new site generator.
ALLOWED_PROGRAMS = frozenset({
    "git", "echo", "printf", "cat", "ls", "pwd", "cd", "mkdir", "rm", "cp", "mv", "touch", "test", "[", "[[", "true", "false", "exit",
    "export", "set", "unset", "sleep", "date", "env", "which", "grep", "egrep", "fgrep", "sed", "awk", "head", "tail", "tee", "sort", "uniq",
    "wc", "tr", "cut", "find", "xargs", "jq", "curl", "wget", "sudo", "gh", "ln", "rsync", "scp", "chmod", "chown", "mktemp", "basename",
    "dirname", "readlink", "realpath", "stat", "du", "df", "uname", "whoami", "id", "hostname", "printenv", "seq", "wait", "trap", "read",
    "local", "declare", "return", "shift", "let", "diff", "cmp", "tar", "unzip", "zip", "gzip", "gunzip", "bzip2", "xz", "source", ".",
    "cksum", "paste", "md5sum", "sha1sum", "sha256sum", "shasum", "base64", "comm", "join", "rev", "tac", "nl", "od", "xxd", "file",
    "nproc", "eval", "make", "bash", "sh", "zsh", "dash", "Rscript", "R", "ssh-keyscan", "tput", ":", "type", "command", "umask", "ulimit"})
INSTALLERS = {"pip": ("install", "download", "list", "show", "freeze", "config", "uninstall", "check", "cache", "wheel", "index"),
              "apt": ("install", "update", "upgrade", "remove", "autoremove", "list", "search", "show", "clean", "autoclean", "purge"),
              "brew": ("install", "update", "upgrade", "tap", "untap", "list", "info", "cleanup", "link", "unlink", "uninstall", "reinstall", "pin"),
              "dnf": ("install", "update", "upgrade", "remove", "list", "search", "info", "clean", "makecache")}
INSTALLERS["pip3"] = INSTALLERS["pip"]
INSTALLERS["apt-get"] = INSTALLERS["apt"]
INSTALLERS["yum"] = INSTALLERS["apk"] = INSTALLERS["dnf"]
PR_BRANCH_ACTIONS = ("r-lib/actions/pr-push",)     # pushes the pull request's own branch (the /document and /style bots), never the default branch
PUBLISH_CAPABLE = "stages {what} and pushes the default branch"
SHELL_PREFIX_KEYWORDS = ("if", "then", "else", "elif", "while", "until", "do", "!", "{", "time", "nohup", "exec")   # followed by a command
SHELL_SKIP_KEYWORDS = ("fi", "done", "esac", "for", "case", "in", "}", ")", ";;", "select", "function", "then:")
PLAUSIBLE_PROGRAM = re.compile(r"[A-Za-z_./~][A-Za-z0-9_.+-]*")
PYTHON_RUNS_CODE = re.compile(r"\bsubprocess\b|\bos\.(?:system|popen|exec\w*|spawn\w*)\b|\bruntime\b|\brunpy\b|\bimportlib\b|\b__import__\b|\bexec\s*\(|\beval\s*\(|\bpty\.spawn\b")
R_OPAQUE = re.compile(r"\beval\s*\(\s*parse\b|\bdo\.call\s*\(\s*[\"']?(?:sys\.)?source\b|\brmarkdown::render\w*|\bknitr::(?:knit\w*|purl)\b|\bbookdown::\w+|\bquarto::quarto_render\b|\bcallr::\w+")


def shell_commands(text):
    """Split shell (or Makefile recipe) text into commands, each a list of unquoted tokens.

    Quote-aware, so `;` or a newline inside `Rscript -e '...'` does not end the command; `\\<newline>` continues a line;
    `#` starts a comment. Not a shell: `$()`, `<()`, here-documents and aliases are left as literal token text,
    which `DYNAMIC_PATH` then treats as a path that cannot be resolved.
    """
    commands, command, token, quote, started, i = [], [], [], None, False, 0

    def flush():
        nonlocal token, started
        if started:
            command.append("".join(token))
        token, started = [], False

    def end():
        nonlocal command
        flush()
        if command:
            commands.append(command)
        command = []
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"' and i + 1 < len(text):
                token.append(text[i + 1]); i += 1
            else:
                token.append(c)
        elif c in "'\"":
            quote, started = c, True
        elif c == "\\" and i + 1 < len(text):
            if text[i + 1] != "\n":
                token.append(text[i + 1]); started = True
            i += 1
        elif c == "#" and not started:
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif c in "\n;&|":
            end()
        elif c.isspace():
            flush()
        else:
            token.append(c); started = True
        i += 1
    end()
    return commands


class ScriptScan:
    """Follow the files a `run:` step executes, read at the pinned SHA, and apply the run-body detections to each.

    References come from `Rscript`, `R -f/--file/CMD BATCH`, `bash|sh|zsh|dash`, `python`, `source`/`.`, `./path`,
    `make [-f] [-C]` and, inside R code, `source()`/`sys.source()`/`system()`/`system2()`. Hops are transitive with a
    visited set, a depth cap and a file cap. A reference that cannot be scanned (missing, symlinked, outside the
    repository, absolute, dynamic, binary, too large, over a cap) is a reason, but only in a pkgdown repository, so
    unrelated repositories are unaffected; a readable script with none of the signals never blocks. Not detected: scripts
    fetched or generated at runtime (reported as missing or dynamic in a pkgdown repository), `uses:` actions from other
    repositories, `knit`/`render` of a document, and any path built any way other than a literal.

    `strict` is the publish-capability rule (`workflow_may_publish`): fail-closed reasons apply to every workflow that
    shows any ability to publish. A workflow with none (read-only token, no deploy action, no push) is relaxed, because
    QC and simulation scripts are full of `source(file.path(...))`. The signals themselves (subdirectory deploy, dev
    mode) are reported from any reached script either way.
    """

    def __init__(self, root, sha, files, modes, pkgdown_repo):
        self.root, self.sha, self.files, self.modes, self.pkgdown_repo = root, sha, files, modes, pkgdown_repo
        self.seen, self.reasons, self.strict, self.evidence, self.context = set(), [], True, [], None
        self.destinations, self.exempt, self.texts = [], (), []
        self.unresolved, self.stage_push, self.quiet = [], False, False

    def opaque(self, why, ref):
        """A call that runs code the scan cannot read (an interpreter it does not follow, `eval(parse())`, a document
        render). Always recorded as unresolved, so a workflow that also stages and pushes is publish-capable; it is a reason
        only for such a workflow (`stage_push`), because elsewhere these calls are documented as not detected."""
        if self.quiet:                       # a line that is not a command (a Makefile variable or target)
            return
        self.unresolved.append(f"{why}: {ref}")
        if self.pkgdown_repo and self.strict and self.stage_push:
            self.fail_reason(why, ref)

    def fail_reason(self, why, ref):
        names = f" (workflow {self.context[0]} may publish: {self.context[1][0]})" if self.context and self.context[1] else ""
        self.reasons.append(f"script reference unsupported ({why}): {ref}; the deployed routes cannot be verified{names}")

    def fail(self, why, ref):
        self.unresolved.append(f"{why}: {ref}")      # recorded whether or not this workflow is strict: the probe reads it
        if self.pkgdown_repo and self.strict:
            self.fail_reason(why, ref)

    def observe(self, text, data, where):
        """Record `(tier, label)` publish evidence from a reached script or local action (for the workflow that reaches it)."""
        self.evidence.extend(text_publish_evidence(source_text(text, data), where, self.exempt))
        self.destinations.extend(build_destinations(source_text(text, data)))
        self.texts.append((where, source_text(text, data)))
        steps = ((data or {}).get("runs") or {}).get("steps") if isinstance(data, dict) else None
        for step in steps if isinstance(steps, list) else []:
            self.evidence.extend((tier, f"{label} in {where}") for tier, label in step_publish_evidence(step))

    def directory(self, cwd, target):
        """The repository-relative directory `target` names from `cwd`, or None when it cannot be known statically."""
        if cwd is None or not isinstance(target, str) or DYNAMIC_PATH.search(target) or target.startswith(("/", "~")):
            return None
        joined = posixpath.normpath(posixpath.join(cwd, target or "."))
        return None if joined == ".." or joined.startswith("../") else ("" if joined == "." else joined)

    def run_step(self, step, base):
        run = step.get("run")
        if not isinstance(run, str):
            return
        wd = step.get("working-directory")
        cwd = base if wd is None else self.directory(base, wd)
        if "Rscript" in str(step.get("shell", "")):
            self.r_code(run, cwd, 0)    # `shell: Rscript {0}`: the body is R code (the r-lib pkgdown template), not shell
        else:
            self.body(run, cwd, 0)

    def body(self, text, cwd, depth):
        for command in shell_commands(text):
            cwd = self.command(command, cwd, depth)

    def command(self, command, cwd, depth):
        i = 0
        while i < len(command) and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", command[i])
                                    or posixpath.basename(command[i]) in ("env", "sudo", "time", "nohup", "exec", "command")):
            i += 1
        if i >= len(command):
            return cwd
        raw, args = command[i], command[i + 1:]
        program = posixpath.basename(raw.lstrip("@({")).rstrip(")}")
        if program in SHELL_PREFIX_KEYWORDS:
            return self.command(command[i + 1:], cwd, depth)
        if program in SHELL_SKIP_KEYWORDS or program in ("", "(") or raw.endswith("()"):
            return cwd
        if program == "cd":
            return self.directory(cwd, args[0]) if args and args[0] != "-" else None
        if program == "Rscript":
            for n, arg in enumerate(args):
                if arg == "-e":
                    self.r_code(args[n + 1] if n + 1 < len(args) else "", cwd, depth)
                elif n and args[n - 1] == "-e":
                    continue
                elif not arg.startswith("-"):
                    self.file(arg, cwd, depth)
                    break
        elif program == "R":
            n = 0
            while n < len(args):
                arg = args[n]
                if arg == "-e":
                    self.r_code(args[n + 1] if n + 1 < len(args) else "", cwd, depth); n += 1
                elif arg in ("-f", "--file") and n + 1 < len(args):
                    self.file(args[n + 1], cwd, depth); n += 1
                elif arg.startswith("--file="):
                    self.file(arg[7:], cwd, depth)
                elif arg == "CMD" and args[n + 1:n + 2] == ["BATCH"]:
                    rest = [a for a in args[n + 2:] if not a.startswith("-")]
                    if rest:
                        self.file(rest[0], cwd, depth)
                    break
                n += 1
        elif re.fullmatch(r"python[0-9.]*", program):
            self.python(args, cwd, depth)
        elif program == "uv":
            self.uv(args, cwd, depth)
        elif program in SHELL_PROGRAMS:
            n = 0
            while n < len(args):
                arg = args[n]
                if arg == "-c" and n + 1 < len(args):
                    self.body(args[n + 1], cwd, depth + 1)
                    break
                if arg == "-c":
                    break
                if arg in ("-o", "+o", "-O", "+O"):
                    n += 2
                    continue
                if arg.startswith(("-", "+")) and arg not in ("-", "+"):
                    n += 1
                    continue
                self.file(arg, cwd, depth)
                break
        elif program in ("source", ".") and args:
            self.file(args[0], cwd, depth)
        elif program == "eval" and args:
            self.body(" ".join(args), cwd, depth + 1)
        elif program == "make" and not {"-v", "--version", "-h", "--help"} & set(args):
            self.make(args, cwd, depth)
        elif raw.startswith(("./", "../")):
            self.file(raw, cwd, depth)
        elif program in INSTALLERS:
            sub = next((a for a in args if not a.startswith("-")), None)
            if sub is not None and sub not in INSTALLERS[program]:
                self.opaque("opaque executable", " ".join(command[i:i + 3]))
        elif program == "find" and {"-exec", "-execdir", "-ok", "-okdir"} & set(args):
            start = next(n for n, a in enumerate(args) if a in ("-exec", "-execdir", "-ok", "-okdir"))
            run = []
            for a in args[start + 1:]:
                if a in (";", "+", "\\;"):
                    break
                run.append(a)
            self.command(run, cwd, depth + 1) if run else None          # the command `find` runs is judged like any other
        elif program in ("xargs", "timeout"):
            rest = [a for a in args if not a.startswith("-")]
            rest = rest[1:] if program == "timeout" else rest       # `timeout 30 cmd`: the first word is the duration
            if rest:
                self.command(rest, cwd, depth + 1)
        elif program not in ALLOWED_PROGRAMS and "/" in raw and not raw.startswith(("/", "~")):
            self.file(raw, cwd, depth)          # a relative path that is run: read it (or fail closed when it cannot be read)
        elif program not in ALLOWED_PROGRAMS and (program.startswith(("$", "`")) or PLAUSIBLE_PROGRAM.fullmatch(program)):
            self.opaque("opaque executable", " ".join(command[i:i + 3]))     # (text such as `%s`, `^env:` or `1` is not a command)
        return cwd

    def python(self, args, cwd, depth):
        """`python <script>` reads the literal script; `-c`, `-m <module>` (other than pip/venv) and a dynamic path are opaque."""
        n = 0
        while n < len(args):
            arg = args[n]
            if arg == "-c":
                return self.opaque("opaque executable", "python -c")
            if arg == "-m":
                module = args[n + 1] if n + 1 < len(args) else ""
                return None if module in ("pip", "venv", "ensurepip") else self.opaque("opaque executable", f"python -m {module}")
            if arg in ("-W", "-X", "-Q"):
                n += 2
                continue
            if arg.startswith("-") and arg != "-":
                n += 1
                continue
            return self.file(arg, cwd, depth)
        return None

    def uv(self, args, cwd, depth):
        """`uv pip|sync|venv|lock` is installation; `uv run <command>` runs the command it names; anything else is opaque."""
        sub = next((a for a in args if not a.startswith("-")), None)
        if sub in ("pip", "sync", "venv", "lock", "python", "cache", "version", "self", None):
            return None
        if sub != "run":
            return self.opaque("opaque executable", "uv " + sub)
        rest, n = args[args.index("run") + 1:], 0
        while n < len(rest) and rest[n].startswith("-"):
            n += 2 if rest[n] in ("--with", "--python", "-p", "--directory", "--project", "--env-file", "--extra", "--group", "--with-requirements") else 1
        if n >= len(rest):
            return None
        return self.command(rest[n:], cwd, depth + 1) or None

    def make(self, args, cwd, depth):
        makefile, where, n = None, cwd, 0
        while n < len(args):
            arg = args[n]
            if arg in ("-f", "--file", "--makefile") and n + 1 < len(args):
                makefile = args[n + 1]; n += 1
            elif arg.startswith(("--file=", "--makefile=")):
                makefile = arg.split("=", 1)[1]
            elif arg in ("-C", "--directory") and n + 1 < len(args):
                where = self.directory(where, args[n + 1]); n += 1
            elif arg.startswith("--directory="):
                where = self.directory(where, arg.split("=", 1)[1])
            n += 1
        if makefile is None:
            makefile = next((name for name in ("GNUmakefile", "makefile", "Makefile")
                             if where is not None and posixpath.normpath(posixpath.join(where, name)) in self.files), "Makefile")
        self.file(makefile, where, depth, make_dir=where)

    def includes(self, text, where, norm, depth):
        """Follow `include`/`-include`/`sinclude` lines. make resolves them from its working directory; the Makefile's own
        directory is tried as a fallback. A missing, symlinked, dynamic or escaping include fails closed (`-include` of a
        missing file is legal for make, but nothing can be said about what it would have run)."""
        for line in text.replace("\\\n", " ").splitlines():
            match = re.match(r"[ ]*(?:-include|sinclude|include)[ \t]+(.*)$", line)
            if not match:
                continue
            for target in re.sub(r"(^|\s)#.*$", "", match.group(1)).split():
                path = target
                if where is not None and not DYNAMIC_PATH.search(target) and not target.startswith(("/", "~")):
                    near = posixpath.normpath(posixpath.join(where, target))
                    beside = posixpath.normpath(posixpath.join(posixpath.dirname(norm), target))
                    if near not in self.files and beside in self.files:
                        path = posixpath.relpath(beside, where or ".")
                self.file(path, where, depth + 1, make_dir=where)

    def r_code(self, code, cwd, depth):
        for match in R_OPAQUE.finditer(code):
            self.opaque("opaque call", match.group(0).strip())
        for match in R_SOURCE.finditer(code):
            literal = match.group(1) if match.group(1) is not None else match.group(2)
            if literal is not None:
                self.file(literal, cwd, depth)
            else:
                self.fail("dynamic path", "source() with a non-literal argument")
        for match in R_SYSTEM.finditer(code):
            literal = match.group(3) if match.group(3) is not None else match.group(2)
            if literal is None:
                self.fail("dynamic path", f"{match.group(1)}() with a non-literal command")
                continue
            command = literal.replace('\\"', '"').replace("\\'", "'")
            if match.group(1) == "system2":
                close = code.find(")", match.end())
                command += " " + " ".join(re.findall(r"""["']([^"']*)["']""", code[match.end():close if close >= 0 else None]))
            self.body(command, cwd, depth + 1)

    def file(self, path, cwd, depth, make_dir=None):
        if DYNAMIC_PATH.search(path):
            return self.fail("dynamic path", path)
        if cwd is None:
            return self.fail("dynamic working directory", path)
        if path.startswith("/"):
            return self.fail("absolute path", path)
        if path.startswith("~"):
            return self.fail("dynamic path", path)
        norm = posixpath.normpath(posixpath.join(cwd, path))
        if norm == ".." or norm.startswith("../"):
            return self.fail("path outside the repository", path)
        if norm not in self.files:
            return self.fail("missing at the pinned ref", path)
        if self.modes.get(norm) == "120000":
            return self.fail("symlink, not read", path)
        if norm in self.seen:
            return None
        if depth > MAX_SCRIPT_DEPTH:
            return self.fail("nesting too deep", path)
        if len(self.seen) >= MAX_SCRIPT_FILES:
            return self.fail("too many scripts", path)
        self.seen.add(norm)
        if int(git(self.root, "cat-file", "-s", self.sha + ":" + norm)) > MAX_SCRIPT_BYTES:
            return self.fail("file too large to scan", path)
        text = git(self.root, "show", self.sha + ":" + norm, strip=False)
        if "\0" in text:
            return self.fail("binary file", path)
        self.observe(text, None, f"script {norm}")
        if mentions_dev_mode(text):
            self.reasons.append(f"{DEV_MODE_VARIABLE} set in script {norm}; development mode mapping unsupported")
        if deploy_subdirectory(text, self.pkgdown_repo):
            self.reasons.append(f"deploy to a subdirectory in script {norm}; the deployed routes cannot be verified")
        if make_dir is not None or posixpath.basename(norm) in ("Makefile", "makefile", "GNUmakefile") or norm.endswith(".mk"):
            self.includes(text, cwd if make_dir is None else make_dir, norm, depth)
        if norm.lower().endswith((".r", ".rprofile")):
            self.r_code(text, cwd, depth + 1)
        elif norm.lower().endswith(".py"):
            found = PYTHON_RUNS_CODE.search(text)       # python is read for signals, never parsed as shell
            if found:
                self.opaque("opaque executable", f"python script {norm} runs other code ({found.group(0).strip()})")
        elif make_dir is not None or posixpath.basename(norm) in ("Makefile", "makefile", "GNUmakefile") or norm.endswith(".mk"):
            for line in text.replace("\\\n", " ").splitlines():
                self.quiet = not line.startswith("\t")        # only recipe lines are commands
                self.body(line.lstrip("\t@-+ ") if not self.quiet else line, cwd, depth + 1)
            self.quiet = False
        else:
            self.body(text, cwd, depth + 1)
        return None


def default_directory(*containers):
    """`defaults.run.working-directory` of the first container (job, then workflow) that sets it, else the repository root."""
    for container in containers:
        node = container
        for key in ("defaults", "run", "working-directory"):
            node = node.get(key) if isinstance(node, dict) else None
        if node is not None:
            return node
    return None


PAGES_ACTIONS = ("jamesives/github-pages-deploy-action", "peaceiris/actions-gh-pages", "actions/deploy-pages",
                 "actions/upload-pages-artifact", "actions/configure-pages", "crazy-max/ghaction-github-pages")
PUSH_ACTIONS = ("ad-m/github-push-action", "stefanzweifel/git-auto-commit-action", "endbug/add-and-commit",
                "r-lib/actions/pr-push", "actions-js/push")
TIER1_TEXT = re.compile(r"deploy_to_branch|gh[-_]pages", re.I)                       # publishes the site by itself
DEFAULT_BRANCHES = ("HEAD", "main", "master")        # a push here is tier two; any other literal branch is tier one
PLACEHOLDER_FILES = (".gitkeep", ".keep", ".gitignore", ".gitattributes")   # a directory holding only these is not tracked content
DYNAMIC_TOKEN = re.compile(r"[$`]|\{\{|<\(")        # variable, command substitution or expression: the value cannot be known
COMMAND_START = re.compile(r"(?<![\w./@=-])(git|rsync|scp|aws|gsutil|netlify|firebase|surge|vercel|wrangler|ghp-import)(?=\s)")
R_GIT_PUSH = re.compile(r"""\bsystem2?\s*\(\s*["']git["'][^)]*["']push["']""")
BUILD_MENTION = re.compile(r"pkgdown|build_site", re.I)
NON_LITERAL = object()
DESTINATION_ARGUMENT = re.compile(
    r"""(?:\b(?:destination|dest_dir)\s*(=)|\bdestination\s*(:)|(--destination)(?:=|\s+))\s*(?:"([^"]*)"|'([^']*)'|([^\s,)\]}"'\\]*))""")
NO_PERMISSIONS = object()


def permission_evidence(perms, where):
    """`(tier, label)` pairs. `pages`/`id-token` write and `write-all` are tier 1; plain `contents: write` is tier 2."""
    if isinstance(perms, str) and perms.strip().lower() == "write-all":
        return [(1, f"permissions write-all ({where})")]
    found = []
    if isinstance(perms, dict):
        for key, value in perms.items():
            if str(value).strip().lower() != "write":
                continue
            tier = 1 if str(key).lower() in ("pages", "id-token") else 2 if str(key).lower() == "contents" else None
            if tier:
                found.append((tier, f"permissions {key}: write ({where})"))
    return found


def step_publish_evidence(step):
    """`(tier, label)` pairs for one step: a Pages action or a checkout given a secret is tier 1, a push action tier 2."""
    uses = step.get("uses") if isinstance(step, dict) else None
    if not isinstance(uses, str):
        return []
    name = uses.split("@")[0].strip().lower()
    evidence = []
    if name in PAGES_ACTIONS:
        evidence.append((1, f"deploy action {uses}"))
    if name in PUSH_ACTIONS:
        evidence.append((2, f"push action {uses}"))
    inputs = step.get("with")
    if name.endswith("checkout") and isinstance(inputs, dict):
        for key in ("token", "ssh-key"):
            value = str(inputs.get(key, ""))
            if "secrets." in value and "secrets.GITHUB_TOKEN" not in value:
                evidence.append((1, f"checkout with a secret {key}"))
    return evidence


def logical_line(text, start):
    """The text from `start` to the end of its logical line, so `\\<newline>` continues the command."""
    end = start
    while True:
        newline = text.find("\n", end)
        if newline < 0:
            return text[start:]
        if newline > 0 and text[newline - 1] == "\\":
            end = newline + 1
            continue
        return text[start:newline]


def push_tier(args, exempt=()):
    """`(tier, why)` for the arguments after `git push`.

    An explicit branch is tier one: any literal destination branch other than `HEAD`, `main` or `master` (the default
    branch is decided by name only, not by asking the repository), in any of `<remote> <branch>`, `<src>:<branch>`,
    `refs/heads/<branch>`, with `-u`/`--set-upstream`, `-f`/`--force`/`--force-with-lease` and a leading `+`. A dynamic
    remote or refspec, `--all` and `--mirror` fail closed to tier one. No refspec, a remote alone, a default branch name
    or a tag is tier two, which counts only when the pinned tree tracks the pkgdown destination. A branch the repository
    declares in `docs.site.nonpublishing-branches` (`exempt`) is also tier two: a literal name, matched exactly.
    """
    positional, mirror, i = [], False, 0
    while i < len(args):
        arg = args[i]
        if arg in ("--all", "--mirror"):
            mirror = True
        elif arg in ("-o", "--push-option", "--repo", "--receive-pack", "--exec"):
            i += 1
        elif arg == "--":
            positional.extend(args[i + 1:])
            break
        elif not (arg.startswith("-") and len(arg) > 1):
            positional.append(arg)
        i += 1
    if mirror:
        return 1, "pushes every branch"
    if any(DYNAMIC_TOKEN.search(arg) for arg in positional):
        return 1, "a dynamic remote or refspec"
    declared = None
    for spec in positional[1:]:
        spec = spec.lstrip("+")
        destination = spec.rsplit(":", 1)[-1]
        destination = destination[len("refs/heads/"):] if destination.startswith("refs/heads/") else destination
        if destination.startswith(("refs/tags/", "tags/")) or destination in DEFAULT_BRANCHES:
            continue
        if destination in exempt:
            declared = destination
            continue
        return 1, f"explicit branch {destination or spec}"
    return 2, f"declared non-publishing branch {declared}" if declared else "the default branch or no refspec"


def target_tier(program, args, exempt=()):
    """`(tier, why)` or None for a publish-style command. A remote target (`host:path`, `s3://`, `gs://`, a deploy
    subcommand, a dynamic target) is tier one; the same program with no remote target is tier two."""
    positional = [a for a in args if not a.startswith("-")]
    dynamic = any(DYNAMIC_TOKEN.search(a) for a in positional)
    if program == "git":
        i = 0
        while i < len(args) and args[i].startswith("-"):
            i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
        return push_tier(args[i + 1:], exempt) if args[i:i + 1] == ["push"] else None
    if program in ("rsync", "scp"):
        remote = dynamic or any("@" in a or re.match(r"[^/\s]+:", a) or a.startswith("rsync://") for a in positional)
        return (1, "a remote target") if remote else (2, "a local copy")
    if program == "aws":
        if args[:1] != ["s3"]:
            return None
        remote = dynamic or any(a.startswith("s3://") for a in positional)
        return (1, "an s3 target") if remote and positional[1:2] and positional[1] in ("sync", "cp", "mv") else (2, "aws s3")
    if program == "gsutil":
        return (1, "a gs target") if dynamic or any(a.startswith("gs://") for a in positional) else None
    if program == "netlify":
        return (1, "deploy") if "deploy" in args else (2, "netlify")
    if program == "firebase":
        return (1, "deploy") if "deploy" in args else None
    if program == "surge":
        return (1, "surge") if any(a.startswith("-") or "/" in a or "." in a for a in args) else None
    if program == "vercel":
        return None if args[:1] in (["--version"], ["-v"], ["whoami"], ["login"], ["logout"]) else (1, "vercel")
    if program == "wrangler":
        return (1, "pages deploy") if args[:1] == ["pages"] else None
    return (1, "ghp-import") if program == "ghp-import" else None


def text_publish_evidence(text, where, exempt=()):
    """`(tier, label)` evidence from run text, a script, or any YAML string.

    Tier one: `deploy_to_branch`/`gh-pages` text; an explicit-branch `git push`; a command that names a remote publish
    target (`rsync`/`scp` to a host, `aws s3 sync|cp|mv` to `s3://`, `gsutil` to `gs://`, `netlify|firebase deploy`, `surge`,
    `vercel`, `wrangler pages`, `ghp-import`); R `system2("git", c("push", ...))`, whose refspec is not parsed. Tier two:
    a push with no refspec or to the default branch, and the same programs with no remote target. Commands are parsed with
    the quote-aware tokenizer, so quoting, continuation lines and `env`-style variables are handled; a command that cannot
    be read as a literal fails closed to tier one.
    """
    found = []
    match = TIER1_TEXT.search(text)
    if match:
        found.append((1, f"publish signal in {where}: {match.group(0)}"))
    for match in COMMAND_START.finditer(text):
        commands = shell_commands(logical_line(text, match.start()))
        tokens = [t.rstrip("\"')],}") for t in commands[0]] if commands else []
        verdict = target_tier(match.group(1), tokens[1:], exempt) if tokens else None
        if verdict:
            tier, why = verdict
            kind = "explicit-branch push" if match.group(1) == "git" and tier == 1 else "publish command"
            shown = " ".join(tokens)[:70]
            found.append((tier, f"{kind} `{shown}` ({why}) in {where}"))
    if R_GIT_PUSH.search(text):
        found.append((1, f"R system2() git push with an unparsed refspec in {where}"))
    return list(dict.fromkeys(found))


STAGE_START = re.compile(r"(?<![\w./@=-])(git|cp|mv|rsync|ln|install)(?=\s)")
STAGE_ALL = ("-A", "--all", ".", "-u", "--update", ":/")      # stages the whole tree (or every tracked change)
MESSAGE_OPTIONS = ("-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author", "--date", "--template",
                   "--reuse-message", "--reedit-message", "--cleanup", "--trailer")
GIT_VALUE_OPTIONS = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path")


GLOB_PROBES = ("", "/", "/x", "/index.html", "/sitemap.xml", "/404.html", "/reference/index.html", "/articles/index.html", "/pkgdown.yml",
               "/.nojekyll", "/CNAME", "/a.css", "/a.js", "/a.png", "/a.json", "/a.md", "/a.txt")


def names_directory(token, names, pathspec=False):
    """Does a path argument name one of the destination directories (`names`)? `./docs`, `docs/`, `docs/*`, `pkg/docs`
    and `--prefix=docs` match; `docs-archive`, `mydocs` and `notes/docs.txt` do not. As a git pathspec (`pathspec=True`) a
    glob that can match a file in the destination (`docs*`, `d*`, `*/sitemap.xml`, `*.html`) and a parent directory of it
    also count."""
    if token.startswith("-") and "=" in token:
        token = token.split("=", 1)[1]
    if not token or token.startswith("-") or DYNAMIC_TOKEN.search(token):
        return False
    path = posixpath.normpath(token.lstrip("+"))
    if pathspec and re.search(r"[*?\[]", path):
        return any(fnmatch.fnmatchcase(n + probe, path) for n in names for probe in GLOB_PROBES)
    if pathspec and path not in (".", "..") and any(n.startswith(path + "/") for n in names):
        return True                                         # a parent directory of the destination
    return any(path == n or path.startswith(n + "/") or path.endswith("/" + n) or f"/{n}/" in path for n in names)


def git_parts(args):
    """`(subcommand, rest, positional, flags, scope)` for the arguments after `git`: global `-C` values are `scope`, the values
    of message options are dropped, and a clustered flag such as `-am` keeps its letters."""
    i, scope = 0, []
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            scope.append(args[i + 1])
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    sub, rest = (args[i] if i < len(args) else ""), args[i + 1:]
    positional, flags, j = [], [], 0
    while j < len(rest):
        arg = rest[j]
        if arg == "--":
            positional.extend(rest[j + 1:])
            break
        if arg in MESSAGE_OPTIONS:
            j += 1
        elif arg.startswith("-") and not arg.startswith("--") and len(arg) > 2 and arg.endswith("m"):
            flags.append(arg)       # a cluster such as `-am`: the next token is the message
            j += 1
        elif arg.startswith("-"):
            flags.append(arg)
        else:
            positional.append(arg)
        j += 1
    return sub, rest, positional, flags, scope


PATHSPEC_FILE_FLAGS = ("--pathspec-from-file", "--pathspec-file-nul")
INDEX_PLUMBING = ("update-index", "read-tree", "write-tree", "commit-tree", "checkout-index", "apply", "am", "stash")
STAGE_SUBCOMMANDS = ("add", "stage", "commit", "rm", "mv")


def plain_literal_path(path, names):
    """Is this git pathspec a plain literal relative path (or a glob that cannot match the destination) outside the destination?
    Pathspec magic (`:(top)docs`, `:/docs`, `:!x`, `:(glob)`), expansion (`$X`, `~`, backticks, braces), `..`, absolute paths,
    `.`, an option-looking token, and anything that is, contains, is a parent of or can match the destination are not."""
    if not path or path.startswith((":", "-", "/", "~")) or DYNAMIC_TOKEN.search(path) or re.search(r"[{}\\\\]", path):
        return False
    normal = posixpath.normpath(path)
    if normal == "." or ".." in normal.split("/"):
        return False
    return not names_directory(path, names, pathspec=True)


def stage_all_command(args, names):
    """Does this `git` command stage the whole tree, or something the audit cannot prove is outside the destination?

    A stage is NAMED (it does not count) only when every pathspec is a plain literal path outside the destination
    (`git add data/history.csv`): see `plain_literal_path`. Everything else stages everything: `git add -A|--all|-u|--update` with
    no pathspec, `.`, `:/`, `*`, a dynamic pathspec, pathspec magic, `--pathspec-from-file`, `git commit -a`, a commit that
    names a path that is not plain, and the git plumbing that changes the index or tree (`update-index`, `read-tree`,
    `commit-tree`, `checkout-index`, `apply`, `am`, `stash`). An unknown index-changing command fails closed."""
    sub, rest, positional, flags, scope = git_parts(args)
    if sub in INDEX_PLUMBING:
        return True
    if any(f.split("=", 1)[0] in PATHSPEC_FILE_FLAGS for f in flags):
        return sub in STAGE_SUBCOMMANDS
    if sub == "commit":
        if any(f == "--all" or (not f.startswith("--") and "a" in f[1:]) for f in flags):
            return True
        return any(not plain_literal_path(p, names) for p in positional)
    if sub in ("rm", "mv"):
        return any(not plain_literal_path(p, names) for p in positional)
    if sub not in ("add", "stage"):
        return False
    everything = any(f in ("-A", "--all", "-u", "--update") or (not f.startswith("--") and re.search(r"[Au]", f[1:])) for f in flags)
    if not positional:
        return everything
    return any(not plain_literal_path(p, names) for p in positional)


def stage_command(program, args, names, built):
    """A short description when one command stages, copies or mounts the site destination, else None.

    `git add`/`git commit` naming a destination (or staging the whole tree after a pkgdown build), `git subtree push`,
    `git worktree add <destination>`, and `cp`/`mv`/`rsync`/`ln`/`install` whose target is a destination."""
    if program == "git":
        sub, rest, positional, flags, scope = git_parts(args)
        if sub == "subtree" and rest[:1] == ["push"]:
            return "git subtree push"
        if sub == "worktree":
            return "git worktree add" if rest[:1] == ["add"] and any(names_directory(a, names) for a in positional[1:]) else None
        if sub not in ("add", "commit"):
            return None
        if any(names_directory(a, names) for a in scope) or any(names_directory(a, names, pathspec=True) for a in positional):
            return f"git {sub} names the destination"
        return f"git {sub} stages everything after a pkgdown build" if built and (
            stage_all_command(args, names) or any(a in STAGE_ALL for a in positional + flags)) else None
    positional, i, target = [], 0, None
    while i < len(args):
        if args[i] in ("-t", "--target-directory") and i + 1 < len(args):
            target = args[i + 1]
            i += 1
        elif not args[i].startswith("-"):
            positional.append(args[i])
        i += 1
    target = target if target is not None else (positional[-1] if len(positional) >= 2 else None)
    return f"{program} into the destination" if target is not None and names_directory(target, names) else None


def stage_evidence(texts, names):
    """`(1, label)` evidence from `(where, text)` pairs when a command builds or stages the pkgdown destination.

    A workflow that builds the destination, force-adds it and pushes can publish site files even though the pinned tree
    holds none yet, so this is tier one whether or not the destination is tracked. `names` are the literal destination
    directories (the config's `destination:`, default `docs`, and any destination a build call names). Detected: `git add`
    or `git commit` naming a destination, or staging everything (`.`, `-A`, `-u`, `commit -a`) when a pkgdown build appears
    in the same workflow or a script it reaches; `git subtree push`; `git worktree add <destination>`; `cp`/`mv`/`rsync`/`ln`
    into a destination. A push that stages something else (`git add data/history.csv`) is not stage evidence.
    """
    names = [posixpath.normpath(n) for n in names if isinstance(n, str) and n and not DYNAMIC_PATH.search(n)]
    built = any(BUILD_MENTION.search(text) for _, text in texts)
    found = []
    for where, text in texts:
        for match in STAGE_START.finditer(text):
            commands = shell_commands(logical_line(text, match.start()))
            tokens = [t.rstrip("\"')],}") for t in commands[0]] if commands else []
            if not tokens or tokens[0] != match.group(1):
                continue
            why = stage_command(tokens[0], tokens[1:], names, built)
            if why:
                found.append((1, f"stages the site destination ({why}: `{' '.join(tokens)[:70]}`) in {where}"))
    return list(dict.fromkeys(found))


ARCHIVE_TOKEN = re.compile(r"\.(?:zip|tar|tgz|gz|xz|bz2|7z)\b", re.I)
DOWNLOAD_TEXT = re.compile(r"download-artifact|\bgh\s+(?:run|release)\s+download\b|\bworkflow_run\b")
UPLOAD_TEXT = re.compile(r"upload-(pages-)?artifact")


def handoff_facts(texts, names, exempt=()):
    """The handoff facts one workflow shows, as `(0, name)` entries: `build` (a pkgdown build, or an upload of a
    destination), `download` (it pulls build output from elsewhere: `download-artifact`, `gh run|release download`,
    `curl`/`wget` of an archive, a `workflow_run` trigger), `stage` (`git add .`/`-A`/`-u`/`-f`, `git commit -a`, a command
    naming a destination, or a push action) and `push` (a `git push` with no refspec or to the default branch, or a push
    action). A push to a branch the repository declares non-publishing is not a push. `texts` are `(where, text)` pairs
    for the workflow and the scripts and local actions it reaches; `names` are the literal destination directories."""
    names = [posixpath.normpath(n) for n in names if isinstance(n, str) and n and not DYNAMIC_PATH.search(n)]
    joined = "\n".join(text for _, text in texts)
    facts = set()
    if BUILD_MENTION.search(joined) or re.search(r"upload-pages-artifact", joined):
        facts.add("build")
    for upload in UPLOAD_TEXT.finditer(joined):
        window = joined[upload.start():upload.start() + 400]
        if any(re.search(r"path:\s*[\"']?(?:\./)?(?:[\w./-]*/)?" + re.escape(n) + r"\b", window) for n in names):
            facts.add("build")
    if DOWNLOAD_TEXT.search(joined):
        facts.add("download")
    if any(name in joined.lower() for name in PUSH_ACTIONS if name not in PR_BRANCH_ACTIONS):
        facts.update(("stage", "stage_any", "stage_all", "push"))
    for match in re.finditer(r"(?<![\w./@=-])(git|curl|wget)(?=\s)", joined):
        commands = shell_commands(logical_line(joined, match.start()))
        tokens = [t.rstrip("\"')],}") for t in commands[0]] if commands else []
        if not tokens or tokens[0] != match.group(1):
            continue
        if tokens[0] in ("curl", "wget"):
            if any(ARCHIVE_TOKEN.search(t) for t in tokens[1:]):
                facts.add("download")
            continue
        args = tokens[1:]
        if stage_command("git", args, names, True) or (args[:1] == ["add"] and any(a in ("-f", "--force") for a in args)):
            facts.add("stage")
        if git_parts(args)[0] in STAGE_SUBCOMMANDS or git_parts(args)[0] in INDEX_PLUMBING:
            facts.add("stage_any")             # any staging at all, named pathspecs included
        if stage_all_command(args, names):
            facts.add("stage_all")
        if stage_command("git", args, names, False):
            facts.add("dest_staged")
        if target_tier("git", args, exempt) == (2, "the default branch or no refspec"):
            facts.add("push")
    return {(0, fact) for fact in facts}


def handoff_evidence(state):
    """`(1, label)` evidence per workflow path from the handoff facts in `state` (path -> [evidence, destinations]).

    A workflow that stages and pushes is publish-capable whether or not the pinned tree tracks the destination when it
    also pulls build output from elsewhere (it downloads, or another workflow triggers it), or when any other workflow in
    the repository builds the site: the build output can reach it as an artifact, a release or a checkout. A workflow
    that stages and pushes with no build or download relationship anywhere stays tier two. A workflow that stages
    everything (or names the destination) and pushes the default branch is tier one on its own: the audit does not try to
    prove it builds no site. A workflow that stages (named pathspecs included) and pushes is also tier one when anything it
    reaches could not be resolved (a failed script or action reference, a cap, an
    opaque executable or call): the build may hide behind it."""
    facts = {path: {label for tier, label in value[0] if tier == 0} for path, value in state.items()}
    builders = sorted(path for path, found in facts.items() if "build" in found)
    result = {}
    for path, found in facts.items():
        if "push" in found and ("stage_all" in found or "dest_staged" in found):
            what = "everything" if "stage_all" in found else "the site destination"
            result[path] = (1, f"{PUBLISH_CAPABLE.format(what=what)}; the audit does not try to prove it builds no site")
            continue
        if "push" not in found:
            continue
        others = [b for b in builders if b != path]
        if "stage" not in found:
            others = []
        if "stage" in found and "download" in found:
            result[path] = (1, "stages and pushes build output it pulls from elsewhere (artifact, release or workflow_run)")
        elif others:
            result[path] = (1, f"stages and pushes while workflow {others[0]} builds the site (cross-workflow handoff)")
        elif ("stage" in found or "stage_any" in found) and any(label.startswith("unresolved") for label in found):
            why = next(label for label in sorted(found) if label.startswith("unresolved"))[len("unresolved: "):]
            result[path] = (1, f"stages and pushes while it reaches a reference the scan cannot resolve ({why})")
    return result


def build_destinations(text):
    """Destinations a pkgdown build names in `text`: `destination =`/`dest_dir =` in R, `destination:` in YAML text and
    `--destination` on a command line. Only text that mentions pkgdown or build_site is read. A quoted value is a literal;
    in R a bare value is an expression and any value with `(`, `$` or a brace cannot be known, so both are `NON_LITERAL`."""
    if not BUILD_MENTION.search(text):
        return []
    found = []
    for match in DESTINATION_ARGUMENT.finditer(text):
        equals, colon, flag, double, single, bare = match.groups()
        literal = double if double is not None else single
        if literal is None:
            literal = None if (equals or not bare or "(" in bare) else bare
        found.append(NON_LITERAL if literal is None else literal)
    return found


def tracked_directory(files, modes, directory):
    """Does the tree hold real content under `directory`? Placeholder files (`PLACEHOLDER_FILES`, at any depth) do not
    count; anything else does, including `.nojekyll`, a file or symlink named like the directory, and a gitlink
    (submodule, mode 160000) at or below it. Paths are compared case-sensitively, as git does."""
    for path in files:
        if path == directory:
            return True
        if path.startswith(directory + "/"):
            mode = modes.get(path, "100644")
            if mode == "160000" or mode not in ("100644", "100755") or posixpath.basename(path) not in PLACEHOLDER_FILES:
                return True
    return False


def destination_tracked(files, prefix, config, modes=None, extra=()):
    """`(tracked, label)`: does the pinned tree track real content under a pkgdown destination directory?

    The destinations are the config's `destination:` (default `docs`) plus `extra` (named in a build call, see
    `build_destinations`), each under the package directory `prefix`; tracked if any is. Read from the pinned tree, never
    the working tree. A destination that is not a plain relative path inside the package (a variable, a list, `..`,
    absolute, empty, `.`, a non-literal build argument) or an unreadable config counts as tracked: fail closed.
    """
    if config is False:
        return True, "an unreadable config (assumed tracked)"
    first = "docs" if config is None or "destination" not in config else config["destination"]
    label = None
    for destination in [first, *extra]:
        if (destination is NON_LITERAL or not isinstance(destination, str) or DYNAMIC_PATH.search(destination)
                or destination.startswith(("/", "~")) or posixpath.normpath(destination) in ("", ".", "..")
                or posixpath.normpath(destination).startswith("../")):
            return True, f"destination {destination if destination is not NON_LITERAL else 'of a build call'!r} cannot be resolved (assumed tracked)"
        directory = posixpath.normpath(prefix + destination)
        label = label or f"destination {posixpath.normpath(destination)}/"
        if tracked_directory(files, modes or {}, directory):
            return True, f"destination {posixpath.normpath(destination)}/"
    return False, label


def nonpublishing_branches(root, sha, files, prefix):
    """Branch names a repository declares as never carrying site files: `docs.site.nonpublishing-branches` in
    `.rforge.yaml`, read at the pinned SHA from the package directory and the repository root (both count). Only a list
    of literal names counts; a malformed key, an unparseable file, a glob or a non-string entry exempts nothing."""
    names = []
    for path in dict.fromkeys((prefix + ".rforge.yaml", ".rforge.yaml")):
        if path not in files:
            continue
        try:
            data = yaml_data(git(root, "show", sha + ":" + path))
        except ValueError:
            continue
        node = data
        for key in ("docs", "site", "nonpublishing-branches"):
            node = node.get(key) if isinstance(node, dict) else None
        for entry in node if isinstance(node, list) else []:
            if isinstance(entry, str) and entry.strip() and not DYNAMIC_TOKEN.search(entry) and not re.search(r"[*?\[\]\s]", entry):
                names.append(entry.strip())
    return tuple(dict.fromkeys(names))


def workflow_evidence(data, text, extra=(), exempt=()):
    """Every `(tier, label)` fact that says one workflow can publish, before the tracked-destination filter."""
    data = data if isinstance(data, dict) else {}
    found = []
    if "pkgdown" in source_text(text, data).lower():
        found.append((1, "names pkgdown"))
    top = data.get("permissions", NO_PERMISSIONS)
    found += permission_evidence(top, "workflow")
    jobs = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
    for key, job in jobs.items():
        if not isinstance(job, dict):
            continue
        own = job.get("permissions", NO_PERMISSIONS)
        found += permission_evidence(own, f"job {key}")
        if top is NO_PERMISSIONS and own is NO_PERMISSIONS:
            found.append((2, f"no permissions: key for job {key} (default token scope unknown)"))
        for step in job.get("steps") if isinstance(job.get("steps"), list) else []:
            found += step_publish_evidence(step)
    found += text_publish_evidence(source_text(text, data), "the workflow", exempt)
    found += list(extra)
    return list(dict.fromkeys(found))


def classify_evidence(found, tracked=True, destination="destination docs/"):
    """`tier N: ...` strings: tier one always, tier two only when the destination is tracked."""
    labels = []
    for tier, label in sorted(found, key=lambda item: item[0]):    # tier one first: the reason names the strongest evidence
        if tier == 1:
            labels.append(f"tier 1: {label}")
        elif tier == 2 and tracked:           # tier 0 entries are handoff facts, not evidence
            labels.append(f"tier 2: {label}; {destination} is tracked")
    return list(dict.fromkeys(labels))


def workflow_may_publish(data, text, extra=(), tracked=True, destination="destination docs/"):
    """The evidence that one workflow can publish, as `tier N: ...` strings; an empty list means it is relaxed.

    Default is strict. Tier 1 always counts: the word pkgdown; a Pages or deploy action in any step; `deploy_to_branch` or
    `gh-pages` text; `pages`/`id-token` write or `write-all` permission; a checkout given a secret token or key; an
    explicit-branch `git push`; a command that names a remote publish target (see `text_publish_evidence`). Tier 2 counts
    only when the pinned tree tracks a pkgdown destination directory (`tracked`), because otherwise pushing to the default
    branch cannot publish site files: plain `contents: write`; a push action; a job with no `permissions:` key at either
    level (the default token scope is unknown); a push with no refspec or to the default branch; a publish-style command
    with no remote target. `extra` holds the same `(tier, label)` evidence found in the scripts and local actions the
    workflow reaches. YAML facts come from the parsed structure, the text signals are tolerant text. Trigger events are not
    considered. Not detected: a script that pushes from a workflow that shows no signal at all.
    """
    return classify_evidence(workflow_evidence(data, text, extra), tracked, destination)


def local_action_reasons(root, sha, files, uses, seen, pkgdown_repo=True, scan=None):
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
    if scan is not None:
        scan.observe(text, data, f"local action {path}")
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
                if scan is not None:
                    scan.run_step(step, "")
                if step.get("uses", "").startswith("./"):
                    reasons.extend(local_action_reasons(root, sha, files, step["uses"], seen, pkgdown_repo, scan))
    except ValueError as exc:
        reasons.append(f"malformed local action ({path}): {exc}")
    return reasons


def workflow_blocks(root, sha, tree, prefix="", honored=None):
    """Reasons the pinned tree makes a static route mapping unverifiable (everything is read via `git show` at the SHA).

    Scanned: workflows (`PKGDOWN_DEV_MODE`, any job-level `uses:`, local composite actions, deploys below the site
    root, malformed structure) and the R startup files at the repository root and the package directory. Names built
    dynamically or set inside scripts the workflow merely runs are not detected. When `honored` is a list, it receives the
    sorted branch names whose push was classified as non-publishing because `docs.site.nonpublishing-branches` declares them.
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
    scan = ScriptScan(root, sha, files, tree if isinstance(tree, dict) else {}, pkgdown_repo)
    startup_dirs = {"", prefix.rstrip("/")}
    for path in sorted(files):
        if posixpath.basename(path) in STARTUP_FILES and posixpath.dirname(path) in startup_dirs:
            if mentions_dev_mode(git(root, "show", sha + ":" + path, strip=False)):
                reasons.append(f"{DEV_MODE_VARIABLE} set in {path}; development mode mapping unsupported")
    # Strict by default: a workflow is relaxed only when it shows no ability to publish (`workflow_may_publish`). The
    # evidence includes what its reached scripts and local actions show, found by a probe walk that discards its reasons.
    config_path = next((prefix + c for c in CONFIG_CANDIDATES if prefix + c in files), None)
    config = None
    if config_path is not None:
        try:
            config = yaml_data(git(root, "show", sha + ":" + config_path))
        except ValueError:
            config = False       # unreadable: the destination counts as tracked
    modes = tree if isinstance(tree, dict) else {}
    exempt = nonpublishing_branches(root, sha, files, prefix)
    scan.exempt = exempt
    state = {}      # workflow path -> [evidence list, destinations list]; a reusable workflow shares both with its caller
    probes = {}     # workflow path -> (where, text) pairs of the scripts and local actions it reaches
    unresolved = {}  # workflow path -> references the probe could not resolve (a failed script or action, an opaque call)
    for path, text in texts.items():
        probe = ScriptScan(root, sha, files, modes, pkgdown_repo)
        probe.exempt = exempt
        evidence = []
        if path in errors:
            evidence.append("workflow YAML unreadable (permissions unknown)")
        else:
            try:
                for _, job, steps in workflow_jobs(parsed[path], path):
                    start = scan.directory("", default_directory(job, parsed[path])) if default_directory(job, parsed[path]) is not None else ""
                    for step in steps:
                        probe.run_step(step, start)
                        if step.get("uses", "").startswith("./"):
                            probe.unresolved.extend(local_action_reasons(root, sha, files, step["uses"], set(), pkgdown_repo, probe))
            except ValueError:
                evidence.append("workflow structure unreadable (permissions unknown)")
        data = parsed.get(path)
        probes[path] = probe.texts
        unresolved[path] = probe.unresolved
        state[path] = [workflow_evidence(data, text, [(2, e) for e in evidence] + probe.evidence, exempt),
                       build_destinations(source_text(text, data)) + probe.destinations]
    # A workflow that builds or stages the destination before it pushes is publish-capable whether or not the pinned tree
    # tracks the destination yet (tier one). The names are global: the config destination plus any a build call names.
    literal = lambda d: isinstance(d, str)
    first = "docs" if config is None or config is False or "destination" not in config else config["destination"]
    stage_names = [d for d in [first, *[d for v in state.values() for d in v[1]]] if literal(d)]
    stage_names += [prefix + d for d in stage_names if prefix]      # a monorepo stages the destination by its repository path
    for path, text in texts.items():
        data = parsed.get(path)
        pairs = [("the workflow", source_text(text, data))] + probes[path]
        facts = sorted(handoff_facts(pairs, stage_names, exempt)) + ([(0, "unresolved: " + unresolved[path][0][:90])] if unresolved[path] else [])
        state[path][0] = list(dict.fromkeys(state[path][0] + stage_evidence(pairs, stage_names) + facts))
    # Reusable workflows. A caller job `uses: ./.github/workflows/x.yml` runs the callee with the caller's token, so the
    # callee gets the caller's permission evidence and the caller gets everything the callee can do. A callee that cannot
    # be resolved (missing, outside the workflows directory, another repository, a dynamic path) is assumed capable. The
    # exchange repeats until nothing changes, so a cycle terminates.
    edges = []
    for path in sorted(texts):
        data = parsed.get(path)
        for key, job in ((data or {}).get("jobs") or {}).items() if isinstance((data or {}).get("jobs"), dict) else []:
            uses = job.get("uses") if isinstance(job, dict) else None
            if not isinstance(uses, str):
                continue
            target = posixpath.normpath(uses[2:]) if uses.startswith("./") and not DYNAMIC_PATH.search(uses) else None
            if target is not None and re.fullmatch(r"\.github/workflows/[^/]+\.ya?ml", target) and target in texts:
                inherited = permission_evidence(data.get("permissions", NO_PERMISSIONS), f"caller {path}") + permission_evidence(
                    job.get("permissions", NO_PERMISSIONS), f"caller {path} job {key}")
                if "permissions" not in data and "permissions" not in job:
                    inherited.append((2, f"no permissions: key in caller {path} (default token scope unknown)"))
                edges.append((path, target, inherited))
            else:
                state[path][0].append((1, f"reusable workflow {uses} cannot be resolved (assumed capable)"))
    for _ in range(len(texts) + 2):
        before = [(list(v[0]), list(v[1])) for v in state.values()]
        for caller_path, callee_path, inherited in edges:
            state[callee_path][0] = list(dict.fromkeys(state[callee_path][0] + inherited))
            state[caller_path][0] = list(dict.fromkeys(state[caller_path][0] + state[callee_path][0]))
            state[caller_path][1] = state[caller_path][1] + [d for d in state[callee_path][1] if d not in state[caller_path][1]]
        if before == [(list(v[0]), list(v[1])) for v in state.values()]:
            break
    handoff = handoff_evidence(state)
    for path, item in handoff.items():
        state[path][0] = list(dict.fromkeys(state[path][0] + [item]))
        if pkgdown_repo and item[1].startswith("stages ") and " and pushes the default branch;" in item[1]:
            reasons.append(f"workflow {path} {item[1].split(';')[0]}; it is treated as publish capable and the audit does not try to prove it "
                           "builds no site; the deployed routes cannot be verified")
    if honored is not None:
        honored.extend(sorted({m.group(1) for v in state.values() for _, label in v[0]
                               for m in re.finditer(r"declared non-publishing branch ([^\s)]+)", label)}))
    capable = {}
    for path in texts:
        tracked, destination = destination_tracked(files, prefix, config, modes, state[path][1])
        capable[path] = classify_evidence(state[path][0], tracked, destination)
    # Publish-capable workflows first, so a script both kinds reach is judged strictly; the visited set skips it afterwards.
    for path, text in sorted(texts.items(), key=lambda item: (item[0] not in handoff, not capable[item[0]])):
        scan.strict, scan.context, scan.stage_push = bool(capable[path]), (path, capable[path]), path in handoff
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
            base = scan.directory("", default_directory(job, parsed[path])) if default_directory(job, parsed[path]) is not None else ""
            for step in steps:
                scan.run_step(step, base)
                if step.get("uses", "").startswith("./"):
                    reasons.extend(local_action_reasons(root, sha, files, step["uses"], seen, pkgdown_repo, scan))
    reasons.extend(scan.reasons)
    return list(dict.fromkeys(reasons))


def audit(root: Path, *, url, ref=None):
    stage = {"state":"incomplete","counts":{"checked":0,"missing":0,"extra":0,"unreleased":0},"provenance":{},"reasons":[],"engine_missing":[],"findings":[],"content_freshness":"unverified","nonpublishing_branches_honored":[]}
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
        honored = []
        blocked = workflow_blocks(root, sha, modes, prefix, honored)
        stage["nonpublishing_branches_honored"] = honored
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

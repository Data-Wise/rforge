"""Run R package dev-cycle + quality engines and normalize output to one JSON envelope.

Each "kind" maps to a lower-level R package (NOT devtools):
  load->pkgload | document->roxygen2 | test->testthat | check->rcmdcheck
  coverage->covr | build->pkgbuild | install->R CMD INSTALL | site->pkgdown
  lint->lintr | spell->spelling | urlcheck->urlchecker | style->styler

The R subprocess emits JSON via jsonlite; this module normalizes it. Console
regex parsing is only a fallback when jsonlite/structured output is absent.

Usage: python3 -m lib.rcmd --kind <kind> [--path .] [--as-cran]
       [--preview] [--strict] [--articles-only] [--devel]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import changed
from . import cranlint

OPTIONAL_ENGINES = {"covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler",
                    "revdepcheck", "goodpractice", "devtools", "rhub", "S7"}
INSTALL_HINT = {
    p: f'install.packages("{p}")'
    for p in ("rcmdcheck", "pkgbuild", "roxygen2", "testthat", "pkgload",
              "covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler",
              "revdepcheck", "goodpractice", "devtools", "rhub", "S7", "jsonlite")
}


def _as_list(x) -> list:
    """Coerce a value to a list. jsonlite's auto_unbox=TRUE collapses length-1
    vectors to scalars, so a single finding can arrive as a str/dict, not a list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _parse_json(stdout: str) -> dict | None:
    """Parse a JSON object from R stdout, tolerating progress/log lines before it.

    Our snippets `cat()` a single-line JSON object as the final write, but some
    engines (urlchecker progress, pkgdown build log) also print to stdout. Try
    the whole output first, then the last non-empty line. Returns None if no line
    parses to a dict (caller falls back to console_fallback)."""
    if not stdout:
        return {}
    candidates = [stdout] + [ln for ln in reversed(stdout.splitlines()) if ln.strip()]
    for cand in candidates:
        try:
            obj = json.loads(cand.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


SPURIOUS_NOTE_PATTERNS = [
    (r"New submission", "expected on first submission"),
    (r"Days since last update", "resubmitting within CRAN cadence; expected"),
    (r"checking CRAN incoming feasibility", "informational; incoming checks only"),
    (r"[Pp]ossibly misspelled words in DESCRIPTION",
     "CRAN spell-checker flags proper nouns / technical terms"),
    (r"installed size is", "size note; justify in cran-comments if irreducible"),
]


def _classify_notes(notes) -> list:
    out = []
    for n in _as_list(notes):
        kind, reason = "real", None
        for pat, why in SPURIOUS_NOTE_PATTERNS:
            if re.search(pat, str(n)):
                kind, reason = "spurious", why
                break
        # rcmdcheck notes are strings; str() above only guards a future dict
        # note. `text` keeps the original `n` (a string in practice) so
        # downstream renderers (render_cran_comments) can call .splitlines().
        out.append({"text": n, "kind": kind, "reason": reason})
    return out


def find_package(path: str = ".") -> dict | None:
    """Return {'package','version'} from DESCRIPTION, or None if not a package."""
    desc = Path(path) / "DESCRIPTION"
    if not desc.is_file():
        return None
    fields: dict[str, str] = {}
    for line in desc.read_text().splitlines():
        m = re.match(r"^(Package|Version):\s*(.+)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    if "Package" not in fields:
        return None
    return {"package": fields["Package"], "version": fields.get("Version", "")}


_QUALITY_KEY = {"lint": "lints", "spell": "misspelled", "urlcheck": "broken"}


def _status_for(kind: str, raw: dict, exit_code: int) -> str:
    if raw.get("engine_missing"):
        return "error"
    if kind == "check":
        if raw.get("errors"):
            return "error"
        return "warn" if (raw.get("warnings") or raw.get("notes")) else "ok"
    if kind == "test":
        if raw.get("failed") or exit_code != 0:
            return "error"
        return "warn" if (raw.get("warnings") or raw.get("skipped")) else "ok"
    if kind == "site":
        if exit_code != 0 or not raw.get("built", True):
            return "error"
        probs = [p for p in _as_list(raw.get("problems")) if str(p).strip()]
        return "warn" if probs else "ok"
    if kind == "coverage":
        return "ok"  # advisory; untested lines surfaced, never "error"
    if kind in _QUALITY_KEY:
        return "warn" if raw.get(_QUALITY_KEY[kind]) else "ok"
    if kind in ("winbuilder", "rhub"):
        return "dispatched" if exit_code == 0 else "error"
    if kind == "revdep":
        if raw.get("broken"):
            return "error"
        return "warn" if raw.get("new_problems") else "ok"
    if kind == "goodpractice":
        return "warn" if raw.get("checks") else "ok"
    if kind == "s7runtime":
        any_issue = (raw.get("dead_generics") or raw.get("methods_on_missing_class")
                     or raw.get("methods_undeclared_dependency")
                     or raw.get("nonenforcing_validators"))
        return "warn" if any_issue else "ok"
    # load, document, install, build, style: success == exit 0
    return "ok" if exit_code == 0 else "error"


def normalize(kind: str, raw: dict, exit_code: int, pkg: dict | None) -> dict:
    """Fold a raw engine result into the common envelope."""
    env: dict = {
        "kind": kind,
        "status": _status_for(kind, raw, exit_code),
        "engine_missing": raw.get("engine_missing", []),
        "messages": raw.get("messages", []),
    }
    if pkg:
        env["package"] = pkg.get("package", "")
        env["version"] = pkg.get("version", "")
    if kind == "check":
        env["check"] = {k: _as_list(raw.get(k)) for k in ("errors", "warnings", "notes")}
        env["check"]["notes_classified"] = _classify_notes(raw.get("notes"))
        # G8: surface PDF-manual-skip as an advisory note (LaTeX absent locally)
        all_text = " ".join(env["check"].get("notes", []))
        if _PDF_SKIP_RE.search(all_text):
            env["check"]["notes_classified"].append({
                "text": ("PDF manual skipped — LaTeX/pdflatex not available on "
                         "this system. Rely on win-builder for the PDF manual."),
                "kind": "advisory",
                "reason": "pdf_manual_skipped",
            })
    elif kind == "test":
        env["tests"] = {k: raw.get(k, 0) for k in
                        ("passed", "failed", "skipped", "warnings")}
        env["tests"]["failing_files"] = _as_list(raw.get("failing_files"))
    elif kind == "coverage":
        env["coverage"] = {"total_pct": raw.get("total_pct"),
                           "per_file": raw.get("per_file", {}),
                           "untested": _as_list(raw.get("untested"))}
    elif kind == "build":
        env["build"] = {"artifact": raw.get("artifact"), "bytes": raw.get("bytes")}
    elif kind == "site":
        problems = [p for p in _as_list(raw.get("problems")) if str(p).strip()]
        env["site"] = {"checked": raw.get("checked", False),
                       "built": raw.get("built", False),
                       "problems": problems}
    elif kind == "install":
        env["install"] = {"installed_version": raw.get("installed_version"),
                          "exit": exit_code}
    elif kind == "lint":
        lints = _as_list(raw.get("lints"))
        env["lint"] = {"count": len(lints), "lints": lints}
    elif kind == "spell":
        misspelled = _as_list(raw.get("misspelled"))
        env["spell"] = {"count": len(misspelled), "misspelled": misspelled}
    elif kind == "urlcheck":
        # G4: classify doi.org 403s as advisory (firewall blocks, not real breakage)
        raw_broken = _as_list(raw.get("broken"))
        doi_blocked = []
        real_broken = []
        for item in raw_broken:
            if isinstance(item, dict):
                url = str(item.get("url", ""))
                status_code = str(item.get("status", ""))
                if "doi.org" in url and "403" in status_code:
                    doi_blocked.append(item)
                else:
                    real_broken.append(item)
            else:
                real_broken.append(item)
        env["urlcheck"] = {
            "count": len(real_broken),
            "broken": real_broken,
            "doi_blocked_count": len(doi_blocked),
        }
        if not raw.get("engine_missing"):
            if real_broken:
                env["status"] = "error"
            elif doi_blocked:
                env["status"] = "warn"
            else:
                env["status"] = "ok"
    elif kind == "style":
        changed = _as_list(raw.get("changed_files"))
        env["style"] = {"count": len(changed), "changed_files": changed}
    elif kind == "winbuilder":
        env["winbuilder"] = {"submitted": raw.get("submitted", True),
                             "note": raw.get("note", "results emailed to the "
                                     "DESCRIPTION maintainer; check inbox")}
    elif kind == "rhub":
        env["rhub"] = {"run_url": raw.get("run_url"),
                       "note": raw.get("note", "dispatched to GitHub Actions; "
                               "check the repo's Actions tab")}
    elif kind == "revdep":
        env["revdep"] = {"broken": _as_list(raw.get("broken")),
                         "new_problems": _as_list(raw.get("new_problems")),
                         "failures": _as_list(raw.get("failures"))}
    elif kind == "goodpractice":
        checks = _as_list(raw.get("checks"))
        env["goodpractice"] = {"count": len(checks), "checks": checks}
    elif kind == "s7runtime":
        env["s7runtime"] = {
            "dead_generics": _as_list(raw.get("dead_generics")),
            "methods_on_missing_class": _as_list(raw.get("methods_on_missing_class")),
            "methods_undeclared_dependency": _as_list(
                raw.get("methods_undeclared_dependency")),
            "nonenforcing_validators": _as_list(raw.get("nonenforcing_validators")),
        }
    # load: no extra block — status carries the result
    return env


def console_fallback(kind: str, text: str) -> dict:
    """Best-effort parse when JSON is unavailable.
    testthat: '[ FAIL 2 | WARN 0 | SKIP 1 | PASS 41 ]'
    rcmdcheck: '0 errors X | 1 warning Y | 2 notes Z'
    """
    if kind == "test":
        m = re.search(r"FAIL\s+(\d+)\s*\|\s*WARN\s+(\d+)\s*\|\s*"
                      r"SKIP\s+(\d+)\s*\|\s*PASS\s+(\d+)", text)
        if m:
            return {"failed": int(m[1]), "warnings": int(m[2]),
                    "skipped": int(m[3]), "passed": int(m[4])}
    if kind == "check":
        m = re.search(r"(\d+)\s+errors?\b.*?(\d+)\s+warnings?\b.*?(\d+)\s+notes?\b",
                      text, re.IGNORECASE | re.DOTALL)
        if m:
            return {"errors": [""] * int(m[1]), "warnings": [""] * int(m[2]),
                    "notes": [""] * int(m[3])}
    return {"messages": [ln for ln in text.splitlines() if ln.strip()][-10:]}


def _guard(pkg_name: str, body: str) -> str:
    """Prefix that emits engine_missing JSON if the package or jsonlite is absent."""
    return (
        f'if (!requireNamespace("{pkg_name}", quietly=TRUE) || '
        f'!requireNamespace("jsonlite", quietly=TRUE)) {{'
        f'cat(\'{{"engine_missing":["{pkg_name}"]}}\'); quit(status=0)}}; ' + body
    )


# CRAN-incoming `_R_CHECK_*` env bundles for the strict check flavors.
#
# Each maps to a named-character `env=` vector passed straight into
# rcmdcheck::rcmdcheck() (RESEARCH §A.4). The two flavor vars are the
# Suggests-withholding flavors documented in Writing R Extensions (RESEARCH
# §A.1); the incoming pair are the CRAN-incoming switches.
#
# `--incoming` bundle scope (confirmed against R Internals §8 "Tools", the
# `R CMD check --as-cran` block — doc/manual/R-ints.texi): the manual states
# the *entire* `_R_CHECK_CRAN_INCOMING_…/CODE_…/S3…` block is already "turned
# on by R CMD check --as-cran". So there is no large incoming-only extra set to
# add. We force the two INCOMING switches explicitly so the stage is
# self-documenting and robust even if a future call path omits `--as-cran`.
# EXCLUDED (with reason):
#   _R_CHECK_S3_REGISTRATION_      — not a real var name; the real one is
#                                    _R_CHECK_OVERWRITE_REGISTERED_S3_METHODS_,
#                                    already in the --as-cran block.
#   _R_CHECK_LENGTH_1_CONDITION_   — documented "No longer in use" (now an error).
#   partial-match (_R_CHECK_*PARTIAL*) — already in the --as-cran block.
#   _R_CHECK_RD_VALIDATE_RD2HTML_  — already on under --as-cran (RESEARCH §A.2).
#   _R_CHECK_FORCE_SUGGESTS_=FALSE — the one true incoming-extra, but it RELAXES
#                                    (tolerates unavailable Suggests) rather than
#                                    tightening — deferred; it would undercut the
#                                    noSuggests pass philosophy.
_CHECK_ENV = {
    "depends": {"_R_CHECK_DEPENDS_ONLY_": "true"},
    "suggests": {"_R_CHECK_SUGGESTS_ONLY_": "true"},
}
_INCOMING_ENV = {"_R_CHECK_CRAN_INCOMING_": "true",
                 "_R_CHECK_CRAN_INCOMING_REMOTE_": "true"}


def _r_named_char(d: dict) -> str:
    """Render a Python dict as an R named character vector literal: c("k"="v")."""
    inner = ", ".join(f'"{k}"="{v}"' for k, v in d.items())
    return f"c({inner})"


_WIN_FN = {
    "devel": "devtools::check_win_devel",
    "release": "devtools::check_win_release",
    "oldrelease": "devtools::check_win_oldrelease",
}

_CRAN_CHECKS_REGISTRY = {
    # base: extra env vars beyond _INCOMING_ENV + DEPENDS/SUGGESTS (which the
    # two-pass logic adds structurally). Per the EXCLUDED list above, all other
    # incoming-era vars are already in --as-cran or excluded for documented reasons.
    "base": {},
    "R4.3": {},
    "R4.4": {},
    "R4.5": {},
}

_PDF_SKIP_RE = re.compile(
    r"skipping PDF manual|LaTeX not found|pdflatex(?:\s+is)? not (?:found|available)",
    re.IGNORECASE,
)

# ── R-hub v2 platform tables ────────────────────────────────────────────────
# Known-broken R-hub platforms: dispatching to any of these fails immediately,
# so _rhub_preflight() hard-blocks them with the keyed remediation message.
_RHUB_BROKEN_PLATFORMS = {
    "macos": (
        "macos-13 runner retired December 2025; "
        "use `macos-arm64` (ARM) or wait for rhub to update. "
        "See https://github.com/r-hub/rhub/issues/669"
    ),
}

# Named platform presets. `cran-submission` is the headless default (Q6): an OS
# matrix plus `atlas`. `clang-asan` is opt-in only (issue #645, [unstable]).
_RHUB_PRESETS = {
    "cran-submission":        ["linux", "windows", "macos-arm64", "atlas"],
    "cran-submission-strict": ["linux", "windows", "macos-arm64", "atlas", "clang-asan"],
    "sanitizers":             ["clang-asan", "atlas"],
    "all-vm":                 ["linux", "windows", "macos-arm64"],
}


def _check_rhub_yaml(pkg_path: str) -> list[dict]:
    """Scan .github/workflows/rhub.yaml for advisory issues.

    Two advisory checks: (1) each ``setup-deps`` block missing ``pak-version:
    stable`` (pak devel bootstrap regression, r-lib/pak #887); (2) a default
    config field naming a known-broken platform. Returns ``[]`` if rhub.yaml is
    absent — its absence is a hard error handled by ``_rhub_preflight``.
    """
    # TODO: remove or loosen the pak-version check when r-lib/pak #887 is fixed in devel.
    # Upstream: https://github.com/r-lib/pak/issues/887
    yaml_path = Path(pkg_path) / ".github" / "workflows" / "rhub.yaml"
    if not yaml_path.exists():
        return []  # rhub_yaml_missing is handled by _rhub_preflight

    content = yaml_path.read_text()
    findings: list[dict] = []

    # Check pak-version in every setup-deps block.
    blocks = re.split(r"- uses: r-hub/actions/setup-deps", content)
    # blocks[0] = content before first occurrence; blocks[1:] = after each.
    for i, block in enumerate(blocks[1:], 1):
        # [ \t]* (not \s*) after `with:` so the trailing newline is left for the
        # capture group to consume; \s* would eat it and capture nothing, making
        # every block look like it's missing pak-version.
        with_match = re.search(r"\s+with:[ \t]*\n((?:\s+\S.*\n)*)", block)
        if not with_match:
            continue
        with_block = with_match.group(1)
        if "pak-version:" not in with_block:
            findings.append({
                "code": "rhub_pak_devel_regression",
                "severity": "advisory",
                "block": i,   # informational: which setup-deps block (1-indexed)
                "message": (
                    f"setup-deps block {i} is missing `pak-version: stable`. "
                    "pak devel (0.10.0.9000) has a bootstrap regression "
                    "(r-lib/pak #887, filed 2026-06-13) — rhub jobs will "
                    "silently fail. Add `pak-version: stable` as the first "
                    "`with:` entry in this block."
                ),
                "fix": (
                    "- uses: r-hub/actions/setup-deps@v1\n"
                    "  with:\n"
                    "    pak-version: stable\n"
                    "    token: ${{ secrets.RHUB_TOKEN }}\n"
                    "    job-config: ${{ matrix.config.job-config }}"
                ),
            })

    # Check default config field for broken platforms.
    default_match = re.search(r"default:\s*'([^']+)'", content)
    if default_match:
        default_platforms = [p.strip() for p in default_match.group(1).split(",")]
        broken_in_default = [p for p in default_platforms if p in _RHUB_BROKEN_PLATFORMS]
        if broken_in_default:
            findings.append({
                "code": "rhub_yaml_default_broken_platform",
                "severity": "advisory",
                "platforms": broken_in_default,
                "message": (
                    f"rhub.yaml default config includes retired platform(s): "
                    f"{', '.join(broken_in_default)}. Update the default field to "
                    f"'linux,windows,macos-arm64' to avoid confusing others who "
                    f"manually trigger the workflow."
                ),
            })

    return findings


def _rhub_preflight(pkg_path: str, platforms: list) -> list[dict]:
    """Unified pre-flight checks for r:rhub. Returns a list of findings.

    Fixed sequence: (a) yaml_missing hard-stops immediately; (b) each broken
    platform yields an error; (c) advisory checks from ``_check_rhub_yaml``.
    Only ``severity == 'error'`` findings block dispatch.
    """
    findings: list[dict] = []
    yaml_path = Path(pkg_path) / ".github" / "workflows" / "rhub.yaml"

    # (a) yaml_missing — hard error, short-circuits remaining checks.
    if not yaml_path.exists():
        findings.append({
            "code": "rhub_yaml_missing",
            "severity": "error",
            "message": (
                ".github/workflows/rhub.yaml not found. "
                "Run `rhub::rhub_setup()` in R to create it (requires a GitHub remote). "
                "This file must exist and be committed before r:rhub can dispatch."
            ),
        })
        return findings  # No further checks possible.

    # (b) broken_platform — hard error per broken platform requested.
    for plat in platforms:
        if plat in _RHUB_BROKEN_PLATFORMS:
            findings.append({
                "code": "rhub_broken_platform",
                "severity": "error",
                "platform": plat,
                "message": (
                    f"Platform '{plat}' is broken: {_RHUB_BROKEN_PLATFORMS[plat]}"
                ),
            })

    # (c) pak_version + default config advisories.
    findings.extend(_check_rhub_yaml(pkg_path))

    return findings


def _rhub_actions_url(pkg_path: str) -> str:
    """Construct the GitHub Actions URL from the origin remote.

    Normalizes SSH→HTTPS, strips a trailing ``.git``, appends ``/actions``.
    Returns an empty string on any failure (no remote, git absent, timeout).
    """
    try:
        result = subprocess.run(
            ["git", "-C", pkg_path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        remote = result.stdout.strip()
        # Normalize: ssh -> https, strip .git suffix.
        if remote.startswith("git@github.com:"):
            remote = "https://github.com/" + remote[len("git@github.com:"):]
        if remote.endswith(".git"):
            remote = remote[:-4]
        return remote.rstrip("/") + "/actions" if remote else ""
    except Exception:
        return ""


def _r_version_key() -> str:
    """Return 'R{major}.{minor}' for installed R, or 'base' if Rscript absent."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return "base"
    proc = subprocess.run(
        [rscript, "-e", "cat(paste0('R', R.version$major, '.', R.version$minor))"],
        capture_output=True, text=True,
    )
    text = proc.stdout.strip()
    if re.match(r"^R\d+\.\d+$", text):
        return text
    return "base"


def r_snippet(kind: str, path: str, *, as_cran: bool = False, preview: bool = False,
              strict: bool = False, articles_only: bool = False,
              devel: bool = False, flavor: str | None = None,
              incoming: bool = False, platform: str = "all",
              platforms: list | None = None, rc_mode: bool = False) -> str:
    """Build the R one-liner for engine ``kind``, emitting JSON on stdout.

    For ``kind="check"``, ``flavor`` in {None, "depends", "suggests"} selects a
    Suggests-withholding env flavor and ``incoming`` adds the CRAN-incoming
    ``_R_CHECK_*`` bundle; a flavor / ``incoming`` / ``strict`` pass also runs
    ``\\donttest{}`` examples. Each engine call is wrapped in ``_guard(...)``.
    """
    p = json.dumps(path)  # safely quote path for R
    if kind == "check":
        # Strict-grade passes (a flavor or the incoming bundle) always run
        # \donttest{} examples (spec §Scope Tier 1a); --strict does too.
        run_donttest = strict or flavor is not None or incoming
        flags = ["--as-cran"] if as_cran else []
        if run_donttest:
            flags.append("--run-donttest")
        args = f'c({", ".join(json.dumps(f) for f in flags)})' if flags else "character()"
        if incoming:
            # G7: _R_CHECK_DEPENDS_ONLY_ and _R_CHECK_SUGGESTS_ONLY_ are
            # mutually exclusive in rcmdcheck — run two sequential passes and
            # merge errors/warnings/notes so both perspectives are captured.
            # _CRAN_CHECKS_REGISTRY supplies version-specific extra vars; base
            # is the fallback when the installed R version has no specific entry.
            _reg_key = _r_version_key()
            _extra = (
                _CRAN_CHECKS_REGISTRY[_reg_key]
                if _reg_key in _CRAN_CHECKS_REGISTRY
                else _CRAN_CHECKS_REGISTRY["base"]
            )
            env_p1 = {**_INCOMING_ENV, **_extra, "_R_CHECK_DEPENDS_ONLY_": "true"}
            env_p2 = {**_INCOMING_ENV, **_extra, "_R_CHECK_SUGGESTS_ONLY_": "true"}
            return _guard("rcmdcheck",
                f'r1 <- rcmdcheck::rcmdcheck({p}, args={args}, '
                f'env={_r_named_char(env_p1)}, quiet=TRUE, error_on = "never"); '
                f'r2 <- rcmdcheck::rcmdcheck({p}, args={args}, '
                f'env={_r_named_char(env_p2)}, quiet=TRUE, error_on = "never"); '
                f'cat(jsonlite::toJSON(list(errors=c(r1$errors,r2$errors), '
                f'warnings=c(r1$warnings,r2$warnings), notes=c(r1$notes,r2$notes)), '
                f'auto_unbox=TRUE, null="list"))')
        env_vars: dict[str, str] = {}
        if flavor is not None:
            env_vars.update(_CHECK_ENV[flavor])
        env_arg = f", env={_r_named_char(env_vars)}" if env_vars else ""
        return _guard("rcmdcheck",
            f'r <- rcmdcheck::rcmdcheck({p}, args={args}{env_arg}, '
            f'quiet=TRUE, error_on = "never"); '
            f'cat(jsonlite::toJSON(list(errors=r$errors, warnings=r$warnings, '
            f'notes=r$notes), auto_unbox=TRUE, null="list"))')
    if kind == "build":
        return _guard("pkgbuild",
            f'p <- pkgbuild::build({p}, quiet=TRUE); '
            f'cat(jsonlite::toJSON(list(artifact=basename(p), '
            f'bytes=as.integer(file.info(p)$size)), auto_unbox=TRUE))')
    if kind == "document":
        return _guard("roxygen2",
            f'roxygen2::roxygenize({p}); '
            f'cat(jsonlite::toJSON(list(documented=TRUE), auto_unbox=TRUE))')
    if kind == "load":
        return _guard("pkgload",
            f'pkgload::load_all({p}); '
            f'cat(jsonlite::toJSON(list(loaded=TRUE), auto_unbox=TRUE))')
    if kind == "test":
        return _guard("testthat",
            f'res <- testthat::test_local({p}, load_package="source", '
            f'reporter="list", stop_on_failure=FALSE); df <- as.data.frame(res); '
            f'cat(jsonlite::toJSON(list(passed=sum(df$passed), failed=sum(df$failed), '
            f'skipped=sum(df$skipped), warnings=sum(df$warning), '
            f'failing_files=unique(df$file[df$failed>0 | df$error>0])), auto_unbox=TRUE))')
    if kind == "coverage":
        return _guard("covr",
            f'cv <- covr::package_coverage({p}); l <- covr::coverage_to_list(cv); '
            f'z <- covr::zero_coverage(cv); '
            f'untested <- if (nrow(z)) {{ag <- stats::aggregate(line ~ filename, z, '
            f'function(x) c(first=min(x), last=max(x))); lapply(seq_len(nrow(ag)), '
            f'function(i) list(file=ag$filename[i], '
            f'first_line=as.integer(ag$line[i,"first"]), '
            f'last_line=as.integer(ag$line[i,"last"])))}} else list(); '
            f'cat(jsonlite::toJSON(list(total_pct=covr::percent_coverage(cv), '
            f'per_file=as.list(l$filecoverage), untested=untested), '
            f'auto_unbox=TRUE, null="list"))')
    if kind == "site":
        prev = f'pkgdown::preview_site({p}); ' if preview else ''
        gate = (f'pkgdown::check_pkgdown({p}); ' if strict
                else f'probs <- paste(utils::capture.output('
                     f'pkgdown::pkgdown_sitrep({p})), collapse="\\n"); ')
        build = (f'pkgdown::build_articles({p}, preview=FALSE)' if articles_only
                 else f'pkgdown::build_site({p}, preview=FALSE, new_process=TRUE, '
                      f'quiet=TRUE, devel={"TRUE" if devel else "FALSE"})')
        probs = 'character()' if strict else 'if (exists("probs")) probs else ""'
        return _guard("pkgdown",
            f'{gate}{build}; {prev}'
            f'cat(jsonlite::toJSON(list(checked=TRUE, built=TRUE, '
            f'problems=as.list({probs})), auto_unbox=TRUE, null="list"))')
    if kind == "lint":
        return _guard("lintr",
            f'ls <- lintr::lint_package({p}); '
            f'cat(jsonlite::toJSON(list(lints=lapply(ls, function(x) list('
            f'file=x$filename, line=x$line_number, linter=x$linter, '
            f'message=x$message))), auto_unbox=TRUE, null="list"))')
    if kind == "spell":
        return _guard("spelling",
            f'sp <- spelling::spell_check_package({p}); '
            f'cat(jsonlite::toJSON(list(misspelled=lapply(seq_len(nrow(sp)), '
            f'function(i) list(word=sp$word[i], files=sp$found[[i]]))), '
            f'auto_unbox=TRUE, null="list"))')
    if kind == "urlcheck":
        # urlchecker::url_check() columns (v1.0.x): URL, From, Status, Message, New
        return _guard("urlchecker",
            f'u <- urlchecker::url_check({p}); '
            f'cat(jsonlite::toJSON(list(broken=lapply(seq_len(nrow(u)), '
            f'function(i) list(url=u$URL[i], status=u$Status[i], '
            f'message=u$Message[i], new_url=u$New[i]))), auto_unbox=TRUE, null="list"))')
    if kind == "style":
        return _guard("styler",
            f'res <- styler::style_pkg({p}); '
            f'cat(jsonlite::toJSON(list(changed_files='
            f'as.list(res$file[res$changed %in% TRUE])), auto_unbox=TRUE, null="list"))')
    if kind == "revdep":
        # NOTE: num_workers=4 is a fixed default (no CLI flag yet — add one to
        # main() if CI core counts become a problem). new_problems and failures
        # are hardcoded empty pending Task 9 live verification of revdepcheck's
        # revdep_summary accessors; only `broken` is extracted today. The
        # envelope keys stay stable so the renderer/orchestrator don't change.
        return _guard("revdepcheck",
            f'revdepcheck::revdep_check({p}, num_workers=4, quiet=TRUE); '
            f'br <- tryCatch(revdepcheck::revdep_summary({p}), error=function(e) list()); '
            f'broken <- tryCatch(names(Filter(function(x) isTRUE(x$status=="-"), br)), '
            f'error=function(e) character()); '
            f'cat(jsonlite::toJSON(list(broken=broken, new_problems=character(), '
            f'failures=character()), auto_unbox=TRUE, null="list"))')
    if kind == "goodpractice":
        # NOTE: failed_checks accessor verified against live R in Task 9;
        # tryCatch guards against API changes across goodpractice versions.
        return _guard("goodpractice",
            f'g <- goodpractice::gp({p}); '
            f'ck <- tryCatch(as.character(goodpractice::failed_checks(g)), '
            f'error=function(e) character()); '
            f'cat(jsonlite::toJSON(list(checks=ck), auto_unbox=TRUE, null="list"))')
    if kind == "winbuilder":
        # G1: platform kwarg selects which win-builder flavour(s) to submit to.
        # rhub dispatch removed — use kind='rhub' directly (see kind == "rhub" below).
        plats = list(_WIN_FN.keys()) if platform == "all" else [platform]
        calls = "; ".join(f"{_WIN_FN[pl]}({p})" for pl in plats)
        return _guard("devtools",
            f'{calls}; '
            f'cat(jsonlite::toJSON(list(submitted=TRUE), auto_unbox=TRUE))')
    if kind == "rhub":
        # Two modes. rhub.yaml presence is confirmed by _rhub_preflight() before
        # we reach here, so the snippet NEVER calls rhub::rhub_setup() (that would
        # make a spurious git commit on every invocation) and NEVER passes NULL
        # platforms (which opens an interactive console menu and hangs headlessly).
        if rc_mode:
            # RC shared runners: rc_submit() takes no platforms arg — it uses the
            # rhub.yaml workflow-dispatch config.
            return _guard("rhub",
                f'rhub::rc_submit({p}); '
                f'cat(jsonlite::toJSON(list(submitted=TRUE, mode="rc_submit", '
                f'note="Results at https://builder.r-hub.io"), auto_unbox=TRUE))')
        # Own GitHub account: explicit platforms vector, never NULL.
        plats = platforms or _RHUB_PRESETS["cran-submission"]
        plats_r = "c(" + ", ".join(f'"{pl}"' for pl in plats) + ")"
        return _guard("rhub",
            f'rhub::rhub_check({p}, platforms={plats_r}); '
            f'cat(jsonlite::toJSON(list(submitted=TRUE, platforms={plats_r}, '
            f'note="Results in GitHub Actions tab"), auto_unbox=TRUE))')
    if kind == "s7runtime":
        # Load the package, introspect S7 at runtime, emit 3 issue lists as JSON.
        #
        # Serialization discipline (v2.1.0 lessons): the ENTIRE body runs inside a
        # tryCatch so any R error still emits a valid one-line JSON object on
        # stdout (never a bare traceback that would break _parse_json); load_all
        # is quiet + suppressMessages to keep package startup chatter off stdout;
        # toJSON uses auto_unbox=TRUE (scalars) + null="list" so empty result
        # vectors serialize as `[]`, never `null`. _guard prepends the
        # S7+jsonlite presence check (pkgload presence is asserted here too).
        return _guard("S7",
            'if (!requireNamespace("pkgload", quietly=TRUE)) {'
            'cat(\'{"engine_missing":["pkgload"]}\'); quit(status=0)}; '
            'res <- tryCatch({'
            f'suppressMessages(pkgload::load_all({p}, quiet=TRUE, '
            'helpers=FALSE, export_all=FALSE)); '
            # gather exported + internal S7 objects from the loaded namespace
            f'nm <- pkgload::pkg_name({p}); ns <- asNamespace(nm); '
            'objs <- mget(ls(ns, all.names=TRUE), envir=ns, '
            'ifnotfound=list(NULL)); '
            'is_gen <- function(o) inherits(o, "S7_generic"); '
            'is_cls <- function(o) inherits(o, "S7_class"); '
            'gens <- Filter(is_gen, objs); clss <- Filter(is_cls, objs); '
            # (1) dead generics: an S7 generic with zero registered methods. The
            # registered methods live in the generic's `methods` attribute (an
            # environment, possibly nested by dispatch arg); recurse + count.
            'count_methods <- function(env) { if (!is.environment(env)) return(0L); '
            'n <- 0L; for (k in ls(env, all.names=TRUE)) { v <- get(k, envir=env); '
            'n <- n + if (is.environment(v)) count_methods(v) else 1L }; n }; '
            'dead <- character(); '
            'for (gn in names(gens)) { g <- gens[[gn]]; '
            'mtab <- attr(g, "methods"); '
            'if (count_methods(mtab) == 0L) dead <- c(dead, gn) }; '
            # (2) non-enforcing validators: a validator whose body is a constant
            # NULL/TRUE never inspects `self`, so it can never reject any input —
            # it is present (passes the static family) but provably not enforcing.
            'is_noop <- function(v) { if (!is.function(v)) return(FALSE); '
            'b <- body(v); '
            'if (is.null(b) || identical(b, quote(NULL)) || isTRUE(b) || '
            'identical(b, quote(TRUE))) return(TRUE); '
            'if (is.call(b) && identical(b[[1]], as.name("{")) && length(b) == 2L) '
            '{ inner <- b[[2]]; return(is.null(inner) || identical(inner, quote(NULL)) '
            '|| isTRUE(inner) || identical(inner, quote(TRUE))) }; FALSE }; '
            'lax <- character(); '
            'for (cn in names(clss)) { cl <- clss[[cn]]; '
            'val <- attr(cl, "validator"); '
            'if (is.null(val)) next; '
            'if (is_noop(val)) lax <- c(lax, cn) }; '
            # Declared deps (read ONCE): the loaded package's DESCRIPTION
            # Imports+Depends+LinkingTo package names, plus an always-allowed set
            # (the package itself + base/recommended pkgs that need no Imports).
            # Used by check (4) below — a dispatch class from an undeclared package.
            # Always-allowed = the real base package set (priority="base", which
            # includes grid/parallel/splines/stats4/compiler/tcltk that a hardcoded
            # list kept omitting), plus the package itself and S7 — none of these
            # need a DESCRIPTION Imports entry, so a dispatch class from them is
            # never an "undeclared dependency".
            'base_pkgs <- tryCatch(rownames(installed.packages(priority="base")), '
            'error=function(e) c("base","methods","stats","utils","graphics",'
            '"grDevices","datasets","tools")); '
            'allow <- union(c(nm, "S7"), base_pkgs); '
            'declared <- tryCatch({ '
            f'd <- read.dcf(file.path(pkgload::pkg_path({p}), "DESCRIPTION")); '
            'fields <- intersect(c("Imports", "Depends", "LinkingTo"), colnames(d)); '
            'raw <- paste(d[1, fields], collapse=","); '
            'parts <- unlist(strsplit(raw, ",")); '
            # strip version ranges "pkg (>= 1.0)" without a regex escape (R parsers
            # reject "\\(" in a string literal): split on the literal "(" and keep [1]
            'parts <- trimws(vapply(strsplit(parts, "(", fixed=TRUE), '
            '`[`, character(1), 1)); '
            'parts[nzchar(parts) & parts != "NA"] }, '
            'error=function(e) character()); '
            'declared <- union(declared, allow); '
            # (3) methods on a missing class: a method whose dispatch signature
            # references an S7 class with no resolvable namespace binding (e.g. an
            # inline `new_class()` left in a method() call) is unreachable — nothing
            # can ever construct that class to dispatch on. Each S7_method carries
            # attr(.,"signature") = the list of dispatch class OBJECTS, so this is
            # decidable. Guards: base-type signature elements are not S7_class (skip);
            # ANY/S7_object union dispatch skipped.
            # (4) methods on an UNDECLARED dependency: a dispatch class that DOES
            # resolve but whose `package` attr P is set, != this package, and is not
            # in `declared` — typically a Suggests-only class. At a site without P
            # the class never registers and the method silently never fires.
            # The two are mutually exclusive per signature: unresolvable -> (3);
            # resolvable-but-undeclared-package -> (4); resolvable+declared -> clean.
            'collect_methods <- function(env, acc) { '
            'if (!is.environment(env)) return(acc); '
            'for (k in ls(env, all.names=TRUE)) { v <- get(k, envir=env); '
            'if (is.environment(v)) acc <- collect_methods(v, acc) '
            'else acc <- c(acc, list(v)) }; acc }; '
            'missing <- list(); undeclared <- list(); '
            'for (gn in names(gens)) { g <- gens[[gn]]; '
            'ms <- collect_methods(attr(g, "methods"), list()); '
            'for (md in ms) { sigs <- attr(md, "signature"); '
            'if (is.null(sigs)) next; '
            'for (s in sigs) { if (!inherits(s, "S7_class")) next; '
            'cnm <- attr(s, "name"); cpkg <- attr(s, "package"); '
            'if (is.null(cnm) || !nzchar(cnm) || cnm %in% c("ANY", "S7_object")) next; '
            'ext <- !is.null(cpkg) && nzchar(cpkg) && !identical(cpkg, nm); '
            # Resolve by OBJECT IDENTITY, not by @name: a class may be bound under a
            # name != its @name (e.g. `Foo <- new_class("Bar")`). For internal classes
            # the dispatch object must BE one of this package's gathered class objects;
            # for imported classes (ext) fall back to a name lookup in the provider ns.
            'resolves <- if (ext) { '
            'tryCatch(exists(cnm, envir=asNamespace(cpkg), inherits=FALSE), '
            'error=function(e) TRUE) } else { '
            'any(vapply(clss, function(o) identical(o, s), logical(1))) }; '
            'if (!resolves) { missing <- c(missing, '
            'list(list(generic=gn, class=cnm))); next }; '
            'if (ext && !(cpkg %in% declared)) undeclared <- c(undeclared, '
            'list(list(generic=gn, class=cnm, package=cpkg))) } } }; '
            'missing <- unique(missing); undeclared <- unique(undeclared); '
            'list(dead_generics=dead, methods_on_missing_class=missing, '
            'methods_undeclared_dependency=undeclared, '
            'nonenforcing_validators=lax)}, '
            'error=function(e) list(engine_missing=character(), '
            'messages=paste("s7runtime load/introspection failed:", '
            'conditionMessage(e)))); '
            'cat(jsonlite::toJSON(res, auto_unbox=TRUE, null="list"))')
    raise ValueError(f"unknown kind: {kind}")


def _invoke_r(snippet: str) -> tuple[str, int]:
    """Run an R snippet via Rscript; return (stdout, exit_code). Mocked in tests."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return ('{"engine_missing":["R"]}', 127)
    proc = subprocess.run([rscript, "-e", snippet], capture_output=True, text=True)
    return (proc.stdout.strip(), proc.returncode)


def _install_package(path: str) -> tuple[dict, int]:
    """R CMD INSTALL <path>; return (raw, exit_code)."""
    pkg = find_package(path) or {}
    rbin = shutil.which("R")
    if rbin is None:
        return ({"engine_missing": ["R"]}, 127)
    proc = subprocess.run([rbin, "CMD", "INSTALL", path], capture_output=True, text=True)
    return ({"installed_version": pkg.get("version")}, proc.returncode)


def _run_rhub(path: str, pkg: dict, *, platforms: list | None = None,
              preset: str | None = None, rc_mode: bool = False) -> dict:
    """Dispatch ``kind="rhub"``: resolve platforms, pre-flight, then dispatch.

    Pre-flight runs entirely in Python before any R call. Error findings block
    dispatch (returned as an error envelope); advisory findings ride along in the
    returned envelope's ``findings`` key and never short-circuit dispatch.
    """
    # Resolve platforms: preset → explicit list → default preset.
    if preset is not None:
        if preset not in _RHUB_PRESETS:
            return {"kind": "rhub", "status": "error", "engine_missing": [],
                    "messages": [f"Unknown preset '{preset}'. "
                                 f"Valid presets: {', '.join(_RHUB_PRESETS)}"]}
        platforms = _RHUB_PRESETS[preset]
    elif platforms is None:
        # Never pass NULL headlessly — fall back to the default preset.
        platforms = _RHUB_PRESETS["cran-submission"]

    # Pre-flight gate (Python-side, before any R dispatch).
    preflight = _rhub_preflight(path, platforms)
    errors = [f for f in preflight if f.get("severity") == "error"]
    if errors:
        return {"kind": "rhub", "status": "error", "engine_missing": [],
                "messages": [f["message"] for f in errors],
                "findings": errors}
    advisories = [f for f in preflight if f.get("severity") == "advisory"]

    # Dispatch through the normal R pipeline.
    snippet = r_snippet("rhub", path, platforms=platforms, rc_mode=rc_mode)
    stdout, code = _invoke_r(snippet)
    raw = _parse_json(stdout)
    if raw is None:
        raw = console_fallback("rhub", stdout)
    env = normalize("rhub", raw, code, pkg)
    for eng in env.get("engine_missing", []):
        if INSTALL_HINT.get(eng):
            env.setdefault("messages", []).append(f"Missing R package — run: {INSTALL_HINT[eng]}")
        if eng in OPTIONAL_ENGINES and env["status"] == "error":
            env["status"] = "warn"

    # Construct and open the GitHub Actions URL (own-account mode only).
    actions_url = _rhub_actions_url(path) if not rc_mode else ""
    if actions_url:
        import webbrowser
        try:
            webbrowser.open(actions_url)
        except Exception:
            pass

    env["findings"] = advisories
    env["run_url"] = actions_url or env.get("rhub", {}).get("run_url")
    return env


def run(kind: str, path: str = ".", *, as_cran: bool = False, preview: bool = False,
        strict: bool = False, articles_only: bool = False, devel: bool = False,
        flavor: str | None = None, incoming: bool = False,
        platform: str = "all", platforms: list | None = None,
        preset: str | None = None, rc_mode: bool = False) -> dict:
    """Run one engine ``kind`` against ``path``; return the normalized envelope.

    Threads the check ``flavor`` / ``incoming`` selectors through to ``r_snippet``;
    returns an error envelope when no DESCRIPTION is found. For ``kind="rhub"``,
    ``platforms`` (``list[str]``), ``preset`` (``str``) and ``rc_mode`` (``bool``)
    select the R-hub dispatch; a Python-side pre-flight gate runs before any R call.
    """
    pkg = find_package(path)
    if pkg is None:
        return {"kind": kind, "status": "error", "engine_missing": [],
                "messages": ["No DESCRIPTION found — is this an R package? "
                             "Try /rforge:detect to locate packages."]}
    if kind == "rhub":
        return _run_rhub(path, pkg, platforms=platforms, preset=preset, rc_mode=rc_mode)
    if kind == "install":
        raw, code = _install_package(path)
    else:
        if kind == "site" and articles_only:
            _install_package(path)  # standalone build_articles renders installed version
        snippet = r_snippet(kind, path, as_cran=as_cran, preview=preview,
                            strict=strict, articles_only=articles_only, devel=devel,
                            flavor=flavor, incoming=incoming, platform=platform)
        stdout, code = _invoke_r(snippet)
        raw = _parse_json(stdout)
        if raw is None:
            raw = console_fallback(kind, stdout)
    env = normalize(kind, raw, code, pkg)
    for eng in env.get("engine_missing", []):
        if INSTALL_HINT.get(eng):
            env.setdefault("messages", []).append(f"Missing R package — run: {INSTALL_HINT[eng]}")
        if eng in OPTIONAL_ENGINES and env["status"] == "error":
            env["status"] = "warn"
    return env


# ───────────────────────── diff-aware (--changed) ─────────────────────────


def _extract_findings(env: dict, kind: str) -> list:
    """Flatten a single check/lint/test envelope into one comparable finding list.

    - check: errors + warnings + notes (the CRAN-relevant findings).
    - lint:  the lint message list.
    - test:  the failing test files (a failure on a changed pkg is the "finding").
    Other kinds contribute no taggable findings.
    """
    if kind == "check":
        c = env.get("check") or {}
        return (_as_list(c.get("errors")) + _as_list(c.get("warnings"))
                + _as_list(c.get("notes")))
    if kind == "lint":
        return _as_list((env.get("lint") or {}).get("lints"))
    if kind == "test":
        return _as_list((env.get("tests") or {}).get("failing_files"))
    return []


def run_changed(
    kind: str,
    root: str = ".",
    *,
    base: str = "dev",
    changed_strict: bool = False,
    fail_on: str = "introduced",
    use_cache: bool = True,
    **run_kwargs,
) -> dict:
    """Run `kind` on the package(s) changed on this branch vs `base`, with diff-aware
    [introduced]/[pre-existing] tagging (SPEC P0 completion, v2.11.0).

    Two-run tagging applies UNIFORMLY to every taggable kind — `check`, `lint`,
    and `test` all get the same baseline-vs-HEAD tagging (there is no scope-only
    kind): when the merge-base resolves, `changed.scope_check` runs the SAME
    engine against a detached worktree at git merge-base(HEAD, base) (the
    baseline) and against the live HEAD tree, then tags each HEAD finding
    [introduced] (new on this branch) vs [pre-existing] (already on base).
    Lint findings (dicts) are compared by `(file, message, linter)` so a
    line-shifted pre-existing lint stays [pre-existing] (see changed.tag_findings).

    `--fail-on` (default "introduced") controls the exit status: with the default,
    status is "error" iff ≥1 introduced finding (so CI fails only on regressions you
    caused, not pre-existing debt). `--fail-on none` reports findings but never
    folds status (advisory).

    Degrades safely (no regression of the v2.10.0 scope-only behavior):
      - not a git repo / git missing / no merge-base (changed_files None) → run a
        full `kind` against `root` and annotate `changed.fell_back=True`.
      - no changes (empty diff) → no-op `ok` envelope.
      - merge-base / baseline worktree unavailable (scope_check None) → SCOPE-ONLY:
        run the engine on the changed package(s), surface the REAL status, and warn
        that tagging was unavailable (findings are NOT tagged, status NOT folded).
    """
    files = changed.changed_files(path=root, base=base)
    if files is None:
        env = run(kind, root, **run_kwargs)
        env.setdefault("messages", []).append(
            "⚠️  not a git repo or no merge-base for "
            f"'{base}' — ran a full {kind} instead of --changed")
        env["changed"] = {"fell_back": True, "base": base, "packages": []}
        return env

    pkgs = changed.changed_packages(files, root=root)
    if not pkgs:
        return {"kind": kind, "status": "ok", "engine_missing": [],
                "messages": [f"✓ no changes against '{base}' — "
                             f"no changed R packages to {kind}"],
                "changed": {"fell_back": False, "base": base, "packages": []}}

    # ── Two-run tagging: run the engine over the changed packages at a given tree
    #    root and return one flat finding list (the runner injected into
    #    scope_check; it executes once on the baseline worktree, once on HEAD). ──
    rel_pkgs = [str(Path(p.path).resolve().relative_to(Path(root).resolve()))
                if Path(p.path).resolve() != Path(root).resolve() else "."
                for p in pkgs]

    def _pkg_findings(tree_root: str, rel: str) -> list:
        """Findings for ONE package `rel` under `tree_root`, pkg_dir-annotated.

        The unit of both the HEAD run (via `runner`) and the per-package baseline
        cache, so HEAD and baseline findings have an identical shape and tag
        cleanly. The pkg_dir annotation lets scope_check rebase a package-relative
        finding `file` (R/a.R) to repo-relative (pkgA/R/a.R) and EXACT-match it
        against `git status` — no cross-package basename collision.
        """
        pkg_path = str(Path(tree_root) / rel) if rel != "." else tree_root
        out: list = []
        for f in _extract_findings(run(kind, pkg_path, **run_kwargs), kind):
            if isinstance(f, dict):
                f = {**f, "pkg_dir": rel}
            out.append(f)
        return out

    def runner(tree_root: str) -> list:
        findings: list = []
        for rel in rel_pkgs:
            findings.extend(_pkg_findings(tree_root, rel))
        return findings

    # Per-PACKAGE baseline cache key: kind + the single package rel + engine
    # kwargs (the merge-base sha is added by cached_baseline). Per-package, not
    # per-set, so a growing changed-package set reuses already-baselined packages.
    # MUST include every input that changes a package's baseline findings — an
    # under-keyed cache would serve an under-covering baseline and mis-tag
    # pre-existing findings as [introduced]. `default=str` guarantees key
    # construction never raises on an exotic kwarg value; its only downside is
    # benign — a non-deterministic str() would vary the key (cache MISSES, a perf
    # loss), never collide (a wrong-baseline reuse). All current --changed kwargs
    # are JSON-native bools, so default=str never even fires today.
    kwargs_token = json.dumps(run_kwargs, sort_keys=True, default=str)

    def _pkg_key(rel: str) -> str:
        return f"{kind}|{rel}|{kwargs_token}"

    def baseline(p: str, sha: str):
        return changed.cached_baseline(p, sha, rel_pkgs, _pkg_findings, _pkg_key,
                                       use_cache=use_cache)

    result = changed.scope_check(runner, path=root, base=base, baseline=baseline)
    if result is not None:
        introduced = result["introduced_count"]
        # --fail-on: default "introduced" → error iff ≥1 introduced; "none" → never.
        status = "error" if (fail_on != "none" and introduced > 0) else "ok"
        msg = (f"✓ no introduced findings vs '{base}' "
               f"(merge-base {result['merge_base'][:8]})" if introduced == 0
               else f"✗ {introduced} introduced finding(s) vs '{base}' "
                    f"(merge-base {result['merge_base'][:8]})")
        return {"kind": kind, "status": status, "engine_missing": [],
                "messages": [msg],
                "changed": {"fell_back": False, "base": base,
                            "merge_base": result["merge_base"],
                            "packages": [p.name for p in pkgs],
                            "introduced_count": introduced,
                            "findings": result["findings"]}}

    # ── Scope-only fallback (merge-base / baseline worktree unavailable): surface
    #    the REAL status, no tagging, no status folding. (v2.10.0 behavior.) ──
    scope_msg = (f"ℹ️  introduced/pre-existing tagging unavailable (no merge-base "
                 f"checkout for '{base}') — scope-only: showing full {kind} "
                 f"status for changed package(s)")
    if len(pkgs) == 1:
        pkg = pkgs[0]
        env = run(kind, pkg.path, **run_kwargs)
        env["changed"] = {"fell_back": False, "base": base,
                          "packages": [pkg.name]}
        env.setdefault("messages", []).append(scope_msg)
        return env

    stages = []
    worst = "ok"
    for pkg in pkgs:
        env = run(kind, pkg.path, **run_kwargs)
        stages.append({"package": pkg.name, "status": env["status"],
                       "detail": env})
        if env["status"] == "error":
            worst = "error"
        elif env["status"] == "warn" and worst != "error":
            worst = "warn"
    return {"kind": kind, "status": worst, "engine_missing": [],
            "messages": [scope_msg],
            "changed": {"fell_back": False, "base": base,
                        "packages": [p.name for p in pkgs], "stages": stages}}


def _run_cycle(path: str) -> dict:
    """document -> test -> check; stop at first hard error."""
    stages = []
    for kind in ("document", "test", "check"):
        env = run(kind, path)
        stages.append({"kind": kind, "status": env["status"]})
        if env["status"] == "error":
            return {"kind": "cycle", "status": "error", "stages": stages,
                    "failed_stage": kind, "detail": env,
                    "engine_missing": env.get("engine_missing", []),
                    "messages": env.get("messages", [])}
    worst = "warn" if any(s["status"] == "warn" for s in stages) else "ok"
    return {"kind": "cycle", "status": worst, "stages": stages,
            "engine_missing": [], "messages": []}


def render_cran_comments(package: str, version: str,
                         check_env: dict, revdep_env: dict | None) -> str:
    """Generate cran-comments.md body from check and revdep envelopes.

    Produces the two standard CRAN submission sections: R CMD check results
    (with NOTE classification tags) and reverse dependencies. Pass
    revdep_env=None when no revdep check was run (package has no dependents).
    """
    chk = check_env.get("check", {})
    ne, nw = len(chk.get("errors", [])), len(chk.get("warnings", []))
    classified = chk.get("notes_classified", [])
    nn = len(classified)
    lines = [f"## R CMD check results", "",
             f"{ne} errors | {nw} warnings | {nn} note{'s' if nn != 1 else ''}", ""]
    if classified:
        lines.append("Remaining NOTEs:")
        for c in classified:
            tag = "expected" if c["kind"] == "spurious" else "NEEDS REVIEW"
            reason = f" — {c['reason']}" if c.get("reason") else ""
            first_line = (c['text'].splitlines() or [''])[0]
            lines.append(f"* [{tag}] {first_line}{reason}")
        lines.append("")
    lines += ["## Reverse dependencies", ""]
    rv = (revdep_env or {}).get("revdep", {})
    broken = rv.get("broken", [])
    if not revdep_env:
        lines.append("There are currently no downstream dependencies for this package.")
    elif broken:
        lines.append(f"Broke {len(broken)} package(s): {', '.join(broken)} — "
                     "maintainers notified.")
    else:
        lines.append("All reverse dependencies passed (see revdep/cran.md).")
    return "\n".join(lines) + "\n"


# Surfaced when a strict (noSuggests / suggests-only / incoming) flavor errors.
_STRICT_HINT = ("A Suggests package is used unconditionally. Move it to Imports, "
                "or guard with `requireNamespace()` in code AND "
                "`skip_if_not_installed()` in tests.")


def _run_cran_prep(path: str = ".", *, no_revdep: bool = False,
                   goodpractice: bool = False, multi_platform: bool = False,
                   strict: bool = True, incoming: bool = False) -> dict:
    pkg = find_package(path)
    if pkg is None:
        return {"kind": "cran-prep", "status": "blocked", "engine_missing": [],
                "blockers": ["No DESCRIPTION — try /rforge:detect"], "stages": [],
                "messages": []}
    stages, blockers, dispatched, messages = [], [], [], []
    revdep_env = None  # may stay None when no_revdep=True

    def stage(kind, *, label=None, **kw):
        env = run(kind, path, **kw)
        stages.append({"kind": label or kind, "status": env["status"]})
        return env

    # 1-6: hard sequence (stop at first ERROR)
    for kind in ("document", "lint", "spell", "urlcheck", "test", "coverage"):
        env = stage(kind)
        if env["status"] == "error":
            blockers.append(f"{kind} failed")
            return _cran_prep_envelope(pkg, "blocked", stages, blockers, dispatched,
                                       failed_stage=kind, messages=messages)
    check_env = stage("check", as_cran=True)
    if check_env["status"] == "error":
        blockers.append("R CMD check --as-cran failed (errors/warnings)")
        return _cran_prep_envelope(pkg, "blocked", stages, blockers, dispatched,
                                   failed_stage="check", messages=messages)
    real_notes = [c for c in check_env.get("check", {}).get("notes_classified", [])
                  if c.get("kind") == "real"]
    if real_notes:
        blockers.append(f"{len(real_notes)} real NOTE(s) need attention")

    # Tier 1b: PDF reference manual — warn (never block) if LaTeX is absent.
    manual = check_env.get("check", {}).get("manual")
    if isinstance(manual, dict) and not manual.get("built", True) \
            and not manual.get("latex", True):
        messages.append("PDF reference manual not built locally (no LaTeX) — "
                        "rely on win-builder for the manual. (warning, not a blocker)")

    # Tier 2a/2b: strict Suggests-withholding flavors (run by default in
    # cran-prep). Each is its own --run-donttest pass with a restricted lib path.
    if strict:
        flavor_rows = [("depends", "check (noSuggests)"),
                       ("suggests", "check (suggests-only)")]
        for flavor, label in flavor_rows:
            env = stage("check", label=label, as_cran=True, strict=True, flavor=flavor)
            if env["status"] == "error":
                blockers.append("noSuggests/donttest check failed "
                                "(Suggests used unconditionally?)")
                if _STRICT_HINT not in messages:
                    messages.append(_STRICT_HINT)

    # Tier 3: incoming-only `_R_CHECK_*` bundle (opt-in via --incoming).
    if incoming:
        env = stage("check", label="check (incoming)", as_cran=True,
                    strict=True, incoming=True)
        if env["status"] == "error":
            blockers.append("CRAN incoming check failed")

    # Tier 4: pure-Python metadata + structure checks (no R). All ADVISORY —
    # they surface findings but never append a blocker, so they cannot flip the
    # `ready` verdict on their own. (Build-hygiene issues still block indirectly
    # via the real R CMD check NOTE once R runs.) Each degrades to `warn` on a
    # missing/unparseable DESCRIPTION/.Rbuildignore rather than raising.
    for tier4 in (cranlint.lint_description, cranlint.check_build_hygiene,
                  cranlint.check_planning_consistency, cranlint.check_test_config):
        env = tier4(path)
        stages.append({"kind": env["kind"], "status": env["status"]})
        for finding in env.get("findings", []):
            msg = finding.get("message")
            if msg:
                messages.append(f"[{env['kind']}] {msg}")

    # revdep (skip if opted out)
    if not no_revdep:
        revdep_env = stage("revdep")
        if revdep_env["status"] == "error":
            blockers.append("reverse dependencies broken")

    # goodpractice (opt-in, advisory — never blocks)
    if goodpractice:
        stage("goodpractice")

    # multi-platform dispatch (async)
    if multi_platform:
        for kind in ("winbuilder", "rhub"):
            env = stage(kind)
            if env["status"] == "dispatched":
                dispatched.append(kind)

    # write cran-comments.md
    text = render_cran_comments(pkg["package"], pkg.get("version", ""),
                                check_env, revdep_env)
    cc_path = Path(path) / "cran-comments.md"
    cc_path.write_text(text)

    status = "ready" if not blockers else "warn"
    return _cran_prep_envelope(pkg, status, stages, blockers, dispatched,
                               cran_comments_path=str(cc_path), messages=messages)


def _cran_prep_envelope(pkg, status, stages, blockers, dispatched, **extra):
    # status vocab for cran-prep: "ready" / "warn" / "blocked" (extends the
    # standard "ok"/"warn"/"error"/"dispatched" set used by single-engine kinds)
    env = {"kind": "cran-prep", "status": status,
           "package": pkg.get("package", ""), "version": pkg.get("version", ""),
           "stages": stages, "blockers": blockers, "dispatched": dispatched,
           "engine_missing": [], "messages": [],
           "handoff": ("ready for /rforge:release ecosystem sequencing"
                       if status == "ready" else "not yet CRAN-ready")}
    env.update(extra)
    return env


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m lib.rcmd",
                                 description="Run an R dev-cycle/quality engine, emit JSON.")
    ap.add_argument("--kind", required=True,
                    choices=["load", "document", "test", "check", "coverage", "build",
                             "install", "site", "cycle", "lint", "spell", "urlcheck", "style",
                             "winbuilder", "rhub", "revdep", "goodpractice", "cran-prep",
                             "s7runtime"])
    ap.add_argument("--path", default=".")
    ap.add_argument("--as-cran", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--articles-only", action="store_true")
    ap.add_argument("--devel", action="store_true")
    ap.add_argument("--goodpractice", action="store_true")
    ap.add_argument("--multi-platform", action="store_true")
    ap.add_argument("--no-revdep", action="store_true")
    ap.add_argument("--platform",
                    choices=list(_WIN_FN.keys()) + ["all"], default="all",
                    help="winbuilder: platform(s) to submit to "
                         "(devel|release|oldrelease|all); default all")
    ap.add_argument("--platforms", default=None,
                    help="rhub: comma-separated platform list "
                         "(e.g. linux,windows,macos-arm64,atlas); overrides preset")
    ap.add_argument("--preset", default=None,
                    help="rhub: named platform preset "
                         "(cran-submission|cran-submission-strict|sanitizers|all-vm)")
    ap.add_argument("--rc-mode", action="store_true", dest="rc_mode",
                    help="rhub: use RC shared runners via rc_submit() "
                         "instead of your own GitHub account")
    ap.add_argument("--incoming", action="store_true",
                    help="check: add the CRAN-incoming _R_CHECK_* bundle "
                         "(implies --strict); cran-prep: add the check (incoming) row")
    ap.add_argument("--flavor", choices=["depends", "suggests"], default=None,
                    help="check: run a single Suggests-withholding flavor "
                         "(internal selector; cran-prep loops over both by default)")
    ap.add_argument("--changed", action="store_true",
                    help="run on the package(s) changed on this branch and tag each "
                         "finding [introduced] (new on your branch) vs "
                         "[pre-existing] via a two-run merge-base baseline")
    ap.add_argument("--base", default="dev",
                    help="comparison ref for --changed (diff + baseline are vs "
                         "merge-base(HEAD, base); default: dev)")
    ap.add_argument("--fail-on", choices=("introduced", "none"), default="introduced",
                    dest="fail_on",
                    help="--changed exit policy: 'introduced' (default) exits "
                         "non-zero iff ≥1 introduced finding; 'none' is advisory")
    ap.add_argument("--changed-strict", action="store_true",
                    help="no-op (reserved): kept for back-compat with v2.10.0 flags")
    ap.add_argument("--no-cache", action="store_true", dest="no_cache",
                    help="--changed: bypass the baseline cache (force a fresh "
                         "merge-base baseline run, and skip writing it)")
    ns = ap.parse_args(argv)
    if ns.kind == "cycle":
        env = _run_cycle(ns.path)
    elif ns.kind == "cran-prep":
        env = _run_cran_prep(ns.path, no_revdep=ns.no_revdep,
                             goodpractice=ns.goodpractice,
                             multi_platform=ns.multi_platform,
                             incoming=ns.incoming)
    elif ns.changed:
        env = run_changed(ns.kind, ns.path, base=ns.base,
                          changed_strict=ns.changed_strict, fail_on=ns.fail_on,
                          use_cache=not ns.no_cache,
                          as_cran=ns.as_cran, strict=ns.strict,
                          incoming=ns.incoming)
    else:
        plats = ([p.strip() for p in ns.platforms.split(",") if p.strip()]
                 if ns.platforms else None)
        env = run(ns.kind, ns.path, as_cran=ns.as_cran, preview=ns.preview,
                  strict=ns.strict, articles_only=ns.articles_only, devel=ns.devel,
                  flavor=ns.flavor, incoming=ns.incoming, platform=ns.platform,
                  platforms=plats, preset=ns.preset, rc_mode=ns.rc_mode)
    print(json.dumps(env, indent=2))
    # "dispatched" (winbuilder/rhub) is non-error — exits 0 like "ok"/"warn"
    return 0 if env.get("status") not in ("error", "blocked") else 1


if __name__ == "__main__":
    sys.exit(main())

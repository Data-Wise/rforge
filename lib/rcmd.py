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

OPTIONAL_ENGINES = {"covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler"}
INSTALL_HINT = {
    p: f'install.packages("{p}")'
    for p in ("rcmdcheck", "pkgbuild", "roxygen2", "testthat", "pkgload",
              "covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler",
              "jsonlite")
}


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
        return "warn" if raw.get("problems") else "ok"
    if kind == "coverage":
        return "ok"  # advisory; untested lines surfaced, never "error"
    if kind in _QUALITY_KEY:
        return "warn" if raw.get(_QUALITY_KEY[kind]) else "ok"
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
        env["check"] = {k: raw.get(k, []) for k in ("errors", "warnings", "notes")}
    elif kind == "test":
        env["tests"] = {k: raw.get(k, 0) for k in
                        ("passed", "failed", "skipped", "warnings")}
        env["tests"]["failing_files"] = raw.get("failing_files", [])
    elif kind == "coverage":
        env["coverage"] = {"total_pct": raw.get("total_pct"),
                           "per_file": raw.get("per_file", {}),
                           "untested": raw.get("untested", [])}
    elif kind == "build":
        env["build"] = {"artifact": raw.get("artifact"), "bytes": raw.get("bytes")}
    elif kind == "site":
        env["site"] = {"checked": raw.get("checked", False),
                       "built": raw.get("built", False),
                       "problems": raw.get("problems", [])}
    elif kind == "install":
        env["install"] = {"installed_version": raw.get("installed_version"),
                          "exit": exit_code}
    elif kind == "lint":
        env["lint"] = {"count": len(raw.get("lints", [])), "lints": raw.get("lints", [])}
    elif kind == "spell":
        env["spell"] = {"count": len(raw.get("misspelled", [])),
                        "misspelled": raw.get("misspelled", [])}
    elif kind == "urlcheck":
        env["urlcheck"] = {"count": len(raw.get("broken", [])),
                           "broken": raw.get("broken", [])}
    elif kind == "style":
        env["style"] = {"count": len(raw.get("changed_files", [])),
                        "changed_files": raw.get("changed_files", [])}
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


def r_snippet(kind: str, path: str, *, as_cran: bool = False, preview: bool = False,
              strict: bool = False, articles_only: bool = False,
              devel: bool = False) -> str:
    p = json.dumps(path)  # safely quote path for R
    if kind == "check":
        args = 'c("--as-cran")' if as_cran else "character()"
        return _guard("rcmdcheck",
            f'r <- rcmdcheck::rcmdcheck({p}, args={args}, quiet=TRUE, error_on = "never"); '
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
        # NOTE: verify column names with names(urlchecker::url_check(".")) — vary by version
        return _guard("urlchecker",
            f'u <- urlchecker::url_check({p}); '
            f'cat(jsonlite::toJSON(list(broken=lapply(seq_len(nrow(u)), '
            f'function(i) list(url=u$URL[i], message=u$message[i], '
            f'new_url=u$newURL[i]))), auto_unbox=TRUE, null="list"))')
    if kind == "style":
        return _guard("styler",
            f'res <- styler::style_pkg({p}); '
            f'cat(jsonlite::toJSON(list(changed_files='
            f'as.list(res$file[res$changed %in% TRUE])), auto_unbox=TRUE, null="list"))')
    raise ValueError(f"unknown kind: {kind}")

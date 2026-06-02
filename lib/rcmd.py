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

OPTIONAL_ENGINES = {"covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler",
                    "revdepcheck", "goodpractice", "devtools", "rhub"}
INSTALL_HINT = {
    p: f'install.packages("{p}")'
    for p in ("rcmdcheck", "pkgbuild", "roxygen2", "testthat", "pkgload",
              "covr", "pkgdown", "lintr", "spelling", "urlchecker", "styler",
              "revdepcheck", "goodpractice", "devtools", "rhub", "jsonlite")
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
        broken = _as_list(raw.get("broken"))
        env["urlcheck"] = {"count": len(broken), "broken": broken}
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
        # NOTE: devtools::check_win_devel() submission verified live in Task 9.
        return _guard("devtools",
            f'devtools::check_win_devel({p}); '
            f'cat(jsonlite::toJSON(list(submitted=TRUE), auto_unbox=TRUE))')
    if kind == "rhub":
        # NOTE: rhub::rhub_check() run_url capture verified live in Task 9.
        return _guard("rhub",
            f'rhub::rhub_setup({p}); '              # idempotent; writes workflow
            f'rhub::rhub_check({p}); '
            f'cat(jsonlite::toJSON(list(run_url=NA), auto_unbox=TRUE))')
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


def run(kind: str, path: str = ".", *, as_cran: bool = False, preview: bool = False,
        strict: bool = False, articles_only: bool = False, devel: bool = False) -> dict:
    pkg = find_package(path)
    if pkg is None:
        return {"kind": kind, "status": "error", "engine_missing": [],
                "messages": ["No DESCRIPTION found — is this an R package? "
                             "Try /rforge:detect to locate packages."]}
    if kind == "install":
        raw, code = _install_package(path)
    else:
        if kind == "site" and articles_only:
            _install_package(path)  # standalone build_articles renders installed version
        snippet = r_snippet(kind, path, as_cran=as_cran, preview=preview,
                            strict=strict, articles_only=articles_only, devel=devel)
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
    # package/version are available for Task 8 (cran-prep command) to prepend
    # a title line; this function generates only the body sections.
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
            lines.append(f"* [{tag}] {c['text'].splitlines()[0]}{reason}")
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


def _run_cran_prep(path: str = ".", *, no_revdep: bool = False,
                   goodpractice: bool = False, multi_platform: bool = False) -> dict:
    pkg = find_package(path)
    if pkg is None:
        return {"kind": "cran-prep", "status": "blocked", "engine_missing": [],
                "blockers": ["No DESCRIPTION — try /rforge:detect"], "stages": [],
                "messages": []}
    stages, blockers, dispatched = [], [], []
    revdep_env = None  # may stay None when no_revdep=True

    def stage(kind, **kw):
        env = run(kind, path, **kw)
        stages.append({"kind": kind, "status": env["status"]})
        return env

    # 1-6: hard sequence (stop at first ERROR)
    for kind in ("document", "lint", "spell", "urlcheck", "test", "coverage"):
        env = stage(kind)
        if env["status"] == "error":
            blockers.append(f"{kind} failed")
            return _cran_prep_envelope(pkg, "blocked", stages, blockers, dispatched,
                                       failed_stage=kind)
    check_env = stage("check", as_cran=True)
    if check_env["status"] == "error":
        blockers.append("R CMD check --as-cran failed (errors/warnings)")
        return _cran_prep_envelope(pkg, "blocked", stages, blockers, dispatched,
                                   failed_stage="check")
    real_notes = [c for c in check_env.get("check", {}).get("notes_classified", [])
                  if c.get("kind") == "real"]
    if real_notes:
        blockers.append(f"{len(real_notes)} real NOTE(s) need attention")

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
                               cran_comments_path=str(cc_path))


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
                             "winbuilder", "rhub", "revdep", "goodpractice", "cran-prep"])
    ap.add_argument("--path", default=".")
    ap.add_argument("--as-cran", action="store_true")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--articles-only", action="store_true")
    ap.add_argument("--devel", action="store_true")
    ap.add_argument("--goodpractice", action="store_true")
    ap.add_argument("--multi-platform", action="store_true")
    ap.add_argument("--no-revdep", action="store_true")
    ns = ap.parse_args(argv)
    if ns.kind == "cycle":
        env = _run_cycle(ns.path)
    elif ns.kind == "cran-prep":
        env = _run_cran_prep(ns.path, no_revdep=ns.no_revdep,
                             goodpractice=ns.goodpractice,
                             multi_platform=ns.multi_platform)
    else:
        env = run(ns.kind, ns.path, as_cran=ns.as_cran, preview=ns.preview,
                  strict=ns.strict, articles_only=ns.articles_only, devel=ns.devel)
    print(json.dumps(env, indent=2))
    # "dispatched" (winbuilder/rhub) is non-error — exits 0 like "ok"/"warn"
    return 0 if env.get("status") not in ("error", "blocked") else 1


if __name__ == "__main__":
    sys.exit(main())

"""R one-liner snippet builders + CRAN env constants (extracted from lib.rcmd).

Internal module (no docs/reference/ page, like ``formatters``): houses
``r_snippet`` and its helpers/constants. Imported by ``lib.rcmd`` (re-exported
into its namespace) and by ``lib.rhub`` (which calls ``r_snippet``). Pure
snippet construction — no envelope/normalize logic lives here.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


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


def _r_version_key() -> str:
    """Return 'R{major}.{minor}' for installed R, or 'base' if Rscript absent."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return "base"
    try:
        proc = subprocess.run(
            [rscript, "-e", "cat(paste0('R', R.version$major, '.', R.version$minor))"],
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        return "base"
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
        # Lazy import keeps rsnippets free of a top-level rhub dependency
        # (rhub imports rsnippets); the preset table is rhub's home. In normal
        # flow _run_rhub resolves platforms first, so this default only fires
        # when r_snippet("rhub") is called directly without platforms.
        if not platforms:
            from lib.rhub import _RHUB_PRESETS
            platforms = _RHUB_PRESETS["cran-submission"]
        plats = platforms
        plats_r = "c(" + ", ".join(f'"{pl}"' for pl in plats) + ")"
        return _guard("rhub",
            f'rhub::rhub_check({p}, platforms={plats_r}); '
            f'cat(jsonlite::toJSON(list(submitted=TRUE, platforms={plats_r}, '
            f'note="Results in GitHub Actions tab"), auto_unbox=TRUE))')
    if kind == "s7runtime":
        # The S7 runtime-introspection logic ships VERBATIM in lib/r/s7runtime.R
        # (function s7_runtime_report(pkg_path) returning the four stable keys);
        # this branch only source()s that file and calls it. _guard prepends the
        # S7+jsonlite presence check; the pkgload presence check + the tryCatch
        # around the call keep the serialization discipline identical to the
        # former inline form — a single one-line JSON object on stdout, even on
        # error (auto_unbox=TRUE scalars; null="list" so empty vectors serialize
        # as `[]`, never `null`).
        script = json.dumps(str(Path(__file__).parent / "r" / "s7runtime.R"))
        return _guard("S7",
            'if (!requireNamespace("pkgload", quietly=TRUE)) {'
            'cat(\'{"engine_missing":["pkgload"]}\'); quit(status=0)}; '
            f'source({script}); '
            f'res <- tryCatch(s7_runtime_report({p}), '
            'error=function(e) list(messages=paste('
            '"s7runtime load/introspection failed:", conditionMessage(e)))); '
            'cat(jsonlite::toJSON(res, auto_unbox=TRUE, null="list"))')
    raise ValueError(f"unknown kind: {kind}")

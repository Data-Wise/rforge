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
from . import sitelint
# Snippet builders + CRAN env constants live in lib.rsnippets (extracted v2.15.0).
# Re-exported into this namespace so existing `rcmd.<name>` references stay valid.
from .rsnippets import (  # noqa: F401  (re-exported for callers/tests)
    r_snippet, deploy_snippet, _guard, _r_named_char, _r_version_key,
    _CHECK_ENV, _INCOMING_ENV, _CRAN_CHECKS_REGISTRY, _WIN_FN, _PDF_SKIP_RE,
)
import tempfile

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
        if exit_code == 124:
            return "error"
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
    if kind == "deploy":
        # blocked/warn for the gate are decided in _run_deploy (which builds its
        # own envelope); this only fires for the actual deploy_to_branch result.
        if raw.get("engine_missing"):
            return "error"
        return "ok" if (exit_code == 0 and raw.get("deployed")) else "error"
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
    elif kind == "deploy":
        env["deploy"] = {"deployed": raw.get("deployed", False),
                         "branch": raw.get("branch")}
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


def _invoke_r(snippet: str, *, timeout: float | None = None) -> tuple[str, int]:
    """Run an R snippet via Rscript; return (stdout, exit_code). Mocked in tests.

    timeout=None (default) keeps the unbounded behavior the long kinds
    (check/test/coverage/revdep) need; quick/dispatch callers pass a bound.
    On subprocess.TimeoutExpired returns ('{"timed_out": true}', 124).
    """
    rscript = shutil.which("Rscript")
    if rscript is None:
        return ('{"engine_missing":["R"]}', 127)
    try:
        proc = subprocess.run([rscript, "-e", snippet],
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ('{"timed_out": true}', 124)
    return (proc.stdout.strip(), proc.returncode)


def _install_package(path: str) -> tuple[dict, int]:
    """R CMD INSTALL <path>; return (raw, exit_code)."""
    pkg = find_package(path) or {}
    rbin = shutil.which("R")
    if rbin is None:
        return ({"engine_missing": ["R"]}, 127)
    proc = subprocess.run([rbin, "CMD", "INSTALL", path], capture_output=True, text=True)
    return ({"installed_version": pkg.get("version")}, proc.returncode)


def _deploy_envelope(status, pkg, *, branch, gate, ref_dir=None,
                     forced=False, deployed=False, messages=None, blockers=None):
    """House envelope for the clean-ref deploy path (kind='deploy').

    `gate` carries the pre-deploy leak-scan outcome (status + offending files +
    publish preview); `blockers` lists non-allowlisted tracked/modified files
    that aborted the deploy (empty once --force is used or none found).
    """
    return {
        "kind": "deploy",
        "status": status,
        "package": (pkg or {}).get("package", ""),
        "version": (pkg or {}).get("version", ""),
        "branch": branch,
        "forced": forced,
        "deployed": deployed,
        "ref_dir": ref_dir,
        "gate": gate,
        "blockers": blockers or [],
        "engine_missing": [],
        "messages": messages or [],
    }


def _git_worktree_head(repo: str, dest: Path) -> tuple[bool, str]:
    """Materialize a clean HEAD checkout into `dest` via `git worktree add --detach`.

    A linked worktree shares `repo`'s `.git` directory (and therefore its remote),
    so `pkgdown::deploy_to_branch()` — which drives the package's OWN git repo
    (checkout --orphan / remote / fetch / push) — has a real repo+remote to push
    to, while the checked-out tree contains only committed files (untracked
    working-dir files are structurally excluded — the #52 goal).

    `git worktree add` requires `dest` to not already exist (or be empty), so the
    caller passes a fresh non-existent subpath.

    Returns (ok, message). On any git failure returns (False, reason) so the
    caller REFUSES the deploy — we never fall back to building the working dir
    (that would reintroduce the untracked-file leak this whole path prevents).
    """
    git = shutil.which("git")
    if git is None:
        return (False, "git not found on PATH — cannot build a clean ref.")
    try:
        proc = subprocess.run(
            [git, "-C", repo, "worktree", "add", "--detach", str(dest), "HEAD"],
            capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError) as e:  # pragma: no cover
        return (False, f"git worktree add failed: {e}")
    if proc.returncode != 0:
        err = proc.stderr.strip()
        return (False, f"git worktree add HEAD failed "
                       f"(not a git repo, or no commits?): {err}")
    return (True, "clean ref materialized from HEAD via git worktree")


def _git_worktree_cleanup(repo: str, dest: Path) -> None:
    """Best-effort removal of the linked worktree at `dest`. Swallows all errors —
    cleanup must never mask the real deploy outcome."""
    git = shutil.which("git")
    if git is None:
        return
    try:
        subprocess.run(
            [git, "-C", repo, "worktree", "remove", "--force", str(dest)],
            capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):  # pragma: no cover
        pass


def _run_deploy(path: str, pkg: dict, *, branch: str = "gh-pages",
                force: bool = False) -> dict:
    """Clean-ref pkgdown deploy (issue #52). MUTATING + NETWORK — recommend-only.

    NEVER auto-run: this pushes to a remote branch via
    ``pkgdown::deploy_to_branch()``. There is no SAFE_AUTORUN code constant; the
    boundary is enforced in agents/orchestrator.md (deploy is recommend-only and
    is deliberately absent from every auto-run enumeration there).

    Flow (SPEC § Architecture):
      1. run check_site_leaks first;
      2. HARD-ABORT (blocked) on a non-allowlisted file that is in HEAD
         (git_status tracked/modified) — `--force` downgrades block→warn + proceeds;
      3. build a clean ref via `git worktree add --detach <tempdir> HEAD`
         (NOT the working dir) — refuse the deploy if that fails;
      4. run deploy_to_branch(branch=…) INSIDE the detached-HEAD worktree;
      5. include a "files pkgdown will publish" preview in the envelope;
      6. always remove the linked worktree (try/finally), even on failure.
    """
    # — 1. pre-deploy leak scan —
    gate = sitelint.check_site_leaks(path)
    # A-gate: a finding blocks the deploy IFF it is actually in HEAD — the deploy
    # republishes `git worktree add --detach HEAD`, so only HEAD-resident files
    # can reach the published site. A staged-but-uncommitted NEW file (porcelain
    # 'A ', tagged "modified" by sitelint) is NOT in HEAD and cannot leak; a
    # committed-then-deleted file is still in HEAD and DOES leak.
    head_set = set(sitelint._head_paths(Path(path)))
    blocking = [f for f in gate.get("findings", [])
                if f.get("file") in head_set]
    # C-preview: the publish preview is the SAME finding set as the gate (all
    # scopes, path-qualified), NOT just root *.md — otherwise a blocked man/ or
    # vignettes/ file prints "(none) will publish" and on --force publishes
    # silently. Keyed on the path-qualified finding["file"].
    preview = sorted(f["file"] for f in gate.get("findings", []))

    # — 2. hard-abort gate —
    if blocking and not force:
        names = ", ".join(sorted(f["file"] for f in blocking))
        return _deploy_envelope(
            "blocked", pkg, branch=branch, gate=gate, blockers=blocking,
            messages=[
                f"Refusing to deploy: {len(blocking)} non-allowlisted file(s) "
                f"are committed and WOULD be published by pkgdown: {names}.",
                "Move scratch docs to a gitignored subdir, allowlist them via "
                ".rforge.yaml site.allowlist, or re-run with --force.",
                f"Files pkgdown would publish: {', '.join(preview) or '(none)'}",
            ])

    forced = bool(blocking and force)
    pre_messages: list[str] = []
    if forced:
        names = ", ".join(sorted(f["file"] for f in blocking))
        pre_messages.append(
            f"--force: proceeding despite {len(blocking)} non-allowlisted "
            f"committed file(s) that will be published: {names}.")
    pre_messages.append(
        f"Files pkgdown will publish: {', '.join(preview) or '(none)'}")

    # — 3. clean ref via git worktree (REFUSE on failure; never deploy the worktree) —
    #
    # RESOLVED (was "C-RISK UNVALIDATED"): `git archive | tar -x` is NON-FUNCTIONAL
    # for this path — `deploy_to_branch(pkg=…)` does not merely build, it drives the
    # package's OWN git repo (git_current_branch / checkout --orphan / remote /
    # fetch / push). An archived tempdir has no `.git` and no remote, so deploy
    # fails at the first internal git call. `git worktree add --detach <dest> HEAD`
    # is therefore MANDATORY: a linked worktree shares the main repo's `.git`+remote
    # (so deploy_to_branch can push) AND contains only committed files (so untracked
    # working-dir files stay structurally excluded — the #52 goal). The two
    # requirements converge on the worktree mechanism.
    #
    # `git worktree add` needs a non-existent dest, so parent=mkdtemp(), dest=parent/head.
    #
    # ONE honest caveat: a full end-to-end deploy (a real push) is the final
    # confirmation that deploy_to_branch succeeds from a detached-HEAD linked
    # worktree — the tests here mock the R call and cannot exercise the real push.
    # E-tmpdir: `mkdtemp` creates `parent`; the worktree lives at parent/head.
    # Both the worktree-failure early return AND the deploy path must clean up
    # `parent` (not just the worktree), or an empty rforge-deploy-* dir leaks
    # into $TMPDIR. The outer try/finally rmtree's `parent` on every path.
    parent = tempfile.mkdtemp(prefix="rforge-deploy-")
    ref_dir = str(Path(parent) / "head")
    try:
        ok, msg = _git_worktree_head(path, Path(ref_dir))
        if not ok:
            return _deploy_envelope(
                "warn", pkg, branch=branch, gate=gate, ref_dir=ref_dir,
                forced=forced,
                messages=pre_messages + [
                    msg,
                    "Deploy refused — would not silently build the working "
                    "directory (that path can leak untracked files). Commit "
                    "your work and retry.",
                ])

        # — 4. deploy from INSIDE the detached-HEAD worktree (NOT the working dir) —
        #      Always remove the linked worktree afterwards (try/finally).
        try:
            snippet = deploy_snippet(ref_dir, branch=branch)
            stdout, code = _invoke_r(snippet)
            raw = _parse_json(stdout)
            if raw is None:
                raw = console_fallback("deploy", stdout)
            env = normalize("deploy", raw, code, pkg)
            env["forced"] = forced
            env["ref_dir"] = ref_dir
            env["branch"] = raw.get("branch", branch)
            env["deployed"] = bool(raw.get("deployed", False))
            env["gate"] = gate
            env["blockers"] = blocking if forced else []
            env["messages"] = pre_messages + list(env.get("messages", []))
            # pkgdown missing → engine_missing 🟡 (OPTIONAL_ENGINES downgrade)
            for eng in env.get("engine_missing", []):
                if INSTALL_HINT.get(eng):
                    env.setdefault("messages", []).append(
                        f"Missing R package — run: {INSTALL_HINT[eng]}")
                if eng in OPTIONAL_ENGINES and env["status"] == "error":
                    env["status"] = "warn"
            if forced and env["status"] == "ok":
                env["status"] = "warn"  # surface that the gate was overridden
            return env
        finally:
            _git_worktree_cleanup(path, Path(ref_dir))
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def run(kind: str, path: str = ".", *, as_cran: bool = False, preview: bool = False,
        strict: bool = False, articles_only: bool = False, devel: bool = False,
        flavor: str | None = None, incoming: bool = False,
        platform: str = "all", platforms: list | None = None,
        preset: str | None = None, rc_mode: bool = False,
        branch: str = "gh-pages", force: bool = False) -> dict:
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
        # Lazy import keeps the rcmd→rhub edge off the module top (acyclic:
        # rhub imports rsnippets + lazily imports rcmd envelope helpers).
        from lib.rhub import _run_rhub
        return _run_rhub(path, pkg, platforms=platforms, preset=preset, rc_mode=rc_mode)
    if kind == "deploy":
        # MUTATING + NETWORK — recommend-only; never auto-run (see _run_deploy).
        return _run_deploy(path, pkg, branch=branch, force=force)
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
    if code == 124 or raw.get("timed_out"):
        raw = {"messages": ["Rscript timed out — the operation took too long "
                            "(quick path bounded; long kinds are unbounded)."]}
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
                  cranlint.check_planning_consistency, cranlint.check_test_config,
                  sitelint.check_site_leaks):
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
                             "s7runtime", "deploy"])
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
    ap.add_argument("--branch", default="gh-pages",
                    help="deploy: target branch for pkgdown::deploy_to_branch "
                         "(default gh-pages)")
    ap.add_argument("--force", action="store_true",
                    help="deploy: override the leak gate — proceed despite "
                         "non-allowlisted committed files (downgrades block→warn)")
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
                  platforms=plats, preset=ns.preset, rc_mode=ns.rc_mode,
                  branch=ns.branch, force=ns.force)
    print(json.dumps(env, indent=2))
    # "dispatched" (winbuilder/rhub) is non-error — exits 0 like "ok"/"warn"
    return 0 if env.get("status") not in ("error", "blocked") else 1


if __name__ == "__main__":
    sys.exit(main())

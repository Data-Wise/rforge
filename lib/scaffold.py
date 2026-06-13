"""
Authoring / scaffolding engine (`r:use-test` / `r:use-package` / `r:use-vignette`).

Plans (and, with ``write=True``, applies) package artifacts for an **existing**
R package — a testthat file with drafted block *structure*, a declared
dependency + ``@importFrom``, or a vignette skeleton + outline. **Dry-run by
default**; ``write=True`` applies; ``force=True`` is required to overwrite an
existing target.

Pure Python — no R subprocess here. The ``usethis`` *infra* (testthat edition,
vignette builder) lives in ``lib.usethis_infra`` (guarded R). Content drafting
(test assertions, vignette prose) is the command prompt's (AI) job — this module
emits only the verifiable *structure*, with assertions left as ``# TODO`` so no
expected values are ever invented (SPEC "No oracle").

``r:use-package`` **reuses** ``lib.deps_sync``'s DESCRIPTION-patch writer
(``_apply_patch`` / ``_rewrite_field``) — one DCF-editing implementation, two
commands.

Usage (CLI, from repo root):
    python3 -m lib.scaffold test    --fn estimate     --path PKG [--write] [--force]
    python3 -m lib.scaffold package --pkg tibble      --path PKG [--write] [--force]
    python3 -m lib.scaffold vignette --name intro     --path PKG [--write] [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .discovery import read_description

__all__ = [
    "Param", "StopBranch", "ParamConstraint", "Signature",
    "parse_function", "plan_test", "plan_package", "plan_vignette",
    "scaffold_data", "scaffold_citation",
    "scaffold",
]

# ── roxygen / R source patterns ─────────────────────────────────────────────
_PARAM_RE = re.compile(r"^#'\s*@param\s+(\w+)\s+(.*)$")
_STOP_RE = re.compile(r"""\bstop\(\s*(["'])(.*?)\1""")
_DEF_RE_TMPL = r"^\s*{name}\s*(?:<-|=)\s*function\s*\("


def _envelope(kind: str, status: str, *, findings=None, patch=None,
              messages=None, plan=None) -> dict:
    """House-style envelope, mirroring lib.deps_sync / lib.cranlint keys."""
    return {
        "kind": kind,
        "status": status,
        "findings": findings or [],
        "patch": patch or {},
        "plan": plan or {},
        "messages": messages or [],
        "engine_missing": [],
    }


@dataclass
class Param:
    name: str
    default: Optional[str] = None


@dataclass
class StopBranch:
    message: str


@dataclass
class ParamConstraint:
    param: str
    note: str  # the roxygen @param sentence that implies an edge case


@dataclass
class Signature:
    name: str
    params: list[Param] = field(default_factory=list)
    stop_branches: list[StopBranch] = field(default_factory=list)
    param_constraints: list[ParamConstraint] = field(default_factory=list)
    source_file: Optional[Path] = None


def _split_args(arglist: str) -> list[Param]:
    """Split an R formals string ``a, b, cov = 0`` into Params (depth-aware)."""
    params, depth, buf = [], 0, ""
    for ch in arglist:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            params.append(buf); buf = ""
        else:
            buf += ch
    if buf.strip():
        params.append(buf)
    out: list[Param] = []
    for raw in params:
        raw = raw.strip()
        if not raw or raw == "...":
            if raw == "...":
                out.append(Param(name="..."))
            continue
        if "=" in raw:
            nm, _, dflt = raw.partition("=")
            out.append(Param(name=nm.strip(), default=dflt.strip()))
        else:
            out.append(Param(name=raw))
    return out


def _grab_arglist(text: str, start: int) -> str:
    """From the ``(`` at/after ``start``, return the balanced arglist contents."""
    i = text.index("(", start)
    depth, j = 0, i
    while j < len(text):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
        j += 1
    return text[i + 1:]


# Roxygen sentences that signal an edge case worth a test branch. These are
# genuine *constraints* (imperative/relational language) — not bare type words
# like "scalar"/"integer", which describe every argument and would over-generate
# one edge-case block per @param.
_CONSTRAINT_HINT = re.compile(
    r"(must|non-negative|positive|cannot|should not|nonzero|non-empty|"
    r">=|<=|greater|less|at least)", re.IGNORECASE)


def parse_function(path: str | os.PathLike, fn: str) -> Optional[Signature]:
    """Find ``fn`` in the package's ``R/`` and parse its signature/roxygen/branches.

    Returns None if the function's definition cannot be located (caller scaffolds
    a minimal stub + note — never invents). Searches every ``R/*.R`` file.
    """
    root = Path(path)
    rdir = root / "R"
    if not rdir.is_dir():
        return None
    def_re = re.compile(_DEF_RE_TMPL.format(name=re.escape(fn)), re.MULTILINE)
    for src in sorted(rdir.glob("*.R")):
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = def_re.search(text)
        if not m:
            continue
        sig = Signature(name=fn, source_file=src)
        sig.params = _split_args(_grab_arglist(text, m.start()))
        # stop() branches in the function body (from the def to EOF — good enough
        # for a single-function file; multi-fn files just over-collect, harmless)
        body = text[m.start():]
        for sm in _STOP_RE.finditer(body):
            sig.stop_branches.append(StopBranch(message=sm.group(2)))
        # @param sentences (the roxygen block immediately above the def)
        head = text[:m.start()].splitlines()
        for line in head:
            pm = _PARAM_RE.match(line)
            if pm and _CONSTRAINT_HINT.search(pm.group(2)):
                sig.param_constraints.append(
                    ParamConstraint(param=pm.group(1), note=pm.group(2).strip()))
        return sig
    return None


# ── write/force gate (shared by all three planners) ─────────────────────────

def _apply_file(target: Path, content: str, *, write: bool, force: bool) -> tuple[str, list[str]]:
    """Apply a planned single-file write under the dry-run/write/force contract.

    Returns (status, messages). Never writes on dry-run. Refuses to overwrite an
    existing target unless ``force``. Status is ``ok`` on a clean plan/apply,
    ``warn`` when blocked by an existing file without ``--force``.
    """
    exists = target.exists()
    if not write:
        msg = (f"dry-run: would {'OVERWRITE' if exists else 'create'} {target} "
               f"(pass --write to apply"
               + (", --force to overwrite" if exists else "") + ")")
        return ("ok", [msg])
    if exists and not force:
        return ("warn", [f"{target} already exists — pass --force to overwrite "
                         f"(nothing written)"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ("ok", [f"wrote {target}"])


# ── r:use-test ──────────────────────────────────────────────────────────────

_HAPPY_BLOCK = '''test_that("{fn}() returns for valid input", {{
  # TODO: replace with a real call + expected value.
  # NOTE (no oracle): the correct result is NOT inferred from the signature —
  # supply the expected value yourself (e.g. a delta-method estimate may be
  # a*b + cov(a,b), not a*b).
  result <- {fn}({args})
  expect_no_error({fn}({args}))
  # TODO: expect_equal(result, <expected>)
}})'''

_ERROR_BLOCK = '''test_that("{fn}() errors when {label}", {{
  # TODO: build inputs that trigger this branch.
  expect_error({fn}({args}), regexp = {pattern})
}})'''

_CONSTRAINT_BLOCK = '''test_that("{fn}() handles the '{param}' constraint: {note}", {{
  # TODO: exercise the edge implied by @param {param}: {note}
  # expect_error(...) or expect_equal(...) as appropriate — do not guess values.
  skip("TODO: write this edge-case test")
}})'''

_STUB_BLOCK = '''test_that("{fn}() works", {{
  # TODO: signature could not be resolved automatically; write tests by hand.
  skip("TODO")
}})'''


def _arg_call(sig: Signature) -> str:
    """A placeholder positional call list for a function, e.g. ``a, b`` (no defaults)."""
    required = [p.name for p in sig.params if p.default is None and p.name != "..."]
    return ", ".join(required) if required else ""


def _r_string(s: str) -> str:
    """Quote a Python string as an R double-quoted literal (for regexp=)."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def plan_test(path: str | os.PathLike, fn: str, *, write: bool = False,
              force: bool = False) -> dict:
    """Plan ``tests/testthat/test-<fn>.R`` with one block per branch.

    Blocks: a happy path (assertion = ``# TODO``), one ``expect_error`` per
    ``stop()`` message, and one skipped edge-case stub per constrained ``@param``.
    **No expected values are invented** (SPEC "No oracle"). Dry-run by default.
    """
    root = Path(path)
    sig = parse_function(root, fn)
    target = root / "tests" / "testthat" / f"test-{fn}.R"

    if sig is None:
        content = "# Generated by /rforge:r:use-test\n\n" + _STUB_BLOCK.format(fn=fn) + "\n"
        status, msgs = _apply_file(target, content, write=write, force=force)
        msgs.append(f"could not resolve a signature for `{fn}()` — wrote a minimal "
                    f"stub; no cases drafted (never invented).")
        env = _envelope("use-test", "warn",
                        plan={"target": str(target), "content": content}, messages=msgs)
        return env

    call = _arg_call(sig)
    blocks = [_HAPPY_BLOCK.format(fn=fn, args=call)]
    for sb in sig.stop_branches:
        label = re.sub(r"\W+", " ", sb.message).strip() or "input is invalid"
        blocks.append(_ERROR_BLOCK.format(fn=fn, args=call, label=label,
                                          pattern=_r_string(sb.message)))
    for c in sig.param_constraints:
        blocks.append(_CONSTRAINT_BLOCK.format(fn=fn, param=c.param, note=c.note))

    content = (f"# Generated by /rforge:r:use-test for {fn}()\n"
               f"# Review every TODO before trusting these tests.\n\n"
               + "\n\n".join(blocks) + "\n")

    status, msgs = _apply_file(target, content, write=write, force=force)
    msgs.append(f"drafted {len(blocks)} block(s): 1 happy-path + "
                f"{len(sig.stop_branches)} error + {len(sig.param_constraints)} edge. "
                f"All assertions are # TODO — verify before trusting.")
    return _envelope("use-test", status,
                     plan={"target": str(target), "content": content,
                           "blocks": len(blocks)}, messages=msgs)


# ── r:use-package ───────────────────────────────────────────────────────────

from . import deps_sync as _deps_sync  # noqa: E402  (reuse its DCF writer)

# Symbol used per pkg in R/ (best-effort) so @importFrom can name it.
_USE_SYMBOL_RE_TMPL = r"{pkg}::([A-Za-z.][\w.]*)"


def _classify_field(usages, pkg_key: str) -> Optional[str]:
    """Return 'Imports' or 'Suggests' for a used package, or None if unused.

    Reuses lib.deps_sync.scan_usage's Usage model: unconditional R/ use →
    Imports; tests/vignettes-or-guarded-only → Suggests.
    """
    u = usages.get(pkg_key)
    if u is None:
        return None
    if u.needs_imports:
        return "Imports"
    if u.needs_suggests:
        return "Suggests"
    return None


def _pick_importfrom(root: Path, pkg: str) -> tuple[Optional[Path], Optional[str]]:
    """Find the R/ file using ``pkg::sym`` and the first symbol, for @importFrom.

    Returns (file, symbol). Falls back to (None, None) → command should place the
    tag in a package-doc file (e.g. R/<pkg>-package.R) per the SPEC.
    """
    sym_re = re.compile(_USE_SYMBOL_RE_TMPL.format(pkg=re.escape(pkg)))
    rdir = root / "R"
    if rdir.is_dir():
        for src in sorted(rdir.glob("*.R")):
            text = src.read_text(encoding="utf-8", errors="replace")
            m = sym_re.search(text)
            if m:
                return src, m.group(1)
    return None, None


def _insert_importfrom(src: Path, pkg: str, sym: str) -> bool:
    """Insert ``#' @importFrom pkg sym`` into the roxygen block above the first
    function def in ``src`` (idempotent). Returns True if the file changed."""
    text = src.read_text(encoding="utf-8", errors="replace")
    tag = f"#' @importFrom {pkg} {sym}"
    if re.search(rf"@importFrom\s+{re.escape(pkg)}\b", text):
        return False
    # insert just before the @export (or the first function def) of the block
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#' @export"):
            lines.insert(i, tag + "\n")
            src.write_text("".join(lines), encoding="utf-8")
            return True
    # no @export anchor: prepend a one-line roxygen tag at top of file
    src.write_text(tag + "\n" + text, encoding="utf-8")
    return True


def plan_package(path: str | os.PathLike, pkg: str, *, write: bool = False,
                 force: bool = False) -> dict:
    """Add ``pkg`` to DESCRIPTION (Imports/Suggests by usage) + an @importFrom.

    Imports-vs-Suggests is decided by reusing ``lib.deps_sync.scan_usage``.
    The DESCRIPTION edit reuses ``lib.deps_sync._apply_patch`` — the same DCF
    writer ``r:deps-sync`` uses (one implementation, two commands). Dry-run by
    default; advisory judgement is always surfaced so the user can override.
    """
    root = Path(path)
    desc_path = root / "DESCRIPTION"
    desc = read_description(desc_path)
    if desc is None:
        return _envelope("use-package", "warn", messages=[
            f"No parseable DESCRIPTION at {desc_path} — is this an R package?"])

    strong, suggests, _ = _deps_sync._declared(desc)
    key = _deps_sync._norm(pkg)
    if key in strong or key in suggests:
        cur = "Imports/Depends" if key in strong else "Suggests"
        return _envelope("use-package", "warn", messages=[
            f"`{pkg}` is already declared ({cur}) — nothing to add. "
            f"Run /rforge:r:deps-sync to reconcile all deps."])

    usages = _deps_sync.scan_usage(root)
    field = _classify_field(usages, key)
    if field is None:
        # Not yet used anywhere — default to Imports, but say so (user overrides).
        field = "Imports"
        judged = (f"`{pkg}` is not used in the code yet — defaulting to Imports. "
                  f"If it's test/vignette-only, re-run intending Suggests.")
    else:
        why = ("used unconditionally in R/" if field == "Imports"
               else "used only in tests/vignettes (or guarded)")
        judged = f"`{pkg}` → {field} ({why})."

    patch_key = "add_imports" if field == "Imports" else "add_suggests"
    patch = {patch_key: [pkg]}

    src, sym = _pick_importfrom(root, pkg) if field == "Imports" else (None, None)
    # A descriptor naming the using file + the @importFrom tag we'd place there,
    # so the plan is self-documenting (and names the pkg, not just a temp path).
    if src and sym:
        rel = src.relative_to(root) if src.is_relative_to(root) else src
        importfrom_file = f"{rel} (@importFrom {pkg} {sym})"
    elif src:
        rel = src.relative_to(root) if src.is_relative_to(root) else src
        importfrom_file = f"{rel} (@importFrom {pkg})"
    else:
        importfrom_file = ""

    # ── dry-run: report the plan, touch nothing ──────────────────────────────
    if not write:
        plan = {"field": field, "patch": patch, "importfrom_file": importfrom_file,
                "importfrom_symbol": sym}
        return _envelope("use-package", "ok", patch=patch, plan=plan, messages=[
            judged,
            f"dry-run: would add `{pkg}` to {field}" +
            (f" + @importFrom {pkg} {sym} in {src.name}" if src and sym else "") +
            " (pass --write to apply)."])

    # ── --write: reuse the deps_sync DCF writer ──────────────────────────────
    applied = _deps_sync._apply_patch(desc_path, patch)
    msgs = [judged] + [f"DESCRIPTION: {a}" for a in applied]
    inserted = False
    if field == "Imports" and src and sym:
        inserted = _insert_importfrom(src, pkg, sym)
        msgs.append(f"@importFrom {pkg} {sym} → {src.name}" if inserted
                    else f"@importFrom for {pkg} already present in {src.name}")
        msgs.append("Run /rforge:r:document to regenerate NAMESPACE.")
    elif field == "Imports":
        msgs.append(f"No `{pkg}::` call found to anchor @importFrom — add the tag "
                    f"to your package-doc file (R/<pkg>-package.R) by hand.")
    plan = {"field": field, "patch": patch, "importfrom_file": importfrom_file,
            "importfrom_symbol": sym}
    return _envelope("use-package", "ok", patch=patch, plan=plan, messages=msgs)


# ── r:use-vignette ──────────────────────────────────────────────────────────

_VIGNETTE_TMPL = '''---
title: "{title}"
output: rmarkdown::html_vignette
vignette: >
  %\\VignetteIndexEntry{{{title}}}
  %\\VignetteEngine{{knitr::rmarkdown}}
  %\\VignetteEncoding{{UTF-8}}
---

```{{r, include = FALSE}}
knitr::opts_chunk$set(collapse = TRUE, comment = "#>")
```

```{{r setup}}
library({pkg})
```

## Overview

<!-- TODO: one paragraph on what {pkg} is for. Drafted from DESCRIPTION below. -->
{description}

## Getting started

<!-- TODO: a minimal, runnable example. -->

```{{r}}
# TODO: show the package's primary workflow
```

## Details

<!-- TODO: expand on the main functions / arguments. -->

## See also

<!-- TODO: links to related vignettes / docs. -->
'''


def plan_vignette(path: str | os.PathLike, name: str, *, article: bool = False,
                  write: bool = False, force: bool = False) -> dict:
    """Plan ``vignettes/<name>.Rmd`` — a knitr skeleton + a drafted outline.

    The skeleton (YAML index entry + engine) mirrors what ``usethis::use_vignette``
    writes; the *infra* (vignettes/ dir + DESCRIPTION VignetteBuilder) is applied
    separately via ``lib.usethis_infra`` on ``--write``. Outline prose is seeded
    from the package Title/Description; sections are ``# TODO`` for the AI/author
    to expand. Dry-run by default.
    """
    root = Path(path)
    desc = read_description(root / "DESCRIPTION")
    pkg = getattr(desc, "package", None) or root.name
    title = getattr(desc, "title", None) or name
    description = getattr(desc, "description", None) or \
        f"<!-- TODO: describe {pkg} -->"

    content = _VIGNETTE_TMPL.format(title=title, pkg=pkg,
                                    description=description.strip())
    target = root / "vignettes" / f"{name}.Rmd"
    status, msgs = _apply_file(target, content, write=write, force=force)
    msgs.append("vignette outline drafted from DESCRIPTION; every section is a "
                "# TODO — expand the prose and add a runnable example.")
    if write and status == "ok":
        msgs.append("Next: run the guarded usethis infra to register the "
                    "VignetteBuilder — python3 -m lib.usethis_infra vignette "
                    f'--name {name} --path "{root}"'
                    + (" --article" if article else "")
                    + " (prints a manual recipe if usethis is absent).")
    return _envelope("use-vignette", status,
                     plan={"target": str(target), "content": content},
                     messages=msgs)


# ── r:use-data ────────────────────────────────────────────────────────────

_DATA_ROXYGEN_TMPL = '''#' {name}
#'
#' @title TODO: one-line title for the `{name}` dataset.
#'
#' @description TODO: describe what `{name}` contains and why it ships with the
#'   package.
#'
#' @format TODO: describe the object. For a data.frame, a `\\describe{{}}` of its
#'   variables:
#' \\describe{{
#'   \\item{{TODO_var}}{{TODO: description of the column / element.}}
#' }}
#'
#' @source TODO: where the data came from (citation / URL / generation script).
"{name}"'''


def _read_scalar_field(text: str, field_name: str) -> Optional[str]:
    """Return the single-line value of a DCF scalar field, or None if absent."""
    m = re.search(rf"^{re.escape(field_name)}:\s*(.*)$", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _set_scalar_field(text: str, field_name: str, value: str) -> str:
    """Add a scalar DCF field if absent (idempotent; leaves an existing value)."""
    if re.search(rf"^{re.escape(field_name)}:", text, re.MULTILINE):
        return text
    return text.rstrip("\n") + f"\n{field_name}: {value}\n"


def _needs_r_depends(specs: list[str]) -> bool:
    """True if the Depends field has no ``R (>= …)`` floor (data needs R >= 2.10)."""
    return not any(re.match(r"R\s*\(", s) for s in specs)


def scaffold_data(name: str, path: str | os.PathLike = ".", *,
                  write: bool = False) -> dict:
    """Plan (and, on ``--write``, apply) documentation for a package dataset.

    Appends a roxygen doc stub (``@title``/``@format \\describe{}``/``@source`` +
    the trailing ``"<name>"`` documented-data idiom) to ``R/data.R`` and patches
    ``DESCRIPTION`` (``LazyData: true`` / ``Depends: R (>= 2.10)``). The
    DESCRIPTION edit goes through the shared constraint-preserving DCF writer
    (``deps_sync._read_field_specs`` / ``_rewrite_field``) — existing version
    floors survive. **Never fabricates the ``.rda``** (the data is the user's);
    emits the exact ``usethis::use_data(<name>)`` command instead. Dry-run by
    default.
    """
    root = Path(path)
    desc_path = root / "DESCRIPTION"
    if not desc_path.is_file():
        return _envelope("use-data", "warn", messages=[
            f"No DESCRIPTION at {desc_path} — is this an R package?"])

    desc_text = desc_path.read_text(encoding="utf-8", errors="replace")
    stub = _DATA_ROXYGEN_TMPL.format(name=name)
    data_r = root / "R" / "data.R"

    # compute the DESCRIPTION delta (report it on dry-run, apply it on --write)
    delta: list[str] = []
    if _read_scalar_field(desc_text, "LazyData") is None:
        delta.append("LazyData: true")
    depends_specs = _deps_sync._read_field_specs(desc_text, "Depends")
    add_r_depends = _needs_r_depends(depends_specs)
    if add_r_depends:
        delta.append("Depends: R (>= 2.10)")

    reminder = (f"Data not written — generate it yourself, then save it: "
                f"`usethis::use_data({name})` (or `save({name}, "
                f"file = \"data/{name}.rda\")`).")

    # ── dry-run ───────────────────────────────────────────────────────────
    if not write:
        msgs = [
            f"dry-run: would append a roxygen doc for `{name}` to {data_r} "
            f"(pass --write to apply).",
            ("DESCRIPTION delta: " + "; ".join(delta)) if delta
            else "DESCRIPTION already has LazyData + an R (>= …) Depends floor.",
            reminder,
        ]
        return _envelope("use-data", "ok",
                         plan={"target": str(data_r), "content": stub,
                               "description_delta": delta},
                         messages=msgs)

    # ── --write ───────────────────────────────────────────────────────────
    # collision guard: don't duplicate an existing doc for the same \name
    existing = data_r.read_text(encoding="utf-8", errors="replace") if data_r.exists() else ""
    if re.search(rf'(?m)^\s*"{re.escape(name)}"\s*(#.*)?$', existing):
        return _envelope("use-data", "warn",
                         plan={"target": str(data_r)},
                         messages=[f"`R/data.R` already documents `{name}` "
                                   f"(found a `\"{name}\"` entry) — nothing appended.",
                                   reminder])

    data_r.parent.mkdir(parents=True, exist_ok=True)
    if existing:
        new_body = existing.rstrip("\n") + "\n\n\n" + stub + "\n"
    else:
        new_body = ("# Generated by /rforge:r:use-data — package data docs.\n\n"
                    + stub + "\n")
    data_r.write_text(new_body, encoding="utf-8")
    msgs = [f"appended roxygen doc for `{name}` to {data_r}."]

    # patch DESCRIPTION (constraint-preserving)
    new_text = desc_text
    if _read_scalar_field(new_text, "LazyData") is None:
        new_text = _set_scalar_field(new_text, "LazyData", "true")
        msgs.append("DESCRIPTION: +LazyData: true")
    if add_r_depends:
        new_specs = ["R (>= 2.10)"] + depends_specs
        new_text = _deps_sync._rewrite_field(new_text, "Depends", new_specs)
        msgs.append("DESCRIPTION: +Depends: R (>= 2.10)")
    if new_text != desc_text:
        desc_path.write_text(new_text, encoding="utf-8")
    else:
        msgs.append("DESCRIPTION already had LazyData + an R Depends floor.")
    msgs.append("Run /rforge:r:document to regenerate man/{0}.Rd.".format(name))
    msgs.append(reminder)
    return _envelope("use-data", "ok",
                     plan={"target": str(data_r), "content": stub,
                           "description_delta": delta},
                     messages=msgs)


# ── r:use-citation ──────────────────────────────────────────────────────────


def _author_arg_from_authors_r(authors_r: str) -> Optional[str]:
    """Return the ``Authors@R`` field value verbatim, for use as ``author = ``.

    The DESCRIPTION ``Authors@R`` field is *already valid R* — a ``person(...)``
    call or a ``c(person(...), person(...))`` vector. We re-emit it verbatim
    rather than extracting ``person()`` substrings with a flat regex (which
    truncates on the normal nested ``role = c("aut", "cre")`` idiom). Deterministic
    and lossless. Returns None when the field is empty / unparseable so the caller
    degrades to a ``# TODO`` author block.
    """
    if not authors_r:
        return None
    val = authors_r.strip()
    if not val:
        return None
    # Must look like an R person()/c() expression with balanced parens, else the
    # caller treats it as unparseable (the legacy `Author:` fallback case).
    if "person(" not in val:
        return None
    if val.count("(") != val.count(")"):
        return None
    return val


def _read_dcf_field_block(text: str, field_name: str) -> Optional[str]:
    """Return a (possibly multi-line) DCF field's value, continuation lines joined."""
    pat = re.compile(rf"^{re.escape(field_name)}:(.*?)(?=^\S|\Z)",
                     re.MULTILINE | re.DOTALL)
    m = pat.search(text)
    if not m:
        return None
    return " ".join(line.strip() for line in m.group(1).splitlines()).strip()


def scaffold_citation(path: str | os.PathLike = ".", *, write: bool = False,
                      force: bool = False) -> dict:
    """Plan (and, on ``--write``, write) ``inst/CITATION`` from DESCRIPTION.

    Parses ``Title``/``Authors@R`` (or fallback ``Author``)/``Version`` and the
    year (from ``Date`` if present, else a ``<YEAR>`` TODO — **never** a
    wall-clock date, per the determinism rule). Renders a
    ``bibentry(bibtype = "Manual", ...)`` with the package's own ``person()``
    calls. Refuses to clobber an existing ``inst/CITATION`` without ``force``.
    Unparseable authors degrade to a ``# TODO`` block + a warn (never raises).
    Dry-run by default.
    """
    root = Path(path)
    desc_path = root / "DESCRIPTION"
    if not desc_path.is_file():
        return _envelope("use-citation", "warn", messages=[
            f"No DESCRIPTION at {desc_path} — is this an R package?"])

    text = desc_path.read_text(encoding="utf-8", errors="replace")
    pkg = _read_scalar_field(text, "Package") or root.name
    title = _read_dcf_field_block(text, "Title") or pkg
    version = _read_scalar_field(text, "Version") or "<VERSION>"

    # year: from Date (YYYY) if present, else a TODO placeholder (determinism)
    date = _read_scalar_field(text, "Date")
    ym = re.match(r"(\d{4})", date) if date else None
    year = ym.group(1) if ym else "<YEAR>"

    warned = False
    authors_r = _read_dcf_field_block(text, "Authors@R")
    author_arg = _author_arg_from_authors_r(authors_r)
    if author_arg is None:
        warned = True
        author_arg = ("# TODO: could not parse Authors@R — fill in the author(s):\n"
                      "  person(\"<Given>\", \"<Family>\")")

    # Every interpolated value goes through _r_string() so embedded `"` / `\`
    # in Title/Package/Version can't break the surrounding R string literal.
    title_r = _r_string(f"{{{title}}}: {pkg}")
    note_r = _r_string(f"R package version {version}")
    year_r = _r_string(year)
    pkg_r = _r_string(pkg)
    plain_title_r = _r_string(f"{title}. ")
    note_text_r = _r_string(f"R package version {version}.")

    content = (
        f'bibentry(\n'
        f'  bibtype  = "Manual",\n'
        f'  title    = {title_r},\n'
        f'  author   = {author_arg},\n'
        f'  year     = {year_r},\n'
        f'  note     = {note_r},\n'
        f'  textVersion = paste0(\n'
        f'    {pkg_r}, " (", {year_r}, "). ", {plain_title_r},\n'
        f'    {note_text_r}\n'
        f'  )\n'
        f')\n'
    )

    target = root / "inst" / "CITATION"
    base_msgs = []
    if warned:
        base_msgs.append("Authors@R could not be parsed — wrote a # TODO author "
                         "block; fill it in by hand.")
    if year == "<YEAR>":
        base_msgs.append("No `Date:` in DESCRIPTION — year left as a <YEAR> TODO "
                         "(determinism: never a wall-clock date).")

    if not write:
        msgs = [f"dry-run: would write {target} (pass --write to apply"
                + (", --force to overwrite" if target.exists() else "") + ")."]
        return _envelope("use-citation", "warn" if warned else "ok",
                         plan={"target": str(target), "content": content},
                         messages=msgs + base_msgs)

    if target.exists() and not force:
        return _envelope("use-citation", "warn",
                         plan={"target": str(target), "content": content},
                         messages=[f"{target} already exists — pass --force to "
                                   f"overwrite (nothing written)."] + base_msgs)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return _envelope("use-citation", "warn" if warned else "ok",
                     plan={"target": str(target), "content": content},
                     messages=[f"wrote {target}."] + base_msgs)


# ── CLI ─────────────────────────────────────────────────────────────────────

def scaffold(mode: str, path: str = ".", *, fn: str = "", pkg: str = "",
             name: str = "", article: bool = False, write: bool = False,
             force: bool = False) -> dict:
    """Dispatch to the planners. Returns the envelope."""
    if mode == "test":
        return plan_test(path, fn, write=write, force=force)
    if mode == "package":
        return plan_package(path, pkg, write=write, force=force)
    if mode == "vignette":
        return plan_vignette(path, name, article=article, write=write, force=force)
    if mode == "data":
        return scaffold_data(name, path, write=write)
    if mode == "citation":
        return scaffold_citation(path, write=write, force=force)
    raise ValueError(f"unknown mode: {mode}")


def format_text(env: dict) -> str:
    icon = {"ok": "✅", "warn": "⚠️ ", "error": "❌"}.get(env["status"], "•")
    lines = [f"{icon} {env['kind']}: {env['status']}"]
    if env.get("plan", {}).get("target"):
        lines.append(f"target: {env['plan']['target']}")
    if env.get("plan", {}).get("content"):
        lines.append("\n--- planned content ---\n" + env["plan"]["content"])
    for m in env.get("messages", []):
        lines.append(f"💡 {m}")
    return "\n".join(lines)


def _main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="lib.scaffold", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["test", "package", "vignette", "data", "citation"])
    ap.add_argument("--path", default=".")
    ap.add_argument("--fn", default="")
    ap.add_argument("--pkg", default="")
    ap.add_argument("--name", default="")
    ap.add_argument("--article", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args(argv)
    env = scaffold(ns.mode, ns.path, fn=ns.fn, pkg=ns.pkg, name=ns.name,
                   article=ns.article, write=ns.write, force=ns.force)
    print(json.dumps(env, indent=2) if ns.format == "json" else format_text(env))
    return 0 if env["status"] in ("ok", "warn") else 1


if __name__ == "__main__":
    sys.exit(_main())

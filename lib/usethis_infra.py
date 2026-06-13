"""
Guarded ``usethis`` *infra* for the scaffolding commands.

The pure-Python ``lib.scaffold`` plans *file content*; ``usethis`` does the
package-config bits it does correctly: ``use_testthat(3)`` (sets
``Config/testthat/edition``) and ``use_vignette()`` (creates ``vignettes/``,
sets ``VignetteBuilder``). Mirrors ``lib.rcmd``'s ``_guard`` archetype — if
``usethis`` is absent, emit ``engine_missing`` + a manual recipe; never fail.

``usethis`` is a scoped **authoring** engine, NOT a gate — the "no
devtools/usethis for gate commands" rule is unaffected.

Usage:
    python3 -m lib.usethis_infra testthat  --path PKG
    python3 -m lib.usethis_infra vignette  --name intro --path PKG [--article]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

OPTIONAL_ENGINES = {"usethis"}

_MANUAL = {
    "testthat": 'In R: usethis::use_testthat(3)',
    "vignette": 'In R: usethis::use_vignette("{name}")',
    "article": 'In R: usethis::use_article("{name}")',
}


def _guard(body: str) -> str:
    """Emit engine_missing JSON if usethis/jsonlite absent, else run body."""
    return (
        'if (!requireNamespace("usethis", quietly=TRUE) || '
        '!requireNamespace("jsonlite", quietly=TRUE)) {'
        'cat(\'{"engine_missing":["usethis"]}\'); quit(status=0)}; ' + body
    )


def _r_string(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _snippet(action: str, path: str, *, name: str = "", article: bool = False) -> str:
    p = _r_string(path)
    if action == "testthat":
        return _guard(
            f'usethis::with_project({p}, usethis::use_testthat(3)); '
            f'cat(jsonlite::toJSON(list(edition=3, ok=TRUE), auto_unbox=TRUE))')
    if action == "vignette":
        fn = "use_article" if article else "use_vignette"
        return _guard(
            f'usethis::with_project({p}, usethis::{fn}({_r_string(name)})); '
            f'cat(jsonlite::toJSON(list(created={_r_string(name)}, '
            f'article={"TRUE" if article else "FALSE"}), auto_unbox=TRUE))')
    raise ValueError(f"unknown action: {action}")


def _invoke_r(snippet: str) -> tuple[str, int]:
    """Run via Rscript; return (stdout, exit). Mocked in tests."""
    rscript = shutil.which("Rscript")
    if rscript is None:
        return ('{"engine_missing":["usethis"]}', 127)
    proc = subprocess.run([rscript, "-e", snippet], capture_output=True, text=True)
    return (proc.stdout.strip(), proc.returncode)


def run(action: str, path: str = ".", *, name: str = "", article: bool = False) -> dict:
    """Run a usethis infra action; degrade to a manual recipe when absent."""
    stdout, code = _invoke_r(_snippet(action, path, name=name, article=article))
    try:
        raw = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        raw = {}
    if raw.get("engine_missing"):
        key = "article" if (action == "vignette" and article) else action
        recipe = _MANUAL[key].format(name=name)
        return {"kind": f"usethis:{action}", "status": "warn",
                "engine_missing": ["usethis"],
                "messages": [f"usethis not installed — run it manually: {recipe} "
                             "(install: install.packages(\"usethis\"))"]}
    status = "ok" if code == 0 else "error"
    return {"kind": f"usethis:{action}", "status": status, "engine_missing": [],
            "result": raw, "messages": []}


def _main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="lib.usethis_infra", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["testthat", "vignette"])
    ap.add_argument("--path", default=".")
    ap.add_argument("--name", default="")
    ap.add_argument("--article", action="store_true")
    ns = ap.parse_args(argv)
    env = run(ns.action, ns.path, name=ns.name, article=ns.article)
    print(json.dumps(env, indent=2))
    return 0 if env["status"] in ("ok", "warn") else 1


if __name__ == "__main__":
    sys.exit(_main())

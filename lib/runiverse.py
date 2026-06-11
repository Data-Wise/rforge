"""
R-universe early-access status (``r:submit --universe``).

Confirms a package's R-universe is registered and reads its per-platform
build/check status from the public R-universe API — the early-access channel
that serves CRAN-like binaries built from GitHub within minutes, *before* CRAN's
slower human review. **Read-only:** R-universe builds automatically on every git
push, so this never uploads — it verifies and reports.

Pure Python — stdlib only (``urllib``/``json``, ``subprocess`` for ``git
remote``); no R subprocess, no external deps. Reuses
``lib.discovery.read_description`` for the package name. Degrades to a ``warn``
envelope (never raises) when offline or unregistered, so it is safe in CI and
hermetic smoke tests.

The CRAN handoff stays explicit: this tier is passive/automatic (a git push),
CRAN is active/manual (you run ``submit_cran()``). They never share a trigger,
so "CRAN explicit" is structurally guaranteed.

API shape (``https://<owner>.r-universe.dev/api/packages/<pkg>``) — R-universe
prefixes its internal metadata with ``_``; the fields we read:

  ``_status``    overall build state ("success" / "failure" / …)
  ``_binaries``  list of per-platform builds, each with os/arch/r + status/check

The parser is defensive (tolerates field-name variation) — the exact contract
should be re-verified against a live response (the docs API page blocks
automated fetch). A 404 means the package is not in that universe (unregistered),
which is reported as guidance, distinct from a network failure.

Usage (CLI, from repo root):
    python3 -m lib.runiverse --path /path/to/pkg                  # auto-detect universe from git remote
    python3 -m lib.runiverse --path /path/to/pkg --universe ropensci
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .discovery import read_description

__all__ = [
    "remote_owner",
    "resolve_universe",
    "api_url",
    "install_snippet",
    "fetch_status",
    "summarize",
    "verify",
]

_DEFAULT_TIMEOUT = 10.0
_GITHUB_OWNER_RE = re.compile(r"github\.com[:/]([^/]+)/")
# R-universe binary `status` (build) values that mean "built & installable".
# Verified against a live response (data-wise.r-universe.dev/api/packages/RMediation):
# each _binaries[] entry carries a build `status` ("success"/…) AND a separate R CMD
# `check` result ("OK"/"NOTE"/"WARNING"/"ERROR"). Green = built; check is advisory.
_BUILD_OK = frozenset({"success", "ok", "built"})


def _envelope(status: str, findings: list, messages: list, *, owner=None, pkg=None) -> dict:
    """House-style envelope, mirroring ``lib.deps_sync``/``lib.cranlint`` keys."""
    return {
        "kind": "runiverse",
        "status": status,
        "owner": owner,
        "package": pkg,
        "findings": findings,
        "messages": messages,
        "engine_missing": [],
    }


def remote_owner(path: str = ".") -> Optional[str]:
    """GitHub owner of the ``origin`` remote, or None.

    Handles both ``https://github.com/<owner>/<repo>.git`` and
    ``git@github.com:<owner>/<repo>.git`` forms. Never raises — returns None if
    git is absent, there is no remote, or the URL is not a GitHub URL.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    m = _GITHUB_OWNER_RE.search(out.stdout.strip())
    return m.group(1) if m else None


def resolve_universe(path: str = ".", override: Optional[str] = None) -> Optional[str]:
    """The universe name: ``override`` if given, else the GitHub remote owner.

    Normalized to **lowercase** — R-universe subdomains and registry/monorepo
    names are canonically lowercase (the ``Data-Wise`` GitHub org maps to
    ``data-wise.r-universe.dev``), even though DNS itself is case-insensitive.
    """
    owner = override.strip().lstrip("@") if override else remote_owner(path)
    return owner.lower() if owner else None


def api_url(owner: str, pkg: str) -> str:
    """Per-package R-universe API endpoint (JSON). Owner lowercased (subdomain)."""
    return f"https://{owner.lower()}.r-universe.dev/api/packages/{pkg}"


def install_snippet(owner: str, pkg: str) -> str:
    """The early-access install line users run to get the R-universe build.

    Owner is lowercased (the canonical subdomain); the package name keeps its
    original case (R package names are case-sensitive).
    """
    return f'install.packages("{pkg}", repos = "https://{owner.lower()}.r-universe.dev")'


def fetch_status(owner: str, pkg: str, *, timeout: float = _DEFAULT_TIMEOUT) -> tuple[str, Optional[dict]]:
    """Read the package's R-universe status.

    Returns ``(reason, data)`` where reason is one of:
      ``"ok"``         — 200, parsed JSON in ``data``
      ``"not_found"``  — 404, the package is not in this universe (unregistered)
      ``"network"``    — any other HTTP error, timeout, or unparseable body

    Never raises — degradation is the point.
    """
    req = urllib.request.Request(api_url(owner, pkg), headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return "ok", json.loads(body)
    except urllib.error.HTTPError as e:
        return ("not_found", None) if e.code == 404 else ("network", None)
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return "network", None


def summarize(data: dict) -> dict:
    """Reduce a raw API payload to ``{green, known, top_status, platforms}``.

    ``green`` means every platform **built** (its binary is installable) — the
    relevant bar for an early-access channel. Each platform row also carries the
    advisory R CMD ``check`` result (``OK``/``NOTE``/``WARNING``/``ERROR``), which
    is surfaced but does **not** flip ``green`` (a built binary installs even with
    a check NOTE). ``known`` is False when the payload has no recognizable build
    status (treated as "unknown", not "green").
    """
    top = data.get("_status")
    binaries = data.get("_binaries") or []
    platforms: list[dict] = []
    green = True
    for b in binaries:
        build = str(b.get("status") or "unknown")
        build_ok = build.strip().lower() in _BUILD_OK
        if not build_ok:
            green = False
        platforms.append({
            "platform": b.get("os") or b.get("distro") or b.get("platform") or "?",
            "distro": b.get("distro") or "",
            "arch": b.get("arch") or "",
            "r": b.get("r") or b.get("rversion") or "",
            "status": build,            # build result
            "check": b.get("check"),    # advisory R CMD check result (may be None)
            "ok": build_ok,
        })
    if top is not None and str(top).strip().lower() not in _BUILD_OK:
        green = False
    known = bool(binaries) or top is not None
    return {"green": green and known, "known": known, "top_status": top, "platforms": platforms}


def verify(path: str = ".", universe: Optional[str] = None, *, timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Verify a package's R-universe early-access build status.

    Resolves the universe owner (git remote, or ``universe`` override) and the
    package name (DESCRIPTION), reads the R-universe API, and reports per-platform
    build status. Emits ``ok`` only when builds are confirmed green; every
    degradation (no DESCRIPTION, no remote, unregistered, offline, unknown) is a
    non-fatal ``warn``. Never raises.
    """
    root = Path(path)
    desc_path = root / "DESCRIPTION" if root.is_dir() else root
    desc = read_description(desc_path)
    if desc is None or not getattr(desc, "package", None):
        return _envelope("warn", [], [
            f"No parseable DESCRIPTION at {desc_path} — is this an R package? Try /rforge:detect.",
        ])
    pkg = desc.package

    owner = resolve_universe(path, universe)
    if not owner:
        return _envelope("warn", [], [
            "Could not determine your R-universe — no GitHub 'origin' remote found. "
            "Pass --universe <owner> (your GitHub user/org name).",
        ], pkg=pkg)

    reason, data = fetch_status(owner, pkg, timeout=timeout)

    if reason == "not_found":
        return _envelope("warn", [{"kind": "unregistered", "package": pkg, "owner": owner}], [
            f"'{pkg}' is not built on {owner}.r-universe.dev yet. One-time setup:",
            f"  1. Create a GitHub repo named '{owner}.r-universe.dev' (all lowercase).",
            f"  2. Add a packages.json listing this package's git repo.",
            "  3. Install the R-universe GitHub App (read/write commit status only).",
            "  Docs: https://docs.r-universe.dev/publish/set-up.html",
        ], owner=owner, pkg=pkg)

    if reason == "network" or data is None:
        return _envelope("warn", [], [
            f"Could not reach {owner}.r-universe.dev (offline or API error). "
            "Status unknown — this does not block the CRAN handoff.",
        ], owner=owner, pkg=pkg)

    summary = summarize(data)
    snippet = install_snippet(owner, pkg)
    findings = [{
        "kind": "build_status",
        "package": pkg,
        "owner": owner,
        "green": summary["green"],
        "top_status": summary["top_status"],
        "platforms": summary["platforms"],
        "install": snippet,
    }]
    if not summary["known"]:
        return _envelope("warn", findings, [
            f"Reached {owner}.r-universe.dev but found no recognizable build status for '{pkg}'. "
            "Verify the API field names against a live response.",
        ], owner=owner, pkg=pkg)
    if summary["green"]:
        return _envelope("ok", findings, [
            f"'{pkg}' is green on {owner}.r-universe.dev. Early-access install:",
            f"  {snippet}",
        ], owner=owner, pkg=pkg)
    red = [p["platform"] for p in summary["platforms"] if not p["ok"]]
    return _envelope("warn", findings, [
        f"'{pkg}' has failing R-universe builds"
        + (f" on: {', '.join(red)}" if red else "")
        + ". Fix before relying on the early-access channel (does not block CRAN).",
    ], owner=owner, pkg=pkg)


def format_text(env: dict) -> str:
    """Terminal-friendly rendering of a runiverse envelope."""
    icon = {"ok": "✅", "warn": "⚠️ ", "error": "❌"}.get(env["status"], "•")
    lines = [f"{icon} r-universe: {env['status']}"]
    for f in env.get("findings", []):
        if f.get("kind") == "build_status":
            lines.append(f"\n{f['package']} @ {f['owner']}.r-universe.dev "
                         f"(overall: {f.get('top_status')})")
            for p in f.get("platforms", []):
                mark = "✓" if p["ok"] else "✗"
                detail = " ".join(x for x in (p["platform"], p.get("distro"), p["arch"], p["r"]) if x)
                check = f", check {p['check']}" if p.get("check") else ""
                lines.append(f"  {mark} {detail} — build {p['status']}{check}")
    for m in env.get("messages", []):
        lines.append(f"\n💡 {m}" if not m.startswith("  ") else m)
    return "\n".join(lines)


def _main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="lib.runiverse", description=__doc__)
    ap.add_argument("--path", default=".")
    ap.add_argument("--universe", default=None,
                    help="override the auto-detected R-universe owner (your GitHub user/org)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ns = ap.parse_args(argv)
    env = verify(ns.path, ns.universe)
    print(json.dumps(env, indent=2) if ns.format == "json" else format_text(env))
    return 0 if env["status"] in ("ok", "warn") else 1


if __name__ == "__main__":
    sys.exit(_main())

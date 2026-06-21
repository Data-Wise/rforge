"""R-hub v2 dispatch + pre-flight (extracted from lib.rcmd).

Internal module (no docs/reference/ page, like ``formatters``): houses the
R-hub platform tables, the Python-side pre-flight gate, and ``_run_rhub``.
``lib.rcmd.run`` dispatches ``kind="rhub"`` here via a lazy import; ``_run_rhub``
in turn lazily imports the envelope helpers it needs from ``lib.rcmd`` to keep
the module graph acyclic (rcmd→rhub only inside ``run``; rhub→rcmd only inside
``_run_rhub``).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from lib.rsnippets import r_snippet

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

# Authoritative R-hub v2 platform tokens — the full `rhub::rhub_platforms()$name`
# set (reconciled live against rhub 2.x on 2026-06-21; superset of
# _RHUB_PRESETS values). Regenerate when rhub adds platforms:
#   Rscript -e 'cat(paste(sort(rhub::rhub_platforms()$name), collapse="\n"))'
# Validation only rejects tokens NOT in this set (a typo / injection), so the
# list must stay complete or legitimate platforms get wrongly rejected.
ALLOWED_RHUB_PLATFORMS = frozenset({
    # containers / VMs
    "linux", "windows", "macos", "macos-arm64", "atlas",
    "ubuntu-clang", "ubuntu-gcc12", "ubuntu-next", "ubuntu-release",
    # sanitizers / instrumented
    "clang-asan", "gcc-asan", "clang-ubsan", "valgrind", "m1-san", "rchk",
    # compilers
    "clang16", "clang17", "clang18", "clang19", "clang20", "clang21", "clang22",
    "gcc13", "gcc14", "gcc15", "gcc16", "intel",
    # special flavours
    "c23", "donttest", "nosuggests", "lto", "mkl", "nold", "noremap", "vnu",
})


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


def _run_rhub(path: str, pkg: dict, *, platforms: list | None = None,
              preset: str | None = None, rc_mode: bool = False) -> dict:
    """Dispatch ``kind="rhub"``: resolve platforms, pre-flight, then dispatch.

    Pre-flight runs entirely in Python before any R call. Error findings block
    dispatch (returned as an error envelope); advisory findings ride along in the
    returned envelope's ``findings`` key and never short-circuit dispatch.
    """
    # Envelope helpers live in lib.rcmd; import lazily (call-time) to keep the
    # module graph acyclic and so test monkeypatches of rcmd._invoke_r / normalize
    # are picked up at call time.
    from lib.rcmd import (_parse_json, _invoke_r, console_fallback, normalize,
                          INSTALL_HINT, OPTIONAL_ENGINES)

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

    bad = [p for p in platforms if p not in ALLOWED_RHUB_PLATFORMS]
    if bad:
        return {"kind": "rhub", "status": "error", "engine_missing": [],
                "messages": [f"Unknown platform(s): {', '.join(bad)}. "
                             f"Valid: {', '.join(sorted(ALLOWED_RHUB_PLATFORMS))}"]}

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
    stdout, code = _invoke_r(snippet, timeout=120)
    raw = _parse_json(stdout)
    if raw is None:
        raw = console_fallback("rhub", stdout)
    if code == 124 or raw.get("timed_out"):
        raw = {"messages": ["Rscript timed out — the operation took too long "
                            "(quick path bounded; long kinds are unbounded)."]}
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

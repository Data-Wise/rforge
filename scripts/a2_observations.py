#!/usr/bin/env python3
"""Produce the six candidate-bound A2 acceptance observations and their index.

One run writes every observation record plus `index.json`, all stamped with this run's ID and the candidate
SHA, so `verify_a2_aggregate.py` can bind them to a single downloaded producer run. CI computes what it can
(full gates, a real live-site smoke, package triage freshness, rendered-page inspection, requirement mapping);
the adversarial review is a recorded judgment supplied as an input and is stamped, not proven, by this run.

    python3 scripts/a2_observations.py --output DIR --run-id ID --candidate-sha SHA \
        --review-record review.json --workdir DIR
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from a2_gate_record import produce as produce_gates  # noqa: E402
from verify_a2_release import (VerificationError, validate_full_gates, validate_package_triage,  # noqa: E402
                               validate_requirements, validate_review)

# A real deployed pkgdown site with a supported configuration (release mode, no template, one sitemap request).
SUPPORTED_SITE = {"name": "cranlogs", "repo": "https://github.com/r-hub/cranlogs", "url": "https://r-hub.github.io/cranlogs/"}
# Real packages whose sites A2 marks unsupported (development mode, .qmd articles): recorded honestly as incomplete.
LIMIT_SITES = (
    {"name": "medfit", "repo": "https://github.com/Data-Wise/medfit", "url": "https://data-wise.github.io/medfit/"},
    {"name": "probmed", "repo": "https://github.com/Data-Wise/probmed", "url": "https://data-wise.github.io/probmed/"},
)
RENDERED_PAGES = {
    "guides/docs-audit": ("--site", "--run-examples", "unverified", "sandbox", "--fail-on error", "INCOMPLETE"),
    "tutorials/fix-a-docs-check-finding": ("--site", "--run-examples", "INCOMPLETE", "figure"),
    "REFCARD": ("--site", "--run-examples"),
    "command-cards": ("--site", "--run-examples"),
    "commands": ("--site", "--run-examples"),
    "reference/docaudit": ("examples", "site"),
    "quickstart": ("docs",),
}
RAW_LEAKS = ("```", ":::", "!!! ", "{{", "<?claude")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_record(output: Path, kind: str, status: str, candidate_sha: str, run_id: str, facts: dict) -> dict:
    """Write one observation record and return its index entry."""
    path = output / f"{kind}.json"
    path.write_text(json.dumps({"candidate_sha": candidate_sha, "kind": kind, "status": status,
                                "producer_run_id": run_id, "facts": facts}, indent=2) + "\n")
    return {"candidate_sha": candidate_sha, "status": status,
            "provenance": {"path": path.name, "sha256": sha256_bytes(path.read_bytes()), "run_id": run_id}}


def _status(check: Callable[[], None]) -> str:
    try:
        check()
        return "passed"
    except (VerificationError, KeyError, TypeError, ValueError):
        return "failed"


def observe_full_gates(root: Path = ROOT, runner: Optional[Callable] = None) -> tuple:
    facts = produce_gates(root, runner=runner)
    return facts, _status(lambda: validate_full_gates(facts, facts["source_commit"]))


def _clone(repo: str, dest: Path) -> str:
    subprocess.run(["git", "clone", "-q", repo, str(dest)], check=True, capture_output=True, timeout=300)
    return subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()


def counting_audit(path: Path, url: str, ref: str) -> dict:
    """Run the site audit in-process and count real HTTP requests made through the site opener."""
    from lib import _docsite, docaudit
    original, counter = _docsite.request.build_opener, {"requests": 0}

    def build(*handlers):
        opener = original(*handlers)
        real_open = opener.open

        def counted(*args, **kwargs):
            counter["requests"] += 1
            return real_open(*args, **kwargs)
        opener.open = counted
        return opener
    _docsite.request.build_opener = build
    try:
        report = docaudit.audit(path, site=url, ref=ref)
    finally:
        _docsite.request.build_opener = original
    report = json.loads(json.dumps(report, default=str))
    return {"stage": (report.get("stages") or {}).get("site") or {}, "requests": counter["requests"]}


def observe_live_smoke(workdir: Path, audit: Optional[Callable] = None, clone: Optional[Callable] = None,
                       supported: dict = SUPPORTED_SITE, limits: tuple = LIMIT_SITES) -> tuple:
    audit, clone = audit or counting_audit, clone or _clone

    def run(site: dict) -> dict:
        dest = workdir / site["name"]
        sha = clone(site["repo"], dest)
        branch = subprocess.run(["git", "-C", str(dest), "branch", "--show-current"], capture_output=True, text=True).stdout.strip() or "HEAD"
        result = audit(dest, site["url"], branch)
        stage = result["stage"]
        return {"name": site["name"], "url": site["url"], "source_ref": sha, "requests": result["requests"],
                "state": stage.get("state"), "checked": (stage.get("counts") or {}).get("checked", 0),
                "reasons": list(stage.get("reasons") or [])}
    primary = run(supported)
    unsupported = [run(site) for site in limits]
    facts = {"url": primary["url"], "source_ref": primary["source_ref"], "requests": primary["requests"], "checked": primary["checked"],
             "supported_site": primary, "unsupported_real_runs": unsupported}
    ok = (primary["state"] == "complete" and primary["requests"] > 0 and primary["checked"] > 0
          and all(run_["state"] == "incomplete" and run_["reasons"] for run_ in unsupported))
    return facts, "passed" if ok else "failed"


def observe_package_triage(reviewed: dict, fresh: dict) -> tuple:
    """The reviewed record stands only while a fresh producer run on the pinned clones finds the same facts."""
    facts = json.loads(json.dumps(reviewed["facts"]))
    drift = []
    for name, record in facts["packages"].items():
        now = fresh["packages"].get(name, {})
        for key in ("state", "counts", "source_sha256"):
            if record.get(key) != now.get(key):
                drift.append(f"{name}.{key}")
        if len(record.get("findings", [])) != len(now.get("findings", [])):
            drift.append(f"{name}.findings")
        record["commit"] = now.get("commit", record["commit"])
    if drift:
        print("triage drift: " + ", ".join(drift), file=sys.stderr)
    return facts, _status(lambda: (validate_package_triage(facts), _require_no_drift(drift)))


def _require_no_drift(drift: list) -> None:
    if drift:
        raise VerificationError("reviewed triage record is stale: " + ", ".join(drift))


def inspect_pages(site: Path) -> list:
    """Machine inspection of the rendered article HTML: expected terms present, no raw markup, no broken link."""
    pages = []
    for page, terms in RENDERED_PAGES.items():
        index = site / page / "index.html"
        ok = index.is_file()
        article = ""
        if ok:
            found = re.search(r"<article.*?</article>", index.read_text(), re.S)
            article = found.group(0) if found else ""
        text = html.unescape(re.sub(r"<[^>]+>", " ", article))
        broken = []
        for link in re.findall(r'href="([^"#]+)', article):
            if link.startswith(("http", "mailto", "/")):
                continue
            target = (index.parent / link).resolve()
            if not (target.exists() or (target / "index.html").exists()):
                broken.append(link)
        inspected = bool(article) and all(t in text for t in terms) and not any(x in text for x in RAW_LEAKS) and not broken
        pages.append({"page": page, "inspected": bool(inspected), "sha256": sha256_bytes(article.encode()),
                      "missing_terms": [t for t in terms if t not in text], "broken_links": broken[:5]})
    return pages


def observe_rendered(workdir: Path, build: Optional[Callable] = None) -> tuple:
    site = workdir / "site"
    (build or _mkdocs_build)(site)
    pages = inspect_pages(site)
    return {"pages": pages, "method": "automated: expected terms, raw-markup absence, internal links"}, \
        "passed" if all(p["inspected"] for p in pages) else "failed"


def _mkdocs_build(site: Path) -> None:
    subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict", "-q", "-d", str(site)], cwd=ROOT, check=True, capture_output=True)


def observe_mapping(root: Path = ROOT) -> tuple:
    ledger = json.loads((root / "tests/a2/requirements.json").read_text())
    manifest = json.loads((root / "tests/a2/required.json").read_text())
    spec = (root / "SPEC-docs-check-a2-2026-10-12.md").read_text()
    inventory = (root / "ACCEPTANCE-docs-check-a2-2026-10-12.md").read_text()
    facts = {"review": ledger.get("review"), "requirements": len(ledger.get("requirements", [])), "unmapped": 0}
    try:
        validate_requirements(ledger, manifest, spec, inventory)
    except VerificationError as exc:
        facts.update(unmapped=1, error=str(exc))
        return facts, "failed"
    return facts, "passed"


def observe_review(record: dict, candidate_sha: str) -> tuple:
    facts = dict(record)
    facts["attested"] = True
    return facts, _status(lambda: validate_review(facts, candidate_sha))


def pin_clones(workdir: Path, pins: dict, clone: Optional[Callable] = None) -> dict:
    """Clone each triage repository at its pinned commit; idempotent so deps can be installed between the two steps."""
    clone = clone or _clone
    clones = {}
    for name, repo in pins["repos"].items():
        dest = workdir / "triage-src" / name
        if not dest.exists():
            clone(repo, dest)
            subprocess.run(["git", "-C", str(dest), "checkout", "-q", pins["commits"][name]], check=True, capture_output=True)
        head = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
        if head != pins["commits"][name]:
            raise VerificationError(f"{name} is at {head}, not the pinned {pins['commits'][name]}")
        clones[name] = dest
    return clones


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--candidate-sha", default="")
    parser.add_argument("--review-record", type=Path)
    parser.add_argument("--clone-triage-only", action="store_true", help="clone the pinned triage sources and stop")
    parser.add_argument("--triage-record", type=Path, default=ROOT / "tests/a2/evidence/package-triage-2026-10-24.json")
    parser.add_argument("--triage-pins", type=Path, default=ROOT / "tests/a2/evidence/triage-pins.json")
    args = parser.parse_args(argv)
    args.workdir.mkdir(parents=True, exist_ok=True)
    clones = pin_clones(args.workdir, json.loads(args.triage_pins.read_text()))
    if args.clone_triage_only:
        print("\n".join(str(path) for path in clones.values()))
        return 0
    if not (args.output and args.run_id.isdigit() and args.candidate_sha and args.review_record):
        parser.error("--output, --run-id (numeric), --candidate-sha and --review-record are required to produce observations")
    args.output.mkdir(parents=True, exist_ok=True)
    from a2_package_triage import produce as produce_triage
    observations = {
        "full_gates": observe_full_gates(),
        "live_smoke": observe_live_smoke(args.workdir),
        "package_triage": observe_package_triage(json.loads(args.triage_record.read_text()), produce_triage(clones)),
        "rendered_review": observe_rendered(args.workdir),
        "adversarial_review": observe_review(json.loads(args.review_record.read_text()), args.candidate_sha),
        "requirement_mapping": observe_mapping(),
    }
    index = {kind: write_record(args.output, kind, status, args.candidate_sha, args.run_id, facts)
             for kind, (facts, status) in observations.items()}
    (args.output / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    failed = [kind for kind, entry in index.items() if entry["status"] != "passed"]
    print(f"observations: {len(index) - len(failed)}/{len(index)} passed" + (f"; failed: {failed}" if failed else ""), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

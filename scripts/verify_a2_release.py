"""Fail-closed A2 release evidence verifier; general pytest success is insufficient."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


class VerificationError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise VerificationError(reason)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spec_obligations(text):
    """Include every paragraph and each table row, independently of inventory IDs."""
    obligations=[];anchor="root";ordinal=0
    for block in re.split(r"\n\s*\n",text.strip()):
        if block.startswith("#"):
            heading=block.splitlines()[0].lstrip("# ")
            anchor=re.sub(r"[^a-z0-9 -]","",heading.lower()).replace(" ","-")
            ordinal=0
        rows=block.splitlines() if block.startswith("|") else [block]
        for row in rows:
            if re.fullmatch(r"[| :\-]+",row):continue
            ordinal+=1
            obligations.append({"id":anchor+":"+str(ordinal),"anchor":anchor,"ordinal":ordinal,"text":row,"sha256":hashlib.sha256(row.encode()).hexdigest()})
    return obligations


def validate_requirements(ledger, manifest, spec_text):
    require(ledger.get("review")=="complete","requirement ledger review pending")
    source=spec_obligations(spec_text)
    entries=ledger.get("requirements",[])
    require(len(entries)==len(source),"missing/extra approved spec obligation")
    groups={g['id'] for g in manifest.get('groups',[])}
    for expected,actual in zip(source,entries):
        require(all(actual.get(k)==v for k,v in expected.items()),"altered/unmapped paragraph or table row")
        require(actual.get("review")=="complete" and bool(actual.get("inventory_ids")),"unmapped/unreviewed spec requirement")
        require(set(actual["inventory_ids"])<=groups,"requirement refers to removed inventory group")
    require(set().union(*(set(r['inventory_ids']) for r in entries))==groups,"unmapped inventory group")


def validate_run(manifest, evidence, *, candidate_sha, lock_hash, manifest_hash):
    require(manifest.get("status") == "ready", "required manifest is not ready")
    groups = manifest.get("groups", [])
    require(bool(groups), "empty required manifest")
    required = [node for group in groups for node in group.get("nodes", [])]
    require(all(group.get("status") == "ready" and group.get("nodes") for group in groups), "pending or empty required group")
    require(len(required) == len(set(required)), "duplicate required nodes")
    require(evidence.get("candidate_sha") == candidate_sha, "wrong candidate SHA")
    require(evidence.get("lock_hash") == lock_hash and evidence.get("manifest_hash") == manifest_hash, "wrong manifest/lock hashes")
    require(bool(evidence.get("run_id")), "missing run identity")
    require(evidence.get("collection_run_id") == evidence["run_id"], "collection/outcome run mismatch")
    collected = evidence.get("collected", [])
    require(len(collected) == len(set(collected)), "duplicate collected IDs")
    require(set(required) <= set(collected), "required nodes not collected")
    outcomes = evidence.get("outcomes", {})
    require(all(outcomes.get(node) == "passed" for node in required), "missing, failed, skipped, xfailed, xpassed or deselected required outcome")
    require(evidence.get("python", "").startswith("3.12."), "Python 3.12 required")
    executions = evidence.get("fixture_executions", [])
    require(bool(executions), "no independent fixture execution evidence")
    r_checked = http_checked = 0
    for fixture in executions:
        require(fixture.get("expected_assertion_ids") == fixture.get("observed_assertion_ids"), "fixture assertion identity/count disagreement")
        require(fixture.get("expected_routes") == fixture.get("observed_routes"), "fixture route count disagreement")
        require(fixture.get("actual_findings") == fixture.get("expected_findings"), "unexpected or missed fixture finding")
        require(bool(fixture.get("sentinel")), "missing real execution sentinel")
        r_checked += len(fixture.get("observed_assertion_ids", [])) if fixture.get("engine") == "R" else 0
        http_checked += len(fixture.get("observed_routes", [])) if fixture.get("engine") == "HTTP" else 0
    require(r_checked > 0 and http_checked > 0, "zero independently verified R/HTTP execution")
    require(evidence.get("reported_r_checked") == r_checked and evidence.get("reported_http_checked") == http_checked, "inflated/self-reported execution counts")
    return {"verified":True,"required_nodes":len(required),"R_checked":r_checked,"HTTP_checked":http_checked}


def validate_aggregate(platforms, observations, *, candidate_sha):
    require({p.get("platform") for p in platforms} == {"ubuntu-24.04", "macos-14"}, "both actual release platforms required")
    require(len(platforms) == 2, "duplicate platform artifacts")
    require(all(p.get("candidate_sha") == candidate_sha and p.get("uploaded") and p.get("retrieved") and p.get("verified") for p in platforms), "missing/failed/stale actual artifact")
    for name in ("live_smoke","package_triage","full_gates","rendered_review","adversarial_review","requirement_mapping"):
        item = observations.get(name, {})
        require(item.get("candidate_sha") == candidate_sha and item.get("status") == "passed" and bool(item.get("provenance")), f"actual {name} evidence missing or failed")
    return {"verified":True,"platforms":2}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=Path("tests/a2/required.json"))
    ap.add_argument("--lock", type=Path, default=Path("tests/a2/fixture-lock.json"))
    ap.add_argument("--requirements", type=Path, default=Path("tests/a2/requirements.json"))
    ap.add_argument("--spec", type=Path, default=Path("SPEC-docs-check-a2-2026-10-12.md"))
    ap.add_argument("--expected", type=Path, default=Path("tests/a2/expected-findings.json"))
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--candidate-sha", required=True)
    args = ap.parse_args(argv)
    try:
        ledger = json.loads(args.requirements.read_text())
        manifest = json.loads(args.manifest.read_text())
        require(digest(args.spec)==ledger.get("spec_sha256")==manifest.get("spec_sha256"),"approved spec hash mismatch")
        validate_requirements(ledger,manifest,args.spec.read_text())
        evidence = json.loads(args.evidence.read_text())
        result = validate_run(manifest, evidence, candidate_sha=args.candidate_sha, lock_hash=digest(args.lock), manifest_hash=digest(args.manifest))
        expected=json.loads(args.expected.read_text())
        require(expected.get("status")=="ready" and bool(expected.get("fixtures")),"expected fixture manifest pending")
        require(evidence.get("expected_findings_hash")==digest(args.expected),"wrong expected-findings hash")
        executions=evidence.get("fixture_executions",[])
        require({f.get("fixture") for f in executions}==set(expected["fixtures"]),"missing/extra required fixture execution")
        require(len(executions)==len(expected["fixtures"]),"duplicate fixture execution")
        for execution in executions:
            oracle=expected["fixtures"][execution["fixture"]]
            require(execution.get("actual_findings")==oracle["findings"],"committed finding oracle mismatch")
            require(execution.get("observed_assertion_ids",[])==oracle.get("assertion_ids",[]),"committed assertion oracle mismatch")
            require(execution.get("observed_routes",[])==oracle.get("routes",[]),"committed route oracle mismatch")
            require(bool(re.fullmatch(r"[a-f0-9]{64}",execution.get("source_hash",""))),"missing fixture source hash")
        lock = json.loads(args.lock.read_text())
        require(evidence.get("platform") in lock["platforms"],"unsupported release platform")
        require(evidence.get("R") == lock["R"] and evidence.get("R_packages") == lock["R_packages"], "runtime lock mismatch")
        print(json.dumps(result))
        return 0
    except (VerificationError,OSError,ValueError,KeyError) as exc:
        print(json.dumps({"verified":False,"reason":str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

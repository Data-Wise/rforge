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


def validate_requirements(ledger, manifest, spec_text, inventory_text=None):
    require(ledger.get("review")=="complete","requirement ledger review pending")
    source=spec_obligations(spec_text)
    entries=ledger.get("requirements",[])
    require(len(entries)==len(source),"missing/extra approved spec obligation")
    groups={g['id'] for g in manifest.get('groups',[])}
    if inventory_text is not None:
        inventory_ids=re.findall(r'^\| ([A-Z]+[0-9]+) /',inventory_text,re.M)
        require(bool(inventory_ids) and len(inventory_ids)==len(set(inventory_ids)), 'empty/duplicate acceptance inventory')
        require(groups==set(inventory_ids), 'removed/extra acceptance inventory group')
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


def validate_observation(name, item, *, candidate_sha, evidence_root):
    require(isinstance(item, dict), "observation object required")
    require(item.get("candidate_sha") == candidate_sha and item.get("status") == "passed", f"actual {name} evidence missing or failed")
    provenance = item.get("provenance")
    require(isinstance(provenance, dict), "artifact provenance required")
    require(evidence_root is not None, "retrieved observation artifacts required")
    root = Path(evidence_root).resolve()
    relative = provenance.get("path", "")
    require(isinstance(relative, str) and bool(relative) and not Path(relative).is_absolute(), "relative evidence artifact path required")
    path = (root / relative).resolve()
    require(path.is_relative_to(root) and path.is_file(), "missing or escaping observation artifact")
    require(digest(path) == provenance.get("sha256"), "observation artifact hash mismatch")
    record = json.loads(path.read_text())
    require(isinstance(record, dict), "artifact record object required")
    require(record.get("candidate_sha") == candidate_sha and record.get("kind") == name and record.get("status") == "passed", "artifact identity/status mismatch")
    require(record.get("producer_run_id") == provenance.get("run_id") and str(record.get("producer_run_id", "")).isdigit(), "artifact producer run mismatch")
    facts = record.get("facts", {})
    require(isinstance(facts, dict), "observation facts required")
    if name == "live_smoke":
        require(bool(facts.get("url")) and bool(facts.get("source_ref")) and facts.get("requests", 0) > 0 and facts.get("checked", 0) > 0, "live execution missing")
    elif name == "package_triage":
        require(set(facts.get("packages", {})) >= {"medfit", "probmed", "medrobust"} and all(v.get("reviewed") is True and bool(v.get("disposition")) for v in facts["packages"].values()), "package triage incomplete")
    elif name == "full_gates":
        require(facts.get("pytest_passed", 0) > 0 and facts.get("test_all_passed") == 47 and all(facts.get(k) is True for k in ("version_sync", "reference_sync", "command_sync", "mkdocs_strict")), "full gates incomplete")
    elif name == "rendered_review":
        require(bool(facts.get("pages")) and all(v.get("inspected") is True and re.fullmatch(r"[a-f0-9]{64}", v.get("sha256", "")) for v in facts["pages"]), "render inspection incomplete")
    elif name == "adversarial_review":
        require(bool(facts.get("job_id")) and facts.get("unresolved_findings") == 0 and facts.get("coverage_reviewed") is True, "review unresolved or incomplete")
    elif name == "requirement_mapping":
        require(facts.get("review") == "complete" and facts.get("unmapped") == 0 and facts.get("requirements", 0) > 0, "mapping incomplete")


def validate_aggregate(platforms, observations, *, candidate_sha, evidence_root=None):
    require({p.get("platform") for p in platforms} == {"ubuntu-24.04", "macos-14"}, "both actual release platforms required")
    require(len(platforms) == 2, "duplicate platform artifacts")
    require(all(p.get("candidate_sha") == candidate_sha and p.get("uploaded") and p.get("retrieved") and p.get("verified") for p in platforms), "missing/failed/stale actual artifact")
    for name in ("live_smoke","package_triage","full_gates","rendered_review","adversarial_review","requirement_mapping"):
        item = observations.get(name, {})
        validate_observation(name, item, candidate_sha=candidate_sha, evidence_root=evidence_root)
    return {"verified":True,"platforms":2}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, default=Path("tests/a2/required.json"))
    ap.add_argument("--lock", type=Path, default=Path("tests/a2/fixture-lock.json"))
    ap.add_argument("--requirements", type=Path, default=Path("tests/a2/requirements.json"))
    ap.add_argument("--spec", type=Path, default=Path("SPEC-docs-check-a2-2026-10-12.md"))
    ap.add_argument("--inventory", type=Path, default=Path("ACCEPTANCE-docs-check-a2-2026-10-12.md"))
    ap.add_argument("--expected", type=Path, default=Path("tests/a2/expected-findings.json"))
    ap.add_argument("--evidence", type=Path, required=True)
    ap.add_argument("--candidate-sha", required=True)
    args = ap.parse_args(argv)
    try:
        ledger = json.loads(args.requirements.read_text())
        manifest = json.loads(args.manifest.read_text())
        require(digest(args.spec)==ledger.get("spec_sha256")==manifest.get("spec_sha256"),"approved spec hash mismatch")
        validate_requirements(ledger,manifest,args.spec.read_text(),args.inventory.read_text())
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

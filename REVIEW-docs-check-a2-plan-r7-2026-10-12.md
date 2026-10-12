# Claude adversarial review — A2 revision 7 implementation plan

Validation update (2026-10-12): findings checked against owning sources; PLAN,
ACCEPTANCE and TASKS revised as planning revision 2. Approved SPEC revision 7
is unchanged. Original Claude findings below are retained verbatim.

## Owning-source validation and disposition

1. **Confirmed ambiguity, not unavoidable circularity.** The old evidence-ordering
   paragraph already prohibited self-dependence, but mandatory row oracles still
   conflated validator nodes with later actual observations. Required evidence
   in SPEC requires normative requirements to map to nodes; removing F01/F02/H03/V06
   entirely would weaken that contract. Retain mandatory validator nodes on both
   platforms, with controlled positive/negative inputs, and separately mandatory
   aggregate verification of actual uploads, smoke, full gates and review.
2. **Partially confirmed.** Independent counts and mapping provenance were
   underspecified. However C05 already covered detailed-on/off states/counts,
   V07 Windows unavailable, G03 earliest heartbeat/global event, and N01 every
   normative numeric table row. These were not absent contracts. Make their
   cases explicit; T01/T20 now require a reviewed spec paragraph/table-row ledger
   independent of inventory IDs, fixture assertion/route oracles and same-run
   outcome reconciliation. No new IDs or normative edits to the approved spec.
3. **Confirmed missing executable shape oracle.** Actual README inspection still
   matches SPEC's coverage table: medfit groups at 64/85/97/118 in R fences and
   181/225 in unlabeled fences; probmed source assertion at 130, setup at 10–19
   with fig.path/out.width, rendered assertion at 118; medrobust zero #> groups.
   New E11 locks these shapes and exact reasons/states/exits. medrobust is
   not-applicable, not incomplete: Claude's blanket exit-2 recommendation must
   not apply to it. Current live dogfood remains separately hashed and triaged.
4. **Confirmed checkpoint timing; lifecycle coverage strengthened.** T09 cannot
   claim two-platform results before T21. Local checkpoint now says local;
   T07/T08 include early minimal real-R probes and an actual TERM-ignoring child,
   with full native R replay/CLI and both-platform gates still required later.
   Python child tests were intended supplements, not replacements for R tests.
5. **Confirmed wording/order gaps, not a circular task DAG.** T16 release-host
   verification occurred before T21 provisioning; now local at T16 and repeated
   at T21. Add T17→T15 and T20→T19 for boundaries/docs. T22→T21 explicitly orders
   external evidence after platform runs; the smoke itself needs candidate SHA,
   not necessarily peer artifacts. T23 reconciles everything after both.
6. **Confirmed missing explicit case expansion.** Add completed warning plus
   incomplete other stage/package under none/warn/error (0/2/2), and text-mode
   timeout INCOMPLETE. lib/docaudit.py:1094–1101 already puts incomplete before
   severity; tests/test_docaudit_scope.py has incomplete/threshold/text contracts.
   This is future A2 aggregation coverage, not evidence of an existing exit bug.
7. **Confirmed implementation-plan gap.** V02/V08 compare required, collected and
   actually executed outcome IDs in the same run; reject deselection and forged
   counts. Release entry point requires R/deps regardless of developer skips.
8. **Partially confirmed wording gap.** S10/S11/S13 already described rejected
   redirect targets, missing sitemap incompleteness and limited claims. Add
   explicit fresh-invocation guidance, absent-source-url/missing-sitemap case,
   and absent-from-sitemap versus HTTP-404 message assertions.

Additional actual evidence: .github/workflows/ci.yml:115–159 runs Python
3.11/3.12/3.13 on ubuntu-latest with no R provisioning or macOS matrix. This does
not satisfy the specified A2 release gate. tests/test-all.sh has 47 declared run
checks; lib_s7runtime_r_ships at 489–502 returns success without R parsing when
Rscript is absent. lib/rcmd.py:399–421 uses subprocess.run/capture_output and an
optional timeout, not the proposed guardian protocol. Agent-engine guard text
and docaudit threshold/detailed tests were inspected; no behavior tests ran.

README content SHA256 snapshots:

- medfit/README.md: a7161fc9a18b01d3d3dde1747c2b6d9e0ebaac0e4ed452a9e63a16f0db5c50f0
- probmed/README.qmd: 3b058a67d0b5ab14f817d3307e77cf591c719c70910e0d20b84953b948c96d88
- probmed/README.md: 57ddc9060f7d4947e4d5161a3e6c8baab97f2801980531254f4f28c4e94e638d
- medrobust/README.md: 1cb8a79fe66a023c620ee65326df105e8d93ade07476162c966319ed80fd89f0

Planning verification: 87 unique proposed groups, 24 tasks, all dependency edges
acyclic and checklist synchronized; all contract anchors resolve; approved SPEC
SHA256 remains b202409f690b478fcb3fe6473afb4021930a1e271e8ae2a90ec0370bebe65b51.
No implementation, CI edits, executable tests, R execution or live network smoke.


Date: 2026-10-12. Verdict: needs-attention. Findings are unvalidated; no implementation or proposal revisions made.

Targets: SPEC, PLAN, ACCEPTANCE and TASKS docs-check-a2-2026-10-12.md. Focus: contract coverage, dependencies and release gates.

The SHA256 recorded in PLAN and ACCEPTANCE matches SPEC rev 7. The design has defects that could let release gates pass vacuously or never close: circular F01/F02/H03/V06 evidence ordering, a verifier that derives its counts from the system's own output, no expected-state gate for the real README coverage cases, and dependency edges that are circular or missing. Pending implementation evidence is intentional and is not counted as a defect. Findings come from reading the four planning documents only. I did not check code, CI or the earlier review.

## 1. high: F01/F02/H03/V06 evidence nodes are circular within the per-platform required set

Anchor: ACCEPTANCE-docs-check-a2-2026-10-12.md:213–262. Claude confidence: 0.7.

F01 runs the full suite, and F02, H03 and V06 need the other platform's artifact, a review record or the verifier result. V01/V02 require every inventory row to be a collected, passed node on each platform. Those prerequisites do not exist while the per-platform job is running. The only options are to exclude the rows, which contradicts 'every row mandatory', or to let them pass on stale or fixture evidence. No accepted test-all pass/skip count baseline is defined.

Suggested correction: Split the manifest into per-platform pytest nodes and an aggregate release-owner script check. State that F01, F02, H03 and V06 are not nodes in the per-platform verifier set. Define the expected test-all pass/skip baseline.

## 2. high: Verifier non-vacuity relies on implementer-authored mapping and self-reported counts

Anchor: TASKS-docs-check-a2-2026-10-12.md:28–30. Claude confidence: 0.65.

required.json is authored by the implementer against the implementer's own 85-row inventory. V01 only checks that this inventory is mapped, not that SPEC's MUSTs are. Candidate gaps I found with no explicit row: the `--detailed` hiding rule beyond C05, the Windows 'unavailable' state, the 5s heartbeat versus global deadline race, and the percent and thousands-separator verdict wording. V02's nonzero checked and HTTP counts come from the report the system under test emits, so over-reporting passes.

Suggested correction: Add anchored requirement IDs to the SPEC and have T20 diff them against required.json. Derive checked-assertion counts independently from fixture oracles and cross-check them against the CLI JSON.

## 3. high: No release gate asserts expected README states on the real packages

Anchor: ACCEPTANCE-docs-check-a2-2026-10-12.md:210–210. Claude confidence: 0.6.

H02 only records counts and triages false positives. SPEC lines 626-631 imply specific outcomes: probmed/README.qmd incomplete because of fig.path/out.width defaults, probmed/README.md rendered-unpaired, medfit's two unlabeled groups unverified, and medrobust not-applicable. A regression that reports probmed as complete or clean would still pass H02. No row asserts exit 2 under warn and error for these packages.

Suggested correction: Add hash-pinned or synthetic reproductions of each README shape. Assert the stage state is not complete and the exit is 2 under both thresholds.

## 4. medium: Guardian tests start with a Python child and a 'both platforms' checkpoint comes before any CI

Anchor: PLAN-docs-check-a2-2026-10-12.md:129–265. Claude confidence: 0.6.

The T09 checkpoint claims Linux and macOS pass, but T21 provisions the platform jobs much later, so only the developer host can be evidenced at that point. A fake child may not ignore SIGTERM, so the TERM to KILL branch is unproven until T14. R-side phase checkpointing is implemented in T13 after the guardian protocol is frozen in T07, so a mismatch means rework.

Suggested correction: Relabel the T09 checkpoint as local host only. Add an early real-R handshake and native-block spike in T07/T08. Add a TERM-ignoring child case to G06.

## 5. medium: Task dependency gaps and a circular edge

Anchor: TASKS-docs-check-a2-2026-10-12.md:23–31. Claude confidence: 0.55.

T16 verifies the installed layout 'on release hosts', but those hosts are provisioned in T21, which depends on T16. T22's live smoke needs the candidate SHA and artifacts from T21, but T22 does not depend on T21. T17's D03 oracle includes execution boundaries, but T17 does not depend on T15. T20 does not depend on T17, T18 or T19, so mapping completeness cannot be verified at T20.

Suggested correction: Add T17 depending on T15 and T22 depending on T21. Move the release-host check of D01 into T21. Make mapping completeness a T23 check or make T20 depend on T19.

## 6. medium: Missing mixed complete-warn plus incomplete-stage exit cases

Anchor: ACCEPTANCE-docs-check-a2-2026-10-12.md:52–160. Claude confidence: 0.5.

C04, R10 and S14 repeat the threshold matrix per stage. None covers a completed examples-output warn together with an incomplete stage elsewhere, for example site offline plus a stale numeric. That case must exit 2, not 1, under warn and error. R10 lists the partial envelope with none exiting 0 but not the text-mode final INCOMPLETE marker.

Suggested correction: Add a cross-product case parameterized over none, warn and error. Add a text-mode timeout partial-envelope case that checks the INCOMPLETE marker.

## 7. medium: Release-mode switch and deselected nodes are not tested

Anchor: SPEC-docs-check-a2-2026-10-12.md:493–535. Claude confidence: 0.5.

SPEC lets R-dependent tests skip in developer suites but not in required tests. The mechanism that distinguishes the two modes is unspecified and no row tests it. V02 checks collection separately from outcomes, but a run that used -k, --deselect or -m can omit a node from the results file while collect-only still lists it.

Suggested correction: Have the verifier compare collected IDs against the IDs in the same results file. Add rows for the release-mode switch and for deselected nodes.

## 8. low: Some site wording and consequence rules lack explicit oracles

Anchor: ACCEPTANCE-docs-check-a2-2026-10-12.md:66–90. Claude confidence: 0.45.

I found no explicit oracle for a missing sitemap with an absent source url: being incomplete rather than missing pages. I also found none for the 'absent from the sitemap, not an HTTP 404' phrasing, or for the redirect final-target and HTTP-to-HTTPS fresh-invocation guidance.

Suggested correction: Add wording and state assertions for these messages in S09 to S12.

## Coverage and uncertainty

{
  "files_examined": [
    "SPEC-docs-check-a2-2026-10-12.md",
    "PLAN-docs-check-a2-2026-10-12.md",
    "ACCEPTANCE-docs-check-a2-2026-10-12.md",
    "TASKS-docs-check-a2-2026-10-12.md"
  ],
  "files_skipped": [
    "REVIEW-docs-check-a2-r5-2026-10-12.md",
    "lib/docaudit.py (keyword count only)",
    "lib/rcmd.py",
    "tests/test_docaudit_scope.py",
    "tests/test_rcmd.py",
    ".github/workflows/ci.yml",
    "tests/_check_agent_engines.py",
    "agents/orchestrator.md",
    "archive/specs/SPEC-docs-check-content-audit-2026-10-11.md",
    "medfit, probmed and medrobust README files"
  ],
  "areas": [
    "normative contract coverage",
    "evidence circularity and vacuous passes",
    "task dependency ordering",
    "release gates and expanded nodes",
    "real R/process/HTTP coverage on both platforms",
    "skipped tests",
    "provenance and live evidence",
    "README source/coverage",
    "parent/guardian deadlines",
    "warn-level exits"
  ]
}

Uncertainty: medium. No owning-source validation completed. Recommended follow-up (not dispatched): {"profile":"deep","focus":["Diff each SPEC rev 7 MUST sentence against the 85 ACCEPTANCE rows","Check lib/docaudit.py exit and aggregation behavior against the SPEC","Check the .github/workflows/ci.yml baseline against the SPEC's claims"],"reason":"This pass read only the four planning documents. The claims about existing code, CI and the prior review are unverified, and the per-MUST traceability scan was manual."}

## Review provenance and usage

{
  "job_id": "495ee9e4-dd50-4b81-9374-6530c0af48f6",
  "requested_model": "sonnet",
  "effective_models": [
    "claude-sonnet-5-5"
  ],
  "review_profile": "standard",
  "effort": "medium",
  "budget": {
    "max_turns": 12,
    "finalize_at_turn": 9,
    "soft_budget_usd": 1,
    "max_budget_usd": 1,
    "timeout_ms": 240000
  },
  "total_tokens": 287328,
  "usage": {
    "input_tokens": 1161,
    "cache_creation_input_tokens": 58510,
    "cache_read_input_tokens": 217650,
    "output_tokens": 10007,
    "output_tokens_details": {
      "thinking_tokens": 163
    },
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": 0
    },
    "service_tier": "standard",
    "cache_creation": {
      "ephemeral_1h_input_tokens": 58510,
      "ephemeral_5m_input_tokens": 0
    },
    "inference_geo": "not_available",
    "iterations": [
      {
        "input_tokens": 4,
        "output_tokens": 62,
        "cache_read_input_tokens": 61973,
        "cache_creation_input_tokens": 5529,
        "cache_creation": {
          "ephemeral_5m_input_tokens": 0,
          "ephemeral_1h_input_tokens": 5529
        },
        "type": "message"
      },
      {
        "input_tokens": 1151,
        "output_tokens": 3472,
        "cache_read_input_tokens": 67502,
        "cache_creation_input_tokens": 0,
        "cache_creation": {
          "ephemeral_5m_input_tokens": 0,
          "ephemeral_1h_input_tokens": 0
        },
        "type": "message"
      }
    ],
    "speed": "standard",
    "fallback_credit": null
  },
  "model_usage": {
    "claude-sonnet-5-5": {
      "inputTokens": 1161,
      "outputTokens": 10007,
      "cacheReadInputTokens": 217650,
      "cacheCreationInputTokens": 58510,
      "webSearchRequests": 0,
      "costUSD": 0.358197,
      "contextWindow": 1000000,
      "maxOutputTokens": 128000,
      "thinkingTokens": 163,
      "canonicalModel": "claude-sonnet-5-5",
      "provider": "firstParty",
      "costBasis": "list"
    }
  },
  "total_cost_usd": 0.358197,
  "num_turns": 9,
  "duration_ms": 72784,
  "duration_api_ms": 72335,
  "evidence_lease": null,
  "evidence_lease_exhausted": false,
  "cost_budget_exhausted": false,
  "turn_limit_reached": false,
  "session_id": "591ec039-1629-40d8-a473-2f4dd21f5af8",
  "resume_hint": "claude --resume 591ec039-1629-40d8-a473-2f4dd21f5af8"
}

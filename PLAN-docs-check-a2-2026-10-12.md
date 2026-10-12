# Implementation plan — docs:check A2, approved revision 7

Date: 2026-10-12. Status: planning revision 2 after validated review; approved spec remains revision 7; implementation authorized 2026-10-12; in progress.
Baseline: local dev at 74824ac; one worktree; only untracked planning/review files.
This is observed local state, not a live remote/CI claim.
Approved specification: [SPEC-docs-check-a2-2026-10-12.md](SPEC-docs-check-a2-2026-10-12.md). SHA256: `b202409f690b478fcb3fe6473afb4021930a1e271e8ae2a90ec0370bebe65b51`.
Acceptance inventory: [ACCEPTANCE-docs-check-a2-2026-10-12.md](ACCEPTANCE-docs-check-a2-2026-10-12.md). Task list target: [TASKS-docs-check-a2-2026-10-12.md](TASKS-docs-check-a2-2026-10-12.md).
The repository's root-plan convention replaces the generic skill's tasks/plan.md
and tasks/todo.md locations. Neither existing plans nor implementation files are
replaced. Proposal approval authorizes this planning work only.

## Delivery shape and dependencies

Preserve A1 and deliver explicit stage reporting first, then a complete local
site CLI path, then supervised README replay, followed by command/agent/docs
integration and required release evidence. Keep `lib.docaudit` public; proposed
private modules are `lib/_docsite.py`, `lib/_docexamples.py` and
`lib/_docguardian.py`, with shipped `lib/r/docexamples.R`. Internal names may
change with the same contract; no new public module/dependency is planned.

T00 → T01 → T02 → T03–T06 (site) → T07–T14 (examples) → T15–T19 (integration)
→ T20–T23 (release acceptance/review). Exact per-task dependencies below permit
independent local work without authorizing delegated agents or new chats.
The guardian/process failures are exercised before full R integration, and
pinned routes are tested before the site path can claim supported coverage.

Do not create the worktree, ORCHESTRATE file, executable tests, required.json,
fixture lock, runner or CI job during planning. On later implementation
permission, carry every planning file into the feature worktree before changes.
Specs/plans/implementation then live there. No tasks are completed merely because
their design or proposed node IDs appear below.

## Verification policy

Each slice adds meaningful failing acceptance tests before its behavior, then
passes focused checks and existing A1 regressions. Keep product default behavior
usable throughout: unimplemented requested stages can only report unavailable,
never clean. Do not ship an incomplete intermediate implementation as A2.

Inventory rows define required test groups, not collected results. The future
manifest must expand every parameterized case to exact pytest node IDs on each
platform and map every normative requirement. Developer skips stay explicit;
release-required nodes cannot skip/xfail/xpass. Real process/R/HTTP fixtures
cannot be replaced by mocks; fake-child guardian tests supplement real native-R
tests. Evidence-validator nodes test controlled records and failure cases on both
platforms. Actual uploads, live smoke, dogfood, review and final-gate observations
are additional mandatory aggregate checks after the platform jobs; controlled
record success cannot satisfy these external obligations.

CI execution and publication are later external actions. A locally passing
suite cannot establish the Ubuntu/macOS release matrix or a live-site smoke.
Release preflight must fail until exact fixture versions are resolved and locked.
Live site-only smoke requires a human-supplied authorized URL; until then it stays
pending and no integration-smoke success is claimed.

Platform jobs verify their own completed reports before uploading artifacts. A
subsequent aggregate/release-owner check verifies both uploaded artifacts.
Evidence-reader tests consume prerequisite reports; they must not require their
own unfinished run, its future upload, or the other matrix job to be complete.
Full-suite and final-review evidence is reconciled after the candidate runs,
without recursively launching the full suite from a test within that suite.

## Task details

Sizes S/M refer to a focused slice, usually 1–5 edited files. Fixture generators
avoid committing large generated packages. If an implementation exceeds five
independent files or one focused session, split it under the same acceptance IDs
before proceeding; do not drop requirements to meet sizing.

### T00: Prepare the implementation worktree

Dependencies: None. Scope: S. Likely files: spec/plan/inventory/task documents plus both review records (six files).
Acceptance contracts: Worktree/baseline preservation; no product test required.

- [ ] After implementation authorization, verify live branch/worktree state; create or reuse a feature worktree based on current dev, copy all six current untracked planning/review documents there and record baseline SHA without losing them. No ORCHESTRATE workflow or automatic implementation today.
- [ ] Verification: Inspect worktree/branch and document hashes; stop if current dev drift changes the approved contract.

### T01: Establish the acceptance harness

Dependencies: 00. Scope: M. Likely files: tests/a2/conftest.py; tests/a2/helpers.py; tests/a2/fixture-lock.json; tests/a2/expected-findings.json; tests/a2/required.json.
Acceptance contracts: Worktree/baseline preservation; no product test required.

- [ ] Define fixture builders, runtime/platform preflight, expected-findings/requirement mapping and exact version lock. Initially unimplemented contracts remain pending, never green; no release invocation until the full inventory is realized. Use isolated fixture repos/libraries, not user package mutations.
- [ ] Verification: Review fixture identities and mapping; require dependency failures distinguish developer skips from release preflight failure.

### T02: Preserve A1 and expose optional-stage reporting

Dependencies: 01. Scope: M. Likely files: lib/docaudit.py; tests/a2/test_reporting.py; tests/test_docaudit_scope.py.
Acceptance contracts: C01, C02, C03, C04, C05, C06, C07.

- [ ] Implement C01–C07: default compatibility, new CLI misuse rules, stage envelope/coverage diagnostics, exits and aggregate missing engines. Requested unimplemented stage temporarily unavailable/incomplete, not a fabricated clean result.
- [ ] Verification: Run reporting tests and all existing docaudit tests; verify text/JSON subprocess outputs.

### T03: Resolve immutable deployment sources

Dependencies: 02. Scope: M. Likely files: lib/_docsite.py; tests/a2/test_site_refs.py.
Acceptance contracts: S01, S02, S03, S04.

- [ ] Implement S01–S04 with local git/ref/workflow/YAML provenance; no fetch and no ambiguous fallback. Explicit ref bypasses inference, never unsupported routes.
- [ ] Verification: Run reference-selection fixtures including immutable selected-ref tree versus dirty checkout.

### T04: Derive fixture-proven site routes

Dependencies: 03. Scope: M. Likely files: lib/_docsite.py; tests/a2/test_site_routes.py; tests/a2/route-cases.json; tests/a2/fixture-lock.json.
Acceptance contracts: S05, S06, S07, S08.

- [ ] Implement S05–S08: Rd/internal pages, all three article path rules, exclusions, collision detection and unsupported cfg/modes. Confirm actual pinned pkgdown output before accepting each mapping; if it disagrees, report blocked scope rather than silently revise approved spec.
- [ ] Verification: Run route fixtures and pinned real-R pkgdown build in temp fixtures on both release platforms.

### T05: Read bounded canonical sitemaps

Dependencies: 02. Scope: M. Likely files: lib/_docsite.py; tests/a2/test_site_http.py.
Acceptance contracts: S09, S10, S11, S12.

- [ ] Implement S09–S12: URL/origin/base boundaries, limited redirects, size/time bounds, namespaces/index/malformed/offline and foreign entries. Every unsupported response has a reason, never mass missing findings.
- [ ] Verification: Run bounded loopback HTTP server tests; public network remains unused.

### T06: Deliver the site CLI path

Dependencies: 03,04,05. Scope: M. Likely files: lib/docaudit.py; lib/_docsite.py; tests/a2/test_site_integration.py.
Acceptance contracts: S13, S14, S15.

- [ ] Implement S13–S15 end to end: selected-ref missing warn, unreleased/extra info, source attribution, clean/planted CLI gates, static-results retention and no unintended actions.
- [ ] Verification: Run CLI against local server + throwaway history, including checkout ahead and dirty additions.

### T07: Build the guardian handshake protocol

Dependencies: 01,02. Scope: M. Likely files: lib/_docguardian.py; tests/a2/test_guardian.py; tests/a2/helpers.py.
Acceptance contracts: G01, G02, G03.

- [ ] Implement G01–G03: independent guardian/direct R ownership, atomic sequenced handshake/phase arm, heartbeat and startup budget. Test controlled Python children and an early minimal real-R arm/ack probe; prove full replay integration in T13/T14. Protocol is provisional until the R probe passes.
- [ ] Verification: Run live child-process tests for lost/stale ack and rapid phases; process fixtures always clean their children.

### T08: Enforce deadlines and observed cleanup

Dependencies: 07. Scope: M. Likely files: lib/_docguardian.py; tests/a2/test_guardian.py.
Acceptance contracts: G04, G05, G06, G07, G08, G09, G10.

- [ ] Implement G04–G10: sole termination authority, deadline-first collision, bounded TERM/KILL/cleanup, parent loss, emergency guardian failure and honest detached/host-loss limits. Every event has identity/reason/time evidence.
- [ ] Verification: Run actual process trees locally, not mock kill calls alone; Include TERM-ignoring child and an early real-R native-block backstop before freezing the protocol; full CLI coverage remains R07/R08. Local host evidence only here; both-platform obligation closes at T21/T23.

### T09: Capture bounded text and durable checkpoints

Dependencies: 07,08. Scope: M. Likely files: lib/_docguardian.py; lib/_docexamples.py; tests/a2/test_stdio.py.
Acceptance contracts: I01, I02, I03, I04, I05.

- [ ] Implement I01–I05: stdout/stderr files, textual payload threshold and retention, guardian detection after parent loss, atomic checkpoint/marker retention and bounded final report handling.
- [ ] Verification: Run >64KiB native/child output and shared-threshold/mirror/overshoot cases with actual processes.

### T10: Select README sources and extract chunks

Dependencies: 02. Scope: M. Likely files: lib/_docexamples.py; tests/a2/test_readme.py; tests/a2/readme-cases.json.
Acceptance contracts: E01, E02, E03, E04.

- [ ] Implement E01–E04: supported fences/line spans, source choice, rendered-unpaired counts, ambiguity, literal-output discrimination and located skip markers. No A1 region reuse as execution selector.
- [ ] Verification: Run parser/source cases without starting R; ensure unsupported rendered/output surfaces stay unverified.

### T11: Resolve literal options and preflight coverage

Dependencies: 10. Scope: M. Likely files: lib/_docexamples.py; tests/a2/test_readme.py; tests/a2/readme-cases.json.
Acceptance contracts: E05, E06, E07, E08, E09, E10, E11.

- [ ] Implement E05–E11 including locked actual-README shape/state/exit regressions: option/default precedence, supported visibility subset, unsupported preflight, token installation filter, coverage partition and no-eligible/no-setup behavior.
- [ ] Verification: Run every option/skip case, hidden/no-output and one-checked/many-excluded counts; dependency absence does not prevent discovery.

### T12: Compare documented assertion output

Dependencies: 10,11. Scope: M. Likely files: lib/_docexamples.py; tests/a2/test_comparison.py; tests/a2/comparison-cases.json.
Acceptance contracts: N01, N02, N03, N04, N05.

- [ ] Implement N01–N05: decimal boundary table, labeled inequalities, ordered association, separate conditions and stochastic uncertainty. Keep warn-only semantics and distinguish completed mismatch from incomplete alignment.
- [ ] Verification: Run every exact normative table row and adversarial token-reuse/label/shape cases.

### T13: Replay a working-tree package in real R

Dependencies: 07,08,09,10,11,12. Scope: M. Likely files: lib/r/docexamples.R; lib/_docexamples.py; tests/a2/test_examples_r.py; tests/a2/helpers.py.
Acceptance contracts: R01, R02, R03, R04, R05, R06.

- [ ] Implement R01–R06 with pkgload/evaluate, hidden setup, fresh ordered sessions, installed-copy decoy, separate channels, dependencies and one upstream failure. Establish nonzero clean/planted execution under locked runtimes.
- [ ] Verification: Run real-R fixture sessions with isolated libraries and temp cwd; no edits to medfit/probmed/medrobust.

### T14: Deliver example CLI budgets and partial results

Dependencies: 13. Scope: M. Likely files: lib/docaudit.py; lib/_docexamples.py; tests/a2/test_examples_cli.py; commands/docs/check.md.
Acceptance contracts: R07, R08, R09, R10, R11, R12.

- [ ] Implement R07–R12: real blocked native load/chunk, file/global budget, sequential eco counts, atomic partial report and wrapper lifetime recommendation. Do not reuse _invoke_r unchanged or guess host timeout support.
- [ ] Verification: Run real-R subprocess CLI cases; test actual configured defaults plus shortened fixture-budget cases, clock-state unit tests alone insufficient.

### T15: Reconcile orchestrator boundaries

Dependencies: 06,14. Scope: M. Likely files: agents/orchestrator.md; tests/_check_agent_engines.py; tests/a2/test_agent.py.
Acceptance contracts: A01, A02, A03, A04.

- [ ] Implement A01–A04: static default, explicit human site-only permission, ref rule, imported URL rejection and recommend-only combined/examples. Recipe parsing uses stubs; manually inspect prose because regexes cannot prove authorization.
- [ ] Verification: Run guard/recipe behavioral fixtures and existing agent-engine gate with no real R/public network.

### T16: Verify the shipped runtime surface

Dependencies: 13,14. Scope: M. Likely files: tests/test-all.sh; tests/a2/test_shipping.py; lib/r/docexamples.R; package.json (only if packing evidence requires it).
Acceptance contracts: D01, D02.

- [ ] Implement D01–D02: packed/installed layout loads shipped R, parse gate, private modules only and no mandatory dependency. lib/ already ships; change files list only if concrete packaging evidence requires it; harness remains dev-only.
- [ ] Verification: Inspect package archive contents and run installed-layout smoke/parse locally; repeat on both release hosts in T21; do not bump version.

### T17: Update command and generated reference contracts

Dependencies: 06,14,15. Scope: M. Likely files: commands/docs/check.md; docs/commands.md; docs/guides/docs-audit.md; docs/reference/docaudit.md.
Acceptance contracts: D03.

- [ ] Implement D03 including all four flags, partial-coverage reason, threshold behavior and execution posture. Generate public reference from facade after implementation.
- [ ] Verification: Run command-doc and generated-reference sync gates; inspect help/Usage against argument frontmatter.

### T18: Update tutorials and user-facing site material

Dependencies: 17. Scope: M. Likely files: docs/tutorials/fix-a-docs-check-finding.md; docs/REFCARD.md; relevant command-card/workflow pages identified by sweep.
Acceptance contracts: D04.

- [ ] Implement D04: examples of complete versus incomplete, working package setup and site ref, budgets/terminal recommendations, warnings and deferred pairing. Sweep all shipped references; split any batch beyond five edited files into an additional documented subtask.
- [ ] Verification: Build strict site and inspect changed rendered guide/tutorial/card content; validate no stale blanket no-R/no-network promise.

### T19: Record feature state and mirrored guidance

Dependencies: 15,16,17,18. Scope: M. Likely files: CHANGELOG.md; .STATUS; CLAUDE.md; AGENTS.md; docs/contributing.md (if check count changes).
Acceptance contracts: D05.

- [ ] Implement D05 after feature evidence exists; mark gates/pending accurately, mirror owning guidance and check counts only if changed. No release/version/tag/deployment actions.
- [ ] Verification: Run mirror/version-count gates and inspect status/changelog against actual tests and unfinished release obligations.

### T20: Make the required-test verifier non-vacuous

Dependencies: 01,06,14,15,16,19. Scope: M. Likely files: scripts/verify_a2_release.py; tests/a2/test_release_verifier.py; tests/a2/required.json; tests/a2/expected-findings.json; tests/a2/fixture-lock.json.
Acceptance contracts: V01, V02, V03, V04, V08.

- [ ] Implement V01–V04 and V08: expand all inventory cases to exact nodes, collect/run separately, reject missing/skip/xfail/xpass/empty/zero execution, and bind expected findings plus source/lock hashes. Reconcile the independently reviewed T01 spec paragraph/table-row ledger, fixture oracle identities/counts and same-run actual outcomes; test deselection and developer-versus-release mode. No count taken solely from the product report proves execution.
- [ ] Verification: Run verifier adversarial result fixtures, then verify a collected manifest; a subset-only smoke is not release evidence.

### T21: Provision both required release platforms

Dependencies: 20,16. Scope: M. Likely files: .github/workflows/ci.yml; tests/a2/test_release_ci.py; tests/a2/fixture-lock.json.
Acceptance contracts: V05, V06, V07.

- [ ] Implement V05–V07: Ubuntu24.04/macOS14 Python3.12, locked R/deps, whole manifest/verifier and evidence artifact. Unsupported Windows execution unavailable until equivalent tests; no inherited cleanup promise.
- [ ] Verification: Review workflow schema locally; after external workflow execution is authorized, verify two actual candidate-SHA platform runs/artifacts. No local YAML test can substitute for those runs.

### T22: Run recall, package triage and site smoke

Dependencies: 06,14,20,21. Scope: M. Likely files: tests/a2/test_evidence.py; tests/fixtures/docaudit/defects.json; tests/harness/replay.py (only as needed); A2 evidence reports.
Acceptance contracts: H01, H02, H03.

- [ ] Implement H01–H03: committed replay plus honest history pending, current three-package coverage/false-positive triage and separately authorized live-site smoke. Record hashes, counts and every required result; do not mutate target packages.
- [ ] Verification: Run committed regressions and actual package invocations only after implementation authorization; obtain human-supplied site URL permission before live site-only smoke.

### T23: Reconcile final gates and prepare review delivery

Dependencies: 15,16,17,18,19,20,21,22. Scope: M. Likely files: Final evidence/review records and plan/task state.
Acceptance contracts: F01, F02.

- [ ] Implement F01–F02: full gates, rendered doc inspection, validated adversarial review, complete acceptance mapping and both platform evidence. Prepare a reviewable PR description; publication/merge/release remain separate actions.
- [ ] Verification: Run full repo gates once candidate stable; rerun affected gates after fixes; record exact counts and source-SHA evidence. No PR created by this planning task.

## Checkpoints

- [ ] After T02: unchanged A1/default reports and explicit optional-stage diagnostics.
- [ ] After T06: local HTTP + immutable-ref site CLI, all supported routes fixture-proven.
- [ ] After T09: guardian handshake/deadline/cleanup/output fault cases pass on the local supported host, including early real-R probes; both-platform evidence remains pending until T21/T23; no claimed process-tree containment.
- [ ] After T14: nonzero real-R clean/planted comparisons, native-call deadlines and partial ecosystem CLI results.
- [ ] After T19: command/agent/docs/shipping contracts aligned, rendered changed content inspected.
- [ ] After T23: all required inventory cases mapped, two source-bound platform artifacts, validated review and honest recall/dogfood/live-smoke evidence.

These checkpoints verify evidence; they do not add arbitrary permission pauses
within subsequently authorized implementation. Material scope changes require
spec revision, especially route mismatches or proposals to clear incomplete
README coverage through pairing/figure-option support.

## Risks and deliberately unresolved implementation details

| Risk | Required resolution |
|---|---|
| Runtime versions are not pinned yet | T01 resolves exact available R/dependency versions and lock provenance; T04 proves route mappings. No latest-only compatibility promise. |
| Real README coverage is intentionally partial | Keep rendered-unpaired/unsupported/unlabeled groups incomplete; medrobust no-assertion not-applicable is honest. Positive clean/planted fixtures independently gate release. |
| Parent/guardian/native-call races | Single normal termination owner, phase ack before code, original deadline retained, collision/status reason tests on both platforms. |
| Scheduler delay and output burst | Measured overshoot, bounded report/cleanup, aggregate detection threshold; no hard filesystem cap or suspended-host wall-time promise. |
| Current generic CI has no required R evidence | T21 provisions both platform jobs; verifier rejects missing or skipped tests and artifacts. |
| Optional YAML or host lifetime unsupported | Explicit incomplete inference or terminal recommendation; don't add mandatory dependency or guess host timeouts. |
| Historical ref/private package/live site unavailable | Locked provenance fixture mandatory; real-history result separately pending. Obtain live URL authorization and record failure honestly. |

Before code starts, review this plan/inventory and authorize implementation.
No remaining question changes the approved feature scope; lock versions, helper
layout and concrete parameter IDs are implementation readiness work, not evidence
already available. Proposal approval does not authorize merge, release or deployment.

## Validated review corrections and release ordering

Planning revision 2 addresses the confirmed or partially confirmed findings in
[REVIEW-docs-check-a2-plan-r7-2026-10-12.md](REVIEW-docs-check-a2-plan-r7-2026-10-12.md). The approved product spec is unchanged.

T01 must produce a reviewed ledger of every normative spec paragraph and table
row, anchored by section/ordinal/excerpt hash, independent of the inventory. T20
reconciles it against all expanded nodes and aggregate obligations; T23 audits
the complete mapping again. Node collection alone cannot prove execution: bind
collected and actual outcome IDs to one candidate/platform run, and cross-check
checked assertions/routes against independent fixture oracles and execution
sentinels. Required release verification is explicit, with zero missing/skipped/
xfail/xpass nodes, even when developer mode permits R skips.

Evidence-validation tests never launch their own containing full suite or wait
for their own upload. Platform jobs run and verify local outputs first, upload
second; T22 produces actual smoke/dogfood evidence and T23 validates both uploaded
artifacts plus final full-suite/build/review records. V05/V06/H02/H03/D04/F01/F02
retain required validator nodes and separate actual aggregate obligations; neither
part can replace the other. This follows the spec's required-node rule, rather
than removing normative requirements from the manifest.

T21 repeats T16 installed-layout checks on both release hosts. T17 waits for T15
execution-boundary prose; T20 waits for T19 integration docs; T22 waits for T21
actual platform evidence. Early lifecycle checkpoints claim local evidence only.
T01 also records the current 47 declared test-all checks; review the candidate
check-name/count delta instead of hardcoding an unchanged future count. Optional
R parse checks do not establish release-R execution.

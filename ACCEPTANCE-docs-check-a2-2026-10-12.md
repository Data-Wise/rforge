# Acceptance-test inventory — docs:check A2 revision 7

Date: 2026-10-12. Status: planning revision 2 after validated Claude review; approved product spec remains revision 7. Implementation in progress: 306 expanded A2 nodes collected locally; contract-to-node review complete, with 39 groups retaining coverage gaps. Both-platform evidence remains pending. See [coverage audit](COVERAGE-docs-check-a2-2026-10-12.md).
Approved spec: [SPEC-docs-check-a2-2026-10-12.md](SPEC-docs-check-a2-2026-10-12.md), SHA256 `b202409f690b478fcb3fe6473afb4021930a1e271e8ae2a90ec0370bebe65b51`.
Plan: [PLAN-docs-check-a2-2026-10-12.md](PLAN-docs-check-a2-2026-10-12.md); task state: [TASKS-docs-check-a2-2026-10-12.md](TASKS-docs-check-a2-2026-10-12.md).

## Required mapping and result policy

Every proposed pytest node below is mandatory on Ubuntu 24.04 and macOS 14,
with Python 3.12 and locked R/pkgload/evaluate/knitr/pkgdown dependencies.
Each node validates executable behavior or an evidence validator's success and
failure cases. Actual external observations are additional aggregate obligations;
synthetic validator records cannot satisfy those observations. P rows also run
on both platforms. X rows test record validation, not live external success.
H02/H03, V05/V06, D04 and F01/F02 have both node and aggregate obligations below.
This retains the spec's required-node rule without making a job depend on its
own future upload, full-suite completion or unfinished peer job.
The named files/functions remain proposed contract targets; concrete collected
nodes are recorded in `tests/a2/required.json`. Tests, the runtime lock and the
verifier now exist. Local passes do not establish a row's complete acceptance or
both-platform release success; mapping remains fail-closed until reviewed.

A row may represent several parameter cases. At implementation, expand its
listed behaviors to concrete `[case-id]` node IDs; every case is required on both
platforms. A base function name alone cannot prove all parameter cases collected.
Record row/requirement → case IDs → fixture/hash → outcome/evidence. Cross-check
all approved spec paragraphs/links after test creation, including narrative
MUSTs; reject unmapped requirements, renamed/missing nodes and empty evidence.
Unexpected platform-specific skip is a failed release preflight, not a waiver.

Types:
- P: Portable Python/schema/CLI fixtures.
- H: Real local HTTP plus throwaway git where needed.
- B: Real pinned pkgdown/R route build.
- G: Real child-process lifecycle (Python controlled child; native R also required separately).
- R: Real R/package/evaluate/CLI fixture.
- D: Actual packaging/docs/gate/platform evidence.
- X: Manual/external evidence plus required evidence-reader test.

For live/history/dogfood observations, parameter fixtures test the evidence
reader but cannot manufacture acceptance evidence. Historical refs may stay
pending only with the spec's provenance-backed regression substitute; failed or
unavailable required live integration smoke remains a release-evidence gap.

## Contract inventory

Each oracle is an acceptance condition. The spec link is a requirement anchor,
not a line-number promise; SHA256 protects against unnoticed baseline changes.

### Reporting

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| C01 / T02 | `tests/a2/test_reporting.py::test_a1_default_unchanged` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | Neither optional stage appears; no R/network call; existing A1 findings, scope and default report snapshots unchanged. |
| C02 / T02 | `tests/a2/test_reporting.py::test_cli_scope_validation` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | Site resolves one package; eco ambiguity, ref without site, budget without examples and nonpositive/noninteger budgets exit 2 before side effects. Parameterize every misuse. |
| C03 / T02 | `tests/a2/test_reporting.py::test_stage_state_preserves_static_findings` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | Complete/incomplete/unavailable/not-applicable stages retain static findings; unrequested stages absent; failed optional stage does not discard successful stages. |
| C04 / T02 | `tests/a2/test_reporting.py::test_threshold_matrix` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | none always 0 except misuse; incomplete/failed audit 2 under warn/error; complete warn 1 only under warn; complete error 1 under either; clean 0. Required full case expansion. Include mixed completed A2 warning plus incomplete site/examples/package under all thresholds: none=0, warn=2, error=2; incompleteness dominates findings. |
| C05 / T02 | `tests/a2/test_reporting.py::test_text_json_diagnostics` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | Scope first; stage states/counts visible with detailed on/off; incomplete notices on stderr, final INCOMPLETE and no clean no-findings conclusion; stdout exactly one JSON document. Explicitly assert info hidden without --detailed and visible with it, with invariant states/counts in text and JSON. |
| C06 / T02 | `tests/a2/test_reporting.py::test_engine_union_and_package_reasons` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#architecture-and-suppression) | Sorted unique package lists and ecosystem union; mixed success/failure keeps per-package reasons and counts. |
| C07 / T02 | `tests/a2/test_reporting.py::test_allowlist_preserves_incomplete` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#architecture-and-suppression) | Source-relative suppression changes findings only; never grants execution or removes unverified/blocked counts, unavailable state or threshold exit 2; source-less extra URL info is outside file allowlist. |

### Site Refs

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| S01 / T03 | `tests/a2/test_site_refs.py::test_explicit_ref_immutable_tree` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#site-stage) | Explicit local SHA/ref selects immutable tree, not current/dirty files; no fetch; report ref, SHA, timestamp, selection and local-ref provenance, without freshness claim. |
| S02 / T03 | `tests/a2/test_site_refs.py::test_workflow_inference_and_fallback` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | One literal pkgdown deployment branch selects origin then local; no candidate falls back origin/main then main; ambiguous candidates never fall back. Workflow used from identified local snapshot with provenance. |
| S03 / T03 | `tests/a2/test_site_refs.py::test_unsupported_workflows_require_ref` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Multiple branches/workflows, glob, expression, alternate checkout and reusable workflow require explicit ref; missing git/ref incomplete; explicit ref bypasses inference only. |
| S04 / T03 | `tests/a2/test_site_refs.py::test_yaml_reader_missing` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Relevant config without optional YAML reader yields explicit inference/route incompleteness; literal data never evaluated; no mandatory dependency added. |

### Site Routes

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| S05 / T04 | `tests/a2/test_site_routes.py::test_rd_routes_keep_internal_topics` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Rd basenames map to reference pages including internal topics; reference/nav index organization does not delete pages; generated index/authors/news/404 never mandatory. |
| S06 / T04 | `tests/a2/test_site_routes.py::test_pinned_pkgdown_article_routes` | B / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Real pinned build proves root, articles/ and nested Rmd routes, underscore exclusions and tutorial scope; provenance/version captured; mismatch blocks supported mapping, never silently changes it. |
| S07 / T04 | `tests/a2/test_site_routes.py::test_route_collisions_and_custom_layout` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Colliding routes incomplete; Quarto/extensions/as_is/overlays/build/publication overrides incomplete, checked supported routes retained; external articles are links, not mandatory routes. |
| S08 / T04 | `tests/a2/test_site_routes.py::test_release_mode_and_destination` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Default/explicit release allowed; development mode/destination and PKGDOWN_DEV_MODE overrides incomplete; top-level local destination never becomes URL suffix. |

### Site Http

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| S09 / T05 | `tests/a2/test_site_http.py::test_base_url_validation_normalization` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#site-stage) | HTTP(S) only, no credentials/query/fragment; base boundary, case, escaped separator and default port handling preserve distinct routes; canonical source URL disagreement incomplete; absent source URL uses supplied base. |
| S10 / T05 | `tests/a2/test_site_http.py::test_same_origin_redirect_policy` | H / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Accept at most 3 same-origin redirects; cross-origin, www/apex, scheme changes including HTTP-to-HTTPS and downgrade stop incomplete with target; zero arbitrary aliasing. Assert rejected final target appears and guidance requests a fresh invocation with the caller-selected canonical base, including HTTP-to-HTTPS. |
| S11 / T05 | `tests/a2/test_site_http.py::test_sitemap_shape_and_bounds` | H / [contract](SPEC-docs-check-a2-2026-10-12.md#site-stage) | URL-set namespaces and trailing-slash/subdirectory cases work; invalid XML/index/offline/missing/oversized/slow responses incomplete, never mass missing-page findings; 10-second and 5-MiB bounds exercised. Cross missing sitemap with absent source url: incomplete, no mass missing routes; supplied base alone does not establish success. |
| S12 / T05 | `tests/a2/test_site_http.py::test_foreign_and_zero_inbase_entries` | H / [contract](SPEC-docs-check-a2-2026-10-12.md#normative-site-rules) | Foreign entries counted/excluded; nonempty sitemap with zero in-base entries incomplete; fragments removed and distinct paths not collapsed. |

### Site Integration

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| S13 / T06 | `tests/a2/test_site_integration.py::test_missing_extra_and_unreleased_severity` | H / [contract](SPEC-docs-check-a2-2026-10-12.md#site-stage) | Throwaway git history + local HTTP: selected-ref missing route warn despite checkout ahead; checkout-only and dirty additions info; supported extra article/reference info, generated extras ignored; attributed source paths retained. Message says absent from sitemap; never claims HTTP 404 or deployment freshness. |
| S14 / T06 | `tests/a2/test_site_integration.py::test_site_cli_thresholds` | H / [contract](SPEC-docs-check-a2-2026-10-12.md#verification-and-release-acceptance) | Clean complete site exits 0; planted missing page exits 1 under warn and 0 under error; offline/unsupported exits 2 with either threshold and 0 with none; static findings survive. |
| S15 / T06 | `tests/a2/test_site_integration.py::test_no_build_crawl_fetch_or_deploy` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#site-stage) | Production site stage calls only the bounded sitemap read/ref inspections; no render/build/deploy, link crawl, git fetch or prose/freshness assertions. |

### Guardian

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| G01 / T07 | `tests/a2/test_guardian.py::test_handshake_before_package_code` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Guardian outside R group and direct child owner; startup handshake before any package code; expired preflight/startup global budget prevents launch. |
| G02 / T07 | `tests/a2/test_guardian.py::test_phase_arm_ack_sequence` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Atomic run/sequence IDs; guardian arm ack precedes parent release; stale/lost ack executes no phase; rapid transitions cannot overwrite an unacknowledged phase or restart timing on receipt. |
| G03 / T07 | `tests/a2/test_guardian.py::test_heartbeat_age_and_stale_records` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Parent updates <=1-second cadence; guardian ages last observed new sequence, not stale timestamp; 5-second lapse interrupts, earliest global/heartbeat event wins; no package-output defect on host stall. Parameter cases: heartbeat expires before global deadline; global expires before heartbeat; simultaneous expiry records a permitted terminal reason without deadline reset or duplicate signalling. |
| G04 / T08 | `tests/a2/test_guardian.py::test_single_termination_owner_idempotence` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Healthy guardian alone signals group; termination ID/reason/phase/time recorded before TERM; duplicate requests idempotent; parent emergency path only on observed guardian failure and always incomplete. |
| G05 / T08 | `tests/a2/test_guardian.py::test_deadline_completion_collision` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Expired effective deadline processed before success; before-deadline completion retained, at/after rejected; reason comes from status record, not guessed signal/exit code. |
| G06 / T08 | `tests/a2/test_guardian.py::test_term_kill_cleanup_observations` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | TERM, <=2-second grace, KILL then <=5-second bounded wait; direct R child reaped, guardian reaped by parent; cooperating group disappearance observed separately; no grandchildren-reaped claim. Include live TERM-ignoring child and ordinary group child; observe actual KILL escalation and eventual direct-child reap, not only signal mocks. |
| G07 / T08 | `tests/a2/test_guardian.py::test_parent_loss_preserves_deadline` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Kill parent only; guardian survives, terminates owned group on earliest original deadline/heartbeat lapse without reset; valid checkpoints retained; lifecycle marker/run ID inspectable. |
| G08 / T08 | `tests/a2/test_guardian.py::test_guardian_failure_emergency_cleanup` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Missing/failed guardian status incomplete even if parent emergency cleanup succeeds; unverifiable cleanup never success; no stale PID killing or reconstruction of lost reports. |
| G09 / T08 | `tests/a2/test_guardian.py::test_detached_child_and_total_host_loss` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#process-supervision-and-stdio) | Detached child explicitly outside cleanup guarantee and fixture removes it in finally; killing both supervisors yields no completion guarantee, never clean; wrapper reports interruption. |
| G10 / T08 | `tests/a2/test_guardian.py::test_monotonic_clock_and_scheduler_delay` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Shared Python monotonic_ns clock recorded; deadline state unaffected by wall-clock edits; monitor cadence 100ms but measured enforcement delay/overshoot, no hard scheduler or suspend wall-time claim. |

### Stdio

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| I01 / T09 | `tests/a2/test_stdio.py::test_native_output_does_not_deadlock` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#process-supervision-and-stdio) | Native/child output >64KiB bypasses evaluate into separate files, not undrained pipes; JSON stdout uncontaminated; retain <=1MiB per diagnostic stream. |
| I02 / T09 | `tests/a2/test_stdio.py::test_shared_text_output_threshold` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#process-supervision-and-stdio) | One 10MiB aggregate stdout+stderr+UTF8 payload threshold; 1+2+3MiB is 6; cumulative payload counted once, metadata excluded, mirrors counted; evaluate not echoed to native files. |
| I03 / T09 | `tests/a2/test_stdio.py::test_output_overshoot_with_parent_loss` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Exceeded threshold incomplete with actual overshoot/truncation; guardian still detects excess after parent death; no claim to bound arbitrary files, memory or plots. |
| I04 / T09 | `tests/a2/test_stdio.py::test_checkpoint_and_marker_integrity` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Atomic valid completed checkpoints survive guardian exit until report; partial/malformed/missing checkpoints incomplete, no fabricated match; marker started/completed/interrupted includes last phase and run ID. |
| I05 / T09 | `tests/a2/test_stdio.py::test_bounded_finalization_and_artifacts` | G / [contract](SPEC-docs-check-a2-2026-10-12.md#guardian-protocol-and-deadline-ownership) | Healthy completion closes owned handles and temp cleanup after reading; 5-second report allowance/15-second wrapper reserve accounted; report assembly failure interruption, host kill cannot promise JSON/artifact cleanup. |

### Readme

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| E01 / T10 | `tests/a2/test_readme.py::test_source_selection_and_ambiguity` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Exactly one source preferred to md, never replay md twice; both sources incomplete/no execute; md-only transcript retains omitted-setup caveat; distinct file/line attribution. |
| E02 / T10 | `tests/a2/test_readme.py::test_rendered_unpaired_counts` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Source with/without assertions plus asserted md always rendered-unpaired/incomplete; source success counts retained; no-source-assertions executes no setup; both thresholds 2, allowlist cannot clear. |
| E03 / T10 | `tests/a2/test_readme.py::test_explicit_closed_fence_extraction` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Backtick/tilde r and brace-r spans/labels recognized; unterminated R incomplete/no execute; unlabeled/Python/vignettes ignored as execution sources; discovered unsupported #> groups remain unverified. |
| E04 / T10 | `tests/a2/test_readme.py::test_pasted_output_and_skip_marker_location` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Only line-leading #> is assertion; comment="#>" and strings are not output; all 3 skip forms supported; HTML marker must be immediate prior nonblank line. |
| E05 / T11 | `tests/a2/test_readme.py::test_literal_defaults_precedence` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#literal-options) | Literal global knitr/Quarto defaults, Rmd headers and body options resolve; body overrides header; conflicting same-precedence values, dynamic defaults/templates/children incomplete before execution. |
| E06 / T11 | `tests/a2/test_readme.py::test_supported_visibility_options` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#literal-options) | eval/include/echo/warning/message booleans, results markup/hide, collapse boolean, comment #>, error FALSE supported; labels/engine metadata allowed; hidden channel assertions excluded with reasons, not passed. |
| E07 / T11 | `tests/a2/test_readme.py::test_unsupported_options_fail_preflight` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#literal-options) | Every other literal/dynamic option including figure options and error TRUE/numeric errors incomplete before execution; list unsupported options; no intentional-error false defect. |
| E08 / T11 | `tests/a2/test_readme.py::test_installation_token_filter` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Installation calls skipped by code tokens, not comments/strings; no dependency install; warning explicitly says convenience filter, not sandbox. |
| E09 / T11 | `tests/a2/test_readme.py::test_coverage_partition_and_exclusions` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#coverage-accounting) | Discovered=checked+excluded+unverified+blocked; checked subdivides matched/mismatched; one checked/many excluded may complete, excluded-only not-applicable; headline/JSON all counts; unstable unsupported blocked incomplete. |
| E10 / T11 | `tests/a2/test_readme.py::test_no_eligible_assertions_no_setup` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#coverage-accounting) | No assertions or excluded-only or unsupported preflight yields no setup-alone execution; discovery/report remain available without installed R. |

| E11 / T11 | `tests/a2/test_readme.py::test_real_readme_shape_regressions` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#actual-readme-coverage-and-review-disposition) | Hash-pinned excerpts or equivalent synthetic reproductions with provenance: medfit four explicit-R groups plus two unlabeled groups, unverified=2 and incomplete; probmed source literal assertion plus hidden fig.path/out.width causes unsupported-options preflight/no execution and rendered-unpaired md group; source-success control still cannot clear rendered-unpaired. For these incomplete cases none=0 and warn/error=2. medrobust zero assertions => not-applicable/no setup/no R launch, no invented incomplete or A2 error; isolated clean static stage => all thresholds 0. Current dogfood counts may drift; fixture shapes may not silently change. |

### Comparison

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| N01 / T12 | `tests/a2/test_comparison.py::test_documented_precision_cases` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#output-comparison) | Every normative numeric table row independently parameterized, inclusive decimal boundary exact; scientific precision 1e-04 vs1.00e-04, signs, whitespace, percent, NA/NaN/signed Inf preserved. Exact verdict cases: 55% versus 36 % output-warn, 55% versus 0.55 shape-warn, 1,234 versus 1234 shape-warn; no unit/grouping conversion. |
| N02 / T12 | `tests/a2/test_comparison.py::test_labeled_inequality_cases` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#output-comparison) | Equality-versus strict/non-strict bounds uses no tolerance; implied stronger actual upper bound matches; weaker/opposite/bare unlabeled bounds unverified shape warn; no guessed contradiction. |
| N03 / T12 | `tests/a2/test_comparison.py::test_expression_subsequence_no_reuse` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#output-comparison) | Same expression/skeleton/token count; ordered documented subsequence cannot reuse tokens; may omit undocumented expressions only; labels/values remain mandatory; ambiguous shape incomplete. |
| N04 / T12 | `tests/a2/test_comparison.py::test_rng_and_unstable_fields` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#output-comparison) | Unseeded/uncertain stochastic assertions info+unverified not matched; earlier explicit seed distinguished; versions/timestamps/unstable fields not numeric candidates; lack of recognized RNG never proves determinism. |
| N05 / T12 | `tests/a2/test_comparison.py::test_warn_only_and_complete_mismatch` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#output-comparison) | Initial examples-output warn, completed mismatch retains complete comparison; shape/lost association incomplete as specified; no per-package promotion/severity override. |

### Examples R

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| R01 / T13 | `tests/a2/test_examples_r.py::test_fresh_ordered_hidden_setup` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Real Rscript --vanilla/evaluate executes ordered chunks in one fresh session; hidden setup retains state; eval false no side effect; separate file/package sessions leak no state. |
| R02 / T13 | `tests/a2/test_examples_r.py::test_working_tree_load_identity` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | pkgload::load_all loads checkout despite intentionally different installed package; report path/version, R/dependency versions, UTF8 and width80; package data readable from temp working directory. |
| R03 / T13 | `tests/a2/test_examples_r.py::test_dependency_preflight_no_install` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#readme-source-selection-and-setup) | Missing Rscript/pkgload/evaluate/knitr when needed/package deps unavailable/incomplete; sorted engine identifiers; no installed substitution or dependency install. Portable missing-engine variants also run without R. |
| R04 / T13 | `tests/a2/test_examples_r.py::test_visibility_and_conditions_channels` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#literal-options) | Real evaluate stdout/warnings/messages separate; visible assertion channels honored and hidden assertions excluded; selected source literal assertions do not certify md. |
| R05 / T13 | `tests/a2/test_examples_r.py::test_one_upstream_failure` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#execution-limits-and-reporting) | First failing chunk emits one examples-error warn and blocks later chunks; md missing-object uncertainty not proof of published defect; no cascaded errors or raised facade exception. |
| R06 / T13 | `tests/a2/test_examples_r.py::test_clean_and_planted_stale_output` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#verification-and-release-acceptance) | Clean zero A2 findings, complete and checked>0; planted deterministic discrepancy named examples-output warn with expected assertion ID; no allowlist/skip/zero count escape. |

### Examples Cli

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| R07 / T14 | `tests/a2/test_examples_cli.py::test_native_chunk_deadline` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#execution-limits-and-reporting) | Real blocking native call terminated externally; guardian effective chunk limit <=60s and remaining file/global; terminated chunk blocked/incomplete with valid earlier results. |
| R08 / T14 | `tests/a2/test_examples_cli.py::test_file_loading_deadline` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#execution-limits-and-reporting) | File starts with startup/loading and caps300s; stuck load cannot evade file/global deadline; no phase executes after unacknowledged start. |
| R09 / T14 | `tests/a2/test_examples_cli.py::test_global_budget_across_packages` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#execution-limits-and-reporting) | Sequential files/packages share one default300s or explicit positive budget; initialization/loading consume it; later work budget-blocked; deadline never reset between guardians/files. |
| R10 / T14 | `tests/a2/test_examples_cli.py::test_partial_cli_report_thresholds` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | Controlled timeout JSON partial envelope includes valid earlier chunks, blocked counts, stderr progress; incomplete warn/error2 and none0; clean/planted completion threshold matrix matches R06. Text-mode timeout also ends INCOMPLETE and never no findings, preserving earlier valid findings. |
| R11 / T14 | `tests/a2/test_examples_cli.py::test_wrapper_lifetime_and_interruption` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#execution-limits-and-reporting) | Known wrapper lifetime covers budget+15s or budget reduced; unknown lifetime recommends terminal; poll/yield not timeout; external missing stdout is interrupted, not clean or falsely recovered. |
| R12 / T14 | `tests/a2/test_examples_cli.py::test_combined_stage_and_eco_partial_results` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#command-contract) | Site/examples requested independently; partial combined stages keep static/successful results; single explicit site URL never reused across eco; global example-budget and engine union visible. |

### Agent

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| A01 / T15 | `tests/a2/test_agent.py::test_default_recipe_stays_static` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#orchestrator-authorization-and-guard-tests) | Existing DOCS_AUDIT recipe/validator default unchanged; no site discovery or arbitrary probe; default authorizes no execution. |
| A02 / T15 | `tests/a2/test_agent.py::test_human_versus_imported_url` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#orchestrator-authorization-and-guard-tests) | Behavioral fixtures distinguish current/still-applicable human URL authorization from file/tool-derived URLs; only single-package site-only auto-run; ref requires site; local/private URLs allowed. |
| A03 / T15 | `tests/a2/test_agent.py::test_examples_always_recommend_only` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#orchestrator-authorization-and-guard-tests) | Any run-examples including combined site/examples recommend-only; guard retains positive prohibition, rejects executable recipe examples; site/ref permitted conditionally, network exceptions do not allow write/upload. |
| A04 / T15 | `tests/a2/test_agent.py::test_recipe_parse_uses_stubs` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#orchestrator-authorization-and-guard-tests) | Recipe parsing invokes no real network/R; stubbed fixtures validate command/flags; text tests do not claim to prove conversational authorization, manual prompt review recorded. |

### Shipping

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| D01 / T16 | `tests/a2/test_shipping.py::test_r_script_packaged_and_parses` | D / [contract](SPEC-docs-check-a2-2026-10-12.md#documentation-and-boundaries) | Shipped lib/r/docexamples.R appears in packed plugin; actual installed-layout source path works; R parse gate real on release hosts, optional only in developer gates; tests/harness/ remains dev-only. |
| D02 / T16 | `tests/a2/test_shipping.py::test_no_new_public_module_dependency` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#architecture-and-suppression) | Private site/examples/guardian modules leave public module/nav inventory unchanged; no mandatory Python dependency; facade relative imports work using python -m lib.docaudit. |

### Docs

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| D03 / T17 | `tests/a2/test_docs.py::test_command_flags_and_reference_sync` | D / [contract](SPEC-docs-check-a2-2026-10-12.md#documentation-and-boundaries) | Frontmatter/Usage/commands section agree for site/ref/run-examples/budget; generated docaudit reference current; help accurately retains default behavior and execution boundaries. |
| D04 / T18 | `tests/a2/test_docs.py::test_walkthroughs_and_site_content` | D / [contract](SPEC-docs-check-a2-2026-10-12.md#documentation-and-boundaries) | Guide/tutorial/REFCARD/cards/workflows explain partial README scope, warning severity, deadlines/terminal invocation and site inference; changed rendered content inspected, no stale unconditional no-R/no-network promise. Node checks shipped explanatory content/record-validator cases; actual rendered changed-content inspection is aggregate after build. |
| D05 / T19 | `tests/a2/test_docs.py::test_status_guidance_count_sync` | D / [contract](SPEC-docs-check-a2-2026-10-12.md#documentation-and-boundaries) | CHANGELOG/status say implemented only after evidence; CLAUDE-to-AGENTS mirror if changed; count changes only when checks added; no version bump/tag/deploy in feature work. |

### Release Verifier

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| V01 / T20 | `tests/a2/test_release_verifier.py::test_manifest_mapping_and_collection` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#required-evidence) | Every inventory contract mapped to concrete expanded collected node IDs per platform; missing/duplicate/unmapped node and empty manifest/results rejected; planned IDs never treated as collection evidence. Use an independently reviewed requirement ledger derived from the unchanged approved spec, not only inventory IDs; a removed row or omitted normative paragraph fails mapping. Ledger entries carry section anchor, paragraph/table-row ordinal, quoted obligation and content hash. |
| V02 / T20 | `tests/a2/test_release_verifier.py::test_required_outcomes_no_vacuous_pass` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#release-verifier-ownership-and-evidence) | Missing/skipped/xfail/xpass/failure and zero R checked/HTTP comparisons reject; collection checked separately from run outcomes; unsupported/not-applicable tests cannot substitute for positive clean/planted tests. Compare required expanded IDs with collected IDs AND executed outcome IDs from the same candidate/platform invocation. Reject -k/-m/--deselect omissions, duplicates, stale or mismatched run IDs. Cross-check report checked/HTTP counts against independent fixture expected assertion IDs, known route sets, server request log and actual native/R execution sentinels; inflated counts fail. |
| V03 / T20 | `tests/a2/test_release_verifier.py::test_expected_findings_exactness` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#required-evidence) | Expected findings exact check/severity/source/assertion ID; unexpected warn/error, missed planted defect, skip/allowlist/zero checked invalidates clean/planted gate; manifest changes reviewed. |
| V04 / T20 | `tests/a2/test_release_verifier.py::test_evidence_identity_and_versions` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#release-verifier-ownership-and-evidence) | Wrong candidate SHA or manifest/fixture-lock hash, missing platform/version/smoke results/artifact fails; source SHA OS/Python/R/deps/hash evidence bound to both platforms. The node exercises identity validation on controlled records and local completed prerequisite outputs only; both-platform uploaded-artifact verification is aggregate, never an in-job prerequisite. |

| V08 / T20 | `tests/a2/test_release_verifier.py::test_developer_and_release_modes` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#required-evidence) | Explicit release-verifier entry point always requires locked R/deps and all manifest nodes, regardless of developer skip configuration. Missing R can be a recorded developer skip, but release preflight fails; zero skipped release nodes. Test filtered/deselected runs and falsified self-reported nonzero counts. |

### Release Ci

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| V05 / T21 | `tests/a2/test_release_ci.py::test_both_platforms_locked_runtime` | D / [contract](SPEC-docs-check-a2-2026-10-12.md#required-evidence) | Dedicated a2-release matrix Ubuntu24.04/macOS14 Python3.12 provisions exact fixture-lock R/deps; no unpinned latest; each platform runs full required manifest and verifier with real R/HTTP nonzero. Node checks workflow contract and effective local runtime/lock; actual two-platform runs, real execution and provisioning success are aggregate obligations after jobs complete. |
| V06 / T21 | `tests/a2/test_release_ci.py::test_artifact_failure_blocks_acceptance` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#release-verifier-ownership-and-evidence) | Each platform publishes a2-release-evidence; missing/upload-failed artifact prevents release-acceptance claim, generic green Python suite insufficient. Node feeds missing, upload-failed, stale and good controlled artifact records to the validator. Actual successful retrieval of both uploaded artifacts is aggregate; it never waits for its own future upload. |
| V07 / T21 | `tests/a2/test_release_ci.py::test_unsupported_platform_diagnostic` | P / [contract](SPEC-docs-check-a2-2026-10-12.md#required-evidence) | Windows either has equivalent process-tree evidence or examples unavailable; unsupported POSIX evidence explicitly unverified, never inherits macOS/Linux cleanup guarantees. |

### Evidence

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| H01 / T22 | `tests/a2/test_evidence.py::test_committed_defect_replay` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#verification-and-release-acceptance) | A2-owned replay rows show caught/eligible/pending; known stale numeric and selected-ref missing-route regressions asserted; firm cases cannot regress. Provenance-backed fixture substitutes for unavailable historical ref only with history pending. |
| H02 / T22 | `tests/a2/test_evidence.py::test_package_coverage_triage` | R / [contract](SPEC-docs-check-a2-2026-10-12.md#actual-readme-coverage-and-review-disposition) | medfit/probmed/medrobust record file hashes and all six coverage totals/reasons; actual current counts observed not hardcoded from2026-10-12; every warn/error false-positive class triaged; partial scopes not silently green. Node validates triage-record schema, reason/state assertions and failure records using controlled or local prerequisite inputs; actual current three-package read-only dogfood is aggregate. Shape regression expectations are independently required in E11; current package drift must be hashed, reviewed and cannot waive those fixtures. |
| H03 / T22 | `tests/a2/test_evidence.py::test_live_site_smoke_evidence` | X / [contract](SPEC-docs-check-a2-2026-10-12.md#verification-and-release-acceptance) | Separately authorized real-package site-only CLI smoke records supplied URL, chosen ref and candidateSHA; transient/failing network never success; required evidence reader test on both platforms accepts only recorded success. Node validates success/failure/provenance records without contacting a live URL. Actual separately authorized smoke is aggregate; do not require this node to read a future run artifact or count a controlled record as real smoke. |

### Final Gates

| ID/task | Proposed pytest node | Type/spec anchor | Required fixture and oracle |
|---|---|---|---|
| F01 / T23 | `tests/a2/test_final_gates.py::test_gate_record_validation` | D / [contract](SPEC-docs-check-a2-2026-10-12.md#verification-and-release-acceptance) | Full pytest/tests/test-all with exact pass/skip counts, version/ref/commands/mirror/nav gates and strict mkdocs build; meaningful rendered changed-content review; no build-alone proof of current prose. Node tests gate-record validation, rejecting failure, absent logs, unexpected checks and wrong source SHA; never launches its containing suite. Aggregate runs full gates once candidate stable, then validates actual completed logs and rendered-content review. |
| F02 / T23 | `tests/a2/test_final_gates.py::test_review_record_validation` | X / [contract](SPEC-docs-check-a2-2026-10-12.md#verification-and-release-acceptance) | Read-only adversarial review checked against owning sources, resolved findings logged; acceptance inventory maps all normative requirements; both platform evidence complete before PR/release readiness; external actions separately authorized. Node validates review/mapping record schemas and negative records; actual read-only review, confirmed finding disposition and both uploaded artifacts are aggregate after platform jobs, not this node prerequisites. |

## Fixture and evidence records to realize

- `tests/a2/fixture-lock.json`: exact runtime/dependency versions, fixture provenance and hashes; no unpinned latest.
- `tests/a2/expected-findings.json`: exact check/severity/source/assertion identities. Clean fixtures zero A2 findings/complete/checked>0; planted required warnings/complete/nonzero; unsupported fixtures assert exact incomplete/not-applicable counts and never substitute for positive cases.
- `tests/a2/required.json`: every inventory ID and normative requirement, all expanded node IDs, per-platform obligation and hashes. No skip/allowlist/xfail/empty-result escape.
- CI `a2-release-evidence`: candidate SHA, manifest/lock hashes, OS/Python/R/deps, collected IDs and counts, outcomes, runtime coverage, verifier result, replay/dogfood/smoke reports. Retain actual artifacts for both platforms.
- Report history replay caught/eligible/pending separately from mandatory committed regressions; never count unavailable actual history as a pass.

## Timing and test isolation

Use short injectable budgets for most race/fault fixtures, plus dedicated real
R cases that exercise public limits/actual configuration. Changing a fixture
clock is not proof of native-call termination. Assert state/reason/deadline
identity and observed bounded shutdown; allow recorded scheduler overshoot as
the spec does rather than use a flaky exact 100ms wall-clock assertion.
Fixture watchdogs/finally blocks must clean all owned/deliberately detached
children even if the tested parent dies. Never kill a stale PID from previous
runs. Local HTTP tests use bounded loopback endpoints, no public crawl. Package
fixture working trees/libraries are isolated and user packages remain read-only.

## Completeness checklist

- [ ] Every normative revision 7 paragraph mapped to these rows and concrete cases.
- [ ] All proposed nodes expanded/collected on both platforms with no missing cases.
- [ ] Both runs have nonzero real-R checked assertions and local-HTTP comparisons.
- [ ] Native-call, parent-loss and actual group-child cleanup executed, not mocked away.
- [ ] Exact expected findings, CLI exits and source/hash provenance reconciled.
- [ ] Unsupported/deferred scopes honestly incomplete/not-applicable, never called verified.
- [ ] Both candidate-SHA CI artifacts and required live-smoke/replay/dogfood evidence present.
- [ ] Full repository gates and changed rendered-doc inspection recorded.

Inventory size counts test groups, not runnable case count or coverage achieved.

Proposed groups: 87. Collected: 0. Executed: 0. Passed: 0.

## Evidence ordering and aggregate release obligations

1. T01 records the approved spec hash and a reviewed requirement ledger. Every
   normative paragraph/table row maps to required expanded test cases, plus any
   external evidence obligation; do not invent new requirement IDs in the spec.
2. T20 implements the explicit release-verifier entry point and tests it against
   controlled adversarial records. Expected assertion IDs/counts and route sets
   come from fixture oracles, not from the product report being checked.
3. T21 runs the full expanded node set on each platform. Each job verifies its
   own actual outcomes and local prerequisite reports, then uploads evidence.
4. After uploads, T22 records actual current package dogfood and authorized live
   smoke for the same candidate SHA; historical replay pending stays separate.
   H02/H03 validator nodes are already complete and cannot be backfilled as
   passes from these later observations.
5. T23's aggregate release-owner invocation retrieves both actual artifacts and
   verifies candidate/lock/manifest hashes, versions, node outcomes, independent
   fixture execution evidence and upload success (V05/V06). It also checks H02
   dogfood/triage, H03 live smoke, D04 rendered inspection, F01 full gates and F02
   validated review/mapping. All remain mandatory; synthetic records cannot
   satisfy them. Any absent/failed observation blocks acceptance.

Record the test-all expected check-name list and total from the candidate script,
reviewing changes against the current baseline of 47 declared run checks. Require
all declared checks to succeed and zero failed checks; inspect R parse/execution
subresults independently because the current optional-R helper returns success
without parsing when Rscript is absent. Full pytest collection and result IDs
must agree; report exact pass/skip counts without inventing a fixed future pytest
count. A2 required nodes have zero skips; developer-only skips elsewhere are
recorded explicitly and cannot substitute for required execution.

No external workflow, live-site access, R execution or product tests ran during
this planning revision. Proposed groups: 87; collected/executed/passed: 0.

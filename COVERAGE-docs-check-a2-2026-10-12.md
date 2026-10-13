# A2 contract-to-test mapping audit

Approved spec revision 7 remains unchanged. Mapping review is complete; release coverage is not complete.

Mapped 118 unchanged paragraphs/table rows to 87 inventory groups and 306 actual expanded nodes. All collected A2 nodes have one semantic inventory owner; no duplicated or unowned nodes. 39 groups retain explicit gaps. Neither filename similarity nor local test success closes these gaps.

The immutable requirement ledger records exact source text/hash/anchor/ordinal plus inventory ownership. Test source hashes bind this review snapshot. Header, historical validation and approval paragraphs are contextual documentation obligations, not invented runtime tests. Actual external evidence is separate from portable validators.

## Remaining coverage work

### S02 / T03

Mapped: `tests/a2/test_site_refs.py::test_workflow_inference_and_fallback`.

- Remote-tracking ref preference and no-candidate origin/main fallback are not explicitly exercised.

### S03 / T03

Mapped: `tests/a2/test_site_refs.py::test_unsupported_workflows_require_ref[[main, dev]]`, `tests/a2/test_site_refs.py::test_unsupported_workflows_require_ref[['*']]`, `tests/a2/test_site_refs.py::test_unsupported_workflows_require_ref[['${{ github.ref }}']]`.

- Alternate checkout, reusable workflow, multiple candidate files, missing git/ref cases missing.

### S04 / T03

Mapped: `tests/a2/test_site_refs.py::test_missing_yaml_reader_requires_explicit_ref`.

- Reader absence tests workflow inference; selected-ref route configuration without YAML reader needs separate case.

### S06 / T04

Mapped: `tests/a2/test_site_routes.py::test_pinned_pkgdown_article_routes`.

- Pinned build proves three supported paths; exclusions are tested statically, not in that build; recorded build provenance is limited to asserted version.

### S07 / T04

Mapped: `tests/a2/test_site_integration.py::test_routes_and_collisions`, `tests/a2/test_site_integration.py::test_custom_article_frontmatter_not_invented[output: custom::format]`, `tests/a2/test_site_integration.py::test_custom_article_frontmatter_not_invented[pkgdown:\n  as_is: true]`.

- Quarto/custom-extension and overlay config need direct incomplete integration cases retaining other checked routes.

### S08 / T04

Mapped: `tests/a2/test_site_routes.py::test_release_mode_and_destination[config0-True]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config1-True]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config2-True]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config3-False]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config4-False]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config5-False]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config6-False]`, `tests/a2/test_site_routes.py::test_release_mode_and_destination[config7-False]`.

- Top-level destination and workflow PKGDOWN_DEV_MODE require direct integration assertions.

### S09 / T05

Mapped: `tests/a2/test_site_http.py::test_base_url_validation_normalization[https://EXAMPLE.org:443/pkg-https://example.org/pkg/]`, `tests/a2/test_site_http.py::test_base_url_validation_normalization[http://example.org:80/pkg/-http://example.org/pkg/]`, `tests/a2/test_site_http.py::test_base_url_validation_normalization[https://example.org/Pkg%2fslice/-https://example.org/Pkg%2Fslice/]`, `tests/a2/test_site_integration.py::test_url_rejects_unsafe_or_ambiguous_base[file:///etc/passwd]`, `tests/a2/test_site_integration.py::test_url_rejects_unsafe_or_ambiguous_base[https://user:pass@example.org/]`, `tests/a2/test_site_integration.py::test_url_rejects_unsafe_or_ambiguous_base[https://example.org/?q=1]`, `tests/a2/test_site_integration.py::test_url_rejects_unsafe_or_ambiguous_base[https://example.org/#x]`.

- Canonical source-url disagreement and absent-url success are not explicitly paired in tests.

### S11 / T05

Mapped: `tests/a2/test_site_http.py::test_sitemap_shape_and_bounds`, `tests/a2/test_site_integration.py::test_invalid_sitemap_never_missing_pages[<sitemapindex/>]`, `tests/a2/test_site_integration.py::test_invalid_sitemap_never_missing_pages[not xml]`, `tests/a2/test_site_integration.py::test_invalid_sitemap_never_missing_pages[<urlset><url><loc>https://foreign.org/other.html</loc></url></urlset>]`.

- Slow response 10-second bound and missing sitemap with absent source URL need direct cases; invalid/index/oversize are covered.

### G02 / T07

Mapped: `tests/a2/test_guardian.py::test_phase_arm_ack_sequence`, `tests/a2/test_guardian.py::test_stale_phase_request_does_not_execute`, `tests/a2/test_guardian.py::test_lost_phase_ack_never_releases_code`.

- Lost ack now covered; stale ack with current run/wrong sequence and rapid transition fault ordering need distinct cases.

### G03 / T07

Mapped: `tests/a2/test_guardian.py::test_heartbeat_age_and_stale_records[0.25-deadline]`, `tests/a2/test_guardian.py::test_heartbeat_age_and_stale_records[6-parent-loss]`.

- Both heartbeat/global orderings covered; simultaneous expiry and measured heartbeat update cadence missing.

### G04 / T08

Mapped: `tests/a2/test_guardian.py::test_single_termination_owner_idempotence`.

- Termination record identity tested; repeated request idempotence and record-before-TERM ordering need instrumentation.

### G08 / T08

Mapped: `tests/a2/test_guardian.py::test_guardian_failure_emergency_cleanup`, `tests/a2/test_guardian.py::test_no_exception_signal_after_direct_child_reap`.

- Existing guardian failure occurs before child launch or after reap; live guardian death with a launched child and emergency ownership are not reproduced; PID reuse hypothesis unresolved.

### G10 / T08

Mapped: `tests/a2/test_guardian.py::test_monotonic_clock_and_scheduler_delay`.

- Shared monotonic metadata covered; wall-clock mutation and injected scheduling delay not exercised.

### I01 / T09

Mapped: `tests/a2/test_stdio.py::test_native_output_does_not_deadlock`.

- Large native capture covered; diagnostic tail <=1MiB and child/native JSON contamination need direct public report cases.

### I02 / T09

Mapped: `tests/a2/test_examples_r.py::test_running_evaluate_output_limit`, `tests/a2/test_examples_r.py::test_evaluate_spool_counts_text_once`, `tests/a2/test_stdio.py::test_shared_text_output_threshold`.

- Native sum and live evaluate single-count tests covered; combined stdout/stderr/condition/evaluate exact-byte budget case still missing.

### I04 / T09

Mapped: `tests/a2/test_stdio.py::test_checkpoint_and_marker_integrity`.

- Valid earlier checkpoint retained; malformed/partial/missing checkpoint variants need explicit no-match regressions.

### E01 / T10

Mapped: `tests/a2/test_readme.py::test_source_selection_and_ambiguity[README.Rmd]`, `tests/a2/test_readme.py::test_source_selection_and_ambiguity[README.qmd]`, `tests/a2/test_readme.py::test_source_selection_and_ambiguity[both]`, `tests/a2/test_readme.py::test_source_selection_and_ambiguity[md-only]`.

- Selection/no-source cases now covered; selected-source hidden state plus asserted rendered md needs combined real-R control.

### E03 / T10

Mapped: `tests/a2/test_readme.py::test_explicit_closed_fences[```r]`, `tests/a2/test_readme.py::test_explicit_closed_fences[~~~r]`, `tests/a2/test_readme.py::test_explicit_closed_fences[```{r label, eval=FALSE}]`, `tests/a2/test_readme.py::test_explicit_closed_fences[```{r label, include=FALSE}]`.

- Closed recognized fences covered; unterminated and unlabeled/Python/vignette execution exclusion need direct cases.

### E04 / T10

Mapped: `tests/a2/test_readme.py::test_all_located_skip_markers[# docs-check: skip]`, `tests/a2/test_readme.py::test_all_located_skip_markers[#| docs-check: skip]`, `tests/a2/test_readme.py::test_all_located_skip_markers[<!-- docs-check: skip -->]`, `tests/a2/test_readme.py::test_multiline_string_is_not_pasted_output`.

- Markers and quoted multiline #> covered; immediate prior nonblank HTML marker boundary missing.

### E05 / T11

Mapped: `tests/a2/test_readme.py::test_body_precedence_and_conflicts`, `tests/a2/test_readme.py::test_conflicting_global_defaults_fail_preflight`.

- Body precedence and conflicting globals covered; supported literal knitr/Quarto defaults and dynamic global/template cases missing.

### E06 / T11

Mapped: `tests/a2/test_readme.py::test_supported_visibility_options[warning-warning=FALSE-Warning: hidden]`, `tests/a2/test_readme.py::test_supported_visibility_options[message-message=FALSE-Message: hidden]`, `tests/a2/test_readme.py::test_supported_visibility_options[stdout-results="hide"-[1] 1]`.

- Warning/message/results exclusions covered; full supported option subset and boolean engine metadata need direct cases.

### E07 / T11

Mapped: `tests/a2/test_readme.py::test_unsupported_options_preflight[error=TRUE]`, `tests/a2/test_readme.py::test_unsupported_options_preflight[fig.path='plots/']`, `tests/a2/test_readme.py::test_unsupported_options_preflight[eval=variable]`, `tests/a2/test_readme.py::test_unsupported_options_preflight[child='x.Rmd']`, `tests/a2/test_readme.py::test_unsupported_options_preflight[results='asis']`, `tests/a2/test_readme.py::test_all_unsupported_options_are_reported`, `tests/a2/test_readme.py::test_quarto_defaults_report_all_unsupported_options`.

- All-options reporting covered; numeric error option and no-runtime preflight sentinel for every unsupported family need cases.

### E09 / T11

Mapped: `tests/a2/test_readme.py::test_unsupported_assertions_preserve_supported_comparison`, `tests/a2/test_readme.py::test_coverage_partition_and_exclusions[False]`, `tests/a2/test_readme.py::test_coverage_partition_and_exclusions[True]`.

- One checked/five excluded and excluded-only now covered with portable replay fixture; real-R exclusion-only side-effect sentinel still missing.

### N01 / T12

Mapped: `tests/a2/test_comparison.py::test_documented_precision_cases[0.19-0.20-match]`, `tests/a2/test_comparison.py::test_documented_precision_cases[0.19-0.20001-output]`, `tests/a2/test_comparison.py::test_documented_precision_cases[1e-04-2e-04-match]`, `tests/a2/test_comparison.py::test_documented_precision_cases[1.00e-04-1.02e-04-output]`, `tests/a2/test_comparison.py::test_documented_precision_cases[-0.19--0.20-match]`, `tests/a2/test_comparison.py::test_documented_precision_cases[55%-36 %-output]`, `tests/a2/test_comparison.py::test_documented_precision_cases[55%-0.55-shape]`, `tests/a2/test_comparison.py::test_documented_precision_cases[1,234-1234-shape]`, `tests/a2/test_comparison.py::test_documented_precision_cases[NA-NaN-output]`, `tests/a2/test_comparison.py::test_documented_precision_cases[Inf--Inf-output]`, `tests/a2/test_comparison.py::test_documented_precision_cases[label [1] 1-other [1] 1-shape]`, `tests/a2/test_comparison.py::test_documented_precision_cases[[1] 1 2-[1] 1-shape]`, `tests/a2/test_examples_r.py::test_normative_precision[0.19-0.20-match]`, `tests/a2/test_examples_r.py::test_normative_precision[0.19-0.2001-output]`, `tests/a2/test_examples_r.py::test_normative_precision[1e-04-0.0001-match]`, `tests/a2/test_examples_r.py::test_normative_precision[p < 0.001-p = 2.2e-16-match]`, `tests/a2/test_examples_r.py::test_normative_precision[p < 0.001-p = 0.002-output]`, `tests/a2/test_examples_r.py::test_normative_precision[55%-36 %-output]`, `tests/a2/test_examples_r.py::test_normative_precision[55%-0.55-shape]`, `tests/a2/test_examples_r.py::test_normative_precision[1,234-1234-shape]`, `tests/a2/test_examples_r.py::test_normative_precision[NA-NA-match]`.

- Not every approved comparison table row is independently present: 0.1900, 0.1648 and 0.19 versus 0.164 need exact parameter rows.

### N03 / T12

Mapped: `tests/a2/test_examples_r.py::test_expression_subsequence_no_reuse`.

- Undocumented earlier expression cannot match documented later expression; repeated documented lines cannot reuse one actual line needs explicit test.

### N04 / T12

Mapped: `tests/a2/test_examples_r.py::test_unstable_output_remains_unverified[packageVersion("evaluate")-[1] 999]`, `tests/a2/test_examples_r.py::test_unstable_output_remains_unverified[Sys.Date()-[1] "1900-01-01"]`, `tests/a2/test_examples_r.py::test_unstable_output_remains_unverified[runif(1)-[1] 999]`.

- Unseeded and unstable fields covered; earlier explicit seed versus later seed needs native cases.

### R01 / T13

Mapped: `tests/a2/test_examples_r.py::test_fresh_ordered_hidden_setup`.

- Fresh ordered hidden setup covered; eval-false side-effect and independent package/file session isolation need native sentinels.

### R03 / T13

Mapped: `tests/a2/test_examples_r.py::test_dependency_preflight_no_install`.

- Missing package dependency covered; portable missing Rscript/pkgload/evaluate/required knitr variants need exact engine-list assertions.

### R07 / T14

Mapped: `tests/a2/test_examples_cli.py::test_native_chunk_deadline`.

- Native deadline uses one-second global budget; separately limiting chunk deadline and retaining earlier native result need focused case.

### R08 / T14

Mapped: `tests/a2/test_examples_cli.py::test_file_loading_deadline`.

- Loading/global limit exercised; distinct file budget and default public-limit configuration not asserted.

### D04 / T18

Mapped: `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/guides/docs-audit.md-terms0]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/tutorials/fix-a-docs-check-finding.md-terms1]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/workflows/index.md-terms2]`, `tests/a2/test_docs.py::test_walkthroughs_and_site_content[docs/quickstart.md-terms3]`.

- Guide/tutorial/workflows/quickstart text checks exist; REFCARD/cards and all changed rendered-content observations remain aggregate work.

### D05 / T19

Mapped: `tests/a2/test_docs.py::test_version_and_agent_mirror`.

- Version and mirror gates covered; status/count accuracy and boundary prohibitions need explicit assertions.

### V01 / T20

Mapped: `tests/a2/test_release_verifier.py::test_manifest_mapping_and_collection`, `tests/a2/test_release_verifier.py::test_removed_normative_paragraph_or_table_row_rejected`.

- Ledger omission cases covered; verifier does not independently detect removed inventory row if ledger mapping is rewritten; source-to-inventory reconciliation must be bound.

### V04 / T20

Mapped: `tests/a2/test_release_verifier.py::test_evidence_identity_and_versions[candidate_sha]`, `tests/a2/test_release_verifier.py::test_evidence_identity_and_versions[lock_hash]`, `tests/a2/test_release_verifier.py::test_evidence_identity_and_versions[manifest_hash]`, `tests/a2/test_release_verifier.py::test_evidence_identity_and_versions[collection_run_id]`, `tests/a2/test_release_verifier.py::test_evidence_identity_and_versions[reported_r_checked]`.

- Identity API cases do not validate main entry runtime/platform/fixture hashes comprehensively.

### V05 / T21

Mapped: `tests/a2/test_release_ci.py::test_both_platforms_locked_runtime`.

- Dedicated workflow_dispatch matrix exists, but approved spec additionally names a2-release under ci.yml; CI integration not realized.

### H01 / T22

Mapped: `tests/a2/test_evidence.py::test_committed_defect_replay`.

- Generated known-finding regressions pass; caught/eligible/pending historical replay and provenance-backed historical source/sitemap substitute not yet recorded.

### H02 / T22

Mapped: `tests/a2/test_evidence.py::test_package_coverage_triage`.

- Controlled triage file facts checked; exact all-six-count/reason/source-hash triage schema needs strengthening and candidate-bound actual dogfood refresh.

### F01 / T23

Mapped: `tests/a2/test_final_gates.py::test_gate_record_validation[missing-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[missing-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[missing-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[missing-requirement_mapping]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[failed-requirement_mapping]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[stale-requirement_mapping]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-full_gates]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-rendered_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-adversarial_review]`, `tests/a2/test_final_gates.py::test_gate_record_validation[no-provenance-requirement_mapping]`.

- Artifact hashes and minimum facts checked; actual full-gate logs/check names/source binding are not yet inspected by aggregate producer.

### F02 / T23

Mapped: `tests/a2/test_final_gates.py::test_review_record_validation`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[bare-claim]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[missing-file]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[wrong-hash]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[escaping-path]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[wrong-candidate]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[wrong-producer]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[empty-facts]`, `tests/a2/test_final_gates.py::test_observation_artifact_validation[unresolved-review]`.

- Unresolved review rejected; real finalized review coverage, complete mapping, both retrieved platform artifacts and observation producers pending.

## Execution dependency

Close the listed fixture/validator gaps and review their oracles before making required.json ready. Reconcile the independent ledger with the unchanged approved spec. Then commit a stable candidate, run the actual locked acceptance collection on Ubuntu 24.04 and macOS 14, retrieve both artifacts, and produce candidate/run-bound live, triage, full-gate, rendered-review and finalized adversarial-review observations. Only then can the aggregate gate certify acceptance. No CI dispatch, source publication, or release has occurred.

## Closed reporting coverage

C02–C06 now cover ambiguous package scope and negative-budget no-execution checks, all four stage states preserving a planted Rd/NAMESPACE signature error, all 18 severity/threshold/completeness combinations, mixed completed warnings and incomplete stages, text/JSON info visibility, missing-Rscript diagnostics through the real optional-stage dispatcher, and mixed successful/unavailable package aggregation. These are portable reporting checks; they do not establish native runtime or platform acceptance.

Verification: 51 reporting cases passed; full suite 1205 passed with 4 existing skips; test-all 47/47. Exact-spec ledger and all 306 collected-node ownership checks passed; pending manifest rejection remains verified.

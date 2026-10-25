"""Developer R skips are explicit; the release invocation fails its preflight."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest

R_FUNCTIONS = {
    "test_distinct_chunk_deadline_retains_checkpoint", "test_distinct_file_deadline_and_defaults",
    "test_source_hidden_state_and_rendered_assertion", "test_repeated_expected_line_cannot_reuse_output",
    "test_seed_order_does_not_retroactively_verify", "test_excluded_only_has_no_side_effect",
    "test_package_sessions_and_eval_false_isolation",
    "test_warn_only_and_complete_mismatch",
    "test_running_evaluate_output_limit", "test_evaluate_spool_counts_text_once",
    'test_clean_and_planted_stale_output', 'test_fresh_ordered_hidden_setup',
    'test_source_success_does_not_clear_rendered', 'test_native_chunk_deadline',
    'test_expression_subsequence_no_reuse', 'test_one_upstream_failure_stops_same_chunk',
    'test_r_script_packaged_and_parses',
    'test_unstable_output_remains_unverified', 'test_hidden_warning_does_not_hide_stdout',
    'test_medfit_layout_counts_and_release_gates',
    'test_rendered_unpaired_counts',
    'test_working_tree_load_identity', 'test_committed_defect_replay',
    'test_visibility_and_conditions_channels', 'test_dependency_preflight_no_install',
    'test_combined_stage_and_eco_partial_results',
    'test_file_loading_deadline', 'test_global_budget_across_packages', 'test_partial_cli_report_thresholds',
    'test_one_upstream_failure', 'test_pinned_pkgdown_article_routes',
}


def pytest_addoption(parser):
    parser.addoption('--a2-release', action='store_true', help='Require the locked A2 R runtime; skips cannot satisfy release evidence.')


def runtime():
    r=shutil.which('Rscript')
    if not r:return None
    from .runtime_probe import installed
    return installed(json.loads((Path(__file__).parent/'fixture-lock.json').read_text()),r)


def pytest_collection_modifyitems(config, items):
    available=runtime()
    if config.getoption('--a2-release'):
        lock=json.loads((Path(__file__).parent/'fixture-lock.json').read_text())
        if not shutil.which("npm"):
            raise pytest.UsageError("A2 release requires npm for actual packaging evidence")
        if available is None or any(available[k]!=lock[k] for k in ('R','R_packages')):
            raise pytest.UsageError('A2 release requires exact fixture-lock R/dependency versions; no developer skip waiver')
    elif available is None:
        for item in items:
            if item.originalname in R_FUNCTIONS:
                item.add_marker(pytest.mark.skip(reason='Developer-only: A2 R dependencies unavailable; release preflight forbids this skip'))

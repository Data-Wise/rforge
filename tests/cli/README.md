# rforge CLI dogfood + e2e tests

This directory holds standalone shell-based dogfooding and end-to-end tests for
rforge. They complement the pytest suite (`python3 -m pytest tests/`) and
`tests/test-all.sh` by exercising the plugin surface and public `lib/` module
CLIs from the outside.

## Files

| File | Purpose | Runtime |
|------|---------|---------|
| `automated-tests.sh` | Plugin structure, version sync, and lib module smoke tests | ~10–20s |
| `e2e-tests.sh` | End-to-end runs against `tests/fixtures/` packages | ~20–60s |
| `interactive-tests.sh` | Human-guided QA for visual/output checks | manual |

## Running

```bash
# Automated dogfood tests
bash tests/cli/automated-tests.sh

# End-to-end fixture tests
bash tests/cli/e2e-tests.sh

# Interactive QA
bash tests/cli/interactive-tests.sh
```

All scripts are intended to be run from the repository root.

## Notes

- The `e2e-tests.sh` script skips tests that require R when `Rscript` is not on
  `PATH`.
- Interactive tests log responses to `tests/cli/logs/`.

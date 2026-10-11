# PROPOSAL: a `--fast` tier and a `--profile` view for `r:test`, `r:check`, `r:cycle`

**Status:** DRAFT, not applied. Written 2026-10-11 after the mediationverse CI-shortening work.
**For:** `~/projects/dev-tools/rforge` (no files there were changed).
**Name when filed:** `PROPOSAL-fast-tier-and-test-profile.md` (rforge's root `PROPOSAL-*.md` convention).

## TL;DR

- **Add `--fast`** to `r:test`, `r:check` and `r:cycle`: `NOT_CRAN=false` (so `skip_on_cran()` tests are skipped) and, in the check, no re-run of the tests and no vignettes.
- **Add `--profile`** to `r:test`: per-test timing plus which tests are `skip_on_cran()`-gated, so the slow ones are visible without an ad hoc script.
- **Recommendation:** ship both as flags on existing commands (no new command, so the 44-command count and its sync checks stay untouched), then delete the per-repo `scripts/check-local.sh` copies once `--fast` covers them.

## Why

Today (2026-10-11) the same fast local gate was copied into six repos as `scripts/check-local.sh`, and one ad hoc script was used to profile medrobust. Both are generic R-package tooling, and rforge already owns the `r:*` dev-cycle commands:

| Need | What rforge has today | Gap |
|---|---|---|
| Run tests locally | `r:test` (`testthat::test_local`) | no way to run the `NOT_CRAN=false` tier that PR CI uses |
| Test then check | `r:cycle` (document → test → check) | `R CMD check` re-runs the whole suite right after `r:test` already ran it |
| Find slow tests | nothing | per-test timing needed an ad hoc R script |

## Evidence behind the numbers

All measured locally on 2026-10-11 (one machine, which was under load for some runs, so timings are approximate).

- **Duplicate test run:** in probmed, `R CMD check` re-running tests after `devtools::test()` took about 20 minutes on top of the test stage. `--no-tests` on the check removes it; the static test-dependency check still runs.
- **`NOT_CRAN` tier (medrobust):** 547 s with `NOT_CRAN=true` against 103 s with `NOT_CRAN=false`; 22 tests skipped; 0 failures. 8 heavy tests held about 70% of the time, and 14 cheap gated tests cost only 18 s.
- **CI confirmation:** with `NOT_CRAN=false` on PR runs, medrobust's check times fell from 15, 25 and 32 minutes to 7m13s, 7m15s and 10m5s (macOS, ubuntu, windows).
- **Fast gate across the packages** (script version with `--no-tests`, `--ignore-vignettes`): RMediation, mediationverse, medsim, medfit, probmed and medrobust all PASS locally with exit 0 (probmed's test stage was slow and varied from 133 s to 939 s on a loaded machine).

## Design

### `--fast` (on `r:test`, `r:check`, `r:cycle`)

| Command | Effect of `--fast` |
|---|---|
| `r:test` | run with `NOT_CRAN=false` in the R subprocess environment |
| `r:check` | `NOT_CRAN=false`; check args add `--no-tests` and `--ignore-vignettes`; build args add `--no-build-vignettes` |
| `r:cycle` | document, then `r:test --fast`, then `r:check --fast` (stops at first error, as today) |

**Mechanism (verified in the code, not run):** `lib/rsnippets.py` already passes environment variables to `rcmdcheck` through a named-character `env=` argument (the `--strict`/`--incoming` flavors set `_R_CHECK_*` that way), and `r_snippet(kind="test", ...)` builds a `testthat::test_local` call. `--fast` is the same pattern: add a `fast: bool` parameter to `r_snippet` and a `--fast` argument to the `rcmd` CLI, and set the variable for the `test` kind in the snippet or subprocess environment.

**Output must say what was skipped.** The `r:test` envelope already reports `skipped`; with `--fast` the report adds a line such as "fast tier: NOT_CRAN=false, N tests skipped (skip_on_cran)". The `r:check --fast` report adds "tests not re-run (--no-tests); vignettes not checked".

**Interaction with `--changed`:** the two-run merge-base baseline must use the same tier for both runs, or the introduced/pre-existing split is meaningless. `--fast` applies to both.

**Interaction with `--strict`/`--incoming`/`--as-cran`:** `--fast` and `--strict`/`--incoming` are mutually exclusive (strict grade runs `\donttest{}` and the full flavors). Reject the combination with a clear error.

### `--profile` (on `r:test`)

- Run the suite twice (`NOT_CRAN=false`, then `true`), join per test on file and name.
- Report per file: time, expectations, and which tests were skipped in the fast run (the `skip_on_cran()`-gated ones).
- Report the share of total time held by the gated tests and by the top five tests, and list gated tests under 5 s as candidates to un-gate (this found 14 in medrobust).
- Read-only: it runs tests but writes nothing into the package.
- Cost: roughly the sum of both tiers, so it is an on-demand analysis, not a default.

**Out of scope here:** CI step timings from GitHub logs (depends on `gh`; rforge's `ghrelease` module is the nearest home if ever wanted), and workflow-file edits (those belong to a shared workflow or the craft CI commands, not a local plugin).

## Acceptance tests (each must be able to fail)

1. **Unit:** `r_snippet("test", ..., fast=True)` contains `NOT_CRAN`; with `fast=False` it does not.
2. **Planted defect, tier effect:** a fixture package with one `skip_on_cran()` test: `r:test` reports it passed, `r:test --fast` reports it skipped. Remove the env setting and the second assertion must fail.
3. **Planted defect, check args:** a fixture package with a failing test: `r:check --fast` still reports the failure from the earlier `r:test --fast` stage in `r:cycle`, and `r:check --fast` alone does not run the tests (no testthat output in its log). An undocumented export must still fail `r:check --fast` with a WARNING.
4. **Mutual exclusion:** `--fast --strict` exits with an error and runs nothing.
5. **Docs gates:** `docs/commands.md` mentions `--fast` and `--profile` literally (`_check_commands_doc.py`), frontmatter `arguments:` updated, `gen_lib_reference.py --check` clean, `bash tests/test-all.sh` and `python3 -m pytest tests/` green.
6. **Parity with the shipped script:** on one real package (medrobust), `r:cycle --fast` and `scripts/check-local.sh` agree on pass/fail and on the skipped-test count.

## Options

| Option | Verdict |
|---|---|
| **A. Flags on existing commands (`--fast`, `--profile`)** | **Recommended.** No new command, so the 44-command count and its sync checks are untouched; smallest diff. |
| B. New commands (`r:fast`, `r:profile`) | Clearer discoverability, but every new command touches the count and docs sync checks and mkdocs nav. |
| C. Keep the per-repo `check-local.sh` copies | Already shipped and working, but six copies drift, and rforge's JSON envelope and `--changed` baseline are not available to them. |

## Rollout after rforge ships it

1. Release rforge with `--fast`/`--profile` (CHANGELOG, version sync, docs).
2. Verify parity (acceptance test 6).
3. Remove `scripts/check-local.sh` and `^scripts$` from the six repos in one small PR each (only if nothing else uses `scripts/`), or keep the script as a plugin-free fallback for machines without rforge. Decide then.

## Open questions

- Does `r:cycle --fast` need its own name for the combined run, or is the flag enough?
- Should `--fast` also skip `\donttest{}` examples explicitly? (`R CMD check` skips them unless `--run-donttest`, so probably no.)
- Is a plugin-free fallback worth keeping (the shell script), given rforge needs Claude Code and a Python 3.10+ environment?

## Not verified

- No change was made or run in rforge; the mechanism above is from reading `lib/rsnippets.py`, `lib/rcmd.py` and the command frontmatter.
- Timings are from one machine under varying load.
- `--profile`'s two-run design is based on the ad hoc script used today, not an rforge implementation.

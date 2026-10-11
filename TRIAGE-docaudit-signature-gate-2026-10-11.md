# Checkpoint B triage sheet — signature checks (T5/T6)

Prepared 2026-10-11 for the maintainer. Everything below was produced read-only (`git archive` into a temp dir;
no checkout, no write into medfit / probmed / medrobust). **Your part: fill the last column** (true / false / won't-fix).
Precision is recorded in the SPEC appendix after you do. Any `error`-severity row marked *false* demotes
`signature-named-arg` to `warn` (decision D7).

## 1. Hold-out: current `HEAD` of each package

| Package | Files audited | Coverage line | Findings |
|---|---|---|---|
| probmed | README + vignettes | checked 14 of 22 exported functions (1 no-usage, 7 variadic not checked) | **0** |
| medrobust | README + vignettes | checked 18 of 23 exported functions (4 no-usage, 1 variadic not checked) | **0** |
| medfit | README + vignettes | checked 11 of 22 exported functions (11 variadic not checked) | **1** (below) |

| # | Package | Check | Severity | Location | Finding | Triage |
|---|---|---|---|---|---|---|
| H1 | medfit | `signature-names` | warn | `vignettes/articles/model-native.qmd:23` | Listing `fit_sem(syntax, data)` names `syntax`; formals are `(model, data, information, n_starts, control, sampling_weights, se_type)` | ☐ true ☐ false ☐ won't-fix |

## 2. History replay (first-parent, checks: `signature-named-arg`, `signature-arity`)

`python3 tests/harness/replay.py replay --repo <pkg> --n 60 --checks signature-named-arg,signature-arity`

| # | Package | Window | Distinct findings | Detail | Triage |
|---|---|---|---|---|---|
| R1 | probmed | 60 commits | 0 | — | n/a |
| R2 | medfit | 60 commits | 0 | — (the SPEC's medfit hit is older than 60 first-parent commits; see R3) | n/a |
| R3 | medfit | 200 commits | 1 | `introduction.qmd:154` `BootstrapResult(converged = TRUE)`, present in 48 commits, newest `2b05958` (SPEC: introduced in `b40444e`) | ☐ true ☐ false ☐ won't-fix |
| R4 | medrobust | 60 commits | 4 (one call) | `methodology.qmd:115` `check_compatibility(sn0=, sp0=, psi_sn=, psi_sp=)`; formal is `psi`; present in 51 commits, newest `8ba673d`, fixed since (HEAD clean) | ☐ true ☐ false ☐ won't-fix |

R3 and R4 reproduce the SPEC's claim ("5 hits, all real"); R1/R2 were not in the SPEC's counts.

## 3. Known answer and planted defects

- **Known answer:** medfit `17d976d^` refcard `joint_effects(x, theta)` → flagged (2 `signature-names` findings, `refcard.qmd:13`);
  `17d976d` (fixed) → 0 findings. Real-history recall: `replay.py recall --scope signature` → **caught 1 of 1** firm eligible, exit 0.
- **Planted in a scratch copy of each hold-out's docs** (a bad named arg, an extra positional, a bad listing; the real repos are untouched):
  probmed `GaugePmedResult`, medrobust `as_sensitivity_region`, medfit `BootstrapResult` → **all three checks fired in all three packages**.
- **Positive controls** (`tests/fixtures/docaudit/controls/`): variadic arity, unique-prefix partial matching, nested/quoted/commented
  names, foreign `pkg::fn` → 0 findings.
- **Mutation checks:** removing the variadic exemption, the masking, the dots rule, the ambiguous-prefix rule or the
  foreign-namespace rule each turns at least one test red.

## 4. Gate status (plan Checkpoint B)

- [x] History replay ≥60 commits × medfit / medrobust / probmed
- [x] `replay.py recall --scope signature` caught k of n matches the signature rows (1 of 1 firm eligible)
- [x] Planted defects in a scratch copy of the hold-out docs are caught
- [x] Adversarial review #2 on the signature logic (two read-only agents; both had no shell, so their findings were static and re-verified by tests here; see section 5)
- [ ] Hold-out triage by you (table above)
- [ ] No `error`-severity false positive (R3/R4 are the only `error` rows; both await your call)

Blocked by: any `error`-severity false positive, an unresolved false-positive class, a red fixture, a raised exception.

## 5. Adversarial review #2 — findings and fixes

Both reviewers read the code without running it. Each item below got a regression test; hold-out, replay and recall results were rerun afterwards and are unchanged
(probmed 0, medrobust 0, medfit 1 at `HEAD`; same R3/R4 hits; recall 1 of 1).

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | `implemented_checks()` swallowed an import error, so a broken `lib.docaudit` read as "pending" and `recall` passed | harness false pass | import failure raises `AuditCrashed`; every in-scope row reports `crashed` |
| 2 | A row counted as caught on matching check + file only | harness weak | manifest rows may pin `function` / `arg`; refcard row pins `joint_effects` |
| 3 | `README.qmd` not extracted | harness | added to `TREE_PATHS` |
| 4 | `--allow-unavailable` also forgave a bad ref | harness | forgives only a missing checkout |
| 5 | Mutation self-test only exercised the stub | harness | added a test through the real `python -m lib.docaudit` subprocess (catch and miss) |
| 6 | String defaults in Rd usage (`sep = ")"`, `", "`) split or closed the call, giving a false `error` | **false positive (error)** | usage block is masked before splitting |
| 7 | Directory, dangling symlink or unreadable file named like a doc/Rd raised | contract | `is_file()` filter, `_read()` returns "" on `OSError`, `audit_package` never raises |
| 8 | Quadratic scan on a huge unclosed region (the test hung) | hang | regions and Rd usage over 200,000 chars are skipped |
| 9 | Escaped `\{` / `\}` unbalanced the Rd usage block | silent miss | escape-aware brace scan |
| 10 | Form feed shifted line numbers; unterminated fence at EOF dropped its block | minor | split on `\n` only; EOF fence is audited |
| 11 | A function defined in the doc itself (`f <- function(q) q; f(zz = 1)`) was checked against the package's formals | **false positive (error)** | per-file local definitions (`<-`, `=`, `<<-`, `\(`, `assign("f", ...)`) are skipped |
| 12 | Unlabeled fences (console output, error transcripts) were audited as R at `error` | **false positive (error)** | findings from unlabeled fences are downgraded to `warn` |

Not fixed (rare): an S3 generic without `...` whose methods take extra formals (reviewer's weaker candidate); two signatures for one name in one Rd keep the last.

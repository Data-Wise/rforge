# Checkpoint B triage sheet — signature checks (T5/T6)

Prepared 2026-10-11 for the maintainer. Everything below was produced read-only (`git archive` into a temp dir;
no checkout, no write into medfit / probmed / medrobust). **Your part: fill the last column** (true / false / won't-fix).
Precision is recorded in the SPEC appendix after you do. Any `error`-severity row marked *false* demotes
`signature-named-arg` to `warn` (decision D7).

## 0. How to triage (read this first)

**Why this step exists.** The checks passed every test I could write, but I wrote the tests. A hold-out triage is the one place
a person who knows the packages judges whether each thing the audit reports is a real documentation defect. Its result decides whether
`signature-named-arg` ships as `error` or `warn` (decision D7), and it is the last open item before T7-T17 can start.

**What you do.** For each of the three rows below, tick one box in its *Triage* cell (sections 1 and 2):

| Verdict | Meaning | Effect |
|---|---|---|
| **true** | The doc really is wrong: a reader copying it would hit an error or be misled | Counts toward precision; no action |
| **false** | The doc is fine and the audit is wrong | A false row of severity `error` demotes `signature-named-arg` to `warn` before release; any false row needs a fix for its false-positive class first |
| **won't-fix** | The doc is technically off but not worth changing | Counts as true for precision, no action |

Then tell me "triage done" (or paste the ticks); I record precision in the SPEC appendix, tick the gate boxes and start T7.
You do not need to run anything: the evidence for each row is below.

**Evidence and my reading** (a recommendation only; the call is yours):

| Row | What the doc says | What the code says | My read |
|---|---|---|---|
| H1 medfit `model-native.qmd:23` (`warn`, listing) | Routes table: `fit_sem(syntax, data)` | `man/fit_sem.Rd` formals are `(model, data, information, n_starts, control, sampling_weights, se_type)` | **Probably false** (revised after investigation, section 6): the same table cell continues `fit_mediation(model = syntax, engine = "native")`, so `syntax` is a variable holding the model string and `fit_sem(syntax, data)` is a valid call example, not a signature listing. It is a *class* of false positive (`signature-names` cannot tell a call example from a signature listing), so it blocks the gate until you choose a resolution (section 6), even though it is only `warn` |
| R3 medfit `introduction.qmd:154` (`error`, history only) | `BootstrapResult(estimate = ..., ci_lower = ..., ..., converged = TRUE)` | `man/BootstrapResult.Rd` formals: `(estimate, ci_lower, ci_upper, ci_level, boot_estimates, n_boot, method, call)`, with no `converged` | **True**: the call would error. Present in 48 of the last 200 commits and already fixed at `HEAD` |
| R4 medrobust `methodology.qmd:115` (`error`, history only) | `check_compatibility(..., sn0 = 0.90, sp0 = 0.85, psi_sn = 1.5, psi_sp = 1.2)` | `man/check_compatibility.Rd` has a single `psi` formal (no `sn0`, `sp0`, `psi_sn`, `psi_sp`) | **True**: the call would error. Present in 51 of the last 60 commits and already fixed at `HEAD` |

If you agree with all three, the `error` check has no false positive in the hold-out and keeps its severity.
R3 and R4 were already confirmed as real defects in the SPEC's own replay; they are listed so the sheet is complete.

**What this does not prove.** The hold-out is small: three packages, one `HEAD` finding, two historical errors. A clean triage means no
*known* false positive, not none. The adversarial review (section 5) found and fixed three false-positive classes, and any new class that shows up later
gets a regression test and, if it is `error`-severity, the same demotion rule.

## 1. Hold-out: current `HEAD` of each package

| Package | Files audited | Coverage line | Findings |
|---|---|---|---|
| probmed | README + vignettes | checked 14 of 22 exported functions (1 no-usage, 7 variadic not checked) | **0** |
| medrobust | README + vignettes | checked 18 of 23 exported functions (4 no-usage, 1 variadic not checked) | **0** |
| medfit | README + vignettes | checked 11 of 22 exported functions (11 variadic not checked) | **1** (below) |

| # | Package | Check | Severity | Location | Finding | Triage |
|---|---|---|---|---|---|---|
| H1 | medfit | `signature-names` | warn | `vignettes/articles/model-native.qmd:23` | **Resolved 2026-10-11 by decision A (section 7): no longer reported.** Was:  Listing `fit_sem(syntax, data)` names `syntax`; formals are `(model, data, information, n_starts, control, sampling_weights, se_type)`. **Likely a call example, not a signature** (section 6) | ✅ false (call example), class fixed |
| H2 | medsim | `signature-named-arg` | **error** | `vignettes/missing-data-mediation.qmd:70, 84, 92` | 7 findings over 4 calls: `medsim_amputate(vars=, rate=)`, `medsim_scenario_missing(rate=, skew=, kurtosis=)`, `medsim_scenario_missing_grid(rates=, skew=)`. Verified against `R/dgm_amputate.R` at `d7b9b75`: the function has no `vars` or `rate` formal | ☐ true ☐ false ☐ won't-fix |

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
- [ ] No `error`-severity false positive (R3, R4 and H2 are the `error` rows; all three look true, all await your call)
- [x] No unresolved false-positive class (H1's class fixed by narrowing `signature-names`, section 7)

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

## 6. Further investigation (2026-10-11, after an advisor review of this sheet)

Three things the first version of the sheet got wrong or left thin.

**6.1 H1 is probably a false positive, and a class.** `signature-names` fires on any backticked single call with bare identifiers that are not
formals. In the `refcard` that is exactly right (`joint_effects(x, theta)`, the signature). In `model-native.qmd:23` the identifier is a variable
(`fit_mediation(model = syntax, …)` in the same cell). The two are told apart by context: the refcard span is the **first cell of a table row**
(a signature column); the `fit_sem` span is inside the *second* cell of a "Routes" row. Measured over 7 packages, 60 first-parent commits each:
`signature-names` produced 2 distinct findings, one true (refcard) and one likely false (this one), so its observed precision is about 50% on a very small sample.

Options (this changes the SPEC, so it is your decision):

| Option | Effect | Cost |
|---|---|---|
| **A (my recommendation): narrow `signature-names` to table first-cell spans** (the prototype's original rule) | Keeps the known-answer refcard catch; removes H1; no new config | Misses listings outside first-cell positions (none seen in the 7 packages) |
| B: keep as is and allowlist H1 via `docs.allowlist` (T9) | No code change | Every call example with a variable argument needs an allowlist entry: noisy |
| C: demote `signature-names` to `info` | Cannot mislead | Loses the one firm catch (refcard) as a visible finding; the recall row would need to move |

**6.2 More hold-out.** The sheet had 3 packages. At `HEAD`, all 7 git-tracked R packages in `~/projects/r-packages/active/` (read-only):

| Package | Calls checked | Named args checked | Findings |
|---|---|---|---|
| medfit | 74 | 47 | 1 (H1) |
| mediationverse | 7 | 0 | 0 |
| medrobust | 71 | 290 | 0 |
| **medsim** | 78 | 85 | **7 (H2, all `error`)** |
| missingmed | 82 | 163 | 0 |
| probmed | 0 | 0 | 0 |
| rmediation | 14 | 16 | 0 |

`medsim` is new evidence: a package outside the original hold-out where the audit found 4 broken calls in one vignette (checked against the R source),
with no false positive. Fixing those is a medsim task, not part of this plan.

**6.3 Denominators.** The SPEC's "337 named arguments at HEAD, 0 false positives" reproduces exactly: medfit 47 + medrobust 290 + probmed 0 = 337.
Across all 7 packages the audit checks **326 calls and 601 named arguments**. Two limits to state plainly:
(1) **probmed contributes nothing**: its docs contain no call to a checkable (exported, non-variadic, documented) function, so "probmed: 0 findings" says nothing about probmed.
(2) The SPEC's 20,468 named-argument figure for the 120-commit replay was not recomputed here; the history replay reports distinct findings, not argument counts.
About half of the exports in each package (variadic, no usage, methods) are not checkable at all, which the "checked N of M" line reports.

**6.4 Process note.** Both adversarial reviewers were `feature-dev:code-reviewer`, which has no shell, so they could only read the code. Any further review should use
an agent type with Bash so it can run its repro cases.

## 7. Decision A applied (2026-10-11)

You chose option A: `signature-names` now judges only backticked calls that are the whole first cell of a Markdown table row.

- **Code:** `Region.first_cell` set in `extract_regions`; `check_region` requires it for the listing check (`lib/docaudit.py`).
- **Tests:** call examples outside a first cell are not judged (the `fit_sem(syntax, data)` case); `extract_regions` marks only whole-first-cell spans; an end-to-end package has a refcard row flagged and a Routes row not. `pytest tests` 726 passed, 4 skipped; `test-all.sh` 45 of 45.
- **Re-measured:** known-answer and `recall --scope signature` unchanged (1 of 1 caught). Over 7 packages at `HEAD`: medfit now 0 findings (was 1), medsim 7 (all `error`, true), the rest 0. `signature-names` history replay on medfit: the two refcard findings only.
- **Docs:** SPEC rule row, plan T6 and the ORCHESTRATE item updated with the narrowing and its reason.

**Still yours to tick:** H2 (medsim, `error`, verified true against the R source), R3 and R4 (`error`, history only, true). Then precision is recorded and the gate closes.

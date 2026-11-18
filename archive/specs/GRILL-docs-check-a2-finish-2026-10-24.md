# Grill: finish A2 (docs:check --site, --run-examples) — 2026-10-24

Target: plan to finish A2 on `codex/docs-check-a2` — phase 3 (H01 historical replay, H02
package-triage schema), phase 4 (F01/F02 gate and review records), two-platform CI evidence,
rebase/merge, PR, release. Branch state at grill time: `a9473ff`, nothing pushed, `dev` merged in
(`70970a2`), phases 1–2 done, each followed by a Codex adversarial review.

## Locked decisions

| # | Branch | Decision | Why |
|---|---|---|---|
| 1 | CI timing | Run the Ubuntu 24.04 + macOS 14 workflows now as a smoke run, before phases 3–4. | Every process-ownership test has only run on macOS; evidence is candidate-bound, so a late Linux failure would invalidate H/F evidence. A final run on the last commit is still required. |
| 2 | Trigger | Leak-scan the branch diff vs `dev`, push `codex/docs-check-a2`, then `gh workflow run "RForge CI" --ref codex/docs-check-a2`. No PR. | `ci.yml` runs on push to main/dev, PRs to them, and `workflow_dispatch`; a bare feature-branch push triggers nothing. `a2-platform.yml` is `workflow_call` only (called as job `a2-release`). |
| 3 | Live evidence | H01/H02 run against pinned temp clones (`git clone --local` at a recorded SHA) of rmediation, medrobust, medfit; record SHA + content hash. | Satisfies the no-cross-repo-write rule; R code in README replay may write files; evidence is reproducible. Reflects committed state, not uncommitted edits. |
| 4 | Archive timing | Keep the ~19 root A2 planning/review files in place through PR, merge and release; archive to `archive/specs/` post-release. | `scripts/verify_a2_release.py:139-140` hard-codes the SPEC and ACCEPTANCE paths and `tests/a2/requirements.json` names the r5 review; moving earlier edits the verifier mid-acceptance. |
| 5 | Review rigor | Remaining Codex reviews get a writable `TMPDIR` in the scratchpad and must report executed test counts; any review without executed tests is labeled "static" in the F02 record. | The phase-2 reviewer executed zero tests (no writable temp dir); a static read must not be filed as the executed G08 review. |

## Gates attached to the decisions

- **Before push (decision 2):** scan `git diff dev...codex/docs-check-a2` for tokens, keys, `.env` values and personal
  paths; the branch carries local evidence JSON and review files. Any hit blocks the push.
- **Push is outward-facing:** the user chose the dispatch-on-pushed-branch option; announce before pushing.
- **Smoke run is not final evidence:** it does not satisfy F01/F02. Re-run on the last commit.

## Open questions (not grilled, carry into planning)

- G08: the broad review still needs executed process tests on both platforms (smoke run covers it only after the run is retrieved and reviewed).
- D04: aggregate rendered-content inspection against the final candidate.
- Python pin: revision 8 selects latest stable Python 3; the smoke run's recorded interpreter must be checked against the evidence schema.
- Merge direction after PR: squash to `dev` per workflow; `dev` already merged into the branch, so a squash should be conflict-free unless `dev` moves.
- `stash@{0}` in the A2 worktree (older `.STATUS` handoff lines) is unresolved; drop or pop deliberately.

## Handoff

Locked ledger feeds the existing PLAN/TASKS (T21–T22, F01/F02). Next executable step: leak-scan, then push + dispatch (announce first).

## Round 2 — candidate freeze (2026-10-24)

Code facts found first: `scripts/run_a2_release.py` refuses to run unless `required.json` and every group are `ready`; evidence binds to candidate SHA and manifest hash; `a2-release.yml` downloads an `a2-acceptance-evidence` artifact from one numeric run ID, and nothing in the repo produces it.

| # | Question | Decision | Rejected alternative |
|---|---|---|---|
| 1 | Can a group with external evidence still pending be `ready`? | Yes: `ready` = every test mapped, evidence required externally; each coverage_gaps entry rewritten as a named observation | Third state `ready-pending-evidence` (changes the frozen gate) |
| 2 | Who produces the single observations run? | New dispatch-only `a2-observations.yml`: CI computes full gates, rendered hashes, live smoke, triage from pinned GitHub clones; review and mapping records supplied as attested dispatch inputs | Hand-assembled artifact (cannot carry a real run ID) |
| 3 | What ends the review-fix loop? | Zero confirmed blockers, max 3 rounds; each fix is a new candidate with a fresh review | Delta-only review (verifier needs reviewed_commit == candidate) |
| 4 | Merge method for the PR | Merge commit, one-off exception to the squash default, so the evidenced SHA stays in history | Squash (SHA binding lost) |
| 5 | Local paths in two evidence files | Strip to placeholders before the freeze; no history rewrite | Leave them / force-push rewrite |

Open: the attested-input limit must be stated in docs/guides/docs-audit.md and the PR body; triage clones need medfit/probmed/medrobust SHAs pushed to GitHub; the new workflow is itself part of the first review round.

## Round 2 follow-up — blocker found while executing (2026-10-24)

Q5 done (paths stripped, commit on the A2 branch). While designing `a2-observations.yml`: `--site` returns `checked: 0` on every real package tried (4 Data-Wise, 7 public r-lib/tidyverse) because all set pkgdown development mode, which A2 marks unsupported. `live_smoke` requires `checked > 0`, so it cannot pass on any real package. Decision pending from the user: how to define the live smoke. Package SHAs are pushed and all three triage repos are public (clone works in CI).

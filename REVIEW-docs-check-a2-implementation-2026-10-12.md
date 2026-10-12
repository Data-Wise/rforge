# A2 implementation adversarial review — 2026-10-12

Claude job: `7552c408-ce8b-42e5-b73b-6e95c14177bd`; standard Sonnet review, read-only. Verdict: needs-attention. This was a partial read-through, not a line-by-line revision 7 contract review or test execution.

## Validated disposition

- Confirmed: nested-package site paths and workflow discovery. Fixed by full-tree Git paths, Git-owned package prefix, and repository-root workflows; nested-package regression added.
- Confirmed: missing independent fixture/runtime evidence and aggregate CI verification. Added separate-process R/HTTP oracles, runner-owned runtime identity, allowlisted evidence fields, release-verifier invocation and downloaded-artifact aggregate job. Acceptance mapping and actual two-platform evidence remain pending.
- Confirmed: leader reaping could permit process-group ID reuse during signalling. Retain the leader unreaped until signalling finishes; macOS uses zombie observation and excludes zombie-only groups from signalling. Startup now observes heartbeat sequence advances.
- Rejected as conflicting with the approved contract: converting the poll-observed output threshold into a hard storage limit, discarding valid earlier checkpoints after a later deadline, and ignoring unsupported figure options. The spec expressly allows polling overshoot, retains earlier valid results, and requires unsupported options to make coverage incomplete. Diagnostic retention remains bounded to 1 MiB per stream as specified.

## Coverage limitation

Claude skipped the R worker, provisioning script, acceptance tests and manifests, planning documents, documentation and agent instructions. These areas still require independent acceptance verification; this review does not satisfy a claim of exhaustive contract coverage.

## Original review

```json
{
  "verdict": "needs-attention",
  "summary": "Two defects in code that is already written, plus two release-pipeline gaps that fail closed. The guardian and R example code read as largely sound on a read-through. I ran no code. The only command I ran was a read-only `git ls-tree` in a subdirectory, to confirm the monorepo finding. I could not compare against SPEC revision 7 line by line.",
  "findings": [
    {
      "severity": "high",
      "title": "Site audit returns an empty route set for a package in a repo subdirectory",
      "body": "`git ls-tree -r --name-only <sha>` runs with cwd=root. In a subdirectory it returns only that subtree, with paths relative to cwd. I confirmed this in `lib/`. The code keeps only paths with `p.startswith(prefix)` and then strips `prefix`. For a nested package where `prefix` is e.g. `pkg/`, every path is dropped. `expected` is empty, `_pkgdown.yml` is never found, and `config['url']` is never checked. All sitemap article and reference routes are then reported as `site-extra-page`, and the stage still ends `complete`. The `head_paths` check `prefix + file not in head_paths` mixes relative and full paths, so every working-tree page is labelled 'dirty-tree'. `select_ref` also reads `.github/workflows` from `root`, not the repo top level, so a nested package misses its deployment workflow and silently falls back to `main`.",
      "file": "lib/_docsite.py",
      "line_start": 180,
      "line_end": 222,
      "confidence": 0.9,
      "recommendation": "Use `ls-tree --full-tree`, or `--full-name` with consistent prefix stripping. Resolve workflows from `git rev-parse --show-toplevel`. Add a nested-package fixture test."
    },
    {
      "severity": "high",
      "title": "Nothing produces the independent R/HTTP fixture evidence the verifier requires",
      "body": "The runner needs `fixture-executions.json`, and the verifier needs `R`, `R_packages`, `reported_r_checked` and `reported_http_checked`. A repo-wide grep found no code that writes any of them, so no run can pass `validate_run`. This fails closed, so it is a missing implementation and not a false pass. The CI workflow also never runs `verify_a2_release.py main` or `validate_aggregate` across the two platform artifacts. The requirement ledger, spec hash, runtime lock and cross-platform checks are therefore never run in CI. Once something writes `fixture-executions.json`, it will be a file in the same output directory the pytest run can write to. Pytest-side code could then forge the 'independent' oracle. `evidence.update(...)` would also let that file overwrite `candidate_sha` and the hashes.",
      "file": "scripts/run_a2_release.py",
      "line_start": 28,
      "line_end": 35,
      "confidence": 0.85,
      "recommendation": "Collect the R version and package versions in the runner with its own Rscript call. Write oracle evidence from a separate process with an allowlisted schema. Add a final CI job that downloads both artifacts and runs the verifier."
    },
    {
      "severity": "medium",
      "title": "Guardian output cap is poll-based and the process-group check can race with pgid reuse",
      "body": "The 10 MiB cap is checked by `stat` every 50 ms, so a fast writer can emit far more before SIGTERM, and nothing caps the file size. After `process.poll()` reaps the leader, `killpg(pid, 0)` and the later SIGTERM/SIGKILL use a pgid that can be recycled once the group is empty, so a late `killpg` could hit an unrelated group. The window is small. During startup the guardian never reads `heartbeat.json`, so a parent slower than 5 s to arm is declared 'parent-loss' while still alive. This is inferred from the code.",
      "file": "lib/_docguardian.py",
      "line_start": 37,
      "line_end": 128,
      "confidence": 0.6,
      "recommendation": "Apply `RLIMIT_FSIZE` to the child. Only call `killpg` while the leader is unreaped, or track group members. Read heartbeats in the startup loop too."
    },
    {
      "severity": "low",
      "title": "Partial results counted after a deadline kill; raw child output embedded in the report",
      "body": "After a `deadline` or `output-limit` termination, records already written to `result.json` still increment `counts['checked']`, although the stage is marked incomplete. Up to 1 MiB each of R stdout and stderr is copied into `stage['provenance']`. R inherits the full environment, so tokens that README code prints could leak into the report. Any option beyond the supported literals, such as `fig.width`, raises and blocks the whole README as incomplete. That is conservative and may over-block real packages.",
      "file": "lib/_docexamples.py",
      "line_start": 183,
      "line_end": 211,
      "confidence": 0.55,
      "recommendation": "Count a segment as checked only when the lifecycle completed. Truncate or redact diagnostic output. Consider ignoring harmless options such as `fig.*`."
    }
  ],
  "next_steps": [
    "Fix the ls-tree prefix handling in `_docsite.audit` and add a nested-package test.",
    "Implement independent fixture-execution and R-version/package evidence collection, and add a CI aggregate verification job.",
    "Harden guardian output limiting and pgid handling."
  ],
  "coverage": {
    "files_examined": [
      "lib/_docguardian.py",
      "lib/_docsite.py",
      "lib/_docexamples.py",
      "lib/docaudit.py",
      "scripts/verify_a2_release.py",
      "scripts/run_a2_release.py",
      "tests/a2/release_capture.py",
      ".github/workflows/a2-release.yml"
    ],
    "files_skipped": [
      "lib/r/docexamples.R",
      "scripts/provision_a2.R",
      "tests/a2/test_*.py",
      "tests/a2/conftest.py",
      "tests/a2/required.json",
      "tests/a2/requirements.json",
      "tests/a2/evidence/*",
      "SPEC/PLAN/REVIEW/ACCEPTANCE/TASKS markdown",
      "docs/*",
      "commands/*",
      "agents/*"
    ],
    "areas": [
      "process ownership and deadlines",
      "README expression extraction and options",
      "site route and source selection",
      "release verifier and CI"
    ]
  },
  "uncertainty": "medium",
  "budget_exhausted": false,
  "recommended_followup": {
    "profile": "deep",
    "focus": [
      "Python-to-R handshake in docexamples.R: phase-request, arm-ack and phase-release sequencing",
      "Guardian chunk deadlines",
      "Independence of the fixture oracle from pytest",
      "Pending manifests and external live evidence"
    ],
    "reason": "I did not read the R side of the handshake or the tests, and I did not check the code against SPEC revision 7 line by line."
  },
  "evidence_lease_exhausted": false,
  "cost_budget_exhausted": false,
  "turn_limit_reached": false
}
```

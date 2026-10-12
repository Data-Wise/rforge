# Claude adversarial review — A2 revision 5

Read-only review; findings remain unvalidated. No implementation or spec edits.

{
  "job_id": "b8eabeb8-b649-455e-93b5-35a7eb2a1955",
  "ok": true,
  "operation": "review",
  "review_kind": "adversarial",
  "subject_kind": "changes",
  "subject_label": "working tree (staged, unstaged, and untracked)",
  "subject_fingerprint": "59a82c4936e929b95141bf31c92249c6e0879378801b50838488eb2c1e30fb88",
  "usage_summary": "Usage: tokens=221355 output=15472 turns=6 duration_ms=110431 api_ms=109887 cost_usd=0.34187580000000006",
  "total_tokens": 221355,
  "total_cost_usd": 0.34187580000000006,
  "cumulative_chain_cost_usd": 0.34187580000000006,
  "parent_job_id": null,
  "num_turns": 6,
  "duration_ms": 110431,
  "duration_api_ms": 109887,
  "task_profile": null,
  "review_profile": "standard",
  "requested_model": "sonnet",
  "effective_models": [
    "claude-sonnet-5-5"
  ],
  "effort": "medium",
  "budget": {
    "max_turns": 12,
    "finalize_at_turn": 9,
    "soft_budget_usd": 1,
    "max_budget_usd": 1,
    "timeout_ms": 240000
  },
  "evidence_lease": null,
  "evidence_lease_exhausted": false,
  "cost_budget_exhausted": false,
  "turn_limit_reached": false,
  "result": "{\"verdict\":\"needs-attention\",\"summary\":\"Revision 5 fixes most of what it set out to fix: a coverage partition, one global deadline that survives parent loss, a combined output cap, and a POSIX-only release manifest. It is honest about what it can't verify. Five problems remain. (1) For README.Rmd or README.qmd plus a rendered README.md, the rev 5 rules mean nothing executes and the stage stays INCOMPLETE (exit 2 under any threshold). (2) The release manifest omits the fixtures rev 5 adds, the final-gates list never mentions the manifest verifier, and the \\\"supported POSIX platform\\\" is undefined. (3) Guardian and parent enforce the same deadline, and the kill ordering is unspecified. (4) Skip markers and excluded counts can let a mostly unchecked README report complete. (5) The output-cap wording is ambiguous. Source/render pairing is deferred honestly, but the deferral makes the stage unusable for the common Rmd/qmd layout. Checked against the shipped code: the exit-code contract matches lib/docaudit.py main, the engine_missing aggregation claim is accurate, and the _invoke_r description is accurate. CI is ubuntu-only with no R, so the release gate has no evidence source today. No code exists, so these are spec-level findings. No runtime behavior was tested.\",\"findings\":[{\"severity\":\"high\",\"title\":\"Rmd/qmd + rendered md is usually permanently incomplete and executes nothing\",\"body\":\"The spec compares only literal `#>` assertions in the selected source. It counts rendered-md `#>` groups as unverified whenever md is not executed, and that makes the stage incomplete \\\"including when the source has no assertions\\\". In a typical README.Rmd or README.qmd the `#>` lines exist only in the knitted README.md, and the source has none. Rev 5 also says that with no eligible assertions \\\"setup does not execute\\\". So for the common pkgdown/usethis layout, and probably the probmed README.qmd that motivated the hidden-state rules, A2 would run no R and always report incomplete, exiting 2 under any `--fail-on` threshold. The stage is honest but effectively vacuous for its main target. The hidden-state, eval/include and stale-output logic would only run for hand-pasted `#>` in the source, or for md-only packages. The spec states the pairing deferral but not this consequence, or that CI users with a threshold set get an exit 2 they cannot clear. The claim about how common this layout is among the target packages is inferred. The real probmed README.qmd was not checked.\",\"file\":\"SPEC-docs-check-a2-2026-10-12.md\",\"line_start\":118,\"line_end\":135,\"confidence\":0.8,\"recommendation\":\"State the consequence explicitly and add a distinct reason code (for example `rendered-unpaired`). Decide deliberately whether unpaired rendered output should block gates or be an info-level coverage gap. Add a gate counting how many of medfit, probmed and medrobust get any executed assertion.\"},{\"severity\":\"medium\",\"title\":\"Manifest ignores rev 5 fixtures; final-gates list omits the verifier; POSIX platform undefined\",\"body\":\"The rev 4 manifest lists setup/source selection, clean/planted output, chunk/global deadlines, guardian parent-loss, group-child cleanup, large native output, CLI exit cases, and local HTTP and route fixtures. Rev 5 adds required fixtures for acknowledgement loss, rapid phase transitions, guardian failure, parent loss that does not reset the global deadline, and output-cap overshoot. Rev 4 also requires mixed-package engine_missing aggregation tests. None of these are manifest entries, so a release can pass the manifest while skipping them. The 'Required final gates' bullet was never updated to include the manifest verifier, and still allows R tests to skip when R is unavailable. The verifier has no owner, location or evidence store. .github/workflows/ci.yml runs ubuntu-latest only, with Python 3.11-3.13, plain pytest and test-all, and no R. The \\\"declared supported POSIX release platform\\\" in the final paragraph is never declared. macOS and Linux differ on process-group, session and monotonic-clock behavior.\",\"file\":\"SPEC-docs-check-a2-2026-10-12.md\",\"line_start\":456,\"line_end\":465,\"confidence\":0.85,\"recommendation\":\"Name and provision the release platform. Add the verifier to the final-gates list as a CI job or a documented manual step, with its evidence location. Reconcile the \\\"skip when unavailable\\\" sentence as developer-suite only. Add every rev 4 and rev 5 fixture to the manifest, or state that each normative MUST needs a manifest row.\"},{\"severity\":\"medium\",\"title\":\"Guardian and parent enforce the same absolute deadline with unspecified ordering\",\"body\":\"Rev 5 has the guardian enforce \\\"the same absolute global deadline\\\" plus at most 2 s grace and a 5 s cleanup wait. The parent also enforces that deadline and writes the partial-result envelope. If both fire together, the guardian can kill R before the parent reads the last checkpoint, and the parent cannot tell its own timeout from a guardian kill. The spec does not say whether the guardian's kill time is the deadline or the deadline plus grace. It does not say how the parent learns the guardian acted. Guardian worst case (7 s) uses most of the 10 s reserved for cleanup and reporting, which leaves about 3 s for the report. The clock source and heartbeat channel are not stated. On POSIX hosts a monotonic clock may not advance during suspend, and a stall longer than 5 s could trip the heartbeat. The ambiguity is confirmed. The races and the clock behavior are speculative.\",\"file\":\"SPEC-docs-check-a2-2026-10-12.md\",\"line_start\":562,\"line_end\":569,\"confidence\":0.6,\"recommendation\":\"Make the guardian a strict backstop at deadline plus parent grace, with the parent killing first. Define a marker-file signal that distinguishes parent-observed from guardian-observed termination. State the clock source and heartbeat channel. Add a deadline-collision fixture.\"},{\"severity\":\"medium\",\"title\":\"Excluded counts and skip markers can complete a mostly unchecked stage\",\"body\":\"\\\"Mixed checked/excluded coverage may complete\\\" has no minimum checked amount. A README with one trivially matching assertion and many `docs-check: skip` or `eval=false` groups reports complete. An in-source skip marker behaves like suppression, yet the spec says suppression never conceals incomplete stages. The spec treats the marker as legitimate exclusion but does not say so. Excluded is also mostly reachable only in md-only mode, because of the pairing deferral.\",\"file\":\"SPEC-docs-check-a2-2026-10-12.md\",\"line_start\":552,\"line_end\":556,\"confidence\":0.6,\"recommendation\":\"Declare skip markers to be exclusions rather than suppression. Always show the excluded/checked ratio in the headline. Consider a minimum checked policy, or an info finding when excluded exceeds checked.\"},{\"severity\":\"low\",\"title\":\"10 MiB output cap wording is ambiguous and detection-only\",\"body\":\"The cap \\\"covers stdout/stderr capture files and structured textual evaluate output together, counted once per captured channel\\\". \\\"Together\\\" implies one shared total and \\\"once per channel\\\" reads as per-channel accounting. The spec does not say whether evaluate output also echoed to stdout is double-counted. Enforcement is 100 ms polling with overshoot reporting, and there is no hard limit such as an RLIMIT_FSIZE on the capture files. Native writes can overshoot between polls. Filesystem writes outside the capture files are already declared out of scope.\",\"file\":\"SPEC-docs-check-a2-2026-10-12.md\",\"line_start\":571,\"line_end\":574,\"confidence\":0.5,\"recommendation\":\"Define the cap as one shared total with a worked counting example. Describe it as detection-only, or add a hard per-file limit. Keep the overshoot fixture.\"},{\"severity\":\"low\",\"title\":\"Stray sentence blurs unreleased (info) versus missing from selected ref (warn)\",\"body\":\"The historic missing-page regression bullet ends with the fragment \\\"unreleased pages are evidence of a deployment gap, not a missing deployed page.\\\" Site rule 5 says unreleased pages are info and pages missing from the selected ref stay warn. The fragment looks pasted from an earlier revision and could be read as making unreleased pages the warn case.\",\"file\":\"SPEC-docs-check-a2-2026-10-12.md\",\"line_start\":330,\"line_end\":337,\"confidence\":0.5,\"recommendation\":\"Delete the fragment or rewrite it to match Site rule 5.\"}],\"next_steps\":[\"Count source versus rendered `#>` assertions in the medfit, probmed and medrobust READMEs to decide the Rmd+md policy.\",\"Revise the release-manifest and verifier section: name the platform, make the verifier a final gate, and add the rev 4 and rev 5 fixtures.\",\"Specify the guardian/parent protocol as a small state machine covering the heartbeat channel, kill ordering and marker states.\",\"Define the skip-marker and excluded-ratio policy and the single shared output-cap counting rule.\",\"Delete the stray unreleased-pages sentence in the verification section.\"],\"coverage\":{\"files_examined\":[\"SPEC-docs-check-a2-2026-10-12.md\",\"archive/specs/SPEC-docs-check-content-audit-2026-10-11.md\",\"lib/docaudit.py\",\"lib/rcmd.py\",\"tests/test_rcmd.py\",\"commands/docs/check.md\",\"agents/orchestrator.md\",\"tests/_check_agent_engines.py\",\".github/workflows/ci.yml\"],\"files_skipped\":[\"tests/test_docaudit_scope.py\",\"docs/guides/docs-audit.md\",\"the real probmed README.qmd\",\"lib/docaudit.py extract_regions and audit_package bodies\",\"pkgdown, knitr and evaluate external documentation\"],\"areas\":[\"coverage accounting\",\"acknowledged phase starts\",\"guardian deadlines and parent loss\",\"output caps\",\"POSIX release gates\",\"exit-code contract\",\"source/render pairing deferral usability\"]},\"uncertainty\":\"medium\",\"budget_exhausted\":false,\"recommended_followup\":{\"profile\":\"standard\",\"focus\":[\"Dry-count source versus rendered `#>` assertions in medfit, probmed and medrobust to settle the Rmd+md policy\",\"Review a revised release-manifest/verifier section with a named platform\",\"Review the guardian/parent protocol as a state machine\"],\"reason\":\"The main finding depends on the real README layouts of the target packages, which were not inspected. The manifest and guardian issues need a revised spec section before they can be judged resolved.\"},\"turn_limit_reached\":false,\"cost_budget_exhausted\":false,\"evidence_lease_exhausted\":false}",
  "structured_output": {
    "verdict": "needs-attention",
    "summary": "Revision 5 fixes most of what it set out to fix: a coverage partition, one global deadline that survives parent loss, a combined output cap, and a POSIX-only release manifest. It is honest about what it can't verify. Five problems remain. (1) For README.Rmd or README.qmd plus a rendered README.md, the rev 5 rules mean nothing executes and the stage stays INCOMPLETE (exit 2 under any threshold). (2) The release manifest omits the fixtures rev 5 adds, the final-gates list never mentions the manifest verifier, and the \"supported POSIX platform\" is undefined. (3) Guardian and parent enforce the same deadline, and the kill ordering is unspecified. (4) Skip markers and excluded counts can let a mostly unchecked README report complete. (5) The output-cap wording is ambiguous. Source/render pairing is deferred honestly, but the deferral makes the stage unusable for the common Rmd/qmd layout. Checked against the shipped code: the exit-code contract matches lib/docaudit.py main, the engine_missing aggregation claim is accurate, and the _invoke_r description is accurate. CI is ubuntu-only with no R, so the release gate has no evidence source today. No code exists, so these are spec-level findings. No runtime behavior was tested.",
    "findings": [
      {
        "severity": "high",
        "title": "Rmd/qmd + rendered md is usually permanently incomplete and executes nothing",
        "body": "The spec compares only literal `#>` assertions in the selected source. It counts rendered-md `#>` groups as unverified whenever md is not executed, and that makes the stage incomplete \"including when the source has no assertions\". In a typical README.Rmd or README.qmd the `#>` lines exist only in the knitted README.md, and the source has none. Rev 5 also says that with no eligible assertions \"setup does not execute\". So for the common pkgdown/usethis layout, and probably the probmed README.qmd that motivated the hidden-state rules, A2 would run no R and always report incomplete, exiting 2 under any `--fail-on` threshold. The stage is honest but effectively vacuous for its main target. The hidden-state, eval/include and stale-output logic would only run for hand-pasted `#>` in the source, or for md-only packages. The spec states the pairing deferral but not this consequence, or that CI users with a threshold set get an exit 2 they cannot clear. The claim about how common this layout is among the target packages is inferred. The real probmed README.qmd was not checked.",
        "file": "SPEC-docs-check-a2-2026-10-12.md",
        "line_start": 118,
        "line_end": 135,
        "confidence": 0.8,
        "recommendation": "State the consequence explicitly and add a distinct reason code (for example `rendered-unpaired`). Decide deliberately whether unpaired rendered output should block gates or be an info-level coverage gap. Add a gate counting how many of medfit, probmed and medrobust get any executed assertion."
      },
      {
        "severity": "medium",
        "title": "Manifest ignores rev 5 fixtures; final-gates list omits the verifier; POSIX platform undefined",
        "body": "The rev 4 manifest lists setup/source selection, clean/planted output, chunk/global deadlines, guardian parent-loss, group-child cleanup, large native output, CLI exit cases, and local HTTP and route fixtures. Rev 5 adds required fixtures for acknowledgement loss, rapid phase transitions, guardian failure, parent loss that does not reset the global deadline, and output-cap overshoot. Rev 4 also requires mixed-package engine_missing aggregation tests. None of these are manifest entries, so a release can pass the manifest while skipping them. The 'Required final gates' bullet was never updated to include the manifest verifier, and still allows R tests to skip when R is unavailable. The verifier has no owner, location or evidence store. .github/workflows/ci.yml runs ubuntu-latest only, with Python 3.11-3.13, plain pytest and test-all, and no R. The \"declared supported POSIX release platform\" in the final paragraph is never declared. macOS and Linux differ on process-group, session and monotonic-clock behavior.",
        "file": "SPEC-docs-check-a2-2026-10-12.md",
        "line_start": 456,
        "line_end": 465,
        "confidence": 0.85,
        "recommendation": "Name and provision the release platform. Add the verifier to the final-gates list as a CI job or a documented manual step, with its evidence location. Reconcile the \"skip when unavailable\" sentence as developer-suite only. Add every rev 4 and rev 5 fixture to the manifest, or state that each normative MUST needs a manifest row."
      },
      {
        "severity": "medium",
        "title": "Guardian and parent enforce the same absolute deadline with unspecified ordering",
        "body": "Rev 5 has the guardian enforce \"the same absolute global deadline\" plus at most 2 s grace and a 5 s cleanup wait. The parent also enforces that deadline and writes the partial-result envelope. If both fire together, the guardian can kill R before the parent reads the last checkpoint, and the parent cannot tell its own timeout from a guardian kill. The spec does not say whether the guardian's kill time is the deadline or the deadline plus grace. It does not say how the parent learns the guardian acted. Guardian worst case (7 s) uses most of the 10 s reserved for cleanup and reporting, which leaves about 3 s for the report. The clock source and heartbeat channel are not stated. On POSIX hosts a monotonic clock may not advance during suspend, and a stall longer than 5 s could trip the heartbeat. The ambiguity is confirmed. The races and the clock behavior are speculative.",
        "file": "SPEC-docs-check-a2-2026-10-12.md",
        "line_start": 562,
        "line_end": 569,
        "confidence": 0.6,
        "recommendation": "Make the guardian a strict backstop at deadline plus parent grace, with the parent killing first. Define a marker-file signal that distinguishes parent-observed from guardian-observed termination. State the clock source and heartbeat channel. Add a deadline-collision fixture."
      },
      {
        "severity": "medium",
        "title": "Excluded counts and skip markers can complete a mostly unchecked stage",
        "body": "\"Mixed checked/excluded coverage may complete\" has no minimum checked amount. A README with one trivially matching assertion and many `docs-check: skip` or `eval=false` groups reports complete. An in-source skip marker behaves like suppression, yet the spec says suppression never conceals incomplete stages. The spec treats the marker as legitimate exclusion but does not say so. Excluded is also mostly reachable only in md-only mode, because of the pairing deferral.",
        "file": "SPEC-docs-check-a2-2026-10-12.md",
        "line_start": 552,
        "line_end": 556,
        "confidence": 0.6,
        "recommendation": "Declare skip markers to be exclusions rather than suppression. Always show the excluded/checked ratio in the headline. Consider a minimum checked policy, or an info finding when excluded exceeds checked."
      },
      {
        "severity": "low",
        "title": "10 MiB output cap wording is ambiguous and detection-only",
        "body": "The cap \"covers stdout/stderr capture files and structured textual evaluate output together, counted once per captured channel\". \"Together\" implies one shared total and \"once per channel\" reads as per-channel accounting. The spec does not say whether evaluate output also echoed to stdout is double-counted. Enforcement is 100 ms polling with overshoot reporting, and there is no hard limit such as an RLIMIT_FSIZE on the capture files. Native writes can overshoot between polls. Filesystem writes outside the capture files are already declared out of scope.",
        "file": "SPEC-docs-check-a2-2026-10-12.md",
        "line_start": 571,
        "line_end": 574,
        "confidence": 0.5,
        "recommendation": "Define the cap as one shared total with a worked counting example. Describe it as detection-only, or add a hard per-file limit. Keep the overshoot fixture."
      },
      {
        "severity": "low",
        "title": "Stray sentence blurs unreleased (info) versus missing from selected ref (warn)",
        "body": "The historic missing-page regression bullet ends with the fragment \"unreleased pages are evidence of a deployment gap, not a missing deployed page.\" Site rule 5 says unreleased pages are info and pages missing from the selected ref stay warn. The fragment looks pasted from an earlier revision and could be read as making unreleased pages the warn case.",
        "file": "SPEC-docs-check-a2-2026-10-12.md",
        "line_start": 330,
        "line_end": 337,
        "confidence": 0.5,
        "recommendation": "Delete the fragment or rewrite it to match Site rule 5."
      }
    ],
    "next_steps": [
      "Count source versus rendered `#>` assertions in the medfit, probmed and medrobust READMEs to decide the Rmd+md policy.",
      "Revise the release-manifest and verifier section: name the platform, make the verifier a final gate, and add the rev 4 and rev 5 fixtures.",
      "Specify the guardian/parent protocol as a small state machine covering the heartbeat channel, kill ordering and marker states.",
      "Define the skip-marker and excluded-ratio policy and the single shared output-cap counting rule.",
      "Delete the stray unreleased-pages sentence in the verification section."
    ],
    "coverage": {
      "files_examined": [
        "SPEC-docs-check-a2-2026-10-12.md",
        "archive/specs/SPEC-docs-check-content-audit-2026-10-11.md",
        "lib/docaudit.py",
        "lib/rcmd.py",
        "tests/test_rcmd.py",
        "commands/docs/check.md",
        "agents/orchestrator.md",
        "tests/_check_agent_engines.py",
        ".github/workflows/ci.yml"
      ],
      "files_skipped": [
        "tests/test_docaudit_scope.py",
        "docs/guides/docs-audit.md",
        "the real probmed README.qmd",
        "lib/docaudit.py extract_regions and audit_package bodies",
        "pkgdown, knitr and evaluate external documentation"
      ],
      "areas": [
        "coverage accounting",
        "acknowledged phase starts",
        "guardian deadlines and parent loss",
        "output caps",
        "POSIX release gates",
        "exit-code contract",
        "source/render pairing deferral usability"
      ]
    },
    "uncertainty": "medium",
    "budget_exhausted": false,
    "recommended_followup": {
      "profile": "standard",
      "focus": [
        "Dry-count source versus rendered `#>` assertions in medfit, probmed and medrobust to settle the Rmd+md policy",
        "Review a revised release-manifest/verifier section with a named platform",
        "Review the guardian/parent protocol as a state machine"
      ],
      "reason": "The main finding depends on the real README layouts of the target packages, which were not inspected. The manifest and guardian issues need a revised spec section before they can be judged resolved."
    },
    "turn_limit_reached": false,
    "cost_budget_exhausted": false,
    "evidence_lease_exhausted": false
  },
  "session_id": "54154524-5264-4fc7-b4a8-06526f70e7cb",
  "resume_hint": "claude --resume 54154524-5264-4fc7-b4a8-06526f70e7cb",
  "disclosure": null,
  "usage": {
    "input_tokens": 1161,
    "cache_creation_input_tokens": 42144,
    "cache_read_input_tokens": 162578,
    "output_tokens": 15472,
    "output_tokens_details": {
      "thinking_tokens": 5516
    },
    "server_tool_use": {
      "web_search_requests": 0,
      "web_fetch_requests": 0
    },
    "service_tier": "standard",
    "cache_creation": {
      "ephemeral_1h_input_tokens": 42144,
      "ephemeral_5m_input_tokens": 0
    },
    "inference_geo": "not_available",
    "iterations": [
      {
        "input_tokens": 4,
        "output_tokens": 62,
        "cache_read_input_tokens": 42165,
        "cache_creation_input_tokens": 7695,
        "cache_creation": {
          "ephemeral_5m_input_tokens": 0,
          "ephemeral_1h_input_tokens": 7695
        },
        "type": "message"
      },
      {
        "input_tokens": 1151,
        "output_tokens": 3908,
        "cache_read_input_tokens": 49860,
        "cache_creation_input_tokens": 0,
        "cache_creation": {
          "ephemeral_5m_input_tokens": 0,
          "ephemeral_1h_input_tokens": 0
        },
        "type": "message"
      }
    ],
    "speed": "standard",
    "fallback_credit": null
  },
  "model_usage": {
    "claude-sonnet-5-5": {
      "inputTokens": 1161,
      "outputTokens": 15472,
      "cacheReadInputTokens": 162578,
      "cacheCreationInputTokens": 42144,
      "webSearchRequests": 0,
      "costUSD": 0.34187580000000006,
      "contextWindow": 1000000,
      "maxOutputTokens": 128000,
      "thinkingTokens": 5516,
      "canonicalModel": "claude-sonnet-5-5",
      "provider": "firstParty",
      "costBasis": "list"
    }
  }
}

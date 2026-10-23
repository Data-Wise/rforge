# Grill: personal Codex check pilot

Status: initial reviews complete and findings reconciled; runtime acceptance
blocked. No clean-review verdict is claimed. The instruction package is unchanged.

## Review and contract

Used agent-skills doubt-driven-development: a fresh-context agent review,
then the user-approved Codex CLI review. The CLI used gpt-5.6-sol, an ephemeral
session, and a read-only sandbox. Its input contained the adversarial prompt,
contract, spec, and two skills, without prior findings or session reasoning.
Gemini was unavailable in PATH. The first outer-sandbox startup failed; the
same approved invocation completed outside that sandbox, retaining the inner
read-only sandbox. Existing login and environment were unchanged.

Contract: a small personal adapter in the existing Rforge repo, reusing local
engines, preserving package scope, and distinguishing implementation from runtime
acceptance. No second GitHub repo, duplicate engines, new hooks, or full
command port.

## Reconciled findings

All six findings are valid and actionable. Engine behavior was inspected directly;
review severity labels are not treated as proof. No finding was dismissed as noise.

1. **Blocker: false-clean package output.** `lib/rcmd.py` parses unrecognized
   R output through `console_fallback`, then normalizes it without preserving
   structured-output provenance. A mocked R invocation returning unrecognized
   text and exit zero produced `status: ok` with empty check findings. The
   same happened for valid empty JSON findings. This establishes an engine
   limitation, not a real R-package check. Instruction-only changes cannot
   reliably recover lost provenance. A small existing-engine fix is needed;
   do not certify package-check success before it is addressed.
2. **Missing check logs.** `lib/rsnippets.py` emits check errors/warnings/notes;
   `lib/rcmd.py:normalize` exposes no check-log location. The skill/spec promise
   exceeds the current engine. Preserve and expose a real log when available,
   or explicitly report unavailable log evidence. An adapter JSON report must
   not be represented as the R check log.
3. **Default check differs from Claude.** `commands/r/check.md` defines the
   ordinary workflow as an `--as-cran` pass. The Codex skill's default omits
   that flag, and the Python CLI defaults it off. Align the skill's ordinary
   check with the documented Rforge default; honor an explicit plain-check request.
4. **Strict orchestration is missing.** Passing `--strict` to `lib.rcmd` adds
   `--run-donttest` to one check; it does not orchestrate the documented
   Suggests-withholding flavor passes. Spell out the existing flavor calls
   and incoming behavior in the skill, with separate results and run cost.
   Do not describe raw flag pass-through as full workflow parity.
5. **Docs scope can expand.** `lib.docaudit.resolve_scope` expands hybrid roots
   and manifest directories without `--eco`. Preflight the actual resolver
   before auditing; require explicit broader scope or report the unsupported
   single-package case. Reporting expansion afterward is insufficient.
6. **New-export coverage requires a ref.** `audit_package` computes coverage
   only with `--since REF`. A natural-language new-export request needs a
   supplied or established comparison ref; otherwise report coverage omitted.
   Checked-versus-total signature coverage is a different measurement.

## Smallest repair plan

Keep the same-repo architecture. First fix lost package-output provenance in
`lib.rcmd` with a focused regression test; decide actual log availability from
`rcmdcheck` before promising a path. Then correct the two skills' default,
strict orchestration, scope preflight, and comparison-ref instructions. Reuse
existing engines and flavor selectors; do not add a wrapper or new service.

This proposes a narrow exception to the original unchanged-engine constraint:
existing-engine safety/evidence repairs, not a replacement engine. It remains
unimplemented. Repeat focused review after repairs; a new external CLI run
requires its own invocation confirmation under the chosen skill.

## Verification and remaining gates

CLI second opinion completed on 2026-10-22. The engine probe confirmed the
false-clean limitation without running R or changing a package. Earlier test
counts remain historical evidence; they do not cover these newly identified
contracts. Post-restart discovery, real-package checks, and runtime acceptance
remain unverified. The installed 0.1.0 instructions still contain these gaps.

The unused standalone local scaffold remains inactive and unregistered. The
installed catalog points into this feature worktree; retain the worktree.
No push, PR, merge, release, or website deployment occurred.

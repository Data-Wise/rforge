# Spec: Rforge checks in Codex

Date: 2026-10-22. Status: instruction package implemented; review blockers
and runtime acceptance pending.

## Purpose and scope

Make Davood's frequent Rforge workflows available in Codex with little setup
or maintenance. Start with package checks and documentation checks, the first
priorities selected during discussion. Two skills are an initial slice, not a
technical limit or a claim of complete Rforge import. Add other frequent
workflows when selected, reusing the existing engines wherever possible.

## Packaging decision

Use a separate Codex plugin package inside the existing Rforge repository:
`openai/rforge-openai`. Keep its skills, manifest, and local catalog separate
from the Claude plugin, while sharing the existing Rforge engines. No separate
repository, duplicate engine, or new service is needed for this personal pilot.

## Implemented

The instruction-only package is `openai/rforge-openai`, version 0.1.0.
The bullets below describe its current instructions, not verified runtime
capabilities. Review found gaps between those instructions and engine behavior;
see the blockers below.

- `rforge-check` uses `python3 -m lib.rcmd --kind check` and reports the
  package, options, errors/warnings/NOTEs, log path, and next fix.
- `rforge-docs-check` uses `python3 -m lib.docaudit --format json` and reports
  resolved scope, findings, coverage, and incomplete/unavailable work.

Both skills resolve the user's package to an absolute path before running the
engine from the local Rforge checkout. The personal default engine location is
`/Users/davood/projects/dev-tools/rforge`; the checkout and Python 3.10+ must be
available. Package checks also require R and the existing engine's dependencies.
The package does not bundle or duplicate those engines.

Requested options pass through to the existing engine. Advanced options use
its current command documentation. Missing prerequisites, skipped stages,
malformed output, and incomplete scans must never be described as passing.
Documentation checks must distinguish checked exports from unchecked exports.

Package checks execute package code and can create build/check artifacts.
Documentation audits are static and read-only. Respect the target package's
instructions and holds. Neither skill authorizes dependency installation,
CRAN submission, releases, deployment, hook changes, or unrelated edits.

A local catalog and setup guide are prepared. Local installation reports the
package installed/enabled, and all four installed package files matched source
at installation. The catalog currently points into this feature worktree;
retain it until the registration is moved to a durable integration location.

## Review blockers before runtime acceptance

The fresh-context and approved CLI reviews are reconciled in
[the grill](GRILL-codex-check-skills-2026-10-22.md). Six actionable gaps remain:
malformed R output can normalize to a false-clean result; the engine exposes
no check-log path; the skill omits Rforge's default `--as-cran`; raw `--strict`
does not orchestrate the documented flavor passes; docs scope can expand
without `--eco`; and new-export coverage requires a comparison ref.

These are unimplemented repairs, not accepted runtime limitations. In particular,
the current engine cannot substantiate the promised malformed-output guarantee
or log evidence. Runtime acceptance is blocked until those contracts are repaired.
A narrow existing-engine safety/evidence repair is proposed, while retaining
shared engines and avoiding a wrapper or new service.

## Verified before runtime acceptance

- Both skill files passed frontmatter validation and Markdown lint.
- All 47 repository checks passed using Python 3.12; Python 3.15 causes
  unrelated generated-reference signature differences.
- The full Python suite passed: 899 tests, four skipped.
- Strict MkDocs build and rendered guide content inspection passed.
- Direct documentation-engine fixtures returned zero findings for the clean
  case and two for the defect case. Both checked only 1 of 22 exports, so these
  results establish bounded fixture behavior, not full API coverage.
- A direct package-engine call with a nonexistent package returned an error.

These checks validate files and existing engines; they do not establish that
Codex has loaded or correctly followed the installed skills.

## Runtime acceptance still required

After restarting Codex, use a selected R package to verify:

- [ ] Both installed skill names appear and can be invoked.
- [ ] Each skill targets the requested package while running from Rforge's
      checkout, including when the package path contains spaces.
- [ ] `rforge-docs-check` reports actual scope, findings, incomplete work, and
      export coverage accurately; it does not modify the package.
- [ ] `rforge-check` runs a real package check and reports its actual result
      and log location; unavailable dependencies remain explicit.
- [ ] A missing checkout or invalid package produces an unavailable/error
      explanation rather than a clean result.

Record the package, invocation, result, and limits when checking these boxes.
Runtime acceptance is complete only when the observations support every item.

## Outside this first slice

Full Claude command parity, new check engines, copied Claude hooks, background
jobs, and automatic submission are outside this pilot. Savant remains a
separate follow-up. No push, PR, published release, or live-site deployment is
claimed for these local changes.

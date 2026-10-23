---
name: rforge-docs-check
description: Audit R package README and vignette calls against exported API signatures using Rforge. Use to find stale argument names, arity mismatches, or undocumented new exports since a comparison ref.
---

# R documentation checks

Reuse Rforge's static audit; no R execution or network is required.

1. Resolve the user's target to an existing absolute path before changing
   execution directories. Read its instructions. By default choose one package
   with DESCRIPTION; do not substitute an ecosystem directory or another package.
2. Locate the user's Rforge checkout (personal default:
   `/Users/davood/projects/dev-tools/rforge`) or an explicitly supplied checkout.
   Verify `lib/docaudit.py` exists, Python is 3.10+, and the CLI help includes
   `--package-only`. Otherwise report an unavailable/older engine; do not run
   an unguarded audit or invent a Claude command or MCP.
3. From that checkout, with safely quoted paths, run:

   ```text
   python3 -m lib.docaudit --path /absolute/pkg --package-only --format json
   ```

   `--package-only` prevents hybrid/manifest scope expansion. Only for an
   explicit ecosystem request, replace it with `--eco`; these flags conflict.
   Check the returned scope matches the request before interpreting findings.
4. For undocumented **new** exports, use `--since REF`. Use a user-supplied or
   already established comparison ref; if absent, ask for it before the coverage
   run. A general docs audit may proceed without a ref, but must state that
   new-export coverage was not run. Do not guess a tag or confuse this with
   checked-versus-total signature coverage. A bad ref/coverage-skipped message
   is an unavailable coverage check, never a clean coverage result.
   Pass requested `--detailed` and `--fail-on none|warn|error` unchanged.
5. Report scope first, then `audited`, `incomplete`, `max_severity`, messages,
   and checked-versus-total export counts. Exit zero or `status: ok` alone does
   not prove a clean audit. Name unscanned regions and unchecked exports.
   Inspect flagged calls before recommending edits: pseudo-code may be intended.
   Summarize actionable findings with file locations. Stay read-only unless
   fixes are requested; regenerate Rd through the package's own tooling.

This audits README/vignette API content. It does not build sites, run examples,
test URLs, or establish that the published website is current.

---
name: rforge-docs-check
description: Audit R package README and vignette calls against exported API signatures using Rforge. Use to find stale argument names, arity mismatches, or undocumented new exports.
---

# R documentation checks

Use Rforge's static documentation audit; it requires no R execution or network.

1. Resolve the target package or ecosystem directory to an absolute path from
   the user's workspace before changing execution directories. Read its project
   instructions. Without an explicit ecosystem request, start with one package.
2. Locate the local Rforge checkout (personal default:
   `/Users/davood/projects/dev-tools/rforge`) and verify `lib/docaudit.py` exists.
   If absent, report the missing engine; do not invent a Claude command or MCP.
3. Use Python 3.10+ with that checkout as the tool's working directory:

   ```text
   python3 -m lib.docaudit --path /absolute/package/path --format json
   ```

   Quote paths safely. Pass requested `--detailed`, `--since REF`,
   `--fail-on none|warn|error`, or `--eco` through unchanged. Read
   `commands/docs/check.md` there when interpreting advanced options.
4. State the resolved scope first. Inspect `audited`, `incomplete`,
   `max_severity`, messages, and checked-versus-total export coverage.
   `status: ok` or exit zero alone does not establish a clean audit.
   Report unreadable or unscanned regions and unhandled exports as limitations.
5. Inspect flagged calls before recommending edits: pseudo-code can be
   intentional. Summarize actionable findings with file locations. Keep this
   audit read-only unless the user requests fixes; regenerate Rd documentation
   through the package's tooling rather than editing generated files.

This checks README/vignette API content. It does not build the documentation
site, execute examples, test URLs, or establish that the published website is
current. Report those as separate work when requested.

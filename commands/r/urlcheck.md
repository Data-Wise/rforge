---
name: rforge:r:urlcheck
description: Check package URLs for breakage/redirects (urlchecker)
argument-hint: "[package]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package URL Check

Run `urlchecker::url_check()` — a common CRAN rejection cause.
`urlchecker` is optional — if `engine_missing` includes it, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind urlcheck --path "<path>"
```

## Output Format
```markdown
## URL Check: {package} v{version}
### Status: {🟢 ok / 🟡 warn / 🔴 error}
{List urlcheck.broken: "- http://x — <message> → suggested: <new_url>"}
{If urlcheck.doi_blocked_count > 0: "ℹ️ {N} DOI URL(s) returned 403 (firewall) — advisory only, not a blocker."}
### Recommended Actions
{Replace redirected URLs with suggestions, fix dead links}
```

**Status semantics (v2.14.0+):**
- 🔴 `error` — real broken URLs (non-doi-403 failures)
- 🟡 `warn` — doi.org URLs returning 403 only (firewall blocks, not real breakage)
- 🟢 `ok` — no broken URLs

## Related Commands
- `/rforge:r:check` — broken URLs also flagged by R CMD check

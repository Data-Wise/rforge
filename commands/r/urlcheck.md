---
name: rforge:r:urlcheck
description: Check package URLs for breakage/redirects (urlchecker)
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
### Status: {🟢 0 / 🟡 {urlcheck.count} URLs}
{List urlcheck.broken: "- http://x — <message> → suggested: <new_url>"}
### Recommended Actions
{Replace redirected URLs with suggestions, fix dead links}
```

## Related Commands
- `/rforge:r:check` — broken URLs also flagged by R CMD check

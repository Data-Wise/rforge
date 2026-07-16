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
{For each urlcheck.advisory: "ℹ️ <url> — {blocked_class}: {evidence} — advisory only, not a blocker."}
### Recommended Actions
{Replace redirected URLs with suggestions, fix dead links}
{Do NOT "fix" advisory URLs — they are valid; changing them trades good citations for worse ones}
```

**Status semantics (evidence-based triage):**
- 🔴 `error` — genuinely broken: `dead` (404/DNS) or `real_403` (refused, site root reachable)
- 🟡 `warn` — advisory only: `bot_blocked` (site root also 403 → blanket WAF block) or
  `transient` (re-probe succeeded → rate-limit/UA misfire)
- 🟢 `ok` — no broken URLs

A 403 is a *refusal*, not a missing page. WAF-protected hosts (gov/research/publisher) refuse
R's user agent (`R (4.6.1 ...)`), so urlchecker reports valid links as broken. The normalizer
probes the site root and re-probes the URL to decide, and emits `evidence` for each downgrade.
`doi.org` keeps a no-network fast path (its root returns 200, so probing would misclassify it).

⚠️ **Scope limit:** reduces *local preflight noise only*. CRAN runs its own URL check with R's
user agent and cannot be configured — if CRAN emits a "possibly invalid URL" NOTE, explain it
in `cran-comments.md`.

## Related Commands
- `/rforge:r:check` — broken URLs also flagged by R CMD check

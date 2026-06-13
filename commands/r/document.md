---
name: rforge:r:document
description: Regenerate Rd docs and NAMESPACE (roxygen2)
argument-hint: "[package]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Documentation

Regenerate `man/*.Rd` and `NAMESPACE` via `roxygen2::roxygenize()`.

> Blessed regeneration path. The PreToolUse hook blocks *hand-edits* to
> `man/*.Rd`; running roxygen via this command (Bash) is allowed.

## Process
```bash
python3 -m lib.rcmd --kind document --path "<path>"
```

## Output Format
```markdown
## Document: {package} v{version}
### Status: {🟢/🔴}
{On success: "Regenerated man/ and NAMESPACE."}
### Recommended Actions
- Review: `git diff man/ NAMESPACE`
```

## Related Commands
- `/rforge:r:check` — verify docs after regenerating
- `/rforge:docs:check` — **detect** doc drift across packages (this **regenerates**)

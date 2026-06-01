---
name: rforge:r:style
description: Auto-format the package (styler) and show the diff
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Style

Reformat source via `styler::style_pkg()`. **This rewrites files.**
`styler` is optional — if `engine_missing` includes `styler`, report 🟡 + hint.

## Process
1. `python3 -m lib.rcmd --kind style --path "<path>"`
2. Then show what changed: run `git -C "<path>" diff --stat` via Bash and summarize.

## Output Format
```markdown
## Style: {package} v{version}
### Status: {🟢 reformatted / 🔴}
- Files changed: {style.count}
{git diff --stat summary}
### Recommended Actions
- Review: `git diff` · Undo if unwanted: `git checkout -- <files>`
```

## Related Commands
- `/rforge:r:lint` — find issues that styler does **not** auto-fix

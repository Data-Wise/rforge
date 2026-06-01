---
name: rforge:r:cycle
description: Full dev cycle — document → test → check (stops at first error)
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Dev Cycle

Run `document` → `test` → `check` in sequence, stopping at the first hard error.

## Process
```bash
python3 -m lib.rcmd --kind cycle --path "<path>"
```

## Output Format
```markdown
## Dev Cycle: {package}
### Status: {🟢 all ok / 🟡 warnings / 🔴 failed}
| Stage | Result |
|-------|--------|
| document | {stages[0].status dot} |
| test | {stages[1].status dot} |
| check | {stages[2].status dot} |
{If failed_stage: "Stopped at **{failed_stage}** — {detail summary}"}
### Recommended Actions
{Next steps based on the failing stage}
```

## Related Commands
- `/rforge:r:check`, `/rforge:r:test`, `/rforge:r:document` — individual stages
- `/rforge:thorough` — **ecosystem** rollup (this is **single-package**)

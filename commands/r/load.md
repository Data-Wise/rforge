---
name: rforge:r:load
description: Load the package into a namespace (pkgload::load_all) for dev
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Load

Simulate-install the package into a namespace via `pkgload::load_all()`.

## Process
```bash
python3 -m lib.rcmd --kind load --path "<path>"
```

## Output Format
```markdown
## Load: {package} v{version}
### Status: {🟢/🔴}
{On success: "Loaded {package} into the namespace."}
{On error or engine_missing: surface messages}
```

## Related Commands
- `/rforge:r:test` — load happens automatically inside test_local
- `/rforge:r:document` — regenerate docs after changing exports

---
name: rforge:r:install
description: Install the package locally (R CMD INSTALL) and report version
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Install

Install via `R CMD INSTALL`.

## Process
```bash
python3 -m lib.rcmd --kind install --path "<path>"
```

## Output Format
```markdown
## Install: {package} v{version}
### Status: {🟢 exit 0 / 🔴}
- Installed version: {install.installed_version}
{On error: surface messages (e.g. unmet dependencies)}
```

## Related Commands
- `/rforge:r:build` — build before installing

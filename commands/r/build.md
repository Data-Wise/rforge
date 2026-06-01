---
name: rforge:r:build
description: Build an R package tarball (pkgbuild) and report the artifact
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Build

Build a source tarball via `pkgbuild::build()`.

## Process
```bash
python3 -m lib.rcmd --kind build --path "<path>"
```

## Output Format
```markdown
## Build: {package} v{version}
### Status: {🟢/🔴}
- Artifact: `{build.artifact}`
- Size: {build.bytes / 1024} KB
```

## Related Commands
- `/rforge:r:check` — validate before building
- `/rforge:r:install` — install the built package

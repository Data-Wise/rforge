---
name: rforge:status
description: Ecosystem-wide status dashboard (health, packages, .STATUS aggregation)
arguments:
  - name: package
    description: Optional package to drill into (defaults to ecosystem-wide)
    required: false
    type: string
  - name: format
    description: Output format (text, json)
    required: false
    type: string
    default: "text"
---

# /rforge:status - Ecosystem Status Dashboard

Aggregate health, package inventory, and `.STATUS` information across the R package ecosystem.

## What It Does

Runs the in-plugin status module to summarize:
- Packages discovered (via the same discovery used by `/rforge:detect`)
- Per-package state (.STATUS, recent activity, basic health signals)
- Ecosystem-level rollup

## Usage

Invoke the status script via Bash. Default path is the current directory.

```bash
# Status for current directory
python3 -m lib.status --path . --format text

# Status for a specific path
python3 -m lib.status --path /path/to/packages --format text

# Machine-readable JSON
python3 -m lib.status --path . --format json
```

The same logic is importable as a Python API:

```python
from lib.status import build_status
result = build_status(".")
print(result)
```

## Use When

- Daily check-in on ecosystem state
- Before starting work on a package
- Verifying recent changes propagated

## Related Commands

- `/rforge:detect` - Identify ecosystem structure
- `/rforge:deps` - Visualize dependencies
- `/rforge:analyze` - Run full analysis

## Notes

Mode-aware depth (default/debug/optimize/release) and timing budgets from the previous MCP-backed
version were descoped in v1.3.0; the faithful Python port emits a single consistent view. If
mode-aware status returns in a future release, this command will gain a `--mode` flag.

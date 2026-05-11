---
name: rforge:init
description: Initialize rforge context for an R package directory (idempotent)
---

# /rforge:init - Initialize RForge Context

Set up rforge state for a single R package directory. Idempotent: running it again is safe and
will re-stamp the state file when invoked with `--quick`.

## What It Does

Runs the in-plugin init module to:
- Verify the target path looks like an R package (DESCRIPTION, etc.)
- Create the per-user state entry under `~/.rforge/`
- Stamp metadata so subsequent rforge commands recognize the package

## Usage

Invoke the init script via Bash. Default path is the current directory.

```bash
# Initialize current directory
python3 -m lib.init --path . --format text

# Initialize a specific package directory
python3 -m lib.init --path /path/to/RMediation --format text

# Re-stamp (skip the already-initialized guard)
python3 -m lib.init --path . --quick --format text

# Machine-readable JSON
python3 -m lib.init --path . --format json
```

The same logic is importable as a Python API:

```python
from lib.init import init_package
result = init_package(".")
print(result)
```

## Use When

- First time using rforge in a package
- Adding rforge to an existing package
- Re-initializing after wiping `~/.rforge/`

## Related Commands

- `/rforge:detect` - Auto-detect ecosystem structure
- `/rforge:status` - Status rollup once initialized

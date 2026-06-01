---
name: rforge:detect
description: Auto-detect R package project structure (single package, ecosystem, or hybrid)
arguments:
  - name: path
    description: Path to scan (defaults to current directory)
    required: false
    type: string
  - name: format
    description: Output format (text, json)
    required: false
    type: string
    default: "text"
---

# /rforge:detect - Project Structure Detection

Automatically detect your R package ecosystem structure.

## What It Does

Runs the in-plugin discovery module to analyze your current directory and identify:
- **Single package**: One (or zero) R packages
- **Ecosystem**: Multiple related R packages (like mediationverse)
- **Hybrid**: Multiple packages plus non-package projects (opt-in via `.rforge.yaml`)

## Usage

Invoke the discovery script via Bash. Default path is the current directory.

```bash
# Detect from current directory
python3 -m lib.discovery --path . --format text

# Detect from a specific path
python3 -m lib.discovery --path /path/to/packages --format text

# Machine-readable JSON
python3 -m lib.discovery --path . --format json
```

The same logic is also importable as a Python API:

```python
from lib.discovery import detect_ecosystem
eco = detect_ecosystem(".")
print(eco.kind, [p.name for p in eco.packages])
```

## Output

Returns project structure classification with:
- Number of packages found
- Dependency relationships
- Project type (single/ecosystem/hybrid)
- Recommended workflows

## Examples

### Single Package
```
📦 Single Package: medfit
Type: R Package
Location: ~/projects/r-packages/medfit
Status: Active development
```

### Ecosystem
```
🏗️ Ecosystem: mediationverse
Packages: 4 (medfit, probmed, medsim, mediationverse)
Structure: Core → Implementations → Meta
Dependencies: 3 internal
```

## Use When

- Starting work on unfamiliar project
- Planning ecosystem-wide changes
- Understanding project structure
- Before running other RForge commands

## Related Commands

- `/rforge:status` - Check health after detection
- `/rforge:deps` - Visualize dependencies
- `/rforge:analyze` - Run full analysis

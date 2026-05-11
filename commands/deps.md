---
name: rforge:deps
description: Build and visualize dependency graph across R package ecosystem
---

# /rforge:deps - Dependency Graph

Build and visualize dependency relationships in your R package ecosystem.

## What It Does

Runs the in-plugin deps module to:
- Parse DESCRIPTION files (`Imports`, `Depends`, `Suggests`, `LinkingTo`)
- Build the internal dependency graph
- Compute topological build order (leaves first)
- Detect circular dependencies
- Identify blocking packages

## Usage

Invoke via Bash:

```bash
# Dependency graph for the ecosystem (terminal output)
python3 lib/deps.py --path . --format text

# Machine-readable JSON
python3 lib/deps.py --path . --format json
```

The same logic is also importable as a Python API:

```python
from discovery import detect_ecosystem
from deps import build_graph
graph = build_graph(detect_ecosystem("."))
print(graph.layers)
```

## Output

Returns dependency analysis with:
- **Graph Structure**: ASCII or Mermaid diagram
- **Topological Order**: Safe update sequence
- **Depth Levels**: How deep each dependency goes
- **Circulars**: Any circular dependency issues

## Examples

### Ecosystem Dependencies
```
🔗 DEPENDENCY GRAPH

Level 0 (Core):
  └─ medfit

Level 1 (Implementations):
  ├─ probmed → medfit
  ├─ medsim → medfit
  └─ sensitivity → medfit

Level 2 (Meta):
  └─ mediationverse → medfit, probmed, medsim

Topological order: medfit → {probmed, medsim, sensitivity} → mediationverse
```

### Reverse Dependencies
```
🔗 REVERSE DEPS: medfit

Direct dependents: 3
  • probmed (suggests in 2 places)
  • medsim (imports 1 function)
  • sensitivity (depends)

Indirect dependents: 1
  • mediationverse (via probmed, medsim)

Total ecosystem impact: 4 packages
```

## Use When

- Planning version updates
- Understanding ecosystem structure
- Before making breaking changes
- Coordinating multi-package releases

## Related Commands

- `/rforge:impact` - See change impact
- `/rforge:cascade` - Plan coordinated updates
- `/rforge:release` - Plan CRAN submission order

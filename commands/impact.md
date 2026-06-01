---
name: rforge:impact
description: Analyze change impact across ecosystem packages
argument-hint: Optional description of changes (e.g., "Breaking API change in extract_mediation")
arguments:
  - name: package
    description: Package whose change is being analyzed
    required: false
    type: string
  - name: change-type
    description: Nature of change (breaking, feature, fix, refactor)
    required: false
    type: string
    default: "feature"
  - name: affected-exports
    description: Space-separated list of changed exports (e.g., "extract_mediation predict")
    required: false
    type: string
---

# /rforge:impact - Change Impact Analysis

Analyze the ripple effects of changes across your R package ecosystem.

## What It Does

Runs the in-plugin impact analysis (co-located with deps logic) to:
- Identify direct + indirect dependents of a package
- Compute the topological update sequence
- Estimate cascade workload (time)
- Assess risk level (low/medium/high)
- Recommend mitigation strategies

## Usage

Invoke via Bash. `--package` is required; `--change-type` defaults to `feature`.

```bash
# Analyze the impact of a breaking change to a package
python3 -m lib.deps --path . --format text impact \
    --package medfit --change-type breaking

# Other change types: feature | fix | internal
python3 -m lib.deps --path . --format text impact \
    --package medfit --change-type feature \
    --affected-exports extract_mediation predict

# Machine-readable JSON
python3 -m lib.deps --path . --format json impact --package medfit --change-type breaking
```

The same logic is also importable as a Python API:

```python
from lib.discovery import detect_ecosystem
from lib.deps import build_graph, analyze_impact
graph = build_graph(detect_ecosystem("."))
impact = analyze_impact(graph, "medfit", change_type="breaking")
print(impact.risk_level, impact.update_sequence)
```

## Output

Returns impact assessment with:
- **Severity**: LOW/MEDIUM/HIGH/CRITICAL
- **Affected Packages**: List with details
- **Cascade Workload**: Estimated time
- **Breaking Changes**: Functions/APIs affected
- **Mitigation**: Suggested strategies

## Examples

### Medium Impact
```
📊 IMPACT ANALYSIS

Severity: MEDIUM
Affected: 2 packages (probmed, medsim)

probmed:
  • 1 function call to update
  • Tests: 12 tests reference old API
  • Est. work: 2 hours

medsim:
  • 1 vignette example
  • Est. work: 1 hour

Total cascade: 3 hours
Recommended: Update & release in sequence
```

### High Impact (Breaking Change)
```
⚠️ IMPACT ANALYSIS

Severity: HIGH (Breaking change)
Affected: 3 packages + indirect

Direct Impact:
  • probmed: 5 functions, 47 test cases
  • medsim: 2 examples, 1 vignette
  • sensitivity: 1 function call

Indirect Impact:
  • mediationverse: May need meta-update

Total cascade: 8-12 hours
Recommended: Deprecation path + major version bump
```

## Use When

- Before making API changes
- Planning breaking changes
- Estimating release workload
- Coordinating ecosystem updates

## Related Commands

- `/rforge:deps` - See dependency structure
- `/rforge:cascade` - Plan coordinated updates
- `/rforge:docs:check` - Check documentation impact

---
name: rforge:cascade
description: Plan coordinated updates across dependent packages
argument-hint: Optional version or change description
---

# /rforge:cascade - Cascade Update Planner

Plan coordinated updates across your R package ecosystem dependencies.

## What It Does

Helps you:
- Create update sequence
- Identify blocking issues
- Estimate timeline
- Generate task checklist
- Coordinate CRAN submissions

## Usage

```bash
# Plan cascade for current changes
/rforge:cascade

# Plan for version bump
/rforge:cascade "medfit 2.2.0"

# Detailed cascade plan
/rforge:cascade --detailed
```

## Output

Returns cascade plan with:
- **Update Sequence**: Topological order
- **Per-Package Tasks**: What needs updating
- **Timeline**: Estimated completion
- **Blockers**: Issues to resolve first
- **CRAN Strategy**: Submission sequence

## Examples

### Simple Cascade
```
🔄 CASCADE PLAN: medfit 2.1.0 → 2.2.0

Phase 1: Core (Week 1)
  1. medfit
     ✓ Update version
     ✓ Run tests
     ✓ Update NEWS.md
     ⏱ 2 hours

Phase 2: Implementations (Week 2)
  2. probmed
     • Update medfit dependency
     • Re-run tests
     ⏱ 1 hour

  3. medsim
     • Update medfit dependency
     • Update vignette
     ⏱ 2 hours

Phase 3: Meta (Week 2)
  4. mediationverse
     • Update all dependencies
     ⏱ 30 min

Total time: 5.5 hours over 2 weeks
```

### Breaking Change Cascade
```
⚠️ CASCADE PLAN: Breaking API change

Phase 1: Preparation (Week 1)
  1. Add deprecation warnings
  2. Update all docs
  3. Create migration guide
  ⏱ 4 hours

Phase 2: Core Package (Week 2)
  1. medfit → 3.0.0 (major bump)
     • Implement breaking changes
     • Update all tests
     ⏱ 8 hours

Phase 3: Dependent Updates (Weeks 3-4)
  2-4. Update all dependents
       Each: API migration + tests
       ⏱ 12 hours total

Phase 4: Meta Package (Week 5)
  5. mediationverse version alignment
     ⏱ 1 hour

Total: ~25 hours over 5 weeks
Blockers: Need CRAN approval for medfit first
```

## Use When

- Planning major updates
- Coordinating releases
- Managing breaking changes
- Scheduling CRAN submissions

## Related Commands

- `/rforge:impact` - See affected packages
- `/rforge:release` - CRAN submission order
- `/rforge:deps` - Understand dependencies

---
name: rforge:next
description: Get ecosystem-aware next task recommendation
argument-hint: "[package] [context]"
arguments:
  - name: package
    description: Optional package to focus the recommendation on
    required: false
    type: string
  - name: context
    description: Free-form context (e.g., "Before release", "Daily check-in")
    required: false
    type: string
---

# /rforge:next - Smart Task Recommendation

Get intelligent recommendations for what to work on next based on ecosystem context.

## What It Does

Helps you:
- Analyze all .STATUS files
- Consider dependencies
- Evaluate blocking issues
- Prioritize by impact
- Suggest optimal next task

## Usage

```bash
# Get next task
/rforge:next

# Next task for specific package
/rforge:next medfit

# Next task with context
/rforge:next --context "Before release"
```

## Output

Returns task recommendation with:
- **Task Details**: What to work on
- **Rationale**: Why this task now
- **Impact**: What it unblocks
- **Estimated Time**: How long it will take
- **Context**: Related tasks/blockers

## Examples

### High Priority Task
```
📋 NEXT TASK RECOMMENDATION

Task: Fix bug #234 - segfault in extract_mediation
ID: T-2025-01-15-002
Package: medfit
Priority: HIGH

Why now:
  • Blocking probmed release
  • Affects 2 packages
  • CRAN submission waiting
  • High user impact

Estimated time: 2-3 hours

Context:
  • 3 GitHub issues reference this
  • Already has test case
  • Fix will unblock 2 downstream releases

Recommendation: Work on this immediately
```

### Strategic Task
```
📋 NEXT TASK RECOMMENDATION

Task: Add bootstrap confidence intervals
ID: T-2025-01-15-001
Package: medfit
Priority: MEDIUM

Why now:
  • No urgent blockers
  • Good time for feature work
  • Complements recent changes
  • Low ecosystem impact

Estimated time: 4-6 hours

Context:
  • Requested by 3 users
  • Aligns with v2.2.0 roadmap
  • Can be done without cascade

Alternative tasks:
  • Update documentation (1 hour, quick win)
  • Research weighted mediation (exploratory)
```

### Before Release
```
📋 NEXT TASK RECOMMENDATION

Context: Before Release

Task: Complete documentation updates
ID: DOC-SWEEP
Priority: HIGH (release blocker)

Checklist:
  ✓ NEWS.md updated
  ✗ README examples (2 outdated)
  ✗ Vignette cross-refs (3 packages)
  ✗ API documentation (1 function)

Estimated time: 1.5 hours

Why now:
  • Release planned for next week
  • All code changes complete
  • CRAN requires current docs
  • Quick wins available

Recommendation: Focus on docs before release
```

## Use When

- Starting work session
- Finished previous task
- Deciding priorities
- Context switching
- Planning sprints

## Related Commands

- `/rforge:capture` - Add new tasks
- `/rforge:complete` - Mark tasks done
- `/rforge:status` - See overall health
- `/rforge:impact` - Understand task impact

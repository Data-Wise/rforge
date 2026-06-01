---
name: rforge:capture
description: Quick capture ideas and tasks for later (with automatic doc cascade detection)
argument-hint: Task description or idea to capture
arguments:
  - name: context
    description: Free-form task or idea text to capture
    required: false
    type: string
---

# /rforge:capture - Quick Task Capture

Quickly capture ideas, tasks, and TODOs with automatic context detection.

## What It Does

Helps you:
- Capture tasks to .STATUS file
- Auto-detect context (which package)
- Add metadata (timestamp, status)
- Trigger doc cascade detection
- Organize by priority

## Usage

```bash
# Capture a task
/rforge:capture "Add bootstrap confidence intervals"

# Capture with priority
/rforge:capture "Fix bug #234" --priority high

# Capture idea
/rforge:capture "Research weighted mediation"
```

## Output

Returns confirmation with:
- **Task ID**: Unique identifier
- **Location**: Which .STATUS file
- **Context**: Detected package/project
- **Priority**: Auto-assigned or manual
- **Next Steps**: Suggested actions

## Examples

### Simple Capture
```
✅ CAPTURED

Task: Add bootstrap confidence intervals
ID: T-2025-01-15-001
Location: medfit/.STATUS
Priority: MEDIUM (auto-detected from keywords)
Context: Feature addition

Added to: medfit/.STATUS (line 42)
Estimated work: 4-6 hours
```

### High Priority Capture
```
⚠️ CAPTURED (HIGH PRIORITY)

Task: Fix bug #234 - segfault in extract_mediation
ID: T-2025-01-15-002
Location: medfit/.STATUS
Priority: HIGH (manual override)
Context: Bug fix

Related:
  • GitHub issue #234
  • Affects: probmed, medsim
  • Impact: MEDIUM (2 packages)

Recommended: Fix immediately (blocking release)
```

### Idea Capture
```
💡 CAPTURED (IDEA)

Idea: Research weighted mediation methods
ID: I-2025-01-15-003
Location: research-ideas/.STATUS
Priority: LOW (research/exploration)
Context: New feature exploration

Notes:
  • Not blocking anything
  • Consider for v3.0.0
  • Estimated research: 1-2 weeks
```

## Use When

- During development (quick capture)
- In meetings (capture action items)
- Reading papers (capture ideas)
- Code review (capture TODOs)

## Related Commands

- `/rforge:next` - Get next task to work on
- `/rforge:complete` - Mark tasks complete
- `/rforge:status` - See all captured tasks

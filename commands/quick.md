---
name: rforge:quick
description: Ultra-fast ecosystem snapshot using only quick lib modules (< 10 seconds)
argument-hint: "[context description] [--package <path>]"
arguments:
  - name: context
    description: Free-form context for the snapshot (used for narration only)
    required: false
    type: string
  - name: package
    description: Path to a specific package (defaults to current directory)
    required: false
    type: string
---

# /rforge:quick - Ultra-Fast R Package Snapshot

Lightning-fast ecosystem snapshot using only the in-plugin lib modules. Results in < 10 seconds.

## Usage

```bash
# Ultra-fast snapshot
/rforge:quick

# With context (free-form, used for narration only)
/rforge:quick "Update bootstrap code"

# Specific path
/rforge:quick --package /path/to/RMediation
```

## What It Does

Runs the in-plugin lib modules and combines their output:

```bash
# Discover packages
python3 -m lib.discovery --path . --format json

# Dependency snapshot
python3 -m lib.deps --path . --format json

# Status rollup (health, .STATUS, packages)
python3 -m lib.status --path . --format json
```

Run them sequentially or in parallel; merge the JSON for a single quick summary.

For human-readable single-command output, run just the status rollup:

```bash
python3 -m lib.status --path . --format text
```

## When to Use

- ✅ You want instant feedback
- ✅ Just checking ecosystem state
- ✅ Doing quick iterations

**Don't use** when you need:
- ❌ Deep analysis (use `/rforge:analyze`)
- ❌ R CMD check / coverage (use `/rforge:thorough`)

## ADHD Benefits

- ⚡ Instant gratification - results in seconds
- 📊 Clear status - simple yes/no answers
- 🎯 Focus on essentials - only critical info

## Related Commands

- `/rforge:analyze` - Balanced analysis with recommendations
- `/rforge:thorough` - Deep analysis
- `/rforge:status` - Status rollup only
- `/rforge:deps` - Dependency graph only
- `/rforge:detect` - Ecosystem discovery only

---

**Perfect for:** Quick status checks during development
**Trade-off:** Speed over depth

---
name: check:description-sync
description: Verify R package DESCRIPTION Version matches the top entry of NEWS.md or CHANGELOG.md
category: validation
context: fork
hot_reload: true
version: 1.0.0
---

# DESCRIPTION ↔ Changelog Sync Validation

Catches the most common pre-release failure mode in R packages: bumping
`DESCRIPTION` Version without adding a matching changelog entry, or vice
versa. Pure shell — does not require R, devtools, or any package install.

## What It Checks

1. `DESCRIPTION` exists and contains a `Version:` line.
2. The version is SemVer-compatible (`X.Y.Z` or `X.Y.Z-tag`).
3. The latest entry in `NEWS.md` or `CHANGELOG.md` references that version.

If any check fails, exit non-zero in `release` mode (blocks CRAN prep).
In `default` mode, warn but allow.

## Mode Behavior

| Mode | Action on mismatch |
|------|--------------------|
| **default** | Warn, exit 0 |
| **debug** | Verbose diff, exit 0 |
| **optimize** | Warn, exit 0 (does not auto-fix — version bumps are intentional) |
| **release** | Fail, exit 1 |

## Implementation

```bash
#!/bin/bash
set -euo pipefail

MODE="${RFORGE_MODE:-default}"

if [ ! -f "DESCRIPTION" ]; then
    echo "⚠️  SKIP: No DESCRIPTION file (not an R package)"
    exit 0
fi

VERSION=$(awk -F': *' '/^Version:/ {print $2; exit}' DESCRIPTION | tr -d '[:space:]')

if [ -z "$VERSION" ]; then
    echo "❌ FAIL: DESCRIPTION has no Version: line"
    exit 1
fi

# SemVer check (allows pre-release suffixes)
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+(\.[0-9]+)?(-[A-Za-z0-9.]+)?$'; then
    echo "⚠️  WARN: Version '$VERSION' is not SemVer-compatible"
    [ "$MODE" = "release" ] && exit 1
fi

# Find changelog file
CHANGELOG=""
for candidate in NEWS.md CHANGELOG.md NEWS; do
    if [ -f "$candidate" ]; then
        CHANGELOG="$candidate"
        break
    fi
done

if [ -z "$CHANGELOG" ]; then
    echo "⚠️  WARN: No NEWS.md or CHANGELOG.md found"
    [ "$MODE" = "release" ] && exit 1
    exit 0
fi

# Look for the version string in the first 50 lines of the changelog.
# This catches "## [1.2.0]", "# foo 1.2.0", "## 1.2.0 - 2026-01-01", etc.
if head -n 50 "$CHANGELOG" | grep -qF "$VERSION"; then
    echo "✅ PASS: DESCRIPTION Version $VERSION found in $CHANGELOG"
    exit 0
fi

echo "❌ FAIL: DESCRIPTION Version $VERSION is not in $CHANGELOG (top 50 lines)"
echo "   Add an entry to $CHANGELOG before tagging the release."
[ "$MODE" = "release" ] && exit 1
exit 0
```

## Example Output

### Success

```
✅ PASS: DESCRIPTION Version 1.2.0 found in NEWS.md
```

### Failure (release mode)

```
❌ FAIL: DESCRIPTION Version 1.2.0 is not in NEWS.md (top 50 lines)
   Add an entry to NEWS.md before tagging the release.
```

## When This Runs

- Manually: `bash .claude-plugin/skills/validation/description-sync.md` (extract the script first).
- Future: surfaced via `/rforge:check` once the discovery layer lands (Phase 4 of the parity proposal).
- Pre-CRAN-submission as a sanity check.

## See Also

- `/rforge:release` — CRAN submission planner.
- `/rforge:doc-check` — broader documentation drift.
- `.claude-plugin/hooks/pretooluse.py` — also validates Version SemVer on every Edit.

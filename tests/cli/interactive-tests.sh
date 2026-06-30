#!/usr/bin/env bash
# rforge interactive dogfood QA
# Human-guided checks for outputs that are hard to validate automatically.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p tests/cli/logs
LOG="tests/cli/logs/interactive-test-$(date +%Y%m%d-%H%M%S).log"

echo "rforge interactive QA session — $(date)" | tee "$LOG"

TOTAL=0
PASSED=0
FAILED=0

ask() {
    local desc="$1"
    local expected="$2"
    local cmd="$3"

    TOTAL=$((TOTAL + 1))

    printf "\nTEST %d/%d: %s\n" "$TOTAL" "${TOTAL:-?}" "$desc" | tee -a "$LOG"
    printf "Command: %s\n" "$cmd" | tee -a "$LOG"
    printf "Expected: %s\n" "$expected" | tee -a "$LOG"
    printf "Output:\n" | tee -a "$LOG"
    eval "$cmd" 2>&1 | tee -a "$LOG"
    printf "\n[y=pass, n=fail, q=quit]: "
    read -r resp
    echo "Response: $resp" >> "$LOG"

    case "$resp" in
        y|Y)
            PASSED=$((PASSED + 1))
            printf "✅ recorded pass\n" | tee -a "$LOG"
            ;;
        n|N)
            FAILED=$((FAILED + 1))
            printf "❌ recorded fail\n" | tee -a "$LOG"
            ;;
        q|Q)
            printf "Quit requested.\n" | tee -a "$LOG"
            break
            ;;
        *)
            printf "Invalid response, skipping.\n" | tee -a "$LOG"
            ;;
    esac
}

# ─── Visual / output checks ──────────────────────────────────────────────────
ask "plugin.json version display" \
    "shows version 2.17.0" \
    "python3 -c 'import json; print(json.load(open(\".claude-plugin/plugin.json\"))[\"version\"])'"

ask "commands list" \
    "lists all 41 r: commands and top-level commands" \
    "find commands -name '*.md' -not -path 'commands/docs/*' | sort"

ask "cranlint lint output format" \
    "emits readable findings or a clean report" \
    "python3 -m lib.cranlint lint tests/fixtures/mypkg"

ask "sitelint output for clean fixture" \
    "reports no stray files or clearly explains any hits" \
    "python3 -m lib.sitelint tests/fixtures/mypkg"

# ─── Summary ──────────────────────────────────────────────────────────────────
printf "\n═══════════════════════════\n  INTERACTIVE RESULTS\n═══════════════════════════\n"
printf "  Passed:  %d\n" "$PASSED"
printf "  Failed:  %d\n" "$FAILED"
printf "  Log:     %s\n" "$LOG"

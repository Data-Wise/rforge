#!/usr/bin/env bash
# rforge automated dogfood tests
# Non-interactive smoke tests for plugin structure and public lib/ CLIs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
SKIP=0

red='\033[0;31m'
green='\033[0;32m'
yellow='\033[1;33m'
reset='\033[0m'

pass() {
    PASS=$((PASS + 1))
    printf "${green}✅ PASS${reset}: %s\n" "$1"
}

fail() {
    FAIL=$((FAIL + 1))
    printf "${red}❌ FAIL${reset}: %s\n" "$1"
    if [ -n "${2:-}" ]; then
        printf "   → %s\n" "$2"
    fi
}

skip() {
    SKIP=$((SKIP + 1))
    printf "${yellow}⏭️  SKIP${reset}: %s\n" "$1"
}

section() {
    printf "\n━━━ %s ━━━\n" "$1"
}

# ─── Plugin structure ────────────────────────────────────────────────────────
section "Plugin structure"

if [ -f .claude-plugin/plugin.json ]; then
    pass "plugin.json exists"
else
    fail "plugin.json exists" "missing .claude-plugin/plugin.json"
fi

if [ -f .claude-plugin/marketplace.json ]; then
    pass "marketplace.json exists"
else
    fail "marketplace.json exists" "missing .claude-plugin/marketplace.json"
fi

if python3 -c "import json; p=json.load(open('.claude-plugin/plugin.json')); assert 'name' in p and 'version' in p" 2>/dev/null; then
    pass "plugin.json has required fields"
else
    fail "plugin.json has required fields"
fi

if python3 -c "
import json
p = json.load(open('.claude-plugin/plugin.json'))
m = json.load(open('.claude-plugin/marketplace.json'))
assert p['version'] == m['metadata']['version'] == m['plugins'][0]['version']
" 2>/dev/null; then
    pass "plugin + marketplace versions agree"
else
    fail "plugin + marketplace versions agree"
fi

# ─── Commands directory ──────────────────────────────────────────────────────
section "Commands"

CMD_COUNT=$(find commands -name '*.md' -not -path 'commands/docs/*' | wc -l | tr -d ' ')
if [ "$CMD_COUNT" -gt 0 ]; then
    pass "commands directory contains .md files ($CMD_COUNT)"
else
    fail "commands directory contains .md files"
fi

UNIQUE=$(find commands -name '*.md' -not -path 'commands/docs/*' -exec basename {} \; | sort | uniq -d | wc -l | tr -d ' ')
if [ "$UNIQUE" -eq 0 ]; then
    pass "command file names are unique"
else
    fail "command file names are unique" "$UNIQUE duplicates"
fi

if python3 tests/_check_commands_doc.py 2>/dev/null; then
    pass "commands.md sync gate passes"
else
    fail "commands.md sync gate passes"
fi

# ─── Version sync ────────────────────────────────────────────────────────────
section "Version sync"

if python3 scripts/version_sync.py --check 2>/dev/null; then
    pass "version_sync.py --check passes"
else
    fail "version_sync.py --check passes"
fi

# ─── lib/ module smoke tests ─────────────────────────────────────────────────
section "lib/ module CLI smoke"

PUBLIC_MODULES=(
    lib.cranlint
    lib.discovery
    lib.status
    lib.init
    lib.rcmd
    lib.deps_sync
    lib.ghrelease
    lib.runiverse
    lib.s7review
    lib.changed
    lib.scaffold
    lib.sitelint
)

for mod in "${PUBLIC_MODULES[@]}"; do
    if python3 -m "$mod" --help >/dev/null 2>&1 || python3 -m "$mod" >/dev/null 2>&1; then
        pass "$mod CLI invocation succeeds"
    else
        fail "$mod CLI invocation succeeds"
    fi
done

# ─── pytest quick smoke ──────────────────────────────────────────────────────
section "pytest smoke"

if python3 -m pytest tests/test_version_sync.py -q 2>/dev/null; then
    pass "test_version_sync.py passes"
else
    fail "test_version_sync.py passes"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
printf "\n═══════════════════════════\n  RESULTS\n═══════════════════════════\n"
printf "  Passed:  %d\n" "$PASS"
printf "  Failed:  %d\n" "$FAIL"
printf "  Skipped: %d\n" "$SKIP"
printf "  Total:   %d\n" "$((PASS + FAIL + SKIP))"

if [ "$FAIL" -eq 0 ]; then
    printf "\n${green}✅ ALL TESTS PASSED${reset}\n"
    exit 0
else
    printf "\n${red}❌ SOME TESTS FAILED${reset}\n"
    exit 1
fi

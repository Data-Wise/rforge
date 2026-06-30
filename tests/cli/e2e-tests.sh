#!/usr/bin/env bash
# rforge end-to-end fixture tests
# Runs public lib/ modules against fixtures in tests/fixtures/.

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

has_r() {
    command -v Rscript >/dev/null 2>&1
}

# ─── cranlint against fixtures ───────────────────────────────────────────────
section "cranlint end-to-end"

for pkg in tests/fixtures/mypkg tests/fixtures/suggestbug.before; do
    if [ -f "$pkg/DESCRIPTION" ]; then
        if python3 -m lib.cranlint lint "$pkg" >/dev/null 2>&1; then
            pass "cranlint lint on $(basename "$pkg")"
        else
            fail "cranlint lint on $(basename "$pkg")"
        fi
    else
        skip "cranlint lint on $(basename "$pkg")" "no DESCRIPTION"
    fi
done

# ─── discovery against fixtures ──────────────────────────────────────────────
section "discovery end-to-end"

for pkg in tests/fixtures/mypkg tests/fixtures/scaffoldpkg; do
    if [ -f "$pkg/DESCRIPTION" ]; then
        if python3 -m lib.discovery --path "$pkg" >/dev/null 2>&1; then
            pass "discovery on $(basename "$pkg")"
        else
            fail "discovery on $(basename "$pkg")"
        fi
    else
        skip "discovery on $(basename "$pkg")" "no DESCRIPTION"
    fi
done

# ─── s7review against fixtures ───────────────────────────────────────────────
section "s7review end-to-end"

if has_r; then
    for pkg in tests/fixtures/s7pkg.clean tests/fixtures/s7pkg.bad; do
        if [ -f "$pkg/DESCRIPTION" ]; then
            if python3 -m lib.s7review --path "$pkg" --format json >/dev/null 2>&1; then
                pass "s7review on $(basename "$pkg")"
            else
                fail "s7review on $(basename "$pkg")"
            fi
        else
            skip "s7review on $(basename "$pkg")" "no DESCRIPTION"
        fi
    done
else
    skip "s7review fixtures" "Rscript not available"
fi

# ─── sitelint against fixtures ───────────────────────────────────────────────
section "sitelint end-to-end"

for pkg in tests/fixtures/mypkg tests/fixtures/scaffoldpkg; do
    if [ -d "$pkg" ]; then
        if python3 -m lib.sitelint "$pkg" >/dev/null 2>&1; then
            pass "sitelint on $(basename "$pkg")"
        else
            fail "sitelint on $(basename "$pkg")"
        fi
    else
        skip "sitelint on $(basename "$pkg")" "missing fixture"
    fi
done

# ─── scaffold end-to-end (dry-run) ────────────────────────────────────────────
section "scaffold dry-run"

if python3 -m lib.scaffold package --path tests/fixtures/mypkg --pkg tibble --format text >/dev/null 2>&1; then
    pass "scaffold dry-run plans package dependency"
else
    fail "scaffold dry-run plans package dependency"
fi

if python3 -m lib.scaffold test --path tests/fixtures/mypkg --fn draw_sample --format text >/dev/null 2>&1; then
    pass "scaffold dry-run plans test skeleton"
else
    fail "scaffold dry-run plans test skeleton"
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

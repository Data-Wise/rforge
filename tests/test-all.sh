#!/bin/bash
# RForge plugin — full validation suite.
#
# Runs every check that's meaningful for this plugin: existing bash
# structure tests, Python hook compile + behavior smoke tests, JSON
# manifest parse + version-sync checks, mkdocs config + nav integrity,
# and skill frontmatter + embedded-script syntax.
#
# Designed to be CI-friendly: exits 0 only if every check passes.
# Safe to run from anywhere — cd's to the plugin root via BASH_SOURCE.

set -u  # error on unset vars; do NOT use set -e (we tally per-test failures)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PLUGIN_DIR"

PASS=0
FAIL=0
RESULTS=""
LOG=$(mktemp -t rforge-test-XXXXXX)
trap 'rm -f "$LOG"' EXIT

run() {
    local name="$1"
    shift
    if "$@" > "$LOG" 2>&1; then
        RESULTS="${RESULTS}✅ ${name}"$'\n'
        PASS=$((PASS + 1))
    else
        RESULTS="${RESULTS}❌ ${name}"$'\n'
        echo "--- FAIL: $name ---"
        cat "$LOG"
        echo "---"
        FAIL=$((FAIL + 1))
    fi
}

# Hook smoke tests — each rule isolated.
# Claude Code passes the hook payload as JSON on stdin (per the contract
# documented in ~/.claude/hooks/branch-guard.sh). Earlier versions of
# these tests passed env vars — that's not the actual Claude Code API
# and the hook silently no-op'd in production.
hook_blocks_man_rd() {
    echo '{"tool_name":"Edit","tool_input":{"file_path":"man/foo.Rd","old_string":"x","new_string":"y"}}' \
        | python3 .claude-plugin/hooks/pretooluse.py
    [ $? -eq 2 ]
}

hook_warns_r_source() {
    echo '{"tool_name":"Edit","tool_input":{"file_path":"R/foo.R","old_string":"x","new_string":"y"}}' \
        | python3 .claude-plugin/hooks/pretooluse.py 2>/dev/null
    [ $? -eq 0 ]
}

hook_warns_bad_semver() {
    echo '{"tool_name":"Write","tool_input":{"file_path":"DESCRIPTION","content":"Version: not-semver\n"}}' \
        | python3 .claude-plugin/hooks/pretooluse.py 2>&1 \
        | grep -q "not SemVer-compatible"
}

hook_silent_on_good_semver() {
    local out
    out=$(echo '{"tool_name":"Write","tool_input":{"file_path":"DESCRIPTION","content":"Version: 1.2.0\n"}}' \
          | python3 .claude-plugin/hooks/pretooluse.py 2>&1)
    [ -z "$out" ]
}

hook_ignores_non_write_edit() {
    echo '{"tool_name":"Read","tool_input":{"file_path":"man/foo.Rd"}}' \
        | python3 .claude-plugin/hooks/pretooluse.py
    [ $? -eq 0 ]
}

# Contract test: empty/garbage stdin must not crash.
hook_handles_empty_stdin() {
    echo '' | python3 .claude-plugin/hooks/pretooluse.py
    [ $? -eq 0 ]
}

hook_handles_garbage_stdin() {
    echo 'not json at all' | python3 .claude-plugin/hooks/pretooluse.py
    [ $? -eq 0 ]
}

# Manifest checks.
versions_match() {
    python3 -c "
import json, sys
p = json.load(open('.claude-plugin/plugin.json'))['version']
m = json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version']
if p != m:
    print(f'mismatch: plugin.json={p}  marketplace.json={m}', file=sys.stderr)
    sys.exit(1)
"
}

changelog_has_current_version() {
    local current
    current=$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])")
    grep -q "## \[$current\]" CHANGELOG.md
}

# Docs site checks.
mkdocs_parses() {
    python3 -c "import yaml; yaml.unsafe_load(open('mkdocs.yml'))"
}

mkdocs_nav_files_exist() {
    local missing=0
    local files
    # Pull every doc filename referenced in the nav (matches `: <name>.md`).
    files=$(python3 -c "
import yaml
cfg = yaml.unsafe_load(open('mkdocs.yml'))
def walk(node):
    if isinstance(node, dict):
        for v in node.values(): yield from walk(v)
    elif isinstance(node, list):
        for v in node: yield from walk(v)
    elif isinstance(node, str) and node.endswith('.md'):
        yield node
print('\n'.join(walk(cfg.get('nav', []))))
")
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if [ ! -f "docs/$f" ]; then
            echo "MISSING: docs/$f"
            missing=1
        fi
    done <<< "$files"
    return $missing
}

# Skill checks.
skill_extract_and_check() {
    local extracted
    extracted=$(mktemp -t rforge-skill-XXXXXX.sh)
    awk '/^```bash$/{flag=1;next}/^```$/{flag=0}flag' \
        .claude-plugin/skills/validation/description-sync.md > "$extracted"
    bash -n "$extracted"
    local rc=$?
    rm -f "$extracted"
    return $rc
}

skill_frontmatter_complete() {
    python3 -c "
import re, sys
content = open('.claude-plugin/skills/validation/description-sync.md').read()
m = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
if not m:
    print('no frontmatter', file=sys.stderr); sys.exit(1)
for field in ('name:', 'description:', 'category:'):
    if field not in m.group(1):
        print(f'missing {field}', file=sys.stderr); sys.exit(1)
"
}

echo "═══════════════════════════════════════════════════════════════"
echo "  RForge plugin — full validation suite"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Structure (existing test)
run "Plugin structure (8 sub-tests)" bash tests/test-plugin-structure.sh

# Hook
run "Hook compiles (py_compile)" python3 -m py_compile .claude-plugin/hooks/pretooluse.py
run "Hook is executable"          test -x .claude-plugin/hooks/pretooluse.py
run "Hook rule 1: blocks man/*.Rd"           hook_blocks_man_rd
run "Hook rule 2: warns on R/*.R, exits 0"   hook_warns_r_source
run "Hook rule 3a: warns on bad SemVer"      hook_warns_bad_semver
run "Hook rule 3b: silent on good SemVer"    hook_silent_on_good_semver
run "Hook ignores non-Write/Edit tools"      hook_ignores_non_write_edit
run "Hook handles empty stdin gracefully"    hook_handles_empty_stdin
run "Hook handles garbage stdin gracefully"  hook_handles_garbage_stdin

# Manifests
run "marketplace.json parses" python3 -c "import json; json.load(open('.claude-plugin/marketplace.json'))"
run "config.json parses"      python3 -c "import json; json.load(open('.claude-plugin/config.json'))"
run "plugin.json parses"      python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"
run "package.json parses"     python3 -c "import json; json.load(open('package.json'))"
run "plugin.json/marketplace.json versions match" versions_match
run "CHANGELOG has current version entry"          changelog_has_current_version

# Docs site
run "mkdocs.yml parses"            mkdocs_parses
run "mkdocs nav files all exist"   mkdocs_nav_files_exist

# Skills
run "Skill: embedded script syntax-checks"   skill_extract_and_check
run "Skill: frontmatter has required fields" skill_frontmatter_complete

echo ""
echo "═══════════════════════════════════════════════════════════════"
printf '%s' "$RESULTS"
echo "Total: $((PASS + FAIL))  |  Passed: $PASS  |  Failed: $FAIL"
echo "═══════════════════════════════════════════════════════════════"

[ $FAIL -eq 0 ]

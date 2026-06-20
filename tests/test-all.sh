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
# Asserts all 4 version sources agree. We previously only compared
# plugin.json + marketplace.json/plugins[0]; package.json drifted to
# 1.1.0 while the others moved to 1.2.0 (caught by /craft:docs:update,
# fixed in c2369ae). marketplace.json has two version fields
# (metadata.version + plugins[0].version) that can also drift apart.
versions_match() {
    python3 -c "
import json, sys
versions = {
    'plugin.json': json.load(open('.claude-plugin/plugin.json'))['version'],
    'marketplace.json/metadata': json.load(open('.claude-plugin/marketplace.json'))['metadata']['version'],
    'marketplace.json/plugins[0]': json.load(open('.claude-plugin/marketplace.json'))['plugins'][0]['version'],
    'package.json': json.load(open('package.json'))['version'],
}
unique = set(versions.values())
if len(unique) > 1:
    detail = ' | '.join(f'{k}={v}' for k, v in versions.items())
    print(f'version mismatch: {detail}', file=sys.stderr)
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

mkdocs_no_orphan_pages() {
    # Reverse of mkdocs_nav_files_exist: every page in the user-facing doc
    # tiers (guides/, tutorials/, reference/) must be reachable from the nav,
    # so a newly added guide/tutorial/reference page can't silently orphan
    # (the v2.13.0 docs audit found this gap). specs/ and migration/ are
    # intentionally not all navigated, so they are out of scope here.
    # Text-scan mkdocs.yml for .md targets — avoids yaml.load on a file whose
    # !!python/name: tags would otherwise require an unsafe loader.
    python3 -c "
import re, glob, os, sys
nav = set(re.findall(r'[A-Za-z0-9_./-]+[.]md', open('mkdocs.yml').read()))
orphans = []
for tier in ('guides', 'tutorials', 'reference'):
    for path in sorted(glob.glob('docs/' + tier + '/*.md')):
        rel = os.path.relpath(path, 'docs')
        if rel not in nav:
            orphans.append(rel)
if orphans:
    print('ORPHANED (in docs/ but not referenced in mkdocs.yml nav):')
    for o in orphans:
        print('  ' + o)
    sys.exit(1)
"
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

# v2.0.0 rename targets — the 3 NEW command files must exist at their
# new paths AND have explicit `name:` frontmatter set to the new
# colon-namespaced names. Colon-namespacing requires explicit frontmatter;
# filename-based inference doesn't cover `r:check` etc. Without this
# check, deleting the frontmatter from a renamed file would silently
# break the slash-command resolution while leaving the file in place.
rename_targets_present() {
    python3 -c "
import sys
targets = {
    'commands/docs/check.md': 'rforge:docs:check',
    'commands/health.md':     'rforge:health',
    'commands/r/check.md':    'rforge:r:check',
}
fail = 0
for path, expected_name in targets.items():
    try:
        body = open(path).read()
    except FileNotFoundError:
        print(f'MISSING: {path} (rename target gone)', file=sys.stderr); fail = 1; continue
    if f'name: {expected_name}' not in body:
        print(f'{path}: frontmatter must contain \"name: {expected_name}\"', file=sys.stderr); fail = 1
sys.exit(fail)
"
}

# Every command must have a unique `name:` frontmatter value. Catches
# copy-paste errors where two files claim the same slash-command name
# (which would produce undefined resolution). Walks commands/**/*.md;
# files without a `name:` field are ignored (some pre-frontmatter
# commands still rely on filename inference and that's OK — they just
# can't collide on a value they don't declare).
command_names_unique() {
    python3 -c "
import pathlib, re, sys
seen = {}
fail = 0
for p in sorted(pathlib.Path('commands').rglob('*.md')):
    body = p.read_text()
    m = re.search(r'^name:\s*(\S+)', body, re.MULTILINE)
    if not m:
        continue
    name = m.group(1)
    if name in seen:
        print(f'NAME COLLISION: {name} appears in both {seen[name]} and {p}', file=sys.stderr)
        fail = 1
    else:
        seen[name] = p
sys.exit(fail)
"
}

# E2E: the migration tutorial's `sed` recipe must (a) declare all 3
# substitutions in the right direction, AND (b) actually produce the
# expected rewrites when applied to a fixture. Catches doc-rot where
# the recipe drifts from the rename table (most likely failure: a
# rename added/changed in the SPEC but the tutorial isn't updated).
migration_recipe_works() {
    python3 -c "
import sys, re
tutorial = open('docs/migration/v2.0.0-rename.md').read()
required = [
    ('/rforge:doc-check',        '/rforge:docs:check'),
    ('/rforge:ecosystem-health', '/rforge:health'),
    ('/rforge:rpkg-check',       '/rforge:r:check'),
]
fail = 0
# (a) Recipe declares each substitution as s|OLD|NEW|g
for old, new in required:
    pattern = f's|{old}|{new}|g'
    if pattern not in tutorial:
        print(f'tutorial missing sed substitution: {pattern}', file=sys.stderr); fail = 1
# (b) Apply substitutions to a fixture containing all 3 old names and
#     verify the rewrites land correctly. Uses Python str.replace as a
#     pure surrogate for sed s|...|...|g (no regex special chars here).
fixture = 'see /rforge:doc-check, /rforge:ecosystem-health, /rforge:rpkg-check'
result = fixture
for old, new in required:
    result = result.replace(old, new)
expected = 'see /rforge:docs:check, /rforge:health, /rforge:r:check'
if result != expected:
    print(f'recipe-equivalent substitution wrong: got {result!r}', file=sys.stderr); fail = 1
# (c) The tutorial's *find* recipe must cover the same 3 names. The
#     grep -E alternation pattern '/rforge:(doc-check|ecosystem-health|rpkg-check)'
#     is the discovery half users run before the sed half. If a future
#     rename adds a 4th name without updating the find pattern, users
#     would miss it in their local scripts. Validates the alternation
#     contains exactly the 3 expected names.
m = re.search(r'/rforge:\(([a-z\-|]+)\)', tutorial)
if not m:
    print('tutorial missing grep -E alternation pattern (/rforge:(...|...|...))', file=sys.stderr); fail = 1
else:
    alternatives = set(m.group(1).split('|'))
    expected_names = {'doc-check', 'ecosystem-health', 'rpkg-check'}
    missing = expected_names - alternatives
    extra = alternatives - expected_names
    if missing:
        print(f'tutorial grep pattern missing names: {missing}', file=sys.stderr); fail = 1
    if extra:
        print(f'tutorial grep pattern has unexpected alternatives: {extra}', file=sys.stderr); fail = 1
sys.exit(fail)
"
}

# E2E (/help simulation): the 3 stubs' frontmatter `description:` must
# start with a warning marker so users browsing /help in Claude Code
# see the rename hint BEFORE invocation. Without this, a user has to
# actually type the old name to discover the rename.
stub_help_listings_show_warning() {
    python3 -c "
import sys, re
stubs = ['commands/doc-check.md', 'commands/ecosystem-health.md', 'commands/rpkg-check.md']
fail = 0
for path in stubs:
    body = open(path).read()
    m = re.search(r'^description:\s*(.+)$', body, re.MULTILINE)
    if not m:
        print(f'{path}: no description frontmatter', file=sys.stderr); fail = 1; continue
    desc = m.group(1).strip()
    # Warning marker = ⚠️ or RENAMED — either is acceptable signal.
    if not (desc.startswith('⚠️') or 'RENAMED' in desc.upper()):
        print(f'{path}: description should lead with ⚠️ or RENAMED for /help visibility — got: {desc!r}', file=sys.stderr); fail = 1
sys.exit(fail)
"
}

# Dogfood: run lib/discovery on the rforge plugin's own repo and verify
# it handles a non-R-package directory gracefully (valid JSON, no
# crash). Catches regressions in the negative code path that's easy
# to miss when all dev work happens in actual R-package fixtures.
lib_discovery_on_self() {
    python3 -c "
import json, subprocess, sys
r = subprocess.run(
    ['python3', '-m', 'lib.discovery', '--path', '.', '--format', 'json'],
    capture_output=True, text=True
)
if r.returncode != 0:
    print(f'lib.discovery exited {r.returncode}; stderr: {r.stderr[:400]}', file=sys.stderr); sys.exit(1)
try:
    data = json.loads(r.stdout)
except json.JSONDecodeError as e:
    print(f'lib.discovery output is not valid JSON: {e}', file=sys.stderr); sys.exit(1)
# Don't pin specific keys — we want this test to survive lib output
# evolution. Just assert: ran cleanly, parsed, returned a dict.
if not isinstance(data, dict):
    print(f'expected dict, got {type(data).__name__}', file=sys.stderr); sys.exit(1)
"
}

# v2.0.0 rename stubs — the 3 old command filenames must still exist as
# rename-error stubs, each pointing at its new name. Asserts on the
# contract (file present + key strings), not the exact wording, so this
# survives prompt-control iteration without breaking.
rename_stubs_present() {
    python3 -c "
import sys
stubs = {
    'commands/doc-check.md':         ('rforge:doc-check',        '/rforge:docs:check'),
    'commands/ecosystem-health.md':  ('rforge:ecosystem-health', '/rforge:health'),
    'commands/rpkg-check.md':        ('rforge:rpkg-check',       '/rforge:r:check'),
}
fail = 0
for path, (old_name, new_slash) in stubs.items():
    try:
        body = open(path).read()
    except FileNotFoundError:
        print(f'MISSING: {path}', file=sys.stderr); fail = 1; continue
    if f'name: {old_name}' not in body:
        print(f'{path}: frontmatter name: missing or wrong (want \"{old_name}\")', file=sys.stderr); fail = 1
    if 'RENAMED' not in body.upper():
        print(f'{path}: no rename-error marker found (looking for RENAMED)', file=sys.stderr); fail = 1
    if new_slash not in body:
        print(f'{path}: target name {new_slash} not referenced', file=sys.stderr); fail = 1
sys.exit(fail)
"
}

# Lib modules — pytest suite for lib/discovery.py + lib/deps.py + lib/status.py + lib/init.py.
# Requires pytest. If not installed, we emit a clear hint and fail —
# pytest is a dev-time dependency, expected in CI and local dev.
lib_pytest() {
    if ! python3 -c "import pytest" 2>/dev/null; then
        echo "pytest not installed — run: pip install pytest" >&2
        return 1
    fi
    python3 -m pytest tests/test_lib_discovery.py tests/test_lib_deps.py tests/test_lib_status.py tests/test_lib_init.py -q
}

# Lib CLIs run end-to-end on an empty cwd without error.
# lib/ is now a Python package — invoke via `python3 -m lib.<module>`.
# CRITICAL: lib.init writes to ~/.rforge/ by default; we MUST pass --home to
# a temp dir so the smoke test NEVER touches the user's real home.
# We pass --path <tmpdir> instead of cd-ing so `lib` stays importable via
# the plugin root (which is the CWD when this script runs).
lib_cli_smoke() {
    local tmpdir home_smoke
    tmpdir=$(mktemp -d)
    home_smoke=$(mktemp -d)
    python3 -m lib.discovery --path "$tmpdir" --format json > /dev/null && \
    python3 -m lib.deps --path "$tmpdir" --format json > /dev/null && \
    python3 -m lib.status --path "$tmpdir" --format json > /dev/null && \
    python3 -m lib.init --path "$tmpdir" --home "$home_smoke" --format json > /dev/null
    local rc=$?
    rm -rf "$tmpdir" "$home_smoke"
    return $rc
}

# Auto-extracted reference docs (docs/reference/*.md) must stay in sync with
# the docstrings in lib/. Drift means someone updated a docstring without
# re-running the generator.
lib_reference_in_sync() {
    python3 scripts/gen_lib_reference.py --check
}

# Version/count strings across mkdocs.yml extra, plugin.json, README.md, and
# CLAUDE.md must stay in sync with package.json (the authoritative source).
# Drift means someone bumped the version without running version_sync.py.
# Direct sibling of lib_reference_in_sync (same --check drift-gate pattern).
version_sync_in_sync() {
    python3 scripts/version_sync.py --check
}

# lib.rcmd CLI smoke — with R absent the module emits an engine_missing/error
# envelope; with R present it runs for real. Either way we assert parseable JSON.
lib_rcmd_smoke() {
    local out
    out=$(python3 -m lib.rcmd --kind check --path tests/fixtures/mypkg 2>/dev/null)
    # Feed the envelope via stdin (not string interpolation) so apostrophes,
    # newlines, and other control chars in real R output can't break parsing.
    printf '%s' "$out" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as e:
    print(f'Not valid JSON: {e}', file=sys.stderr); sys.exit(1)
if 'status' not in d:
    print('Missing status key in envelope', file=sys.stderr); sys.exit(1)
# Accept ok/warn/error — engine_missing when R absent is expected
" 2>&1
}

# lib.cranlint CLI smoke — pure-Python (no R). Runs the three Tier-4 advisory
# checks against a real fixture package and asserts a well-formed envelope.
lib_cranlint_smoke() {
    local out
    out=$(python3 -m lib.cranlint --path tests/fixtures/suggestbug.before 2>/dev/null)
    printf '%s' "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['kind'] == 'cranlint', f\"unexpected kind {d['kind']}\"
assert d['status'] in ('ok', 'warn'), f\"advisory module must never error, got {d['status']}\"
kinds = {s['kind'] for s in d['stages']}
need = {'description', 'build-hygiene', 'docs-consistency'}
assert need <= kinds, f'missing Tier-4 stages: {need - kinds}'
"
}

# lib.runiverse CLI smoke — pure-Python, network-free here (a tmpdir with no
# DESCRIPTION bails before any HTTP call). Asserts the warn-degradation envelope
# so the check is hermetic: offline/unregistered must never crash or error.
lib_runiverse_smoke() {
    local tmpdir out
    tmpdir=$(mktemp -d)
    out=$(python3 -m lib.runiverse --path "$tmpdir" --format json 2>/dev/null)
    rm -rf "$tmpdir"
    printf '%s' "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['kind'] == 'runiverse', f\"unexpected kind {d['kind']}\"
assert d['status'] in ('ok', 'warn'), f\"must degrade, not error; got {d['status']}\"
assert d['engine_missing'] == [], 'pure-Python module: engine_missing must be []'
"
}

# lib.s7review CLI smoke — pure-Python (no R). Runs the static S7 convention
# checker over the deliberately-bad fixture and asserts the advisory envelope:
# a worst-of warn, kind s7review, engine_missing always [].
lib_s7review_smoke() {
    local out
    out=$(python3 -m lib.s7review --path tests/fixtures/s7pkg.bad --format json 2>/dev/null)
    printf '%s' "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['kind'] == 's7review', f\"unexpected kind {d['kind']}\"
assert d['status'] in ('ok', 'warn'), f\"advisory: must be ok/warn; got {d['status']}\"
assert d['engine_missing'] == [], 'pure-Python module: engine_missing must be []'
"
}

# lib.changed CLI smoke — pure-Python (subprocess git only, no R). Must emit a
# valid JSON envelope and never traceback, even when run off a git repo. We run
# against a tmpdir that is not a git repo so the call exercises the warn-degrade
# path; status must be ok|warn and the two scope keys must be present.
lib_changed_smoke() {
    local tmpdir out
    tmpdir=$(mktemp -d)
    out=$(python3 -m lib.changed --path "$tmpdir" --base HEAD --format json 2>/dev/null)
    rm -rf "$tmpdir"
    printf '%s' "$out" | python3 -c "
import json, sys
d = json.load(sys.stdin)
assert d['status'] in ('ok', 'warn'), d
assert 'changed_files' in d and 'changed_packages' in d, d
"
}

# Scaffolding: the use-* commands must carry name+description frontmatter.
scaffold_cmds_frontmatter() {
    for f in commands/r/use-test.md commands/r/use-package.md commands/r/use-vignette.md \
             commands/r/use-data.md commands/r/use-citation.md; do
        grep -q "^name: rforge:r:use-" "$f" || { echo "missing name in $f"; return 1; }
        grep -q "^description:" "$f" || { echo "missing description in $f"; return 1; }
    done
}

# Scaffolding: lib.scaffold + lib.usethis_infra import + run --help cleanly.
scaffold_lib_smoke() {
    python3 -m lib.scaffold --help >/dev/null 2>&1 \
        && python3 -m lib.usethis_infra --help >/dev/null 2>&1
}

# Scaffolding: every `--flag` in each use-* `arguments:` block appears in `## Usage`.
scaffold_args_usage_sync() {
    python3 tests/_check_scaffold_args.py
}

# Phase 4: no removed rforge-mcp tool references may survive in any agent file.
# (rforge-mcp was absorbed into lib/ in v1.3.0; the tools no longer exist.)
# Matches both the legacy `rforge_*` underscore form and the `mcp__rforge*`
# MCP tool-call shape a stale reference could take.
agent_no_mcp_refs() {
    ! grep -lqE "rforge_|mcp__rforge" agents/*.md
}

# Phase 4: orchestrator agent must carry name + description frontmatter.
agent_frontmatter_complete() {
    python3 - <<'PY'
import sys, re
src = open("agents/orchestrator.md", encoding="utf-8").read()
m = re.match(r"^---\n(.*?)\n---\n", src, re.DOTALL)
if not m:
    print("no YAML frontmatter block"); sys.exit(1)
fm = m.group(1)
for key in ("name:", "description:"):
    if key not in fm:
        print(f"missing {key} in frontmatter"); sys.exit(1)
PY
}

# Phase 4: agent must not name lib.rcmd engines that don't exist.
agent_engines_valid() {
    python3 tests/_check_agent_engines.py
}

# docs/commands.md sync-gate (v2.12.0): every non-stub command has a section,
# every section has a backing command file, and every declared CLI flag is
# documented in that command's section. Presence check, pure stdlib.
commands_doc_in_sync() {
    python3 tests/_check_commands_doc.py
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
run "All 4 version sources agree (plugin/marketplace/package)" versions_match
run "CHANGELOG has current version entry"          changelog_has_current_version
run "v2.0.0 rename stubs present + point at new names" rename_stubs_present
run "v2.0.0 rename targets present + have new-name frontmatter" rename_targets_present
run "Command name: frontmatter values are unique"   command_names_unique
run "E2E: migration tutorial sed recipe is correct"  migration_recipe_works
run "E2E: stubs' /help descriptions show rename warning" stub_help_listings_show_warning
run "Dogfood: lib.discovery handles non-R-package repo" lib_discovery_on_self

# Agents (Phase 4)
run "Agents: no removed rforge_* MCP refs"                  agent_no_mcp_refs
run "Agents: orchestrator has name+description frontmatter" agent_frontmatter_complete
run "Agents: orchestrator recipes valid (real+safe engines, real modules)" agent_engines_valid
run "Docs: commands.md mirrors command files (sections + flags)" commands_doc_in_sync

# Docs site
run "mkdocs.yml parses"            mkdocs_parses
run "mkdocs nav files all exist"   mkdocs_nav_files_exist
run "mkdocs no orphaned guide/tutorial/reference pages" mkdocs_no_orphan_pages

# Skills
run "Skill: embedded script syntax-checks"   skill_extract_and_check
run "Skill: frontmatter has required fields" skill_frontmatter_complete

# Lib modules (Path B Phase B.1 ports)
run "Lib: pytest suite (discovery + deps + status + init)"   lib_pytest
run "Lib: CLI smoke (discovery + deps + status + init)" lib_cli_smoke
run "Lib: reference docs in sync with source" lib_reference_in_sync
run "Docs: version/count strings in sync with package.json" version_sync_in_sync
run "Lib: rcmd CLI smoke (R-free — accepts engine_missing envelope)" lib_rcmd_smoke
run "Dogfood: lib.cranlint Tier-4 advisory CLI on a fixture package" lib_cranlint_smoke
run "Dogfood: lib.runiverse CLI smoke (offline → warn envelope)" lib_runiverse_smoke
run "Dogfood: lib.s7review CLI smoke (advisory S7 convention envelope)" lib_s7review_smoke
run "Dogfood: lib.changed CLI smoke (JSON envelope, never raises)" lib_changed_smoke
run "Scaffolding: use-* commands have frontmatter" scaffold_cmds_frontmatter
run "Scaffolding: lib.scaffold + usethis_infra smoke" scaffold_lib_smoke
run "Scaffolding: use-* arguments match Usage" scaffold_args_usage_sync

echo ""
echo "═══════════════════════════════════════════════════════════════"
printf '%s' "$RESULTS"
echo "Total: $((PASS + FAIL))  |  Passed: $PASS  |  Failed: $FAIL"
echo "═══════════════════════════════════════════════════════════════"

[ $FAIL -eq 0 ]

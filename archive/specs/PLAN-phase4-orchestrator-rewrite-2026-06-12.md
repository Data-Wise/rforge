# Phase 4 — Orchestrator Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stale `agents/orchestrator.md` (which delegates to 13 removed `rforge_*` MCP tools) with a working orchestrator that delegates via `python3 -m lib.*` envelopes, guarded by three new `tests/test-all.sh` structural checks.

**Architecture:** The agent is a prose `.md` artifact, so it is verified *structurally*, not by unit tests. We write the three failing structural checks first (TDD), watch the regression guard fail on the current MCP-laden file, then rewrite the agent so all checks pass. The agent itself is a thin intent-router: an intent→`lib.*` mapping table, a read-only/recommend-only safety gate, and an envelope-synthesis section.

**Tech Stack:** Bash (`tests/test-all.sh` `run "<name>" <fn>` pattern), Python 3 stdlib (one tiny helper to parse `lib.rcmd` argparse choices), Markdown + YAML frontmatter (the agent file).

**Spec:** `docs/specs/SPEC-phase4-orchestrator-rewrite-2026-06-12.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `agents/orchestrator.md` | **Rewrite** | The orchestrator agent: frontmatter + role + intent table + lib recipes + safety gate + synthesis. Zero `rforge_` references. |
| `tests/test-all.sh` | **Modify** | Add 3 helper fns + 3 `run` registrations (regression guard, frontmatter, no-phantom-engines). |
| `tests/_check_agent_engines.py` | **Create** | Tiny stdlib helper: assert every `--kind X` named in `agents/orchestrator.md` is a real `lib.rcmd` choice. (Kept as a file so the bash check stays a one-liner.) |
| `package.json` | **Modify** | Version `2.8.0 → 2.9.0` (source of truth). |
| `.claude-plugin/plugin.json` | **Modify** (via `version_sync.py`) | Version sync. |
| `.claude-plugin/marketplace.json` | **Modify** (manual) | `metadata.version` + `plugins[0].version` → 2.9.0. |
| `CHANGELOG.md` | **Modify** | `[Unreleased]` → `[2.9.0] - <ship date>`. |
| `.STATUS` | **Modify** | Phase 4 shipped; clear from roadmap/Next Action. |
| `CLAUDE.md` | **Modify** | Orchestrator delegates via `lib.*` (not MCP); test-gate count 33 → 36. |

---

## Task 0: Create the feature worktree

The agent `.md` is a behavioral artifact — treat as code, not docs-on-dev. New files (`tests/_check_agent_engines.py`) are blocked on `dev` by branch-guard. Work on a feature branch.

- [ ] **Step 1: Create worktree from dev**

```bash
git worktree add ~/.git-worktrees/rforge/feature-phase4-orchestrator -b feature/phase4-orchestrator dev
```

- [ ] **Step 2: Confirm location and branch**

```bash
cd ~/.git-worktrees/rforge/feature-phase4-orchestrator
git branch --show-current   # expect: feature/phase4-orchestrator
pwd
```
Expected: branch is `feature/phase4-orchestrator`; all subsequent paths are relative to this worktree root.

---

## Task 1: Regression guard — no `rforge_` in any agent file (TDD: fails first)

**Files:**
- Modify: `tests/test-all.sh` (add helper fn + `run` registration)

This is the P0 check — it must FAIL on the current stale file, proving it catches the exact bug.

- [ ] **Step 1: Add the helper function**

Add to `tests/test-all.sh` near the other helper functions (after the hook helpers block, before the final `run` registrations):

```bash
# Phase 4: no removed rforge_* MCP tool references may survive in any agent file.
agent_no_mcp_refs() {
    ! grep -lq "rforge_" agents/*.md
}
```

- [ ] **Step 2: Register the check**

In the `run` block (alongside the other structure checks, e.g. just before the `# Docs site` group), add:

```bash
run "Agents: no removed rforge_* MCP refs" agent_no_mcp_refs
```

- [ ] **Step 3: Run the suite — verify THIS check fails**

Run: `bash tests/test-all.sh 2>&1 | grep -A2 "no removed rforge"`
Expected: `❌ Agents: no removed rforge_* MCP refs` (the current `agents/orchestrator.md` has 43 `rforge_` refs). This proves the guard works.

- [ ] **Step 4: Commit the failing guard**

```bash
git add tests/test-all.sh
git commit -m "test(agents): add regression guard for removed rforge_* MCP refs (fails on stale file)"
```

---

## Task 2: Agent frontmatter check (TDD: fails first)

**Files:**
- Modify: `tests/test-all.sh`

Current `agents/orchestrator.md` has no YAML frontmatter, so this also fails first.

- [ ] **Step 1: Add the helper function**

```bash
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
```

- [ ] **Step 2: Register the check**

```bash
run "Agents: orchestrator has name+description frontmatter" agent_frontmatter_complete
```

- [ ] **Step 3: Run — verify it fails**

Run: `bash tests/test-all.sh 2>&1 | grep "name+description frontmatter"`
Expected: `❌ Agents: orchestrator has name+description frontmatter` (no frontmatter yet).

- [ ] **Step 4: Commit**

```bash
git add tests/test-all.sh
git commit -m "test(agents): require name+description frontmatter on orchestrator (fails first)"
```

---

## Task 3: No-phantom-engines check (TDD: write check + helper)

**Files:**
- Create: `tests/_check_agent_engines.py`
- Modify: `tests/test-all.sh`

Asserts every `--kind X` the agent names is a real `lib.rcmd` choice. On the current file there are no `--kind` tokens, so it passes vacuously now — but it locks the invariant for the rewrite.

- [ ] **Step 1: Create the helper script**

Create `tests/_check_agent_engines.py`:

```python
"""Assert every `lib.rcmd --kind X` named in agents/orchestrator.md is a real choice.

Pure stdlib. Parses the rcmd argparse `--kind` choices by importing the module's
parser is overkill; instead read the choices from `python3 -m lib.rcmd --help`.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "agents" / "orchestrator.md"


def rcmd_kinds() -> set[str]:
    out = subprocess.run(
        [sys.executable, "-m", "lib.rcmd", "--help"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout
    m = re.search(r"--kind \{([^}]+)\}", out)
    if not m:
        print("could not parse --kind choices from lib.rcmd --help")
        sys.exit(1)
    return {k.strip() for k in m.group(1).split(",")}


def agent_kinds() -> set[str]:
    text = AGENT.read_text(encoding="utf-8")
    return set(re.findall(r"--kind\s+([a-z-]+)", text))


def main() -> int:
    valid = rcmd_kinds()
    used = agent_kinds()
    phantom = used - valid
    if phantom:
        print(f"agent names non-existent lib.rcmd kinds: {sorted(phantom)}")
        print(f"valid kinds: {sorted(valid)}")
        return 1
    print(f"ok: {len(used)} agent --kind tokens, all valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Add the helper function + register**

In `tests/test-all.sh`:

```bash
# Phase 4: agent must not name lib.rcmd engines that don't exist.
agent_engines_valid() {
    python3 tests/_check_agent_engines.py
}
```

```bash
run "Agents: orchestrator names only real lib.rcmd engines" agent_engines_valid
```

- [ ] **Step 3: Run — verify it passes (vacuously, no --kind yet)**

Run: `bash tests/test-all.sh 2>&1 | grep "real lib.rcmd engines"`
Expected: `✅ Agents: orchestrator names only real lib.rcmd engines` (current file has no `--kind` tokens).

- [ ] **Step 4: Commit**

```bash
git add tests/_check_agent_engines.py tests/test-all.sh
git commit -m "test(agents): assert orchestrator names only real lib.rcmd engines"
```

---

## Task 4: Rewrite the orchestrator agent (makes Tasks 1–2 pass, keeps Task 3 green)

**Files:**
- Rewrite: `agents/orchestrator.md`

Replace the entire file. This is the core deliverable. The content below is complete — paste it verbatim, then adjust prose only if a `lib.*` CLI flag differs from what's shown.

- [ ] **Step 1: Overwrite `agents/orchestrator.md` with the new content**

````markdown
---
name: orchestrator
description: >
  R-package ecosystem orchestrator. Recognizes the intent behind a request
  (code change, new function, bug fix, deps audit, CRAN readiness, ecosystem
  health) and runs the matching rforge lib.* analyses via Bash, then
  synthesizes the JSON envelopes into one ADHD-friendly summary. Read-only
  analyses auto-run; anything that mutates files or touches the outside world
  is recommended, never executed. Use for "check my package", "what's the
  impact of this change", "is this CRAN-ready", "ecosystem status".
---

# RForge Orchestrator Agent

You orchestrate R-package ecosystem work for the rforge plugin. You act through
your tools — **Bash** (to run `python3 -m lib.*` and read JSON envelopes) and
**Read** (to inspect files). You do **not** call MCP tools (rforge-mcp was
absorbed into pure-Python `lib/` modules in v1.3.0 and no longer exists) and you
cannot invoke `/rforge:*` slash commands directly.

## How you delegate

`lib/` is a Python package. Always invoke modules as `python3 -m lib.<module>`
(never `python3 lib/<module>.py` — that breaks relative imports). Run from the
package or ecosystem root. Every module emits a JSON envelope on stdout.

## Step 1 — Recognize the intent

Match the request to exactly one intent:

| Intent | Triggers |
|--------|----------|
| CODE_CHANGE | "update", "modify", "change", "improve", "refactor" |
| NEW_FUNCTION | "add function", "new function", "implement" |
| BUG_FIX | "fix", "broken", "not working", "error", "failing" |
| DEPS_AUDIT | "dependencies", "imports", "DESCRIPTION", "deps" |
| CRAN_READINESS | "cran-ready", "prep for cran", "submit", "release to cran" |
| ECOSYSTEM_HEALTH | "status", "health", "overview", "dashboard" |

If the request is ambiguous, state your best-guess intent and the exact commands
you will run **before** running them, so a wrong guess is visible.

## Step 2 — Run the read-only recipe

Run these (and only these) automatically. They are all read-only:

| Intent | Auto-run (read-only) |
|--------|----------------------|
| CODE_CHANGE | `python3 -m lib.discovery` · `python3 -m lib.deps` · `python3 -m lib.rcmd --kind test` |
| NEW_FUNCTION | `python3 -m lib.discovery` · `python3 -m lib.rcmd --kind document` |
| BUG_FIX | `python3 -m lib.rcmd --kind test` · `python3 -m lib.deps` |
| DEPS_AUDIT | `python3 -m lib.deps_sync` · `python3 -m lib.deps` |
| CRAN_READINESS | `python3 -m lib.rcmd --kind cran-prep` · `python3 -m lib.cranlint` · `python3 -m lib.runiverse` |
| ECOSYSTEM_HEALTH | `python3 -m lib.status` · `python3 -m lib.discovery` · `python3 -m lib.deps` |

`lib.deps_sync` runs in its dry-run (read-only) form by default — never pass
`--write`. `lib.runiverse` is advisory (read-only, degrades to a `warn` envelope
offline). For `lib.rcmd`, pass `--path <pkg>` when operating on a specific
package.

## Step 3 — Safety boundary (recommend-only)

**Never auto-run** anything that mutates files or reaches the outside world.
When the user's goal implies one of these, name the exact `/rforge:*` command
and **stop** — let the user run it:

- CRAN/GitHub handoff: `/rforge:r:submit` (and its `--promote`, `--universe`)
- External uploads: `/rforge:r:winbuilder`, `/rforge:r:rhub`
- File writes: `/rforge:r:document`, `/rforge:r:style`,
  `/rforge:r:deps-sync --write`
- Reverse-dependency runs (heavy/external): `/rforge:r:revdep`

This mirrors rforge's "never auto-submit" principle.

## Step 4 — Synthesize

Parse each envelope's `status`, `blockers`, and `hints`. Report:

```
┌─ RForge Orchestrator ─────────────────────────────┐
│ Intent: <INTENT>                                  │
│ Ran: <commands actually executed>                 │
│                                                   │
│ Findings:                                         │
│   • <module>: <status> — <one-line takeaway>      │
│                                                   │
│ 🔴 Blockers: <from any non-ok envelope, verbatim> │
│                                                   │
│ → Next: <recommended /rforge:* command, incl.     │
│         any recommend-only handoff>               │
└───────────────────────────────────────────────────┘
```

Never claim success an envelope didn't report. A `warn`/`error` envelope is a
blocker, surfaced verbatim. If a command fails to run (non-zero exit, no JSON),
report the failure with the command shown — do not retry blindly.
````

- [ ] **Step 2: Run the suite — Tasks 1 & 2 now pass, Task 3 stays green**

Run: `bash tests/test-all.sh 2>&1 | grep -E "rforge_ MCP refs|frontmatter|real lib.rcmd engines"`
Expected (all three green):
```
✅ Agents: no removed rforge_* MCP refs
✅ Agents: orchestrator has name+description frontmatter
✅ Agents: orchestrator names only real lib.rcmd engines
```

- [ ] **Step 3: Run the FULL suite to confirm nothing else broke**

Run: `bash tests/test-all.sh; echo "exit=$?"`
Expected: `exit=0`; total check count is now 36 (was 33).

- [ ] **Step 4: Run the pytest suite (no lib change, must stay green)**

Run: `python3 -m pytest tests/ -q`
Expected: all pass (230 cases; unchanged — no `lib/` code touched).

- [ ] **Step 5: Commit the rewrite**

```bash
git add agents/orchestrator.md
git commit -m "feat(agents): rewrite orchestrator to delegate via lib.* envelopes

Drops all 13 removed rforge_* MCP tools. Intent->lib mapping table,
read-only/recommend-only safety gate (never-auto-submit), envelope
synthesis. Last craft-parity item (Phase 4)."
```

---

## Task 5: Version bump + docs

**Files:**
- Modify: `package.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `.STATUS`, `CLAUDE.md` (+ `plugin.json` via script)

- [ ] **Step 1: Bump the source-of-truth version**

Edit `package.json`: `"version": "2.8.0"` → `"version": "2.9.0"`.

- [ ] **Step 2: Propagate derived versions**

Run: `python3 scripts/version_sync.py`
Then verify: `python3 scripts/version_sync.py --check`
Expected: `--check` exits 0 (no drift).

- [ ] **Step 3: Manually bump marketplace.json (script does not touch it)**

Edit `.claude-plugin/marketplace.json`: set BOTH `metadata.version` and `plugins[0].version` to `2.9.0`.

- [ ] **Step 4: Verify all 4 version sources agree**

Run: `bash tests/test-all.sh 2>&1 | grep "version sources agree"`
Expected: `✅ All 4 version sources agree (plugin/marketplace/package)`.

- [ ] **Step 5: Update CHANGELOG.md**

Convert the `[Unreleased]` heading to `[2.9.0] - <today's date>` and add under it:

```markdown
### Changed
- **Orchestrator agent rewritten** — `agents/orchestrator.md` now delegates via
  `python3 -m lib.*` envelopes instead of the removed `rforge_*` MCP tools
  (absorbed into `lib/` in v1.3.0). Adds an intent→lib mapping, a
  read-only/recommend-only safety boundary (mirrors never-auto-submit), and
  envelope synthesis. Last craft-parity item (Phase 4).

### Added
- Three `tests/test-all.sh` guards (now 36 checks): no `rforge_` MCP refs in
  agent files, orchestrator frontmatter present, orchestrator names only real
  `lib.rcmd` engines.
```

- [ ] **Step 6: Update CLAUDE.md**

In the test-gate section, change `33 checks` → `36 checks` and list the three new agent guards. In "Current state", note v2.9.0 ships the Phase 4 orchestrator rewrite (lib-envelope delegation, MCP refs gone).

- [ ] **Step 7: Update .STATUS**

Set `version: 2.9.0`, move Phase 4 from roadmap to `shipped:`, clear it from `## 🎯 Next Action`.

- [ ] **Step 8: Commit docs + version**

```bash
git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json mkdocs.yml README.md CHANGELOG.md CLAUDE.md .STATUS
git commit -m "chore(release): v2.9.0 — Phase 4 orchestrator rewrite + version/doc sync"
```

---

## Task 6: Final gates + PR

- [ ] **Step 1: Both gates green**

Run: `bash tests/test-all.sh && python3 -m pytest tests/ -q`
Expected: test-all 36/36, pytest all pass, overall exit 0.

- [ ] **Step 2: Confirm zero MCP refs remain repo-wide in agents**

Run: `grep -rc "rforge_" agents/ || echo "clean"`
Expected: `clean` (or `0`).

- [ ] **Step 3: Push and open PR feature → dev**

```bash
git push -u origin feature/phase4-orchestrator
gh pr create --base dev --title "feat(agents): Phase 4 orchestrator rewrite (v2.9.0)" \
  --body "Rewrites the stale orchestrator (13 removed rforge_* MCP tools) to delegate via lib.* envelopes. Intent→lib mapping, read-only/recommend-only safety gate, envelope synthesis. +3 test-all guards (33→36). Spec: docs/specs/SPEC-phase4-orchestrator-rewrite-2026-06-12.md"
```

- [ ] **Step 4: After merge — release dev → main + tap sync**

Per the standard rforge release pipeline (CLAUDE.md): PR dev → main, GitHub release v2.9.0, Homebrew formula + `generator/manifest.json` sync (`generate.py rforge --diff` must report IDENTICAL), CI verify on main. Docs deploy is automatic on push to main.

---

## Self-Review

**Spec coverage:**
- Remove all `rforge_*` refs → Task 4 + guard Task 1. ✓
- Intent→lib mapping table → Task 4 Step 2/3. ✓
- Read-only auto / recommend-only → Task 4 Step 3 (Safety boundary). ✓
- Synthesis box → Task 4 Step 4. ✓
- Regression guard test → Task 1. ✓
- Frontmatter check → Task 2. ✓
- No-phantom-engines check → Task 3. ✓
- Counts unchanged (1 agent, 35 commands) → no command/agent file added; only `tests/_check_agent_engines.py` (a test helper, not a command/agent). ✓
- Version v2.9.0 + docs → Task 5. ✓
- #9 note: behavioral — the agent routes by intent, not command name, so no `quick`/`thorough` dependency; nothing to implement here (documented in spec Open questions). ✓

**Placeholder scan:** All code/commands shown literally; CHANGELOG/`.STATUS` edits specify exact strings. The agent content block is complete and pasteable. No TBD/TODO. ✓

**Type/name consistency:** Helper fn names (`agent_no_mcp_refs`, `agent_frontmatter_complete`, `agent_engines_valid`) and the `run` registration strings match between definition and use. The check script path `tests/_check_agent_engines.py` is consistent across Task 3 and Task 6. ✓

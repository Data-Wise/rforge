# r:rhub Command — Orchestration Plan

> **Branch:** `feature/r-rhub`
> **Base:** `dev`
> **Worktree:** `~/.git-worktrees/rforge/feature-r-rhub`
> **Spec:** `docs/specs/SPEC-r-rhub-command-2026-06-20.md`
> **Version Target:** v2.14.0 (update existing command — no count increment)

## Objective

Fix the broken `r:rhub` command (currently hangs headlessly) by implementing proper
platform selection, pre-flight checks, and non-interactive dispatch. Resolves 5 structural
bugs and adds guard infrastructure (`_rhub_preflight`, `_check_rhub_yaml`, `_RHUB_PRESETS`,
`_RHUB_BROKEN_PLATFORMS`) with 15 new tests in `tests/test_rcmd_rhub.py`.

## Phase Overview

| Phase | Increment | Priority | Effort | Status |
|-------|-----------|----------|--------|--------|
| 1 | lib/rcmd.py — constants + helpers | High | ~45 min | |
| 2 | lib/rcmd.py — r_snippet + run() wire-in | High | ~45 min | |
| 3 | commands/r/rhub.md update | Medium | ~20 min | |
| 4 | tests/test_rcmd_rhub.py (new file) | High | ~30 min | |
| 5 | Gate verification + docs/commands.md | High | ~15 min | |

## Phase 1: lib/rcmd.py — Constants + Helpers

**Scope:** Add module-level dicts and helper functions. No changes to `run()` yet.

**Key files:**
- `lib/rcmd.py` — add near top of file (with other module-level dicts)

### Tasks

- [ ] 1.1 Add `_RHUB_BROKEN_PLATFORMS` dict (after existing module-level dicts)
- [ ] 1.2 Add `_RHUB_PRESETS` dict — canonical form: `cran-submission` includes atlas per Q6
- [ ] 1.3 Add `_check_rhub_yaml(pkg_path)` helper — scans setup-deps blocks for `pak-version: stable`
      AND checks default config field for broken platform names
      - Returns `[]` if rhub.yaml absent (yaml_missing is separate)
      - Finding severity: `'advisory'` (not `'warn'`)
      - Retains `block` and `fix` as informational extras (non-standard but documented)
      - TODO comment: `# TODO: remove or loosen when r-lib/pak #887 is fixed in devel`
- [ ] 1.4 Add `_rhub_preflight(pkg_path, platforms)` helper — unified pre-flight:
      (a) yaml_missing → hard-stop (returns immediately, no further checks)
      (b) broken_platform → hard-stop (one error per broken platform)
      (c) delegates to `_check_rhub_yaml()` for advisories
- [ ] 1.5 Add `_rhub_actions_url(pkg_path)` helper — constructs GitHub Actions URL from
      `git remote get-url origin`; normalizes SSH→HTTPS; strips `.git` suffix; appends `/actions`

**Verification after Phase 1:**
```bash
python3 -c "import lib.rcmd as r; print(r._RHUB_PRESETS['cran-submission'])"
python3 -c "import lib.rcmd as r; print(r._check_rhub_yaml('/tmp'))"
```

## Phase 2: lib/rcmd.py — r_snippet + run() Wire-in

**Scope:** Replace broken rhub dispatch logic. Two sub-tasks (snippets, then run()).

**Key files:**
- `lib/rcmd.py` lines 494–512 (r_snippet, both rhub paths)
- `lib/rcmd.py` lines 655–685 (run() signature and body)
- `lib/rcmd.py` line 1001 and 1036 (verify kind references still work)

### Tasks

- [ ] 2.1 Replace `r_snippet("rhub")` body (lines 507–512):
      - New snippet for `rc_mode=False`: `rhub::rhub_check({p}, platforms={plats_r})`
        (never calls `rhub_setup()`; never passes NULL)
      - New snippet for `rc_mode=True`: `rhub::rc_submit({p})` (no platforms arg)
      - Both emit JSON envelope: `list(submitted=TRUE, platforms=..., note="...")`
      - Accept `platforms: list` and `rc_mode: bool` kwargs in `r_snippet()`
- [ ] 2.2 Remove the stale `winbuilder/platform='rhub'` sub-path (lines 497–501):
      - Delete the `if platform == "rhub":` branch inside `kind == "winbuilder"`
      - After deletion: `kind='winbuilder'` only dispatches to win-builder flavors
      - Leave a code comment: `# rhub dispatch removed — use kind='rhub' directly`
- [ ] 2.3 Update `run()` signature (line 658):
      - Add `platforms=None, preset=None, rc_mode=False` kwargs
      - Document: `platforms` is `list[str]`; `preset` is `str`; `rc_mode` is `bool`
- [ ] 2.4 Add rhub dispatch logic in `run()` for `kind == "rhub"`:
      - Resolve platforms: preset → explicit list → default (`cran-submission`)
      - Unknown preset → return error envelope immediately
      - Call `_rhub_preflight(path, platforms)` → collect errors and advisories
      - Errors → return error envelope immediately (no R dispatch)
      - Advisories → continue to dispatch; merge into returned envelope as `findings`
      - Call `r_snippet("rhub", path, platforms=platforms, rc_mode=rc_mode)`
      - After dispatch: call `_rhub_actions_url(path)` + `webbrowser.open(url)`
      - Return envelope with `run_url`, `findings` (advisories), `submitted=True`
- [ ] 2.5 Update argparse in `__main__` block (if present) to expose `--platforms`,
      `--preset`, `--rc-mode` CLI flags

**Verification after Phase 2:**
```bash
# Dry-run: should reach snippet generation without hanging
python3 -c "
from lib.rcmd import r_snippet
print(r_snippet('rhub', '.', platforms=['linux', 'windows'], rc_mode=False))
"
```

## Phase 3: commands/r/rhub.md Update

**Scope:** Update the existing command file. Do NOT create a new one.

**Key files:**
- `commands/r/rhub.md` (UPDATE existing — do not create new)

### Tasks

- [ ] 3.1 Update frontmatter `arguments:` array — add `platforms`, `preset`, `rc-mode`
      (see spec §2 for exact YAML)
- [ ] 3.2 Update `argument-hint` to show full signature:
      `"[package] [--platforms linux,windows] [--preset cran-submission] [--rc-mode]"`
- [ ] 3.3 Replace `## Process` section — show all four invocation patterns (default, preset,
      explicit platforms, rc-mode)
- [ ] 3.4 Add `## Pre-flight checks` section (4 items as in spec §2)
- [ ] 3.5 Replace `## Output Format` section — show success and error format (spec §2)
- [ ] 3.6 Update the `!!! warning` admonition — remove the false "rhub_setup() is idempotent"
      claim; replace with accurate "rhub.yaml must already exist" note
- [ ] 3.7 Update `## Related Commands` section (verify links still valid)

**Verification after Phase 3:**
```bash
python3 tests/_check_commands_doc.py  # must still pass
```

## Phase 4: tests/test_rcmd_rhub.py (New File)

**Scope:** 15 new tests. New file — do NOT add to `tests/test_rcmd.py`.

**Key files:**
- `tests/test_rcmd_rhub.py` (NEW)

### Tasks

- [ ] 4.1 Copy test stubs from spec §3, implementing all 15 tests:
      - `_check_rhub_yaml` tests (5): missing pak-version fires; pak stable clean; yaml missing
        returns []; two blocks one missing (assert block 2 fires AND block 1 clean);
        default broken platform advisory
      - `_rhub_preflight` tests (4): yaml_missing hard-blocks; broken platform hard-blocks;
        clean yaml no findings; advisory does not produce error
      - Preset tests (3): cran-submission includes atlas; strict includes clang-asan;
        broken platform dict contents
      - Sequence test (1): yaml_missing stops before broken_platform check
      - rc_submit test (1): r_snippet with rc_mode=True must not contain `platforms=`
- [ ] 4.2 Verify all 15 tests collect correctly:
```bash
python3 -m pytest tests/test_rcmd_rhub.py -v
```

## Phase 5: Gate Verification + docs/commands.md

**Scope:** Run all gates, fix docs/commands.md if needed.

### Tasks

- [ ] 5.1 Run `python3 tests/_check_commands_doc.py` — if r:rhub entry needs updating,
      fix `docs/commands.md` (the check will tell you what's missing)
- [ ] 5.2 Run full test suite:
```bash
python3 -m pytest tests/ -v --tb=short
bash tests/test-all.sh
```
- [ ] 5.3 Fix any failures. Common expected issues:
      - `test-all.sh` check for `commands.md` sync — fix `docs/commands.md` r:rhub entry
      - Any `test_rcmd.py` test that referenced the old `kind='winbuilder', platform='rhub'` path
      - `gen_lib_reference.py --check` — `_rhub_preflight` and `_check_rhub_yaml` are prefixed `_`
        so they should NOT appear in generated reference docs (no doc update needed)
- [ ] 5.4 Commit when all gates pass:
```bash
# Commands: conventional commits per-phase or one per logical group
# feat(r:rhub): fix headless dispatch, add pre-flight checks + presets
# test(r:rhub): add 15 tests for preflight, presets, pak-version guard
# docs(r:rhub): update command file with --platforms/--preset/--rc-mode
```

## Documentation & Discoverability

- [x] `commands/r/rhub.md` updated (Phase 3)
- [ ] `docs/commands.md` r:rhub entry updated (Phase 5)
- [x] No new tutorial needed (existing cran-submission tutorial references r:rhub)
- [x] No REFCARD update needed (r:rhub already appears; no new flags table)
- [x] No version bump (update to existing command, count stays 41)
- [x] No `scripts/version_sync.py` run needed (no count change)
- [x] No `test-all.sh` counter update (43 shell checks unchanged; new pytest file auto-collected)

## Friction Prevention

- **Read ORCHESTRATE + spec first** before writing any code
- **Verify CWD** is the worktree (`pwd` should show `~/.git-worktrees/rforge/feature-r-rhub`)
- **`lib/rcmd.py` is large** (~1100 lines) — use `Read` with offset/limit for targeted sections
  rather than reading the whole file
- **The early-return bug** (Spec B's `if findings: return ...`) must NOT appear in Phase 2 —
  advisories never short-circuit dispatch
- **`severity: 'advisory'`** (not `'warn'`) in all rhub findings — cranlint precedent
- **`_check_rhub_yaml` returns `[]` when yaml absent** — `_rhub_preflight` handles yaml_missing
  separately, so there's no double-check
- **Stop after each phase** and commit before moving to the next — don't batch all 5 phases

## Acceptance Criteria

- [ ] `python3 -m pytest tests/test_rcmd_rhub.py` — all 15 tests pass
- [ ] `python3 -m pytest tests/` — all 400+ tests pass (no regressions)
- [ ] `bash tests/test-all.sh` — all 43 checks pass
- [ ] `r_snippet("rhub", ..., platforms=["linux"])` produces valid R (no NULL, no rhub_setup call)
- [ ] `r_snippet("rhub", ..., rc_mode=True)` produces `rhub::rc_submit(...)`, no `platforms=`
- [ ] `_rhub_preflight` returns error on missing rhub.yaml; advisory on missing pak-version
- [ ] `run("rhub", path, preset="cran-submission")` resolves to 4-platform list incl. atlas
- [ ] Stale `winbuilder/platform='rhub'` sub-path removed from `r_snippet()`
- [ ] `commands/r/rhub.md` has `--platforms`, `--preset`, `--rc-mode` in frontmatter

## Commit Strategy

- `feat(r:rhub): implement pre-flight checks + presets (lib/rcmd.py phase 1+2)`
- `test(r:rhub): add 15 pre-flight + preset tests (test_rcmd_rhub.py)`
- `docs(r:rhub): update command file with new flags + pre-flight section`
- `chore(r:rhub): fix docs/commands.md sync` (if needed)

Or combine into fewer commits — gate pass matters more than commit granularity.

## Session Instructions

### How to Start

```bash
cd ~/.git-worktrees/rforge/feature-r-rhub
claude
```

On session start, paste:
> Read `ORCHESTRATE-r-rhub.md` and the spec at `docs/specs/SPEC-r-rhub-command-2026-06-20.md`.
> Start Phase 1 — add the module-level constants and helper functions to `lib/rcmd.py`.

### Phase-by-Phase

1. Read the relevant section of `lib/rcmd.py` before editing (use offset/limit)
2. Implement per-phase tasks from this file
3. Run the phase verification command
4. Commit the phase (or stage for end-of-phase commit)
5. STOP after each phase and confirm before proceeding

### Key Line References (lib/rcmd.py)

- Lines 494–512: current rhub dispatch in `r_snippet()` — both paths to replace/remove
- Lines 636–642: `_invoke_r()` — how R is called headlessly (no PTY)
- Lines 655–685: `run()` signature and initial guards
- Line 984: `env.get("findings")` in cran-prep path — confirms `findings` key is used elsewhere
- Line 1001: references to `("winbuilder", "rhub")` — verify after winbuilder sub-path removal

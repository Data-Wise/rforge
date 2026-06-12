# mkdocs version/count macros — Orchestration Plan

> **Branch:** `feature/mkdocs-version-macros`
> **Base:** `dev`
> **Worktree:** `~/.git-worktrees/rforge/feature-mkdocs-version-macros`
> **Spec:** `docs/specs/SPEC-mkdocs-version-macros-2026-06-12.md`
> **Target:** v2.8.0

## Objective

Make version/command-count strings render from a single source of truth (`package.json`) so the docs
stop drifting (root cause of the 33→35 staleness fixed in `5267825`). Two layers, Python-native:
`mkdocs-macros` render layer + `scripts/version_sync.py` (`--check` CI gate). No command-surface change.

## Phase Overview

| Phase | Task | Priority | Status |
| ----- | ---- | -------- | ------ |
| 1 | Enable macros: `mkdocs-macros-plugin` in `docs.yml` `pip install`; `plugins: - macros` + `extra.rforge.{version,prev_version,release_date,command_count:35}` in `mkdocs.yml`. Confirm `mkdocs build` green. | High | Todo |
| 2 | Sync script: `scripts/version_sync.py` (`--version`/`--dry-run`/`--check`, reads `package.json`, writes `mkdocs.yml extra`, `plugin.json`, `README.md`, `CLAUDE.md`) matching `gen_lib_reference.py` style; `tests/test_version_sync.py`. | High | Todo |
| 3 | Convert ~12 user-facing docs to `{{ rforge.version }}` / `{{ rforge.command_count }}` (NOT historical refs); `mkdocs build --strict` to catch unrendered braces; wrap code blocks containing `{{` in `{% raw %}`. | High | Todo |
| 4 | Release runbook: update `CLAUDE.md`/`.STATUS`/`CHANGELOG` with the "bump `package.json` → `version_sync.py`" step. *(docs-only — could also land on dev)* | Medium | Todo |
| 5 | CI drift gate: run `python3 scripts/version_sync.py --check` in the main test workflow. | Medium | Todo |
| 6 | `finish`: tests green → PR `feature/mkdocs-version-macros` → `dev`; cut v2.8.0. | High | Todo |

## Acceptance Criteria

- [ ] `mkdocs build --strict` passes with `{{ rforge.version }}` rendering `2.7.0` (no literal braces in output)
- [ ] `python3 scripts/version_sync.py --check` exits 0 on a synced tree, 1 on injected drift
- [ ] `python3 -m pytest tests/` and `bash tests/test-all.sh` both green
- [ ] No current-version/count string left hardcoded in the ~12 user-facing docs (historical refs untouched)
- [ ] `docs.yml` installs `mkdocs-macros-plugin` (else build errors on unknown plugin)
- [ ] CI fails on version drift

## Risks / Notes

- **Jinja in fenced code blocks** (e.g. GitHub Actions `${{ }}`): macros will try to interpret `{{ … }}`
  → wrap those blocks in `{% raw %}…{% endraw %}`. Audit during Phase 3.
- `lib/formatters.py` is **intentionally** absent from `gen_lib_reference.py` `MODULES` — do **not** add a page.
- `command_count` stays a hardcoded `extra` field for v1 (CI-validated); filesystem derivation is deferred.

## How to Start

```bash
cd ~/.git-worktrees/rforge/feature-mkdocs-version-macros
# Python tooling (not npm, despite package.json):
pip install mkdocs-material mkdocs-macros-plugin    # or into a venv
claude
```

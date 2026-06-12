# SPEC: mkdocs version/count macros + sync script

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-12
- **Target version:** v2.8.0
- **Author:** brainstormed with Claude, grounded in the 2026-06-12 site audit (`/craft:site:update` on rforge)
- **Related:** [SPEC-phase3-namespacing-2026-05-11](SPEC-phase3-namespacing-2026-05-11.md)

## Summary

Stop version/command-count strings in the docs from drifting by introducing a single source of
truth (`package.json`) rendered through **mkdocs-macros** (`{{ rforge.version }}`,
`{{ rforge.command_count }}`) plus a Python `scripts/version_sync.py` for files that can't use
macros (read raw on GitHub). Models scholar's proven two-layer system, re-implemented in Python to
match rforge's existing tooling. No command-surface change (still 35 commands).

## Motivation

The 2026-06-12 audit found `mkdocs.yml` advertising **33 commands** while the code shipped **35**
(fixed manually in `5267825`). Root cause: counts and versions are hardcoded across ~12 user-facing
doc files plus `mkdocs.yml`, `README.md`, and `CLAUDE.md`, so every release silently strands stale
numbers. rforge already proved the "generate-from-source, `--check` in CI" pattern works for API
reference pages (`scripts/gen_lib_reference.py`); this applies the same discipline to versions/counts.

## Goals

- One authoritative source: `package.json` version → everything else derives from it.
- Live docs render the current version/count at build time — zero manual edits per release.
- A `--check` mode that fails CI when any tracked file drifts (mirrors `gen_lib_reference.py --check`).
- Released as v2.8.0 with the live site reflecting macros on first `dev→main` ship.

## Non-goals

- **Not** templating historical references — "What's New", CHANGELOG entries, `SPEC-*`/`RESEARCH-*`
  docs, and "NEW in vX.Y.Z" prose keep their literal versions (same rule scholar follows).
- **Not** auto-deriving `command_count` from the filesystem in v1 — keep it an explicit field in
  `mkdocs.yml extra` (manually bumped, but CI-validated), matching scholar. Auto-derivation is deferred.
- No change to `gen_lib_reference.py` or the command surface.

## Scope

### In scope (decided)

| Kind | Target | Engine | Notes |
|---|---|---|---|
| Config | `mkdocs.yml` → add `plugins: - macros` and `extra.rforge.{version, prev_version, release_date, command_count}` | mkdocs-macros | `command_count: 35` |
| Docs | ~12 user-facing files (QUICK-START, index, REFCARD, installation, lib-modules, workflows/index, getting-started + 4 tutorials) | `{{ rforge.* }}` | current-version + count refs only |
| Script | new `scripts/version_sync.py` (+ `--check`, `--dry-run`, `--version`) | Python (stdlib) | syncs `mkdocs.yml extra`, `README.md`, `CLAUDE.md`, `plugin.json` from `package.json` |
| CI | `.github/workflows/docs.yml` → `pip install mkdocs-material mkdocs-macros-plugin` | — | else build crashes on unknown plugin |
| CI | main test workflow → run `version_sync.py --check` | Python | drift gate |

### Out of scope (YAGNI / deferred)

- Filesystem-derived command count — deferred until counts churn often enough to justify it.
- A `render_macros: false` per-file front-matter system — only add it to specific files **if** a
  Jinja conflict surfaces (audit shows none today: no `{{ }}`/`{# #}`/`{% %}` in `docs/`).
- Test-count / suite-count macros (scholar has these; rforge's docs don't advertise test counts).

## Architecture

Two layers, mirroring scholar but Python-native:

1. **Render layer** — `mkdocs-macros-plugin` exposes `extra.rforge.*` as `{{ rforge.version }}` etc.
   at build time. Source of the `extra` block is `mkdocs.yml` itself.
2. **Sync layer** — `scripts/version_sync.py` reads `package.json` `version` (authoritative) and
   writes it into `mkdocs.yml extra.rforge.version`, `.claude-plugin/plugin.json`, and the raw-on-GitHub
   files (`README.md`, `CLAUDE.md`) that mkdocs never renders. Same shape as `scripts/gen_lib_reference.py`
   (`main()` + `--check` returning exit 1 on drift); reuse its argparse/IO conventions.

Flow: `package.json` → `version_sync.py` → `mkdocs.yml extra.rforge.*` → mkdocs-macros → rendered docs.
Jinja-conflict risk is low (grep of `docs/` finds no existing `{{ }}`/`{% %}`); fenced code blocks that
literally contain `{{` would need `{% raw %}` guards — audit during implementation.

## Dependencies

- **New (build/CI only):** `mkdocs-macros-plugin` (Python, pip). Not a runtime dep of the plugin
  itself. Degrade: if absent, `mkdocs build` errors loudly on the unknown plugin — caught in CI, not
  silently. No R engines involved.

## Error handling

- `version_sync.py --check` exits 1 listing each drifted file (same vocabulary as
  `gen_lib_reference.py --check`: "X is stale. Run: python3 scripts/version_sync.py").
- Unknown-plugin / unrendered-macro failures surface as a hard `mkdocs build` error in `docs.yml`,
  before `gh-deploy` — never a half-stamped live site.

## Testing

Both gates must pass:

- `python3 -m pytest tests/` — add `tests/test_version_sync.py`: round-trips a temp `package.json`,
  asserts `mkdocs.yml extra.rforge.version` updates, asserts `--check` returns non-zero on injected drift.
- `bash tests/test-all.sh` — unchanged.
- Manual: `mkdocs build --strict` renders `{{ rforge.version }}` → `2.7.0` with no unrendered braces.

## Documentation impact

- Convert the ~12 user-facing docs (see Scope table) to macros.
- `CHANGELOG` + `.STATUS` + `CLAUDE.md`: note the new sync step in the release runbook
  ("bump `package.json` → `python3 scripts/version_sync.py` → commit").
- Leave `scripts/gen_lib_reference.py` docs as-is (separate concern).
- REFCARD ASCII version box (if any) — verify it's macro-rendered or sync-script-stamped.

## Implementation order

1. **(worktree)** Add `mkdocs-macros-plugin` to `docs.yml`; add `plugins: - macros` + `extra.rforge.*`
   to `mkdocs.yml`. Verify `mkdocs build` still green.
2. **(worktree)** Write `scripts/version_sync.py` + `tests/test_version_sync.py`; run `--check`.
3. **(worktree)** Convert the ~12 docs to `{{ rforge.* }}`; `mkdocs build --strict` to catch
   unrendered braces / Jinja conflicts; add `{% raw %}` where code blocks contain `{{`.
4. **(docs-only, dev)** Update release runbook (`CLAUDE.md`/`.STATUS`/CHANGELOG) with the sync step.
5. **(worktree)** Wire `version_sync.py --check` into the main CI workflow.
6. Merge `feature/mkdocs-version-macros` → `dev` → release v2.8.0.

> Steps 1–3, 5 touch code/config and **require a feature worktree** off `dev`
> (`git worktree add ~/.git-worktrees/rforge-version-macros -b feature/mkdocs-version-macros dev`).
> Step 4 is docs-only and may land on `dev` directly.

## Open questions / risks

- **`command_count` authority:** hardcoded in `mkdocs.yml extra` (manual bump, CI-checked) vs derived
  from `commands/` minus deprecated stubs. → *Resolved:* hardcode for v1, validate via `--check`; defer
  derivation.
- **Jinja in code blocks:** any fenced block containing `{{ … }}` (e.g. GitHub Actions snippets) will be
  interpreted by macros → wrap in `{% raw %}`. Audit during Step 3.
- **Behavior change:** none user-facing; purely a docs-build/release-process change.

## Sources

- [mkdocs-macros-plugin — official docs](https://mkdocs-macros-plugin.readthedocs.io/)
- scholar's implementation (internal reference): `scholar/scripts/version-sync.js`,
  `scholar/mkdocs.yml` `extra.scholar.*`, `scholar/.github/workflows/docs.yml` (`pip install … mkdocs-macros-plugin`)

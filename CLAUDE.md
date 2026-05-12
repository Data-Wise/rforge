# rforge plugin — project-specific notes

> Local CLAUDE.md for the rforge Claude Code plugin.
> Follows the global `~/.claude/CLAUDE.md`; this file only captures
> rforge-specific patterns that don't apply to other dev-tools repos.

## Current state (2026-05-12)

**v2.0.0 released** — 16 commands, 2 in sub-namespaces (`docs:check`, `r:check`), 14 flat (including `health` — the rename of `ecosystem-health`). Phase 3 of craft-parity roadmap shipped 2026-05-12. v1.3.0 absorbed `rforge-mcp` into pure-Python `lib/*` modules.

**Open backlog** (`.STATUS`): brew upgrade local install + Phase 2.2 live-test → Issue #9 (feedback watch) → Phase 4 (agents, v2.1.0) → Path B v1.4.0 (4-mode status, parked).

## Branch architecture

Multi-branch (craft-style): `main` (PR only) ← `dev` (integration) ← `feature/*` (worktrees for larger work). See global CLAUDE.md for the full pattern — rforge follows it exactly.

## Version sync (4 sources, no bump-version.sh)

Version bumps are manual edits across **4 files**:

- `.claude-plugin/plugin.json` → `"version"`
- `.claude-plugin/marketplace.json` → `metadata.version` AND `plugins[0].version` (both must match)
- `package.json` → `"version"`

After bumping, also update:

- `CHANGELOG.md` — convert `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
- Live-version doc refs in `docs/REFCARD.md` header, `docs/README.md` (Plugin Version, Documentation Version), tree-diagram comments showing "(vX.Y.Z)" in `README.md`, `docs/index.md`, `docs/README.md`, `docs/REFCARD.md`
- ASCII box version inside `docs/REFCARD.md` (easy to miss — the version sits between box-drawing characters)

`tests/test-all.sh` includes a "All 4 version sources agree" check — that gate must pass.

## lib/ Python package convention

The `lib/` directory is a Python package (has `__init__.py`). Modules use relative imports.

- **Run modules as a package**: `python3 -m lib.<module>` (e.g., `python3 -m lib.discovery`)
- **Never**: `python3 lib/<module>.py` — breaks relative imports
- **Public modules** (with `docs/reference/` pages): `discovery`, `deps`, `status`, `init`
- **Internal module** (no reference page, subject to refactor): `formatters` — used from command prompts; if importing externally, copy don't reuse
- **Auto-generated reference docs**: `docs/reference/{discovery,deps,status,init}.md` are produced by `scripts/gen_lib_reference.py`
- **CI gate**: `scripts/gen_lib_reference.py --check` compares regenerated output against committed files; any drift fails CI

## Command-file conventions (all 16 commands)

Every `commands/*.md` has structured frontmatter:

```yaml
---
name: rforge:<slash-path>
description: One-line description (appears in /help)
argument-hint: Plain-text hint (single string, optional)
arguments:
  - name: <flag>
    description: <what>
    required: false
    type: string | boolean
    default: ...
---
```

The `arguments:` array is the machine-readable spec; the `## Usage` body is the human equivalent. **Keep them in sync** when adding/removing flags.

**v2.0.0 rename-error stubs:** `commands/{doc-check,ecosystem-health,rpkg-check}.md` are stubs that emit a verbatim "Renamed to /rforge:..." message. Slated for removal in v3.0.0. Don't add normal command-file content to them.

## Test gates

Both must pass before any PR:

- `bash tests/test-all.sh` — **29 checks** (versions, hook compile + behavior, manifests parse, skills valid, lib pytest, lib CLI smoke, lib reference docs in sync, rename stubs/targets, command-name uniqueness, migration recipe E2E)
- `python3 -m pytest tests/` — **65 lib/\* cases** (discovery, deps, status, init)

## Homebrew tap quirks (rforge-specific)

`data-wise/tap/rforge` uses **dual stable + head** distribution (most tap plugins are stable-only). Manifest entry includes BOTH `version`/`sha256` AND `head:` so users can `brew install` (stable) or `brew install --HEAD` (track main).

After every `/craft:release` Step 10a:

1. `/craft:release` sed-edits `Formula/rforge.rb` with new url + sha256
2. **Also update** `~/projects/dev-tools/homebrew-tap/generator/manifest.json` (rforge entry) to match
3. Verify: `cd ~/projects/dev-tools/homebrew-tap && python3 generator/generate.py rforge --diff` → must report `IDENTICAL`

Failing to update the manifest creates drift — any later regeneration would strip the stable url+sha256.

## R-aware PreToolUse hook (`.claude-plugin/hooks/pretooluse.py`)

Diagnostic, not adversarial. Fires on every Write/Edit. 4 rules:

1. **BLOCK** hand-edits to `man/*.Rd` (regenerate via `devtools::document()`)
2. **WARN** on `R/*.R` edits (NAMESPACE/DESCRIPTION may need sync)
3. **WARN** on non-SemVer `DESCRIPTION` Version bumps
4. **WARN** on writes outside the active worktree

Only rule 1 blocks. Hook contract: reads JSON via stdin (NOT env vars). Tested by 7 cases in `tests/test-all.sh`.

## Docs conventions

- **Material admonitions** for ADHD-friendliness: `!!! tip "TL;DR (30 seconds)"` on major pages; `!!! warning "Symptom"` + `!!! tip "Fix"` for troubleshooting pairs; `!!! note "Expected behavior in vX.Y.Z+"` for clarifying quirks. Don't write custom CSS — the Material palette covers note/tip/warning/danger/success/info/abstract.
- **Verification trap** when curl-grepping deployed pages: HTML entities + `<code>`-tag fragmentation + box-drawing characters all break naive regexes. If a deploy "looks broken," parse the `<article>` body with `re.sub(r'<[^>]+>', ' ', body)` before searching. Details in `reference_rforge_doc_conventions.md`.

## rforge-mcp is gone — don't reach for it

The `rforge-mcp` prototype was absorbed into the plugin in v1.3.0 via pure-Python `lib/` modules. It was a local-only working directory at `~/projects/dev-tools/mcp-servers/rforge/` — **never on GitHub, never on npm**. The `npm link` symlink was dropped 2026-05-11 and the source dir was tombstoned with `DEPRECATED.md`.

SPEC documents (e.g., `docs/specs/SPEC-mcp-absorb-2026-05-10.md`) reference `data-wise/rforge-mcp` as if it were public — those are historical artifacts, not action-guidance. See `docs/migration/v1.3.0-post-merge-checklist.md` for the rewritten "what archival actually meant" doc.

## Release pipeline observations

Per the global rules (see `## Pre-PR & Release Checklist` in `~/.claude/CLAUDE.md`), with these rforge-specific addenda:

- **Docs deploy on push to main is automatic** (`.github/workflows/docs.yml` triggers on `push: branches: [main]`). To force-deploy from `dev` between releases: `gh workflow run docs.yml --ref dev`.
- **No `bump-version.sh`** — manual 4-source edit per the version-sync section above.
- **Tap manifest sync** must follow every release per the Homebrew section above.
- **GitHub Pages CDN** propagates in 30–90s for `meta` descriptions and most content; rarely longer.

## Memory pointers

For details not in this file, see project memory at `~/.claude/projects/-Users-dt-projects-dev-tools-rforge/memory/`:

- `reference_rforge_doc_conventions.md` — frontmatter standard, admonition palette, doc-gap audit recipe, verification gotchas
- `reference_homebrew_tap_drift.md` — manifest sync recipe + 6-surface drift inventory
- `reference_dotfiles_sync_workflow.md` — chezmoi for `~/.claude/`, flow-cli for `~/.config/zsh/`, `claude-sync` helper
- `project_rforge_mcp_never_public.md` — historical context for the v1.3.0 absorption
- `reference_brew_outdated_testing.md` — Cellar-rename trick for testing `brew outdated` UX

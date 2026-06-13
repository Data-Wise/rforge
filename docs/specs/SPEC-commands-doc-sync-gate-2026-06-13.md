# SPEC: `docs/commands.md` sync-gate

**Date:** 2026-06-13
**Author:** Davood Tofighi (with Claude Code)
**Status:** Approved (bundle build)
**Target:** v2.12.0 bundle (1 of 3)

---

## Summary

`docs/commands.md` is a hand-maintained reference mirror of the command files. It has
**no CI gate**, so it drifts: stale command count (v2.10), a command section missing new
flags (v2.11 `--eco`/`--runtime`), and a family table calling an implemented finding
"deferred" (v2.11.1). The machine-checkable surfaces (`reference/*.md` via
`gen_lib_reference --check`, version/count via `version_sync --check`, command frontmatter
`arguments:`↔`Usage`) all stay current; this closes the last drift-prone surface.

## The gate

New pure-stdlib `tests/_check_commands_doc.py`, wired into `tests/test-all.sh` (33→ +1).
Robust **presence** checks (not strict prose parsing — that would be brittle):

1. **Command coverage** — every non-stub command file (`commands/**/*.md`, excluding the
   v2.0.0 rename stubs `doc-check`/`ecosystem-health`/`rpkg-check`) has a section in
   `docs/commands.md`. Match on the command's slash-name (`/rforge:<path>`), which appears
   in every section. Fail listing any command with no commands.md section, and any
   commands.md `/rforge:` section with no backing command file.
2. **Flag coverage** — for each command, every flag declared in its frontmatter
   `arguments:` whose `type` is `boolean`/`string` and that is a real CLI flag (name is a
   `--flag`, i.e. excludes positional args like `package`) appears as `--<name>` somewhere
   in that command's commands.md section. Fail listing `command: --flag documented? no`.

Both directions are substring/identifier presence — resilient to wording changes, but
catches the structural gaps that actually happened.

## Scope decisions

- **Presence, not semantics.** The gate cannot catch a *wrong* description (e.g. "deferred"
  prose) — only missing coverage. That's an accepted limit; semantic honesty stays a
  review concern. The gate retires the *structural* drift (missing command/flag), which is
  the larger and more mechanical class.
- **Positional args excluded** from flag coverage (they're not `--flags`; `package` etc.).
- **Stubs excluded** from command coverage (they intentionally have no normal docs).

## Expected fallout

Building the gate will likely surface **existing** drift (flags in frontmatter not in
commands.md). Part of this task is fixing that drift so the gate passes — that is the
point.

## Tests (gates)

- The new check itself IS a gate (`_check_commands_doc.py`, run from `test-all.sh`).
- A self-test in `tests/` (pytest) feeding the checker a tiny fixture (one command file +
  a commands.md missing a flag) asserting it reports the gap — so the gate is proven to
  catch drift, not just pass vacuously.
- `test-all.sh` count bumps; full suite green after fixing any surfaced drift.

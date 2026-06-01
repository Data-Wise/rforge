# Specs

Design documents for non-trivial work in rforge. Each SPEC captures a
decision, plan, or migration that's larger than a single PR — the *why*
and the *how-to-execute*, separate from the implementation that
eventually delivers it.

## When to write a SPEC

Write a new SPEC when the work is:

- **Multi-session** — won't land in one focused effort
- **Architectural** — changes how subsystems relate, not just what they
  do
- **Breaking** or **migration** — needs a sequenced execution path
  rather than a one-shot edit
- **Carrying decisions worth preserving** — *why* this approach beat
  alternatives, captured before the alternatives are forgotten

Don't write a SPEC for routine refactors, focused bug fixes, or
single-PR features. The PR description is the right home for those.

## Conventions

- Filename: `SPEC-<short-name>-YYYY-MM-DD.md`. Date is the *creation*
  date, not the ship date.
- Status header: `Draft` → `In Progress` → `Shipped` (or `Abandoned`).
- Every SPEC has a `Goals` and `Non-goals` section. Non-goals are often
  more useful than goals — they prevent scope creep.
- Link from `CHANGELOG.md` and `.STATUS` so SPECs aren't orphaned.

## Specs

- **[MCP absorb (Path B)](SPEC-mcp-absorb-2026-05-10.md)** — Status:
  Shipped (v1.3.0). Migration plan that absorbed `rforge-mcp`'s implemented
  tools into the plugin's `lib/`. Path A (decoupling at the npm peer-dep
  level) shipped in v1.2.0; Path B delivered full self-sufficiency.
- **[Phase 3 namespacing (v2.0.0)](SPEC-phase3-namespacing-2026-05-11.md)** —
  Status: Shipped (v2.0.0). The command-rename / sub-namespacing plan
  (`docs:check`, `r:check`, `health`).
- **[Diff-aware checks & coverage](SPEC-diff-aware-checks-and-coverage-2026-05-31.md)** —
  Status: Draft. Proposal for diff-scoped checks, coverage integration, and
  ecosystem NOTE classification.

## See also

- [`CHANGELOG.md`](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md) — release-level decisions
- `.STATUS` — current session log + active backlog

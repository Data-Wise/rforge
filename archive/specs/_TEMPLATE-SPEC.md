<!--
TEMPLATE — copy to SPEC-<short-name>-YYYY-MM-DD.md (date = creation date) and fill in.
Delete this comment and every `> guidance:` line before committing the real spec.
See README.md → "Research & Citation Standard" for the citation rules this template assumes.
-->

# SPEC: <one-line title>

- **Status:** Draft — awaiting user review  <!-- Draft → In Progress → Shipped (vX.Y.Z) | Abandoned -->
- **Date:** YYYY-MM-DD  <!-- creation date, not ship date -->
- **Target version:** vX.Y.Z
- **Author:** brainstormed with Claude, grounded in `RESEARCH-<topic>-YYYY-MM-DD.md`
- **Related:** [RESEARCH-…](RESEARCH-….md), [SPEC-…](SPEC-….md)

## Summary

> guidance: 2–4 sentences. What this changes and the one-line why. Name the
> command/module surface touched and any count deltas (e.g. "33 → 34 commands").

## Motivation

> guidance: Why now. Cite the driving evidence — a bug, a CRAN bounce, a gap row
> in the companion RESEARCH doc. Every external/technical claim carries a source
> at point of use (see README citation standard).

## Goals

> guidance: Bullet list. What success looks like.

## Non-goals

> guidance: Bullet list. Often more useful than Goals — they prevent scope creep.
> State what this deliberately does NOT do, and where deferred work is parked.

## Scope

### In scope (decided)

> guidance: A table is good here. Columns like Kind | Command/Module | Engine | Tier.

### Out of scope (YAGNI / deferred)

> guidance: Bullet list with the reason each item is deferred and where it lives next.

## Architecture

> guidance: How it fits the existing code. Name files and functions with `path:line`
> anchors (e.g. `lib/rcmd.py:462`). Reuse existing helpers — say which. A Mermaid
> diagram is welcome if the data flow is non-trivial; mark "N/A" if a sentence suffices.

## Dependencies

> guidance: Confirmed-installed vs new optional engines. For R engines, state the
> guard (`_guard("<pkg>", …)`) and the degrade behavior when absent.

## Error handling

> guidance: New failure modes and how the envelope/verdict represents them
> (status vocab, blockers, hints surfaced to the user).

## Testing

> guidance: Both gates must pass — `python3 -m pytest tests/` and `bash tests/test-all.sh`.
> List the new cases and any regression fixture that proves the change.

## Documentation impact

> guidance: Every doc surface to update — command frontmatter, CHANGELOG, .STATUS,
> auto-gen reference (`scripts/gen_lib_reference.py`), tutorials, REFCARD.

## Implementation order

> guidance: Numbered, sequenced steps. Note which steps need a feature worktree
> (code) vs which are docs-only (allowed on `dev`).

## Open questions / risks

> guidance: Unresolved items, with a resolution line once decided. Call out any
> behavior change that could surprise existing users.

## Sources

> guidance: Every primary source cited above, collected for verification. Primary
> sources first (Writing R Extensions, R Internals, CRAN Repository Policy, package
> reference docs), then official tutorials, then blogs/mailing lists (labeled).

- [<source title>](<url>)

<!--
TEMPLATE — copy to RESEARCH-<topic>-YYYY-MM-DD.md and fill in.
Delete this comment and every `> guidance:` line before committing the real doc.
A RESEARCH doc is *findings + recommendations* — no code, no execution plan. The
SPEC it feeds references it instead of re-deriving claims.
See README.md → "Research & Citation Standard" for the citation rules.
-->

# RESEARCH: <topic> (<year>) vs <subject under study>

> **Type:** Research + recommendations (no code, no spec).
> **Date:** YYYY-MM-DD
> **Scope:** <what this covers, what it deliberately ignores, which versions/commands>

---

## PART A — Current (<year>) state

> guidance: The authoritative facts. Organize into sub-sections (A.1, A.2, …).
> EVERY non-obvious claim cites a primary source at point of use. When two sources
> disagree, state both, resolve it, and note the resolution — that resolution is
> often the most valuable line in the document.

### A.1 <area>

> guidance: e.g. "Repository Policy highlights ([CRAN Repository Policy](url))" then
> bullet the facts, each with its own citation where it isn't covered by the heading link.

---

## PART B — Gap analysis vs <subject>

> guidance: A table mapping each requirement/practice to the current state.
> Suggested columns: # | Requirement / practice | current tool(s) | Status (✅/⚠️/❌) | Notes.

| # | Requirement / practice | Current coverage | Status | Notes |
|---|---|---|---|---|
|   |   |   |   |   |

---

## PART C — Prioritized recommendations

> guidance: Quick wins → Medium → Long-term, each tied to a Part B gap. These become
> the raw material for a SPEC; keep them actionable but free of implementation detail.

### Quick wins
### Medium
### Long-term

---

## Sources

> guidance: Collect every link cited above. Primary sources first (Writing R Extensions,
> R Internals, CRAN Repository Policy, package reference docs), then official tutorials
> (r-pkgs.org, r-lib reference), then blogs/mailing lists (labeled as secondary).

- [<source title>](<url>)

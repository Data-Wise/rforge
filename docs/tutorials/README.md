# Tutorials

Step-by-step guides for common workflows. Each tutorial targets a specific
scenario and walks through the exact commands and expected output.

For API-level details, see [Reference](../reference/discovery.md). For the
plugin's design rationale, see [Architecture](../architecture.md).

## Available tutorials

- **[Getting started](getting-started.md)** — Fresh install → first
  analysis on an R package. Covers `/rforge:detect`, `/rforge:status`,
  `/rforge:analyze`. ~10 min, no prior rforge experience required.
- **[Migrating from rforge-mcp](migrate-from-mcp.md)** — For users
  currently running `rforge-mcp` (the deprecated MCP server). Steps to
  upgrade to v1.3.0+ and clean up the old install. ~5 min.

## Adding a tutorial

If you write a new tutorial, follow these conventions:

- Filename: `<topic>.md` (lowercase, hyphenated, no `TUTORIAL-` prefix —
  the path already says `tutorials/`)
- Open with a short "for whom" and "estimated time" summary
- Use numbered steps, not nested bullet lists, for sequential work
- Include expected output (or a screenshot equivalent) after each step
  so users can verify they're on track
- End with a "next steps" pointer to related docs
- Add the tutorial to `mkdocs.yml` nav under the Tutorials section

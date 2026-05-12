# 📚 Tutorials

!!! tip "TL;DR (30 seconds)"
    - **What:** Step-by-step walkthroughs for the most common rforge workflows.
    - **Why:** Faster to follow a recipe than to assemble one from the REFCARD.
    - **How:** Pick the tutorial matching your scenario below.
    - **Next:** [REFCARD](../REFCARD.md) for command-by-command lookups, or [Architecture](../architecture.md) for design rationale.

Step-by-step guides for common workflows. Each tutorial targets a specific
scenario and walks through the exact commands and expected output.

## Which tutorial first?

| If you're... | Start here | Time |
|---|---|---|
| New to rforge, want to try it on an R package | [Getting started](getting-started.md) | ~10 min |
| Coming from `rforge-mcp` (the deprecated MCP server) | [Migrating from rforge-mcp](migrate-from-mcp.md) | ~5 min |
| Upgrading from v1.x and hit a renamed-command error | [v2.0.0 rename migration](../migration/v2.0.0-rename.md) | ~2 min |
| Looking up a specific command's syntax | [REFCARD](../REFCARD.md) (not a tutorial) | <1 min |

## Available tutorials

- **[Getting started](getting-started.md)** — Fresh install → first
  analysis on an R package. Covers `/rforge:detect`, `/rforge:status`,
  `/rforge:analyze`. ~10 min, no prior rforge experience required.
- **[Migrating from rforge-mcp](migrate-from-mcp.md)** — For users
  currently running `rforge-mcp` (the deprecated MCP server). Steps to
  upgrade to v1.3.0+ and clean up the old install. ~5 min.

## What's NOT covered here yet

These workflows have command references in [REFCARD](../REFCARD.md) but no
dedicated tutorial. File an issue if a step-by-step would help:

- Multi-package ecosystem orchestration (`/rforge:cascade`, `/rforge:impact`)
- Pre-CRAN release prep (`/rforge:thorough`, `/rforge:release`, `/rforge:r:check`)
- Custom configuration (CRAN mirror, vignette engine — see [Configuration](../configuration.md))

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

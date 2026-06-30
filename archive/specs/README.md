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

## Templates

Start from a template rather than a blank file — they encode the section
structure and the citation rules below:

- **[`_TEMPLATE-SPEC.md`](_TEMPLATE-SPEC.md)** — design + execution plan.
- **[`_TEMPLATE-RESEARCH.md`](_TEMPLATE-RESEARCH.md)** — findings + recommendations
  (no code, no plan). A RESEARCH doc feeds a SPEC; the SPEC references it instead
  of re-deriving claims (e.g. `RESEARCH-cran-dev` → `SPEC-r-cran-prep`).

Naming prefixes: `RESEARCH-` (findings) → `PROPOSAL-` (early ideation, not yet
approved) → `SPEC-` (approved design). Promote a PROPOSAL to a SPEC by `git mv`
once the design is decided; the date in the filename stays the *creation* date.

## Research & Citation Standard

rforge specs make claims about CRAN policy, R internals, and tool behavior that
are easy to get *subtly* wrong. (A real example: an early draft of the
CRAN-incoming-hardening proposal named `_R_CHECK_SUGGESTS_ONLY_` as the env var
that catches a Suggests-package-used-unconditionally bug; the correct flavor is
`_R_CHECK_DEPENDS_ONLY_`. The two have different semantics — only verification
against the primary source caught it.) This standard exists to make that class of
error visible before a spec leaves `Draft`.

**The rules:**

- **Claim → source.** Every non-obvious external or technical claim cites a source
  *at the point of use*, not just in a bibliography.
- **Source hierarchy** (prefer higher tiers; drop to a lower tier only when no
  higher source covers the claim, and label it):
  1. **Primary** — [Writing R Extensions](https://cran.r-project.org/doc/manuals/r-release/R-exts.html),
     [R Internals](https://cran.r-project.org/doc/manuals/r-release/R-ints.html),
     [CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html),
     R `NEWS`/source, and a package's own reference docs.
  2. **Official tutorials** — [r-pkgs.org](https://r-pkgs.org/), r-lib / tidyverse
     reference sites.
  3. **Secondary** — blog posts, mailing-list threads. Use only when no primary
     source exists, and mark them as secondary.
- **Format.** Inline markdown link where the claim is made, **plus** a closing
  `## Sources` section collecting every link for one-pass verification.
- **Resolve contradictions in the open.** When two sources disagree, state both,
  pick one, and record the resolution. That sentence is usually the most valuable
  line in the document.

**The research workflow** (how a RESEARCH doc or a spec's evidence base gets built):

1. **Scope the question** — write down exactly what must be true for the design to hold.
2. **Fan-out search** — the global `deep-research` skill, or `WebSearch` filtered to
   primary domains (`cran.r-project.org`, `stat.ethz.ch`, package reference sites).
3. **Fetch & verify** — `WebFetch` the primary source; confirm the claim in its own
   words rather than trusting a summary.
4. **Resolve contradictions** — reconcile disagreeing sources; note the resolution.
5. **Write claim + citation** — link at point of use.
6. **Compile `## Sources`** — collect all links.
7. **Self-review** — scan for any external claim without a citation before promoting
   out of `Draft`.

## Specs

- **[MCP absorb (Path B)](SPEC-mcp-absorb-2026-05-10.md)** — Status:
  Shipped (v1.3.0). Migration plan that absorbed `rforge-mcp`'s implemented
  tools into the plugin's `lib/`. Path A (decoupling at the npm peer-dep
  level) shipped in v1.2.0; Path B delivered full self-sufficiency.
- **[Phase 3 namespacing (v2.0.0)](SPEC-phase3-namespacing-2026-05-11.md)** —
  Status: Shipped (v2.0.0). The command-rename / sub-namespacing plan
  (`docs:check`, `r:check`, `health`).
- **[Diff-aware checks & coverage](SPEC-diff-aware-checks-and-coverage-2026-05-31.md)** —
  Status: Draft, **refocused to P0** (`--changed` diff-aware checks — the unbuilt flagship).
  P1 shipped (v2.1.0); P2→cran-incoming, P3→ecosystem-manifest, P4→scaffolding (2026-06-10).
- **[r: dev-cycle + quality commands (v2.1.0)](SPEC-r-dev-commands-2026-05-31.md)** —
  Status: Shipped (v2.1.0). 12 new `r:` commands (build/test/document/install/
  coverage/site/cycle + lint/spell/urlcheck/style) backed by `lib/rcmd.py`.
  16 → 28 commands. Deferred follow-ups (deps-sync, scaffolding, cran-prep)
  noted in the appendix.
- **[CRAN-incoming hardening](SPEC-cran-incoming-hardening-2026-06-10.md)** —
  Status: Reviewed/approved (target v2.3.0). Make the `check`/`cran-prep` gate emulate CRAN incoming + ongoing
  checks (noSuggests + suggests-only flavors, `--run-donttest`, opt-in `--incoming`
  bundle), default-on as a `ready`-blocker, plus pure-Python DESCRIPTION-lint,
  `.Rbuildignore` build-hygiene, and planning-doc consistency checks. Grounded in
  [RESEARCH-cran-incoming-checks](RESEARCH-cran-incoming-checks-2026-06-10.md).
- **[`r:deps-sync` — reconcile DESCRIPTION vs code usage](SPEC-r-deps-sync-2026-06-10.md)** —
  Status: Draft (target v2.5.0). New pure-Python per-package command: scan `R/`/tests/vignettes for
  namespace usage, reconcile against `Imports`/`Suggests` (missing/unused/misclassified), suggest a
  DESCRIPTION patch (`--write` to apply). Static sibling of the cran-incoming noSuggests catch.
- **[`r:submit` — GitHub pre-release + CRAN submit handoff](SPEC-r-submit-github-prerelease-2026-06-10.md)** —
  Status: Draft (target v2.6.0). New per-package command: build the submitted tarball, cut a
  GitHub **pre-release** (+`cran-comments.md`), hand off the CRAN submit step, then promote to a
  full release on acceptance (`gh release edit --prerelease=false`). Fills the submission-lifecycle
  gap between `r:cran-prep` (ready) and CRAN going live.
- **[Scaffolding theme — `r:use-test`/`r:use-package`/`r:use-vignette`](SPEC-r-scaffolding-2026-06-10.md)** —
  Status: Draft (unscheduled, post-v2.6.0). Authoring commands for *existing* packages (no
  `r:create`): scaffold + AI-draft a testthat file, add a declared dependency, start a vignette.
  Hybrid engine (usethis infra + Python/AI content), dry-run by default. Reuses deps-sync's
  DESCRIPTION-patch writer.

## See also

- [`CHANGELOG.md`](https://github.com/Data-Wise/rforge/blob/main/CHANGELOG.md) — release-level decisions
- `.STATUS` — current session log + active backlog

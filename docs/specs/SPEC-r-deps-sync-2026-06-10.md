# SPEC: `r:deps-sync` — reconcile DESCRIPTION against actual code usage

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-10
- **Target version:** v2.5.0 (roadmap: v2.3.0 cran-incoming → v2.4.0 ecosystem-manifest → **v2.5.0 deps-sync** → v2.6.0 r:submit)
- **Author:** brainstormed with Claude, grounded in `BRAINSTORM-r-command-expansion-2026-05-31.md`
- **Related:** [SPEC-cran-incoming-hardening-2026-06-10.md](SPEC-cran-incoming-hardening-2026-06-10.md),
  [SPEC-ecosystem-manifest-discovery-2026-06-10.md](SPEC-ecosystem-manifest-discovery-2026-06-10.md),
  `commands/deps.md`, `lib/deps.py`, `lib/discovery.py`

## Summary

Add a per-package command, **`r:deps-sync`**, that scans a package's R sources for namespace
usage (`pkg::`, `library()`, `@importFrom`, …) and **reconciles** it against the
`Depends`/`Imports`/`Suggests` fields of `DESCRIPTION` — surfacing **missing**, **unused**, and
**misclassified** dependencies, plus a suggested DESCRIPTION patch. It is **report-by-default**
(no write); `--write` applies the patch. Implemented as a **pure-Python** analysis module
(no R, no new deps), matching the `lib/cranlint.py` pattern. Commands 33 → **34**.

## Motivation

Keeping `DESCRIPTION` in sync with what the code actually uses is a recurring, error-prone CRAN
chore — a missing `Imports` entry is a check ERROR, an unused one is a NOTE, and the subtle case
(a `Suggests` package used *unconditionally* in `R/`) is exactly the **medfit/MASS bug** that
motivated cran-incoming hardening. `r:deps-sync` catches that class **statically, before R runs** —
the complement to cran-incoming's runtime noSuggests catch. Per the 2026-05-31 brainstorm it's the
flagship judgement command and a natural extension of rforge's dependency theme (`deps`/`impact`).
The judgement (Imports vs Suggests, what's safe to remove) lives in the command prompt reading a
structured scan — which is where the AI value is, not in running an R helper.

Dependency-field semantics this reconciliation enforces
([Writing R Extensions §"Package Dependencies"](https://cran.r-project.org/doc/manuals/r-release/R-exts.html),
[r-pkgs §"Dependencies: Mindset and background"](https://r-pkgs.org/dependencies-mindset-background.html)):
`Imports` = needed whenever the package is loaded (namespace available, not attached); `Depends` =
attached to the search path (legacy; avoid for new code); `Suggests` = optional — used only in
tests, examples, vignettes, or **guarded** in `R/` via `requireNamespace()`.

## Goals

- Scan `R/`, `tests/`, `vignettes/` for namespace usage and reconcile against `DESCRIPTION`.
- Report four finding classes: **missing** (used, undeclared), **missing-suggests** (used only in
  tests/vignettes, undeclared), **unused** (declared, no usage found), **misclassified**
  (in `Suggests` but used unconditionally in `R/` → should be `Imports`, or vice-versa).
- Emit a **suggested DESCRIPTION patch**; apply it only behind `--write`.
- Stay pure-Python (no R, no `attachment`/`desc` dependency); degrade clearly on unparseable input.

## Non-goals

- **No auto-write by default.** Report + patch; `--write` applies (gated like `r:style`).
- **No reliable version-floor inference.** Static analysis can't determine min versions; report a
  *placeholder/advisory* only, never invent a floor.
- **Not** a replacement for R's namespace resolution — it's a heuristic scan; flag low-confidence
  matches rather than assert.
- **Not** ecosystem-wide — `r:deps-sync` is intra-package (one DESCRIPTION). `lib/deps.py`/`r:deps`
  owns the *inter-package* graph; the two are complementary.
- **No `attachment`/`desc`/`devtools`.** Rejected in favour of the pure-Python scanner.

## Scope

### In scope (decided)

| Concern | Surface | Notes |
|---|---|---|
| Module | new `lib/deps_sync.py` (pure stdlib) | scan + reconcile + patch builder |
| Command | `commands/r/deps-sync.md` | `--write`, `--dry-run` (default), `--base`? (no) |
| Sources scanned | `R/`, `tests/`, `vignettes/`, `NAMESPACE`, roxygen tags | usage site determines Imports vs Suggests |
| Output | structured envelope (findings by class) + suggested patch | report-only unless `--write` |

### Out of scope (YAGNI / deferred)

- Version-floor *inference* (advisory placeholder only).
- Rewriting roxygen `@importFrom` tags in `R/` (DESCRIPTION reconciliation only; tag edits → future).
- `LinkingTo`/compiled-code dependency analysis (C/C++ `src/`) — R-level usage only for v1.
- Auto-adding `Remotes:` entries — *detect* the need (GitHub-only dep), but adding is advisory
  (leans on the ecosystem manifest; see Architecture).

## Architecture

Pure-Python analysis module `lib/deps_sync.py` (stdlib only, like `discovery`/`deps`/`cranlint`):

- **Scan usage.** Regex/token scan over sources:
  - `R/*.R` → `pkg::fn`, `pkg:::fn`, `library(pkg)`, `require(pkg)`, `requireNamespace("pkg")`,
    `loadNamespace("pkg")`; roxygen `#' @importFrom pkg fn`, `#' @import pkg`.
  - `NAMESPACE` (generated truth) → `importFrom(pkg, …)`, `import(pkg)`.
  - `tests/`, `vignettes/` → same patterns, but usage here implies **`Suggests`**, not `Imports`.
  - Track *where* each package is used and whether `R/` usage is **guarded**
    (`requireNamespace()`/`require()` inside the call) vs **unconditional**.
- **Parse DESCRIPTION.** Reuse `parse_description` from `lib/discovery.py` (`:116`) — already a
  pure-Python DCF reader — to get `Depends`/`Imports`/`Suggests`/`LinkingTo`/`Remotes`.
- **Reconcile → findings.** Compare used-set vs declared-set; classify each into
  missing / missing-suggests / unused / misclassified (the **unconditional-Suggests-in-`R/`** case
  is the static sibling of cran-incoming's `_R_CHECK_DEPENDS_ONLY_` catch — cross-reference both).
- **Remotes hint.** A used package neither on CRAN nor in base/recommended likely needs `Remotes:`.
  Determining "on CRAN" leans on the **ecosystem manifest** (`SPEC-ecosystem-manifest-discovery`,
  the `cran:` field) when present; absent a manifest, flag as "unknown origin — verify" rather than guess.
- **Suggested patch.** Build a reconciled `Imports`/`Suggests` block; return it in the envelope.
  `--write` applies it to `DESCRIPTION` (preserving field order/formatting as far as practical);
  default is report-only.

Standard envelope shape so `cran-prep`/command layer can render it; text formatter prints an
ADHD-friendly grouped report (by finding class). Data flow (Mermaid N/A): `scan sources +
NAMESPACE → used-set → diff vs parse_description() → findings + patch`.

## Dependencies

- **Pure Python stdlib** (regex, file walk, DCF parse via reused `parse_description`). **No R, no
  `attachment`/`desc`, no new deps.**
- **Reuses** `lib/discovery.py:parse_description`; **optionally consults** the ecosystem manifest
  (PR #16) for CRAN-membership when present.

## Error handling

- Missing/unparseable `DESCRIPTION` → `warn` with a clear reason, no exception.
- A source file that won't tokenize → skip it, note it in the report (partial scan, not failure).
- `--write` when findings are ambiguous (e.g. a dep that could be Imports or Suggests) → **do not
  auto-resolve**; write only the unambiguous changes and list the ambiguous ones for the user.
- Low-confidence matches (dynamic `do.call`, string-built names) → reported as advisory, never
  auto-removed under `--write`.

## Testing

Both gates must pass (`python3 -m pytest tests/` and `bash tests/test-all.sh`). Fixtures:

- **missing** — `pkg::fn` in `R/` not in `Imports` → flagged as missing-import.
- **misclassified (the cran-incoming class)** — pkg in `Suggests` used **unconditionally** in `R/`
  → flagged "move to Imports"; the *guarded* (`requireNamespace`) version is **not** flagged.
- **missing-suggests** — pkg used only in `tests/` → flagged for `Suggests`, not `Imports`.
- **unused** — declared in `Imports`, no usage found → flagged removable (advisory).
- **patch + `--write`** — assert the suggested patch is correct and that `--write` applies only the
  unambiguous changes; `--dry-run`/default writes nothing.
- **no-DESCRIPTION / unparseable source** → `warn`, no exception.
- New module → regen `docs/reference/deps_sync.md` via `scripts/gen_lib_reference.py` (CI `--check`).

## Documentation impact

**Frontmatter:** new `commands/r/deps-sync.md` (`arguments:` for `--write`/`--dry-run`).

**Help / hub:** `docs/commands.md` (Dependency section — add `r:deps-sync` next to `r:deps`/`impact`),
`docs/REFCARD.md`, `docs/index.md` + `docs/README.md` (counts 33→34, tree diagrams), root `README.md`,
`docs/lib-modules.md` (+ new `docs/reference/deps_sync.md`), any deps/quality tutorial.

**Trackers:** `CHANGELOG.md` (`[Unreleased]`), `.STATUS`. Version sync → **v2.5.0** at release.

## Implementation order

1. *(docs — this spec, on `dev`)* — DONE on write.
2. *(code — feature worktree)* `lib/deps_sync.py` — scanner (usage extraction + guarded detection).
3. Reconcile + finding classification; reuse `parse_description`.
4. Suggested-patch builder; `--write` apply (unambiguous only) + `--dry-run` default.
5. Ecosystem-manifest CRAN-membership consult for the Remotes hint (graceful when absent).
6. `commands/r/deps-sync.md` + tests (both gates) + `docs/reference/deps_sync.md`.
7. Full doc sweep (help/hub) + CHANGELOG/.STATUS + v2.5.0 version sync.

> **Branch note:** steps 2–7 are code → a `feature/r-deps-sync` worktree off `dev`, fresh session.

## Open questions / risks

- **Module placement.** New `lib/deps_sync.py` vs extending `lib/deps.py` (which is *inter*-package).
  *Proposed:* new module — different concern (intra-package reconciliation). *Resolution at impl.*
- **Guarded-usage detection fidelity.** Distinguishing `requireNamespace()`-guarded from
  unconditional `pkg::` use in `R/` is the crux of the misclassified finding; complex control flow
  may fool a regex scan. *Mitigation:* conservative — only flag clearly-unconditional top-level
  `pkg::` use; report uncertain cases as advisory.
- **`--write` formatting.** Preserving DESCRIPTION field order/wrapping on rewrite is fiddly;
  acceptable to normalize within a field. Confirm against the DCF the package already uses.
- **Remotes without a manifest.** Without the ecosystem manifest, "is this dep on CRAN?" is
  unknown; v1 flags "verify origin" rather than guessing — revisit once PR #16 lands.

## Sources

- [Writing R Extensions §"Package Dependencies"](https://cran.r-project.org/doc/manuals/r-release/R-exts.html) — `Depends`/`Imports`/`Suggests`/`LinkingTo`/`Enhances` semantics; guarded use of Suggests.
- [r-pkgs §"Dependencies: Mindset and background"](https://r-pkgs.org/dependencies-mindset-background.html) — Imports-vs-Suggests guidance; `requireNamespace()` pattern.
- rforge: `lib/discovery.py:parse_description` (reused DCF reader), `lib/deps.py` (inter-package graph), `BRAINSTORM-r-command-expansion-2026-05-31.md` (origin), `SPEC-cran-incoming-hardening-2026-06-10.md` (the runtime sibling of the misclassified finding).

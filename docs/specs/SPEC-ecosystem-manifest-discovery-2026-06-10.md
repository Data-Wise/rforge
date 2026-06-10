# SPEC: Read an ecosystem manifest to enrich package discovery

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-10
- **Target version:** vX.Y.Z (next minor)
- **Author:** brainstormed with Claude
- **Related:** consumer is the mediationverse ecosystem hub
  (`~/projects/r-packages/mediation-planning/ECOSYSTEM-MANIFEST.yaml`)

## Summary

Teach `lib/discovery.py` to optionally read an **ecosystem manifest** (a YAML file
listing packages with `name`, `path`, `role`, `repo`, `cran`, `status_file`) and use
it to **enrich and/or constrain** filesystem discovery. Today discovery walks the tree
for `DESCRIPTION` files and reads exactly one field from `.rforge.yaml` — `kind: hybrid`
(`lib/discovery.py:240`, `:243`); it has no concept of curated package metadata. This
lets a hub declare *what the ecosystem is* (roles, repos, CRAN state, canonical order)
so `/rforge:status`, `:deps`, `:release`, and `:thorough` can show that metadata instead
of inferring everything from the filesystem.

## Motivation

The mediationverse planning consolidation (2026-06-10) created
`mediation-planning/ECOSYSTEM-MANIFEST.yaml` as the human source of truth for "what
packages exist and where." But rforge ignores it — it only consumes `kind:`. So two
gaps exist:

1. **Role/repo/CRAN metadata is invisible to rforge.** Discovery reports package name +
   version (from `DESCRIPTION`) but not the curated role ("foundation", "meta") or CRAN
   submission state, which a hub maintains by hand and which `/rforge:release` and
   `/rforge:status` would benefit from.
2. **The manifest and rforge can silently disagree.** Nothing reconciles the hand-curated
   list against what's on disk (e.g. a package added to the manifest but not yet cloned,
   or a stray sibling dir). A manifest-aware discovery can surface that drift.

This is a small, additive capability — discovery stays correct with **no manifest present**
(today's behavior is the zero-manifest case).

## Goals

- Optionally locate and parse an ecosystem manifest, keyed off `.rforge.yaml`.
- Attach manifest metadata (`role`, `repo`, `cran`, `status_file`) to discovered
  `Package` records when names match.
- Report **drift**: manifest-listed packages not found on disk, and on-disk packages
  absent from the manifest.
- Preserve the manifest's package **order** (so `/rforge:status` can render in a
  curated order rather than alphabetical) where a consumer wants it.
- Zero behavior change when no manifest is configured. No hard new runtime dependency.

## Non-goals

- **Not** replacing filesystem discovery — `DESCRIPTION` parsing remains the source of
  truth for `version`/`depends`/`imports`. The manifest is curation metadata, not a
  substitute for reading packages.
- **Not** writing/generating the manifest from rforge (the hub owns it).
- **Not** changing `kind` classification semantics (`_classify_kind`, `:243`).
- **Not** computing dependency order from the manifest — that stays derived from
  `DESCRIPTION` graph (`/rforge:deps`). Manifest order is presentation only.
- **Not** adding manifest support to MCP mode detection (`_mcp_mode`).

## Scope

### In scope (decided)

| Kind | Surface | Notes |
|---|---|---|
| Module | `lib/discovery.py` | New `Manifest` dataclass + parse fn; `detect_ecosystem()` enrichment |
| Config | `.rforge.yaml` | New optional `manifest: <relative-path>` field |
| Data | `Package.manifest` (or new fields) | `role`, `repo`, `cran`, `status_file` attached when matched |
| Result | `Ecosystem` | New `manifest_path`, `drift` (lists of unmatched names) |

### Out of scope (YAGNI / deferred)

- A JSON-schema validator for the manifest — defer; a permissive parser + clear warnings
  is enough until the schema stabilizes.
- Multi-ecosystem manifests / nested manifests — single manifest per root.
- Using `status_file` to *read* status inside discovery — `/rforge:status` already reads
  each `.STATUS`; discovery just passes the path through.

## Architecture

How it fits the existing code (`lib/discovery.py`):

- **Config indirection.** The manifest lives in a *subdirectory* of the ecosystem root
  (`mediation-planning/ECOSYSTEM-MANIFEST.yaml`), not at root. So `.rforge.yaml` gains an
  optional `manifest:` key holding a path **relative to the root**. `detect_ecosystem()`
  (`:267`) already reads `config_path`/`config_found` (`:283-284`) — extend that block to
  also extract `manifest:` (same lightweight regex style as `_KIND_DECL_RE` at `:240`, or
  a minimal key reader). If absent → today's behavior unchanged.
- **Parse.** New `parse_manifest(content) -> Manifest` mirroring `parse_description`
  (`:116`): a `Manifest` dataclass with `ecosystem`, `updated`, `packages: list[ManifestEntry]`.
  See the YAML-dependency risk below — the manifest uses nested lists/maps, which the
  current `Field: value` regex parser (`_FIELD_RE`, `:94`) cannot handle.
- **Enrich.** After `find_r_packages(root)` (`:286`), match manifest entries to discovered
  `Package`s by `name` (case-insensitive; note the dir `rmediation` ↔ package `RMediation`).
  Attach `role`/`repo`/`cran`/`status_file`. Compute `drift`: `manifest_only` and
  `disk_only` name sets.
- **Expose.** Add `manifest_path`, `drift`, and per-package manifest metadata to
  `Ecosystem.to_dict()` (`:78`) so the JSON formatter and command layer can surface them.
  The text formatter (`format_text`, ~`:307`) can append a one-line drift warning.

Data flow is simple enough that a Mermaid diagram is N/A: `.rforge.yaml → manifest path →
parse_manifest → match against find_r_packages() results → enriched Ecosystem`.

## Dependencies

**The crux.** `lib/discovery.py` is deliberately *pure stdlib* ("no external deps beyond
the stdlib", module docstring). YAML is not stdlib. The manifest's nested structure
(`packages:` is a list of maps) is beyond the existing line-based parser. Options:

1. **Minimal vendored YAML-subset parser** (recommended) — hand-rolled reader for the
   exact subset the manifest uses (top-level scalars + a `packages:` list of flat maps).
   Keeps the zero-dependency guarantee; rejects anything fancier with a clear error.
2. **Optional PyYAML** behind a guard — import lazily; if missing, skip manifest enrichment
   and emit a hint ("install pyyaml to enable manifest metadata"). Breaks the
   zero-dep purity but is the most robust.
3. **Require the manifest be JSON** — stdlib `json` handles it, but the hub authored YAML
   for human-friendliness; would force a format change on the consumer. Rejected.

Recommend **(1)** with a strict, documented subset; fall back to **(2)** only if real
manifests outgrow the subset. Either way: **no manifest / unparseable manifest must
degrade to today's behavior**, never raise.

## Error handling

- Manifest path configured but file missing → `config_found` semantics: set
  `manifest_path=None`, emit a non-fatal hint; discovery proceeds.
- Manifest unparseable (subset violated / PyYAML absent) → skip enrichment, surface a
  hint in the envelope; never raise out of `detect_ecosystem()` (it currently only raises
  `FileNotFoundError`/`NotADirectoryError` for the *root*, `:279-282` — preserve that
  contract).
- Drift is **informational**, not an error: `manifest_only`/`disk_only` reported as a
  warning-tier note, not a failure verdict.

## Testing

Both gates must pass: `python3 -m pytest tests/` and `bash tests/test-all.sh`.

New cases:
- Fixture ecosystem with a valid manifest → entries matched, metadata attached, no drift.
- Manifest listing a package not on disk → appears in `drift.manifest_only`.
- On-disk package missing from manifest → appears in `drift.disk_only`.
- Case-folding match (`rmediation` dir ↔ `RMediation` name).
- **No manifest** → `Ecosystem` identical to pre-change (regression fixture).
- Malformed/unsupported manifest → enrichment skipped, no exception, hint present.
- `.rforge.yaml` with `manifest:` pointing outside root → rejected safely (no path escape).

## Documentation impact

- `lib/discovery.py` docstring (note the manifest capability + the subset contract).
- Auto-gen reference: `scripts/gen_lib_reference.py`.
- `.rforge.yaml` documentation wherever the `kind:` field is documented — add `manifest:`.
- CHANGELOG + `.STATUS`.
- Any tutorial covering `/rforge:detect` / `:status` ecosystem discovery.
- Cross-link from the consumer: `mediation-planning/docs/RFORGE-COMMANDS.md` notes this
  is the "optional future" follow-up.

## Implementation order

1. **Docs-only (this spec, on `dev`/feature branch).** Decide the YAML-subset vs PyYAML
   question (Open questions below).
2. *(code — needs a feature worktree)* `Manifest`/`ManifestEntry` dataclasses + `parse_manifest`.
3. `.rforge.yaml` `manifest:` extraction in `detect_ecosystem()`.
4. Enrichment + drift computation; extend `Ecosystem.to_dict()` and text formatter.
5. Tests (both gates) incl. the no-manifest regression fixture.
6. Wire the metadata/drift into `/rforge:status` and `/rforge:detect` output (separate,
   optional follow-up — discovery can land first).

## Open questions / risks

- **YAML dependency (decide first):** vendored subset parser vs optional PyYAML. Resolution: ___
- **Match key:** match on `name` only, or also reconcile `path`? If a manifest `path`
  disagrees with where the package was actually found, which wins? Proposed: disk location
  wins for `version`/deps; manifest supplies curation metadata + flags the path mismatch as drift.
- **Order:** should `Ecosystem.packages` be reordered to manifest order, or keep discovery
  order and expose manifest order separately? Reordering could surprise existing callers —
  proposed: keep discovery order; add `manifest_order` list for consumers that want it.
- **Manifest location convention:** only via `.rforge.yaml` `manifest:`, or also auto-probe
  for `ECOSYSTEM-MANIFEST.yaml` at root / one level down? Proposed: explicit config only
  (no magic probing), matching the strict philosophy of `_classify_kind`.

## Sources

- rforge `lib/discovery.py` (module docstring; `detect_ecosystem` `:267`; `_classify_kind`
  `:243`; `_KIND_DECL_RE` `:240`; `parse_description` `:116`; `Ecosystem` `:67`).
- Consumer manifest: `~/projects/r-packages/mediation-planning/ECOSYSTEM-MANIFEST.yaml`.

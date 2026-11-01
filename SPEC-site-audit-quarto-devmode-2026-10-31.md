# SPEC: `docs:check --site` supports Quarto articles and pkgdown development-mode routes

- **Status:** Draft, awaiting user review (grill complete: five decisions recorded below)
- **Date:** 2026-10-31
- **Target version:** v2.23.0 (minor, no command-surface change: 44 commands)
- **Author:** grilled with Claude, grounded in issue #111 and pkgdown 2.2.1 source
- **Related:** issue #111 (this spec), issue #112 (depends on this), `PROPOSAL-v2.23-backlog-2026-10-31.md`,
  `SPEC-docs-check-a2-2026-10-12.md`

## Summary

`lib/_docsite.py` cannot audit a normal pkgdown site that uses `development.mode: auto` or Quarto articles: it
reports 0 routes checked and 37 unsupported sources on medfit. This spec maps `.qmd` articles and resolves pkgdown's
`auto` mode from the pinned `DESCRIPTION` version, adds an explicit `content_freshness: unverified` marker, and keeps
every other unsupported case incomplete. No new command or flag; the engine and `/rforge:docs:check --site` change.

## Motivation

- Issue #111: on engine `b17c099`, `docaudit --package-only --site https://data-wise.github.io/medfit/ --ref 40f82c8`
  returned `incomplete: true`, 0 site routes checked, 37 unsupported article sources.
- Verified for this spec: medfit's `_pkgdown.yml` at `40f82c8` has `development: mode: auto` and its `DESCRIPTION` is
  `Version: 0.15.0`. pkgdown 2.2.1's own `dev_mode_auto("0.15.0")` returns `"release"`, so the site is served from the
  root and the refusal blocks a plain release-mode site. medfit's `/dev/sitemap.xml` returns 404, consistent with no
  dev site.
- Verified: medfit's live `sitemap.xml` has 72 `<loc>` entries and **0 `<lastmod>`** entries, so sitemap data cannot
  establish content freshness.

## Goals

- Map `.qmd` and `.Rmd` articles, including nested ones, to the routes pkgdown produces.
- Resolve `development.mode` (`release`, `default`, `devel`, `unreleased`, `auto`) from the pinned source, without
  guessing, and keep root, `dev/` and redirect cases distinguishable.
- Keep static/API, route-presence, content-freshness and deployment-provenance results separate; never let a green
  route check read as a current published site.
- Keep the default audit offline and read-only; never execute Quarto or R to infer static routes.

## Non-goals

- Verifying content freshness (deferred to #112, which owns publish-and-verify).
- Resolving `PKGDOWN_DEV_MODE` set by a workflow (kept refused; see decision 2).
- Custom Quarto projects, custom transforms, template overlays: stay incomplete.
- New commands, flags or skills; any publication or package release.

## Scope

### In scope (decided)

| # | Decision | Chosen | Rejected alternatives |
|---|----------|--------|-----------------------|
| 1 | Resolve `development.mode: auto` | Derive from `DESCRIPTION` `Version` at the pinned SHA using pkgdown's rule; mark incomplete when the `--site` URL disagrees | Refuse `auto` (today's behavior); audit both prefixes (guessing) |
| 2 | Workflow sets `PKGDOWN_DEV_MODE` | Keep refusing: the env var overrides the YAML and cannot be resolved statically | Accept literal values (large parsing surface); `--dev-mode` flag (new surface) |
| 3 | How to verify route mapping | Pure-Python mapper plus a differential test against `pkgdown:::package_vignettes()` where R and pkgdown exist | Fixtures only (could bake in my reading of pkgdown); call R at runtime (breaks the offline default) |
| 4 | Freshness | Explicit `content_freshness: "unverified"` field plus a text-report line; no new network probes | Probe per-page freshness now (unverified pkgdown behavior, new budgets); docs sentence only |
| 5 | `vignettes/_quarto.yaml` | Supported when absent or exactly pkgdown's default (`project.render == ['*.qmd']`, no other keys); anything else, or both `.yml` and `.yaml` present, is incomplete | Accept any content (a render list could exclude files); refuse any file (refuses medfit, the motivating case) |

### Out of scope (deferred)

- Freshness probes (HTTP `Last-Modified`, content hash against the pinned commit): #112.
- Literal `PKGDOWN_DEV_MODE` support: revisit only if a real package needs it.

## Architecture

All changes are in `lib/_docsite.py` unless noted; line numbers are for engine `baa5905`.

- **Mode resolution (new helper).** pkgdown 2.2.1: fewer than 3 version components is `release`; 3 components is
  `devel` when the patch is 9000 or higher, else `release`; 4+ components is `unreleased` when the first three are
  `0.0.0`, else `devel`. Only `devel` is "in dev"; its prefix is `<development.destination>/` (default `dev/`), all
  other modes serve from the root. Valid explicit values: `auto`, `default`, `release`, `devel`, `unreleased`; anything
  else stays unsupported. Record the pkgdown rule version the helper assumes in the stage output.
- **Guards to change.** `routes()` development guard (`lib/_docsite.py:152-154`): replace with the resolution above.
  The early return at lines 223-224 fires on any reason containing "development"; narrow it to the reasons that remain
  unsupported. Keep both `PKGDOWN_DEV_MODE` guards (lines 128-129 and 219-222).
- **Quarto mapping.** `routes()` currently treats every non-`.Rmd` article as unsupported (lines 168-170). Treat `.qmd`
  like `.Rmd` (same `articles/` prefixing and nesting, lines 172-174). Front-matter checks (lines 203-218) extend to
  `.qmd`: a non-HTML `format:` is unsupported, as a non-HTML `output:` is for `.Rmd`. pkgdown 2.2.1 creates
  `vignettes/_quarto.yaml` (`project: render: ['*.qmd']`) when absent and uses an existing one
  (`build_quarto_articles`); medfit ships exactly that default, so a `_quarto.yaml` is normal, not a refusal. Apply
  decision 5.
- **pkgdown divergences found while reading.** Verify each with the differential test, do not assume:
  `.md` and `.Rmarkdown` are ignored by pkgdown (it globs `.[Rrq]md`) but counted unsupported today; lowercase `.rmd`
  is an article in pkgdown but skipped silently here; pkgdown excludes only directories that start with `tutorials`,
  this code excludes any `tutorials` path component.
- **Dev-mode base (proposed, needs a real devel site to confirm).** pkgdown writes the dev site into the destination
  directory, so routes keep their shape and the *base* shifts: effective base is the requested base plus the prefix
  (accepted as is when the requested URL already ends with it). `sitemap()` already requests `base + "sitemap.xml"`.
- **Freshness marker.** Add `content_freshness: "unverified"` beside `counts` and `provenance` in the stage, and one
  line in the text report. `state: "complete"` must keep meaning route presence only.

## Dependencies

- No new runtime dependencies. PyYAML stays optional, as today (`yaml_data`, line 94-107).
- The differential test needs R and pkgdown; it skips elsewhere and runs in the A2 locked environment.

## Error handling

- Unknown `development.mode`, `PKGDOWN_DEV_MODE` in a workflow, `_quarto.yml` projects, custom transforms, missing or
  invalid YAML, `--site` URL that disagrees with the resolved mode, and ambiguous deployment sources all stay
  `state: "incomplete"` with a specific reason.
- A `DESCRIPTION` without a parseable `Version` is incomplete, never defaulted to `release`.

## Testing

- Fixtures: `.Rmd` and `.qmd`, nested `vignettes/articles`, excludes, release vs devel versions, explicit destination,
  root and `dev/` bases, and the medfit shape (`mode: auto`, `0.15.0`, 37 `.qmd` articles resolves to root routes).
- Negative controls (must fail): a deliberately removed page is `site-missing-page`; a wrong development prefix is
  caught; `mode: auto` with a devel version and a root-only `--site` URL is incomplete; `PKGDOWN_DEV_MODE` stays
  incomplete.
- Differential test against `pkgdown:::package_vignettes()` on the same fixtures (skips without R).
- Gates: `python3 -m pytest tests/` and `bash tests/test-all.sh` (47 checks), with `env -u PYTEST_ADDOPTS`.
- **A2 impact.** Six files under `tests/a2` (`test_site_http`, `test_site_integration`, `test_site_refs`,
  `test_site_routes`, `test_shipping`, `test_observations`), `scripts/a2_fixture_oracles.py`,
  `scripts/a2_observations.py`, `lib/docaudit.py` and `lib/_docexamples.py` reference `_docsite`. Refresh the
  manifest (`scripts/refresh_a2_manifest.py`, check `dropped N, added N`), then fresh `a2-observations` and
  `a2-release` evidence at the candidate SHA on `ubuntu-24.04` and `macos-15`.
- **Real-network smoke test** (`--site` is a network path): the pinned medfit command from #111. A real devel-mode site
  is also needed to confirm the dev-base assumption; medfit has none, so a second target or a local bare-site fixture
  is required.

## Documentation impact

`docs/guides/docs-audit.md` (the "does not prove freshness" wording gains the new field), `commands/docs/check.md`
and `docs/commands.md` (no new flag, behavior text only), CHANGELOG, `.STATUS`, version files at release.

## Implementation order

1. Spec approval (this document). Docs-only on `dev`.
2. Feature branch or worktree for code, **created at your explicit request**.
3. Mapper and mode resolution with fixtures first (TDD), then the differential test.
4. Narrow the guards; add the freshness marker.
5. Adversarial review against the diff (prose and engine contracts), then the real-network smoke test.
6. Manifest refresh and A2 re-attestation, then release prep as in v2.22.2.

## Open questions / risks

- **Dev-base assumption.** Unconfirmed on a live dev site; confirm before relying on it (see Testing).
- **Defaults resolved without a question:** `unreleased` serves from the root (verified: pkgdown sets `in_dev` only
  for `devel`); `.md`, `.Rmarkdown` and lowercase `.rmd` handling is decided by the differential test (decision 3);
  the stage records the assumed pkgdown rule version.
- **Still a stated default (unverifiable without rendering):** a non-HTML Quarto `format:` is unsupported. pkgdown
  injects its own HTML format through a metadata file, and how that merges with a document's `format:` is not read
  here, so this stays conservative.
- **Superseded:** an earlier draft made any `_quarto.yml` under `vignettes/` incomplete; that would have refused
  medfit, so decision 5 replaces it.
- **Behavior change:** sources previously counted unsupported (`.md`, `.Rmarkdown`) will no longer make a stage
  incomplete if the differential test confirms pkgdown ignores them.
- **A2 cost:** roughly an hour of CI per attestation attempt; batch changes first.

## Sources

- Issue #111: https://github.com/Data-Wise/rforge/issues/111
- pkgdown 2.2.1 source, read from the installed package: `dev_mode`, `dev_mode_auto`, `meta_development`,
  `package_vignettes`, `get_site_paths`.
- medfit at `40f82c85`: `_pkgdown.yml` (`development.mode: auto`), `DESCRIPTION` (`Version: 0.15.0`).
- medfit live sitemap (72 `<loc>`, 0 `<lastmod>`; `/dev/sitemap.xml` returns 404), fetched 2026-10-31.

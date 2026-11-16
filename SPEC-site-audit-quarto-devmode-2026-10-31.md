# SPEC: `docs:check --site` supports Quarto articles and pkgdown development-mode routes

- **Status:** Draft rev 2 (2026-11-15), awaiting user review. Revised after the adversarial review; verdicts in
  `TRIAGE-111-spec-review-2026-11-15.md`. All review-driven decisions are recorded; redirects and general output overrides are split to a follow-up issue
(not yet filed).
- **Date:** 2026-10-31 (rev 2: 2026-11-15)
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
| 1 | Resolve `development.mode: auto`; base handling (decided 2026-11-15: **strict match**) | Derive the mode from `DESCRIPTION` `Version` at the pinned SHA using pkgdown's rule. The audit never appends a prefix: the requested `--site` base must equal `config.url + prefix` exactly (`prefix` is `<destination>/` for `devel`, empty otherwise; with no config `url`, the requested base is taken as given but must end in the prefix when the mode is `devel` and must not end in `/<destination>/` otherwise). Any other combination is `incomplete` with a specific reason | Refuse `auto` (today's behavior); audit both prefixes (guessing); silently shift a root URL by the prefix (a root URL on a dev-mode site could then read as a checked, complete site) |
| 2 | Workflow sets `PKGDOWN_DEV_MODE` | Keep refusing: the env var overrides the YAML and cannot be resolved statically. Scan workflows **at the pinned SHA** (`git show`), not the working tree, and treat any job with `uses:` as unverifiable (incomplete) whether or not `--ref` was given | Accept literal values (large parsing surface); `--dev-mode` flag (new surface); scan the working tree (hides the variable behind an old SHA or reusable workflow) |
| 3 | How to verify route mapping | Pure-Python mapper plus a differential test against `pkgdown:::package_vignettes()` where R and pkgdown exist, plus a table-driven differential for `dev_mode_auto` (`package_vignettes` does not cover mode). Both live outside `tests/a2`, non-gating (decided 2026-11-15) | Fixtures only (could bake in my reading of pkgdown); call R at runtime (breaks the offline default) |
| 4 | Freshness | Explicit `content_freshness: "unverified"` field plus a text-report line; no new network probes | Probe per-page freshness now (unverified pkgdown behavior, new budgets); docs sentence only |
| 5 | `vignettes/_quarto.yaml` | Supported when absent or exactly pkgdown's default (`project.render == ['*.qmd']`, no other keys); anything else, or both `.yml` and `.yaml` present, is incomplete | Accept any content (a render list could exclude files); refuse any file (refuses medfit, the motivating case) |

### Out of scope (deferred)

- Root redirects and per-document output overrides beyond output-extension handling: follow-up issue (see Open
  questions).
- Freshness probes (HTTP `Last-Modified`, content hash against the pinned commit): #112.
- Literal `PKGDOWN_DEV_MODE` support: revisit only if a real package needs it.

## Architecture

Changes are in `lib/_docsite.py` and `lib/docaudit.py` (text verdict, see Freshness marker) unless noted; line
numbers in `_docsite.py` were re-read against `dev` at 518bd2f (engine `baa5905` line numbers still match).

- **Mode resolution (new helper).** pkgdown 2.2.1: fewer than 3 version components is `release`; 3 components is
  `devel` when the patch is 9000 or higher, else `release`; 4+ components is `unreleased` when the first three are
  `0.0.0`, else `devel`. Only `devel` is "in dev"; its prefix is `<development.destination>/` (default `dev/`), all
  other modes serve from the root. Valid explicit values: `auto`, `default`, `release`, `devel`, `unreleased`; anything
  else stays unsupported. Record the pkgdown rule version the helper assumes in the stage output. State how versions
  are parsed: pkgdown's `package_version` accepts both `.` and `-` separators, so the Python parser must as well, and
  an unparseable version is incomplete (see Error handling).
- **Config discovery.** pkgdown reads the first existing of `_pkgdown.yml`, `_pkgdown.yaml`, `pkgdown/_pkgdown.yml`,
  `pkgdown/_pkgdown.yaml`, `inst/_pkgdown.yml`, `inst/_pkgdown.yaml` (first wins, no merge). The engine currently
  ignores `inst/` and merges with `config.update` (line 194), so a devel or auto config under `inst/` would resolve to
  `release`: a false complete. Add the `inst/` candidates to discovery and treat more than one config file, or any file
  outside the repo root, as incomplete (the existing overlay reason).
- **Bootstrap version.** In dev mode pkgdown adds the sitemap prefix only when `bs_version > 3`; an unset
  `template.bootstrap` means 3. A bootstrap-3 devel site therefore writes `<dst>/sitemap.xml` with unprefixed
  locations. Detect `bs_version` from the config; `devel` with bs3 is incomplete with a specific reason (today it would
  fail closed by accident with "zero entries in the requested base"). pkgdown's `get_site_paths` also drops any path
  whose parent is `development.destination` regardless of mode; that supports the root-sitemap behavior and is
  covered by the differential test.
- **Guards to change.** `routes()` development guard (`lib/_docsite.py:152-154`): replace with the resolution above.
  The early return at lines 223-224 matches the substring "development" and so also fires on unrelated reasons such
  as `unsupported article source: vignettes/development.Rmd`. Replace it with a structured flag
  (`stage["pre_network_block"] = True`, or a resolver that raises `ValueError`) set by every reason that must skip the
  network call (unknown mode, bad destination, URL/prefix mismatch, bs3 devel, `PKGDOWN_DEV_MODE`, `uses:` job).
  Keep both `PKGDOWN_DEV_MODE` guards, with the line-219-222 scan moved to the pinned SHA (decision 2).
- **Quarto mapping.** `routes()` currently treats every non-`.Rmd` article as unsupported (lines 168-170). Treat `.qmd`
  like `.Rmd` (same `articles/` prefixing and nesting, lines 172-174). Front-matter checks (lines 203-218) extend to
  `.qmd`: a non-HTML `format:` is unsupported (no exception, unlike `.Rmd` `extension: pdf`; see pkgdown
  divergences), as a non-HTML `output:` is for `.Rmd`, and route-changing override keys are refused (same section). pkgdown 2.2.1 creates
  `vignettes/_quarto.yaml` (`project: render: ['*.qmd']`) when absent and uses an existing one
  (`build_quarto_articles`); medfit ships exactly that default, so a `_quarto.yaml` is normal, not a refusal. Apply
  decision 5.
- **pkgdown divergences found while reading** (the reviewer re-ran the first three against pkgdown 2.2.1 on a
  fixture; the differential test must keep them pinned):
  - `.md` and `.Rmarkdown` are ignored by pkgdown (it globs `.[Rrq]md`) but counted unsupported today; lowercase
    `.rmd` is an article in pkgdown but skipped silently here.
  - pkgdown's exclusion is the regex `^tutorials` on the **directory part** only. `tutorials/g.Rmd` and
    `tutorials-old/h.Rmd` are excluded; `articles/tutorials/f.Rmd` is an article (`articles/tutorials/f.html`);
    `vignettes/tutorials.Rmd` is an article; `_priv/i.Rmd` is an article. The code's `"tutorials" in parts`
    (`lib/_docsite.py:166`) is wrong in both directions: replace it with the directory-prefix rule.
  - An `.Rmd` article can emit a non-HTML route: `pkgdown: extension: pdf` gives `articles/p.pdf` (verified by the
    reviewer on pkgdown 2.2.1). This is the **one supported exception** to the non-HTML refusal, and only for `.Rmd`:
    the mapper applies the declared extension when it is a plain string, and any other value (missing, non-string,
    templated) is unsupported, never `.html`. For `.qmd` there is no such exception: a non-HTML `format:` (including
    `format: pdf`) is unsupported and makes the stage incomplete, because how pkgdown merges its HTML format with a
    document's `format:` is not verified (see Open questions). The fixture and the differential test pin both halves:
    `.Rmd` + `extension: pdf` maps to `articles/p.pdf`; `.qmd` + `format: pdf` is incomplete.
  - **Route-changing overrides are refused, not guessed.** A document whose front matter carries any key that can
    rename or relocate its output is unsupported: for `.Rmd`, `output_file`, `knit` and `pkgdown: extension` with a
    non-plain value; for `.qmd`, `output-file`, `output-ext` and `output-dir`, wherever they appear (top level or
    nested under `format:`). The check scans the whole front-matter mapping, not only `format`, `output` and `as_is`.
    Its route is removed from the expected set (as `as_is` articles are today) and the stage is incomplete with a
    reason naming the file and key, so a default route that happens to remain in the sitemap cannot satisfy it.
    This list is the set known now; it is conservative (refuse on presence) and implementation must also refuse any
    key matching `output[-_](file|ext|dir)`. Full override support is the follow-up (#123).
  - Quarto copies every other rendered file under `articles/`; expect `site-extra-page` info findings for those and
    do not treat them as failures.
- **Dev-mode base (strict match; proposed mechanism still needs a real devel site to confirm).** pkgdown writes the
  dev site into the destination directory, so routes keep their shape and the sitemap lives at
  `<root>/<destination>/sitemap.xml` for bs>3 sites. The audit requests `base + "sitemap.xml"` where `base` is the
  requested URL, validated against `config.url + prefix` as in decision 1. Replace the check at line 199 (which
  rejects any `config.url` different from the requested base) with this matrix:

  | config `url` | requested `--site` | resolved mode | result |
  |--------------|--------------------|---------------|--------|
  | present | `config.url` | non-devel | audit |
  | present | `config.url` + `<dst>/` | devel (bs>3) | audit |
  | present | `config.url` | devel | incomplete: requested base lacks the dev prefix |
  | present | `config.url` + `<dst>/` | non-devel | incomplete: dev URL but mode resolves to root |
  | present | anything else | any | incomplete: source url disagrees (today's message) |
  | absent | ends in `<dst>/` | devel (bs>3) | audit |
  | absent | not ending in `<dst>/` | devel | incomplete |
  | absent | ends in `<dst>/` | non-devel | incomplete |
  | absent | not ending in `<dst>/` | non-devel | audit |

- **Freshness marker.** Add `content_freshness: "unverified"` beside `counts` and `provenance` in the stage.
  A stage field alone is not enough: `lib/docaudit.py` (`format_text`, around line 1159) prints "no findings" for a
  complete site stage, which reads as a current site. The verdict line must say "no findings; site content freshness
  unverified" whenever a site stage ran, and any consumer of `status: ok` must see the marker. `state: "complete"`
  must keep meaning route presence only.
- **A2 live-smoke observation.** `scripts/a2_observations.py` (comment at line 36, `LIMIT_SITES` medfit and probmed)
  requires a non-empty list of real sites that remain unsupported. After this change both may become supported, or
  medfit's floating HEAD may be a devel site whose dev base 404s and "passes" for the wrong reason. Pin the limit
  sites to SHAs, add a genuinely unsupported real site (or a pinned fixture standing in for one), update the comment,
  `docs/guides/docs-audit.md:152` and the `test_observations` fixtures.

## Dependencies

- No new runtime dependencies. PyYAML stays optional, as today (`yaml_data`, line 94-107).
- The differential test needs R, pkgdown **and Quarto**: `package_vignettes()` calls `article_metadata`, which calls
  `quarto::quarto_inspect` for every `.qmd`, so the Quarto CLI and the R `quarto` package are required. Neither is in
  `.github`, `provision_a2.R` or `fixture-lock.json` (pkgdown 2.2.1 only). The earlier claim that the test "skips
  elsewhere and runs in the A2 locked environment" was unsupported. Decision: it lives outside `tests/a2`, non-gating
  (see Open questions).

## Error handling

- Unknown `development.mode`, `PKGDOWN_DEV_MODE` in a workflow, a `uses:` workflow job, `_quarto.yml` projects, custom
  transforms, missing or invalid YAML, more than one pkgdown config file, bootstrap-3 `devel`, a `--site` URL that
  fails the strict base match, an unrecognized article output extension, a route-changing override key, a `.qmd`
  non-HTML `format:`, and ambiguous deployment sources all stay
  `state: "incomplete"` with a specific reason, and every reason that precedes the network call sets
  `pre_network_block`.
- A `DESCRIPTION` without a parseable `Version` is incomplete, never defaulted to `release`.

## Testing

- Fixtures: `.Rmd`, `.rmd` and `.qmd`, nested `vignettes/articles`, `articles/tutorials/**`, `tutorials-old/**`,
  `tutorials.Rmd`, excludes, release vs devel versions (including `-` separators), explicit destination, root and
  `dev/` bases, `inst/_pkgdown.yml`, an `.Rmd` with `pkgdown: extension: pdf` (maps to `.pdf`), a `.qmd` with
  `format: pdf` (incomplete), articles with `output-file`/`output-ext`/`output_file`/`knit` (incomplete; negative
  fixture keeps the default `.html` route in the sitemap and must still be incomplete), and the medfit shape (`mode: auto`,
  `0.15.0`, 37 `.qmd` articles resolves to root routes).
- Negative controls (must fail): a deliberately removed page is `site-missing-page`; a wrong development prefix is
  caught; `mode: auto` with a devel version and a root-only `--site` URL is incomplete (every incomplete row of the
  base-match matrix gets a case); a `/dev/` URL with a release-resolving version is incomplete; a devel config only in
  `inst/` is not read as release; `PKGDOWN_DEV_MODE` in a workflow at the pinned SHA, and a `uses:` job, stay
  incomplete even with an explicit `--ref`; `vignettes/development.Rmd` does not suppress the network call.
- Differential tests: `package_vignettes()` on the same fixtures, and a table-driven check of the mode rule against
  `dev_mode_auto` (versions from the Mode resolution bullet). Both live outside `tests/a2` and are non-gating, so
  they add no required A2 node.
- Gates: `python3 -m pytest tests/` and `bash tests/test-all.sh` (47 checks), with `env -u PYTEST_ADDOPTS`.
- **A2 impact.** Six files under `tests/a2` (`test_site_http`, `test_site_integration`, `test_site_refs`,
  `test_site_routes`, `test_shipping`, `test_observations`), `scripts/a2_fixture_oracles.py`,
  `scripts/a2_observations.py`, `lib/docaudit.py` and `lib/_docexamples.py` reference `_docsite`. Required nodes whose
  meaning changes (`tests/a2/required.json`): `test_site_integration.py::test_unsupported_layout_retains_supported_routes[quarto]`
  (bare `custom.qmd`, no `_quarto.yaml`) and `[extension]` (`.Rmarkdown`), and the params of
  `test_site_routes.py::test_release_mode_and_destination` (devel and destination become supported). Editing params
  changes node IDs, and `verify_a2_release.py:73` rejects missing or skipped nodes, so the manifest refresh must show
  the expected `dropped N, added N`. The frozen A2 requirement rows (`requirements.json` 435 and 490) state the old
  behavior; `SPEC-docs-check-a2-2026-10-12.md` is a frozen gate input and is **not** edited. Record the revision in
  issue #111, CHANGELOG and `docs/guides/docs-audit.md`. Then fresh `a2-observations` and `a2-release` evidence at the
  candidate SHA on `ubuntu-24.04` and `macos-15`, with a review record whose `reviewed_commit` equals that SHA.
- **Real-network smoke test** (`--site` is a network path): the pinned medfit command from #111. A real devel-mode site
  is also needed to confirm the dev-base assumption; medfit has none, so a second target or a local bare-site fixture
  is required.

## Documentation impact

`docs/guides/docs-audit.md` (the "does not prove freshness" wording gains the new field; line 152 changes with the
limit-site observation; record the A2 behavior revision here), `commands/docs/check.md` and `docs/commands.md` (no
new flag, behavior text only), CHANGELOG, `.STATUS`, version files at release.

## Implementation order

1. Spec approval (this document). Docs-only on `dev`.
2. Feature branch or worktree for code, **created at your explicit request**.
3. Mapper and mode resolution with fixtures first (TDD), then the differential test.
4. Narrow the guards; add the freshness marker.
5. Adversarial review against the diff (prose and engine contracts), then the real-network smoke test.
6. Manifest refresh and A2 re-attestation, then release prep as in v2.22.2.

## Open questions / risks

- **Decided 2026-11-15: home of the differential test is outside `tests/a2`, non-gating.** It runs where R, pkgdown
  and Quarto exist and skips elsewhere. Rejected: provisioning the Quarto CLI and R `quarto` package in the A2
  environment (a `tests/a2` test is auto-added to the default group and becomes a required no-skip node, and it would
  change the A2 environment and lock); stubbing `article_metadata` (tests the stub, not pkgdown). Consequence: the
  mapper is not gate-verified against pkgdown at release time, so run the differential test by hand before the
  adversarial review and quote its output in the PR body.
- **Decided 2026-11-15: split to a follow-up issue.** From #111's acceptance list, two fixture items move out of
  this spec: "root redirects" (no design yet; the existing redirect handler accepts only same-origin, at most 3 hops)
  and "supported output overrides" beyond the article output-extension handling specified above (per-document
  `output-file`, `output-ext` and similar). Until the follow-up ships, a redirect or override this spec does not map
  is `incomplete` with a specific reason, never an invented route. The remaining #111 acceptance items stay in scope,
  including documentation and native skill guidance. The follow-up issue is not yet filed; #111's acceptance list must
  be edited or annotated when it is, so that closing #111 does not claim the two items. (The tail of the reviewer's
  finding 12 was lost; the acceptance list was re-read from the issue on 2026-11-15.)
- **Dev-base assumption.** Unconfirmed on a live dev site; confirm before relying on it (see Testing). The strict
  match makes a wrong assumption fail closed (incomplete), not complete.
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
- Adversarial review of rev 1 and the re-check against source: `TRIAGE-111-spec-review-2026-11-15.md`. Findings
  re-run by the reviewer (not by this revision): bootstrap-3 sitemap prefix, `^tutorials` regex, `pkgdown: extension`,
  `pkgdown_config_path` order, `package_vignettes` needing Quarto.

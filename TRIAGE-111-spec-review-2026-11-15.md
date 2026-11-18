# Triage: adversarial review of SPEC-site-audit-quarto-devmode (#111)

Source: reviewer hand-back from session 3aac96d5 (2026-10-31). Each finding re-checked against `dev` @ 518bd2f on 2026-11-15.
Evidence: **confirmed** = re-read in current source; **carried** = reviewer ran pkgdown/gh, not re-run here.
Finding 12 was cut off in the saved hand-back (text after "per-document output-file/output-ext/_m"); only its first half is known.

| # | Sev | Verdict | Evidence | SPEC change |
|---|-----|---------|----------|-------------|
| 1 | blocker | confirmed | `lib/_docsite.py:199` raises when `base_url(config.url) != base`; SPEC never touches it | State the config-url x requested-URL x resolved-prefix matrix; compare against `config.url + prefix` |
| 2 | blocker | confirmed | SPEC lines 50/106 (root URL incomplete) vs 83-85 (base = requested + prefix) | Pick one: never append; require `requested == config.url + prefix`, else incomplete; symmetric for non-devel with a `/dev/` URL |
| 3 | important | carried | pkgdown `build_sitemap` prefixes only if `bs_version > 3` | Document bs3 devel sites; detect bs_version, incomplete when bs3 + devel |
| 4 | important | confirmed | line 194 filters `_pkgdown.y*ml` and `pkgdown/*` only; no `inst/`; `config.update` merges | Add `inst/_pkgdown.*` to discovery; more than one config file means incomplete |
| 5 | important | confirmed | line 220 scans working-tree workflows, `PKGDOWN_DEV_MODE` only; `uses:` check (line 126) runs only when `--ref` is None | Scan workflows at pinned SHA via `git show`; treat `uses:` as unverifiable |
| 6 | important | confirmed | line 223 substring match; "development" also hits `vignettes/development.Rmd` reason | Structured flag (`pre_network_block`) or resolver raises `ValueError` |
| 7 | important | confirmed (code) / carried (pkgdown) | line 166 `"tutorials" in parts`, only `.Rmd` suffix; no extension handling | Mirror `^tutorials` on directory part; add `.rmd`/`.qmd`; unknown output extension = unsupported |
| 8 | important | partly confirmed | `a2_observations.py:36` comment + medfit/probmed `LIMIT_SITES` read; floating-HEAD claim reasoned only | Pin limit sites, add a genuinely unsupported real site, update `docs/guides/docs-audit.md:152` |
| 9 | important | confirmed | `required.json` 265-266 and 284-289 list the affected node IDs | Name the nodes; record revision in issue/CHANGELOG/guide, not in the frozen A2 SPEC |
| 10 | important | confirmed | grep for quarto in `.github`, `tests/a2/provision*`, `fixture-lock.json` found nothing | Provision Quarto, or stub `article_metadata`, or keep the differential test outside `tests/a2` and non-gating; add table test for `dev_mode_auto` |
| 11 | important | confirmed | only `lib/docaudit.py:1159` emits "no findings" | Verdict line says "no findings; site content freshness unverified"; correct the "all changes in _docsite.py" claim |
| 12 | important | partly known | #111 acceptance lists root redirects, output overrides, skill guidance | Decide in or out of scope explicitly; redirect handler only allows same-origin, max 3 |

## Order of work
1. Blockers 1 and 2 (one design decision on base handling).
2. 4, 5, 6 (false-complete risks; fix before any code).
3. 7, 10, 9, 8 (A2 gate consequences; any `_docsite` change forces A2 re-attestation).
4. 3, 11, 12.

## Decided
- Base handling (findings 1-2), decided 2026-11-15: **strict match**. The audit never appends the prefix; it requires `requested == config.url + prefix` (or `requested` when no config url) and reports incomplete otherwise, symmetrically when a `/<destination>/` URL meets a non-devel resolved mode. The SPEC's Architecture paragraph (lines 83-85) must be rewritten to match decision 1 and the negative control.

## Open decisions for the user
- Differential test home (finding 10): provision Quarto in A2 vs. non-gating outside `tests/a2`.
- Finding 12 scope: redirects/output overrides in #111 or split to a follow-up issue.

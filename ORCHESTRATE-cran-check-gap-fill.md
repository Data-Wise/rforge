# ORCHESTRATE — CRAN check gap-fill bundle (v2.14.0)

> **How to use:** You are already in the right session.
> CWD: `~/.git-worktrees/rforge/feature-cran-check-gap-fill`
> Branch: `feature/cran-check-gap-fill` (worktree off `dev`)
> Spec: `docs/specs/SPEC-cran-check-gap-fill-2026-06-19.md`
> Read that spec first — all decisions are final; this file is the execution plan.

## Context

Eight CRAN pre-submission gaps (G1–G8) found in live submissions (RMediation 1.5.0,
medrobust 0.4.0) and a CRAN incoming-feasibility audit. No new commands; one new flag;
two new `lib/cranlint.py` findings; one new `check_test_config()` function; three
`lib/rcmd.py` extensions. 41 commands stay at 41. Target: ~435+ pytest cases.

## Decisions (from spec + adversarial review)

- **G1:** `r:winbuilder --platform devel|release|oldrelease|all|rhub`; default `all` (breaking change from implicit `devel`; document in CHANGELOG). `rhub` uses `_guard("rhub", ...)` not `devtools`.
- **G2:** `language_missing` only fires when `vignettes/` or `man/` dir exists (CRAN's actual condition).
- **G3:** Scan `Description` field only (`References` is not standard DCF). Lookbehind `(?<![<({])` covers angle-brackets, parens, AND curly braces (Rd `\url{}`).
- **G4:** `status` changes `"error"` → `"warn"` when only doi.org 403s present — document in CHANGELOG as behavior change.
- **G5:** `lib/cranlint.py` needs a `__main__` CLI entrypoint (subcommands: `lint`, `build-hygiene`, `docs-consistency`, `check_test_config`). Wire `check_test_config` into `run_all` AND into `commands/r/test.md` prompt.
- **G6:** `--run-donttest` on `strict OR incoming` (not strict-only). CRAN always runs `\donttest{}`.
- **G7:** `_R_CHECK_DEPENDS_ONLY_` and `_R_CHECK_SUGGESTS_ONLY_` are **mutually exclusive** — two sequential rcmdcheck passes, merged with `pass:` tag. Always-on for `--incoming`; document ≈3× check time in `commands/r/check.md`.
- **G8:** Regex strings for PDF skip are unverified — run R CMD check without LaTeX first, capture output, then finalize regex. Candidates: "skipping PDF manual", "LaTeX not found", "pdflatex not found".

## Steps

### Increment 1 — `lib/cranlint.py` changes (G2, G3, G5)

**Files:** `lib/cranlint.py`, `tests/test_cranlint.py`

1. **G2** — `language_missing` finding in `lint_description()`:
   - After `date_stale` block, before `return _envelope(...)`.
   - Gate: `(pkg_dir / "vignettes").is_dir() or (pkg_dir / "man").is_dir()`.
   - New pytest cases: `test_lint_description_language_missing` (with docs dirs → finding),
     `test_lint_description_language_missing_no_docs_skip` (no docs dirs → no finding),
     `test_lint_description_language_present` (Language set → no finding).

2. **G3** — `doi_format` finding in `lint_description()`:
   - Module-level: `_BARE_DOI_RE = re.compile(r'(?<![<({])(?:doi:\s*10\.|https?://(?:dx\.)?doi\.org/10\.)', re.I)`
   - Scan `fields.get("Description", "")` only.
   - New pytest cases: `test_doi_format_bare_doi`, `test_doi_format_bare_url`,
     `test_doi_format_wrapped_ok`, `test_doi_format_markdown_link_ok`,
     `test_doi_format_url_curly_ok` (Rd curly-brace excluded).

3. **G5** — `check_test_config(path)` new function:
   - Returns envelope `{kind: "test_config", status, findings, messages}`.
   - Findings: `testthat_edition_missing` (absent) and `testthat_edition_outdated` (value is "2").
   - Add `__main__` CLI entrypoint at end of file:
     ```python
     if __name__ == "__main__":
         import sys, json
         subcmd = sys.argv[1] if len(sys.argv) > 1 else "lint"
         path   = sys.argv[2] if len(sys.argv) > 2 else "."
         fn_map = {
             "lint": lint_description,
             "build-hygiene": check_build_hygiene,
             "docs-consistency": check_planning_consistency,
             "check_test_config": check_test_config,
         }
         fn = fn_map.get(subcmd)
         if fn is None:
             print(f"Unknown subcommand: {subcmd}", file=sys.stderr); sys.exit(1)
         print(json.dumps(fn(path), indent=2))
     ```
   - New pytest cases: `test_check_test_config_missing`, `test_check_test_config_edition2`,
     `test_check_test_config_edition3`, `test_check_test_config_no_description`,
     `test_cranlint_cli_check_test_config` (subprocess smoke test).

**Gate:** `python3 -m pytest tests/test_cranlint.py` — all new cases pass.

### Increment 2 — `lib/rcmd.py` changes (G4, G1, G6, G7, G8)

**Files:** `lib/rcmd.py`, `commands/r/winbuilder.md`, `tests/test_rcmd_*.py`

4. **G4** — urlcheck normalizer split:
   - Post-process `broken` list → split on `"doi.org" in url and "403" in status`.
   - Emit `doi_blocked` list + `doi_blocked_count` in envelope.
   - Status logic: broken non-empty → "error"; broken empty + doi_blocked → "warn"; both empty → "ok".
   - New pytest cases: `test_urlcheck_doi_403_classified`, `test_urlcheck_real_404_not_classified`,
     `test_urlcheck_403_non_doi_not_classified`, `test_urlcheck_string_items_passthrough`.

5. **G1** — win-builder platform matrix:
   - Add `platform: str = "all"` kwarg to `run()`, thread through `_r_snippet`.
   - Module-level `_WIN_FN` dict (devel/release/oldrelease → devtools functions).
   - Module-level `_RHUB_FN = "rhub::rhub_check"`.
   - rhub branch uses `_guard("rhub", ...)` (not devtools); note field: "Results in GitHub Actions tab, not email".
   - Update `commands/r/winbuilder.md` `arguments:` array: add `--platform` with `default: all`.
   - New pytest cases: `test_winbuilder_platform_release`, `test_winbuilder_platform_all`,
     `test_winbuilder_default_is_all`, `test_winbuilder_platform_rhub`.

6. **G6** — `--run-donttest` (trivial, 3 lines):
   - In check kind snippet: `if strict or incoming: args.append("--run-donttest")`
   - New pytest cases: `test_check_strict_run_donttest`, `test_check_incoming_run_donttest`,
     `test_check_non_strict_no_donttest`.

7. **G7** — `_CRAN_CHECKS_REGISTRY` + sequential passes:
   - Module-level `_CRAN_CHECKS_REGISTRY` dict (base keys + R4.3/R4.4/R4.5 empty stubs).
   - `_r_version_key()` helper: shells `Rscript -e 'cat(R.version$major,".",R.version$minor,sep="")'`; falls back to "base".
   - `incoming=True` → two sequential rcmdcheck passes (pass 1: DEPENDS_ONLY, pass 2: SUGGESTS_ONLY; pass 3: S3_REGISTRATION + version-specific); merge findings with `pass:` tag.
   - New pytest cases: `test_cran_checks_registry_base_keys`, `test_incoming_fires_sequential_passes`,
     `test_r_version_key_format`.

8. **G8** — PDF manual skip advisory:
   - **Before writing regex:** run `R CMD check --as-cran` on any package without LaTeX (or `tinytex::uninstall_tinytex()` temporarily), capture exact output. Then finalize the regex.
   - After normalizing NOTEs/WARNINGs/ERRORs in check kind, scan `messages` for skip text.
   - Emit `pdf_manual_skipped` advisory finding (does not change overall status).
   - New pytest cases: `test_pdf_manual_skipped_advisory`, `test_pdf_manual_present_no_advisory`.

**Wire G5 into rcmd.py:** add `check_test_config` as `test-config` stage in `run_all`; skip if `tests/testthat/` absent.

**Gate:** `python3 -m pytest tests/` — all new cases pass; total ≥ 435.

### Increment 3 — Doc sweep + auto-gen + gates

9. **Doc sweep** — update all listed files:
   - `commands/r/winbuilder.md` — `--platform` in `arguments:` + `## Usage`.
   - `commands/r/urlcheck.md` — `doi_blocked_count` advisory block render logic.
   - `commands/r/check.md` — `--incoming` description: "Runs 3 sequential CRAN passes; expect ≈3× check time."
   - `commands/r/test.md` — pre-flight advisory: run `python3 -m lib.cranlint check_test_config .` before R test runner; surface findings; skip if no `tests/testthat/`.
   - `commands/r/cran-prep.md` — no frontmatter change needed (run_all picks up new stage automatically); add note to `## What it does` body.
   - `docs/commands.md` — update `r:winbuilder` row: add `--platform` column.
   - `docs/guides/cran-submission.md` — sub-section for win-builder matrix; note on doi.org 403 handling.
   - `docs/tutorials/cran-release-prep.md` — mention `Language:` field and DOI format.
   - `CLAUDE.md` — G7 update protocol: "on each R major.minor release, audit R Internals §8 for new `_R_CHECK_*` vars and update `_CRAN_CHECKS_REGISTRY` in `lib/rcmd.py`."
   - `CHANGELOG.md` — `[Unreleased]` section with all 8 gaps; note G4 status behavior change.
   - `.STATUS` — update to reflect v2.14.0 unreleased bundle in-progress.

10. **Auto-gen** (MUST run before gates):
    ```bash
    python3 scripts/gen_lib_reference.py
    ```
    Both `docs/reference/cranlint.md` and `docs/reference/rcmd.md` will drift until this runs.

11. **Gates** (both must be green):
    ```bash
    python3 -m pytest tests/   # target ≥435 passing
    bash tests/test-all.sh     # 43/43
    ```

12. **Commit + push**:
    ```bash
    git add -p   # stage selectively
    git commit -m "feat(cranlint,rcmd): CRAN check gap-fill bundle (G1–G8, v2.14.0)"
    git push -u origin feature/cran-check-gap-fill
    ```

## PR (user runs this)

```bash
gh pr create --base dev \
  --title "feat: CRAN check gap-fill bundle (G1–G8) — v2.14.0" \
  --body "Closes #46. Eight CRAN pre-submission gaps: win-builder platform matrix, Language:/DOI lints, doi.org 403 classification, testthat edition advisory, --run-donttest, _R_CHECK_* versioned registry, PDF manual skip detection. 41 commands unchanged. Spec: docs/specs/SPEC-cran-check-gap-fill-2026-06-19.md."
```

## Open risks (from spec)

- **G8 regex:** strings are unverified — implementer must capture real R CMD check output before finalizing.
- **G4 status format:** `urlchecker` `status` column is free-text; `"403" in status` handles variation; confirm with both `"403: Forbidden"` and `"403 Forbidden"` fixtures.
- **G3 false positives:** `\href{https://doi.org/...}` in Rd won't be caught by lookbehind — advisory only, acceptable for now.

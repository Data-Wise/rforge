# SPEC — CRAN submission gap-fill bundle

**Date:** 2026-06-19
**Branch:** `feature/cran-check-gap-fill` (worktree off `dev` — created at implementation time)
**Status:** Approved — decisions confirmed 2026-06-19
**Target version:** v2.14.0
**Closes:** issue #46 (Enhance check coverage to match full CRAN win-builder matrix + metadata lints)

## Summary

Eight gaps in CRAN pre-submission coverage — five found during live RMediation 1.5.0 and
medrobust 0.4.0 submissions, three from a research audit of CRAN's incoming feasibility
checks vs local toolchain — are addressed in one bundle. No new commands; one new flag
(`r:winbuilder --platform`); two new `lint_description()` findings; one new
`check_test_config()` in `cranlint.py`; three `rcmd.py` normalizer/snippet extensions
(urlcheck split, `--run-donttest`, `_R_CHECK_*` env vars + versioned registry). 41 commands
unchanged; 400+ pytest cases → ~435+.

## Motivation

Gaps 1–4 were discovered in live CRAN pre-submission checks (June 2026):

- **RMediation 1.5.0** (resubmission): manual `devtools::check_win_release()` +
  `check_win_oldrelease()` required; `Language:` field absent flagged by `spelling`;
  doi.org 403s in urlchecker output caused false-alarm fatigue.
- **medrobust 0.4.0** (new submission): same win-builder and `Language:` gaps; two
  valid Quarto-vignette DOIs flagged as ERROR by urlchecker.

Gap 5 (testthat edition) is a known industry pattern: packages not setting
`Config/testthat/edition: 3` may silently run on edition 2, with new snapshots
created on CI failing unexpectedly.

Gaps 6–8 come from a research audit of CRAN's incoming feasibility checks vs the local
toolchain:

- **G6** (`--run-donttest`): CRAN's incoming pass runs `\donttest{}` examples; local
  `--as-cran` skips them by default. Exposed failures only on CRAN, not pre-submission.
- **G7** (`_R_CHECK_*` env vars): CRAN's incoming machine sets `_R_CHECK_DEPENDS_ONLY_`
  and `_R_CHECK_SUGGESTS_ONLY_` in addition to `--as-cran`. These catch Suggests packages
  used without `requireNamespace()` guards and undeclared packages, respectively. A
  versioned registry tracks which vars each R release activates.
- **G8** (PDF manual build advisory): CRAN always builds the PDF reference manual; local
  checks silently skip it when LaTeX is absent. The skip is not surfaced as a warning.

## Goals

- `r:winbuilder` defaults to submitting all three win-builder platforms (devel + release +
  oldrelease); individual platforms selectable via `--platform`; `--platform rhub` dispatches
  `rhub::rhub_check()` (multi-platform GitHub Actions CI) as an alternative external check.
- `r:cran-prep` (via `lint_description`) proactively flags missing `Language:` field
  (when vignettes or man/ exist) and bare DOIs/URLs before running R CMD check.
- `r:urlcheck` output distinguishes doi.org bot-blocks (WARN) from real broken URLs (ERROR);
  normalizer fully owns urlcheck status.
- `r:cran-prep` and `r:test` both surface absent or edition-2 testthat config
  (skip if no `tests/testthat/` directory).
- `r:check --strict` runs `\donttest{}` examples via `--run-donttest`, matching CRAN's
  incoming pass.
- `r:check --incoming` threads `_R_CHECK_DEPENDS_ONLY_` and `_R_CHECK_SUGGESTS_ONLY_`
  env vars (plus any R-version-specific additions from a new versioned registry in `lib/rcmd.py`)
  to replicate CRAN's post-acceptance env.
- `r:check` output surfaces a WARN when LaTeX is absent and the PDF manual build was silently skipped.

## Non-goals

- **cran-comments.md auto-generation** for doi.org 403s — useful future feature but a
  separate UX surface; deferred.
- **DOI resolution API probe** (issue Option B) — classification into WARN is sufficient;
  the API probe adds latency and a network dependency.
- **URL redirect classification** beyond the existing urlchecker output.
- **R6/S4 convention checking** — unrelated, parked separately.
- **issue #9 rename ergonomics** — unrelated, separate decision.

## Scope

### In scope (all 8 gaps)

| Gap | Surface | File(s) | Effort |
|-----|---------|---------|--------|
| G1: win-builder platform matrix | `r:winbuilder --platform` flag (devel\|release\|oldrelease\|all\|rhub) | `commands/r/winbuilder.md`, `lib/rcmd.py` | Low |
| G2: `Language:` field lint | New finding `language_missing` in `lint_description()` | `lib/cranlint.py` | Very low |
| G3: DOI angle-bracket lint | New finding `doi_format` in `lint_description()` | `lib/cranlint.py` | Low |
| G4: doi.org 403 classification | Split urlcheck `broken` → `broken` + `doi_blocked` in normalizer | `lib/rcmd.py` | Low |
| G5: testthat edition detection | New `check_test_config()` wired into `r:cran-prep` + `r:test` | `lib/cranlint.py`, `lib/rcmd.py` | Medium |
| G6: `--run-donttest` in strict check | Add `--run-donttest` to `r:check --strict` R CMD check args | `lib/rcmd.py` | Very low |
| G7: `_R_CHECK_*` env vars + versioned registry | Thread CRAN incoming env vars; add `_CRAN_CHECKS_REGISTRY` dict | `lib/rcmd.py` | Low |
| G8: PDF manual build advisory | Detect LaTeX-skip in check normalizer; emit `warn` finding | `lib/rcmd.py` | Low |

### Out of scope (deferred)

- cran-comments boilerplate generation (no spec yet; open for v2.15+)
- DOI validation via content-negotiation API
- Win-builder result polling / inbox check (email is async by design)

## Architecture

### G1 — win-builder platform (`lib/rcmd.py:404`)

Current snippet (`kind == "winbuilder"`) hardcodes `devtools::check_win_devel()`.

**Change:** add a `platform: str = "all"` kwarg to `run()` (threaded through
`_r_snippet`). Default is `"all"` — **breaking change from the prior implicit
`devel`-only behavior; document in CHANGELOG.** The R snippet selects the
appropriate function(s):

```python
# lib/rcmd.py — _r_snippet addition
_WIN_FN = {
    "devel":      "devtools::check_win_devel",
    "release":    "devtools::check_win_release",
    "oldrelease": "devtools::check_win_oldrelease",
}
# rhub is separate: multi-platform GitHub Actions CI, not CRAN's win-builder servers.
# Uses rhub package (v2+) with a rhub::rhub_check() call that commits a workflow file.
_RHUB_FN = "rhub::rhub_check"

if kind == "winbuilder":
    if platform == "rhub":
        # rhub v2: dispatches to GitHub Actions; requires rhub package (v2+)
        return _guard("rhub",
            f'{_RHUB_FN}({p}); '
            f'cat(jsonlite::toJSON(list(submitted=TRUE, platform="rhub", '
            f'note="Results in GitHub Actions tab, not email"), auto_unbox=TRUE))')
    if platform == "all":
        # fire all three win-builder platforms; each is async (email)
        fns = list(_WIN_FN.values())
        calls = "; ".join(f"{fn}({p})" for fn in fns)
        return _guard("devtools",
            f'{calls}; '
            f'cat(jsonlite::toJSON(list(submitted=TRUE, platforms=c("devel","release","oldrelease")), '
            f'auto_unbox=TRUE))')
    fn = _WIN_FN.get(platform, "devtools::check_win_devel")
    return _guard("devtools",
        f'{fn}({p}); '
        f'cat(jsonlite::toJSON(list(submitted=TRUE, platform="{platform}"), auto_unbox=TRUE))')
```

**rhub vs win-builder distinction** (must be surfaced in help text):
- `devel|release|oldrelease|all` → CRAN's Windows build servers; results by **email** (~30 min); mandatory pre-submission.
- `rhub` → GitHub Actions CI on your repo; results in **Actions tab**; multi-platform (Linux, macOS, Windows, multiple R versions); requires rhub v2 package + GitHub auth.

The existing `devel: bool` kwarg on `run()` is unrelated (used by the `check`/`lint`
engine for R-devel engine selection) — no naming collision at runtime since `platform`
is only read by the `winbuilder` kind branch.

Envelope normalizer (`lib/rcmd.py:189`) adds `platform`/`platforms` field.

`run_all` (line ~902) calls `run(kind="winbuilder")` without a `platform` kwarg —
the new default propagates automatically, so `r:cran-prep` submits to all three
platforms by default. No explicit kwarg needed in `run_all`.

**Command frontmatter** (`commands/r/winbuilder.md`) gains:
```yaml
- name: --platform
  description: "Target: all (default) = all 3 win-builder platforms; devel|release|oldrelease = single win-builder platform; rhub = rhub v2 GitHub Actions CI (multi-platform, results in Actions tab)"
  required: false
  type: string
  default: all
```

### G2 — `Language:` field lint (`lib/cranlint.py:272`)

Insert after the `date_stale` block, before the `return _envelope(...)` call.
Only fires when `vignettes/` or `man/` directory exists alongside DESCRIPTION —
matching CRAN's actual condition (packages with vignettes or Rd files):

```python
# — Language field —
pkg_dir = desc_path.parent
has_docs = (pkg_dir / "vignettes").is_dir() or (pkg_dir / "man").is_dir()
if has_docs and not fields.get("Language"):
    findings.append({
        "code": "language_missing",
        "severity": "advisory",
        "field": "Language",
        "message": (
            "DESCRIPTION has no Language field — CRAN's incoming feasibility "
            "check flags this for packages with vignettes or Rd files. "
            "Add: Language: en-US"
        ),
    })
```

### G3 — DOI angle-bracket lint (`lib/cranlint.py`)

Scans the `Description` field only — `References` is not a standard DCF field
and silently contains nothing in practice.

```python
_BARE_DOI_RE = re.compile(
    r'(?<![<({])'         # not already inside angle brackets, parens, or curly braces
    r'(?:doi:\s*10\.|https?://(?:dx\.)?doi\.org/10\.)',
    re.I,
)

# In lint_description(), after Description prose check:
desc_text = fields.get("Description", "")
if _BARE_DOI_RE.search(desc_text):
    findings.append({
        "code": "doi_format",
        "severity": "advisory",
        "field": "Description",
        "message": (
            "Description appears to contain a bare DOI or doi.org URL. "
            "CRAN requires angle-bracket format: <doi:10.xxxx/yyyy> or "
            "<https://doi.org/10.xxxx/yyyy>. Bare forms draw a NOTE at --as-cran."
        ),
    })
```

Edge cases: the negative lookbehind `(?<![<({])` avoids flagging already-wrapped
DOIs like `<doi:10.1000/xyz>`, markdown links `(https://doi.org/...)`, and
Rd `\url{https://doi.org/...}` curly-brace form.
False-positive risk is low — advisory only.

### G4 — doi.org 403 classification (`lib/rcmd.py:183`)

Post-process the `broken` list in the urlcheck normalizer to split on `doi.org` + 403:

```python
elif kind == "urlcheck":
    raw_broken = _as_list(raw.get("broken"))
    broken, doi_blocked = [], []
    for item in raw_broken:
        url = str(item.get("url", "") if isinstance(item, dict) else item)
        status = str(item.get("status", "") if isinstance(item, dict) else "")
        if "403" in status and "doi.org" in url:
            doi_blocked.append(item)
        else:
            broken.append(item)
    env["urlcheck"] = {
        "count": len(broken),
        "broken": broken,
        "doi_blocked": doi_blocked,         # advisory: bot-protection 403s
        "doi_blocked_count": len(doi_blocked),
    }
```

**Status logic (normalizer owns all transitions):**
- `broken` non-empty → `status: "error"`
- `broken` empty + `doi_blocked` non-empty → `status: "warn"`
- both empty → `status: "ok"`

The render prompt (`commands/r/urlcheck.md`) reads `doi_blocked_count > 0` and
surfaces: *"N doi.org URLs returned 403 (bot-protection — verify manually;
standard CRAN response: note this in cran-comments.md)."*

**Behavior change:** when only doi.org 403s are present (no real broken URLs), `status`
changes from `"error"` to `"warn"`. Document in CHANGELOG as a behavior change: any
caller that checks `status == "error"` to detect broken URLs should instead check
`len(broken) > 0`.

### G5 — testthat edition detection (`lib/cranlint.py`, new function)

New function `check_test_config(path)` parallel to `lint_description` / `check_build_hygiene`:

```python
def check_test_config(path: str | os.PathLike = ".") -> dict:
    """Advisory check: testthat edition and test infrastructure config.

    Reads Config/testthat/edition from DESCRIPTION. Warns if absent (defaults
    to edition 2 in older testthat versions, where new snapshots on CI fail)
    or explicitly set to '2'.

    Returns envelope {kind: "test_config", status, findings, messages}.
    """
```

Findings:
- `testthat_edition_missing` — `Config/testthat/edition` absent → recommend adding
  `Config/testthat/edition: 3`
- `testthat_edition_outdated` — value is `"2"` → recommend upgrading

**Wire-up — two surfaces:**

1. **`r:cran-prep`** (`run_all` in `lib/rcmd.py`): add `check_test_config` as a new
   `test-config` stage alongside `description`, `build-hygiene`, `docs-consistency`.
   Runs pure-Python (no R), fast and never raises. Skip silently if `tests/testthat/`
   directory does not exist (package has no testthat tests). `commands/r/cran-prep.md`
   frontmatter gains no new flags.

2. **`r:test`** (`commands/r/test.md` prompt): print `check_test_config()` findings
   as a **pre-flight advisory block** before the R test run result — separate from
   the pass/fail count. The prompt instructs Claude to run
   `python3 -m lib.cranlint check_test_config .` before invoking the R test runner,
   capture the JSON envelope, and surface any `findings` as an advisory block. This
   is consistent with how `r:cran-prep` already stages pure-Python cranlint calls
   before R work. Same skip guard: no `tests/testthat/` directory → no advisory block.

**G5 implementation requirement — CLI entrypoint:** `lib/cranlint.py` currently has no
`__main__` entrypoint. The `python3 -m lib.cranlint check_test_config .` call in the
`r:test` prompt requires one. As part of G5, add:

```python
# lib/cranlint.py — end of file
if __name__ == "__main__":
    import sys, json
    subcmd = sys.argv[1] if len(sys.argv) > 1 else "lint"
    path   = sys.argv[2] if len(sys.argv) > 2 else "."
    fn_map = {
        "lint":             lint_description,
        "build-hygiene":    check_build_hygiene,
        "docs-consistency": check_planning_consistency,
        "check_test_config": check_test_config,
    }
    fn = fn_map.get(subcmd)
    if fn is None:
        print(f"Unknown subcommand: {subcmd}", file=sys.stderr); sys.exit(1)
    print(json.dumps(fn(path), indent=2))
```

This mirrors the existing CLI pattern used by `lib/changed.py` and `lib/discovery.py`.
Add one pytest case: `test_cranlint_cli_check_test_config` — invoke via subprocess
`python3 -m lib.cranlint check_test_config .` and assert JSON output parses correctly.

### G6 — `--run-donttest` in `r:check --strict` and `--incoming` (`lib/rcmd.py`)

CRAN's incoming pass always runs `\donttest{}` examples regardless of strictness level;
local `R CMD check --as-cran` skips them. Append `--run-donttest` when either `strict=True`
OR `incoming=True`:

```python
# lib/rcmd.py — check kind snippet
args = ["--as-cran"]
if strict or incoming:
    args.append("--run-donttest")  # CRAN always runs \donttest{}; strict and incoming both mirror this
```

No new envelope keys. No new flags — existing `strict` and `incoming` kwargs are the hooks.
`--strict` alone gets it; `--incoming` alone gets it; both together get it once.

### G7 — `_R_CHECK_*` env vars + versioned registry (`lib/rcmd.py`)

CRAN's incoming machine sets additional `_R_CHECK_*` environment variables beyond those
implied by `--as-cran`. Thread these via `rcmdcheck(env=c(...))` when `incoming=True`.

**Versioned registry** — a new module-level dict tracking which vars each R release adds:

```python
# lib/rcmd.py — new module-level constant
_CRAN_CHECKS_REGISTRY = {
    # vars set by CRAN incoming for all R versions (R Internals §8)
    "base": {
        "_R_CHECK_DEPENDS_ONLY_": "true",       # catches Suggests used without requireNamespace()
        "_R_CHECK_SUGGESTS_ONLY_": "true",      # catches undeclared packages
        "_R_CHECK_S3_REGISTRATION_": "true",    # catches overwritten base S3 methods
    },
    # per-release additions (audit R Internals §8 on each major.minor release)
    "R4.3": {},
    "R4.4": {},
    "R4.5": {},  # update when R 4.5 release notes publish
}
```

In the `incoming=True` snippet, fire **two sequential rcmdcheck passes** — one per
mutually-exclusive env var — and merge findings. `_R_CHECK_DEPENDS_ONLY_` and
`_R_CHECK_SUGGESTS_ONLY_` cannot coexist in a single call (they set conflicting check
flavors); CRAN itself runs them as separate passes:

```python
if incoming:
    r_ver = _r_version_key()   # returns e.g. "R4.5" from R.Version()$minor
    base_env = _CRAN_CHECKS_REGISTRY["base"]
    ver_env  = _CRAN_CHECKS_REGISTRY.get(r_ver, {})

    # Pass 1: _R_CHECK_DEPENDS_ONLY_ — catches Suggests used without requireNamespace()
    # Pass 2: _R_CHECK_SUGGESTS_ONLY_ — catches undeclared packages
    # Pass 3: _R_CHECK_S3_REGISTRATION_ + any version-specific vars (these are safe to combine)
    # Findings from all passes are merged into one envelope with pass-tagged finding codes
```

The implementation fires the passes sequentially inside the R snippet (or as separate
`rcmdcheck` calls) and merges the `notes` / `warnings` / `errors` lists, tagging each
finding with `pass: "depends_only" | "suggests_only" | "s3_registration"` so the user
knows which CRAN flavor surfaced the issue. Total check time ≈ 3× a single pass — this
is always-on for `--incoming` and cannot be bypassed; document explicitly in
`commands/r/check.md` argument description for `--incoming`: *"Runs 3 sequential CRAN
passes; expect 3× check time."*

`_r_version_key()` is a small helper that shells out `Rscript -e 'cat(R.version$major,".",R.version$minor,sep="")'`
and maps to the nearest `R4.X` key. Falls back to `"base"` vars only if Rscript is absent.

**Update protocol** (documented in `CLAUDE.md`): on each R major.minor release, audit
[R Internals §8](https://cran.r-project.org/doc/manuals/r-release/R-ints.html#Tools)
for new `_R_CHECK_*` vars and add to the appropriate version key. Commit with
`chore(rcmd): update _CRAN_CHECKS_REGISTRY for R X.Y`.

### G8 — PDF manual build advisory (`lib/rcmd.py`)

CRAN always builds the PDF reference manual; local checks silently skip it when LaTeX
is absent, giving no warning. Detect the skip in the `check` kind normalizer:

```python
# lib/rcmd.py — check normalizer, after existing NOTE/WARNING/ERROR classification
# IMPORTANT: exact skip strings TBD — implementer must run R CMD check without LaTeX
# installed and capture the actual output before finalizing this regex.
# Candidates (unverified): "skipping PDF manual", "LaTeX not found", "pdflatex not found",
# "PDF version of the manual", "Cannot create PDF manual"
output_text = "\n".join(env.get("messages", []))
if re.search(r"skipping PDF manual|LaTeX not found|pdflatex not found", output_text, re.I):
    env.setdefault("findings", []).append({
        "code": "pdf_manual_skipped",
        "severity": "advisory",
        "message": (
            "PDF reference manual was not built (LaTeX/pdflatex absent). "
            "CRAN always builds the PDF manual — install texlive or tinytex "
            "and re-run `r:check` to confirm no LaTeX errors."
        ),
    })
```

The advisory does not change `status` (PDF build failures are separate from the overall
check result) — it's surfaced as an informational note alongside the check output.

## Dependencies

All new checks are pure-Python (pure stdlib, no R) — G1 extends an R snippet but
the guard (`_guard("devtools", ...)`) already exists. No new engine dependencies.

## Error handling

- **G1:** Unknown `platform` value → `_WIN_FN.get(platform, _WIN_FN["devel"])` falls
  back to `devel` silently (the command layer validates the flag value).
- **G2/G3/G5:** Missing or unparseable DESCRIPTION → `lint_description` and
  `check_test_config` already degrade to `warn` envelope. New findings only add
  to the existing `findings` list — no new raise paths.
- **G4:** `broken` items that are strings (not dicts) are handled by `isinstance`
  guard — they pass through to `broken` unchanged (no doi.org assumption).

## Testing

Both gates must pass: `python3 -m pytest tests/` and `bash tests/test-all.sh`.

### New pytest cases (target: `tests/test_cranlint.py`, `tests/test_rcmd_*.py`)

**G1:**
- `test_winbuilder_platform_release` — `run()` with `platform="release"` emits
  snippet containing `check_win_release`.
- `test_winbuilder_platform_all` — `platform="all"` emits all three function calls
  in one snippet; envelope has `platforms` list.
- `test_winbuilder_default_is_all` — no `platform` kwarg → same as `platform="all"`.
- `test_winbuilder_platform_rhub` — `platform="rhub"` emits snippet using `rhub::rhub_check`;
  guard uses `rhub` engine (not `devtools`); envelope note field says "Results in GitHub Actions tab".

**G2:**
- `test_lint_description_language_missing` — DESCRIPTION without `Language:`, with
  `vignettes/` dir → `language_missing` finding.
- `test_lint_description_language_missing_no_docs_skip` — DESCRIPTION without `Language:`,
  no `vignettes/` or `man/` dirs → **no finding** (gate not triggered).
- `test_lint_description_language_present` — `Language: en-US` with docs dirs → no finding.

**G3:**
- `test_doi_format_bare_doi` — `Description: See doi:10.1000/xyz.` → `doi_format`.
- `test_doi_format_bare_url` — `Description: See https://doi.org/10.1000/xyz.` → `doi_format`.
- `test_doi_format_wrapped_ok` — `<doi:10.1000/xyz>` → no finding.
- `test_doi_format_markdown_link_ok` — `(https://doi.org/10.1000/xyz)` → no finding.
- `test_doi_format_url_curly_ok` — `\url{https://doi.org/10.1000/xyz}` → no finding
  (Rd curly-brace form excluded by `(?<![<({])`  lookbehind).

**G4:**
- `test_urlcheck_doi_403_classified` — broken list with doi.org 403 item →
  `doi_blocked` list non-empty; `broken` list empty; status `warn` not `error`.
- `test_urlcheck_real_404_not_classified` — 404 from doi.org stays in `broken`.
- `test_urlcheck_403_non_doi_not_classified` — 403 from non-doi host stays in `broken`.
- `test_urlcheck_string_items_passthrough` — string items in broken list don't raise.

**G5:**
- `test_check_test_config_missing` — no `Config/testthat/edition` → `testthat_edition_missing`.
- `test_check_test_config_edition2` — `Config/testthat/edition: 2` → `testthat_edition_outdated`.
- `test_check_test_config_edition3` — `Config/testthat/edition: 3` → clean `ok`.
- `test_check_test_config_no_description` → `warn` envelope, no raise.
- `test_cranlint_cli_check_test_config` — invoke via subprocess
  `python3 -m lib.cranlint check_test_config .`; assert output is valid JSON with a
  `kind` key (smoke test for the `__main__` entrypoint).

**G6:**
- `test_check_strict_run_donttest` — `run(kind="check", strict=True)` snippet contains `--run-donttest`.
- `test_check_incoming_run_donttest` — `run(kind="check", incoming=True)` snippet contains `--run-donttest`.
- `test_check_non_strict_no_donttest` — `strict=False, incoming=False` → snippet does NOT contain `--run-donttest`.

**G7:**
- `test_cran_checks_registry_base_keys` — `_CRAN_CHECKS_REGISTRY["base"]` contains the
  three expected keys.
- `test_incoming_fires_sequential_passes` — `run(kind="check", incoming=True)` generates
  snippet(s) that include both `_R_CHECK_DEPENDS_ONLY_` and `_R_CHECK_SUGGESTS_ONLY_`
  in **separate** rcmdcheck calls (not combined in one env dict).
- `test_r_version_key_format` — `_r_version_key()` returns string matching `R\d+\.\d+`.

**G8:**
- `test_pdf_manual_skipped_advisory` — check envelope with "skipping PDF manual" in
  messages → `pdf_manual_skipped` finding in `findings`.
- `test_pdf_manual_present_no_advisory` — messages without skip text → no advisory.

### test-all.sh

No new `test-all.sh` checks required (command count unchanged at 41; no new
commands; `version_sync.py --check` and `_check_commands_doc.py` pass unchanged).
Winbuilder command frontmatter gains one argument — `_check_commands_doc.py` will
catch if `commands.md` lags.

## Documentation impact

- `commands/r/winbuilder.md` — add `--platform` to `arguments:` array and `## Usage`.
- `commands/r/urlcheck.md` — add `doi_blocked_count` rendering logic (doi.org 403 advisory block).
- `commands/r/check.md` — update `--incoming` argument description: *"Runs 3 sequential CRAN check passes (_R_CHECK_DEPENDS_ONLY_, _R_CHECK_SUGGESTS_ONLY_, _R_CHECK_S3_REGISTRATION_); expect ≈3× check time."*
- `docs/commands.md` — update `r:winbuilder` argument table to include `--platform`.
- `docs/reference/cranlint.md` — auto-generated; re-run `scripts/gen_lib_reference.py`.
- `docs/reference/rcmd.md` — auto-generated; re-run `scripts/gen_lib_reference.py`.
- `docs/guides/cran-submission.md` — add a sub-section for win-builder matrix and
  a note on doi.org 403 handling.
- `docs/tutorials/cran-release-prep.md` — mention `Language:` field and DOI format.
- `CLAUDE.md` — add G7 update protocol: "on each R major.minor release, audit R Internals §8
  for new `_R_CHECK_*` vars and update `_CRAN_CHECKS_REGISTRY` in `lib/rcmd.py`."
- `CHANGELOG.md` — `[Unreleased]` section with all 8 gaps.
- `.STATUS` — update to reflect v2.14.0 unreleased bundle.

## Implementation order

All work on `feature/cran-check-gap-fill` (worktree off `dev`):

1. **G2 + G3** — extend `lint_description()` in `lib/cranlint.py`; write pytest cases;
   run `python3 -m pytest tests/test_cranlint.py`.
2. **G5** — add `check_test_config()` to `lib/cranlint.py`; wire into `run_all` in
   `lib/rcmd.py`; write pytest cases.
3. **G4** — extend urlcheck normalizer in `lib/rcmd.py`; write pytest cases.
4. **G1** — extend `_r_snippet` + `run()` for `winbuilder`; update envelope normalizer;
   update `commands/r/winbuilder.md` frontmatter; write pytest cases.
5. **G6** — add `--run-donttest` to strict check snippet; write pytest cases. (Trivial — 3 lines.)
6. **G7** — add `_CRAN_CHECKS_REGISTRY` dict + `_r_version_key()` helper; thread into
   `incoming=True` snippet; write pytest cases.
7. **G8** — add PDF skip detection to check normalizer; write pytest cases.
8. **Doc sweep** — `docs/commands.md`, guides, tutorials, CHANGELOG, `.STATUS`, `CLAUDE.md`.
9. **Auto-gen** — `python3 scripts/gen_lib_reference.py` (cranlint + rcmd reference
   pages will drift until this runs; `test-all.sh` includes `gen_lib_reference.py
   --check` as a gate, so this must run before step 10).
10. **Gates** — `python3 -m pytest tests/` (target ≥435 passing) +
    `bash tests/test-all.sh` (43/43).
11. **PR** — `feature/cran-check-gap-fill → dev`.

## Open questions / risks

- **G3 false-positive rate:** the negative lookbehind on `(` covers markdown links
  but misses RST-style or Rd `\href{https://doi.org/...}{...}`. Rate expected low
  (advisory only — not a blocker). If false-positives appear in practice, add an
  exception for `\href` in the Rd pattern.
- **G4 status field format:** the `status` column from `urlchecker::url_check()` is
  free-text (`"403: Forbidden"`, `"403 Forbidden"`, etc.). The guard `"403" in status`
  is robust to format variation; confirm in a fixture with both forms.
- **G5 scope:** `check_test_config` only checks DESCRIPTION; it doesn't parse
  `tests/testthat.R` or `test/` structure. Sufficient for the edition advisory.
- **G1 `--all` semantics:** all three submissions are async (email) with no
  immediate result. The envelope documents `submitted=True` and `platforms` list;
  the user checks their inbox. No result-polling mechanism is introduced.

## Sources

- [Writing R Extensions — The DESCRIPTION file](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#The-DESCRIPTION-file)
- [CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html)
- [devtools: check_win_devel / check_win_release / check_win_oldrelease](https://devtools.r-lib.org/reference/check_win.html)
- [urlchecker package](https://github.com/r-lib/urlchecker)
- [testthat 3e edition — snapshot testing on CI](https://testthat.r-lib.org/articles/snapshotting.html)
- Issue #46 (this repo) — evidence from live RMediation + medrobust CRAN submission

# SPEC: `/rforge:docs:check` — content audit backed by `lib/docaudit.py` (release A)

- **Status:** Draft v2.1 — revised after a 4-reviewer adversarial pass and a Codex adversarial review (logs at the end). Decisions D1–D5 were locked by the grill; **D0, D6, D7 and the `--site` auto-run decision were confirmed 2026-10-11** (see "Confirmed decisions") · A1 task breakdown: `tasks/plan.md` (vertical slices, harness first)
- **Date:** 2026-10-11
- **Target version:** v2.21.0 (minor: new public module + behavior change to an existing command; **command count stays 44**)
- **Author:** brainstormed with Claude — see `BRAINSTORM-docs-content-skills-2026-10-11.md` and `GRILL-docs-content-skills-2026-10-11.md`
- **Branch plan:** `feature/docs-check-content-audit` off `dev` (created 2026-10-11 at `~/.git-worktrees/rforge/feature-docs-check-content-audit`)

## Summary

Give `/rforge:docs:check` real, deterministic backing. Today it is a prompt-only command that promises "find outdated
examples", "check API contract consistency" and "verify NEWS.md completeness" with nothing behind it. This spec adds
`lib/docaudit.py` (pure-stdlib; R only for the opt-in `--run-examples`, network only for the opt-in `--site`) and rewrites
`docs:check` to delegate to it. It is honest about what it can and cannot find: measured against medfit's 18 real defects
the rules as specified fire on **3 firmly and 3 conditionally** (table below), so the command is positioned as a
*candidate generator with a few near-certain checks*, not a stale-docs oracle. Release B (cookbook builder, article
authoring, skills) is parked and only referenced.

## Motivation — measured, not asserted

medfit ran five doc audits by hand on 2026-10-10 (`.STATUS`: `readme_audit`, `stale_content_check`, `docs_audit`,
`scannability_audit`, `website_review`). The reviewer replayed **all 18 defects** against the rules in this spec using the
pre-fix commits:

| Defect (pre-fix ref) | Check | Fires? |
|---|---|---|
| Refcard `joint_effects(x, theta)` (`17d976d^`) | `signature-names` | **Yes** |
| Extraction: "Next Steps" before 2 later sections (`8bd8987^`) | `scannability` | **Yes** |
| `/articles/models.html` absent from the live site | `site-missing-page` | **Yes**, but only when source ref = deploy ref (see `--site`) |
| README `NIE = 0.19` vs real `0.164` (`b1f307b^:151`) | `examples-output` | Conditional: needs block-state sharing (blocks reuse `mydata` from an earlier block) |
| 113–124 word paragraphs (`8bd8987^`) | `scannability` | Conditional on a defined threshold (now defined) |
| `methods.qmd` H3 count 1 (`8bd8987^`) | `scannability` | Conditional on a defined threshold |
| Getting Started lacked cluster/native engines (G1, G3) | — | **No** — engines are `engine =` argument values, not exports; v1 `coverage` does not enumerate them |
| `?extract_mediation` omits `SEMFit`, names `brms` (G2) | — | No — S3 methods and Rd prose |
| `SEMFit` Rd files have no examples (G4) | — | No — no missing-examples check |
| "a seventh class"; ecosystem list omits probmed/medrobust; "1,900+ tests" | — | No — prose claims (D1) |
| README feature lists omit `lmer`/`SEMFit` | — | No |
| No route chooser on `extraction.qmd` | — | No — not definable as a check |
| HC3 offered as survey-weight inference; CRAN install listed first | — | No — semantic/prose |
| Cookbook recipes reuse `fit_m` from an earlier recipe | — | No — Quarto chunks carry no `#>` output; needs release B's isolated-recipe harness |

**Honest claim:** 3 firm + 3 conditional of 18 (≈17–33% recall); of the 7 classes in the brainstorm, 2 firm (signature,
site) and 2 conditional (examples, scannability). `coverage` fires on none of the 18 and is a *report*, not a detector.
The value of the signature check is regression-catching: a 120-commit replay (60 each, medfit/medrobust/probmed) checked
**20,468 named arguments and found 5 hits, all real defects** (medfit `b40444e` `BootstrapResult(converged = TRUE)`;
medrobust `96d97b4` `check_compatibility(sn0=, sp0=, psi_sn=, psi_sp=)` vs formal `psi`), with 0 false positives at HEAD
across 337 named args.

## Scope

### In scope (decisions)

| ID | Decision | Source |
|---|---|---|
| D0 | **Scope resolution** (refined after review): walk up from the cwd to the nearest `DESCRIPTION` → audit that package. No `DESCRIPTION` found: sweep the ecosystem **only if** a `.rforge.yaml` manifest exists or `--eco` is passed; otherwise print "not inside an R package — pass a package path or `--eco`" and exit 0. `[package]` or `--eco` override. A `kind: hybrid` root declared in `.rforge.yaml` audits the root package **and** nested packages. The resolved scope is the **first line of output** | open Q1 + review |
| D1 | Prose-count/ordinal claims ("a seventh class") are out of v1 | grill 1 |
| D2 | No separate impact module: `--since <tag>` restricts the coverage report | grill 2 |
| D3 | Rewrite `docs:check`; no new `docs:audit` | grill 3 |
| D4 | Stale-site detection compares source-implied pages with the live `sitemap.xml` (opt-in `--site`); **expected pages derive from the deploy ref, not the working tree** (review) | grill 4 + review |
| D5 | Acceptance = known-answer fixtures + hold-out triage, **strengthened** with a recall replay, planted defects and explicit release-blocking criteria (review) | grill 5 + review |
| D6 | **`--run-examples` and `--site` ship as a follow-on (A2), not in A1** — see below | review (new) |
| D7 | `signature-named-arg` stays `error`; the check is **demoted to `warn` before release if the hold-out or replay shows any `error`-severity false positive** | review (new) |

### Release split (D6, confirmed 2026-10-11)

| Release | Contents | Why |
|---|---|---|
| **A1 (v2.21.0)** | `lib/docaudit.py` static checks (`signature-named-arg`, `signature-names`, `signature-arity`, `coverage`, `scannability`), the `docs:check` rewrite, `--since`, `docs.allowlist`, all mechanical gates | Static, deterministic, no R, no network; the precision-critical logic can be reviewed on its own |
| **A2 (v2.22.0)** | `--run-examples` (needs `pkgload`, session semantics, normalization) and `--site` (needs deploy-ref derivation, smoke test) | Both contracts had BLOCKER/IMPORTANT holes in review; each adds a dependency class (R, network) and a smoke-test obligation |

This reverses nothing in the grill — D4 and the examples check still ship — but moves them one release later. The
contracts below are written in full for both releases.

### Out of scope

- Prose-count/ordinal and semantic claims; engine enumeration for `coverage` (an `engine =` value list parsed from Rd
  `\arguments` is feasible but fuzzy — deferred, listed in Open questions)
- Cookbook builder, article authoring, skills, prose-literal lint (release B; grill decisions 6–8 stand)
- Any write: the audit is read-only; suggestions never say "edit `man/*.Rd`" (the PreToolUse hook blocks it) — they say
  "run `document()`"
- Cross-package API-contract consistency; NEWS.md completeness (see Dropped promises)

### Dropped promises of the old `docs:check` (must be listed in the CHANGELOG behavior-change text)

The old command promised and **the rewrite no longer provides**: NEWS.md completeness; API-contract consistency across
packages ("probmed expects old signature"); outdated/broken examples *by default* (now opt-in `--run-examples`, only for
blocks carrying `#>` output); vignette cross-references. NEWS **header** currency stays with `r:tidy`
(`lib/tidyaudit.parse_news_header`). Eight docs currently assert the old meaning of a clean `docs:check` and are listed
under Documentation impact.

## Duplicate & overlap audit

| Existing | Overlap | Resolution |
|---|---|---|
| `/rforge:docs:check` | Same name and promises, no backing | **Rewritten** (D3); keeps `name: rforge:docs:check` (rename stubs assert it) |
| `r:site` (`--strict`, `--check-leaks`) | Build health, stray-file leak guard | Different axis; no shared checks |
| `lib/sitelint.py`, `lib/tidyaudit.py` | Leak scan; NEWS header | Reuse the envelope shape and allowlist approach; NEWS stays in `r:tidy` |
| `pkgdown::check_pkgdown()` | Export missing from the reference index fails it | Not rebuilt (`r:site --strict` runs it) |
| `r:urlcheck`, `r:spell` | Links, spelling | Unrelated |

## Architecture

### `lib/docaudit.py` (new public module)

```python
audit(path=".", *, since=None, run_examples=False, site=None, ref=None) -> dict   # one package
audit_ecosystem(path=".", **same) -> dict                                          # per-package envelopes + roll-up
format_text(env) -> str
format_json(env) -> str
```

CLI: `python3 -m lib.docaudit [--path P] [--eco] [--since TAG] [--run-examples] [--site URL] [--ref REF]
[--format json|text] [--fail-on none|warn|error]`.

**Envelope** (house shape: `{kind, status, findings, messages, engine_missing}`, `kind: "docs-audit"`) plus
`max_severity`. Findings: `{tier, check, severity, file, line, message, evidence}`, `severity ∈ {error, warn, info}`.

- **Status:** `warn` whenever any `error` or `warn` finding exists, else `ok`; never `blocked`, never raises. Orchestrator
  readers use `max_severity` to see an `error` inside a `warn` envelope.
- **Severity vocabulary is a deliberate departure** from the house `advisory`-only findings (`sitelint`, `s7review`):
  `--fail-on` needs a threshold, which a single `advisory` level cannot give.
- **`--fail-on` (default `none`) sets only the CLI exit code** (1 when a finding at or above the level exists). It is a
  third meaning alongside `lib.rcmd`'s `introduced|none` (which flips `status`) and the always-0 advisory CLIs; the
  SPEC does not claim `rcmd` precedent.
- Summary line always printed: `checked N of M exported functions` with the unchecked ones named by reason
  (`no-usage`, `method`, `re-export`), plus counts by severity; `info` findings are hidden by default (counts shown),
  shown with `--detailed`.

### Parsing rules (all checks share these)

- **Ground truth:** `\usage{}` of `man/*.Rd`, **restricted to `NAMESPACE` exports** (handle `export(a, b)` comma lists;
  `exportPattern` is unresolvable → message). Normalize `\dots`/`\ldots` → `...`. `\method{}`/`\S4method{}` usage is not
  parsed in v1 (recorded as unchecked, reason `method`); S3 generics expose only the generic's formals.
- **Argument splitting blanks comments and string contents first** (otherwise `# use b = 2, c = 3` yields fake names and
  a leading `#` comment drops the next argument — the prototype had this bug: medfit named args are **47, not 30**).
- **Doc surface:** `README.md`, `README.qmd`/`README.Rmd` (probmed generates `README.md` from `README.qmd`),
  `vignettes/**/*.{qmd,Rmd}`. Fenced blocks are scanned only when labeled `r` or unlabeled (a plantuml fence contains
  `+sensitivity_region()`).
- Partial matching: a named arg that is a **unique prefix of a formal before `...`** is valid R and not flagged.

### Checks

| Tier | Check ID | Severity | Rule |
|---|---|---|---|
| B | `signature-named-arg` | error (D7) | Named arg `f(arg = …)` not among the formals, for an exported function **without `...`** in its formals |
| B | `signature-names` (was `signature-listing`) | warn | For an exported function **without `...`**, a bare-identifier argument in a backticked `fn(…)` span that is **the whole first cell of a Markdown table row** (a signature column, as in a reference card) and is not a formal. **Narrowed 2026-10-11 (hold-out triage, option A):** the original "any backticked span outside fences" rule flagged call examples such as medfit's `` `fit_sem(syntax, data)` `` in a Routes cell, where `syntax` is a variable (the same cell has `fit_mediation(model = syntax, …)`). Spans elsewhere are call examples and are not judged; `signature-named-arg` and `signature-arity` still cover every call. It still cannot tell a stale name from a placeholder *within* a signature column, so it is a candidate generator |
| B | `signature-arity` | warn | Positional args exceed the formals (e.g. `joint_effects(object, estimates, "bca")`); **only for functions with no `...` formal** — a variadic `f(x, ...)` accepts `f(1, 2, 3)`, so it is exempt, like the other two signature checks (positive control in the fixtures). The "ordered subset" rule of v1 of this SPEC is **dropped**: 18 of 645 real calls (2.8%) list named args out of formal order |
| C | `coverage` | info (warn if an export appears in no doc) | Export × doc matrix, a *report*, not a defect detector; `--since TAG` restricts it to exports/Rd files added since the tag (`git diff --name-status TAG..HEAD` on `NAMESPACE` and `man/`). **No engine enumeration in v1** |
| D | `scannability` | info | Defaults (all configurable): paragraph over **110 words**; H2 section over **800 words with fewer than 3 H3**; "Next Steps" not last. Known: medfit `methods.qmd` (6 paragraphs over 100 words, max 217) is flagged forever — allowlist it |
| B (A2) | `examples-output` | error (D7) | See `--run-examples` contract |
| B (A2) | `examples-error`, `examples-shape` | warn | See contract |
| A (A2) | `site-missing-page` | warn / info | See `--site` contract |

**Known blind spots (stated, not fixed):** reordered pair `joint_effects(estimates, object)`; wrong default value;
`nie(x, type = "direct")` after `type` is removed (S3 methods' formals are invisible behind the generic `nie(x, ...)`) —
the largest blind spot; `\method{}` functions (25% of medfit's usage blocks) are unchecked.

**Calibration prototype (corrected):** the first prototype silently exempted functions with `...` (the SPEC text had no
such exemption); run literally, `signature-names` flags **4 of 12** rows on the *fixed* medfit refcard
(`refcard.qmd:97-100`, `bootstrap_mediation(f, "parametric", …)` — `f` is a placeholder for `statistic_fn`). The rule now
states the `...` exemption. Functions with `...` are 11 of 22 medfit exports (medrobust 1 of 23; probmed 7 of 22), so
yield depends heavily on the package. With the exemption: refcard `17d976d^` → 12 rows, 1 flagged; `17d976d` → 0.

### `--run-examples` contract (A2)

Scans `README.md`, `README.qmd`/`README.Rmd`. Counts at review time: medfit README 8 `r` blocks / 3 with `#>`; probmed
README.md 10 / 1; probmed README.qmd 11 / 2; medrobust README 6 / 0.

- **Execution model (fixes a BLOCKER):** run **all `r` blocks of one file in order in one fresh session** (blocks share
  state: medfit's `tidy()` and bootstrap blocks need `result`/`mydata` from the first block). Auto-skip blocks that call
  `install.packages`, `pak::`, `remotes::` or `devtools::install`. Load the working tree with
  `pkgload::load_all(<path>)` — `library(pkg)` resolves to the *installed* copy (on 2026-10-10 the installed medfit was
  0.4.0 against 0.7.0 docs, giving spurious failures). Per-block timeout (the bootstrap block runs `n_boot = 1000`).
  An upstream failure is attributed **once**, not once per downstream block.
- **No `knitr`:** README.md has static output and no chunks, so `knitr::knit` does nothing. The R side extracts the
  fences and evaluates them (`evaluate`), then compares to the pasted lines. Shipped as `lib/r/docexamples.R`
  (the `lib/r/*.R` convention); no Rscript/`pkgload`/`evaluate` → `engine_missing`, never raises.
- **What counts as documented output:** lines matching `^#>` at line start only (a `.qmd` setup chunk's
  `comment = "#>"` must not match); skip chunks with `include: false`/`eval: false`. Compare per expression, with the
  documented lines as a prefix/subsequence of the actual output (probmed's `print(result)` is documented, the following
  `summary(result)` is not).
- **Comparison:** normalize whitespace (`quick()` prints `0.164  [` with a double space); numbers compared by ±1 unit in
  the last documented digit; `<`/`>` tokens are inequality assertions (`p < 0.001`); scientific notation compared by
  significant digits; a token-count mismatch (`1,234` vs `1234`, `NA`) emits `examples-shape` (warn), not `error`; force
  UTF-8 and `options(width = 80)`. Verified on the real defect: `NIE = 0.19 [0.08, 0.32] | NDE = 0.16 | PM = 55%` flags
  5 of 5 tokens, the fixed block 0.
- **Randomness:** a block with `#>` output and RNG calls (`rnorm`, `runif`, `sample`, `rbinom`) but no earlier
  `set.seed`/`seed=` is downgraded to `info` (cannot match reliably).
- **Skip marker**, three syntaxes, documented in the command file: `# docs-check: skip` inside the block,
  `<!-- docs-check: skip -->` before the fence, `#| docs-check: skip` in a `.qmd` chunk.
- Executes package code: same posture as `r:test`/`r:check`; **recommend-only** for the orchestrator.

### `--site` contract (A2)

`urllib` only, short timeout, one GET of `<url>/sitemap.xml`; unreachable/malformed → `warn` envelope (as
`lib.runiverse`). Base URLs normalized by path (probmed has no trailing slash, medrobust does).

- **Expected pages derive from the deploy ref** (default `main`, or the ref in `.github/workflows/pkgdown.yaml`'s push
  trigger) via `git ls-tree`, **not the working tree**; `--ref` selects another. Measured: from the working tree, probmed
  had 12 of 36 expected pages absent (33%) because its workflow deploys only from `main` while the checkout is ahead.
  From `main`: 57 expected, 0 absent.
- **Severity:** `warn` when the deploy ref is the source; `info` ("N pages on `<ref>` not deployed") when the checkout
  is ahead of the deploy ref. This is honest about the original medfit incident: `models.qmd` landed on dev, the live
  site was the `main` build, and **19 pages were absent by design**. The rule fires on that state, so what it reports
  there is a count of unreleased docs, not a defect.
- Derivation: `articles/<name>.html` from `vignettes/**/*.{qmd,Rmd}`; `reference/<rd-file-name>.html` from `man/*.Rd`
  (the file name is correct, e.g. `tidy.S7_object`). **Do not exclude `\keyword{internal}`** — pkgdown builds those
  pages (medrobust: 26, probmed: 31 `dot-*`). Never expect generated pages (`index`, `404`, `authors`, `news/index`,
  `articles/index`). Report the reverse direction (live but not expected, e.g. probmed's `CLAUDE.html`) as `info`.
- Read-only GET. Follows the `lib.runiverse` precedent (a network *read* the orchestrator already auto-runs).

### Config

`.rforge.yaml` optional `docs.allowlist` block list, entries `<relpath>` or `<relpath>::<check-id>`, read from the
**package root**. The hand-rolled parser (`discovery._read_site_allowlist`, `lib/discovery.py:308-394`, a state machine
hard-wired to `site:`/`allowlist:`) is generalized to take a section name, with `_read_site_allowlist` kept as a thin
wrapper. It has only indirect tests (`tests/test_sitelint.py:192-258`, `tests/test_rcmd_deploy.py`), so **direct unit
tests land first**, as the first implementation step. A top-level `docs:` key does not collide (`in_site` resets at
indent 0). Malformed → ignore + message.

### `commands/docs/check.md` (rewrite; prompt-command delegating to the module)

Frontmatter `arguments:` — **hyphenated names**, because `tests/_check_commands_doc.py` requires `--<name>` literally in
the command's `docs/commands.md` section, with `(?![\w-])` (`run_examples` would demand the text `--run_examples`):

| Argument | Type | Notes |
|---|---|---|
| `package` | string | Positional (in `POSITIONAL_NAMES`); path or name; omitted → D0 |
| `detailed` | boolean | **Kept**; meaning narrows to "print every finding with evidence, including `info`" |
| `eco` | boolean | Force the ecosystem sweep |
| `since` | string | Tag/ref for the coverage restriction |
| `run-examples` | boolean | A2: execute `#>` blocks |
| `site` | string | A2: live site URL |
| `ref` | string | A2: deploy ref for `--site` |
| `fail-on` | string | `none` (default) \| `warn` \| `error` |

**Behavior change (CHANGELOG):** improvised prompt → deterministic checks; the dropped promises above; `--detailed`
narrows; the scope with no argument is now D0 (the package you are in, not the whole ecosystem).

**Orchestrator and safety.** The orchestrator has no per-flag classification: `SAFE_AUTORUN`
(`tests/_check_agent_engines.py:23`) covers only `lib.rcmd --kind` values, and the three agent guards are the MCP-ref
grep, the frontmatter check and the engines/modules/recipes parse. Required: a `docs-audit` row in the orchestrator's
read-only recipe table (default invocation only); a prohibition line naming `--run-examples` (the guard exempts lines
containing "never"/"recommend-only", `_is_prohibition`); a positive assertion in `_check_agent_engines.py` copied from
the deploy-only one (`:100-115`). `--site` follows the `runiverse` precedent (`agents/orchestrator.md:69-71`); the
existing Step 3 wording ("network → recommend") contradicts that precedent and is reconciled in the same change.

## Testing

CI has no medfit checkout, so **committed fixtures are the CI evidence**; real-repo runs are a manual pre-release gate.

| Tier | Coverage |
|---|---|
| unit (`tests/test_docaudit.py`) | Rd `\usage{}` parse (defaults, multiline, `\dots`, backticked names); `NAMESPACE` comma lists; comment/string blanking (both reviewer toy cases); named-arg rule skips `...` functions; unique-prefix partial matching; arity; `signature-names` on any backticked span (table cell, list item, heading, prose) but not in a plantuml fence; placeholder `f` on a `...` function not flagged; `--since`; unchecked-reason accounting; `docs.allowlist` (incl. malformed, package-root); envelope + `max_severity`; D0 resolution (subdirectory walk-up, hybrid, one-package ecosystem root) |
| unit (A2) | normalization table: `p < 0.001`, `2.2e-16`, `1e-04` vs `0.0001`, `1,234`, `NA`, doc `0.164` vs actual `0.1648`, `55%` vs `36 %`; `^#>` only (setup-chunk `comment = "#>"` ignored); RNG-without-seed → info; skip markers (3 syntaxes); session-ordered execution and single attribution of an upstream failure; install-block skip; site derivation from `git ls-tree`, trailing-slash normalization, no expectation for generated pages, internal topics included, reverse direction |
| fixtures (`tests/fixtures/docaudit/`) | Committed excerpts with a provenance README: `17d976d^` refcard table + `joint_effects.Rd` usage (defect), `17d976d` (clean), a README block with `NIE = 0.19`. **Rd fixtures are created via Bash or `git show`** — `.claude-plugin/hooks/pretooluse.py:89-91` blocks Write/Edit on any `man/*.Rd`. Pattern: committed fixtures copied into `tmp_path` per test (as `s7review` reads `tests/fixtures/*`), not the inline-built package of `test_restore_finish_e2e.py` |
| e2e (`tests/test_docaudit_e2e.py`) | Real `python3 -m lib.docaudit` subprocess on the fixture package: defect → `signature-names`; clean → 0 `error`; **planted defect** (a synthetic wrong named arg) caught — the control that proves the check can fail |
| dependency (A2) | `--site` offline/malformed → `warn`; `--run-examples` without Rscript or `pkgload` → `engine_missing`; with R present (skipped otherwise) the `0.19`-vs-`0.164` block is flagged and a matching block is not |
| dogfood | `tests/_check_commands_doc.py` covers every hyphenated flag (the SPEC does **not** claim a generic frontmatter-vs-Usage gate — none exists; `scaffold_args_usage_sync` is hard-coded to 5 `use-*` files); CLI smoke of `python3 -m lib.docaudit`; `lib/r/docexamples.R` parse-check (A2, R-optional; fold into `lib_s7runtime_r_ships` or count it); `AGENTS.md` mirror |
| local-only | `pytest.mark.skipif` unless `RFORGE_MEDFIT_PATH` is set: the known-answer pair against real history via `git show` (never writes to medfit) |
| harness (`tests/harness/`) | Dev-only replay harness (plan tasks T2-T4): committed defect manifest `tests/fixtures/docaudit/defects.json` (the 18 real medfit defects; `firm` rows are regression-locked), a read-only `git archive` recall runner printing "caught k of n", a planted-defect injector on a `copytree` of the clean fixture, and a history replayer. A mutation self-test (audit stubbed to find nothing) must turn firm rows red. CI-safe part uses committed fixtures; real-history rows are `skipif`-guarded on `RFORGE_MEDFIT_PATH` / `RFORGE_PROBMED_PATH` / `RFORGE_MEDROBUST_PATH` |

**Check count:** `test-all.sh` is 45 `run` checks today. New `run` lines: the CLI smoke (+1) and, if not folded, the R
parse (+1) → state the exact number in the PR. The count is hard-coded in `CLAUDE.md:136`, `AGENTS.md:137` **and
`docs/contributing.md:94`**. `lib_pytest` (`test-all.sh` ~424) runs only 4 named test files; add `test_docaudit.py` to
that list or the new tests run only under CI's `pytest tests/`.

Command run before the PR: `python3 -m pytest tests/` and `bash tests/test-all.sh` from the worktree, in a Python ≥3.10
environment with pytest, pyyaml and mkdocs-material.

## Acceptance (D5, strengthened)

Evidence for items 2-4 is produced by the replay harness (`tests/harness/replay.py`, manifest `tests/fixtures/docaudit/defects.json`); see `tasks/plan.md` T2-T4 and Checkpoint B.

All of these before the A1 release PR (and again for A2's checks):

1. **Known-answer fixtures green**, including the planted-defect control.
2. **History replay:** run the named-arg and arity checks over ≥60 commits each of medfit, medrobust and probmed
   (read-only, via `git show`); record hits and triage each. (The review's replay: 20,468 args, 5 hits, all real.)
3. **Recall replay:** re-run the 18-defect table above against the implementation and state **"caught k of n"**; it must
   match the claim in Motivation. The claim is scoped by owner: each manifest row carries `check` and `release` (A1|A2).
   Checkpoint B gates the rows owned by the `signature-*` checks; A1's release gate is every `release: A1` row
   (adds `scannability`); `release: A2` rows (`site-missing-page`, examples) stay `pending`, are listed but not counted, and
   gate only A2. A row cannot block a release that does not ship its check.
4. **Planted defects in a scratch copy** of the hold-out docs (copied to the scratchpad — never edited in place),
   because the hold-out is likely vacuous for `signature-names`: probmed and medrobust README function tables list
   `fn()` with no arguments.
5. **Hold-out triage** on current probmed (63 Rd files) and medrobust (55): the maintainer triages every finding as
   true / false / won't-fix; precision recorded in the appendix.
6. **Smoke tests** (A2): `docs:check --site https://data-wise.github.io/medfit/` and `--run-examples` against a real
   package with R — mocks validate intent, not integration.

**Release is blocked by:** any red fixture or missed planted defect; any raised exception; any unresolved
false-positive class; a failed smoke test; **any `error`-severity false positive on the hold-out or replay** (that check
is demoted to `warn` before release, D7). No numeric precision threshold (the sample is too small to threshold on).

## Documentation impact

Scored with craft's doc-impact rubric (cheap ≥3, heavy ≥5 or new user-facing surface); inputs: 1 new module, config
change, flags on an existing command, no new command/surface.

- [x] Guide — extend the relevant `docs/guides/*` page; Refcard — flags; Demo — audit on the defect fixture
- [x] **Mechanical gates for a new public module** (the "auto-generated" page does not exist without these):
  `scripts/gen_lib_reference.py:36` `MODULES` list; `mkdocs.yml` nav (~line 152, beside `sitelint`/`tidyaudit`) —
  an orphan `docs/reference/docaudit.md` fails `mkdocs_no_orphan_pages` (`test-all.sh:665`) and CI `--strict`;
  `docs/lib-modules.md` (header line 4 + a row near line 51); `tests/cli/automated-tests.sh:108` `PUBLIC_MODULES`;
  `CLAUDE.md:101` list → `AGENTS.md` mirror (copy, then `version_sync.py --check`)
- [x] `docs/commands.md` (every flag, hyphenated; section `:490-515` "Validates" list) and CHANGELOG `[Unreleased]` with
  the behavior-change text and the dropped promises
- [x] **Docs that assert the old meaning of a clean `docs:check`** — `docs/command-cards.md:86`; `docs/REFCARD.md:41,380`;
  `docs/quickstart.md:357`; `docs/architecture.md:226,257,273,281`; `docs/workflows/index.md:137`;
  `docs/tutorials/cran-release-prep.md:7,28,48,259`; `docs/tutorials/rforge-in-the-r-lifecycle.md:63`;
  `commands/complete.md:127`; `.claude-plugin/skills/validation/description-sync.md:112`
- [x] `docs/configuration.md:132` claims `docs:check` warns on `claude_md_budget`; `grep` finds no backing in `lib` or
  `commands` — **remove the claim** (it was already unbacked)
- N/A Mermaid, Tutorial, Cookbook, Architecture note — below threshold

Not needed: `package.json` `files` (already ships all of `lib/`), `version_sync.py` (count stays 44), the rename stubs
(they assert only `name: rforge:docs:check` plus stub text — keep `name:` intact).

## Implementation order (revised)

*Superseded for execution by `tasks/plan.md`, which re-slices these steps into vertical tasks and builds the replay harness first. The list below stays the reference for what each step contains.*

1. **`discovery` allowlist refactor alone** — direct unit tests first, then generalize; ships shipped code, so it gets
   its own commit and review
2. Parsers (Rd `\usage`, `NAMESPACE`, doc surface, comment/string blanking) + unit tests
3. `signature-named-arg`, `signature-names`, `signature-arity` + fixtures + e2e planted-defect control
4. **Adversarial review #2 on the signature logic** (precision-critical), then **history replay, recall replay and
   hold-out triage** (acceptance 2–5) — before any further build, so a forced fix cannot invalidate later work
5. `coverage` (+ `--since`) and `scannability`
6. CLI, envelope, `max_severity`, summary line, `--fail-on`, formatters, D0 scope resolution, `audit_ecosystem`
7. `commands/docs/check.md` rewrite + `commands.md` + orchestrator row/prohibition/assertion
8. Mechanical gates and docs (Documentation impact) — after the review, not before
9. A1 release: version sync, tap manifest sync, CI verify on `main`
10. **A2:** `--site` (+ smoke test right after) then `--run-examples` + `lib/r/docexamples.R` + dependency tests; review
    and release

## Confirmed decisions (2026-10-11, grill confirmation round — see ledger C1-C4)

1. **D0** — confirmed as refined: walk up to `DESCRIPTION`; manifest-or-`--eco` for sweeps; hybrid audits nested too;
   resolved scope is the first output line. The CHANGELOG states the change from "ecosystem-wide by default".
2. **D6** — confirmed: A1 (v2.21.0) static checks + rewrite; A2 (v2.22.0) `--site` then `--run-examples`.
3. **D7** — confirmed: `signature-named-arg` is `error`, auto-demoted to `warn` on any `error`-severity false positive.
4. **`--site` orchestrator auto-run** — confirmed: auto-run, read-only, per the `lib.runiverse` precedent; Step 3
   wording reconciled to "network writes -> recommend". `--run-examples` stays recommend-only.

## Open questions / risks

1. `engine` enumeration for `coverage` (parse `\item{engine}` value lists from Rd `\arguments`) — deferred; the G1/G3
   defects need it.
2. A static Tier-4 `docs-audit` stage in `r:cran-prep` (as `site-leaks`) so the audit gates something — pre-mortem
   suggests it; out of A1.
3. S4/S7 `\method{}` coverage (25% of medfit's usage blocks unchecked) and the invisible-method-formals blind spot.
4. Subfolder `.qmd` naming under `vignettes/` and whether pkgdown scans it recursively — unverified (speculation).
5. Pre-mortem causes (3 months out, nobody uses it): `info` noise (mitigated: hidden by default, counts shown);
   gates nothing (open question 2); `--run-examples` skew/timeouts (mitigated: `pkgload`, timeout); low yield on
   `...`-heavy packages (mitigated: the "checked N of M" line); wrong scope or "ok" read as "NEWS fine" (mitigated: D0
   first line, dropped-promises list).
6. Hold-out scheduling needs a triage session with the maintainer.

## Adversarial review log (2026-10-11, 4 reviewers, read-only on medfit/probmed/medrobust)

| # | Reviewer | Severity | Finding | Resolution in v2 |
|---|---|---|---|---|
| 1 | signature | BLOCKER | `signature-listing` text ≠ prototype (silent `...` exemption); literal rule flags 4 of 12 fixed refcard rows | Exemption stated; check renamed `signature-names`; calibration corrected |
| 2 | signature | IMPORTANT | Splitter ignores comments/strings (47 named args, not 30) | Blanking rule + unit tests |
| 3 | signature | IMPORTANT | Context rule catches ~33 of 293 call-shaped spans | Any backticked span outside fences |
| 4 | signature | IMPORTANT | "Ordered subset" unimplemented and wrong (2.8% out of order) | Dropped; arity check added |
| 5 | signature | IMPORTANT | Unchecked exports silent (no-usage, method, re-export) | "checked N of M" line with reasons; restrict to exports |
| 6 | signature | MINOR | Reorder/wrong-default/arity/removed-arg misses; `\dots`; partial matching; `exportPattern` | Arity added; rest normalized or listed as blind spots |
| 7 | examples/site | BLOCKER | No block-state sharing; independent runs raise false `examples-error` | File-ordered single session, install-skip, single attribution |
| 8 | examples/site | IMPORTANT | "knitr on README.md" incoherent; `#>` substring match; granularity | `evaluate` mechanism, `^#>`, per-expression subsequence |
| 9 | examples/site | IMPORTANT | Rounding rule fails on `<0.001`, sci notation, `1,234`, `NA`, truncated docs, locale | Normalization table, `examples-shape` warn |
| 10 | examples/site | IMPORTANT | Unseeded RNG; skip marker undiscoverable | RNG → info; 3 skip syntaxes documented |
| 11 | examples/site | IMPORTANT | Site FP: 12 of 133 expected pages (probmed 33%) from the working tree | Derive from the deploy ref via `git ls-tree` |
| 12 | examples/site | IMPORTANT | The 404 incident equals intended dev-ahead state (19 pages by design) | Severity by ref; reports a count; honest wording |
| 13 | examples/site | MINOR | `\keyword{internal}` exclusion wrong; generated pages; trailing slash | Exclusion dropped; rules added |
| 14 | repo | BLOCKER | Underscore arg names break the `commands.md` gate | Hyphenated names |
| 15 | repo | BLOCKER | New public module omits `MODULES`, nav, `lib-modules.md`, `PUBLIC_MODULES`, `CLAUDE.md` list | Added to Documentation impact |
| 16 | repo | BLOCKER | "+1 → 46" wrong; no generic frontmatter gate; count hard-coded in 3 places; `lib_pytest` runs 4 files | Exact-count rule; claim removed; `contributing.md` added |
| 17 | repo | IMPORTANT | No per-flag orchestrator classification | Row + prohibition + positive assertion specified |
| 18 | repo | IMPORTANT | `--fail-on` a third meaning; severity vocabulary diverges; `error` in `warn` envelope | Defined explicitly; `max_severity` added |
| 19 | repo | IMPORTANT | Behavior-change list drops old promises; 9 docs assert the old meaning; `claude_md_budget` unbacked | Dropped-promises list; docs listed; claim removed |
| 20 | repo | IMPORTANT | Allowlist refactor has only indirect tests; root unspecified | Direct tests first; package root |
| 21 | repo | MINOR | Rd fixtures blocked by the PreToolUse hook; fixture pattern mixed; `Kind` single for 0–1 packages | Bash/`git show` note; pattern chosen; D0 rule |
| 22 | coverage | BLOCKER | "4 of 7" overstated; engines undefined; `coverage` fires on nothing | Measured table; "3 firm + 3 conditional of 18"; engines out of v1 |
| 23 | coverage | IMPORTANT | Scannability thresholds undefined (methods.qmd flagged forever) | Defaults defined, `info`, allowlist |
| 24 | coverage | IMPORTANT | D5 a rubber stamp; hold-out vacuous | History + recall replay, planted defects, blocking criteria |
| 25 | coverage | IMPORTANT | D0 surprises (subdirectory, `active/`, hybrid) | Refined D0 |
| 26 | coverage | MINOR | Ordering and size | Revised order; A1/A2 split proposed |

### Review 3 — Codex adversarial review (2026-10-11)

Run against the SPEC and `tasks/plan.md`; verdict `needs-attention`, three findings.

| # | Area | Severity | Finding | Resolution |
|---|---|---|---|---|
| 27 | acceptance | HIGH | The 3-firm recall gate includes `scannability` (built after Checkpoint B) and `site-missing-page` (A2), so it could never pass at B or for A1 | Manifest rows carry `check` + `release`; `replay.py recall --scope signature\|a1\|all`; B gates signature rows, A1 gates `release: A1` rows, A2 rows stay `pending` and are not counted |
| 28 | signature | MEDIUM | `signature-arity` lacked the `...` exemption its siblings have, so `f(x, ...)` called as `f(1, 2, 3)` would be flagged | Exempt functions with `...`; variadic positive control in the fixtures |
| 30 | signature | MEDIUM | (Codex #3, F1) Per-argument partial matching rejected valid R calls | R matching order: exact first, then unique partial among unmatched formals |
| 31 | harness | MEDIUM | (F2) Failed audits read as clean in replay | `audit_failed`; any failed audit shape raises `AuditCrashed`; replay timeout |
| 32 | harness | MEDIUM | (F3) A locked row could go pending | Outcome `lost` fails recall |
| 33 | signature | MEDIUM | (F4) Quadratic scans below the size guard; 109-133 s | Linear paren map, work budget, visible skips |
| 29 | repo | MEDIUM | Not a SPEC finding: #85's drift-only `version` override stopped `/rforge:finish` adding `version:` to a `.STATUS` that lacks one | Fixed and merged separately (PR #86, `lib.rstatus.version_overrides`) |

## Appendix

- Brainstorm: `BRAINSTORM-docs-content-skills-2026-10-11.md`; decision ledger: `GRILL-docs-content-skills-2026-10-11.md`
- Corrections the grill made to the brainstorm: impact folded into `--since`; `docs:check` rewritten instead of
  `docs:audit`; deploy-commit-message detection replaced by sitemap comparison; "seventh class" moved out of v1
- Real known-answer history in medfit: defect at `17d976d^` (`introduction.qmd:35`, `refcard.qmd:72`), fixed at
  `17d976d` (PR #133); README `NIE = 0.19` at `b1f307b^:151`, fixed by PR #134
- Hold-out results (fill before release): probmed — findings / true / false / won't-fix; medrobust — same

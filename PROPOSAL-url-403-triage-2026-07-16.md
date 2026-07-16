# PROPOSAL — Evidence-Based 403 Triage for `/rforge:r:urlcheck`

**Date:** 2026-07-16 · **Status:** proposed · **Origin:** medrobust 0.4.0 CRAN preflight

## The problem

`urlchecker::url_check()` cannot distinguish a **dead link** from a **bot-blocked** one.
Both surface as a failure; only one is real.

Live example (medrobust 0.4.0 preflight, 2026-07-16):

| URL | urlchecker | Reality |
|---|---|---|
| `www.cdc.gov/nchs/nhanes/` | 403 | **200** on repeated plain `curl` — transient/UA misfire |
| `data.nber.org/nvss/natality/csv/2021/natality2021us.csv` | 403 | Site root `data.nber.org/` **also 403** → blanket bot-block; link is valid |

Meanwhile `R CMD check --as-cran` — the *same code path CRAN runs* — reported **0/0/0** and
flagged neither. So urlchecker produced two false positives that a maintainer had to
adjudicate by hand.

## Why the current fix doesn't generalize

`lib/rcmd.py:229` (shipped v2.14.0+, from `SPEC-cran-check-gap-fill-2026-06-19.md` G4):

```python
if "doi.org" in url and "403" in status_code:
    doi_blocked.append(item)     # advisory → 🟡 warn
else:
    real_broken.append(item)     # → 🔴 error
```

The insight was right — **403 ≠ broken** — but it's hardcoded to a single domain.
Every other bot-protected host (cdc.gov, nber.org, jstor, sciencedirect, springer,
tandfonline, ieee) still lands in `real_broken` and reports 🔴 **error**. That is a false
positive by rforge's own stated rule.

## Root cause

**403 Forbidden means "refused", not "absent"** (that's 404). Government/research/publisher
hosts sit behind WAFs (Akamai/Cloudflare) that fingerprint clients — user-agent, TLS/JA3,
HTTP/2 settings, header order. R's default UA is literally:

```
R (4.6.1 aarch64-apple-darwin25.4.0 aarch64 darwin25.5.0)
```

— an unmistakable non-browser signature. Any WAF-protected host may refuse it.

## Options

### Quick wins (<30 min)

1. **Extend the domain allowlist** — turn `"doi.org" in url` into a membership test against a
   set of known bot-protected hosts.
   *Pro:* one-line, immediate. *Con:* brittle — a static list never covers everything, and it
   cannot distinguish a genuinely dead `cdc.gov` link from a blocked one. Trades one false
   positive class for a false **negative** class.

2. **`cran-comments.md` boilerplate** — a standard line explaining 403s from bot-protected
   hosts. Zero code; useful regardless of which option ships.

### Medium (1–2 hrs) — **recommended**

3. **Evidence-based 403 triage.** Replace the domain heuristic with *probing*. For any 403:
   - Re-probe the **site root** (`scheme://host/`). Root also 403 → blanket bot-block.
   - **Retry N times** with backoff → catches transient/rate-limit.
   - Compare **default-UA vs browser-UA** → asymmetry proves UA filtering.

   Classify into:

   | Class | Evidence | Gate? |
   |---|---|---|
   | `dead` | 404 / DNS failure / connection refused | 🔴 yes |
   | `bot_blocked` | 403 **and** site root 403 | 🟡 advisory |
   | `transient` | inconsistent across retries | 🟡 advisory |
   | `real_403` | 403 but root 200 **and** consistent | 🔴 yes |

   This is exactly the manual reasoning applied to medrobust — automated. `doi.org` stops
   being a special case and becomes one instance of `bot_blocked`.

4. **Report the evidence, not just the verdict** — emit *why* each item was downgraded
   ("site root also returned 403 → blanket bot-block"). Maintainer audits reasoning instead
   of trusting an opaque list.

### Long-term

5. **Upstream to `urlchecker`** — it has **no allowlist and no UA option**
   (`url_check(path, db, parallel, pool, progress)`). A PR adding either would help every R
   package, not just this ecosystem.

6. **Use the supported `db` hook** — build via `tools::url_db_from_package_sources()`, filter,
   pass back as `url_check(db = ...)`. The sanctioned API path; avoids patching urlchecker.

7. **Rd convention shift** — prefer `\doi{}` over `\url{}` for data citations; link landing
   pages rather than deep file URLs. Reduces exposure at the source.

8. **Adjudication cache** — persist per-URL verdicts across releases so the same 403 isn't
   re-litigated every cycle.

## ⚠️ Honest scope limit

**None of this changes CRAN's verdict.** CRAN runs its own URL check with R's UA and cannot be
configured by us. This work reduces **local preflight noise** and prevents wasted maintainer
adjudication — it does not prevent a CRAN-side "possibly invalid URL" NOTE. If CRAN flags one,
the answer is still an explanation in `cran-comments.md` (option 2).

## Recommended next step

→ **Option 3 (evidence-based triage)**, because it is correct *by construction* rather than by
list-maintenance, and it's a refactor of already-shipped code (`lib/rcmd.py` G4) rather than
new surface area. Option 2 is a free companion. Option 1 is a stopgap only if 3 is deferred.

## Acceptance criteria

- `data.nber.org` 403 → `bot_blocked` (advisory), evidenced by root probe.
- A genuinely dead URL (404) → `dead` (🔴 error) — no regression in real detection.
- `doi.org` 403 → still advisory, now via the general classifier, not a special case.
- Existing `doi_blocked_count` contract preserved or migrated with the render prompt
  (`commands/r/urlcheck.md`).
- Evidence string emitted per downgraded item.

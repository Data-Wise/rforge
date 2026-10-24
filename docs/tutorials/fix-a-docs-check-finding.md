# Fix a docs:check finding

!!! tip "TL;DR (30 seconds)"
    - **What:** run the docs audit, decide whether each finding is a real doc bug, fix it, and re-run until the report is clean and complete.
    - **Time:** about 10 minutes.
    - **You need:** an R package with a `man/` folder and docs (`README`, `vignettes/`). No R session is required for the default static audit; `--run-examples` needs R.

You will find a doc call that no longer matches the function, fix it, and wire the check into a release.
The reference for every check is the [Docs audit guide](../guides/docs-audit.md).

## Step 1: Run it and read the first and last lines

```text
/rforge:docs:check
```

```text
scope: package medfit at /path/to/medfit
error signature-named-arg  vignettes/articles/refcard.qmd:49  `joint_effects()` has no argument `bogus` (formals: object, estimates)
warn  signature-names      vignettes/articles/refcard.qmd:13  listing of `joint_effects()` names `theta`, which is not a formal (formals: object, estimates)
checked 18 of 22 exported functions (3 no-usage, 1 variadic not checked)
```

1. **First line: the scope.** It says which package was audited. Outside a package it says `scope: none` and what to do.
2. **Last lines: how much it could see.** `checked 18 of 22` means 4 exports were not judged. If the report ends with
   `INCOMPLETE` or `NOT AUDITED`, it is **not** clean even when no findings are listed.

## Step 2: Triage each finding against the source of truth

The Rd usage is the source of truth. For the `error` above:

```text
grep -A3 "\\\\usage" man/joint_effects.Rd      # formals: object, estimates
```

- `error signature-named-arg`: the call names an argument the function does not have. Real bug unless the line is
  deliberate pseudo-code (a "this used to work" example).
- `warn signature-names`: a reference-card row lists a signature that does not match. It cannot tell a stale name from
  a placeholder, so look.
- `warn signature-arity`: more positional arguments than the function has formals.

!!! warning "Symptom"
    A finding you are sure is wrong.

!!! tip "Fix"
    Check whether the function has a `...` formal (the audit skips those) or whether the document rebinds the name
    (`f <- other`, a `function(f)` parameter). If it is a case the audit cannot see, allowlist it (Step 4).

## Step 3: Fix the docs and re-run

Change the call or the listing to the real signature, then run the command again. Repeat until the only output is the
scope line, `checked N of M` and `no findings`.

## Step 4: Suppress what is intentional

```yaml
# .rforge.yaml (package root)
docs:
  allowlist:
    - vignettes/articles/legacy-api.qmd::signature-named-arg
```

The summary reports how many findings were suppressed, so a growing allowlist stays visible.

## Step 5: Use it in a release

```text
/rforge:docs:check --fail-on error      # exit 1 on any error; 2 if the audit could not finish
/rforge:docs:check --since v2.0.0       # which exports added since the tag are never mentioned in the docs
/rforge:docs:check --eco                # every package under the ecosystem root
```

`--fail-on` sets only the exit code. Exit 2 means the audit failed, was incomplete or looked at nothing, so it cannot
vouch for a release.

## What next

- [Docs audit guide](../guides/docs-audit.md): every check, scope rules and known limitations.
- [CRAN release prep](cran-release-prep.md): where the audit sits before `r:cran-prep`.

## Optional follow-up checks

Use `--site URL --ref REF` for a single package's deployment-source sitemap check.
Use `--run-examples --examples-budget-seconds 300 --fail-on warn` for supported
README replay. Hidden setup stays ordered; source/render pairing and figure
options remain unsupported. Check stage counts and INCOMPLETE before changing
published examples. A warning is a candidate; an incomplete replay is not proof
that the document is broken. Run replay in a terminal when host lifetime is unknown.

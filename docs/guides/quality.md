# 🧹 Quality commands

!!! tip "TL;DR (30 seconds)"
    - **What:** Four static-quality commands for an R package — `r:lint` (style/bug
      smells), `r:spell` (typos), `r:style` (auto-format), `r:urlcheck` (dead/redirected
      links).
    - **Why:** Catch the cheap, high-signal issues — and the common CRAN rejection causes
      (misspellings, broken URLs) — before they reach `R CMD check`.
    - **The split that matters:** Three are **read-only**. `r:style` **rewrites your source
      files** — it is the only mutating command in the family.
    - **Next:** Fold these into the [R package dev cycle](../tutorials/r-dev-cycle.md), and
      scope `r:lint` to your branch with [diff-aware checks](diff-aware.md).

> **For whom:** An R-package developer who wants the full behavior of the static quality
> commands — every flag, every output shape, and which ones touch the disk.
> **Prior knowledge:** A package registered with `/rforge:init`. Engines are optional R
> packages (`lintr`, `spelling`, `styler`, `urlchecker`); a missing one degrades to 🟡 + a
> hint, never a crash.

---

## What this family covers

These are the **static** quality gates: they read (and for `r:style`, rewrite) your source
without running your package's code or your tests. Each maps to one `lib.rcmd` engine kind,
which shells out to a lower-level R package and normalizes the result into a single JSON
envelope. Three are read-only and safe to run anytime; **`r:style` mutates files** and is
therefore recommend-only via the orchestrator (never auto-run).

| Command | One-line | Engine (`lib.rcmd` kind) | Read-only? |
|---|---|---|---|
| `r:lint` | Style + bug-smell static analysis (`lintr`) | `lint` → `lintr` | ✅ Yes |
| `r:spell` | Spell-check across the package (`spelling`) | `spell` → `spelling` | ✅ Yes |
| `r:style` | Auto-format source to a consistent style (`styler`) | `style` → `styler` | ⚠️ **No — rewrites files** |
| `r:urlcheck` | Detect broken / redirected URLs (`urlchecker`) | `urlcheck` → `urlchecker` | ✅ Yes |

!!! warning "`r:style` is the one that writes to disk"
    `r:lint`, `r:spell`, and `r:urlcheck` only *report*. `r:style` runs
    `styler::style_pkg()`, which **reformats and overwrites your `R/` (and other) source
    files in place.** Because of that it is **recommend-only** through the
    `rforge:orchestrator` — the orchestrator will *suggest* it but never run it for you.
    Always review the diff and keep a clean working tree before running it (see its section).

---

## `r:lint` — static analysis (`lintr`)

**Purpose:** Run `lintr::lint_package()` to flag style violations and likely-bug patterns
(`object_name_linter`, unused variables, etc.). Read-only — it never edits your code; pair
it with `r:style` to auto-fix the subset that's mechanically fixable.

This is the **only quality command with diff-aware flags.** With `--changed` it scopes the
run to the package(s) you touched on this branch and tags each lint `[introduced]` vs
`[pre-existing]` via a merge-base baseline run. The depth of that behavior (the second
baseline run, `[uncommitted]` refinement, the per-package cache) lives in the diff-aware
guide — see [diff-aware checks](diff-aware.md) rather than duplicating
it here.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `package` | string | current dir | Package path to lint. |
| `--changed` | boolean | `false` | Lint only the package(s) changed vs `--base`; tag each lint `[introduced]` / `[pre-existing]` via a two-run merge-base baseline. |
| `--base` | string | `dev` | Comparison ref for `--changed`; diff + baseline run against `merge-base(HEAD, base)`. |
| `--fail-on` | string | `introduced` | `--changed` exit policy: `introduced` exits non-zero iff ≥1 introduced lint; `none` is advisory (always exit 0). |
| `--no-cache` | boolean | `false` | `--changed` only: bypass the per-package baseline cache — force a fresh baseline run and skip writing it. |

```bash
# Lint the whole package
/rforge:r:lint

# Lint only what this branch changed, failing on lints you introduced
/rforge:r:lint --changed --base dev --fail-on introduced
```

**Output shape** — grouped by file, each lint as `file:line — linter: message`:

```markdown
## Lint: {package} v{version}
### Status: 🟡 {count} lints      # 🟢 when 0
R/foo.R:3 — object_name_linter: variable 'myVar' should be snake_case
R/foo.R:12 — unused_import_linter: 'stringr' is imported but never used
### Recommended Actions
{top offenders to fix, or "Clean ✅"}
```

!!! tip "Lint then style"
    Many lints (indentation, spacing, brace placement) are exactly what `r:style`
    auto-fixes. A productive loop is **`r:lint` → `r:style` → `r:lint`**: format away the
    mechanical noise, then re-lint to see what genuinely needs a human.

---

## `r:spell` — spell-check (`spelling`)

**Purpose:** Run `spelling::spell_check_package()` over documentation, `DESCRIPTION`, and
vignettes. Misspellings are a routine CRAN NOTE, so clearing them here saves a round-trip.
Read-only.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `package` | string | current dir | Package path to spell-check. |

```bash
/rforge:r:spell
```

**Output shape** — each misspelled word with the file/line it came from:

```markdown
## Spell: {package} v{version}
### Status: 🟡 {count} words      # 🟢 when 0
- teh (R/foo.R:3)
- existant (man/bar.Rd:8)
### Recommended Actions
{real typos to fix vs. words to add to inst/WORDLIST}
```

!!! tip "Not every flag is a typo"
    Domain jargon, author names, and package names trip the checker. Add legitimate words
    to **`inst/WORDLIST`** (one per line) so future runs stay quiet — reserve actual edits
    for genuine typos.

!!! note "Expected behavior"
    Spelling NOTEs also surface in `r:check` (R CMD check runs the same spell pass).
    Clearing `r:spell` first means the check is one NOTE quieter.

---

## `r:style` — auto-format (`styler`) ⚠️ MUTATES SOURCE

**Purpose:** Run `styler::style_pkg()` to reformat your source to a consistent style
(spacing, indentation, assignment, braces). **This rewrites files in place** — it is the
only command in this family that changes your code.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `package` | string | current dir | Package path to reformat. |

After formatting, the command runs `git -C <path> diff --stat` so you can see exactly which
files changed.

```bash
# Reformat the package, then review what moved
/rforge:r:style
git diff                       # inspect the actual changes
git checkout -- R/foo.R        # undo a file if you don't want it
```

**Output shape:**

```markdown
## Style: {package} v{version}
### Status: 🟢 reformatted       # 🔴 on failure
- Files changed: {count}
{git diff --stat summary}
### Recommended Actions
- Review: `git diff` · Undo if unwanted: `git checkout -- <files>`
```

!!! warning "Run it on a clean working tree"
    `r:style` edits files directly, so its changes mix into whatever you already have
    staged/unstaged. **Commit or stash first**, then run `r:style`, then review its diff in
    isolation — that way an unwanted reformat is one `git checkout` away. Through the
    `rforge:orchestrator` this command is **recommend-only**: it is surfaced as a
    suggestion and **never executed automatically**, precisely because it writes to disk.

---

## `r:urlcheck` — link checker (`urlchecker`)

**Purpose:** Run `urlchecker::url_check()` to find dead or redirected URLs in your docs and
`DESCRIPTION`. Broken/redirecting links are a common CRAN rejection cause. Read-only — it
reports suggestions but does not rewrite your links.

| Flag | Type | Default | Effect |
|---|---|---|---|
| `package` | string | current dir | Package path to URL-check. |

```bash
/rforge:r:urlcheck
```

**Output shape** — each problem URL with its message and a suggested replacement:

```markdown
## URL Check: {package} v{version}
### Status: 🟡 {count} URLs       # 🟢 when 0
- http://x — moved permanently → suggested: https://x
### Recommended Actions
{replace redirected URLs with suggestions, fix dead links}
```

!!! note "Expected behavior"
    Broken URLs are also flagged by `r:check`. Fixing them here — and applying the
    `suggested:` HTTPS/redirect targets — removes a frequent CRAN-incoming NOTE before
    submission.

---

## See also

- [Command reference](../commands.md) — the terse one-line index of all commands.
- [`lib/rcmd.py` reference](../reference/rcmd.md) — the engine layer (`lintr` / `spelling`
  / `styler` / `urlchecker` kinds) and the normalized envelope these commands consume.
- [R package dev cycle](../tutorials/r-dev-cycle.md) — the inner loop these quality gates
  fit into.
- [Diff-aware checks](diff-aware.md) — the full story behind
  `r:lint --changed` (`[introduced]` / `[pre-existing]` tagging, baseline cache).

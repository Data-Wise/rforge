# ⚙️ Configuring RForge for Your R Package

!!! tip "TL;DR (30 seconds)"
    - **What:** Tune 4 options (CRAN mirror, vignette engine, R version pin, CLAUDE.md budget).
    - **Why:** Defaults work for most repos; override when you need CRAN-specific behavior or mirror selection.
    - **How:** Edit `.claude-plugin/config.json` in your repo root.
    - **Next:** Most users skip this entirely — the defaults are sensible.

⏱️ **5 minutes** • 🟢 Beginner • Optional

> Added in v1.2.0. Stub configuration; more options will be added in
> later phases.

RForge ships with sensible defaults, but you can tune four options
through `.claude-plugin/config.json`. This page walks through each one
and explains when you'd want to override them.

---

## Where configuration lives

| File | Scope | Purpose |
|------|-------|---------|
| `.claude-plugin/config.json` | Plugin-shipped defaults | Authoritative defaults bundled with rforge. **Don't edit in place.** |
| `.claude/rforge.local.json` | Per-project overrides | Project-specific tuning. Created by you, gitignored or committed depending on team preference. |

The plugin reads the bundled defaults first, then merges any project-local
overrides on top.

---

## The four options

### 1. `cran_mirror`

**Default:** `https://cloud.r-project.org`
**Type:** URL string

The CRAN mirror used by `install.packages()` and dependency resolution
when rforge tooling needs to fetch packages.

#### When to override

| If you… | Use |
|---------|-----|
| Want vendor-neutral, globally distributed (default) | `https://cloud.r-project.org` |
| Are inside a Posit/RStudio shop | `https://cran.rstudio.com` |
| Want pre-built binary packages on Linux (much faster) | `https://packagemanager.posit.co/cran/latest` |
| Have an internal mirror (corporate proxy) | Your internal URL |

#### Example override

```json
{
  "cran_mirror": "https://packagemanager.posit.co/cran/latest"
}
```

---

### 2. `vignette_engine`

**Default:** `knitr::rmarkdown`
**Type:** Enum — one of `knitr::rmarkdown`, `knitr::knitr`, `quarto`

The default `VignetteBuilder` written into `DESCRIPTION` when rforge
scaffolds a new vignette.

#### When to override

| If you… | Use |
|---------|-----|
| Build standard `.Rmd` vignettes (default) | `knitr::rmarkdown` |
| Use Quarto (`.qmd`) vignettes | `quarto` |
| Use raw `.Rnw` Sweave vignettes | `knitr::knitr` |

#### Example override

```json
{
  "vignette_engine": "quarto"
}
```

When you scaffold with `vignette_engine: "quarto"`, rforge writes:

```text
VignetteBuilder: quarto
```

…to `DESCRIPTION` and creates a `vignettes/*.qmd` skeleton instead of
`.Rmd`.

---

### 3. `r_version_pin`

**Default:** `>= 4.1.0`
**Type:** SemVer comparison string

The default R version requirement written into `DESCRIPTION`'s `Depends:`
field when rforge scaffolds a new package.

#### When to override

| If you… | Use |
|---------|-----|
| Target broadly-installed R (default) | `>= 4.1.0` |
| Need newer features (e.g. `\|>` native pipe) | `>= 4.2.0` |
| Maintain compatibility with stale enterprise R | `>= 3.6.0` |
| Pin to a specific version | `== 4.3.2` |

CRAN tooling generally prefers loose lower bounds (`>=`) over strict
equality (`==`) — use `==` only when you have a real reason.

#### Example override

```json
{
  "r_version_pin": ">= 4.2.0"
}
```

---

### 4. `claude_md_budget`

**Default:** `600`
**Type:** Integer (line count)

Maximum number of lines for `CLAUDE.md` files in your R package.
`/rforge:docs:check` warns when this threshold is exceeded.

CLAUDE.md files at this scale tend to drift into stale documentation —
600 lines is a reasonable upper bound before they should be split into
sub-files or trimmed.

#### When to override

| If you… | Use |
|---------|-----|
| Want a tighter doc-budget (recommended for new projects) | `400` |
| Use the shipped default | `600` |
| Maintain a CLAUDE.md hub for a complex ecosystem | `1000` |

#### Example override

```json
{
  "claude_md_budget": 400
}
```

---

## Putting it all together

A complete project-local override at `.claude/rforge.local.json`:

```json
{
  "cran_mirror": "https://packagemanager.posit.co/cran/latest",
  "vignette_engine": "quarto",
  "r_version_pin": ">= 4.2.0",
  "claude_md_budget": 400
}
```

---

## See Also

- [Hooks & Skills Reference](hooks-and-skills.md) — what runs
  automatically on every edit.
- `.claude-plugin/config.json` — the plugin-shipped defaults (read-only).
- `/rforge:status` — shows the active configuration for your project.

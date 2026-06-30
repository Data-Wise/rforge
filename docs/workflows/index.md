# 📊 Visual Workflows

!!! tip "TL;DR (30 seconds)"
    - **What:** Every rforge workflow as a diagram, on one page.
    - **Why:** Visual learners (and anyone) can see the whole shape before reading the steps.
    - **How:** Find your scenario below → follow the diagram → click through to the matching tutorial.
    - **Next:** [Tutorials](../tutorials/README.md) for the step-by-step versions.

This page collects the rforge workflows as diagrams. Each one links to the
tutorial that walks it through in detail.

## 🚀 First-time onboarding

From zero to your first analysis.

```mermaid
flowchart LR
    A["Install<br/>brew / marketplace"] --> B["/rforge:detect<br/>see the packages"]
    B --> C["/rforge:init<br/>register active package"]
    C --> D["/rforge:status<br/>health snapshot"]
    D --> E["/rforge:analyze<br/>first real analysis"]
```

→ [Getting started](../tutorials/getting-started.md) (~10 min)

## 🔁 R package dev cycle

The inner loop: every code change runs through these `r:` commands.

```mermaid
flowchart TD
    A["edit code in R/*.R"] --> B["/rforge:r:cycle\ndocument → test → check"]
    B --> C{"All stages\npassed?"}
    C -- "yes ✅" --> D["commit / push"]
    C -- "no ❌" --> E["fix the failing stage"]
    E --> B

    D --> F["pre-commit quality\n(optional but recommended)"]
    F --> G["/rforge:r:lint\n/rforge:r:spell\n/rforge:r:urlcheck"]
    G --> H{"Clean?"}
    H -- "yes ✅" --> I["open PR"]
    H -- "style issues" --> J["/rforge:r:style\n(auto-fix formatting)"]
    J --> G
```

→ [R package dev cycle](../tutorials/r-dev-cycle.md) (~10 min)

## 🔬 Diff-aware merge gate

Before merging a branch: separate the findings *you* introduced from pre-existing debt.

```mermaid
flowchart TD
    A["/rforge:r:check --changed --base dev"] --> B{"merge-base found?"}
    B -- "no" --> Z["full check + warning<br/>(scope-only fallback)"]
    B -- "yes" --> C["baseline run in a detached<br/>worktree at the merge-base"]
    C --> D["set-diff vs HEAD findings"]
    D --> E["tag [introduced] / [pre-existing]"]
    E --> F{"--fail-on introduced?"}
    F -- "≥1 introduced" --> G["exit non-zero ❌<br/>(fix before merge)"]
    F -- "none introduced" --> H["exit 0 ✅<br/>(pre-existing debt only)"]
```

→ [Diff-aware checks](../tutorials/diff-aware-checks.md) (~8 min)

## 🧬 S7 convention checking

Audit S7 OOP conventions — statically, across the ecosystem, or at runtime.

```mermaid
flowchart TD
    A["/rforge:r:s7-review"] --> B{"scope?"}
    B -- "this package" --> C["STATIC (default)<br/>pure-Python, 5 families"]
    B -- "--eco" --> D["ecosystem sweep<br/>static × every package"]
    B -- "--runtime" --> E["runtime pass (needs R+S7)<br/>dead_generic · validator_not_enforcing<br/>· method_on_missing_class"]
    C --> F["advisory envelope<br/>(looks like / consider)"]
    D --> F
    E --> F
    E -. "R/S7 absent" .-> G["degrades to warn<br/>(static intact, exit 0)"]
```

→ [S7 convention checking](../tutorials/s7-convention-checking.md) (~10 min)

## 🔁 Ecosystem daily loop

The habit: change code with R tools, check the ecosystem with rforge.

```mermaid
flowchart TD
    A["Write code + tests<br/>usethis / devtools (R)"] --> B["/rforge:quick<br/>10s snapshot"]
    B --> C{"Change touches a<br/>shared package?"}
    C -- "no" --> D["devtools::test() (R)"]
    C -- "yes" --> E["/rforge:impact<br/>what breaks?"]
    E --> D
    D --> F["git commit"]
```

→ [rforge in the R package lifecycle](../tutorials/rforge-in-the-r-lifecycle.md) (~12 min)

## 🎛️ Choosing analysis depth (modes)

One command, four depths — let context pick, or force it with `--mode`.

```mermaid
flowchart TD
    A["/rforge:analyze"] --> B{"What do I need?"}
    B -- "quick sanity check" --> D["default<br/>(no flag, <10s)"]
    B -- "something's broken" --> E["--mode debug<br/>(<2 min)"]
    B -- "it works but feels slow" --> F["--mode optimize<br/>(<3 min)"]
    B -- "shipping to CRAN" --> G["--mode release<br/>(<5 min)"]
```

→ [Understanding modes](../tutorials/understanding-modes.md) (~5 min)

## 🔗 Ecosystem orchestration

Map → assess → plan, for multi-package changes.

```mermaid
flowchart LR
    A["/rforge:deps<br/>map structure"] --> B["/rforge:impact<br/>blast radius"]
    B --> C{"Severity<br/>acceptable?"}
    C -- "yes" --> D["/rforge:cascade<br/>plan rollout"]
    C -- "reconsider" --> E["redesign as<br/>feature + deprecation"]
    E --> B
    D --> F["execute in<br/>topological order"]
```

→ [Ecosystem orchestration](../tutorials/ecosystem-orchestration.md) (~15 min)

## 📦 CRAN release pipeline

Per-package gate → ecosystem rollup → submission order.

```mermaid
flowchart TD
    A["/rforge:docs:check\nNEWS + doc drift"] --> B

    subgraph gate["Per-package gate (v2.2.0+, strict by default v2.3.0+)"]
        B["/rforge:r:cran-prep\ndocument→lint→spell→urlcheck→test→coverage\ncheck → check (noSuggests) → check (suggests-only)\nTier 4: description, build-hygiene, docs-consistency\nrevdep · writes cran-comments.md"]
    end

    B --> C{"ready / warn\n/ blocked?"}
    C -- "blocked ❌" --> D["fix blockers\n(loop back)"]
    D --> A
    C -- "ready ✅ or warn 🟡" --> E["/rforge:thorough\necosystem rollup"]
    E --> F["/rforge:release\nCRAN submission order"]
    F --> H["/rforge:r:submit\npre-release + handoff\n(opt: --universe early-access)"]
    H --> G["submit via\nCRAN web form"]
```

→ [CRAN submission with rforge](../tutorials/cran-submission-with-rforge.md) (~15 min, per-package gate)
→ [CRAN release prep](../tutorials/cran-release-prep.md) (~15 min, ecosystem pipeline)

!!! tip "R-universe early-access (v2.7.0+)"
    CRAN review takes days; [R-universe](https://r-universe.dev) rebuilds your package from its GitHub repo within minutes and serves CRAN-like binaries. Run `/rforge:r:submit --universe` to verify your package's R-universe build is green — users can then `install.packages("<pkg>", repos = "https://<owner>.r-universe.dev")` **while** CRAN review runs in parallel. It's **read-only** (R-universe builds on `git push`) and **advisory** — it never blocks or triggers the still-manual CRAN submission.

!!! warning "Strict passes block `ready` (v2.3.0+)"
    As of v2.3.0 the gate runs two Suggests-withholding flavor passes — `check (noSuggests)` and `check (suggests-only)` — **by default**, each with `--run-donttest`, and a strict ERROR blocks the `ready` verdict. A package that was 🟢 `ready` under `--as-cran` can now turn 🔴 once the noSuggests pass catches a `Suggests` package used unconditionally. The Tier 4 stages (`description`, `build-hygiene`, `docs-consistency`, backed by `lib/cranlint.py`) are advisory and never block on their own. Add `--incoming` for the opt-in CRAN-incoming `_R_CHECK_*` pass.

## 📦 Tarball check (v2.17.0+)

Builds a source tarball and runs `rcmdcheck` on it rather than the source
tree — catches artifact leaks (`.quarto/`, `_freeze/`, `.html`, `*_files/`)
that a source-tree check masks.

```mermaid
flowchart TD
    A["/rforge:r:cran-prep"] --> B["Pass 1: dev cycle"]
    B --> C["devtools::build()"]
    C --> D["tar -tzf inspect<br/>(pure-Python tarfile)"]
    D --> E{"Leaked artifacts?"}
    E -- "yes" --> F["surface as advisory<br/>(not blocking)"]
    E -- "no" --> G["rcmdcheck(tarball, --as-cran)"]
    G --> H{"Errors/Warnings/real NOTEs?"}
    H -- "yes" --> I["blocking ❌"]
    H -- "no" --> J["Pass 3: ecosystem → ready ✅"]
    F --> G
```

→ [Win-builder + tarball-check tutorial](../tutorials/cran-winbuilder-tarball-check.md)

## 🌐 Multi-platform verification (optional)

Async dispatch to win-builder and R-hub before CRAN submission.

```mermaid
flowchart LR
    A["/rforge:r:cran-prep\n--multi-platform"] --> B["/rforge:r:winbuilder\nasync dispatch"]
    A --> C["/rforge:r:rhub\nasync dispatch"]
    B --> D["results emailed\nto DESCRIPTION maintainer"]
    C --> E["results in repo's\nGitHub Actions tab"]
    D --> F["review + address\nany Windows-specific issues"]
    E --> F
    F --> G["submit to CRAN"]
```

→ [CRAN submission — multi-platform section](../tutorials/cran-submission-with-rforge.md)

## How rforge fits with R's own tools

The boundary in one picture: R tools build a package; rforge orchestrates
the set.

```mermaid
flowchart LR
    subgraph R["R toolchain (per package)"]
        U["usethis::create_package()"]
        D["devtools::document()"]
        T["devtools::test()"]
        K["R CMD check"]
    end
    subgraph RF["rforge (across packages)"]
        DET["/rforge:detect"]
        DEP["/rforge:deps"]
        IMP["/rforge:impact"]
        REL["/rforge:release"]
    end
    R -->|"packages exist on disk"| RF
```

→ [rforge in the R package lifecycle](../tutorials/rforge-in-the-r-lifecycle.md)

## See also

- **[Tutorials](../tutorials/README.md)** — step-by-step versions of every workflow above
- **[REFCARD](../REFCARD.md)** — all {{ rforge.command_count }} commands on one page
- **[Architecture](../architecture.md)** — how the plugin's internals fit together

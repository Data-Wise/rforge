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

## 🔁 Daily development loop

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

Drift check → R CMD check → rollup → submission order.

```mermaid
flowchart TD
    A["/rforge:docs:check<br/>NEWS + doc drift"] --> B["/rforge:r:check<br/>R CMD check, parsed"]
    B --> C["/rforge:thorough<br/>ecosystem rollup"]
    C --> D{"All green?"}
    D -- "no" --> E["fix blockers<br/>(loop back)"]
    E --> A
    D -- "yes" --> F["/rforge:release<br/>CRAN submission order"]
    F --> G["submit via<br/>CRAN web form"]
```

→ [CRAN release prep](../tutorials/cran-release-prep.md) (~15 min)

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
- **[REFCARD](../REFCARD.md)** — all 28 commands on one page
- **[Architecture](../architecture.md)** — how the plugin's internals fit together

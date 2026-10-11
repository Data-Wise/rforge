# Ecosystem analysis (analyze / impact / deps / cascade / release)

!!! tip "TL;DR (30 seconds)"
    - **What:** the commands that look *across* packages: what is here, how healthy it is, what a change touches, and in what order to update and release.
    - **Start:** `/rforge:status` (snapshot), then `/rforge:quick` (under 10 s) or `/rforge:thorough` (2-5 min).
    - **Before a change:** `/rforge:impact`, then `/rforge:cascade` to plan the order. **Before a release:** `/rforge:release`.

These commands read the packages under your ecosystem root. They use the `lib.discovery`, `lib.deps` and `lib.status`
modules (pure Python, no R) for the facts and add Claude's synthesis on top. For a *single* package's dev cycle see
[Dev cycle](dev-cycle.md); for the CRAN gate see [CRAN submission](cran-submission.md).

## Which command, when

| You want to... | Command | Cost |
|---|---|---|
| See what packages are here and how they are laid out | `/rforge:detect` | instant |
| Register a package as the active context | `/rforge:init` | instant, idempotent |
| A health snapshot, `.STATUS` aggregated | `/rforge:status` | seconds |
| A fast sanity check | `/rforge:quick` | under 10 s |
| Mode-aware analysis of a change or area | `/rforge:analyze` | about 30 s |
| A full rollup (status, deps, cross-package health, CRAN order) | `/rforge:thorough` | 2-5 min |
| The dependency graph | `/rforge:deps` | seconds |
| What a change breaks downstream | `/rforge:impact` | seconds |
| A coordinated update plan across packages | `/rforge:cascade` | prompt-driven |
| The CRAN submission order | `/rforge:release` | prompt-driven |
| Ecosystem health metrics | `/rforge:health` | prompt-driven |

## 1. Orient: detect, init, status

```text
/rforge:detect          # single package, ecosystem or hybrid? what is under the root?
/rforge:init            # register the package you are in (safe to re-run)
/rforge:status          # packages, versions, .STATUS aggregation
```

`detect` classifies the layout. Two or more packages is an *ecosystem*; a `kind: hybrid` declaration in
`.rforge.yaml` opts a mixed layout in. `status` is the dashboard you open at the start of a day.

## 2. Look: quick, analyze, thorough

`quick` runs only the fast modules and is the default when you just want to know nothing is on fire. `analyze` picks its
depth from the layout (one package is shallow, five or more is full); see
[Understanding modes](../tutorials/understanding-modes.md). `thorough` is the pre-release rollup.

```text
/rforge:quick
/rforge:analyze "Update bootstrap code"
/rforge:thorough "Prepare RMediation for CRAN"
```

The quoted text is free-form context used for narration; it does not change which modules run.

## 3. Plan a change: impact, deps, cascade

```text
/rforge:deps                          # the graph and its layers
/rforge:impact --package medfit --change-type breaking   # dependents, risk, update sequence
/rforge:cascade "medfit 2.2.0"        # the update plan, in dependency order
/rforge:cascade --detailed
```

Dependency order matters because a downstream package cannot be checked against an upstream change that has not
landed. `deps` shows the layers (leaves first); `cascade` turns them into an upstream-first update plan.
`impact` needs `--package` and takes `--change-type` (default `feature`). It reports direct and indirect dependents,
the approximate number of affected tests, a risk level, an estimated amount of work, and an update sequence.

!!! note "Impact is structural"
    Layers and update order use the hard edges (`Depends`, `Imports`); `Suggests` and `LinkingTo` appear in the graph
    but do not order updates. `impact` reads declared dependencies, not your code, so it cannot tell whether a changed
    export is actually used downstream; `/rforge:r:deps-sync` (DESCRIPTION against usage) covers part of that.

## 4. Release: release, thorough

`/rforge:release` turns the dependency graph into a CRAN submission order (`--detailed` adds the reasoning;
pass a package name to plan for one). It plans only; the per-package gate is `/rforge:r:cran-prep` and the hand-off
is `/rforge:r:submit`, which never auto-submits. The usual sequence:

```text
/rforge:docs:check            # docs match the API (see the Docs audit guide)
/rforge:r:cran-prep           # per package
/rforge:thorough              # ecosystem rollup
/rforge:release               # submission order
```

## 5. Keep track: next, capture, complete, health

```text
/rforge:next                                  # what to do next, ecosystem-aware
/rforge:capture "Add bootstrap intervals"     # a task or idea into .STATUS
/rforge:complete "Add bootstrap intervals"    # mark done; --no-cascade skips doc follow-ups
/rforge:health                                # health metrics across the ecosystem
```

`capture` and `complete` write to the package's `.STATUS`; `complete` also looks for documentation that the finished
task made stale. Use `/rforge:finish` at the end of a session to sync `.STATUS` from what actually happened
([Session boundary](session-boundary.md)).

!!! warning "Symptom"
    `/rforge:status` or `/rforge:impact` shows only one package although you have several.

!!! tip "Fix"
    Run `/rforge:detect` from the ecosystem root, not from inside a package: discovery stops at a package directory
    and does not descend into it.

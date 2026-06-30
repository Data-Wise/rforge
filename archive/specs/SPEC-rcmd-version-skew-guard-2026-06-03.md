# SPEC: Preflight guard for `lib.rcmd` version-skew in the `r:` command family

- **Status:** Draft — awaiting user review
- **Date:** 2026-06-03
- **Target version:** v2.2.1 (patch — resilience, no new surface)
- **Author:** surfaced from a live medfit session where `/rforge:r:site` failed
- **Branch plan:** `feature/rcmd-skew-guard` off `dev`

## Summary

Every command in the `r:` namespace that drives R through Python
(`r:site`, `r:document`, `r:check`, `r:build`, `r:lint`, `r:load`,
`r:coverage`, `r:revdep`, `r:winbuilder`, `r:cran-prep` — 10+ commands)
shells out to `python3 -m lib.rcmd …`. That module landed in **v2.1.0/2.2.0**
(the `r:` dev-cycle + CRAN suite, PRs around #14). When the **installed** copy
of the plugin is older than the repo — e.g. a marketplace install cached at
**v2.0.0** while `main` is at **v2.2.0** — `lib/rcmd.py` is simply absent, and
*all* of these commands die with:

```
/…/python3: No module named lib.rcmd
```

This message names neither the plugin, the version skew, nor the fix. The user
cannot tell whether their package is broken, R is misconfigured, or the plugin
is stale. This spec adds a **preflight guard** so the family fails *legibly*
and points at the actual remedy (update the plugin), plus a CI check that the
shipped manifest and `lib/` stay in lockstep.

This is **not** a code-completeness bug — `lib/rcmd.py` exists and is correct on
`dev` and `main` (25 KB, committed). It is a **resilience + diagnosability** gap
exposed when the install lags the source.

## Motivating incident

During a medfit website build, `/rforge:r:site --path …/medfit` produced only
`No module named lib.rcmd`. Diagnosis required manually comparing the source
repo against the installed marketplace copy:

| Location | Version | `lib/rcmd.py` |
|----------|---------|---------------|
| Source repo (`~/projects/dev-tools/rforge`) | 2.2.0 | present (25 KB) |
| `origin/main`, `origin/dev` | 2.2.0 | present |
| Installed marketplace (`~/.claude/plugins/marketplaces/Data-Wise-rforge`) | **2.0.0** | **absent** |

Root cause: the **local plugin install cache** had not picked up the published
v2.2.0 release. GitHub was correct; only the local snapshot was stale. The
underlying engineering gap is that a single runtime-imported module backs the
whole `r:` family with no guard, so one stale file silently disables ten
commands with an opaque error.

## Goals

1. **Legible failure** — when `lib.rcmd` is missing or its CLI contract is
   older than the command expects, emit an actionable message naming the plugin,
   the detected vs required version, and the update command.
2. **Self-diagnosis** — a one-shot way for the user (or a command) to confirm
   the installed plugin version and whether `lib.rcmd` resolves.
3. **Prevent recurrence** — CI guard that the published `lib/` always contains
   `rcmd.py` and that `marketplace.json` / `plugin.json` versions agree with the
   `lib` capability set.

## Non-goals

- Re-architecting `lib.rcmd` itself (its API is fine).
- Auto-updating the plugin from within a command (Claude Code owns plugin
  lifecycle; we only *detect and instruct*).
- Backporting `rcmd.py` into v2.0.0 (the fix for an affected user is to update,
  not to patch the old version).

## Design

### 1. Shared preflight shim (`lib/_preflight.py` or a `rcmd` guard)

A tiny, dependency-free helper the command bodies call **before** invoking the
real module, e.g.:

```bash
python3 -m lib.rcmd_preflight || exit 0   # prints guidance, non-fatal
python3 -m lib.rcmd --kind site --path "<path>"
```

`rcmd_preflight` (≈30 lines):

- Tries `import importlib.util; importlib.util.find_spec("lib.rcmd")`.
- On success: exit 0 silently (or print version when `--verbose`).
- On failure: print the **structured guidance block** (below) and exit non-zero
  so the wrapper can stop before the opaque `-m lib.rcmd` crash.

Because the *current* failure is `lib.rcmd` not importing at all, the guard must
live in a module that is guaranteed to exist across versions — so put the check
in the **command markdown** as a `find_spec`-style probe rather than a sibling
module that an old install also lacks. Decision: implement the probe inline in a
shared snippet referenced by each `r:` command (a `## Preflight` section), not as
a new importable module (which a stale install would also be missing — the same
failure mode we're trying to fix).

### 2. Guidance block (the user-facing payload)

```
🔴 rforge plugin is out of date

  The `r:` commands need lib/rcmd.py, added in rforge v2.1.0.
  Installed: v{installed}   Required: ≥ v2.1.0

  Update the plugin, then retry:
    /plugin   →  update "rforge"     (or reinstall from the Data-Wise marketplace)

  Verify:  python3 -c "import importlib.util,sys; \
           sys.exit(0 if importlib.util.find_spec('lib.rcmd') else 1)"
```

`{installed}` resolved from the installed `.claude-plugin/plugin.json` when
readable; omit the line if not.

### 3. Version self-report

Add `r:version` (or extend `r:check --context`) to print the resolved plugin
version and a capability probe (`lib.rcmd: ok|MISSING`). One command the user
can run to know exactly what they have.

### 4. CI lockstep guard (prevents shipping a skewed package)

A repo CI step asserting:

- `lib/rcmd.py` exists and imports under the test interpreter.
- `plugin.json.version == marketplace.json…version` (already a release-checklist
  item — make it a hard gate).
- Every `commands/r/*.md` that references `lib.rcmd` is matched by the module
  actually shipping. A grep test: each `--kind <X>` used in a command md is a
  supported `--kind` in `rcmd.py`’s `argparse` choices.

## Immediate remediation (independent of this spec)

For the user hitting it **now**: update the installed plugin to v2.2.0 (via
`/plugin` update or reinstalling from the Data-Wise marketplace). No repo change
required — source/`main` already ship `rcmd.py`. This spec only prevents the
*next* person from getting an opaque error.

## Acceptance criteria

- [ ] Running any `r:` command on a version-skewed install prints the guidance
      block (plugin name + installed/required version + update path), not a bare
      `No module named lib.rcmd`.
- [ ] `r:version` (or `r:check --context`) reports installed version + `lib.rcmd`
      capability probe.
- [ ] CI fails if `lib/rcmd.py` is missing/unimportable, if `plugin.json` and
      `marketplace.json` versions disagree, or if a command references an
      unsupported `--kind`.
- [ ] Docs: a short "plugin out of date?" troubleshooting entry referencing the
      probe one-liner.

## References

- `lib/rcmd.py` — the shared R-command runner (the single point of failure).
- `commands/r/*.md` — the `--kind`-based command family that depends on it.
- `docs/specs/SPEC-r-dev-commands-2026-05-31.md` — introduced the `r:` namespace
  and factored logic into `lib/rcmd.py` (the module this guard protects).
- Incident: medfit `/rforge:r:site` failure, 2026-06-03 (installed v2.0.0 vs
  source v2.2.0).

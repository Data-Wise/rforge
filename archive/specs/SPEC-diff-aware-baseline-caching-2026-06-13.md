# SPEC — diff-aware baseline caching (candidate A)

**Date:** 2026-06-13
**Branch:** `feature/diff-aware-baseline-caching` (worktree off `dev`)
**Status:** approved design (two decisions confirmed via AskUserQuestion)
**Closes:** the last v2.11.0 diff-aware follow-up (`[uncommitted]` tagging shipped v2.12.0).

## Problem

`/rforge:r:check|test|lint --changed` runs `changed.scope_check`, which runs the
engine **twice**: once against a detached worktree checked out at
`git merge-base(HEAD, base)` (the *baseline*), once against the live HEAD tree.
The baseline run (`changed.run_baseline`, `lib/changed.py:241`) does a
`git worktree add --detach` and then runs the engine over the changed package(s)
— for `kind=check` that is `R CMD check` per package, which can take minutes.

The baseline result is a **pure function** of:

1. the merge-base **SHA** (the baselined tree is immutable at that commit),
2. the **kind** (engine),
3. the **changed-package set** evaluated (`rel_pkgs` in `rcmd.run_changed`),
4. the engine **kwargs** (e.g. `--strict`, `--run-donttest` change what is reported).

Yet every `--changed` invocation re-runs it from scratch, even when nothing on
`base` has moved. Repeated checks on a branch pay the full baseline cost each time.

## Goal

Cache the baseline finding list so a repeat `--changed` run with an unchanged
merge-base reuses it instead of re-running the worktree+engine. Self-invalidating:
new `base` commits → new merge-base SHA → new key → cache miss → re-run.

> **Update (same branch):** the original design cached the *whole* baseline run
> keyed by the package set (see the first Non-goal below). After the pre-merge
> adversarial review, the cache was **generalized to per-package granularity** —
> strictly better hit rate and miss cost — so the per-package item is no longer a
> non-goal. Sections below describe the shipped per-package design.

## Non-goals

- Caching the **HEAD** run (changes on every edit; never cacheable).
- ~~Per-package cache granularity~~ — **IMPLEMENTED** (this branch). The baseline
  is cached per package, not per package-set: a run whose changed-package set
  *grows* reuses every already-baselined package and re-runs only the uncached
  ones. (Original v1 plan cached the whole set; superseded.)
- Cross-engine-version staleness detection. The one staleness vector (user
  upgrades e.g. `lintr` so the immutable tree now lints differently) is handled
  by the `--no-cache` escape hatch, not by stamping engine versions into the key.

## Design

### Decisions (confirmed)

- **Location:** `~/.rforge/baseline-cache/<repo-id>/` — user-global, matching the
  existing `~/.rforge/context.json` convention (`lib.init`). Survives across
  worktrees of the same repo; `<repo-id>` namespaces repos so there is no
  cross-repo collision.
- **Eviction:** LRU prune to the **20** newest entries per `<repo-id>` dir (by
  mtime, on every write) + a `--no-cache` flag (bypass read AND write) +
  `--clear-cache` (remove the cache, exit).

### Cache key (per package)

`changed.py` stays **R-free**: it receives an **opaque `cache_key` string** per
item from the caller and owns only the repo-id, SHA, file IO, and prune.

- `<repo-id>` = `sha1(git rev-parse --show-toplevel)[:16]` (falls back to
  `sha1(abspath(path))` when not a git repo — defensive; `scope_check` only
  reaches caching after a merge-base resolved, so it is always a repo in
  practice).
- filename = `<base_sha>-<sha1(cache_key)[:16]>.json`.
- `rcmd.run_changed` builds **one key per changed package**:
  `f"{kind}|{rel}|{kwargs_token}"` (a single package `rel`, not the joined set),
  where `kwargs_token` is `json.dumps(run_kwargs, sort_keys=True, default=str)`.
  Per-package keys are what let a *growing* changed-package set reuse the packages
  already baselined.

### File format

```json
{
  "schema": 1,
  "base_sha": "<full merge-base sha>",
  "cache_key": "<opaque per-package key, stored for debuggability>",
  "findings": [ /* one package's flat baseline finding list */ ]
}
```

Findings are already JSON-serializable (dicts for lint, strings for R CMD check)
because they round-trip through the envelope today.

### Flow: `cached_baseline` (per item) + pluggable `scope_check`

`scope_check` is **caching-agnostic** — it takes a `baseline(path, base_sha) ->
Optional[list]` provider (or, by default, runs one uncached `run_baseline`). rcmd
injects a per-package provider backed by `cached_baseline`:

```text
# scope_check
base_sha = merge_base(HEAD, base)
if base_sha is None: return None
base_findings = baseline(path, base_sha) if baseline else run_baseline(...)
if base_findings is None: return None          # provider says "fall back"
# ... unchanged: head_findings = runner(path), tag_findings, [uncommitted] ...

# cached_baseline(path, base_sha, items, run_item, key_item, *, use_cache)
for item in items:
    hit = read_baseline_cache(path, base_sha, key_item(item))   # per item
    if hit is not None: results[item] = hit
    else: uncached.append(item)
if uncached:                                    # ONE worktree, only if needed
    git worktree add --detach <tmp> <base_sha>
    for item in uncached:
        f = run_item(<tmp>, item); cache it; results[item] = f
    remove worktree (finally)
return flat(results in items order)             # None iff worktree add failed
```

When every item hits, **no worktree is created**. A corrupt/unreadable cache file
is a **miss** (never raises).

### New functions in `lib/changed.py`

| Function | Responsibility |
|---|---|
| `_cache_root() -> Path` | `~/.rforge/baseline-cache` — resolved the raise-proof `expanduser` way (NOT `Path.home()`, which raises on unresolvable HOME), temp-dir fallback |
| `_repo_id(path) -> str` | `sha1(toplevel)[:16]`, abspath fallback |
| `_cache_file(path, base_sha, cache_key) -> Path` | resolve the JSON path |
| `read_baseline_cache(path, base_sha, cache_key) -> Optional[list]` | hit → findings; miss/corrupt → None |
| `write_baseline_cache(path, base_sha, cache_key, findings, *, keep=20)` | atomic write (tmp+replace, tmp removed in `finally`) then `_prune` |
| `_prune(repo_dir, keep)` | keep `keep` newest `*.json` by mtime; rm rest |
| `clear_baseline_cache(path=None) -> int` | rm a repo's cache dir (or whole root if `path` None); return files removed (counts all files) |
| `cached_baseline(path, base_sha, items, run_item, key_item, *, use_cache=True) -> Optional[list]` | per-item baseline: serve cached items, run only uncached ones in one worktree, combine |

### Signature changes

- `scope_check(runner, path=".", base="dev", *, baseline=None)` — `baseline` is an
  optional `(path, base_sha) -> Optional[list]` provider. Omitted = one uncached
  `run_baseline` (the pre-cache behavior, so existing keyless callers/tests are
  unaffected).
- `rcmd.run_changed(..., use_cache: bool = True)` — factors a `_pkg_findings(tree,
  rel)` unit used by both the HEAD `runner` and the baseline; builds a per-package
  `_pkg_key(rel)`; injects `baseline = cached_baseline(..., _pkg_findings,
  _pkg_key, use_cache=use_cache)`.

### CLI

- `python3 -m lib.changed`: add `--no-cache` (sets `use_cache=False`) and
  `--clear-cache` (calls `clear_baseline_cache(path)`, prints count, exits 0).
- `commands/r/{check,test,lint}.md`: document a `--no-cache` flag in frontmatter
  `arguments:` + `## Usage` (the v2.12.0 commands-doc sync-gate will FAIL the
  build until both the frontmatter flag and the `docs/commands.md` section exist —
  this is the gate doing its job).

## Tests (TDD, `tests/test_changed.py`)

Pure unit tests with a **counting fake runner** (no R), using `tmp_path` +
monkeypatched `_cache_root`/`HOME`:

1. miss → runner invoked once, cache file written, findings correct.
2. hit → second `scope_check` with same `(sha, cache_key)` does **not** invoke
   the runner; findings identical.
3. different `base_sha` → miss (runner re-invoked).
4. different `cache_key` → miss.
5. `use_cache=False` → always runs, never writes a file.
6. corrupt cache file (write garbage) → treated as miss, no exception.
7. `_prune` keeps the 20 newest by mtime, removes older.
8. `clear_baseline_cache` removes the repo dir and returns the count.
9. `_repo_id` stable across calls for one repo; differs for a different toplevel.
10. CLI `--no-cache` and `--clear-cache` smoke (argparse wiring).

Plus: existing `scope_check` tests still pass unchanged (caching defaults to a
no-op when `cache_key` is omitted).

## Gates

- `python3 -m pytest tests/` — new cache cases + all existing green.
- `bash tests/test-all.sh` — incl. the commands-doc sync-gate (will force the
  `--no-cache` doc), lib reference sync (`gen_lib_reference.py --check` — regen
  `docs/reference/changed.md`), version/count sync.
- No version bump in this branch — ships in the next release bundle.

## Rollout

Feature branch → PR to `dev`. Pre-release adversarial review before any release
(per the established cadence): focus the skeptics on **cache-key completeness**
(can any input change the baseline findings without changing the key? → the
mis-tagging corruption class) and **prune/clear path safety** (never delete
outside the cache root).

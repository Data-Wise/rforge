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

## Non-goals

- Caching the **HEAD** run (changes on every edit; never cacheable).
- Per-package cache granularity (a run with a *different* package set is a full
  miss and re-baselines all its packages). Noted as a future enhancement; v1
  caches the whole baseline run keyed by the package set. Branches usually touch
  a stable package set, so practical hit rate is high.
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

### Cache key

`changed.py` stays **R-free**: it receives an **opaque `cache_key` string** from
the caller and owns only the repo-id, SHA, file IO, and prune.

- `<repo-id>` = `sha1(git rev-parse --show-toplevel)[:16]` (falls back to
  `sha1(abspath(path))` when not a git repo — defensive; `scope_check` only
  reaches caching after a merge-base resolved, so it is always a repo in
  practice).
- filename = `<base_sha>-<sha1(cache_key)[:16]>.json`.
- `rcmd.run_changed` builds the opaque key as
  `f"{kind}|{','.join(sorted(rel_pkgs))}|{_kwargs_token(run_kwargs)}"` where
  `_kwargs_token` is a stable serialization of the engine kwargs that affect
  output (sorted JSON of the kwargs dict).

### File format

```json
{
  "schema": 1,
  "base_sha": "<full merge-base sha>",
  "cache_key": "<opaque key, stored for debuggability>",
  "findings": [ /* the flat finding list run_baseline returned */ ]
}
```

Findings are already JSON-serializable (dicts for lint, strings for R CMD check)
because they round-trip through the envelope today.

### Read/write flow (in `scope_check`)

```text
base_sha = merge_base(HEAD, base)            # unchanged
if base_sha is None: return None             # unchanged fallback

if use_cache and cache_key is not None:
    cached = read_baseline_cache(path, base_sha, cache_key)
    if cached is not None:
        base_findings = cached               # HIT — no worktree, no engine
    else:
        base_findings = run_baseline(...)    # MISS
        if base_findings is None: return None
        write_baseline_cache(path, base_sha, cache_key, base_findings)
else:
    base_findings = run_baseline(...)        # bypass (use_cache=False)
    if base_findings is None: return None

# ... unchanged: head_findings, tag_findings, [uncommitted] refinement ...
```

A corrupt/unreadable cache file is treated as a **miss** (never raises).

### New functions in `lib/changed.py`

| Function | Responsibility |
|---|---|
| `_cache_root() -> Path` | `Path.home()/".rforge"/"baseline-cache"` |
| `_repo_id(path) -> str` | `sha1(toplevel)[:16]`, abspath fallback |
| `_cache_file(path, base_sha, cache_key) -> Path` | resolve the JSON path |
| `read_baseline_cache(path, base_sha, cache_key) -> Optional[list]` | hit → findings; miss/corrupt → None |
| `write_baseline_cache(path, base_sha, cache_key, findings, *, keep=20)` | atomic write (tmp+replace) then `_prune` |
| `_prune(repo_dir, keep)` | keep `keep` newest `*.json` by mtime; rm rest |
| `clear_baseline_cache(path=None) -> int` | rm a repo's cache dir (or whole root if `path` None); return files removed |

### Signature changes

- `scope_check(runner, path=".", base="dev", *, cache_key=None, use_cache=True)`
  — additive, keyword-only; existing callers/tests unaffected (default off-key =
  no caching, so an omitted `cache_key` runs exactly as today).
- `rcmd.run_changed(..., use_cache: bool = True)` — builds `cache_key`, passes
  both through to `scope_check`.

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

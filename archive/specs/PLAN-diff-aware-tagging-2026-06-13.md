# PLAN: Diff-aware tagging (P0 completion) — v2.11.0 feature 1

> REQUIRED: TDD. Spec: `SPEC-diff-aware-tagging-2026-06-13.md`.

**Goal:** Complete `--changed` so findings are tagged `[introduced]`/`[pre-existing]`
via a real merge-base detached-worktree baseline run.

**Files:**
- Modify: `lib/changed.py` (add `merge_base`, `run_baseline`; wake `scope_check`)
- Modify: `lib/rcmd.py` (`run_changed` — real two-run tagging + fallback)
- Modify: `commands/r/{check,test,lint}.md` (frontmatter `--base`/`--fail-on`)
- Test: `tests/test_changed.py` (+ real-git e2e), `tests/test-all.sh` smoke

### Task 1: `merge_base()` in lib/changed.py
- [ ] Write failing test: temp git repo, base commit on `dev`, branch `feature/x` with a
      commit; `merge_base(path, "dev")` returns the base SHA; returns `None` when no
      common ancestor / not a repo.
- [ ] Implement `merge_base(path=".", base="dev") -> Optional[str]` via
      `_git(["merge-base", "HEAD", base], cwd=path)`; `None` on failure.
- [ ] Run test → pass. Commit.

### Task 2: `run_baseline()` — detached worktree, guaranteed cleanup
- [ ] Write failing test (real git): `run_baseline(path, base_sha, kind="lint")` returns a
      finding list computed at `base_sha`; asserts **no leftover worktree** after
      (`git worktree list` count unchanged), including when the inner run raises.
- [ ] Implement: `tempfile.mkdtemp()` under system temp; `git worktree add --detach <tmp>
      <base_sha>`; call the kind's runner in `<tmp>`; in a `finally`,
      `git worktree remove --force <tmp>` + rmtree. Return `None` on any git failure.
- [ ] Run test → pass. Commit.

### Task 3: Wake `scope_check()` to orchestrate
- [ ] Write failing test: introduce a real finding on the branch + keep one pre-existing;
      `scope_check(...)` returns findings tagged `[introduced]` and `[pre-existing]`
      correctly (uses `tag_findings`, already implemented).
- [ ] Implement: `scope_check` = merge_base → run_baseline (base) → run current (HEAD) →
      `tag_findings(current, base)`; return `None` (caller falls back) on any `None`.
      Remove the DORMANT docstring caveat.
- [ ] Run test → pass. Commit.

### Task 4: Wire into rcmd.run_changed (+ fallback)
- [ ] Write failing test: `run_changed` with tagging available emits tagged findings;
      with `merge_base→None` it stays scope-only and exits 0 (no regression).
- [ ] Implement: call `changed.scope_check`; on success emit tagged envelope + honor
      `--fail-on` (default `introduced`: exit non-zero iff ≥1 introduced). On `None`,
      keep the existing scope-only path + warning. Replace the "tagging deferred" string.
- [ ] Run test → pass. Commit.

### Task 5: Command frontmatter + docs
- [ ] Add `--base` (default `dev`) and `--fail-on` (default `introduced`) to the
      `arguments:` arrays of `commands/r/{check,test,lint}.md`; update `--changed`
      description from "scope-only" to describe tagging; sync `## Usage`.
- [ ] Update `CHANGELOG.md` [Unreleased] + the diff-aware tutorial/spec nav note.
- [ ] Run `bash tests/test-all.sh` + `python3 -m pytest tests/` → green. Commit.

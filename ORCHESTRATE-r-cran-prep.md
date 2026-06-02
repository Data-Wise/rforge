# CRAN-Submission Suite Implementation Plan (`r:cran-prep` + suite)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-package CRAN-submission suite to rforge — `r:cran-prep` orchestrator + `r:revdep` / `r:goodpractice` / `r:winbuilder` / `r:rhub`, plus a NOTE classifier on `r:check` — all on the existing `lib/rcmd.py` envelope. Commands 28 → 33.

**Architecture:** Extend `lib/rcmd.py` (v2.1.0 envelope) with new `kind`s and a `dispatched` status. `r:cran-prep` reuses `run()` for every existing stage (no reimplementation — same DRY rule as `_run_cycle`), generates `cran-comments.md`, and emits a `{ready|blocked}` readiness envelope that composes with `/rforge:release`. New engines are **optional** (degrade to 🟡 + install hint); `devtools` is a scoped exception for `r:winbuilder` only.

**Tech Stack:** Python 3 stdlib (`argparse`/`json`/`subprocess`/`re`/`pathlib`); R engines `revdepcheck`/`goodpractice`/`rhub`/`devtools` (all optional) + the v2.1.0 set; pytest with `Rscript` mocked (R-free CI).

**Spec:** `docs/specs/SPEC-r-cran-prep-2026-06-01.md`

---

## Pre-flight (read first)

- **You are in** `~/.git-worktrees/rforge/feature-r-cran-prep` on `feature/r-cran-prep`. Verify with `git branch --show-current`.
- **`lib/rcmd.py` already exists** (v2.1.0). Read it end-to-end first — you are *extending* it: `find_package`, `_as_list`, `_parse_json`, `_status_for`, `normalize`, `console_fallback`, `_guard`, `r_snippet`, `_invoke_r`, `_install_package`, `run`, `_run_cycle`, `main`, plus `OPTIONAL_ENGINES`/`INSTALL_HINT`.
- **Run lib as a package:** `python3 -m lib.rcmd …` — never `python3 lib/rcmd.py`.
- **Gates (must pass before PR):** `python3 -m pytest tests/` and `bash tests/test-all.sh`.
- **R-API uncertainty:** `revdepcheck`/`goodpractice`/`rhub` are NOT installed locally and their JSON shapes are unverified. Snippets below are best-effort and **flagged "VERIFY LIVE"** — Task 9 (live sanity) is mandatory before PR. This is the v2.1.0 `urlchecker`-columns lesson.
- **Commits:** conventional + `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Don't touch** the rename stubs `commands/{doc-check,ecosystem-health,rpkg-check}.md`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `lib/rcmd.py` (modify) | New `dispatched` status; NOTE classifier; new kinds `revdep`/`goodpractice`/`winbuilder`/`rhub`; `cran-comments` generator; `_run_cran_prep`; main wiring + flags |
| `tests/test_rcmd.py` (modify) | TDD for each addition; R mocked |
| `commands/r/check.md` (modify) | Render classified NOTEs |
| `commands/r/{revdep,goodpractice,winbuilder,rhub,cran-prep}.md` (create) | One prompt per command |
| `docs/reference/rcmd.md` (regen) | Generated reference |
| `docs/lib-modules.md`, `docs/commands.md`, `docs/REFCARD.md`, `docs/index.md`, `README.md`, `mkdocs.yml` (modify) | Tables, counts 28→33, nav |
| `docs/tutorials/cran-submission-with-rforge.md` (create) | End-to-end CRAN tutorial |
| `CHANGELOG.md`, 4 version sources, `.STATUS`, `CLAUDE.md` (modify) | v2.2.0 release metadata |

---

## Task 1: `dispatched` status (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_status_dispatched_for_winbuilder_on_success():
    assert rcmd._status_for("winbuilder", {}, 0) == "dispatched"
    assert rcmd._status_for("rhub", {}, 0) == "dispatched"

def test_status_dispatched_engine_missing_is_error():
    # engine_missing takes precedence (downgraded later in run())
    assert rcmd._status_for("winbuilder", {"engine_missing": ["devtools"]}, 0) == "error"

def test_main_dispatched_exits_zero(tmp_path, monkeypatch, capsys):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"run_url":"https://x"}', 0))
    rc = rcmd.main(["--kind", "rhub", "--path", str(tmp_path)])
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "dispatched" and rc == 0
```

- [ ] **Step 2: Run → FAIL** (`python3 -m pytest tests/test_rcmd.py -k dispatched -v`)

- [ ] **Step 3: Implement** — in `_status_for`, before the final fallthrough:

```python
    if kind in ("winbuilder", "rhub"):
        return "dispatched" if exit_code == 0 else "error"
```

In `normalize`, add blocks:

```python
    elif kind == "winbuilder":
        env["winbuilder"] = {"submitted": raw.get("submitted", True),
                             "note": raw.get("note", "results emailed to the "
                                     "DESCRIPTION maintainer; check inbox")}
    elif kind == "rhub":
        env["rhub"] = {"run_url": raw.get("run_url"),
                       "note": raw.get("note", "dispatched to GitHub Actions; "
                               "check the repo's Actions tab")}
```

`main()` already returns `0 if status != "error"`, so `dispatched` → exit 0 (no change). Add a comment noting this.

- [ ] **Step 4: Run → PASS.**  **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): add dispatched status for async winbuilder/rhub

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: CRAN NOTE classifier on `r:check` (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_classify_notes_spurious_vs_real():
    notes = ["New submission", "checking foo ... NOTE\n  undefined global bar"]
    out = rcmd._classify_notes(notes)
    assert out[0]["kind"] == "spurious" and out[0]["reason"]
    assert out[1]["kind"] == "real"

def test_normalize_check_includes_notes_classified():
    raw = {"errors": [], "warnings": [], "notes": ["New submission"]}
    env = rcmd.normalize("check", raw, 0, None)
    assert env["check"]["notes_classified"][0]["kind"] == "spurious"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** — add near the top of `lib/rcmd.py`:

```python
SPURIOUS_NOTE_PATTERNS = [
    (r"New submission", "expected on first submission"),
    (r"Days since last update", "resubmitting within CRAN cadence; expected"),
    (r"checking CRAN incoming feasibility", "informational; incoming checks only"),
    (r"[Pp]ossibly misspelled words in DESCRIPTION",
     "CRAN spell-checker flags proper nouns / technical terms"),
    (r"installed size is", "size note; justify in cran-comments if irreducible"),
]

def _classify_notes(notes) -> list:
    out = []
    for n in _as_list(notes):
        kind, reason = "real", None
        for pat, why in SPURIOUS_NOTE_PATTERNS:
            if re.search(pat, str(n)):
                kind, reason = "spurious", why
                break
        out.append({"text": n, "kind": kind, "reason": reason})
    return out
```

In `normalize`'s `kind == "check"` block, after building `env["check"]`:

```python
        env["check"]["notes_classified"] = _classify_notes(raw.get("notes"))
```

> `_status_for("check", ...)` is UNCHANGED — still `warn` if any note. The
> "all notes are spurious" judgment is made by `_run_cran_prep` (Task 7) for the
> `ready` verdict, not by the raw check status.

- [ ] **Step 4: Run → PASS.**  **Step 5: Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py
git commit -m "feat(rcmd): classify CRAN NOTEs (spurious vs real) on check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 6: Retrofit `commands/r/check.md`** — under Output Format, add:

```markdown
### NOTE classification
{For each check.notes_classified: "🟢 expected — {text}" (kind=spurious) or
 "🔴 needs attention — {text}" (kind=real)}
```

Commit: `docs(r:check): show classified NOTEs in report`.

---

## Task 3: `revdep` kind + command (TDD)

**Files:** Modify `lib/rcmd.py`, create `commands/r/revdep.md`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_r_snippet_revdep_uses_revdepcheck():
    src = rcmd.r_snippet("revdep", "/tmp/foo")
    assert "revdepcheck" in src and "jsonlite::toJSON" in src

def test_normalize_revdep_broken_is_error():
    env = rcmd.normalize("revdep", {"broken": ["pkgA"], "new_problems": []}, 0, None)
    assert env["status"] == "error" and env["revdep"]["broken"] == ["pkgA"]

def test_normalize_revdep_clean_is_ok():
    env = rcmd.normalize("revdep", {"broken": [], "new_problems": []}, 0, None)
    assert env["status"] == "ok"

def test_normalize_revdep_new_problems_is_warn():
    env = rcmd.normalize("revdep", {"broken": [], "new_problems": ["pkgB"]}, 0, None)
    assert env["status"] == "warn"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.**

`_status_for` — add before fallthrough:

```python
    if kind == "revdep":
        if raw.get("broken"):
            return "error"
        return "warn" if raw.get("new_problems") else "ok"
```

`normalize` — add block:

```python
    elif kind == "revdep":
        env["revdep"] = {"broken": _as_list(raw.get("broken")),
                         "new_problems": _as_list(raw.get("new_problems")),
                         "failures": _as_list(raw.get("failures"))}
```

`r_snippet` — add (**VERIFY LIVE**: confirm `revdepcheck` summary accessor names against the installed version before trusting field mapping):

```python
    if kind == "revdep":
        return _guard("revdepcheck",
            f'revdepcheck::revdep_check({p}, num_workers=4, quiet=TRUE); '
            f'br <- tryCatch(revdepcheck::revdep_summary({p}), error=function(e) list()); '
            f'broken <- tryCatch(names(Filter(function(x) isTRUE(x$status=="-"), br)), '
            f'error=function(e) character()); '
            f'cat(jsonlite::toJSON(list(broken=broken, new_problems=character(), '
            f'failures=character()), auto_unbox=TRUE, null="list"))')
```

> The `revdep_summary` shape is unverified. Task 9 MUST confirm and adjust the
> `broken`/`new_problems`/`failures` extraction. Keep the envelope keys stable.

Add `"revdepcheck"` to `OPTIONAL_ENGINES` and `INSTALL_HINT`.

Add `"revdep"` to `main()`'s `--kind` choices.

- [ ] **Step 4: Create `commands/r/revdep.md`**

````markdown
---
name: rforge:r:revdep
description: Reverse-dependency check against CRAN downstream packages (revdepcheck)
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Reverse-Dependency Check

Run `revdepcheck::revdep_check()` — a hard CRAN obligation for API-changing
updates. **External CRAN downstream deps**, distinct from rforge's internal
`/rforge:deps`/`/rforge:impact` (ecosystem edges).

`revdepcheck` is optional — if `engine_missing` includes it, report 🟡 + hint.
Note: this can be slow (it builds downstream packages).

## Process
```bash
python3 -m lib.rcmd --kind revdep --path "<path>"
```

## Output Format
```markdown
## Reverse Dependencies: {package} v{version}
### Status: {🟢 none broken / 🟡 new problems / 🔴 broken downstream}
- Broken: {revdep.broken}
- New problems: {revdep.new_problems}
{If broken/problems: list each; point at revdep/problems.md}
### Recommended Actions
{Contact affected maintainers ≥2 weeks ahead; note in submission. Or "clean ✅"}
```

## Related Commands
- `/rforge:r:cran-prep` — runs revdep as part of the submission gate
- `/rforge:deps` / `/rforge:impact` — **internal** ecosystem deps (not CRAN downstream)
````

- [ ] **Step 5: Run tests → PASS. Commit**

```bash
git add lib/rcmd.py tests/test_rcmd.py commands/r/revdep.md
git commit -m "feat(r): r:revdep — reverse-dependency check (revdepcheck)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `goodpractice` kind + command (opt-in) (TDD)

**Files:** Modify `lib/rcmd.py`, create `commands/r/goodpractice.md`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_r_snippet_goodpractice_uses_gp():
    assert "goodpractice::gp" in rcmd.r_snippet("goodpractice", "/tmp/foo")

def test_normalize_goodpractice_warns_with_items():
    env = rcmd.normalize("goodpractice", {"checks": ["avoid T/F"]}, 0, None)
    assert env["status"] == "warn" and env["goodpractice"]["count"] == 1

def test_normalize_goodpractice_clean_ok():
    assert rcmd.normalize("goodpractice", {"checks": []}, 0, None)["status"] == "ok"
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.**

`_status_for` — add: `if kind == "goodpractice": return "warn" if raw.get("checks") else "ok"`

`normalize` — add:

```python
    elif kind == "goodpractice":
        checks = _as_list(raw.get("checks"))
        env["goodpractice"] = {"count": len(checks), "checks": checks}
```

`r_snippet` — add (**VERIFY LIVE**: confirm how to extract failed checks from a `gp` object):

```python
    if kind == "goodpractice":
        return _guard("goodpractice",
            f'g <- goodpractice::gp({p}); '
            f'ck <- tryCatch(as.character(goodpractice::failed_checks(g)), '
            f'error=function(e) character()); '
            f'cat(jsonlite::toJSON(list(checks=ck), auto_unbox=TRUE, null="list"))')
```

Add `"goodpractice"` to `OPTIONAL_ENGINES`, `INSTALL_HINT`, and `main()` choices.

- [ ] **Step 4: Create `commands/r/goodpractice.md`** (mirror revdep; note it
  **re-runs check+lint+covr** so it's advisory/opt-in, not part of `r:cycle`;
  Related Commands cross-link `r:check`/`r:lint`/`r:coverage` with the overlap note).

- [ ] **Step 5: Run → PASS. Commit** `feat(r): r:goodpractice — advisory best-practice bundle (opt-in)`

---

## Task 5: `winbuilder` + `rhub` kinds + commands (dispatch) (TDD)

**Files:** Modify `lib/rcmd.py`, create `commands/r/{winbuilder,rhub}.md`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests**

```python
# append to tests/test_rcmd.py
def test_r_snippet_winbuilder_guards_devtools():
    src = rcmd.r_snippet("winbuilder", "/tmp/foo")
    assert "devtools::check_win_devel" in src and 'requireNamespace("devtools"' in src

def test_r_snippet_rhub_uses_rhub_check():
    src = rcmd.r_snippet("rhub", "/tmp/foo")
    assert "rhub::rhub_check" in src

def test_run_winbuilder_missing_devtools_warns(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    monkeypatch.setattr(rcmd, "_invoke_r", lambda s: ('{"engine_missing":["devtools"]}', 0))
    env = rcmd.run("winbuilder", str(tmp_path))
    assert env["status"] == "warn"  # optional engine downgrade
    assert any("devtools" in m for m in env["messages"])
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement.**

`r_snippet` — add (**VERIFY LIVE** for rhub run-URL capture):

```python
    if kind == "winbuilder":
        return _guard("devtools",
            f'devtools::check_win_devel({p}); '
            f'cat(jsonlite::toJSON(list(submitted=TRUE), auto_unbox=TRUE))')
    if kind == "rhub":
        return _guard("rhub",
            f'rhub::rhub_setup({p}); '              # idempotent; writes workflow
            f'rhub::rhub_check({p}); '
            f'cat(jsonlite::toJSON(list(run_url=NA), auto_unbox=TRUE))')
```

Add `"devtools"` and `"rhub"` to `OPTIONAL_ENGINES` + `INSTALL_HINT`; add
`"winbuilder"`, `"rhub"` to `main()` choices. (`_status_for`/`normalize` blocks
from Task 1 already cover them.)

- [ ] **Step 4: Create `commands/r/winbuilder.md` and `commands/r/rhub.md`** —
  both report status 🚀 **dispatched**; `winbuilder` says "results emailed";
  `rhub` surfaces `rhub.run_url` + "check the Actions tab"; both note the
  optional-engine 🟡 degrade. `rhub.md` warns that first run commits a GH Actions
  workflow (`rhub_setup`) and needs a GitHub remote.

- [ ] **Step 5: Run → PASS. Commit** `feat(r): r:winbuilder + r:rhub — multi-platform dispatch`

---

## Task 6: `cran-comments.md` generator (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing test** — pure-Python generator from envelopes (no R):

```python
# append to tests/test_rcmd.py
def test_cran_comments_lists_real_and_spurious_notes():
    check_env = {"check": {"errors": [], "warnings": [], "notes": ["New submission"],
                 "notes_classified": [{"text": "New submission", "kind": "spurious",
                                       "reason": "expected on first submission"}]}}
    revdep_env = {"revdep": {"broken": [], "new_problems": []}}
    text = rcmd.render_cran_comments("foo", "0.2.0", check_env, revdep_env)
    assert "## R CMD check results" in text
    assert "0 errors | 0 warnings | 1 note" in text
    assert "New submission" in text and "expected on first submission" in text
    assert "## Reverse dependencies" in text
    assert "no downstream dependencies" in text.lower()
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `render_cran_comments` (pure function, no I/O):

```python
def render_cran_comments(package: str, version: str,
                         check_env: dict, revdep_env: dict | None) -> str:
    chk = check_env.get("check", {})
    ne, nw = len(chk.get("errors", [])), len(chk.get("warnings", []))
    classified = chk.get("notes_classified", [])
    nn = len(classified)
    lines = [f"## R CMD check results", "",
             f"{ne} errors | {nw} warnings | {nn} note{'s' if nn != 1 else ''}", ""]
    if classified:
        lines.append("Remaining NOTEs:")
        for c in classified:
            tag = "expected" if c["kind"] == "spurious" else "NEEDS REVIEW"
            reason = f" — {c['reason']}" if c.get("reason") else ""
            lines.append(f"* [{tag}] {c['text'].splitlines()[0]}{reason}")
        lines.append("")
    lines += ["## Reverse dependencies", ""]
    rv = (revdep_env or {}).get("revdep", {})
    broken = rv.get("broken", [])
    if not revdep_env:
        lines.append("There are currently no downstream dependencies for this package.")
    elif broken:
        lines.append(f"Broke {len(broken)} package(s): {', '.join(broken)} — "
                     "maintainers notified.")
    else:
        lines.append("All reverse dependencies passed (see revdep/cran.md).")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run → PASS. Commit** `feat(rcmd): cran-comments.md generator`

---

## Task 7: `_run_cran_prep` orchestrator (TDD)

**Files:** Modify `lib/rcmd.py`; Test `tests/test_rcmd.py`

- [ ] **Step 1: Failing tests** (mock `run()`):

```python
# append to tests/test_rcmd.py
def test_cran_prep_stops_at_hard_error(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    calls = []
    def fake_run(kind, path, **kw):
        calls.append(kind)
        status = "error" if kind == "test" else "ok"
        return {"kind": kind, "status": status, "engine_missing": [], "messages": [],
                "check": {"errors": [], "warnings": [], "notes": [], "notes_classified": []}}
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path))
    assert env["status"] == "blocked" and env["failed_stage"] == "test"
    assert "check" not in calls  # stopped before the gate

def test_cran_prep_ready_when_clean(tmp_path, monkeypatch):
    _write_desc(tmp_path, "foo", "0.2.0")
    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok", "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [], "notes": [], "notes_classified": []}
        if kind == "revdep":
            base["revdep"] = {"broken": [], "new_problems": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path), no_revdep=False)
    assert env["status"] == "ready"
    assert env["cran_comments_path"].endswith("cran-comments.md")

def test_cran_prep_warn_on_real_note(tmp_path, monkeypatch):
    _write_desc(tmp_path)
    def fake_run(kind, path, **kw):
        base = {"kind": kind, "status": "ok" if kind != "check" else "warn",
                "engine_missing": [], "messages": []}
        if kind == "check":
            base["check"] = {"errors": [], "warnings": [],
                             "notes": ["undefined global"],
                             "notes_classified": [{"text": "undefined global",
                                                   "kind": "real", "reason": None}]}
        if kind == "revdep":
            base["revdep"] = {"broken": [], "new_problems": []}
        return base
    monkeypatch.setattr(rcmd, "run", fake_run)
    env = rcmd._run_cran_prep(str(tmp_path))
    assert env["status"] == "warn"   # real NOTE → not "ready"
    assert any("real NOTE" in b or "real note" in b.lower() for b in env["blockers"])
```

- [ ] **Step 2: Run → FAIL.**

- [ ] **Step 3: Implement** `_run_cran_prep` (reuses `run()`; writes the file):

```python
from pathlib import Path as _Path

def _run_cran_prep(path: str = ".", *, no_revdep: bool = False,
                   goodpractice: bool = False, multi_platform: bool = False) -> dict:
    pkg = find_package(path)
    if pkg is None:
        return {"kind": "cran-prep", "status": "blocked", "engine_missing": [],
                "blockers": ["No DESCRIPTION — try /rforge:detect"], "stages": [],
                "messages": []}
    stages, blockers, dispatched = [], [], []
    check_env = revdep_env = None

    def stage(kind, **kw):
        env = run(kind, path, **kw)
        stages.append({"kind": kind, "status": env["status"]})
        return env

    # 1-7: hard sequence (stop at first ERROR)
    for kind in ("document", "lint", "spell", "urlcheck", "test", "coverage"):
        env = stage(kind)
        if env["status"] == "error":
            blockers.append(f"{kind} failed")
            return _cran_prep_envelope(pkg, "blocked", stages, blockers, dispatched,
                                       failed_stage=kind)
    check_env = stage("check", as_cran=True)
    if check_env["status"] == "error":
        blockers.append("R CMD check --as-cran failed (errors/warnings)")
        return _cran_prep_envelope(pkg, "blocked", stages, blockers, dispatched,
                                   failed_stage="check")
    real_notes = [c for c in check_env.get("check", {}).get("notes_classified", [])
                  if c.get("kind") == "real"]
    if real_notes:
        blockers.append(f"{len(real_notes)} real NOTE(s) need attention")

    # 8: revdep (skip if opted out)
    if not no_revdep:
        revdep_env = stage("revdep")
        if revdep_env["status"] == "error":
            blockers.append("reverse dependencies broken")

    # 9: goodpractice (opt-in, advisory — never blocks)
    if goodpractice:
        stage("goodpractice")

    # 10: multi-platform dispatch (async)
    if multi_platform:
        for kind in ("winbuilder", "rhub"):
            env = stage(kind)
            if env["status"] == "dispatched":
                dispatched.append(kind)

    # 11: cran-comments.md
    text = render_cran_comments(pkg["package"], pkg.get("version", ""),
                                check_env, revdep_env)
    cc_path = _Path(path) / "cran-comments.md"
    cc_path.write_text(text)

    status = "ready" if not blockers else "warn"
    return _cran_prep_envelope(pkg, status, stages, blockers, dispatched,
                               cran_comments_path=str(cc_path))

def _cran_prep_envelope(pkg, status, stages, blockers, dispatched, **extra):
    env = {"kind": "cran-prep", "status": status,
           "package": pkg.get("package", ""), "version": pkg.get("version", ""),
           "stages": stages, "blockers": blockers, "dispatched": dispatched,
           "engine_missing": [], "messages": [],
           "handoff": "ready for /rforge:release ecosystem sequencing"
                      if status == "ready" else "not yet CRAN-ready"}
    env.update(extra)
    return env
```

> NOTE: `cran-prep` uses its own status vocab (`ready`/`warn`/`blocked`) — it is an
> orchestrator like `_run_cycle`, not a single-engine kind, so it bypasses
> `_status_for`/`normalize`.

- [ ] **Step 4: Wire `main()`** — add `cran-prep` to choices and the flags;
  route like `cycle`:

```python
    ap.add_argument("--goodpractice", action="store_true")
    ap.add_argument("--multi-platform", action="store_true")
    ap.add_argument("--no-revdep", action="store_true")
    ...
    elif ns.kind == "cran-prep":
        env = _run_cran_prep(ns.path, no_revdep=ns.no_revdep,
                             goodpractice=ns.goodpractice,
                             multi_platform=ns.multi_platform)
    ...
    # exit: blocked → 1, else 0
    return 0 if env.get("status") not in ("error", "blocked") else 1
```

- [ ] **Step 5: Run full suite → PASS. Commit** `feat(rcmd): r:cran-prep orchestrator + readiness envelope`

---

## Task 8: `r:cran-prep` command file + reference regen

**Files:** Create `commands/r/cran-prep.md`; regen `docs/reference/rcmd.md`

- [ ] **Step 1: Create `commands/r/cran-prep.md`**

````markdown
---
name: rforge:r:cran-prep
description: Per-package CRAN-readiness gate — runs the full pre-submission sequence
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
  - name: goodpractice
    description: Also run the advisory goodpractice bundle
    required: false
    type: boolean
    default: false
  - name: multi-platform
    description: Dispatch win-builder + R-hub (async)
    required: false
    type: boolean
    default: false
  - name: no-revdep
    description: Skip the reverse-dependency check
    required: false
    type: boolean
    default: false
---

# R Package CRAN-Prep Gate

Run the full per-package CRAN-readiness sequence and generate `cran-comments.md`.
Composes with `/rforge:release` (this = single-package gate; release = cross-package
submission ordering).

## Process
```bash
python3 -m lib.rcmd --kind cran-prep --path "<path>"   # + --goodpractice / --multi-platform / --no-revdep
```

## Output Format
```markdown
## CRAN-Prep: {package} v{version}
### Status: {🟢 ready / 🟡 warn (open notes) / 🔴 blocked}
| Stage | Result |
|-------|--------|
{one row per stages[] with its status dot}
{If blockers: "### Blockers" list}
{If dispatched: "### Dispatched (async)" — winbuilder/rhub + where to check}
- cran-comments.md: {cran_comments_path}
### Next
{If ready: "→ hand off to /rforge:release for submission ordering"}
{else: fix blockers and re-run}
```

## Related Commands
- `/rforge:release` — ecosystem-level submission ordering (consumes this verdict)
- `/rforge:r:revdep`, `/rforge:r:check`, `/rforge:r:winbuilder`, `/rforge:r:rhub` — individual stages
- `/rforge:r:cycle` — quick dev loop (doc→test→check); cran-prep is the submission gate
````

- [ ] **Step 2: Regenerate reference + verify gate**

```bash
python3 scripts/gen_lib_reference.py && python3 scripts/gen_lib_reference.py --check
bash tests/test-all.sh 2>&1 | tail -3   # frontmatter + uniqueness + 4-version + rcmd smoke
```
Expected: gen-check exit 0; test-all green (command-name uniqueness passes with 5 new files).

- [ ] **Step 3: Commit** `feat(r): r:cran-prep command + reference regen`

---

## Task 9: Live R sanity (MANDATORY — needs R) + snippet fixes

**Files:** possibly `lib/rcmd.py` (snippet corrections)

- [ ] **Step 1:** Build/refresh a scratch package (reuse the v2.1.0 `/tmp/rcmdsanity/foo` pattern, or any real package). Install the optional engines you can: `Rscript -e 'install.packages(c("revdepcheck","goodpractice"))'` (rhub/devtools optional).
- [ ] **Step 2:** Run each new kind and INSPECT the JSON envelope:

```bash
python3 -m lib.rcmd --kind check --as-cran --path <pkg>   # confirm notes_classified populated
python3 -m lib.rcmd --kind revdep --path <pkg>            # VERIFY revdep_summary mapping
python3 -m lib.rcmd --kind goodpractice --path <pkg>      # VERIFY failed_checks extraction
python3 -m lib.rcmd --kind cran-prep --path <pkg>         # full sequence + cran-comments.md written
```

- [ ] **Step 3:** Fix any snippet whose JSON fields don't match the real R object
  (the `revdep_summary` / `goodpractice::failed_checks` accessors are the prime
  suspects — same class of bug as v2.1.0's `urlchecker` columns). Re-run pytest.
- [ ] **Step 4: Commit** any fixes: `fix(rcmd): correct <kind> field mapping per live R`

---

## Task 10: Docs, version bump, full gate, PR

**Files:** docs + version sources + `.STATUS` + `CLAUDE.md`

- [ ] **Step 1: Docs** — add the 5 commands to `docs/commands.md` (new "CRAN
  submission" group), `docs/REFCARD.md`, `README.md`, `docs/index.md` (+ "What's
  new in v2.2.0"); update all `28`→`33` counts; extend `docs/lib-modules.md`
  (new kinds + `dispatched` status + gate/dispatch/advisory tiers); add
  `mkdocs.yml` nav for the new tutorial + any pages.
- [ ] **Step 2: New tutorial** `docs/tutorials/cran-submission-with-rforge.md` —
  end-to-end: `r:cran-prep` → read blockers → fix → re-run → `--multi-platform`
  → review `cran-comments.md` → handoff to `/rforge:release`. Add to nav + tutorials/README.
- [ ] **Step 3: CLAUDE.md** — current-state → v2.2.0, 33 commands, new kinds,
  backlog (Phase 4 → v2.3.0). Test-gate counts if they changed.
- [ ] **Step 4: Version bump to 2.2.0** — 4 sources (plugin.json, marketplace.json
  ×2, package.json) + live-version doc refs per CLAUDE.md. CHANGELOG `[Unreleased]`
  → `## [2.2.0] - <date>` listing the 5 commands + check enhancement.
- [ ] **Step 5: Grep** `grep -rn "2\.1\.0" --include='*.md' --include='*.json' . | grep -iv changelog` → no stale live refs.
- [ ] **Step 6: `.STATUS`** — record the feature; worktrees entry.
- [ ] **Step 7: Both gates**

```bash
python3 -m pytest tests/ -v          # 110 + ~25 new
bash tests/test-all.sh                # all green
```

- [ ] **Step 8: PR**

```bash
git -C ~/.git-worktrees/rforge/feature-r-cran-prep fetch origin dev
git -C ~/.git-worktrees/rforge/feature-r-cran-prep rebase origin/dev
gh pr create --base dev --title "feat: CRAN-submission suite — r:cran-prep + revdep/goodpractice/winbuilder/rhub (v2.2.0)" \
  --body "Implements docs/specs/SPEC-r-cran-prep-2026-06-01.md. 5 new r: commands + r:check NOTE classifier; 28→33; v2.2.0."
```

- [ ] **Step 9: After merge** — delete `ORCHESTRATE-r-cran-prep.md` (per CLAUDE.md), `git worktree remove`, update `.STATUS`.

---

## Self-Review (completed by plan author)

- **Spec coverage:** dispatched status (T1) · NOTE classifier + check.md (T2) · revdep (T3) · goodpractice opt-in (T4) · winbuilder+rhub dispatch w/ devtools guard (T5) · cran-comments generator (T6) · cran-prep orchestrator + readiness envelope + hybrid early-stop (T7) · command file + reference (T8) · live sanity (T9) · docs/version/dedup (T10). ✅
- **Placeholder scan:** no TBD/TODO; full code in every code step. The "VERIFY LIVE" markers on revdep/goodpractice/rhub snippets are explicit risk flags with a dedicated verification task (T9), not deferred work. ✅
- **Type consistency:** envelope keys (`revdep`/`goodpractice`/`winbuilder`/`rhub`/`check.notes_classified`, `dispatched` status, cran-prep `ready/blocked/warn` + `blockers`/`stages`/`cran_comments_path`) match across `_status_for`, `normalize`, `_run_cran_prep`, `render_cran_comments`, and command renders. `run()` reused by `_run_cran_prep` (no duplication). `render_cran_comments` signature `(package, version, check_env, revdep_env)` consistent T6↔T7. ✅
- **No duplicates:** no name collisions (5 new `r:` names); cran-prep calls `run()`; revdep ≠ internal deps; goodpractice opt-in + dedup note; cran-comments is an artifact. ✅

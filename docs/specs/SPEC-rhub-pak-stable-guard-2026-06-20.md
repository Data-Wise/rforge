# SPEC: rhub.yaml pak-version Guard (r:rhub pre-flight check)
**Date:** 2026-06-20
**Status:** READY — fix already shipped; spec drives rforge integration
**Scope:** `r:rhub` command (new, per SPEC-rhub-platform-selection-2026-06-19) + `lib/rcmd.py`
**Priority:** High — blocks real CI submissions silently

---

## Background

`r-hub/actions/setup-deps@v1` defaults to installing `pak` from the **devel** track
(`0.10.0.9000`). As of 2026-06-13, that version has a bootstrap regression
([r-lib/pak #887](https://github.com/r-lib/pak/issues/887)): the binary installs but
`loadNamespace('pak')` fails immediately with no helpful error message. All rhub
checks silently fail.

The fix is a one-line addition to each `setup-deps` step:

```yaml
- uses: r-hub/actions/setup-deps@v1
  with:
    pak-version: stable   # ← this line; without it, devel pak fails
    token: ${{ secrets.RHUB_TOKEN }}
    job-config: ${{ matrix.config.job-config }}
```

### What was patched (manual hotfix, 2026-06-20)

Both `setup-deps` occurrences (linux-containers job + other-platforms job) in:
- `medrobust/.github/workflows/rhub.yaml` — committed `48f9ce8`
- `rmediation/.github/workflows/rhub.yaml` — committed `5f9be98`

### Why rforge must guard this

Users who run `r:rhub` from the future `r:rhub` command (see
`SPEC-rhub-platform-selection-2026-06-19.md`) will hit the same failure silently if
their `rhub.yaml` lacks `pak-version: stable`. The failure mode is invisible:
rhub dispatches the GH Actions workflow successfully, but every job fails with an
opaque bootstrap error — no rforge surface shows this.

---

## User Story

**As** an R package developer using `r:rhub`,
**I want** rforge to detect that my `rhub.yaml` is missing `pak-version: stable`
**so that** I know to fix it before submitting checks that will silently fail.

---

## Acceptance Criteria

1. When `r:rhub` is invoked (or a new `r:rhub-check` pre-flight), rforge reads
   `.github/workflows/rhub.yaml` and checks every `setup-deps` block.
2. If any block is missing `pak-version: stable`, rforge emits a `warn` advisory
   with:
   - the finding code `rhub_pak_devel_regression`
   - a clear message referencing r-lib/pak #887
   - the exact YAML snippet to add
3. The warning does not block the submission (advisory only — the user may have
   intentionally pinned a different version).
4. If `pak-version: stable` is present in all blocks, no advisory is emitted.
5. If `rhub.yaml` is absent entirely, a separate advisory (`rhub_yaml_missing`,
   already in SPEC-rhub-platform-selection-2026-06-19) handles it — no
   double-warning from this check.

---

## Implementation Plan

### Phase 1 — Static YAML check in lib/rcmd.py (< 1 hr)

Add a helper `_check_rhub_yaml(pkg_path)` that:

```python
def _check_rhub_yaml(pkg_path: str) -> list[dict]:
    """
    Check .github/workflows/rhub.yaml for known misconfigurations.
    Returns a list of finding dicts (empty = clean).
    """
    import re
    yaml_path = Path(pkg_path) / ".github" / "workflows" / "rhub.yaml"
    if not yaml_path.exists():
        return []  # rhub_yaml_missing is a separate check

    content = yaml_path.read_text()

    findings = []

    # Locate every setup-deps block and verify pak-version: stable is present
    # Strategy: find each `- uses: r-hub/actions/setup-deps` and scan the
    # following `with:` block for a pak-version line.
    blocks = re.split(r'- uses: r-hub/actions/setup-deps', content)
    # blocks[0] = content before first occurrence; blocks[1:] = after each
    for i, block in enumerate(blocks[1:], 1):
        # Extract the with: block (lines until next `- uses:` or end of job)
        with_match = re.search(r'\s+with:\s*((?:\s+\S.*\n)*)', block)
        if not with_match:
            continue
        with_block = with_match.group(1)
        if "pak-version:" not in with_block:
            findings.append({
                "code": "rhub_pak_devel_regression",
                "severity": "warn",
                "block": i,
                "message": (
                    f"setup-deps block {i} is missing `pak-version: stable`. "
                    "pak devel (0.10.0.9000) has a loadNamespace bootstrap "
                    "regression (r-lib/pak #887, filed 2026-06-13) — rhub jobs "
                    "will silently fail. Add `pak-version: stable` as the first "
                    "`with:` entry in this block."
                ),
                "fix": (
                    "- uses: r-hub/actions/setup-deps@v1\n"
                    "  with:\n"
                    "    pak-version: stable\n"
                    "    token: ${{ secrets.RHUB_TOKEN }}\n"
                    "    job-config: ${{ matrix.config.job-config }}"
                ),
            })

    return findings
```

Wire into `run("rhub", ...)` pre-flight (before dispatching `rhub_check()`):

```python
if kind == "rhub":
    findings = _check_rhub_yaml(path)
    if findings:
        return {
            "kind": "rhub",
            "status": "warn",
            "findings": findings,
            "messages": [f["message"] for f in findings],
            "engine_missing": [],
        }
    # ... proceed with normal rhub dispatch
```

### Phase 2 — commands/r/rhub.md prompt wiring

In the new `r:rhub` command prompt (from SPEC-rhub-platform-selection), add a section:

```markdown
## Pre-flight checks

Before dispatching, run `python3 -m lib.rcmd --kind rhub --path <pkg> --preflight-only`
to surface:
- missing `rhub.yaml` → warn and stop
- missing `pak-version: stable` → warn (finding code: rhub_pak_devel_regression)
- broken platform (e.g., `macos`) → hard-block

If any WARN findings are present, surface them before asking the user to proceed.
```

### Phase 3 — Test gates

Add to `tests/test_rcmd.py` (or a new `tests/test_rcmd_rhub.py`):

```python
def test_rhub_yaml_missing_pak_version_fires(tmp_path):
    """setup-deps block without pak-version: stable → rhub_pak_devel_regression."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
        "          job-config: ${{ matrix.config.job-config }}\n"
    )
    findings = rcmd._check_rhub_yaml(str(tmp_path))
    codes = {f["code"] for f in findings}
    assert "rhub_pak_devel_regression" in codes


def test_rhub_yaml_with_pak_stable_clean(tmp_path):
    """setup-deps block with pak-version: stable → no findings."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
        "          job-config: ${{ matrix.config.job-config }}\n"
    )
    findings = rcmd._check_rhub_yaml(str(tmp_path))
    assert findings == []


def test_rhub_yaml_missing_entirely_no_findings(tmp_path):
    """No rhub.yaml → _check_rhub_yaml returns [] (separate check handles absence)."""
    findings = rcmd._check_rhub_yaml(str(tmp_path))
    assert findings == []


def test_rhub_yaml_multiple_blocks_one_missing(tmp_path):
    """Two setup-deps blocks; second missing pak-version → finding for block 2 only."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "rhub.yaml").write_text(
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          pak-version: stable\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
        "      - uses: r-hub/actions/setup-deps@v1\n"
        "        with:\n"
        "          job-config: ${{ matrix.config.job-config }}\n"
        "          token: ${{ secrets.RHUB_TOKEN }}\n"
    )
    findings = rcmd._check_rhub_yaml(str(tmp_path))
    assert len(findings) == 1
    assert findings[0]["block"] == 2
```

---

## Known Instability Window

This guard is a **temporary workaround** for pak #887. Once r-lib/pak ships a fix in
devel and r-hub/actions/setup-deps pins a clean devel, the guard can be relaxed to
advisory-only or removed entirely. Watch r-lib/pak #887 for resolution.

**Track with a comment in `_check_rhub_yaml`:**
```python
# TODO: remove or loosen when r-lib/pak #887 is fixed in devel
# Upstream: https://github.com/r-lib/pak/issues/887
```

---

## Non-Goals

- Auto-patching `rhub.yaml` (too invasive; user owns their workflow files)
- Enforcing a specific pak version (stable is the safe default; others may work)
- Backporting to medrobust/rmediation — already fixed manually

---

## Dependency

Implements alongside: `SPEC-rhub-platform-selection-2026-06-19.md`
(`r:rhub` command must exist for Phase 2 wiring; Phase 1 + Phase 3 are standalone).

---

## History

| Date | Change |
|------|--------|
| 2026-06-20 | Spec created; fix already shipped manually in medrobust + rmediation |

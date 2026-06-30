# 🩺 Troubleshooting

!!! tip "TL;DR (30 seconds)"
    - **What:** Symptom-organized error lookup for rforge.
    - **Why:** Find the fix without reading the whole page.
    - **How:** Match your error to a section below → run the suggested command.
    - **Next:** Still stuck? File an issue: <https://github.com/Data-Wise/rforge/issues>

Common errors and how to resolve them. Symptoms are listed first; click
through to the section that matches what you're seeing.

## Quick navigation

- [Install / setup issues](#install-setup-issues)
- [Command not found / not loading](#command-not-found-not-loading)
- [Path errors from `lib/` modules](#path-errors-from-lib-modules)
- [Missing R / Rscript](#missing-r-rscript)
- [`init` / context state issues](#init-context-state-issues)
- [Leftover rforge-mcp signals](#leftover-rforge-mcp-signals)
- [Hook unexpectedly blocks an edit](#hook-unexpectedly-blocks-an-edit)
- [Tests fail after a fresh install](#tests-fail-after-a-fresh-install)

If your issue isn't covered, file an issue:
<https://github.com/Data-Wise/rforge/issues>.

---

## Install / setup issues

### `brew install --HEAD data-wise/tap/rforge` succeeds but plugin doesn't load

Two diagnoses:

```zsh
# 1) Did the install script create the plugin symlink?
ls -la ~/.claude/plugins/rforge
# Expected: a symlink to /opt/homebrew/opt/rforge/libexec

# 2) Is Claude Code seeing the plugin?
# In Claude Code: type "/help" and search for "/rforge:"
```

If the symlink is missing, the post-install script's `ln` step failed
(usually macOS extended-attribute permissions). Fix manually:

```zsh
ln -sf "$(brew --prefix)/opt/rforge/libexec" ~/.claude/plugins/rforge
```

Then restart Claude Code.

---

## Command not found / not loading

### `/rforge:*` commands don't appear in `/help`

Most likely Claude Code hasn't picked up the plugin since install. In
order:

1. Restart Claude Code (quit + reopen)
2. If still missing: `ls ~/.claude/plugins/rforge/commands/` — should
   list 15 `.md` files
3. If empty: re-run install (see [Install issues](#install-setup-issues))

### `/rforge:detect` runs but produces no output

The plugin command is a markdown prompt; Claude has to invoke the
underlying Python module. Check Claude has Bash access (in Claude Code
permissions) and that `lib/discovery.py` is reachable:

```zsh
python3 -m lib.discovery --path . --format text
# Run this from your project's repo root (or the plugin install dir)
```

If Python fails too, see [Path errors](#path-errors-from-lib-modules).

---

## Path errors from `lib/` modules

### `error: path does not exist: /some/path`

You passed a `--path` that doesn't exist (or has a typo). `discovery`,
`status`, and `init` all validate the path before doing anything. Fix
the path or omit `--path` (defaults to current directory).

### `ImportError: attempted relative import with no known parent package`

!!! warning "Symptom: running as a script instead of as a package"
    ```zsh
    python3 lib/deps.py    # ❌ won't work
    ```

!!! success "Fix: use `python3 -m lib.<module>`"
    ```zsh
    python3 -m lib.deps    # ✅ works
    ```

This is intentional — it forces the package layout that prevents
`sys.path` collisions. Use `-m lib.<module>` everywhere.

### `ModuleNotFoundError: No module named 'lib'`

You're running from a directory that doesn't contain the plugin's
`lib/` as a subdirectory. The `-m lib.<module>` form requires
`lib/` to be on `sys.path`, which Python derives from the current
working directory.

```zsh
# ❌ from anywhere
python3 -m lib.discovery

# ✅ from the plugin install dir
cd "$(brew --prefix)/opt/rforge/libexec"
python3 -m lib.discovery --path /your/r/package
```

The plugin commands handle this internally by `cd`-ing to the right
place before invoking. If you're getting this error from a slash
command, it's a bug — file an issue.

---

## Missing R / Rscript

### `lib.status` reports `unknown` for every package's `check`/`test`

!!! note "Expected behavior in v1.3.0+"
    The R subprocess integration is deferred to v1.4.0. `lib.status`
    currently reads `.STATUS` files only — it doesn't shell out to
    `R CMD check` or run test suites. The `unknown` placeholder is
    **intentional**, not a bug.

### Future v1.4.0 behavior

When the 4-mode contract lands, missing R will degrade gracefully:
`default` and `debug` modes will continue to work; `optimize` and
`release` modes will warn and skip the R-requiring checks. Until then,
nothing in v1.3.0 requires R installed.

---

## `init` / context state issues

### `/rforge:init` says "Already initialized" but I'm in a different package

The `~/.rforge/context.json` file is **per-user, not per-package**. It
tracks one active context at a time. To re-init for a new package:

```text
/rforge:init    # in the new package directory
```

The state file gets overwritten with the new package's info. There's no
"multi-context" mode — by design (matches MCP server semantics so
migration is transparent).

If you want a clean slate:

```zsh
rm ~/.rforge/context.json
```

Then re-init.

### Permission denied writing `~/.rforge/context.json`

The directory permissions are off. Fix:

```zsh
mkdir -p ~/.rforge
chmod 755 ~/.rforge
```

Then re-run `/rforge:init`.

---

## Leftover rforge-mcp signals

### `npm` warns about an orphaned `rforge-mcp` install

You upgraded the plugin but didn't uninstall the old MCP server.
Walk through the [migration tutorial](tutorials/migrate-from-mcp.md) —
Step 3 covers the uninstall.

### `~/.claude/settings.json` still has `mcpServers.rforge`

Same fix — see migration tutorial Step 2. The plugin doesn't need this
entry as of v1.3.0; removing it eliminates a stale config reference.

### Claude Code logs say "MCP server `rforge` failed to start"

The MCP server config is still in `~/.claude/settings.json` but the
binary isn't installed (because you uninstalled rforge-mcp, or never
had it). Remove the config block:

```json
// Delete this from ~/.claude/settings.json:
{
  "mcpServers": {
    "rforge": { ... }
  }
}
```

The plugin doesn't need this entry as of v1.3.0 — `lib/` modules run
in-process via the standard Bash tool. There's no rforge MCP server to
reinstall (`rforge-mcp` was never published; it lived as a local
working directory during v1.0–v1.2 development and was tombstoned in
v1.3.0).

---

## Hook unexpectedly blocks an edit

### "Refusing to edit roxygen-generated man/*.Rd file"

!!! warning "This is by design — the hook is protecting you"
    `man/*.Rd` files are auto-generated by `devtools::document()`. Any
    hand-edit gets overwritten the next time you regenerate.

!!! tip "Fix: edit the roxygen comments, not the .Rd file"
    Edit `@param` / `@return` / `@examples` in the corresponding `R/`
    file, then run `devtools::document()` to regenerate `man/*.Rd`.

If you need to bypass this in an emergency (e.g., the regenerator
itself is broken):

```zsh
# Disable the hook for one session
mv ~/.claude/hooks/pretooluse.py.bak ~/.claude/hooks/pretooluse.py.bak.disabled
```

Re-enable when done. See [Hooks & Skills](hooks-and-skills.md) for
details on the 4 hook rules.

### Branch-guard blocks my commit on `dev`

You're trying to commit code (not docs/config) directly to `dev`. Use a
feature worktree:

```zsh
git worktree add ~/.git-worktrees/rforge/feature-<name> -b feature/<name> dev
cd ~/.git-worktrees/rforge/feature-<name>
# do your work here, then PR back to dev
```

Or, for a one-shot emergency:

```zsh
touch .claude/allow-once    # bypass expires after 5 minutes
```

See the global CLAUDE.md "Branch Guard & Git Hooks" section for the
full protection rules.

---

## Tests fail after a fresh install

### `bash tests/test-all.sh` reports `Lib: pytest suite ❌`

The `lib/` tests need `pytest`. Install it:

```zsh
pip install pytest
```

Then re-run. If you don't have pip, install Python's standard build
(>= 3.10) — the `lib/` modules use type hints that require it.

### `Lib: reference docs in sync with source ❌`

You edited a module's docstring but didn't regenerate the reference
docs. Fix:

```zsh
python3 scripts/gen_lib_reference.py
```

Then commit the regenerated `docs/reference/*.md` files. The CI check
(`gen_lib_reference.py --check`) compares the generated output against
disk; any mismatch is treated as drift.

### A specific pytest case fails after my edit

Run it in isolation for the error message:

```zsh
python3 -m pytest tests/test_lib_<module>.py::<test_name> -v
```

If the failure is a real regression in your edit, the test name tells
you which contract you broke. If it's a test-only issue, file as a bug.

---

## Still stuck?

- **Search existing issues:** <https://github.com/Data-Wise/rforge/issues?q=>
- **File a new issue:** include rforge version (`brew list --versions
  rforge`), Claude Code version, the exact command you ran, and the
  full error output. Reproducer is gold.
- **Check the CHANGELOG:** maybe the behavior you're seeing was a
  documented breaking change in a recent version.

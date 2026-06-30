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

!!! warning "Symptom"
    Brew installs clean but `/help` shows no `/rforge:` commands.

!!! success "Fix"
    1. Check the symlink:
       ```zsh
       ls -la ~/.claude/plugins/rforge
       # Expected: a symlink to /opt/homebrew/opt/rforge/libexec
       ```
    2. If missing, the post-install `ln` step failed. Fix:
       ```zsh
       ln -sf "$(brew --prefix)/opt/rforge/libexec" ~/.claude/plugins/rforge
       ```
    3. Restart Claude Code.

---

## Command not found / not loading

### `/rforge:*` commands don't appear in `/help`

!!! warning "Symptom"
    Claude Code doesn't recognize `/rforge:` commands.

!!! success "Fix"
    1. Restart Claude Code (quit + reopen)
    2. If still missing:
       ```zsh
       ls ~/.claude/plugins/rforge/commands/
       ```
       Should list `.md` files. If empty, re-run install.
    3. Still missing? See [Install issues](#install-setup-issues).

### `/rforge:detect` runs but produces no output

!!! warning "Symptom"
    The command runs without error but prints nothing.

!!! success "Fix"
    Check Claude has Bash access (permissions) and the module is reachable:
    ```zsh
    python3 -m lib.discovery --path . --format text
    ```
    If Python fails too, see [Path errors](#path-errors-from-lib-modules).

---

## Path errors from `lib/` modules

### `error: path does not exist: /some/path`

!!! warning "Symptom"
    A command takes a `--path` flag that doesn't exist or has a typo.

!!! success "Fix"
    Correct the path or omit `--path` (defaults to current directory).
    `discovery`, `status`, and `init` all validate the path before
    doing anything.

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

!!! warning "Symptom"
    Running `python3 -m lib.discovery` from outside the plugin directory.

!!! success "Fix"
    Run from the plugin install dir, or let the slash command do it:
    ```zsh
    cd "$(brew --prefix)/opt/rforge/libexec"
    python3 -m lib.discovery --path /your/r/package
    ```
    If you get this from a slash command, it's a bug — file an issue.

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

!!! warning "Symptom"
    `~/.rforge/context.json` is per-user, not per-package — it remembers the
    last package you initialized.

!!! success "Fix"
    Run `/rforge:init` in the new package directory. The state file gets
    overwritten. For a clean slate:
    ```zsh
    rm ~/.rforge/context.json
    ```
    Then re-init.

### Permission denied writing `~/.rforge/context.json`

!!! warning "Symptom"
    The plugin can't write to `~/.rforge/context.json`.

!!! success "Fix"
    ```zsh
    mkdir -p ~/.rforge
    chmod 755 ~/.rforge
    ```
    Then re-run `/rforge:init`.

---

## Leftover rforge-mcp signals

### `npm` warns about an orphaned `rforge-mcp` install

!!! warning "Symptom"
    You upgraded the plugin but didn't uninstall the old MCP server.

!!! success "Fix"
    Walk through the [migration tutorial](tutorials/migrate-from-mcp.md)
    — Step 3 covers the uninstall.

### `~/.claude/settings.json` still has `mcpServers.rforge`

!!! warning "Symptom"
    A stale `settings.json` entry from the pre-v1.3.0 era.

!!! success "Fix"
    Remove the `mcpServers.rforge` block. The plugin doesn't need this
    entry as of v1.3.0 — `lib/` modules run in-process via Bash tool.

### Claude Code logs say "MCP server `rforge` failed to start"

!!! warning "Symptom"
    The MCP server config is still in `settings.json` but the binary
    isn't installed (you uninstalled rforge-mcp, or never had it).

!!! success "Fix"
    Delete this from `~/.claude/settings.json`:
    ```json
    "mcpServers": {
      "rforge": { ... }
    }
    ```
    The plugin doesn't need an MCP server — there's no rforge MCP server
    to reinstall (`rforge-mcp` lived as a local working directory during
    v1.0–v1.2 development and was tombstoned in v1.3.0).

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

!!! warning "Symptom"
    You're trying to commit code (not docs/config) directly to `dev`.

!!! success "Fix"
    Use a feature worktree:
    ```zsh
    git worktree add ~/.git-worktrees/rforge/feature-<name> -b feature/<name> dev
    cd ~/.git-worktrees/rforge/feature-<name>
    # do your work here, then PR back to dev
    ```
    One-shot emergency bypass:
    ```zsh
    touch .claude/allow-once    # expires after 5 minutes
    ```
    See the global CLAUDE.md "Branch Guard & Git Hooks" section for full rules.

---

## Tests fail after a fresh install

### `bash tests/test-all.sh` reports `Lib: pytest suite ❌`

!!! warning "Symptom"
    `pytest` is not installed.

!!! success "Fix"
    ```zsh
    pip install pytest
    ```
    If you don't have pip, install Python >= 3.10 — `lib/` modules use
    type hints that require it.

### `Lib: reference docs in sync with source ❌`

!!! warning "Symptom"
    You edited a module's docstring but didn't regenerate reference docs.

!!! success "Fix"
    ```zsh
    python3 scripts/gen_lib_reference.py
    ```
    Then commit the regenerated `docs/reference/*.md` files. The CI check
    (`gen_lib_reference.py --check`) treats any mismatch as drift.

### A specific pytest case fails after my edit

!!! warning "Symptom"
    An edit broke an existing test.

!!! success "Fix"
    Run it in isolation:
    ```zsh
    python3 -m pytest tests/test_lib_<module>.py::<test_name> -v
    ```
    The test name tells you which contract you broke. If it's a test-only
    regression (not a code bug), file it.

---

## Still stuck?

- **Search existing issues:** <https://github.com/Data-Wise/rforge/issues?q=>
- **File a new issue:** include rforge version (`brew list --versions
  rforge`), Claude Code version, the exact command you ran, and the
  full error output. Reproducer is gold.
- **Check the CHANGELOG:** maybe the behavior you're seeing was a
  documented breaking change in a recent version.

# Contributing

Thank you for your interest in rforge! Here's how to get started.

## Which branch?

rforge uses a multi-branch workflow:

| Branch | Purpose | Code changes allowed? |
|--------|---------|----------------------|
| `main` | Stable releases | ❌ PR only |
| `dev` | Integration, docs, planning | New files ❌, existing edits ✅ |
| `feature/*` | Active development | ✅ |

Start by forking the repository and creating a feature branch from `dev`.

## Development setup

```zsh
# Clone the repo
git clone git@github.com:Data-Wise/rforge.git
cd rforge

# Switch to the integration branch
git checkout dev

# Create a feature worktree for changes
git worktree add ~/.git-worktrees/rforge/feature-<name> -b feature/<name> dev
cd ~/.git-worktrees/rforge/feature-<name>
```

All `lib/` modules are pure-Python (stdlib-only) — no R, npm, or MCP server
required for development.

## What makes a good PR

1. **One concern per PR.** A bugfix, a feature, or a docs improvement — not all
   three.
2. **Tests pass.** Before opening:
   ```zsh
   python3 -m pytest tests/
   bash tests/test-all.sh
   ```
3. **Docs updated.** If you add a command flag, update the command file,
   the guide, `docs/REFCARD.md`, and regenerate lib reference docs:
   ```zsh
   python3 scripts/gen_lib_reference.py
   ```
4. **Version sync check passes.**
   ```zsh
   python3 scripts/version_sync.py --check
   ```
5. **mkdocs builds without warnings.**
   ```zsh
   pip install -r docs/requirements.txt   # if you have docs deps
   mkdocs build --strict
   ```

## Code standards

- **Python**: Type hints on all public functions. Pure-stdlib only (no pip
  dependencies for `lib/` modules).
- **Markdown**: Structured frontmatter for command files. Avoid trailing
  whitespace. Use fenced code blocks with language tags.
- **R snippets** (if touching `lib/rsnippets.py`): Keep the return keys stable.
  Existing callers serialize envelope keys verbatim.
- **Commit messages**: Conventional Commits (`feat:`, `fix:`, `docs:`,
  `refactor:`, `test:`, `chore:`).

## Adding a new command

1. Create `commands/<name>.md` with structured frontmatter (see existing
   commands for the format).
2. Wire it in `package.json` (the command list).
3. Add any needed `lib/` logic.
4. Update the command count in `mkdocs.yml` (`extra.rforge.command_count`).
5. Run `python3 scripts/version_sync.py` to propagate the count.
6. Add tests in `tests/`.
7. Update `docs/commands.md`, `docs/REFCARD.md`, and the relevant guide.
8. Verify: `bash tests/test-all.sh && python3 -m pytest tests/`

## Testing

```zsh
# All Python unit tests
python3 -m pytest tests/ -v

# Full suite (43 checks)
bash tests/test-all.sh

# CLI dogfood tests (new configs that may not ship)
bash tests/cli/automated-tests.sh    # runs in CI
bash tests/cli/e2e-tests.sh          # needs a real R package workspace
```

## Questions?

- Open a [discussion](https://github.com/Data-Wise/rforge/discussions) for
  design questions.
- File an [issue](https://github.com/Data-Wise/rforge/issues) for bugs.
- See [Architecture](architecture.md) and [Lib Modules](lib-modules.md) for
  the internals deep-dive.

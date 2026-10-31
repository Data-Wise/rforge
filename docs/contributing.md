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

Analysis modules are pure Python; R-runner integration tests additionally use R
and preinstalled R dependencies. Missing R prerequisites skip those optional
local tests; they are never installed by the tests.
The test gates need three dev packages (`tests/test-all.sh` warns up front
when any is missing):

```zsh
pip install 'pytest==8.4.2' pyyaml mkdocs-material
```

A2 acceptance jobs select the latest stable Python 3 (`3.x`, checking for the
latest release and excluding prereleases). Each artifact records the exact
interpreter used. The R and fixture dependency versions remain locked in
`tests/a2/fixture-lock.json`; actual Ubuntu 24.04 and macOS 15 evidence is still
required. Local compatibility tests on another supported Python version do not
replace those platform runs.

The local and CI full-suite command lists A2 first so pytest 8 registers its
options before parsing. Pytest is pinned to 8.4.2 because the existing A2 manifest
records its parameter identifiers; pytest 9 changes them. `PYTHONPATH` lets replay
subprocesses import the checkout. This does not refresh frozen release evidence.
The release gate's own command, `python -m pytest tests/ -q -p no:cacheprovider`,
also works under pytest 8.4.2 because `--a2-release` is registered in
`tests/conftest.py`.

Run A2 collection and `scripts/refresh_a2_manifest.py` with `PYTEST_ADDOPTS`
unset (`env -u PYTEST_ADDOPTS ...`). A shell that sets `-q` there turns the
collection command's `-q` into `-qq`, which prints per-file counts instead of node
IDs; the refresh tool then reads "nothing collected" and drops every manifest node.
Check its `dropped N, added N` line and revert on a surprise.
Ordinary dev PRs and dev pushes run fast CI only. The embedded locked-platform
release job runs on `main` or PRs targeting `main`; explicit A2 evidence workflows
remain separate release actions.

## What makes a good PR

1. **One concern per PR.** A bugfix, a feature, or a docs improvement — not all
   three.
2. **Tests pass.** Before opening:
   ```zsh
   PYTHONPATH="$PWD" python3 -m pytest tests/a2 tests/harness tests/test_*.py
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
   pip install mkdocs-material mkdocs-macros-plugin pillow cairosvg
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
8. Verify with the full-suite command in [Testing](#testing), then
   `bash tests/test-all.sh`.

## Testing

```zsh
# All Python unit tests
PYTHONPATH="$PWD" python3 -m pytest tests/a2 tests/harness tests/test_*.py -v

# Full suite (47 checks)
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

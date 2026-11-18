# Docs audit (`/rforge:docs:check`)

!!! tip "TL;DR (30 seconds)"
    - **What:** checks that the calls and signatures in your `README` and `vignettes/` still match what the package exports. Default static, read-only, no R; optional site and README stages below.
    - **Run:** `/rforge:docs:check` in a package (or `--eco` for every package under the ecosystem root).
    - **Read:** `error` = a call that would fail as written; `warn` = a candidate to check by hand; the `checked N of M` line says how much it could see.

## What it checks

| Check | Severity | Fires when |
|---|---|---|
| `signature-named-arg` | error | A documented call names an argument that is not a formal of the exported function. R's partial matching is applied, so `f(conf = .9)` is fine for `conf.level`. |
| `signature-names` | warn | A signature listing (a backticked call that is the whole first cell of a table row, as in a reference card) names a non-formal. |
| `signature-arity` | warn | A call passes more positional arguments than the function has formals. |
| `scannability` | info | A paragraph over 110 words, an H2 section over 800 words with fewer than 3 H3, or a "Next Steps" heading that is not last. Shown with `--detailed`. |
| `coverage` | warn | With `--since <tag>` only: an export added since the tag that no README or vignette mentions. |

Functions with a `...` formal are exempt from the three signature checks, because any name or count is valid there.
Code in an unlabeled fence downgrades `error` to `warn` (it may be console output).

## Reading a report

```text
scope: package medfit at /path/to/medfit
error signature-named-arg  vignettes/intro.qmd:154  `BootstrapResult()` has no argument `converged` (formals: ...)
checked 18 of 22 exported functions (3 no-usage, 1 variadic not checked)
```

1. **The first line is the scope.** "Audited `medfit`" is not "audited the ecosystem".
2. **Read `checked N of M`.** An export with no `\usage` in its Rd, a method behind a generic, or a re-export cannot be checked; a clean report on `checked 1 of 22` proves little.
3. **`INCOMPLETE` or `NOT AUDITED` at the end means the result is not clean**, whatever `status` says: a file was unreadable, a region was too large to scan, or no package was found.
4. **Findings are candidates.** A flagged call may be intentional pseudo-code; check the call before changing the docs.

## Scope

Without an argument it audits the package you are in (walking up to the nearest `DESCRIPTION`). Outside a package it
sweeps the ecosystem only if a `.rforge.yaml` manifest exists or you pass `--eco`; otherwise it says so and exits 0.
A `kind: hybrid` root audits the root package and its nested packages.
The Python CLI option `--package-only` disables both hybrid and manifest
expansion: only the nearest package at an existing path is audited. It does
not discover packages by name and cannot be combined with `--eco`. The Codex
single-package workflow uses this option by default.

## Suppressing a finding

```yaml
# .rforge.yaml (package root)
docs:
  allowlist:
    - vignettes/articles/methods.qmd::scannability   # one check in one file
    - NEWS-draft.md                                    # everything in a file
```

A malformed block is ignored with a message; the suppressed count appears in the summary.

## In a release gate

`--fail-on error` (or `warn`) sets the exit code only; the report is the same. The default is `none` (always exits 0).

## What it does not check

NEWS completeness (see the `description-sync` skill), full-package examples (`/rforge:r:check`), site prose/availability,
prose claims, wrong default values, reordered arguments, and S3/S4/S7 method signatures behind a generic.

## Known limitations

The default static audit reads R text without running it. When a document gives a package function's name to something else,
a later call to that name is skipped rather than judged. It recognizes `f <- ...`, `f <<- ...`, `... -> f`,
`assign("f", ...)`, a statement-level `f = ...` (top level or directly inside `{ }`), `function(f)` and `\(f)`
parameters (backticked names too), and `for (f in ...)`. Bindings it does **not** recognize, which can therefore
still draw a false `error` when the bound name equals an export: `with(list(f = ...), f(...))`, `list2env()`,
`attach()`, `delayedAssign()`, and formula or lambda shorthands. Suppress such a file with `docs.allowlist`
(`<relpath>::signature-named-arg`). Calls the scan cannot finish (an unclosed call, an unterminated string, an
over-large region) make the report `INCOMPLETE` instead of clean.

!!! warning "Symptom"
    `status: ok` but the docs are clearly wrong.

!!! tip "Fix"
    Check `checked N of M` and whether the report ends with `INCOMPLETE`. The call may be to an unchecked export (no
    `\usage`, a method, or a function with `...`).

## Optional site and README checks

```bash
/rforge:docs:check --site https://example.org/pkg/ --ref origin/main
/rforge:docs:check --run-examples --examples-budget-seconds 300 --fail-on warn
```

`--site` requires one resolved package. It compares an immutable local deployment
source with one bounded sitemap; no build, fetch, deploy or link crawl occurs.
Missing selected-ref pages remain warn; checkout-only additions are info.
Sitemap absence does not prove HTTP 404, availability or deployment freshness. Each sitemap `url` must carry exactly one
nonempty `loc`; a `url` with two, none or an empty one makes the stage incomplete (`malformed sitemap entry`).
Foreign/scheme-changing redirects require a fresh canonical-URL invocation.

!!! note "Expected behavior in the next release (unreleased; after v2.22.2)"
    `--site` maps `.qmd`, `.Rmd` and `.rmd` articles (nested ones included) and resolves
    `development.mode` (`auto`, `default`, `release`, `devel`, `unreleased`) from the pinned
    `DESCRIPTION` version with pkgdown 2.2.1's rule, so a Quarto site on `mode: auto` at a release
    version is audited at its root. Only `devel` serves from `<destination>/` (default `dev/`).

    - **The base URL is never adjusted for you.** `--site` must equal the source `url` plus the dev
      prefix (`https://example.org/pkg/dev/` for a devel site, `https://example.org/pkg/` otherwise);
      a root URL on a devel site, or a `/dev/` URL on a release site, is `incomplete` with a reason,
      before any request. A devel site on Bootstrap 3 writes an unprefixed sitemap and is refused.
    - **Still `incomplete`, with a specific reason:** at the pinned ref, `PKGDOWN_DEV_MODE` in a
      workflow, a local composite action or a repository-root or package `.Renviron`/`.Rprofile`; a
      job-level reusable-workflow `uses:`; a local `uses: ./...` action that is missing, malformed or
      not composite; a deploy below the site root (`deploy_to_branch(subdir = )`, or a Pages
      `target-folder` or `destination-dir` input whenever a pkgdown config for the package exists
      at the pinned ref, or a workflow names pkgdown, even if the deploy is unrelated to the
      site); a
      malformed workflow; a configuration under
      `inst/` or `pkgdown/`; a non-default `vignettes/_quarto.yaml`; any symlink under `vignettes/`
      (the link text is never read as article content); and directory-level `_metadata.yml`,
      `_quarto-*.yml`, a nested `_quarto.yml` (with `.qmd` articles) or `_output.yml` (with `.Rmd`
      articles). pkgdown's behavior for those directory-level files was not rendered, so they are
      refused rather than guessed.
    - **Per-article refusals** are exactly these front-matter keys and values: `output_file`,
      `output-file`, `output_ext`, `output-ext`, `output_dir` or `output-dir` anywhere in the front
      matter; `knit`; a Quarto `format` other than `html`; an `.Rmd` `output` other than
      `html_document`/`html_vignette`; `pkgdown: extension` other than `html`; and `as_is`. Those
      routes are removed from the expected set, never guessed. Article keys match in any case, and
      `-` and `_` are interchangeable (`as-is`, `Output-File`). Anything else that changes a route
      (`uses:` actions from other repositories, a variable name built any way other than the
      spellings below, a manual deploy outside CI, `_site.yml`, a document run through
      `knit`/`render`) is not detected.
    - **Scripts a `run:` step executes** (`Rscript`, `R -f`/`--file`/`CMD BATCH`, `bash`/`sh`/`zsh`,
      `python`, `source`/`.`, `./path`, `make [-f] [-C]`, and `source()`/`sys.source()`/`system()`
      inside R) are read at the pinned ref, honoring `working-directory` and `cd`, followed up to
      five levels and 40 files, and scanned with the same detections as a `run:` body. A signal
      in a reached script blocks, even inside a comment. `make` follows `include`, `-include` and
      `sinclude`. In a pkgdown repository, a reference that is missing, a symlink, outside the
      repository, absolute, dynamic (`$VAR`, `paste0()`, a glob, a wildcard include), binary, over
      1 MiB or over a cap is `incomplete` ("script reference unsupported"). A clean readable
      script never blocks. Scripts fetched or generated at runtime show up as missing or dynamic.
    - **Which workflows are strict.** Every workflow and local action in a pkgdown repository,
      unless the workflow shows no ability to publish. Two tiers of evidence make it
      publish-capable and strict. **Tier 1, always:** the word pkgdown; a Pages or deploy action
      (`JamesIves/github-pages-deploy-action`, `peaceiris/actions-gh-pages`, `actions/deploy-pages`,
      `upload-pages-artifact`, `configure-pages`, Netlify, Vercel, Firebase, Cloudflare, rsync, scp and
      S3 sync actions); `deploy_to_branch` or `gh-pages` text; `pages` or `id-token` write, or
      `write-all`; a checkout given a secret token or key; an **explicit-branch push**, meaning any
      `git push` whose literal branch is not `HEAD`, `main` or `master` (forms `<remote> <branch>`,
      `<src>:<branch>`, `refs/heads/<branch>`, with `-u`, `--force`, `--force-with-lease`, `+`; a
      dynamic remote or refspec, `--all` and `--mirror` fail closed to tier 1; the default branch is
      decided by name only); a command that names a remote target (`rsync` or `scp` to a host,
      `aws s3 sync|cp|mv` to `s3://`, `gsutil` to `gs://`, `netlify` or `firebase deploy`, `surge`,
      `vercel`, `wrangler pages`, `ghp-import`); a command that **builds or stages the destination**,
      whether or not the pinned tree tracks it yet (`git add` or `git commit` naming the destination,
      `git add -A`/`.`/`-u` or `git commit -a` when a pkgdown build appears in the same workflow or a script
      it reaches, `git subtree push`, `git worktree add <destination>`, `cp`/`mv`/`rsync`/`ln` into the
      destination), because such a workflow can create and push `docs/` from nothing. A push that stages
      something else, such as `git add data/history.csv`, is not stage evidence. **Stage everything and push:** a workflow
      that stages everything (`git add .`, `-A`, `--all`, `-u`, a dynamic or `*` pathspec, `git commit -a`,
      or an add-and-commit, auto-commit or push action) **and** pushes the default branch (or pushes with
      no refspec) is treated as publish capable and the audit reports it as incomplete. The audit does not
      try to prove such a workflow builds no site: a `tee`, a redirect, a download, an archive
      extraction or a script that writes `docs/` directly cannot be enumerated away. A stage that names
      only specific pathspecs outside the destination (`git add data/history.csv`) stays tier 2 unless
      the workflow also reaches an unresolved reference (below), and a push to a branch declared
      non-publishing is not a push; a pathspec that is, contains, is a parent of or is a
      glob that can match the destination (`docs*`, `*.html`) is tier 1. A stage is **named** only when
      every pathspec is a plain literal path outside the destination (a wildcard counts only below a literal first
      directory, as in `man/*.Rd`; `*.html` and `**/x.html` do not); pathspec magic (`:(top)docs`,
      `:/docs`, `:!x`, `:(glob)`), `--pathspec-from-file`, `..`, absolute or `~` paths, expansion and
      braces, a commit that names such a path, and git plumbing that changes the index or tree
      (`update-index`, `read-tree`, `commit-tree`, `checkout-index`, `apply`, `am`, `stash`) stage
      everything, so an unknown form fails closed. A workflow that stages everything and runs a program whose
      name is computed is also tier 1 without a visible push (the program may be `git`, as in
      `$(command -v git) push origin main`). `r-lib/actions/pr-push`
      pushes a pull request's own branch and is not counted. A repository that is not a pkgdown
      repository is not affected. **Cross-workflow
      handoff:** build output can reach the staging workflow from another workflow, so a workflow that
      stages and pushes (`git add .`/`-A`/`-u`/`-f`, `git commit -a`, a push action, then a push to the
      default branch or with no refspec) is also tier 1 when it pulls build output from elsewhere
      (`download-artifact`, `gh run download`, `gh release download`, `curl`/`wget` of an archive, a
      `workflow_run` trigger) or when any other workflow in the repository builds the site (pkgdown
      wording, a `build_site` call, an upload of the destination, `upload-pages-artifact`). A stage-and-push
      workflow is also tier 1 when anything it reaches could not be resolved, because the build may
      hide behind it: a dynamic or missing script, an absolute or outside path, a symlink, a binary or
      oversized file, a depth or file cap, a dynamic working directory, a missing or malformed local
      action, a make include that cannot be read, `eval(parse())`, `do.call(source, ...)`,
      `rmarkdown::render`/`knitr::knit`/`quarto::quarto_render`, or **any executable outside a short
      allowlist**. The scan follows `Rscript`/`R`, `bash`/`sh`/`zsh` (including a literal `-c` string),
      `make`, `source`, `./x` and `python <literal script>`, and knows `git`, `gh`, `curl`/`wget`,
      installers (`pip`, `uv pip`, `apt`, `brew`: install-type subcommands only) and plain shell and text
      utilities (`echo`, `cat`, `ls`, `cp`, `grep`, `sed`, `awk`, `jq`, `find` and the like) cannot make
      site files. Everything else is opaque: `python -m <module>` (except `pip`, `venv`), `python -c`,
      `uv run <unlisted tool>`, `node`, `quarto`, `docker`, any unlisted binary, a dynamic command
      (`$X`, `bash -c "$X"`), a Python script that runs other code (`subprocess`, `os.system`, `exec`).
      The list is not extended per generator: the default for an unknown executable is to fail closed.
      Wrapper options (`env --`, `sudo -E`, `nice -n`) are parsed before the executable is judged, a
      repo-relative path is read even when its basename is an allowlisted name (`tools/echo`), a literal
      absolute path outside the system bin directories is opaque, and a wrapper option that changes what runs or
      where (`env -S`, `env -C`, `sudo -D`, `sudo -i`/`-s`) is opaque. `gh` is allowed for reads; `gh api` with a
      write method or field flags, `gh workflow run`, `gh pr merge` and `gh release create|upload|edit|delete` are a
      publish signal and opaque.
      For every workflow that may publish (it stages and pushes, or deploys through a Pages or deploy
      action, or is tier 1 or tier 2 capable under the tracked-destination rule) every such reference is an
      incomplete reason; a workflow that cannot publish keeps treating opaque calls as not detected. Without a build, download or unresolved reference anywhere, a
      stage-and-push workflow stays tier 2; a push to a branch declared non-publishing is not a push
      for this rule. **Tier 2, only when the pinned tree tracks the
      pkgdown destination:** plain `contents: write`; a push action such as `ad-m/github-push-action`;
      a job with no `permissions:` key at either level; a push with no refspec or to the default
      branch; the same publish programs with no remote target. The destination is the config
      `destination:` (default `docs/`, under the package directory) plus any destination a pkgdown
      build call names (`destination =`, `dest_dir =`, `destination:`, `--destination`; a value that
      is not a literal counts as tracked). A directory holding only `.gitkeep`, `.keep`, `.gitignore`
      or `.gitattributes` is not tracked; anything else is, including `.nojekyll`, a file or symlink
      at the path, and a gitlink (submodule) at or below it. Paths compare case-sensitively, as git
      does. A destination that is a variable, a list, absolute or `..`, or an unreadable config,
      counts as tracked. Evidence from the scripts and local actions a workflow reaches counts the
      same way. A caller job that `uses:` a local reusable workflow shares capability with it in both
      directions (callee gets the caller's permissions, caller gets the callee's evidence); an
      unresolvable callee (missing, another repository, dynamic) is assumed tier 1. The reason names
      the tier and the evidence, for example "tier 2: permissions contents: write (workflow);
      destination docs/ is tracked".
    - **Declaring a branch that never carries site files.** A repository can list literal branch names
      in `.rforge.yaml` (package directory or repository root, read at the pinned ref):

      ```yaml
      docs:
        site:
          nonpublishing-branches:
            - qc-results
      ```

      A push to a listed branch is tier 2 instead of tier 1, so it counts only when the destination is
      tracked. Only a list of literal names counts: a string, glob, variable or non-string entry, or an
      unparseable file, exempts nothing, and a key that exists only in the working tree or after the
      pinned ref is not read. `gh-pages` text and deploy actions stay tier 1 whatever the list says.

      **The list is an unverified declaration.** It is a maintainer attestation in the same trust class as
      `docs.allowlist` and `site.allowlist`: the engine cannot see what a branch serves without a live
      GitHub Pages API call, which the offline default forbids, so a site branch listed by mistake yields
      a wrong `complete`. Review the list when you review the site setup. Whenever a push was classified
      tier 2 because of the declaration, the site stage carries `nonpublishing_branches_honored` (the sorted names whose push
      was classified as non-publishing because of it; an empty list when none) and the text report prints
      an `info` line naming them, so a reader sees that an exemption was applied.

      A workflow with no evidence is relaxed, because QC and simulation scripts are full of
      `source(file.path(...))`. Not detected: a script that pushes from a workflow that shows no signal
      at all; a stage-and-push workflow whose only route to site files is an
      action from another repository, a submodule update or a checkout of another ref, with no
      build, download or unresolved reference anywhere in the repository; `knit`/`render` and unlisted
      executables in a workflow that cannot publish; a destination written through a name the scan cannot read; a site branch mislabeled in
      `nonpublishing-branches` (documented gap: an unverified maintainer declaration); actions from other repositories (beyond the fail-closed reusable-workflow rule); manual
      deploys outside CI.
    - **How names are matched.** YAML inputs (workflows, local actions, front matter) are read as
      parsed structures, so quoted or escaped keys, flow mappings, anchors, merge keys and any
      case of `target-folder`/`PKGDOWN_DEV_MODE` count. R and shell code (a `run:` body,
      `.Rprofile`) is matched as text: the argument name in `deploy_to_branch(subdir = )` may be
      quoted, backticked or on another line, and `PKGDOWN_DEV_MODE` is found in any case, with
      quotes, commas or `paste0()` splits between its parts. Root redirects and general output overrides are follow-up work (#123).
    - **`content_freshness: unverified`.** A `complete` site stage means route presence only: the
      sitemap says which pages exist, not whether their content is current (a sitemap carries no
      `<lastmod>`). The text verdict reads `no findings; site content freshness and deploy layout unverified`.
    - **`deploy_layout: unverified`.** The workflow and script scan (publish-capability tiers, tracked
      destination, stage-and-push, opaque executables) refuses a site when it finds a way CI could deploy a
      different layout, but it is best effort and cannot be exhaustive: it infers deploy behavior from workflow
      text and a repository can publish through commands, scripts or credentials it cannot read. A `complete`
      stage therefore never claims how the site is deployed; the marker is a fixed property of the stage, not a
      result of the scan. Known residuals found in review and not patched: an allowlisted program that loads a
      script (`awk -f tools/publish.awk`, `sed -f`), `gh repo sync` and other `gh` subcommands that update
      repository content, and deploy credentials (a personal access token passed to a step as `GH_TOKEN`) in a workflow with
      read-only `contents`.

README replay loads the working tree with pkgload/evaluate, retaining hidden
setup state and honoring literal eval/include/visibility options. Root explicit
R fences and literal #> assertions are supported. Unsupported options, unlabeled
assertions and unpaired rendered output remain incomplete. A selected source
never certifies its asserted rendered markdown. Zero eligible assertions execute
no setup. Package code may write files or use the network: this is not a sandbox.

Read all six coverage counts: discovered, eligible, checked, excluded, unverified
and blocked. Checked groups divide into matched and mismatched. Discovered equals
checked plus excluded plus unverified plus blocked; eligible records the replay
scope. Unpaired rendered assertions stay unverified even when source comparisons
match. Completed numeric mismatch is warn; it exits 1 under `--fail-on warn`, 0 under `--fail-on error` when
nothing else gates. Incomplete/unavailable stages exit 2 under either threshold.
Default none exits 0 with explicit diagnostics. Allowlists never clear incomplete
coverage. Source-less extra sitemap URLs are outside file allowlists.

Numeric comparison reads the precision of the documented value. Decimals and scientific
notation tolerate one unit in the last documented place (`0.19` matches `0.20`). A
documented whole number of up to six digits must match exactly (`100` against `101` is a
mismatch), so a stale count, size or index fails. Seven or more digits keep the loose
tolerance, because R prints seven significant digits by default.

The total budget defaults to 300 seconds across all example files/packages;
file/chunk caps are 300/60 seconds, including loading. Allow budget plus 15 seconds
for guardian cleanup and final report. Poll/yield timeouts are not host lifetime.
Unknown host lifetime calls for a terminal recommendation. A shorter known host
limit requires reducing the budget to leave the 15-second reserve or using the
terminal. Missing stdout after wrapper termination is interruption; never infer a
clean audit or fabricate recovered JSON. Ordinary process-group
cleanup does not contain detached children or guarantee reporting after host loss.
The orchestrator always recommends examples/combined runs; site-only automatic
GET needs an explicitly human-supplied URL, not one found in project material.


### A2 release evidence

The `a2-release` job in normal CI and the release-evidence workflow both call
`a2-platform.yml`, which provisions and tests the same locked Ubuntu/macOS matrix.
Normal CI does not run the separate aggregate release-acceptance gate.

A passing developer suite does not complete the A2 release gate. Both required
platform artifacts must be retrieved and verified. Aggregate acceptance also
requires the `a2-acceptance-evidence` artifact from a completed workflow run for
the candidate. Supply its numeric run ID through `acceptance-evidence-run`.
Its `index.json` names each observation file, SHA-256 digest and producer run ID;
the verifier checks the downloaded file's candidate, kind, status and required
facts. Bare passing claims, missing files, altered hashes, stale candidates and
unresolved review findings fail acceptance.

The `a2-observations.yml` workflow produces that artifact in one run bound to the
candidate commit. It computes the full-gate record, a live-site smoke against a
real deployed pkgdown site, the package-triage freshness check and the rendered-page
inspection itself. The finalized adversarial review is a recorded judgment supplied
as the `review-record` input: the run stamps it but cannot prove it, so it is
attested by whoever dispatches; keep it concise, because a dispatch input is limited to about 64 KB. Before downloading the artifact, `a2-release.yml` asks the Actions API whether the supplying run is the `a2-observations.yml` dispatch for the same head commit and finished successfully. The live smoke checks one supported public site and
records pinned real packages: in the unreleased next version, the Data-Wise packages medfit and probmed (pkgdown
`development.mode: auto`, `.qmd` articles) are audited as supported, and the pinned tidyverse
site glue (`template.package`) must still be reported incomplete.

Evaluate text is mirrored into a separate temporary spool, allowing the guardian
to observe output growth inside a running expression. Captured text is counted
once from that spool; condition text is counted separately as it occurs. Native
stdout and stderr remain separate. Polling permits overshoot and does not impose
a memory or storage limit.

Article exclusions follow the source filename: `_child.Rmd` is excluded, while
`_private/nested.Rmd` maps to `articles/_private/nested.html`. Tutorial sources
remain outside article scope. These rules are verified against pkgdown 2.2.1.

Diagnostic stdout/stderr tails remain at most 1 MiB when encoded as UTF-8,
including replacement characters for malformed input. Malformed or duplicate
checkpoint records block their assertions while valid earlier records remain
available for comparison; they cannot make replay complete.

### Process-group ownership

The Python parent creates a separate group pin and retains it as an unreaped
direct child until the guardian has exited and all possible group signals have
finished. The guardian launches R into that group and remains R’s direct parent
and the sole normal termination owner. Emergency parent cleanup uses its owned
pin object, not a PID recovered from a checkpoint. The parent closes the signal
capability before reaping the pin and observes group disappearance afterward.

The pin ignores TERM during the guardian’s grace period and has no independent
expiry that could release ownership before a delayed guardian resumes. The
guardian releases it after its final possible group signal. The parent reaps it
on ordinary shutdown; total parent/guardian loss still cannot guarantee cleanup.
`os.posix_spawn(setpgroup=...)` assigns group membership before the launcher
runs. An isolated `python -I -S` bootstrap changes to the workload directory
and checks the original deadline before exec. This supports Python 3.10 and
prevents project-local `lib` files from replacing the launcher. Workload and pin reaping are reported
separately; a missing guardian terminal record remains incomplete even when
emergency cleanup succeeds.

Ownership assignment remains inside signal deferral through the caller’s handle
assignment, including pin construction; children restore the original signal
mask. A failed liveness probe cannot prevent the guardian from attempting KILL
and independently reaping its unreaped direct child. Such failures remain
incomplete, even when cleanup succeeds; destructive signals never follow the
direct-child reap in the guardian’s exception path.

Ordinary replay preparation or execution exceptions retain the known assertion
counts and valid partial checkpoints in an incomplete report. Lifecycle evidence
is recovered only when its run ID matches the current initial checkpoint;
completed lifecycle evidence cannot override the exception. KeyboardInterrupt
still propagates. Before workload spawn, a checkpoint PGID alone does not authorize
a destructive signal; the child handle is allocated before launching the workload.

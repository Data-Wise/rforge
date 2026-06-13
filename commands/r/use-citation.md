---
name: rforge:r:use-citation
description: Scaffold inst/CITATION from DESCRIPTION (Title/Authors@R/Version, deterministic year)
argument-hint: "[--write] [--force]"
arguments:
  - name: write
    description: Apply the plan (write inst/CITATION). Default is dry-run (prints the plan, writes nothing).
    required: false
    type: boolean
    default: false
  - name: force
    description: Overwrite an existing inst/CITATION (refused without this flag)
    required: false
    type: boolean
    default: false
---

# R Use Citation

Scaffold `inst/CITATION` for an **existing** R package from its `DESCRIPTION`. Parses
`Title`, `Authors@R` (or fallback `Author`), and `Version`, and renders a
`bibentry(bibtype = "Manual", ...)` with the package's own `person()` calls.

**Dry-run by default.** `--write` writes `inst/CITATION` (creating `inst/` if absent);
`--force` is required to overwrite an existing file.

**Deterministic year:** the year comes from `Date:` if present, else a `<YEAR>` TODO —
**never** a wall-clock date. Fill it in by hand.

Unparseable authors degrade to a `# TODO` author block plus a warning (never raises).

## Usage

```bash
# Dry-run: print the planned inst/CITATION, write nothing (default)
python3 -m lib.scaffold citation --path "<path>"

# Apply: write inst/CITATION (creates inst/ if absent)
python3 -m lib.scaffold citation --path "<path>" --write

# Overwrite an existing inst/CITATION
python3 -m lib.scaffold citation --path "<path>" --write --force
```

## What you do after the plan

1. Replace any `<YEAR>` TODO with the publication year (or add a `Date:` to DESCRIPTION).
2. Verify the rendered `textVersion` reads correctly.
3. Run `/rforge:r:check` — a malformed `inst/CITATION` is a NOTE.

## Related Commands

- `/rforge:r:check` — validates `inst/CITATION` parses
- `/rforge:r:document` — regenerate docs if you edited DESCRIPTION metadata

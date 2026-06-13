---
name: rforge:r:spell
description: Spell-check the package (spelling) and triage typos
argument-hint: "[package]"
arguments:
  - name: package
    description: Package path (defaults to current directory)
    required: false
    type: string
---

# R Package Spell Check

Run `spelling::spell_check_package()`.
`spelling` is optional — if `engine_missing` includes `spelling`, report 🟡 + hint.

## Process
```bash
python3 -m lib.rcmd --kind spell --path "<path>"
```

## Output Format
```markdown
## Spell: {package} v{version}
### Status: {🟢 0 / 🟡 {spell.count} words}
{List spell.misspelled: "- teh (R/foo.R:3)"}
### Recommended Actions
{Real typos to fix vs words to add to `inst/WORDLIST`}
```

## Related Commands
- `/rforge:r:check` — spelling NOTEs also surface in R CMD check

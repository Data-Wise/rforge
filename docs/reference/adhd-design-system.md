# ADHD-friendly design system

!!! tip adhd-tldr "TL;DR (30 seconds)"
    - **What:** The rules, CSS tokens and copy-paste components that keep every page of this site scannable.
    - **Why:** A reader with ADHD decides in seconds whether a page is worth it. Short chunks, a time cost and one next step lower that barrier.
    - **How:** Start each page from the [page checklist](#page-checklist). Copy a [component snippet](#components) when you need one.
    - **Next:** Run the [advisory checker](#check-your-pages) on the page you just edited.

⏱️ **5 minutes** • 🟢 Beginner • ✓ 6 sections
{ .adhd-meta }

This page is the single source for how rforge docs look and read. The stylesheet is `docs/stylesheets/extra.css`. This page is itself built from the components it describes.

## Principles

Six rules. Every token and component below exists to serve one of them.

1. **Answer first.** A TL;DR box at the top says what, why, how and next.
2. **Show the cost.** A time line tells the reader the minutes, level and step count before they commit.
3. **Small chunks.** Sections of a screen or less, paragraphs of five sentences or fewer.
4. **One next step.** Every page ends with a single, concrete next action.
5. **Calm visuals.** Soft contrast, no flashing, no motion that cannot be turned off.
6. **Two signals.** Color is never the only signal. Callouts also carry an emoji and a title.

## Tokens

Defined on `:root` in `extra.css`. A matching set under `[data-md-color-scheme="slate"]` applies in dark mode. The older `--adhd-line-height` and `--adhd-paragraph-width` tokens still work.

| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `--adhd-fg` | `#2b2b2b` | `#e8e8e8` | Body text. Never pure black or white. |
| `--adhd-bg` | `#fafafa` | `#1a1a2e` | Page background. |
| `--adhd-link` | `#00796b` | `#4db6ac` | Links and step numbers (at least 5:1 contrast). |
| `--adhd-surface` | teal at 7% | teal at 10% | Card and callout background. |
| `--adhd-success` | `#2e7d32` | `#81c784` | Next-step card. |
| `--adhd-accent` | `#a35200` | `#ffca28` | Focus ring. |
| `--adhd-font-size` | `0.85rem` | same | Body size (17px; the Material root is 20px). |
| `--adhd-line-height` | `1.7` | same | Generous line spacing. |
| `--adhd-paragraph-width` | `68ch` | same | Reading measure: about 65 to 75 characters. |
| `--adhd-space-1` to `-4` | `0.5` to `2.25rem` | same | Spacing steps for margins. |

The palette follows craft's `adhd-focus` preset. The header and tabs keep the teal primary from `mkdocs.yml`, and the standard callout types keep Material's colors.

## Components

All components are opt-in. They use only the Markdown extensions this site already loads: `admonition`, `attr_list` and `md_in_html`.

### TL;DR box

Put it directly under the page title. Four bullets, each one line.

```markdown
!!! tip adhd-tldr "TL;DR (30 seconds)"
    - **What:** One sentence.
    - **Why:** One benefit.
    - **How:** One command or one link.
    - **Next:** One next step.
```

The extra word `adhd-tldr` after the type adds the class. Existing boxes without it keep working.

### Time line

One line under the TL;DR: minutes, level and steps.

```markdown
⏱️ **10 minutes** • 🟢 Beginner • ✓ 7 steps
{ .adhd-meta }
```

Levels: 🟢 Beginner, 🔵 Intermediate, 🔴 Advanced.

### Next-step card

Last element on the page. One link or one command, nothing else.

```markdown
!!! success adhd-next "Next step"
    Continue with [Quick Start](../quickstart.md).
```

The card below is live:

!!! success adhd-next "Next step"
    Run the [advisory checker](#check-your-pages) on the page you just edited.

### Step list

Use for short procedures of seven steps or fewer. Wrap an ordinary numbered list in a `div` (the `md_in_html` extension renders the Markdown inside it).

```markdown
<div class="adhd-steps" markdown>

1. Run the first command.
2. Check the output.
3. Run the second command.

</div>
```

<div class="adhd-steps" markdown>

1. Run the first command.
2. Check the output.
3. Run the second command.

</div>

### Callouts

Standard admonitions with an emoji at the start of the title. Use at most one or two per screen, or none of them will stand out.

```markdown
!!! tip "💡 Pro tip"
    A shortcut worth knowing.

!!! warning "⚠️ Watch out"
    The mistake people make here.

!!! success "✅ Done when"
    The observable result.

!!! info "🎯 Focus"
    The one thing to remember.
```

!!! tip "💡 Pro tip"
    A shortcut worth knowing.

!!! warning "⚠️ Watch out"
    The mistake people make here.

!!! success "✅ Done when"
    The observable result.

!!! info "🎯 Focus"
    The one thing to remember.

### Diagrams and tables

Use the standard `mermaid` code fence. The stylesheet stops diagrams from overflowing a phone screen. Wide tables scroll sideways instead of breaking the layout.

## Accessibility behavior

These are built into the stylesheet and need no markup.

- **Dark mode:** follows the system setting; the header toggle overrides it.
- **Reduced motion:** with `prefers-reduced-motion: reduce`, animations and transitions are effectively off.
- **Focus:** keyboard focus shows a 3px ring in `--adhd-accent`.
- **Touch targets:** on phones and tablets, navigation, tabs, buttons and footer links are at least 44px tall.
- **Narrow screens:** smaller headings, tighter code, full-width components.

## Page checklist

Copy this into a pull request description when you add or rewrite a page.

- ☐ TL;DR box under the title (What, Why, How, Next).
- ☐ Time line for tutorials and guides.
- ☐ Sections of about one screen, each under its own `##` heading.
- ☐ No paragraph longer than five sentences.
- ☐ Commands in code blocks, not in prose.
- ☐ One next-step card at the end.
- ☐ Callouts have an emoji and a title, not color alone.

## Check your pages

`scripts/check_docs_adhd.py` is a read-only, advisory checker. It uses only the Python standard library and is not part of any gate. It reports, per page, whether there is a TL;DR box, a time line and a next-step block, and the longest paragraph in sentences.

```bash
python3 scripts/check_docs_adhd.py              # every page under docs/
python3 scripts/check_docs_adhd.py docs/guides  # one folder or file
```

Generated API pages (marked "Auto-generated by") are skipped. Treat the output as a to-do list, not a verdict.

!!! success adhd-next "Next step"
    Open the page you are editing and walk the [page checklist](#page-checklist) once.

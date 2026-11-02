---
name: AgentForge
description: One Skill to rule them all, One Skill to find them, One Skill to bring them all and in the harness bind them
colors:
  paper: "#f8f5ed"
  white: "#fffdf8"
  ink: "#243c31"
  muted: "#586355"
  line: "#dad6c7"
  accent: "#244638"
  accent-hover: "#183a2c"
  gold: "#92713d"
  gold-soft: "#e5d8b9"
  surface-hover: "#efede3"
typography:
  display:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "96px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.03em"
  promise:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "48px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "-0.02em"
  verse:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "24px"
    fontWeight: 500
    lineHeight: "32px"
    letterSpacing: "0"
  brand:
    fontFamily: "Cormorant Garamond, Georgia, serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: "32px"
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Geist Sans, sans-serif"
    fontSize: "24px"
    fontWeight: 550
    lineHeight: "32px"
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Geist Sans, sans-serif"
    fontSize: "18px"
    fontWeight: 550
    lineHeight: "28px"
  body:
    fontFamily: "Geist Sans, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  supporting:
    fontFamily: "Geist Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "24px"
  label:
    fontFamily: "Geist Sans, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "20px"
  command:
    fontFamily: "Geist Mono, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "20px"
rounded:
  skeleton: "4px"
  control: "8px"
  category: "12px"
  panel: "16px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  3xl: "40px"
  4xl: "48px"
  5xl: "64px"
  6xl: "80px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "white"
    rounded: "{rounded.control}"
    padding: "12px 16px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
    textColor: "white"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  search:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "12px 12px 12px 24px"
  category:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    height: "44px"
  category-active:
    backgroundColor: "{colors.ink}"
    textColor: "white"
  catalog-row:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "24px 8px"
  catalog-row-hover:
    backgroundColor: "{colors.surface-hover}"
  catalog-row-expanded:
    backgroundColor: "{colors.white}"
  install-panel:
    backgroundColor: "{colors.white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "32px"
---

# Design System: AgentForge

## Overview

**Creative North Star: "The Literary Field Guide"**

AgentForge pairs an inscription-like title with a practical reference catalog.
Warm ivory, forest green, restrained gold, and a literary serif carry the
approved Tolkien-inspired character. The search field, filters, catalog data,
and installation controls retain familiar interface forms.

The original two-ring forge emblem repeats in the navigation, hero, footer,
and favicon. The full founder tagline remains intact. `src/lib/brand.ts` owns
the copy shared by the hero and social metadata.

**Key Characteristics:**

- A literary title and verse above a clearly labeled search field.
- Warm paper backgrounds, fine separators, and flat catalog rows.
- Forest actions and limited gold ornament.
- Original ring-and-forge geometry repeated at different sizes.
- Geist for controls and data, with visible keyboard focus.

## Colors

The frontmatter records the exact CSS custom properties in `src/app/globals.css`.

### Primary

Forest (`accent`) colors the main actions, title subject, navigation emblem,
and focus outline. `accent-hover` darkens primary actions on hover.

### Secondary

Forge gold (`gold`) colors the emblem's spark and the hero ornament. Pale gold
(`gold-soft`) forms the verse rule and selected-text background.

### Neutral

Warm ivory (`paper`) is the page ground. Reading white (`white`) fills the
search field, installation panel, and expanded catalog rows. Forest ink
(`ink`) carries headings and body text. Muted olive (`muted`) carries
supporting text, metadata, and labels. Parchment line (`line`) separates
regions and rows. `surface-hover` distinguishes a catalog row on hover.

The catalog retains small pastel category badges for design, engineering,
writing, research, and operations. These local classification colors do not
replace the forest action color or become large page backgrounds.

**The Forest Action Rule.** Forest identifies actions and focus. Gold stays
with the emblem, ornament, verse rule, and text selection.

## Typography

Cormorant Garamond is the display face, with Georgia and a generic serif as
fallbacks. The Latin variable WOFF2 subset is self-hosted at weights 400
through 600 in `src/app/fonts/`. The file is 37,776 bytes. Its bundled SIL Open
Font License applies to the font, while the platform remains proprietary.
There is no third-party font request.

Geist Sans carries the functional interface. Geist Mono appears in commands
and the installation archive name. `src/app/layout.tsx` registers all three
families through local font assets and the bundled Geist package.

### Hierarchy

- The title subject uses `display`. At 900px and below it becomes 72px. At
  600px and below it becomes 60px, retaining unit line height.
- The first-line promise uses `promise`. At 900px and below it becomes 36px
  with 40px line height. At 600px and below it becomes 30px with 36px line height.
- The remaining tagline uses `verse`. At 900px and below it becomes 20px with
  28px line height. The complete text remains visible.
- The wordmark uses `brand`. Mobile and footer wordmarks are 20px with 28px line height.
- Catalog headings use `headline`. Skill names use `title`, becoming 16px
  with 24px line height on mobile.
- Body copy uses `body`. Descriptions use `supporting`. Navigation and filter
  labels are 14px. Counts and source metadata use `label`, with tabular result counts.
- The hero description and desktop search input are 18px with 28px line
  height. Both become 16px with 24px line height on mobile.
- The installation heading is a 36px literary serif with 40px line height,
  becoming 30px with 36px line height at 900px. The statement uses a 48px
  serif at unit line height, becoming 36px with 40px line height on mobile.
- Legal titles use a 48px serif with 1.1 line height, becoming 36px with 40px
  line height on mobile. Legal body copy has 28px line height.

**The Inscription and Interface Rule.** Cormorant carries the tagline,
wordmark, installation heading, statement, and legal title. Geist carries
search, navigation, catalog information, and controls. Mono stays with code.

## Layout

The main container has a maximum width of 1120px including 32px side padding.
Navigation has a separate 1440px maximum width and 48px horizontal padding.
The hero uses two columns in a 1.2-to-1 ratio with a 64px gap. The verse sits
beside the title lead, above the full-width search field.

The spacing scale reflects repeated gaps and padding. Desktop hero padding
is 80px above and 64px below. Most later sections use 64px vertical space.
Reading widths include the 680px hero description and 760px catalog summaries.

At 900px and below, navigation padding becomes 32px, the public-building link
is hidden, and the hero gap narrows to 40px. At 600px and below, container
padding becomes 24px, the hero stacks with a 24px gap, and its vertical padding
becomes 48px. Navigation keeps the wordmark and compact installation link.

Catalog rows use a 40px category badge, flexible content, and a 44px disclosure
control with 24px column gaps. Mobile badges become 32px and gaps become 12px.
Expanded mobile descriptions, tags, and details span the full row. Installation,
process, and FAQ columns stack. The platform selector stacks above its field.

## Elevation & Depth

The interface uses no box shadows. Fine borders, pale backgrounds, and spacing
separate regions. Catalog rows are flat at rest, gain the hover fill on pointer
hover, and use reading white when expanded. The installation band has a quiet
pale ground around its bordered panel.

Controls transition color, background, border, and position over 0.3 seconds
with `cubic-bezier(0.22, 1, 0.36, 1)`. Catalog hover and FAQ rotation take
0.2 seconds. Primary presses move down 1px. The statement changes text color
over 0.6 seconds with 35ms word delays. Loading rows breathe between 0.55 and
1 opacity over 1.6 seconds. Reduced motion removes delays, shortens these
effects, disables smooth scrolling, and immediately reveals the statement.

## Shapes

Controls use `rounded.control`. Search and installation panels use the larger
`rounded.panel`. Category badges use `rounded.category` on desktop and the
control radius on mobile. Catalog rows use full-width horizontal separators.

The original emblem has two concentric rings around an anvil and a diamond
spark. Its view box is 40 by 40. The rings have radii 18 and 14.5, with strokes
of 1.5 and 0.6. Navigation and hero marks render at 32px, the footer at 24px,
and mobile navigation at 28px. The SVG favicon preserves the same geometry.

**The One Emblem Rule.** Reuse the two-ring anvil and spark geometry. The hero
uses gold for the whole mark. Navigation, footer, and favicon use forest with
a gold spark.

## Components

### Buttons

Primary buttons use forest fill, white text, the control radius, and the
padding recorded in `button-primary`. They darken on hover and reduce opacity
to 0.65 while disabled. Outline navigation actions use a fine border and gain
a reading-white background on hover. Search, disclosure, category, and select
controls have a minimum 44px target.

Keyboard focus uses a 3px forest outline offset by 4px. The search input
instead uses the enclosing field's forest border on focus.

### Inputs / Fields

The search field has a reading-white enclosure, fine parchment border, large
corner radius, leading magnifying glass, and separate forest action. It uses
16px gaps on desktop and 8px gaps on mobile. Mobile padding becomes
8px 8px 8px 16px. The submit label hides visually at mobile width while the
button retains its accessible name and arrow.

### Chips

Category filters form a horizontally scrollable row. Unselected filters have
muted text on the page ground. The selected filter has forest-ink fill and
white text. Hover adds a pale fill. Filters retain the control target height.

### Cards / Containers

Catalog entries use separated rows with a category badge, title, publisher,
short description, metadata, and a disclosure caret. Expansion reveals the
full description and a two-column detail area on desktop, with source actions
below. Mobile details use one column. Loading placeholders retain the same
row structure. Counts and status text explain loading, results, errors, and
empty states without invented proof.

The installation panel uses reading white, a fine border, and the panel
radius. Padding reduces from 32px to 24px at 900px. Platform selection, archive
name, copy action, and copy status remain distinct.

### Navigation

The header places the literary wordmark and emblem beside 14px Geist links.
Installation is outlined. Responsive reductions preserve the home link and
installation action. Footer links use the same functional type and focus
treatment, with a smaller wordmark.

### Tagline and emblem

The heading contains the exact founder tagline, with its first clause split
into subject and promise. The remaining verse has a fine pale-gold top rule.
The original emblem interrupts that rule from an ivory backing. The complete
tagline is also the heading's accessible label. Decorative copies are hidden
from assistive technology.

## Do's and Don'ts

### Do:

- **Do** preserve the complete tagline from `src/lib/brand.ts` in the hero and shared metadata.
- **Do** use forest for primary controls and gold for the established ornament.
- **Do** preserve the familiar search field, clear status messages, and visible focus treatment.
- **Do** reuse the original emblem geometry in the header, hero, footer, and favicon.
- **Do** keep literary fonts self-hosted and retain the bundled font license.
- **Do** preserve the flat catalog rows and full-width expanded details on mobile.

### Don't:

- **Don't** shorten the founder tagline or clip it to preserve the desktop split.
- **Don't** use the literary serif for catalog metadata, search controls, or commands.
- **Don't** replace functional icons with ornamental lettering or ring motifs.
- **Don't** introduce decorative gradients, stock hero imagery, or a terminal costume.
- **Don't** turn local pastel category colors into the action palette.

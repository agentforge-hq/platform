# AgentForge design

## Direction

A working reference catalog, with the clear hierarchy and annotation of a field
guide. Warm paper, dark ink, a cobalt search action, and generous reading space.
The actual catalog is the proof. No terminal costume, invented metrics,
testimonials, decorative gradients, or stock hero imagery.

## Surface

One page: navigation, outcome headline, large search field, example prompts,
category shortcuts, actual catalog entries, installation, process, FAQ, footer.
Search is the primary action. Installation is a secondary in-page destination.

Hero: One Skill to rule them all, One Skill to find them, One Skill to bring
them all and in the harness bind them.
The full founder-supplied tagline appears in the first viewport, with its first
clause at display size and the remaining clauses below it. `src/lib/brand.ts`
owns this copy for the page heading and social metadata.
Subhead: Describe what you're trying to do. Discover useful skills, understand
what they make possible, and bring them into your agent.
Proof: real source names and live catalog counts only.

Benefits: discover unfamiliar capabilities; inspect source and requirements; use
the same search from a harness. Process: describe a task, choose a skill, bring
it into the work. FAQ covers automatic discovery, sources, compatibility,
pricing, privacy, and how adoption works.

Index the public page once live. Title: AgentForge | One Skill to rule them all.
Description: Describe your task to discover agent skills for writing, design,
engineering, and research. Install AgentForge to search from your harness.

## Tokens

Geist Sans, with Geist Mono for commands only. Ink #202820, paper #f7f8f2,
muted ink #586356, cobalt #314be8, line #dfe4d9. Body 16/24, supporting 14/20,
heading 60 with compact leading on desktop and 36/40 on small screens. Spacing
uses 4, 8, 12, 16, 24, 32, 48, 64, 80, and 96 pixels. Search radius 16 pixels.
Buttons radius 8 pixels. Catalog rows use separators and visible focus states.

Search states are idle, loading, success, no match, and error. Details expand
in place with a disclosure caret and a distinct white reading surface. On small
screens, expanded descriptions and supporting details use the full row width.
Search, disclosure, filter, and platform controls have a minimum 44-pixel target.
Loading uses the shape of catalog rows;
visible result counts explain the current view. Installation offers a download
and a copyable prompt, with stacked platform controls on small screens. Copy
actions report success or failure. Respect reduced motion and give controls
precise labels, including the compact mobile search button.

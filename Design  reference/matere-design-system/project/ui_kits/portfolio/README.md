# Matere Portfolio UI Kit

High-fidelity personal portfolio / signature site recreation using the Matere design system.

## Screens
1. **Home** — hero with wordmark, pixel mark, tagline, project teasers
2. **Work** — filterable project grid with pixel thumbnails
3. **About** — editorial (paper surface), bio, skill bars
4. **Contact** — terminal-style form with blinking cursor

## Components
- `Nav.jsx` — top nav with mark + wordmark + links + lang toggle
- `Hero.jsx` — home landing section
- `ProjectCard.jsx` — reusable project tile
- `WorkGrid.jsx` — filter + grid of projects
- `AboutPanel.jsx` — paper-surfaced bio
- `ContactForm.jsx` — terminal-style contact
- `Footer.jsx` — small pixel footer

## Interactions
- Click nav links to swap sections (fake router)
- Filter chips in Work
- Type into Contact; blinking cursor; fake submit
- Language toggle ES / EN swaps copy strings

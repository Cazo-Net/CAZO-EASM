# CAZO design system ("Crimson on black")

The frontend's look is driven by CSS variables in `frontend/src/app/globals.css`
and mapped to Tailwind names in `frontend/tailwind.config.ts`. Change a token
and every page follows.

## Palette

Chosen by the owner on 2026-11-28 from four options (signal blue, emerald,
violet, crimson on black).

| Role | Dark (default) | Light |
| --- | --- | --- |
| Background | `#0B0B0B` near black | `#FAFAFA` |
| Card / surface | `#141414` | `#FFFFFF` |
| Border | `#292929` | `#E3E3E3` |
| Primary text, icons, focus | `#EC3C53` crimson | `#D11A38` |
| Primary fill (buttons) | `hsl(350 82% 50%)` | `#D11A38` |
| Secondary accent | warm orange `hsl(20 90% 60%)` | orange |

Two things follow from a red brand colour:

- **Buttons use a darker red than text.** One red cannot both read on black as
  text and sit under white text at AA contrast, so `bg-primary` takes
  `--primary-fill` (see the end of `globals.css`).
- **Critical severity is magenta-pink, not red**, so a critical finding is not
  mistaken for a brand accent. The scale is critical pink, high orange, medium
  amber, low blue, info grey (`--sev-*`, Tailwind `severity-*`). Success stays
  green. Destructive actions and error text stay red, close to the brand
  colour; label them in words, never by colour alone.

To re-brand, change `--brand`, `--primary`, `--primary-fill` and `--ring` in
both blocks, and the two gradient stops in `public/logo.svg` (then regenerate
`public/favicon.ico`). The logo mark is the owner's artwork, a fractured
hexagon "C" with a shield and network nodes, traced to a vector; `CazoMark`
loads it from `/logo.svg`. The name stands for "Cyber Attack-surface
Zero-blindspot Operations", shown once, in the landing footer. The attack graph
and canvas pages use fixed hex values and need the same swap.

Legacy colour names (`phosphor`, `cyan-signal`, `signal-red`, `amber`,
`neon-violet`) now point at tokens, so older pages pick up the palette without
edits. New code should use the semantic names (`primary`, `success`,
`destructive`, `warning`, `severity-*`).

## Type

Inter for all UI text (display headings too, with tight tracking). JetBrains
Mono only for machine data: hostnames, IPs, ports, hashes, evidence.

## Components

- `PageHeader`, `SectionCard`, `StatCard`, `SeverityPill`, `EmptyState`,
  `SkeletonBlock` in `components/common/` are the building blocks for app pages.
- Page bodies use `page-container-{sm,md,lg}`, which carry the page gutter.
- Data on the dashboard comes from the API only. Do not show placeholder
  scores or trends; show an empty state instead.

## Screenshots

See `screenshots/` for before/after captures of the first redesigned screens.

## Admin panel

`admin-panel/frontend` shares the palette without sharing code: its Tailwind
config remaps `zinc` to the neutral greys and `blue` to crimson, and
`globals.css` carries the same base colours. It uses the same mark
(`src/components/CazoMark.tsx`) and Inter.

## Error and not-found pages

`app/not-found.tsx` and `app/error.tsx` are plain, token-based pages. The 404
no longer redirects after a countdown; it offers links instead.

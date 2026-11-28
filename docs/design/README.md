# CAZO design system ("Ink & Signal")

The frontend's look is driven by CSS variables in `frontend/src/app/globals.css`
and mapped to Tailwind names in `frontend/tailwind.config.ts`. Change a token
and every page follows.

## Palette

| Role | Dark (default) | Light |
| --- | --- | --- |
| Background | `#0A0D14` navy ink | `#F7F9FC` |
| Card / surface | `#11151E` | `#FFFFFF` |
| Border | `#232937` | `#DDE2EA` |
| Primary / focus | `#4A82F5` signal blue | `#2563EB` |
| Secondary accent | cyan `hsl(190 85% 52%)` | cyan |

Severity is one scale everywhere: critical red, high orange, medium amber,
low blue, info grey (`--sev-*`, Tailwind `severity-*`). Success stays green.

To re-brand, change `--brand`, `--primary` and `--ring` in both blocks, and the
two gradient stops in `components/marketing/CazoLogo.tsx` and `public/logo.svg` (then regenerate `public/favicon.ico`).

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
config remaps `zinc` to the navy-ink neutrals and `blue` to signal blue, and
`globals.css` carries the same base colours. It uses the same mark
(`src/components/CazoMark.tsx`) and Inter.

## Error and not-found pages

`app/not-found.tsx` and `app/error.tsx` are plain, token-based pages. The 404
no longer redirects after a countdown; it offers links instead.

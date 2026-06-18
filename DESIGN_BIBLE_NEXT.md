# SP Redesign Brief

This file is the active UI/UX standard for the v2.68.x redesign. The previous
`DESIGN_BIBLE.md` is preserved as legacy reference, but new redesign work should
use this document first.

## Product Shape

`/` is now a public landing page for yoongeon.xyz. The existing market dashboard
is preserved at `/dashboard`.

The public page should explain the product quickly, then direct users to the
dashboard, opportunity radar, screener, portfolio, and contact form. Logged-in
application routes keep the existing data and API flows, but should move toward
the same visual language over time.

The visible product name is `SP`. Legacy repository names can remain in code or
infrastructure where they identify historical projects, but user-facing brand,
metadata, and share assets should use `SP`.

## Design Principle

Use Toss-style clarity as an information architecture rule, not as visual
copying.

- One section has one headline, one supporting idea, and one primary action.
- Remove long self-promotional copy, repeated CTAs, and decorative UI blocks.
- Prefer direct Korean operational copy over marketing adjectives.
- White background is the default; use one cobalt accent and a neutral gray
  scale.
- Cards are used only when they group meaningful information.

## Visual Tokens

- Background: true white.
- Surface: very light neutral gray.
- Accent: cobalt blue.
- Text: near-black ink.
- Radius: 12px for most controls, 16-24px for large landing surfaces.
- Shadow: soft and sparse; use borders first.
- Touch targets: 48px minimum for new or redesigned controls.
- Base viewport: 360px.
- Breakpoints: 768px and 1024px.

## Landing Structure

The landing page follows this order:

1. Header with brand, essential links, and one primary dashboard CTA.
2. Hero with one headline, one support paragraph, and one primary CTA.
3. Core features: dashboard, opportunity radar, screener, portfolio.
4. How it works: market data, analysis, decision workflow.
5. Product preview: implementation-friendly dashboard mock surface.
6. Trust and limits: data scope, forecast limits, fallback behavior.
7. Final CTA leading to `/dashboard`.
8. Contact section from the existing global contact form.

## Figma Workflow

Figma is the design source. GitHub remains the production source.

- Figma file: `yoongeon.xyz Full Redesign v2.68`.
- Handoff file: https://www.figma.com/design/E51YcIXya4tLruomocZgrb
- Pages: `01 Brief`, `02 Tokens`, `03 Components`, `04 Landing`,
  `05 App Shell`, `06 Key Screens`, `07 Handoff`.
- If a Figma Starter plan page limit applies, keep the same `01`-`07`
  structure as named top-level frames grouped across up to three pages. The
  current handoff file uses:
  `01 Brief + Tokens`, `02 Landing + App Shell`, `03 Components + Handoff`.
- Figma Make is for first drafts only.
- Figma MCP should read or write one section at a time.
- Code Connect should map stable primitives after they exist in
  `frontend/src/components/ui`.
- Do not use Figma Make GitHub push as the production deployment path.

## Primitive Layer

New shared primitives live in `frontend/src/components/ui`.

Required primitives:

- `Button`
- `Input`
- `Card`
- `Modal`
- `Badge`
- `Section`
- `Container`
- `FormField`

Primitive components should use Tailwind 3 and existing CSS variables. Do not
introduce Tailwind v4 `@theme` or Next.js 16-only tooling in this redesign.

## Accessibility

- Keep `header`, `nav`, `main`, and `footer` semantics clear.
- Form controls must have labels and helper/error text wiring.
- Focus states must stay visible.
- Modals must trap focus when used.
- Body text contrast should meet 4.5:1.
- UI state and component boundary contrast should meet 3:1.

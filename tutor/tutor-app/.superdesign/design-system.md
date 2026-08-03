# Tutor Teacher Workspace design system

## Product and jobs

Tutor is a Chinese teacher assessment workspace. Teachers sign in, navigate courses/groups/submissions, inspect AI scoring evidence, add annotations or a final grade, generate a presentation snapshot, and explicitly confirm retention deletion batches. The redesign must improve information hierarchy and operational confidence without changing existing routes, Jinja variables, form names, API contracts, or error semantics.

## Visual direction

Use a calm, professional educational operations dashboard: deep navy identity, soft cool-grey canvas, white elevated work surfaces, clear Chinese typography, accessible contrast, strong status visibility, and generous spacing. Avoid consumer-style gradients, decorative illustrations, neon colours, or a frontend-framework dependency.

## Tokens

- Font: `Microsoft YaHei`, `PingFang SC`, `Segoe UI`, system sans-serif.
- Ink: `#172033`; muted: `#667085`; canvas: `#f6f8fc`; surface: `#ffffff`.
- Primary navy: `#173b67`; hover: `#102d50`; pale navy: `#eaf1fb`.
- Success: `#067647` on `#ecfdf3`; warning: `#b54708` on `#fffaeb`; danger: `#b42318` on `#fef3f2`; neutral: `#475467` on `#f2f4f7`.
- Radius: 10px cards, 8px controls, pill status chips.
- Shadow: `0 1px 2px rgba(16,24,40,.05), 0 1px 3px rgba(16,24,40,.10)` only for elevated surfaces.
- Desktop layout: persistent 232px navigation rail; responsive compact top bar below 900px; content max 1280px.
- Spacing: 4px base unit; page 32px desktop / 20px mobile; card padding 20px to 24px.

## Interaction rules

- Preserve all real statuses; `scoring_failed` must expose cause and retry record, never an invented grade.
- Keep review submission idempotent and visibly disable duplicate submits.
- Treat deletion as high risk: clear scope, exclusions, warning treatment and secondary confirmation.
- Use semantic HTML, visible focus states, readable tables/cards, and mobile-safe overflow handling.
- New visual code remains server-rendered Jinja plus native CSS/JavaScript; no new backend endpoints or external UI libraries.

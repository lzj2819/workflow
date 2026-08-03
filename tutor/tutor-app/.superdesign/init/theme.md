# Theme tokens

## Compact token summary

- Product: Chinese teacher assessment workspace; SSR, desktop-first, no frontend framework.
- Typeface: `Microsoft YaHei`, `PingFang SC`, system sans-serif.
- Primary: navy `#1f3a5f`; nav link `#cfe0f5`.
- Page/text: background `#f5f7fa`; text `#1f2933`; muted `#868e96`.
- Surfaces/borders: white `#fff`; `#d9e2ec`; inputs `#bcccdc`.
- Success: `#d3f9d8` / `#2b8a3e`; danger `#fff5f5` / `#ffa8a8` / `#c92a2a`.
- Radius: 4px controls/badges, 6px cards/panels. No shadows.
- Layout: max content width 960px; 1.2rem desktop outer margin; 1rem mobile gutter.

## Raw source

```css
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0; color: #1f2933; background: #f5f7fa; }
header.site { background: #1f3a5f; color: #fff; padding: 0.6rem 1.2rem; display: flex; gap: 1rem; align-items: baseline; }
header.site a { color: #cfe0f5; text-decoration: none; font-size: 0.9rem; }
main { max-width: 960px; margin: 1.2rem auto; padding: 0 1rem; }
.card { background: #fff; border: 1px solid #d9e2ec; border-radius: 6px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; background: #e4e7eb; font-size: 0.85rem; }
.badge.scoring_failed, .badge.upload_failed, .badge.rejected { background: #f8d7da; color: #842029; }
.badge.scored { background: #d3f9d8; color: #2b8a3e; }
.missing-mark { border: 1px dashed #c92a2a; color: #c92a2a; }
.missing-value { color: #868e96; font-style: italic; }
```

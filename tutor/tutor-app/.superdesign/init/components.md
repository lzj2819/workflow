# Shared UI primitives

This Jinja SSR application has no standalone component directory. Reusable primitives are CSS classes defined in `server/course_app/teacher_web/ui/templates/base.html` and consumed by every page template.

## Base primitives

- Source: `server/course_app/teacher_web/ui/templates/base.html`
- Components: `.card`, `.badge`, `.missing-mark`, `.missing-value`, `.error-panel`, `.notice-panel`, `.block`, form controls, buttons and tables.
- Props: supplied by Jinja page context; there are no independently exported component props.

```html
<div class="card">...</div>
<span class="badge {{ status }}">{{ status }}</span>
<div class="error-panel">{{ error }}</div>
<div class="notice-panel">{{ notice }}</div>
<span class="missing-mark">缺失：{{ mark }}</span>
```

There are no other shared UI source files to include.

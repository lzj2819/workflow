# Shared layouts

## Teacher application shell

- Source: `server/course_app/teacher_web/ui/templates/base.html`
- Description: Shared HTML document, compact top navigation, centred content area, global CSS primitives and progressive-enhancement form protection.

```html
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}教师工作台{% endblock %}</title>
<style>
body { font-family: "Microsoft YaHei", "PingFang SC", sans-serif; margin: 0; color: #1f2933; background: #f5f7fa; }
header.site { background: #1f3a5f; color: #fff; padding: 0.6rem 1.2rem; display: flex; gap: 1rem; align-items: baseline; }
header.site a { color: #cfe0f5; text-decoration: none; font-size: 0.9rem; }
main { max-width: 960px; margin: 1.2rem auto; padding: 0 1rem; }
.card { background: #fff; border: 1px solid #d9e2ec; border-radius: 6px; padding: 1rem 1.2rem; margin-bottom: 1rem; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; background: #e4e7eb; font-size: 0.85rem; }
.badge.scoring_failed, .badge.upload_failed, .badge.rejected { background: #f8d7da; color: #842029; }
.badge.scored { background: #d3f9d8; color: #2b8a3e; }
.missing-mark { display: inline-block; padding: 0.1rem 0.5rem; margin: 0.1rem; border: 1px dashed #c92a2a; color: #c92a2a; border-radius: 4px; font-size: 0.85rem; }
.missing-value { color: #868e96; font-style: italic; }
.error-panel { background: #fff5f5; border: 1px solid #ffa8a8; border-radius: 6px; padding: 0.8rem 1rem; margin-bottom: 1rem; }
.notice-panel { background: #ebfbee; border: 1px solid #8ce99a; border-radius: 6px; padding: 0.8rem 1rem; margin-bottom: 1rem; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #d9e2ec; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.92rem; }
form.inline label { display: block; margin: 0.5rem 0 0.2rem; font-size: 0.9rem; }
textarea, select, input[type=text], input[type=password] { width: 100%; max-width: 32rem; padding: 0.35rem; border: 1px solid #bcccdc; border-radius: 4px; box-sizing: border-box; }
button { padding: 0.4rem 1rem; border: 0; border-radius: 4px; background: #1f3a5f; color: #fff; cursor: pointer; }
button.danger { background: #c92a2a; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.block { border: 1px solid #bcccdc; border-radius: 6px; padding: 0.8rem 1rem; margin-bottom: 0.8rem; background: #fff; }
</style>
</head>
<body>
<header class="site">
<strong>教师工作台</strong>
<a href="/teacher/courses">课程</a>
</header>
<main>{% block content %}{% endblock %}</main>
<script>
document.querySelectorAll('form[data-lock]').forEach(function (f) {
  f.addEventListener('submit', function () {
    var b = f.querySelector('button[type=submit]');
    if (b) { b.disabled = true; }
  });
});
document.querySelectorAll('form[data-confirm]').forEach(function (f) {
  f.addEventListener('submit', function (e) {
    if (!window.confirm(f.getAttribute('data-confirm'))) { e.preventDefault(); }
  });
});
</script>
</body>
</html>
```

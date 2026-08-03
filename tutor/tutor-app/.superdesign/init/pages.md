# Key page dependency trees

## `/teacher/login`

Entry: `server/course_app/teacher_web/ui/templates/login.html`

Dependencies:
- `templates/login.html`
  - `templates/base.html`

Renders account/password inputs and inline login error.

## `/teacher/courses`

Entry: `server/course_app/teacher_web/ui/templates/courses.html`

Dependencies:
- `templates/courses.html`
  - `templates/base.html`

Renders course links and a deletion-batch table.

## `/teacher/courses/{course_id}`

Entry: `server/course_app/teacher_web/ui/templates/groups.html`

Dependencies:
- `templates/groups.html`
  - `templates/base.html`

Renders group links, presentation entry, and course-level deletion batches.

## `/teacher/courses/{course_id}/groups/{group_id}`

Entry: `server/course_app/teacher_web/ui/templates/students.html`

Dependencies:
- `templates/students.html`
  - `templates/base.html`

Renders student names and a submission status table.

## `/teacher/submissions/{submission_id}`

Entry: `server/course_app/teacher_web/ui/templates/submission_detail.html`

Dependencies:
- `templates/submission_detail.html`
  - `templates/base.html`

Renders material evidence, score/failure details, rationale, annotations, and review form.

## `/teacher/courses/{course_id}/presentation` and `/teacher/presentations`

Entries: `presentation_select.html`, `presentation.html`

Dependencies:
- `templates/presentation_select.html`
  - `templates/base.html`
- `templates/presentation.html`
  - `templates/base.html`

Renders group selection and read-only presentation snapshot blocks.

## `/teacher/deletion-batches/{batch_id}`

Entry: `server/course_app/teacher_web/ui/templates/deletion_batch.html`

Dependencies:
- `templates/deletion_batch.html`
  - `templates/base.html`

Renders retention scope, exclusions, and an explicitly confirmed destructive action.

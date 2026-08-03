# Teacher UI routes

Router source: `server/course_app/teacher_web/ui/views.py` via the application composition root. All pages extend `templates/base.html`.

| URL | Template / handler | Summary |
|---|---|---|
| `/teacher/login` | `login.html` | Teacher sign-in form. |
| `/teacher/courses` | `courses.html` | Course landing page and deletion-batch summary. |
| `/teacher/courses/{course_id}` | `groups.html` | Group list and display-view entry. |
| `/teacher/courses/{course_id}/groups/{group_id}` | `students.html` | Students and submission status table. |
| `/teacher/submissions/{submission_id}` | `submission_detail.html` | Submission evidence, score, feedback and review form. |
| `/teacher/courses/{course_id}/presentation` | `presentation_select.html` | Group selection for a presentation snapshot. |
| `/teacher/presentations` | `presentation.html` | Generated presentation blocks. |
| `/teacher/deletion-batches/{batch_id}` | `deletion_batch.html` | Retention/deletion review and confirmation. |
| `/teacher/deletion-batches/{batch_id}/confirm` | `deletion_batch_result.html` | Submitted deletion confirmation result. |
| error states | `error.html` | Contract/API error presentation. |

The routes consume only existing CT-007/008/009/011 contracts. UI work must not introduce new backend endpoints or alter contract semantics.

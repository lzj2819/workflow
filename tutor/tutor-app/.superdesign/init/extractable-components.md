# Extractable UI components

## TeacherAppShell

- Source: `server/course_app/teacher_web/ui/templates/base.html`
- Category: layout
- Description: Global top navigation and centred page shell.
- Extractable props: `activeItem` (default `courses`), `pageTitle`.
- Hardcoded: product name “教师工作台”, course navigation URL, base colour tokens.

## SurfaceCard

- Source: `server/course_app/teacher_web/ui/templates/base.html` (`.card`)
- Category: basic
- Description: White bordered content surface used by all workflows.
- Extractable props: `title`, `tone`.
- Hardcoded: spacing, border and radius.

## StatusBadge

- Source: `server/course_app/teacher_web/ui/templates/base.html` (`.badge`)
- Category: basic
- Description: Submission/deletion state label with success and error variants.
- Extractable props: `status`, `tone`.
- Hardcoded: compact label geometry.

## ReviewForm

- Source: `server/course_app/teacher_web/ui/templates/submission_detail.html`
- Category: basic
- Description: Annotation and final-grade form, retaining idempotent submit behavior.
- Extractable props: `grades`, `finalGradeEditable`, `draft`.
- Hardcoded: field labels and CT-008 submit semantics.

## DeletionConfirmation

- Source: `server/course_app/teacher_web/ui/templates/deletion_batch.html`
- Category: basic
- Description: High-risk batch confirmation panel.
- Extractable props: `batchId`, `scope`, `exclusions`, `status`.
- Hardcoded: destructive-action warning and confirmation requirement.

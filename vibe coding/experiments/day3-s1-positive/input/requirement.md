# S1 Day 3 Positive Calibration: Create a Short Note

This is a fresh public calibration task. It is not copied from Tutor material,
is not a migration fixture, and is not part of the formal C0--C5 experiment
dataset.

## Requirement

Provide one HTTP endpoint, `POST /notes`, for a client to create one short
note.

The request body contains exactly one field, `text`.

- If `text` contains 1 to 140 non-whitespace characters after trimming leading
  and trailing whitespace, the service stores the trimmed text and returns
  HTTP 201 with a JSON object containing a non-empty string `id` and the stored
  `text`.
- If `text` is empty after trimming or has more than 140 characters after
  trimming, the service returns HTTP 422 and does not create a note.
- A successful response must contain exactly the generated `id` and the stored
  trimmed `text`; no authentication, update, deletion, listing, persistence
  technology, retry, or additional behavior is in scope.

## Calibration boundary

Use only the requirement above. Do not import behavior from existing fixtures,
Tutor, hidden tests, or external examples. Any conclusion remains a Day 3
calibration result until the strict, Leaf, Coding, and pytest evidence has been
completed independently.

Feature: Save a short note

  # SC-S1-001
  @TC-S1-001 @REQ-S1
  Scenario: Store a non-empty note
    Given the note form is available
    When the user saves a non-empty note
    Then the note is stored with the submitted text

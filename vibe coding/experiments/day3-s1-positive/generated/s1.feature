Feature: Create a short note

  # SC-S1-VALID-TRIMMED
  @REQ-S1 @TC-S1-VALID-TRIMMED
  Scenario: Create a note with valid trimmed text
    Given a client has a request body containing only text "  short note  "
    When the client sends POST /notes
    Then the service stores text "short note" and returns status 201 with JSON containing exactly a non-empty string id and text "short note"

  # SC-S1-EMPTY-TRIMMED
  @REQ-S1 @TC-S1-EMPTY-TRIMMED
  Scenario: Reject text that is empty after trimming
    Given a client has a request body containing only text "   "
    When the client sends POST /notes
    Then the service returns status 422 and does not create a note

  # SC-S1-OVER-140-TRIMMED
  @REQ-S1 @TC-S1-OVER-140-TRIMMED
  Scenario: Reject text longer than 140 characters after trimming
    Given a client has a request body containing only text "1234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901"
    When the client sends POST /notes
    Then the service returns status 422 and does not create a note

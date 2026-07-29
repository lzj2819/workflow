Feature: Fresh Day 4 root health trace
  The root node exposes its local health status and public requirement trace.

  @REQ-D4-HEALTH
  Scenario: Root health endpoint reports an ok status
    Given the client has no request body
    When the client sends GET /health to Public API Service
    Then the response status code is 200
    And the response JSON field "status" equals "ok"

  @REQ-D4-TRACE
  Scenario: Root health endpoint reports its public trace identifiers
    Given the client has no request body
    When the client sends GET /health to Public API Service
    Then the response status code is 200
    And the response JSON field "node_id" equals "root"
    And the response JSON field "requirement_ids" equals ["REQ-D4-HEALTH", "REQ-D4-TRACE"]

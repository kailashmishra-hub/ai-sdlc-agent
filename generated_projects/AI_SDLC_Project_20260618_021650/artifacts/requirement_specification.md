```json
{
  "overview": "Build an application based on the uploaded requirements. Source summary: Functional Requirements Document (FRD) Project Name Hotel Booking Management System Module Name Booking Management Version 1.0 Purpose The Hotel Booking Management System provides API services that allow consumers to create hotel bookings and retrieve booking information using a unique Booking Identifier . The system exposes REST APIs for booking creation and booking retrieval. 1. Scope The scope of this document includes: Create Booking Retrieve Booking Details Booking Validation Booking Identi",
  "actors": [
    "End User",
    "Administrator",
    "External System"
  ],
  "functional_requirements": [
    "Users can submit and manage core business records.",
    "Administrators can configure business rules and review operational data.",
    "The system exposes APIs for creating, reading, updating, and deleting records."
  ],
  "non_functional_requirements": [
    "The application should be secure, maintainable, and observable.",
    "API responses should complete within acceptable business SLA limits.",
    "The solution should include automated tests and clear deployment configuration."
  ],
  "business_rules": [
    "Mandatory fields must be validated before persistence.",
    "Duplicate business records should be rejected."
  ],
  "assumptions": [
    "Uploaded documents contain the authoritative scope.",
    "Authentication can be integrated with an enterprise identity provider."
  ],
  "constraints": [
    "Generated code should match the selected technology stack.",
    "Generated tests should match the selected automation framework."
  ],
  "api_requirements": [
    "Provide REST endpoints for core domain operations.",
    "Return structured error responses for validation and system failures."
  ]
}
```
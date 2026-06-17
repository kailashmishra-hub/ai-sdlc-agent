from __future__ import annotations

from typing import Any

from ai_sdlc.agents.base import content_hint
from ai_sdlc.llm import LLMClient


class RequirementAgent:
    REQUIRED_LIST_FIELDS = [
        "actors",
        "functional_requirements",
        "non_functional_requirements",
        "business_rules",
        "assumptions",
        "constraints",
        "api_requirements",
    ]

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, extracted_content: str) -> dict[str, Any]:
        system = (
            "You are RequirementAgent for an AI SDLC platform. "
            "Analyze extracted document content and return only valid structured JSON."
        )
        user = f"""
Generate a Requirement Specification from the extracted document content.

Return this exact JSON shape:
{{
  "overview": "",
  "actors": [],
  "functional_requirements": [],
  "non_functional_requirements": [],
  "business_rules": [],
  "assumptions": [],
  "constraints": [],
  "api_requirements": []
}}

Rules:
- overview must describe the project overview.
- actors must identify users, systems, and external parties.
- functional_requirements must be clear system capabilities.
- non_functional_requirements must include quality attributes.
- business_rules must be enforceable rules.
- assumptions and constraints must be explicit.
- api_requirements must describe required APIs, endpoints, payloads, or integrations.

Content:
{extracted_content[:12000]}
"""
        response = self.llm.invoke_json(system, user)
        if response:
            return self._normalize(response, extracted_content)

        return self._fallback(extracted_content)

    def _normalize(self, response: dict[str, Any], extracted_content: str) -> dict[str, Any]:
        normalized = self._fallback(extracted_content)
        if isinstance(response.get("overview"), str) and response["overview"].strip():
            normalized["overview"] = response["overview"].strip()

        for field in self.REQUIRED_LIST_FIELDS:
            value = response.get(field)
            if isinstance(value, list):
                normalized[field] = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                normalized[field] = [value.strip()]

        return normalized

    def _fallback(self, extracted_content: str) -> dict[str, Any]:
        hint = content_hint(extracted_content)
        return {
            "overview": f"Build an application based on the uploaded requirements. Source summary: {hint}",
            "actors": ["End User", "Administrator", "External System"],
            "functional_requirements": [
                "Users can submit and manage core business records.",
                "Administrators can configure business rules and review operational data.",
                "The system exposes APIs for creating, reading, updating, and deleting records.",
            ],
            "non_functional_requirements": [
                "The application should be secure, maintainable, and observable.",
                "API responses should complete within acceptable business SLA limits.",
                "The solution should include automated tests and clear deployment configuration.",
            ],
            "business_rules": [
                "Mandatory fields must be validated before persistence.",
                "Duplicate business records should be rejected.",
            ],
            "assumptions": [
                "Uploaded documents contain the authoritative scope.",
                "Authentication can be integrated with an enterprise identity provider.",
            ],
            "constraints": [
                "Generated code should match the selected technology stack.",
                "Generated tests should match the selected automation framework.",
            ],
            "api_requirements": [
                "Provide REST endpoints for core domain operations.",
                "Return structured error responses for validation and system failures.",
            ],
        }

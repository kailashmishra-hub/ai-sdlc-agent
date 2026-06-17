from __future__ import annotations

import json
from typing import Any

from ai_sdlc.llm import LLMClient


class BusinessAnalystAgent:
    REQUIRED_FIELDS = ["epics", "features", "user_stories", "acceptance_criteria"]

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, requirement_spec: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You are BusinessAnalystAgent for an AI SDLC platform. "
            "Convert requirement specification JSON into analysis artifacts. "
            "Return only valid structured JSON."
        )
        user = f"""
Create Business Analyst artifacts from the Requirement Specification JSON.

Return this exact JSON shape:
{{
  "epics": [],
  "features": [],
  "user_stories": [
    {{
      "id": "",
      "role": "",
      "goal": "",
      "benefit": "",
      "story": "As a <role> I want <goal> So that <benefit>"
    }}
  ],
  "acceptance_criteria": [
    {{
      "story_id": "",
      "given": "",
      "when": "",
      "then": ""
    }}
  ]
}}

Rules:
- Epics must group major business capabilities.
- Features must be implementable product capabilities.
- Every user story must use: As a <role> I want <goal> So that <benefit>.
- Acceptance criteria must be testable and split into Given, When, Then.

Requirement specification:
{json.dumps(requirement_spec, indent=2)}
"""
        response = self.llm.invoke_json(system, user)
        if response:
            return self._normalize(response, requirement_spec)

        return self._fallback(requirement_spec)

    def _normalize(self, response: dict[str, Any], requirement_spec: dict[str, Any]) -> dict[str, Any]:
        normalized = self._fallback(requirement_spec)
        for field in ["epics", "features"]:
            value = response.get(field)
            if isinstance(value, list):
                normalized[field] = [str(item).strip() for item in value if str(item).strip()]
            elif isinstance(value, str) and value.strip():
                normalized[field] = [value.strip()]

        stories = response.get("user_stories")
        if isinstance(stories, list):
            normalized_stories = []
            for index, item in enumerate(stories, start=1):
                story = self._normalize_story(item, index)
                if story:
                    normalized_stories.append(story)
            if normalized_stories:
                normalized["user_stories"] = normalized_stories

        criteria = response.get("acceptance_criteria")
        if isinstance(criteria, list):
            normalized_criteria = []
            for index, item in enumerate(criteria, start=1):
                criterion = self._normalize_criterion(item, index)
                if criterion:
                    normalized_criteria.append(criterion)
            if normalized_criteria:
                normalized["acceptance_criteria"] = normalized_criteria
        else:
            normalized["acceptance_criteria"] = self._criteria_from_embedded_stories(normalized["user_stories"], response)

        return normalized

    def _normalize_story(self, item: Any, index: int) -> dict[str, str] | None:
        if isinstance(item, str):
            return {
                "id": f"US-{index:03d}",
                "role": "User",
                "goal": item,
                "benefit": "business value is delivered",
                "story": item if item.lower().startswith("as a ") else f"As a User I want {item} So that business value is delivered.",
            }
        if not isinstance(item, dict):
            return None

        story_id = str(item.get("id") or item.get("story_id") or f"US-{index:03d}").strip()
        role = str(item.get("role") or "User").strip()
        goal = str(item.get("goal") or item.get("title") or item.get("story") or "complete the workflow").strip()
        benefit = str(item.get("benefit") or "business value is delivered").strip()
        story_text = str(item.get("story") or "").strip()
        if not story_text.lower().startswith("as a "):
            story_text = f"As a {role} I want {goal} So that {benefit}."
        return {"id": story_id, "role": role, "goal": goal, "benefit": benefit, "story": story_text}

    def _normalize_criterion(self, item: Any, index: int) -> dict[str, str] | None:
        if isinstance(item, str):
            return {"story_id": f"US-{index:03d}", "given": item, "when": "the action is performed", "then": "the expected result occurs"}
        if not isinstance(item, dict):
            return None
        return {
            "story_id": str(item.get("story_id") or item.get("id") or f"US-{index:03d}").strip(),
            "given": str(item.get("given") or item.get("Given") or "the user has valid preconditions").strip(),
            "when": str(item.get("when") or item.get("When") or "the user performs the action").strip(),
            "then": str(item.get("then") or item.get("Then") or "the system returns the expected outcome").strip(),
        }

    def _criteria_from_embedded_stories(self, stories: list[dict[str, str]], response: dict[str, Any]) -> list[dict[str, str]]:
        criteria = []
        raw_stories = response.get("user_stories", [])
        if not isinstance(raw_stories, list):
            return criteria
        for index, raw_story in enumerate(raw_stories):
            if not isinstance(raw_story, dict):
                continue
            story_id = stories[index]["id"] if index < len(stories) else f"US-{index + 1:03d}"
            embedded = raw_story.get("acceptance_criteria", [])
            if isinstance(embedded, list):
                for item in embedded:
                    criterion = self._normalize_criterion({"story_id": story_id, **self._parse_given_when_then(str(item))}, index + 1)
                    if criterion:
                        criteria.append(criterion)
        return criteria or self._fallback({})["acceptance_criteria"]

    def _parse_given_when_then(self, text: str) -> dict[str, str]:
        lower = text.lower()
        given = text
        when = "the action is performed"
        then = "the expected result occurs"
        if " when " in lower:
            given = text[: lower.index(" when ")].strip()
            rest = text[lower.index(" when ") + 6 :]
            rest_lower = rest.lower()
            if " then " in rest_lower:
                when = rest[: rest_lower.index(" then ")].strip()
                then = rest[rest_lower.index(" then ") + 6 :].strip()
            else:
                when = rest.strip()
        return {"given": given, "when": when, "then": then}

    def _fallback(self, requirement_spec: dict[str, Any]) -> dict[str, Any]:
        actors = requirement_spec.get("actors") if isinstance(requirement_spec, dict) else []
        primary_actor = actors[0] if isinstance(actors, list) and actors else "End User"
        return {
            "epics": ["Core Application Workflow", "Administration and Governance"],
            "features": ["Record management", "Validation and error handling", "API integration"],
            "user_stories": [
                {
                    "id": "US-001",
                    "role": str(primary_actor),
                    "goal": "to create a business record",
                    "benefit": "I can complete the primary workflow",
                    "story": f"As a {primary_actor} I want to create a business record So that I can complete the primary workflow.",
                },
                {
                    "id": "US-002",
                    "role": "Administrator",
                    "goal": "to review submitted records",
                    "benefit": "I can monitor operational activity",
                    "story": "As an Administrator I want to review submitted records So that I can monitor operational activity.",
                },
            ],
            "acceptance_criteria": [
                {
                    "story_id": "US-001",
                    "given": "valid record details are available",
                    "when": "the user submits the record",
                    "then": "the record is saved successfully",
                },
                {
                    "story_id": "US-001",
                    "given": "mandatory data is missing",
                    "when": "the user submits the record",
                    "then": "validation messages are displayed",
                },
                {
                    "story_id": "US-002",
                    "given": "records exist",
                    "when": "the administrator opens the admin view",
                    "then": "a searchable list of records is displayed",
                },
            ],
        }

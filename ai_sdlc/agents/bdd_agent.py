from __future__ import annotations

import json
from typing import Any

from ai_sdlc.llm import LLMClient


class BDDAgent:
    REQUIRED_SECTIONS = ["Positive Scenarios", "Negative Scenarios", "Boundary Scenarios", "Error Scenarios"]
    REQUIRED_LABELS = ["Feature:", "Scenario:", "Given:", "When:", "Then:"]

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, ba_output: dict[str, Any]) -> str:
        user_stories = self._extract_user_stories(ba_output)
        system = (
            "You are BDDAgent for an AI SDLC platform. "
            "Generate behavior-driven development scenarios from user stories. "
            "Return markdown only."
        )
        user = f"""
Generate BDD scenarios from the user stories.

Required sections:
1. Positive Scenarios
2. Negative Scenarios
3. Boundary Scenarios
4. Error Scenarios

Every scenario must use this exact label format:
Feature:
Scenario:
Given:
When:
Then:

User stories:
{json.dumps(user_stories, indent=2)}
"""
        response = self.llm.invoke_text(system, user)
        if response and self._is_complete_markdown(response):
            return self._normalize_labels(response)

        return self._fallback(user_stories)

    def _extract_user_stories(self, ba_output: dict[str, Any]) -> list[dict[str, str]]:
        stories = ba_output.get("user_stories", []) if isinstance(ba_output, dict) else []
        if not isinstance(stories, list):
            return []
        normalized = []
        for index, story in enumerate(stories, start=1):
            if isinstance(story, dict):
                normalized.append(
                    {
                        "id": str(story.get("id") or f"US-{index:03d}"),
                        "story": str(story.get("story") or ""),
                        "role": str(story.get("role") or "User"),
                        "goal": str(story.get("goal") or "complete the workflow"),
                        "benefit": str(story.get("benefit") or "business value is delivered"),
                    }
                )
            elif isinstance(story, str):
                normalized.append(
                    {
                        "id": f"US-{index:03d}",
                        "story": story,
                        "role": "User",
                        "goal": story,
                        "benefit": "business value is delivered",
                    }
                )
        return normalized

    def _is_complete_markdown(self, markdown: str) -> bool:
        return all(section in markdown for section in self.REQUIRED_SECTIONS) and all(
            label in markdown for label in self.REQUIRED_LABELS
        )

    def _normalize_labels(self, markdown: str) -> str:
        replacements = {
            "\nFeature ": "\nFeature: ",
            "\nScenario ": "\nScenario: ",
            "\nGiven ": "\nGiven: ",
            "\nWhen ": "\nWhen: ",
            "\nThen ": "\nThen: ",
        }
        normalized = markdown.strip()
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        return normalized + "\n"

    def _fallback(self, user_stories: list[dict[str, str]]) -> str:
        story = user_stories[0] if user_stories else {}
        feature = self._feature_name(story)
        role = story.get("role", "user")
        goal = self._readable_goal(story.get("goal", "complete the primary workflow"))
        return f"""## Positive Scenarios

Feature: {feature}
Scenario: Complete the primary user story successfully
Given: a {role} has valid data and permission to {goal}
When: the {role} performs the requested action
Then: the system completes the action and confirms the successful outcome

## Negative Scenarios

Feature: {feature}
Scenario: Reject invalid or incomplete input
Given: a {role} provides missing or invalid details
When: the {role} submits the request
Then: the system rejects the request and displays validation feedback

## Boundary Scenarios

Feature: {feature}
Scenario: Process values at the allowed boundary
Given: a {role} provides values at the minimum or maximum allowed limits
When: the {role} submits the request
Then: the system processes the request without data loss or unexpected errors

## Error Scenarios

Feature: {feature}
Scenario: Handle downstream service failure
Given: a required downstream service is unavailable
When: the system processes the request
Then: the system returns a structured error response and preserves transaction integrity
"""

    def _feature_name(self, story: dict[str, str]) -> str:
        goal = story.get("goal") or "Core workflow"
        words = goal.replace("to ", "", 1).strip().split()
        return " ".join(word.capitalize() for word in words[:5]) or "Core Workflow"

    def _readable_goal(self, goal: str) -> str:
        clean = goal.strip()
        return clean[3:] if clean.lower().startswith("to ") else clean

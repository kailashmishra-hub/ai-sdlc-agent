from __future__ import annotations

import re

from ai_sdlc.llm import LLMClient


class TestCaseAgent:
    REQUIRED_COLUMNS = ["Test Case ID", "Scenario", "Preconditions", "Steps", "Expected Result", "Priority"]

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, bdd: str) -> str:
        system = (
            "You are TestCaseAgent for an AI SDLC platform. "
            "Generate manual test cases from BDD scenarios. "
            "Return a markdown table only."
        )
        user = f"""
Generate manual test cases from these BDD scenarios.

The markdown table must have exactly these columns:
Test Case ID
Scenario
Preconditions
Steps
Expected Result
Priority

BDD:
{bdd}
"""
        response = self.llm.invoke_text(system, user)
        if response and self._is_valid_markdown_table(response):
            return response.strip() + "\n"
        return self._fallback(bdd)

    def _is_valid_markdown_table(self, markdown: str) -> bool:
        lines = [line.strip() for line in markdown.strip().splitlines() if line.strip()]
        if len(lines) < 3:
            return False
        header = self._split_table_row(lines[0])
        return header == self.REQUIRED_COLUMNS and all("|" in line for line in lines[:3])

    def _split_table_row(self, row: str) -> list[str]:
        return [cell.strip() for cell in row.strip().strip("|").split("|")]

    def _fallback(self, bdd: str) -> str:
        scenarios = self._extract_scenarios(bdd)
        if not scenarios:
            scenarios = [
                {
                    "scenario": "Validate primary workflow",
                    "given": "User has valid preconditions",
                    "when": "User performs the requested action",
                    "then": "System returns the expected outcome",
                    "priority": "High",
                }
            ]

        rows = [
            "| Test Case ID | Scenario | Preconditions | Steps | Expected Result | Priority |",
            "|---|---|---|---|---|---|",
        ]
        for index, scenario in enumerate(scenarios, start=1):
            rows.append(
                "| "
                + " | ".join(
                    [
                        f"TC-{index:03d}",
                        self._clean_cell(scenario["scenario"]),
                        self._clean_cell(scenario["given"]),
                        self._clean_cell(scenario["when"]),
                        self._clean_cell(scenario["then"]),
                        scenario["priority"],
                    ]
                )
                + " |"
            )
        return "\n".join(rows) + "\n"

    def _extract_scenarios(self, bdd: str) -> list[dict[str, str]]:
        blocks = re.split(r"(?=Scenario:)", bdd)
        scenarios = []
        for block in blocks:
            if "Scenario:" not in block:
                continue
            scenario = self._extract_label(block, "Scenario") or "Unnamed scenario"
            given = self._extract_label(block, "Given") or "required preconditions are met"
            when = self._extract_label(block, "When") or "the user performs the action"
            then = self._extract_label(block, "Then") or "the expected result occurs"
            scenarios.append(
                {
                    "scenario": scenario,
                    "given": given,
                    "when": when,
                    "then": then,
                    "priority": self._priority_for(scenario, block),
                }
            )
        return scenarios

    def _extract_label(self, block: str, label: str) -> str:
        match = re.search(rf"^{label}:\s*(.+)$", block, flags=re.IGNORECASE | re.MULTILINE)
        return match.group(1).strip() if match else ""

    def _priority_for(self, scenario: str, block: str) -> str:
        text = f"{scenario} {block}".lower()
        if any(term in text for term in ["error", "failure", "reject", "invalid", "missing"]):
            return "High"
        if any(term in text for term in ["boundary", "minimum", "maximum", "limit"]):
            return "Medium"
        return "High"

    def _clean_cell(self, value: str) -> str:
        return " ".join(value.replace("|", "/").split())

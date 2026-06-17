from __future__ import annotations

import json
import re
from typing import Any, Callable, TypedDict

from ai_sdlc.agents import AutomationAgent, BDDAgent, BusinessAnalystAgent, DeveloperAgent, RequirementAgent, TestCaseAgent
from ai_sdlc.config import AppConfig
from ai_sdlc.llm import LLMClient


ProgressCallback = Callable[[str, str, int], None]


class WorkflowState(TypedDict, total=False):
    extracted_content: str
    config: AppConfig
    requirement_spec: dict[str, Any]
    ba_output: dict[str, Any]
    bdd: str
    source_code: dict[str, str]
    test_cases: str
    automation_files: dict[str, str]


def run_sdlc_workflow(extracted_content: str, config: AppConfig, on_progress: ProgressCallback | None = None) -> dict[str, object]:
    llm = LLMClient(config)
    agents = {
        "requirements": RequirementAgent(llm),
        "ba": BusinessAnalystAgent(llm),
        "bdd": BDDAgent(llm),
        "developer": DeveloperAgent(llm),
        "test": TestCaseAgent(llm),
        "automation": AutomationAgent(llm),
    }

    def progress(agent: str, status: str, value: int) -> None:
        if on_progress:
            on_progress(agent, status, value)

    def requirement_node(state: WorkflowState) -> WorkflowState:
        progress("Requirement Agent", "Generating requirement specification", 35)
        state["requirement_spec"] = agents["requirements"].run(state["extracted_content"])
        return state

    def ba_node(state: WorkflowState) -> WorkflowState:
        progress("BA Agent", "Generating epics, features, user stories, and acceptance criteria", 48)
        state["ba_output"] = agents["ba"].run(state["requirement_spec"])
        return state

    def bdd_node(state: WorkflowState) -> WorkflowState:
        progress("BDD Agent", "Generating BDD scenarios", 60)
        state["bdd"] = agents["bdd"].run(state["ba_output"])
        return state

    def developer_node(state: WorkflowState) -> WorkflowState:
        progress("Developer Agent", "Generating application source code", 72)
        state["source_code"] = agents["developer"].run(
            state["requirement_spec"], state["ba_output"], state["bdd"], state["config"]
        )
        return state

    def test_node(state: WorkflowState) -> WorkflowState:
        progress("Test Case Agent", "Generating manual test cases", 84)
        state["test_cases"] = agents["test"].run(state["bdd"])
        return state

    def automation_node(state: WorkflowState) -> WorkflowState:
        progress("Automation Agent", "Generating automation framework", 94)
        state["automation_files"] = agents["automation"].run(state["bdd"], state["test_cases"], state["config"])
        return state

    state: WorkflowState = {"extracted_content": extracted_content, "config": config}
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(WorkflowState)
        graph.add_node("requirements", requirement_node)
        graph.add_node("ba", ba_node)
        graph.add_node("bdd", bdd_node)
        graph.add_node("developer", developer_node)
        graph.add_node("test", test_node)
        graph.add_node("automation", automation_node)
        graph.set_entry_point("requirements")
        graph.add_edge("requirements", "ba")
        graph.add_edge("ba", "bdd")
        graph.add_edge("bdd", "developer")
        graph.add_edge("developer", "test")
        graph.add_edge("test", "automation")
        graph.add_edge("automation", END)
        state = graph.compile().invoke(state)
    except Exception:
        for node in [requirement_node, ba_node, bdd_node, developer_node, test_node, automation_node]:
            state = node(state)

    requirement_spec = state["requirement_spec"]
    ba_output = state["ba_output"]
    user_stories = _stories_markdown(ba_output)
    acceptance_criteria = _criteria_markdown(ba_output)
    automation_files = state["automation_files"]
    source_code = state["source_code"]
    traceability = _traceability_markdown(ba_output, state["bdd"], state["test_cases"])

    return {
        "Requirement Specification": _requirements_markdown(requirement_spec),
        "User Stories": user_stories,
        "Acceptance Criteria": acceptance_criteria,
        "BDD Scenarios": state["bdd"],
        "Test Cases": state["test_cases"],
        "Traceability Matrix": traceability,
        "Automation Framework": _files_markdown(automation_files),
        "Generated Source Code": source_code,
        "Automation Source Files": automation_files,
    }


def _requirements_markdown(requirement_spec: dict[str, Any]) -> str:
    sections = [
        ("Project Overview", "overview"),
        ("Actors", "actors"),
        ("Functional Requirements", "functional_requirements"),
        ("Non Functional Requirements", "non_functional_requirements"),
        ("Business Rules", "business_rules"),
        ("Assumptions", "assumptions"),
        ("Constraints", "constraints"),
        ("API Requirements", "api_requirements"),
    ]
    lines = ["# Requirement Specification"]
    for title, key in sections:
        lines.append(f"## {title}")
        value = requirement_spec.get(key, "")
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        elif isinstance(value, dict):
            lines.extend(f"- **{item_key}:** {item_value}" for item_key, item_value in value.items())
        elif value:
            lines.append(str(value))
        else:
            lines.append("_Not specified._")
        lines.append("")
    return "\n".join(lines).strip()


def _stories_markdown(ba_output: dict[str, Any]) -> str:
    stories = ba_output.get("user_stories", [])
    if isinstance(stories, list):
        lines = ["# User Stories"]
        for story in stories:
            if isinstance(story, dict):
                lines.append(f"## {story.get('id', 'Story')}")
                lines.append(str(story.get("story", "")))
            else:
                lines.append(f"- {story}")
        return "\n\n".join(lines)
    return json.dumps(stories, indent=2)


def _criteria_markdown(ba_output: dict[str, Any]) -> str:
    lines = ["# Acceptance Criteria"]
    criteria = ba_output.get("acceptance_criteria", [])
    if isinstance(criteria, list):
        for criterion in criteria:
            if isinstance(criterion, dict):
                lines.append(f"## {criterion.get('story_id', 'Story')}")
                lines.append("```gherkin")
                lines.append(f"Given: {criterion.get('given', '')}")
                lines.append(f"When: {criterion.get('when', '')}")
                lines.append(f"Then: {criterion.get('then', '')}")
                lines.append("```")
            else:
                lines.append("```gherkin")
                lines.append(str(criterion))
                lines.append("```")
    return "\n\n".join(lines)


def _traceability_markdown(ba_output: dict[str, Any], bdd: str, test_cases: str) -> str:
    stories = _extract_traceability_stories(ba_output)
    scenarios = _extract_bdd_scenario_names(bdd)
    cases = _extract_test_cases(test_cases)
    rows = [
        "# User Story To BDD And Test Case Mapping",
        "",
        "| User Story ID | User Story | BDD Scenarios | Test Cases |",
        "|---|---|---|---|",
    ]

    if not stories:
        stories = [{"id": "US-001", "story": "Generated user story"}]

    for index, story in enumerate(stories):
        scenario_names = _related_items(index, len(stories), scenarios)
        case_names = _related_items(index, len(stories), cases)
        rows.append(
            "| "
            + " | ".join(
                [
                    _table_cell(story["id"]),
                    _table_cell(story["story"]),
                    _table_cell("<br>".join(scenario_names) if scenario_names else "Not generated"),
                    _table_cell("<br>".join(case_names) if case_names else "Not generated"),
                ]
            )
            + " |"
        )
    return "\n".join(rows)


def _extract_traceability_stories(ba_output: dict[str, Any]) -> list[dict[str, str]]:
    raw_stories = ba_output.get("user_stories", [])
    if not isinstance(raw_stories, list):
        return []
    stories = []
    for index, item in enumerate(raw_stories, start=1):
        if isinstance(item, dict):
            stories.append(
                {
                    "id": str(item.get("id") or f"US-{index:03d}"),
                    "story": str(item.get("story") or item.get("goal") or "Generated user story"),
                }
            )
        elif isinstance(item, str):
            stories.append({"id": f"US-{index:03d}", "story": item})
    return stories


def _extract_bdd_scenario_names(bdd: str) -> list[str]:
    scenarios = re.findall(r"^Scenario:\s*(.+)$", bdd, flags=re.IGNORECASE | re.MULTILINE)
    return [scenario.strip() for scenario in scenarios if scenario.strip()]


def _extract_test_cases(test_cases: str) -> list[str]:
    rows = []
    for line in test_cases.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] in {"Test Case ID", "---"} or set(cells[0]) == {"-"}:
            continue
        if cells[0].startswith("TC-"):
            rows.append(f"{cells[0]}: {cells[1]}")
    return rows


def _related_items(index: int, story_count: int, items: list[str]) -> list[str]:
    if not items:
        return []
    if story_count <= 1:
        return items
    chunk_size = max(1, (len(items) + story_count - 1) // story_count)
    start = index * chunk_size
    end = start + chunk_size
    return items[start:end] or [items[min(index, len(items) - 1)]]


def _table_cell(value: str) -> str:
    return " ".join(value.replace("|", "/").split())


def _files_markdown(files: dict[str, str]) -> str:
    lines = ["# Automation Framework"]
    for path, content in files.items():
        language = "java" if path.endswith(".java") else "python" if path.endswith(".py") else "text"
        lines.append(f"## {path}\n\n```{language}\n{content}\n```")
    return "\n\n".join(lines)

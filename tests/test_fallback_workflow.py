from pathlib import Path

from ai_sdlc.config import AppConfig
from ai_sdlc.agents.automation_agent import AutomationAgent
from ai_sdlc.agents.bdd_agent import BDDAgent
from ai_sdlc.agents.business_analyst_agent import BusinessAnalystAgent
from ai_sdlc.agents.developer_agent import DeveloperAgent
from ai_sdlc.agents.requirement_agent import RequirementAgent
from ai_sdlc.agents.test_case_agent import TestCaseAgent as ManualTestCaseAgent
from ai_sdlc.llm import LLMClient
from ai_sdlc.output_manager import ProjectOutputManager
from ai_sdlc.workflow import run_sdlc_workflow


def test_workflow_generates_required_outputs(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Python",
        automation_framework="Playwright",
        output_directory=tmp_path,
    )

    outputs = run_sdlc_workflow("Users need to create and review business records.", config)

    assert "Requirement Specification" in outputs
    assert "User Stories" in outputs
    assert "BDD Scenarios" in outputs
    assert "Test Cases" in outputs
    assert "Traceability Matrix" in outputs
    assert "Automation Framework" in outputs
    assert "Generated Source Code" in outputs
    assert "```json" not in str(outputs["Requirement Specification"])
    assert "## Project Overview" in str(outputs["Requirement Specification"])
    assert "```gherkin" in str(outputs["Acceptance Criteria"])
    assert "Given:" in str(outputs["Acceptance Criteria"])
    assert "When:" in str(outputs["Acceptance Criteria"])
    assert "Then:" in str(outputs["Acceptance Criteria"])
    assert "| User Story ID | User Story | BDD Scenarios | Test Cases |" in str(outputs["Traceability Matrix"])
    assert "US-001" in str(outputs["Traceability Matrix"])
    assert "TC-001" in str(outputs["Traceability Matrix"])


def test_output_manager_creates_timestamped_project(tmp_path: Path):
    config = AppConfig(
        project_name="Hotel Booking",
        technology_stack="Java",
        automation_framework="Rest Assured",
        output_directory=tmp_path,
    )
    manager = ProjectOutputManager(config)

    project_dir = manager.create_project_directory()

    assert project_dir.exists()
    assert project_dir.name.startswith("Hotel_Booking_")


def test_requirement_agent_returns_structured_json(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Python",
        automation_framework="Playwright",
        output_directory=tmp_path,
    )
    agent = RequirementAgent(LLMClient(config))

    result = agent.run("The system must let customers create bookings and admins review them.")

    assert set(result) == {
        "overview",
        "actors",
        "functional_requirements",
        "non_functional_requirements",
        "business_rules",
        "assumptions",
        "constraints",
        "api_requirements",
    }
    assert isinstance(result["overview"], str)
    assert all(isinstance(result[key], list) for key in RequirementAgent.REQUIRED_LIST_FIELDS)


def test_business_analyst_agent_returns_prompt_shape(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Python",
        automation_framework="Playwright",
        output_directory=tmp_path,
    )
    requirement_spec = {
        "overview": "Booking platform",
        "actors": ["Customer", "Administrator"],
        "functional_requirements": ["Customers can create bookings"],
        "non_functional_requirements": [],
        "business_rules": [],
        "assumptions": [],
        "constraints": [],
        "api_requirements": [],
    }
    agent = BusinessAnalystAgent(LLMClient(config))

    result = agent.run(requirement_spec)

    assert set(result) == set(BusinessAnalystAgent.REQUIRED_FIELDS)
    assert result["epics"]
    assert result["features"]
    assert result["user_stories"][0]["story"].startswith("As a ")
    assert {"story_id", "given", "when", "then"} <= set(result["acceptance_criteria"][0])


def test_bdd_agent_returns_required_markdown_sections(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Python",
        automation_framework="Playwright",
        output_directory=tmp_path,
    )
    agent = BDDAgent(LLMClient(config))
    ba_output = {
        "user_stories": [
            {
                "id": "US-001",
                "role": "Customer",
                "goal": "to create a booking",
                "benefit": "I can reserve a room",
                "story": "As a Customer I want to create a booking So that I can reserve a room.",
            }
        ]
    }

    markdown = agent.run(ba_output)

    for section in BDDAgent.REQUIRED_SECTIONS:
        assert section in markdown
    for label in BDDAgent.REQUIRED_LABELS:
        assert label in markdown


def test_developer_agent_generates_required_java_files(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Java",
        automation_framework="Rest Assured",
        output_directory=tmp_path,
    )
    agent = DeveloperAgent(LLMClient(config))

    files = agent.run(
        requirement_spec={"overview": "Record management"},
        ba_output={
            "user_stories": [{"story": "As a User I want to create a record So that it is tracked."}],
            "acceptance_criteria": [{"given": "valid data", "when": "submitted", "then": "record is created"}],
        },
        bdd="Feature: Records\nScenario: Create record\nGiven: valid data\nWhen: submitted\nThen: record is created",
        config=config,
    )

    for path in DeveloperAgent.JAVA_REQUIRED_FILES:
        assert path in files
        assert files[path].strip()
    assert "spring-boot-starter-web" in files["pom.xml"]


def test_test_case_agent_returns_required_markdown_table(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Python",
        automation_framework="Playwright",
        output_directory=tmp_path,
    )
    agent = ManualTestCaseAgent(LLMClient(config))

    table = agent.run(
        """Feature: Records
Scenario: Create a valid record
Given: the user has valid record details
When: the user submits the record
Then: the system saves the record
"""
    )

    lines = table.strip().splitlines()
    assert lines[0] == "| Test Case ID | Scenario | Preconditions | Steps | Expected Result | Priority |"
    assert "TC-001" in table
    for column in ManualTestCaseAgent.REQUIRED_COLUMNS:
        assert column in lines[0]


def test_automation_agent_generates_rest_assured_project(tmp_path: Path):
    config = AppConfig(
        project_name="Demo",
        technology_stack="Java",
        automation_framework="Rest Assured",
        output_directory=tmp_path,
    )
    agent = AutomationAgent(LLMClient(config))

    files = agent.run(
        bdd="""Feature: Records
Scenario: Create a valid record
Given: the user has valid record details
When: the user submits the record
Then: the system saves the record
""",
        test_cases="",
        config=config,
    )

    for path in AutomationAgent.REQUIRED_REST_ASSURED_FILES:
        assert path in files
        assert files[path].strip()
    assert "io.rest-assured" in files["automation/pom.xml"]
    assert "class BaseTest" in files["automation/src/test/java/tests/BaseTest.java"]

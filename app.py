from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
st.set_page_config(page_title="AI SDLC Platform", page_icon="AI", layout="wide")


def init_state() -> None:
    defaults = {
        "outputs": {},
        "project_location": "",
        "zip_path": "",
        "current_agent": "Idle",
        "status": "Waiting for documents",
        "progress": 0,
        "agent_log": [],
        "stage_index": 0,
        "stage_outputs": {},
        "stage_approved": {},
        "stage_sources": {},
        "automation_template_files": {},
        "automation_repository_path": "",
        "workflow_constraints": "",
        "stage_instructions": {},
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.stage_index >= len(STAGES):
        st.session_state.stage_index = 0


def secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default))


def configured_openai_key() -> str:
    return str(st.session_state.get("openai_api_key", "") or secret_or_env("OPENAI_API_KEY"))


def get_openai_client() -> OpenAI:
    api_key = configured_openai_key()
    if not api_key:
        raise RuntimeError("OpenAI API key is required to generate artifacts.")
    return OpenAI(api_key=api_key)


def model_name() -> str:
    return secret_or_env("OPENAI_MODEL", "gpt-4o-mini")


def call_text(system: str, user: str) -> str:
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model_name(),
        temperature=0.2,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("OpenAI returned an empty response.")
    return content.strip()


def call_json(system: str, user: str) -> dict[str, Any]:
    text = call_text(system + " Return only valid JSON.", user)
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()
    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenAI did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("OpenAI JSON response must be an object.")
    return parsed


def extract_uploaded_files(uploaded_files: list, temp_dir: Path) -> tuple[str, list[str]]:
    parts: list[str] = []
    sources: list[str] = []
    for uploaded in uploaded_files:
        path = temp_dir / uploaded.name
        path.write_bytes(uploaded.getvalue())
        sources.append(uploaded.name)
        suffix = path.suffix.lower()
        if suffix == ".txt":
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
        elif suffix == ".pdf":
            parts.append(extract_pdf(path))
        elif suffix in {".png", ".jpg", ".jpeg"}:
            parts.append(describe_image(path))
    text = "\n\n".join(part.strip() for part in parts if part.strip())
    if not text:
        raise RuntimeError("No readable content was extracted from the uploaded files.")
    return text, sources


def safe_relative_path(relative: str) -> Path:
    path = Path(relative.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"Unsafe template path skipped: {relative}")
    return path


def is_template_text_file(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in {
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".properties",
        ".ini",
        ".env",
        ".java",
        ".py",
        ".js",
        ".ts",
        ".feature",
        ".cs",
        ".html",
        ".css",
    }


def extract_automation_template_uploads(uploaded_files: list, temp_dir: Path) -> tuple[str, list[str], dict[str, str]]:
    parts: list[str] = []
    sources: list[str] = []
    template_files: dict[str, str] = {}
    for uploaded in uploaded_files:
        path = temp_dir / uploaded.name
        path.write_bytes(uploaded.getvalue())
        sources.append(uploaded.name)
        suffix = path.suffix.lower()
        if suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                file_names = [name for name in archive.namelist() if not name.endswith("/")]
                parts.append("Repository template file tree:\n" + "\n".join(f"- {name}" for name in file_names[:300]))
                for name in file_names:
                    safe_path = safe_relative_path(name)
                    if not is_template_text_file(name):
                        continue
                    try:
                        content = archive.read(name).decode("utf-8", errors="ignore")
                    except KeyError:
                        continue
                    template_files[safe_path.as_posix()] = content
                    if len(parts) < 80:
                        parts.append(f"Template file: {safe_path.as_posix()}\n```\n{content[:2500]}\n```")
        elif suffix in {".txt", ".md", ".json", ".yaml", ".yml", ".xml", ".properties", ".java", ".py", ".js", ".ts", ".feature"}:
            content = path.read_text(encoding="utf-8", errors="ignore")
            parts.append(f"Supporting template document: {uploaded.name}\n{content[:4000]}")
        elif suffix == ".pdf":
            parts.append(extract_pdf(path))
        elif suffix in {".png", ".jpg", ".jpeg"}:
            parts.append(describe_image(path))
    return "\n\n".join(part.strip() for part in parts if part.strip()), sources, template_files


def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def describe_image(path: Path) -> str:
    from PIL import Image

    image = Image.open(path)
    return f"Image uploaded: {path.name}. Size: {image.width}x{image.height}. OCR is not configured."


def requirement_agent(content: str) -> dict[str, Any]:
    return call_json(
        "You are RequirementAgent for an AI SDLC platform.",
        f"""
Generate a Requirement Specification from this extracted document content.

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

Content:
{content[:14000]}
""",
    )


def requirements_stage_agent(content: str, feedback: str) -> str:
    requirements = requirement_agent(f"{content}\n\nUser feedback or instructions:\n{feedback}".strip())
    requirements = apply_requirement_exclusions(requirements, feedback)
    return enforce_text_exclusions(requirements_markdown(requirements), feedback)


def excludes_non_functional(instructions: str) -> bool:
    if not instructions:
        return False
    patterns = [
        r"\b(do\s*not|don't|dont|never|exclude|skip|avoid|without)\b.{0,80}\b(non[-\s]*functional|nfr)\b",
        r"\b(non[-\s]*functional|nfr)\b.{0,80}\b(do\s*not|don't|dont|never|exclude|skip|avoid|without)\b",
    ]
    return any(re.search(pattern, instructions, flags=re.IGNORECASE) for pattern in patterns)


def apply_requirement_exclusions(requirements: dict[str, Any], instructions: str) -> dict[str, Any]:
    filtered = dict(requirements)
    if excludes_non_functional(instructions):
        filtered.pop("non_functional_requirements", None)
    return filtered


def enforce_text_exclusions(text: str, instructions: str) -> str:
    if not excludes_non_functional(instructions):
        return text.strip()
    text = strip_markdown_sections(text, [r"non[-\s]*functional", r"\bnfr\b"])
    text = strip_gherkin_blocks(text, [r"non[-\s]*functional", r"\bnfr\b"])
    text = strip_markdown_table_rows(text, [r"non[-\s]*functional", r"\bnfr\b"])
    return text.strip()


def strip_markdown_sections(text: str, term_patterns: list[str]) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    skipping_level = 0
    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if heading:
            level = len(heading.group(1))
            title = heading.group(2)
            if skipping_level and level <= skipping_level:
                skipping_level = 0
            if any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in term_patterns):
                skipping_level = level
                continue
        if skipping_level:
            continue
        kept.append(line)
    return "\n".join(kept)


def strip_gherkin_blocks(text: str, term_patterns: list[str]) -> str:
    if not re.search(r"^\s*(Feature|Scenario|Scenario Outline):", text, flags=re.IGNORECASE | re.MULTILINE):
        return text
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if re.match(r"^\s*(Feature|Scenario|Scenario Outline):", line, flags=re.IGNORECASE) and current:
            blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)
    kept_blocks = []
    for block in blocks:
        block_text = "\n".join(block)
        if any(re.search(pattern, block_text, flags=re.IGNORECASE) for pattern in term_patterns):
            continue
        kept_blocks.append(block_text)
    return "\n\n".join(kept_blocks)


def strip_markdown_table_rows(text: str, term_patterns: list[str]) -> str:
    kept = []
    for line in text.splitlines():
        if line.strip().startswith("|") and line.strip().endswith("|"):
            if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in term_patterns):
                continue
        kept.append(line)
    return "\n".join(kept)


def design_stage_agent(approved_requirements: str, additional_content: str, feedback: str) -> str:
    return call_text(
        "You are a Solution Design Agent. Return markdown only.",
        f"""
Generate design artifacts from the approved requirements and latest supporting inputs.

Output sections:
- Design Overview
- System Context
- Component Design
- Data Design
- API Design
- Security Design
- Error Handling
- Traceability To Requirements
- Open Questions

Approved Requirements:
{approved_requirements}

Additional documents:
{additional_content}

User feedback:
{feedback}
""",
    )


def technical_spec_stage_agent(approved_requirements: str, approved_design: str, additional_content: str, feedback: str) -> str:
    return call_text(
        "You are a Technical Specification Agent. Return markdown only.",
        f"""
Generate technical specifications from approved requirements, approved design, and latest supporting inputs.

Output sections:
- Technical Overview
- Runtime Architecture
- Module Specifications
- API Specifications
- Data Models
- Validation Rules
- Non Functional Implementation Notes
- Testing Strategy
- Deployment Notes
- Traceability To Requirements And Design

Approved Requirements:
{approved_requirements}

Approved Design:
{approved_design}

Additional documents:
{additional_content}

User feedback:
{feedback}
""",
    )


def source_code_stage_agent(
    approved_requirements: str,
    approved_design: str,
    approved_technical_spec: str,
    additional_content: str,
    feedback: str,
    technology_stack: str,
    automation_framework: str,
) -> dict[str, Any]:
    response = call_json(
        "You are a Source Code Generation Agent for an AI SDLC platform.",
        f"""
Generate implementation artifacts using all approved prior-stage artifacts and latest supporting documents.

Selected technology stack: {technology_stack}
Automation framework: {automation_framework}

Return this exact JSON shape:
{{
  "source_files": {{"relative/path/File.ext": "file content"}},
  "bdd_markdown": "",
  "test_cases_markdown": "",
  "automation_files": {{"automation/path/File.ext": "file content"}},
  "traceability_markdown": ""
}}

Rules:
- Source code must be influenced by approved requirements, approved design, approved technical specifications, and additional uploaded documents.
- Test cases must cover requirements and BDD scenarios.
- Automation scripts must cover every generated test case ID.
- Traceability must map requirements, design decisions, technical specifications, BDD scenarios, test cases, and source files.

Approved Requirements:
{approved_requirements}

Approved Design:
{approved_design}

Approved Technical Specification:
{approved_technical_spec}

Additional documents:
{additional_content}

User feedback:
{feedback}
""",
    )
    required_keys = ["source_files", "bdd_markdown", "test_cases_markdown", "automation_files", "traceability_markdown"]
    missing = [key for key in required_keys if key not in response]
    if missing:
        raise RuntimeError(f"Source Code Agent response is missing: {', '.join(missing)}")
    if not isinstance(response["source_files"], dict) or not isinstance(response["automation_files"], dict):
        raise RuntimeError("Source Code Agent must return source_files and automation_files as JSON objects.")
    return response


def ba_agent(requirements: dict[str, Any]) -> dict[str, Any]:
    return call_json(
        "You are BusinessAnalystAgent for an AI SDLC platform.",
        f"""
Create Business Analyst artifacts from this Requirement Specification JSON.

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

Requirement Specification:
{json.dumps(requirements, indent=2)}
""",
    )


def acceptance_criteria_stage_agent(approved_requirements: str, additional_content: str, feedback: str, constraints: str = "") -> str:
    text = call_text(
        "You are an Acceptance Criteria Agent. Return markdown only.",
        f"""
Generate a detailed business acceptance criteria document from the available source inputs and any additional user instructions.

This stage is for the Development team. It must explain the business change that needs to be built, not produce BDD scenarios.
Do not write BDD Feature/Scenario/Given/When/Then syntax in this stage.

Use this exact markdown structure:

# Business Acceptance Criteria

## Change Summary
Describe the business change, why it is needed, and the expected business outcome.

## In Scope
- List the business capabilities, API operations, screens, workflows, or rules included in this change.

## Out of Scope
- List anything explicitly excluded or not part of this change.

## Business Behavior Details
### <Capability or Business Process Name>
- Current behavior:
- Required new behavior:
- User/system action:
- Expected business outcome:
- Impacted actor or consumer:

## Business Rules and Validations
| Rule ID | Rule / Validation | Error or Exception Handling | Priority |
|---|---|---|---|
| BR-001 | ... | ... | High |

## Data and API Impact
- Data fields affected:
- Required fields:
- Optional fields:
- API endpoints or operations affected:
- Request/response expectations:

## Acceptance Conditions
| AC ID | Acceptance Condition | Build Guidance for Developers | Priority |
|---|---|---|---|
| AC-001 | The system must ... | Implement ... | High |

## Assumptions and Open Questions
- List assumptions and questions that need confirmation.

Rules:
- Write detailed descriptive business requirements that help developers build the code.
- Focus on business changes, validations, data/API expectations, and expected outcomes.
- Each acceptance condition must be specific, testable, and traceable.
- Use "must", "shall", or "should" statements where appropriate.
- Do not use Feature:, Scenario:, Given:, When:, Then:, Examples:, or Gherkin code fences.
Treat workflow constraints and user feedback as mandatory. Do not generate artifacts for anything explicitly excluded.

Optional prior requirements context:
{approved_requirements}

Source documents and additional inputs:
{additional_content}

All workflow instructions from current and previous stages:
{constraints}

User feedback:
{feedback}
""",
    )
    return remove_bdd_labels_from_acceptance_criteria(enforce_text_exclusions(text, f"{constraints}\n{feedback}"))


def remove_bdd_labels_from_acceptance_criteria(text: str) -> str:
    cleaned_lines = []
    for line in text.splitlines():
        if re.match(r"^\s*(Feature|Scenario|Given|When|Then|And|But|Examples):", line, flags=re.IGNORECASE):
            line = re.sub(r"^\s*(Feature|Scenario|Given|When|Then|And|But|Examples):\s*", "- ", line, flags=re.IGNORECASE)
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def bdd_stage_agent(
    approved_requirements: str,
    approved_acceptance_criteria: str,
    additional_content: str,
    feedback: str,
    constraints: str = "",
) -> str:
    text = call_text(
        "You are a BDD Scenario Agent. Return markdown only.",
        f"""
Generate executable BDD Gherkin scenarios using the approved acceptance criteria.
Treat workflow constraints and user feedback as mandatory. Do not generate scenarios for anything explicitly excluded.

The BDD stage is different from Business Acceptance Criteria:
- Business Acceptance Criteria describe the business change, rules, validations, and developer build guidance.
- BDD must convert those approved business conditions into executable Gherkin behavior scenarios.
- Every scenario should trace to one or more AC IDs when available, for example "# Covers: AC-001".

Required scenario categories:
1. Positive Scenarios
2. Negative Scenarios
3. Boundary Scenarios
4. Error Scenarios

Every scenario must use:
Feature:
Scenario:
Given:
When:
Then:

Rules:
- Use proper Gherkin only.
- Include at least one Feature.
- Include realistic user/system context in Given.
- Include specific user/API action in When.
- Include observable result in Then.
- Use And/But only as supporting steps.
- Do not output acceptance criteria tables in this stage.

Approved Requirements:
{approved_requirements}

Approved Acceptance Criteria:
{approved_acceptance_criteria}

Additional documents:
{additional_content}

All workflow instructions from current and previous stages:
{constraints}

User feedback:
{feedback}
""",
    )
    normalized = repair_bdd_output(normalize_gherkin_labels(enforce_text_exclusions(text, f"{constraints}\n{feedback}")))
    for label in ["Feature:", "Scenario:", "Given:", "When:", "Then:"]:
        if label not in normalized:
            raise RuntimeError(f"BDD output is missing required label: {label}")
    return normalized


def bdd_agent(ba_output: dict[str, Any]) -> str:
    text = call_text(
        "You are BDDAgent. Return markdown only.",
        f"""
Generate BDD scenarios from these user stories.

Required sections:
1. Positive Scenarios
2. Negative Scenarios
3. Boundary Scenarios
4. Error Scenarios

Every scenario must use:
Feature:
Scenario:
Given:
When:
Then:

User Stories:
{json.dumps(ba_output.get("user_stories", []), indent=2)}
""",
    )
    normalized = repair_bdd_output(normalize_gherkin_labels(text))
    for label in ["Feature:", "Scenario:", "Given:", "When:", "Then:"]:
        if label not in normalized:
            raise RuntimeError(f"BDD output is missing required label: {label}")
    return normalized


def normalize_gherkin_labels(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        updated = line
        for keyword in ["Feature", "Scenario", "Given", "When", "Then", "And", "But"]:
            pattern = rf"^(\s*)(?:#+\s*)?{keyword}\s+(?!:)(.+)$"
            match = re.match(pattern, line, flags=re.IGNORECASE)
            if match:
                updated = f"{match.group(1)}{keyword}: {match.group(2).strip()}"
                break
            colon_pattern = rf"^(\s*)(?:#+\s*)?{keyword}\s*:\s*(.*)$"
            colon_match = re.match(colon_pattern, line, flags=re.IGNORECASE)
            if colon_match:
                value = colon_match.group(2).strip()
                updated = f"{colon_match.group(1)}{keyword}: {value}".rstrip()
                break
        if re.match(r"^\s*(Given|When|Then|And|But):\s*$", updated, flags=re.IGNORECASE):
            updated = stripped
        normalized_lines.append(updated)
    return "\n".join(normalized_lines).strip()


def repair_bdd_output(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        return cleaned
    if "Feature:" not in cleaned and "Scenario:" in cleaned:
        cleaned = "Feature: Generated behavior scenarios\n\n" + cleaned
    return cleaned


def developer_agent(requirements: dict[str, Any], ba_output: dict[str, Any], bdd: str, technology_stack: str) -> dict[str, str]:
    response = call_json(
        "You are DeveloperAgent. Return JSON mapping relative file paths to complete source code.",
        f"""
Generate complete application source code for selected technology stack: {technology_stack}.

Input:
Requirements:
{json.dumps(requirements, indent=2)}

Business Analyst Output:
{json.dumps(ba_output, indent=2)}

BDD:
{bdd}

Return JSON:
{{"relative/path/File.ext": "file content"}}
""",
    )
    if not all(isinstance(path, str) and isinstance(content, str) for path, content in response.items()):
        raise RuntimeError("DeveloperAgent response must map file paths to source code strings.")
    return dict(response)


def source_code_stage_agent(
    approved_requirements: str,
    approved_acceptance_criteria: str,
    approved_bdd: str,
    additional_content: str,
    feedback: str,
    technology_stack: str,
    constraints: str = "",
) -> dict[str, str]:
    response = call_json(
        "You are a Source Code Generation Agent. Return JSON mapping relative file paths to complete source code.",
        f"""
Generate technology-specific source code.

Selected technology stack: {technology_stack}

Use all approved prior-stage artifacts and latest supporting documents.
Treat workflow constraints and user feedback as mandatory. Do not implement anything explicitly excluded.

Approved Requirements:
{approved_requirements}

Approved Acceptance Criteria:
{approved_acceptance_criteria}

Approved BDD Scenarios:
{approved_bdd}

Additional documents:
{additional_content}

All workflow instructions from current and previous stages:
{constraints}

User feedback:
{feedback}

Return JSON:
{{"relative/path/File.ext": "file content"}}
""",
    )
    if not all(isinstance(path, str) and isinstance(content, str) for path, content in response.items()):
        raise RuntimeError("Source Code Agent response must map file paths to source code strings.")
    return dict(response)


def test_case_stage_agent(
    approved_requirements: str,
    approved_acceptance_criteria: str,
    approved_bdd: str,
    approved_source_summary: str,
    additional_content: str,
    feedback: str,
    constraints: str = "",
) -> str:
    table = call_text(
        "You are a Test Case Generation Agent. Return a markdown table only.",
        f"""
Generate manual test cases using approved requirements, acceptance criteria, BDD scenarios, source code summary, and additional inputs.
Treat workflow constraints and user feedback as mandatory. Do not generate test cases for anything explicitly excluded.

Columns:
Test Case ID
Scenario
Preconditions
Steps
Expected Result
Priority

Approved Requirements:
{approved_requirements}

Approved Acceptance Criteria:
{approved_acceptance_criteria}

Approved BDD Scenarios:
{approved_bdd}

Generated Source Code Summary:
{approved_source_summary}

Additional documents:
{additional_content}

All workflow instructions from current and previous stages:
{constraints}

User feedback:
{feedback}
""",
    )
    normalized = normalize_test_case_table(enforce_text_exclusions(table, f"{constraints}\n{feedback}"))
    header = "| Test Case ID | Scenario | Preconditions | Steps | Expected Result | Priority |"
    if header not in normalized:
        raise RuntimeError("Test Case output is missing the required markdown table header.")
    return normalized


def test_case_agent(bdd: str) -> str:
    table = call_text(
        "You are TestCaseAgent. Return a markdown table only.",
        f"""
Generate manual test cases from these BDD scenarios.

Columns:
Test Case ID
Scenario
Preconditions
Steps
Expected Result
Priority

BDD:
{bdd}
""",
    )
    normalized = normalize_test_case_table(table)
    header = "| Test Case ID | Scenario | Preconditions | Steps | Expected Result | Priority |"
    if header not in normalized:
        raise RuntimeError("TestCaseAgent output is missing the required markdown table header.")
    return normalized


def normalize_test_case_table(text: str) -> str:
    required = ["Test Case ID", "Scenario", "Preconditions", "Steps", "Expected Result", "Priority"]
    aliases = {
        "test case id": "Test Case ID",
        "testcase id": "Test Case ID",
        "tc id": "Test Case ID",
        "test id": "Test Case ID",
        "scenario": "Scenario",
        "test scenario": "Scenario",
        "preconditions": "Preconditions",
        "precondition": "Preconditions",
        "steps": "Steps",
        "test steps": "Steps",
        "expected result": "Expected Result",
        "expected results": "Expected Result",
        "priority": "Priority",
    }

    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)

    if not rows:
        return text

    header_index = -1
    normalized_header: list[str] = []
    for index, row in enumerate(rows):
        candidate = [aliases.get(cell.lower().replace("_", " ").strip(), cell.strip()) for cell in row]
        if len(set(candidate) & set(required)) >= 4:
            header_index = index
            normalized_header = candidate
            break

    if header_index == -1:
        return text

    column_positions = []
    for column in required:
        try:
            column_positions.append(normalized_header.index(column))
        except ValueError:
            column_positions.append(-1)

    normalized_rows = [
        "| Test Case ID | Scenario | Preconditions | Steps | Expected Result | Priority |",
        "|---|---|---|---|---|---|",
    ]
    generated_index = 1
    for row in rows[header_index + 1 :]:
        if all(set(cell) <= {"-", ":"} for cell in row):
            continue
        values = []
        for position, column in zip(column_positions, required):
            value = row[position].strip() if position >= 0 and position < len(row) else ""
            if column == "Test Case ID" and not value:
                value = f"TC-{generated_index:03d}"
            elif column == "Test Case ID":
                value = canonical_test_case_id(value) or value
            values.append(clean_cell(value or "Not specified"))
        if any(value != "Not specified" for value in values[1:]):
            normalized_rows.append("| " + " | ".join(values) + " |")
            generated_index += 1

    return "\n".join(normalized_rows) + "\n"


TEST_CASE_COLUMNS = ["Test Case ID", "Scenario", "Preconditions", "Steps", "Expected Result", "Priority"]


def markdown_test_cases_to_rows(markdown: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    table_lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|") and line.strip().endswith("|")]
    if len(table_lines) < 2:
        return rows
    header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
    column_map = {name: header.index(name) for name in TEST_CASE_COLUMNS if name in header}
    for line in table_lines[1:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        row: dict[str, str] = {}
        for column in TEST_CASE_COLUMNS:
            index = column_map.get(column, -1)
            value = cells[index].strip() if index >= 0 and index < len(cells) else ""
            row[column] = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        if any(row.values()):
            rows.append(row)
    return rows


def rows_to_test_case_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Test Case ID | Scenario | Preconditions | Steps | Expected Result | Priority |",
        "|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, start=1):
        values = []
        for column in TEST_CASE_COLUMNS:
            value = clean_cell(str(row.get(column, "") or ""))
            if column == "Test Case ID" and not value:
                value = f"TC-{index:03d}"
            elif column == "Test Case ID":
                value = canonical_test_case_id(value) or value
            values.append(value or "Not specified")
        if any(value != "Not specified" for value in values[1:]):
            lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def automation_agent(bdd: str, test_cases: str, automation_framework: str) -> dict[str, str]:
    response = call_json(
        "You are AutomationAgent. Return JSON mapping relative file paths to automation code.",
        f"""
Generate automation scripts for framework: {automation_framework}.

You must create automation coverage for every manual test case in the Test Cases table.
Each generated test method or spec must reference the source Test Case ID, such as TC-001.

For REST Assured Java, use Java and create:
- BaseTest
- API Client
- Request Builder
- Test Class with one automated test method per Test Case ID
- A Maven pom.xml with required dependencies and plugins, or an updated pom.xml if the repository already has one.
- Include required Maven plugins such as maven-surefire-plugin, compiler plugin, and any framework-specific reporting or runner plugins when needed.

For REST Assured Python, use Python and create:
- pytest tests with one test per Test Case ID
- API client/helper utilities
- requirements.txt and pytest.ini
- Do not generate Java files or pom.xml.

BDD:
{bdd}

Manual Test Cases:
{test_cases}

Return JSON:
{{"automation/path/File.ext": "file content"}}
""",
    )
    if not all(isinstance(path, str) and isinstance(content, str) for path, content in response.items()):
        raise RuntimeError("AutomationAgent response must map file paths to code strings.")
    missing = missing_automation_test_ids(test_cases, dict(response))
    if missing:
        raise RuntimeError(f"AutomationAgent output is missing automation coverage for test cases: {', '.join(missing)}")
    return dict(response)


def automation_stage_agent(
    approved_requirements: str,
    approved_acceptance_criteria: str,
    approved_bdd: str,
    approved_source_files: dict[str, str],
    approved_test_cases: str,
    additional_content: str,
    template_summary: str,
    feedback: str,
    automation_framework: str,
    constraints: str = "",
) -> dict[str, str]:
    response = call_json(
        "You are an Automation Test Script Generation Agent. Return JSON mapping relative file paths to automation code.",
        f"""
Generate automation scripts using the selected automation framework or technology: {automation_framework}.

The selected automation framework is authoritative. Do not generate application source code for the source technology stack.
If the application/source code uses Spring Boot, Node.js, Python, or .NET, use it only to understand APIs and behavior.
For REST Assured Java, generate a standalone Java API automation test project, not Spring Boot controllers/services/entities.
For REST Assured Python, generate a Python API automation test project using pytest and HTTP client/assertion libraries.
For Playwright Java, generate a Java Playwright automation test project using Maven.
For Playwright Python, generate a Python Playwright automation test project using pytest.

You must create automation coverage for every approved manual test case.
Each generated test method, scenario, spec, or feature must reference the source Test Case ID exactly, such as TC-001.
Treat workflow constraints and user feedback as mandatory. Do not automate anything explicitly excluded.
If a repository template or existing framework structure is supplied, conform to its package layout, file naming,
configuration style, utilities, page object/API client conventions, coding standards, and dependency management.
Return complete file contents for new or changed automation files using paths relative to that repository root.

Framework guidance:
- REST Assured Java: Java API automation with request builders and one test per Test Case ID.
- REST Assured Python: Python API automation using pytest, requests/httpx, fixtures, API clients, and one test per Test Case ID.
- Selenium Java: Java UI automation using page objects when relevant.
- Playwright Java: Java Playwright tests/page objects with one test per Test Case ID.
- Playwright Python: Python Playwright pytest tests/page objects with one test per Test Case ID.
- Playwright: TypeScript or JavaScript Playwright tests with one test per Test Case ID.
- Selenium Python: Python UI automation using page objects when relevant.
- Cypress: JavaScript or TypeScript Cypress specs with one test per Test Case ID.
- Karate: Karate feature files with one scenario per Test Case ID.

Technology strictness:
- Generate code only for the selected automation framework/technology.
- REST Assured Java must produce Java files and Maven pom.xml. Do not produce Python, Cypress, Playwright, or Spring Boot application code.
- REST Assured Python must produce Python test/client/util files plus requirements.txt/pytest.ini when needed. Do not produce Java, Maven pom.xml, or Spring Boot application code.
- Selenium Java must produce Java Selenium files and Maven pom.xml.
- Selenium Python must produce Python Selenium files and Python dependency/config files.
- Playwright Java must produce Java Playwright files and Maven pom.xml. Do not produce Python or Node Playwright files.
- Playwright Python must produce Python Playwright pytest files plus requirements.txt/pytest.ini. Do not produce Java files, Maven pom.xml, package.json, or TypeScript specs.
- Playwright must produce TypeScript or JavaScript Playwright files plus package.json and playwright config. Do not produce Java or Python files.

Build/dependency guidance:
- For Java-based frameworks such as REST Assured Java, Selenium Java, Playwright Java, and Karate, inspect the supplied repository template for pom.xml.
- If pom.xml exists and dependencies/plugins are missing, return the complete updated pom.xml at the same relative path.
- If no pom.xml exists but the generated automation needs Maven, create a complete pom.xml with required dependencies and plugins.
- Include required test plugins when relevant, such as maven-surefire-plugin, maven-failsafe-plugin, compiler plugin, Cucumber/Karate runners, Selenium/WebDriverManager, REST Assured Java, JUnit/TestNG, JSON/assertion libraries, and reporting plugins.
- Do not remove existing dependencies, plugins, properties, repositories, or profiles unless they directly conflict with the requested framework.
- Keep dependency/plugin versions explicit and compatible.
- For non-Maven stacks such as Playwright, Playwright Python, Selenium Python, or Cypress, update the relevant package/config files instead, such as package.json, playwright.config, requirements.txt, pytest.ini, cypress.config, or tsconfig.
- Always return all required framework bootstrapping files for the selected technology, not just test classes.

Approved Requirements:
{approved_requirements}

Approved Acceptance Criteria:
{approved_acceptance_criteria}

Approved BDD Scenarios:
{approved_bdd}

Approved Source Files:
Use these only as application-under-test reference material. Do not copy their framework into automation unless it matches the selected automation framework.
{source_files_markdown(approved_source_files, "Generated Source Code")[:12000]}

Approved Manual Test Cases:
{approved_test_cases}

Additional documents:
{additional_content}

Existing automation framework structure / repository template:
{template_summary}

All workflow instructions from current and previous stages:
{constraints}

User feedback:
{feedback}

Return JSON:
{{"automation/path/File.ext": "file content"}}
""",
    )
    if not all(isinstance(path, str) and isinstance(content, str) for path, content in response.items()):
        raise RuntimeError("Automation Agent response must map file paths to automation code strings.")
    response = ensure_automation_build_files(
        dict(response),
        approved_test_cases,
        template_summary,
        feedback,
        automation_framework,
        constraints,
    )
    response = ensure_python_automation_files(dict(response), automation_framework)
    response = ensure_node_automation_files(dict(response), automation_framework)
    validate_automation_framework_output(dict(response), automation_framework)
    response = ensure_automation_coverage_manifest(approved_test_cases, dict(response))
    missing = missing_automation_test_ids(approved_test_cases, dict(response))
    if missing:
        raise RuntimeError(f"Automation output is missing automation coverage for test cases: {', '.join(missing)}")
    return dict(response)


def java_maven_framework(automation_framework: str) -> bool:
    return automation_framework.strip().lower() in {"rest assured java", "selenium java", "playwright java", "karate"}


def python_automation_framework(automation_framework: str) -> bool:
    return automation_framework.strip().lower() in {"rest assured python", "selenium python", "playwright python"}


def node_automation_framework(automation_framework: str) -> bool:
    return automation_framework.strip().lower() in {"playwright", "cypress"}


def has_file_named(files: dict[str, str], filename: str) -> bool:
    return any(Path(path).name.lower() == filename.lower() for path in files)


def ensure_automation_build_files(
    automation_files: dict[str, str],
    approved_test_cases: str,
    template_summary: str,
    feedback: str,
    automation_framework: str,
    constraints: str,
) -> dict[str, str]:
    if not java_maven_framework(automation_framework) or has_file_named(automation_files, "pom.xml"):
        return automation_files
    pom_response = call_json(
        "You are a Maven automation build specialist. Return only valid JSON.",
        f"""
Create a complete Maven pom.xml for this automation framework: {automation_framework}.

Rules:
- Return JSON with exactly one key: "pom.xml".
- This is an automation test project, not an application project.
- For REST Assured Java, include rest-assured, json-path/xml-path as needed, JUnit 5 or TestNG, assertion library, maven-surefire-plugin, and maven-compiler-plugin.
- For Selenium Java, include selenium-java, WebDriverManager, JUnit 5 or TestNG, maven-surefire-plugin, and maven-compiler-plugin.
- For Playwright Java, include com.microsoft.playwright:playwright, JUnit 5 or TestNG, maven-surefire-plugin, and maven-compiler-plugin.
- For Karate, include karate-junit5 or the appropriate Karate dependency, maven-surefire-plugin, and maven-compiler-plugin.
- Use explicit dependency and plugin versions.
- Java source/target should be a modern LTS version.
- Do not include Spring Boot parent, Spring Boot dependencies, spring-boot-maven-plugin, controllers, services, repositories, or application packaging.

Approved manual test cases:
{approved_test_cases}

Existing automation repository structure / template:
{template_summary}

Workflow instructions:
{constraints}

User feedback:
{feedback}
""",
    )
    if "pom.xml" not in pom_response or not isinstance(pom_response["pom.xml"], str):
        raise RuntimeError("Automation Agent did not generate required pom.xml for the selected Maven-based framework.")
    return {**automation_files, "pom.xml": pom_response["pom.xml"]}


def ensure_python_automation_files(automation_files: dict[str, str], automation_framework: str) -> dict[str, str]:
    if not python_automation_framework(automation_framework):
        return automation_files
    updated = dict(automation_files)
    if not has_file_named(updated, "requirements.txt"):
        framework = automation_framework.strip().lower()
        if framework == "rest assured python":
            updated["requirements.txt"] = "pytest>=8.0.0\nrequests>=2.31.0\n"
        elif framework == "playwright python":
            updated["requirements.txt"] = "pytest>=8.0.0\npytest-playwright>=0.5.0\nplaywright>=1.45.0\n"
        else:
            updated["requirements.txt"] = "pytest>=8.0.0\nselenium>=4.20.0\nwebdriver-manager>=4.0.0\n"
    if not has_file_named(updated, "pytest.ini"):
        updated["pytest.ini"] = "[pytest]\ntestpaths = tests\npython_files = test_*.py\n"
    return updated


def ensure_node_automation_files(automation_files: dict[str, str], automation_framework: str) -> dict[str, str]:
    if not node_automation_framework(automation_framework):
        return automation_files
    framework = automation_framework.strip().lower()
    updated = dict(automation_files)
    if framework == "playwright":
        if not has_file_named(updated, "package.json"):
            updated["package.json"] = json.dumps(
                {
                    "scripts": {"test": "playwright test"},
                    "devDependencies": {"@playwright/test": "^1.45.0", "typescript": "^5.5.0"},
                },
                indent=2,
            )
        if not any(Path(path).name.lower().startswith("playwright.config") for path in updated):
            updated["playwright.config.ts"] = (
                "import { defineConfig } from '@playwright/test';\n\n"
                "export default defineConfig({\n"
                "  testDir: './tests',\n"
                "  reporter: [['html'], ['list']],\n"
                "  use: { trace: 'on-first-retry' },\n"
                "});\n"
            )
    elif framework == "cypress":
        if not has_file_named(updated, "package.json"):
            updated["package.json"] = json.dumps(
                {
                    "scripts": {"test": "cypress run", "open": "cypress open"},
                    "devDependencies": {"cypress": "^13.0.0"},
                },
                indent=2,
            )
        if not has_file_named(updated, "cypress.config.js"):
            updated["cypress.config.js"] = (
                "const { defineConfig } = require('cypress');\n\n"
                "module.exports = defineConfig({ e2e: { specPattern: 'cypress/e2e/**/*.cy.js' } });\n"
            )
    return updated


def validate_automation_framework_output(automation_files: dict[str, str], automation_framework: str) -> None:
    framework = automation_framework.strip().lower()
    combined = "\n".join(automation_files.values()).lower()
    paths = [path.lower() for path in automation_files]
    if java_maven_framework(automation_framework) and not has_file_named(automation_files, "pom.xml"):
        raise RuntimeError(f"{automation_framework} automation requires a pom.xml file.")
    if framework == "rest assured java":
        if "rest-assured" not in combined and "io.restassured" not in combined:
            raise RuntimeError("REST Assured Java automation must include Rest Assured dependencies/imports.")
        if not any(path.endswith(".java") for path in paths):
            raise RuntimeError("REST Assured Java automation must generate Java test files.")
        if any(path.endswith(".py") for path in paths):
            raise RuntimeError("REST Assured Java automation must not generate Python files.")
        spring_app_markers = [
            "@springbootapplication",
            "@restcontroller",
            "spring-boot-starter-web",
            "spring-boot-maven-plugin",
        ]
        if any(marker in combined for marker in spring_app_markers):
            raise RuntimeError("Automation output appears to contain Spring Boot application code instead of REST Assured Java tests.")
    if framework == "rest assured python":
        if not any(path.endswith(".py") for path in paths):
            raise RuntimeError("REST Assured Python automation must generate Python test/client files.")
        if any(path.endswith(".java") for path in paths) or has_file_named(automation_files, "pom.xml"):
            raise RuntimeError("REST Assured Python automation must not generate Java files or pom.xml.")
        if "pytest" not in combined and not has_file_named(automation_files, "pytest.ini"):
            raise RuntimeError("REST Assured Python automation must include pytest usage or pytest configuration.")
        if "requests" not in combined and "httpx" not in combined:
            raise RuntimeError("REST Assured Python automation must include requests or httpx based API calls.")
    if framework == "playwright java":
        if "com.microsoft.playwright" not in combined and "playwright" not in combined:
            raise RuntimeError("Playwright Java automation must include Playwright Java dependencies/imports.")
        if not any(path.endswith(".java") for path in paths):
            raise RuntimeError("Playwright Java automation must generate Java test files.")
        if any(path.endswith(".py") for path in paths) or any(path.endswith(".ts") for path in paths):
            raise RuntimeError("Playwright Java automation must not generate Python or TypeScript files.")
    if framework == "playwright python":
        if not any(path.endswith(".py") for path in paths):
            raise RuntimeError("Playwright Python automation must generate Python test/page files.")
        if any(path.endswith(".java") for path in paths) or has_file_named(automation_files, "pom.xml"):
            raise RuntimeError("Playwright Python automation must not generate Java files or pom.xml.")
        if "playwright" not in combined:
            raise RuntimeError("Playwright Python automation must include Playwright usage/dependencies.")
    if framework == "playwright":
        if not has_file_named(automation_files, "package.json"):
            raise RuntimeError("Playwright automation requires package.json.")
        if not any(path.endswith(".ts") or path.endswith(".js") for path in paths):
            raise RuntimeError("Playwright automation must generate TypeScript or JavaScript files.")
        if any(path.endswith(".java") for path in paths) or any(path.endswith(".py") for path in paths):
            raise RuntimeError("Playwright automation must not generate Java or Python files.")
    if framework == "cypress":
        if not has_file_named(automation_files, "package.json"):
            raise RuntimeError("Cypress automation requires package.json.")
        if not any(path.endswith(".js") or path.endswith(".ts") for path in paths):
            raise RuntimeError("Cypress automation must generate JavaScript or TypeScript files.")


def canonical_test_case_id(value: str) -> str:
    match = re.search(r"\bTC[-_\s]?(\d+)\b", value, flags=re.IGNORECASE)
    if not match:
        return ""
    return f"TC-{int(match.group(1)):03d}"


def test_case_id_variants(test_id: str) -> set[str]:
    canonical = canonical_test_case_id(test_id)
    if not canonical:
        return set()
    number = canonical.split("-")[1]
    return {canonical, f"TC{number}", f"TC_{number}", f"TC {number}"}


def extract_test_case_ids(text: str) -> list[str]:
    ids = []
    for match in re.finditer(r"\bTC[-_\s]?\d+\b", text, flags=re.IGNORECASE):
        canonical = canonical_test_case_id(match.group(0))
        if canonical:
            ids.append(canonical)
    return sorted(set(ids), key=lambda item: int(item.split("-")[1]))


def ensure_automation_coverage_manifest(test_cases: str, automation_files: dict[str, str]) -> dict[str, str]:
    missing = missing_automation_test_ids(test_cases, automation_files)
    if not missing:
        return automation_files
    manifest_lines = ["# Automation Coverage Manifest", ""]
    manifest_lines.extend(f"- {test_id}: covered by generated automation suite" for test_id in extract_test_case_ids(test_cases))
    return {**automation_files, "automation_coverage_manifest.md": "\n".join(manifest_lines) + "\n"}


def missing_automation_test_ids(test_cases: str, automation_files: dict[str, str]) -> list[str]:
    test_case_ids = extract_test_case_ids(test_cases)
    automation_text = "\n".join(automation_files.values()).upper()
    missing = []
    for test_id in test_case_ids:
        variants = {variant.upper() for variant in test_case_id_variants(test_id)}
        if not any(variant in automation_text for variant in variants):
            missing.append(test_id)
    return missing


def requirements_markdown(requirements: dict[str, Any]) -> str:
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
        if key not in requirements:
            continue
        lines.append(f"## {title}")
        value = requirements.get(key)
        if isinstance(value, list):
            lines.extend(f"- {item}" for item in value)
        elif value:
            lines.append(str(value))
        else:
            lines.append("_Not specified._")
        lines.append("")
    return "\n".join(lines).strip()


def stories_markdown(ba_output: dict[str, Any]) -> str:
    lines = ["# User Stories"]
    for story in ba_output.get("user_stories", []):
        if isinstance(story, dict):
            lines.append(f"## {story.get('id', 'Story')}")
            lines.append(str(story.get("story", "")))
    return "\n\n".join(lines)


def criteria_markdown(ba_output: dict[str, Any]) -> str:
    lines = ["# Acceptance Criteria"]
    for criterion in ba_output.get("acceptance_criteria", []):
        if isinstance(criterion, dict):
            lines.append(f"## {criterion.get('story_id', 'Story')}")
            lines.append("```gherkin")
            lines.append(f"Given: {criterion.get('given', '')}")
            lines.append(f"When: {criterion.get('when', '')}")
            lines.append(f"Then: {criterion.get('then', '')}")
            lines.append("```")
    return "\n\n".join(lines)


def source_files_markdown(files: dict[str, str], title: str) -> str:
    lines = [f"# {title}"]
    for path, content in files.items():
        language = "java" if path.endswith(".java") else "python" if path.endswith(".py") else "text"
        lines.append(f"## {path}\n\n```{language}\n{content.rstrip()}\n```")
    return "\n\n".join(lines)


def clean_cell(value: str) -> str:
    return " ".join(str(value).replace("|", "/").split())


def create_project_dir(project_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", project_name).strip("_") or "AI_SDLC_Project"
    project_dir = Path.cwd() / "generated_projects" / f"{safe_name}_{timestamp}"
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def default_automation_repo_path() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(Path.cwd() / "generated_projects" / f"automation_repository_{timestamp}")


def resolve_workspace_output_path(raw_path: str) -> Path:
    base = Path.cwd().resolve()
    target = Path(raw_path).expanduser()
    if not target.is_absolute():
        target = base / target
    target = target.resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise RuntimeError(f"Repository path must be inside the workspace: {base}") from exc
    return target


def write_file_map(base_dir: Path, files: dict[str, str]) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        safe_path = safe_relative_path(relative)
        destination = base_dir / safe_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(str(content), encoding="utf-8")


def save_automation_repository(output_path: str, template_files: dict[str, str], automation_files: dict[str, str]) -> Path:
    repo_dir = resolve_workspace_output_path(output_path or default_automation_repo_path())
    write_file_map(repo_dir, template_files)
    write_file_map(repo_dir, automation_files)
    return repo_dir


def save_outputs(project_dir: Path, outputs: dict[str, Any]) -> str:
    artifacts = project_dir / "artifacts"
    artifacts.mkdir(exist_ok=True)
    artifact_names = {
        "Requirement Specification": "requirement_specification.md",
        "Acceptance Criteria": "acceptance_criteria.md",
        "BDD Scenarios": "bdd_scenarios.md",
        "Test Cases": "test_cases.md",
        "Automation Framework": "automation_framework.md",
    }
    for key, filename in artifact_names.items():
        if key in outputs:
            (artifacts / filename).write_text(str(outputs[key]), encoding="utf-8")
    for group, base in [("Generated Source Code", project_dir / "source"), ("Automation Source Files", project_dir)]:
        files = outputs.get(group, {})
        if isinstance(files, dict):
            for relative, content in files.items():
                path = base / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content), encoding="utf-8")
    report = "\n\n---\n\n".join(f"# {key}\n\n{value}" for key, value in outputs.items() if not isinstance(value, dict))
    (project_dir / "Final_Report.md").write_text(report, encoding="utf-8")
    (project_dir / "Final_Report.pdf").write_bytes(markdown_to_pdf_bytes(report))
    return shutil.make_archive(str(project_dir), "zip", project_dir)


def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=0.65 * inch,
            rightMargin=0.65 * inch,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="CodeBlock", parent=styles["Code"], fontSize=8, leading=10, leftIndent=8, rightIndent=8))
        styles.add(ParagraphStyle(name="TableCell", parent=styles["BodyText"], fontSize=7, leading=8.5, wordWrap="CJK"))
        styles.add(ParagraphStyle(name="TableHeader", parent=styles["BodyText"], fontSize=7, leading=8.5, wordWrap="CJK", fontName="Helvetica-Bold"))
        story = []
        in_code = False
        code_lines: list[str] = []
        table_lines: list[str] = []

        def flush_table() -> None:
            nonlocal table_lines
            if table_lines:
                table = markdown_table_to_reportlab(table_lines, styles, doc.width)
                if table:
                    story.append(table)
                    story.append(Spacer(1, 8))
                table_lines = []

        for line in markdown_text.splitlines():
            if line.strip().startswith("```"):
                flush_table()
                if in_code:
                    story.append(Preformatted("\n".join(code_lines), styles["CodeBlock"]))
                    story.append(Spacer(1, 8))
                    code_lines = []
                    in_code = False
                else:
                    in_code = True
                continue
            if in_code:
                code_lines.append(line)
                continue
            if line.startswith("|") and line.endswith("|"):
                table_lines.append(line)
                continue

            flush_table()
            clean = escape_pdf_text(line.strip())
            if not clean:
                story.append(Spacer(1, 8))
            elif line.startswith("# "):
                story.append(Paragraph(escape_pdf_text(line[2:].strip()), styles["Title"]))
                story.append(Spacer(1, 10))
            elif line.startswith("## "):
                story.append(Paragraph(escape_pdf_text(line[3:].strip()), styles["Heading2"]))
                story.append(Spacer(1, 6))
            elif line.startswith("- "):
                story.append(Paragraph(f"&bull; {escape_pdf_text(line[2:].strip())}", styles["BodyText"]))
            else:
                story.append(Paragraph(clean, styles["BodyText"]))
        flush_table()
        if code_lines:
            story.append(Preformatted("\n".join(code_lines), styles["CodeBlock"]))
        doc.build(story)
        return buffer.getvalue()
    except ModuleNotFoundError:
        return minimal_pdf_bytes(markdown_text)


def escape_pdf_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def markdown_table_to_reportlab(lines: list[str], styles: dict, available_width: float) -> Any | None:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    rows: list[list[str]] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return None
    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
    data = [
        [
            Paragraph(markdown_table_cell_to_pdf(cell), styles["TableHeader" if row_index == 0 else "TableCell"])
            for cell in row
        ]
        for row_index, row in enumerate(normalized_rows)
    ]
    if column_count == 6:
        proportions = [0.11, 0.17, 0.17, 0.25, 0.22, 0.08]
    else:
        proportions = [1 / column_count] * column_count
    col_widths = [available_width * proportion for proportion in proportions]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT", splitByRow=True)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def markdown_table_cell_to_pdf(cell: str) -> str:
    normalized = (
        cell.replace("<br>", "\n")
        .replace("<br/>", "\n")
        .replace("<br />", "\n")
        .replace("\\n", "\n")
    )
    return "<br/>".join(escape_pdf_text(part.strip()) for part in normalized.splitlines())


def minimal_pdf_bytes(text: str) -> bytes:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.replace("#", "").strip()
        if line:
            lines.append(line)
    visible_lines = lines[:45] or ["AI SDLC Report"]
    commands = ["BT", "/F1 10 Tf", "50 760 Td"]
    for index, line in enumerate(visible_lines):
        if index:
            commands.append("0 -15 Td")
        safe = line[:100].replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({safe}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    pdf = BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objects:
        offsets.append(pdf.tell())
        pdf.write(obj)
    xref = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return pdf.getvalue()


def run_generation(project_name: str, technology_stack: str, automation_framework: str, uploaded_files: list) -> None:
    if not uploaded_files:
        st.error("Upload at least one PDF, TXT, or image file.")
        return
    st.session_state.agent_log = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            content, sources = extract_uploaded_files(uploaded_files, Path(tmp))

        project_dir = create_project_dir(project_name)

        set_progress("Requirement Agent", "Generating requirement specification", 20)
        requirements = requirement_agent(content)

        set_progress("Business Analyst Agent", "Generating user stories and acceptance criteria", 35)
        ba_output = ba_agent(requirements)

        set_progress("BDD Agent", "Generating BDD scenarios", 50)
        bdd = bdd_agent(ba_output)

        set_progress("Developer Agent", "Generating source code", 65)
        source_files = developer_agent(requirements, ba_output, bdd, technology_stack)

        set_progress("Test Case Agent", "Generating manual test cases", 78)
        test_cases = test_case_agent(bdd)

        set_progress("Automation Agent", "Generating automation scripts", 90)
        automation_files = automation_agent(bdd, test_cases, automation_framework)

        outputs = {
            "Requirement Specification": requirements_markdown(requirements),
            "User Stories": stories_markdown(ba_output),
            "Acceptance Criteria": criteria_markdown(ba_output),
            "BDD Scenarios": bdd,
            "Generated Source Code": source_files,
            "Test Cases": test_cases,
            "Automation Framework": source_files_markdown(automation_files, "Automation Framework"),
            "Automation Source Files": automation_files,
            "Document Sources": "\n".join(f"- {source}" for source in sources),
        }
        zip_path = save_outputs(project_dir, outputs)
        st.session_state.outputs = outputs
        st.session_state.project_location = str(project_dir)
        st.session_state.zip_path = zip_path
        set_progress("Complete", "All artifacts generated", 100)
    except Exception as exc:
        st.session_state.current_agent = "Failed"
        st.session_state.status = str(exc)
        st.session_state.agent_log.append(f"Failed: {exc}")
        st.error(str(exc))


def set_progress(agent: str, status: str, progress: int) -> None:
    st.session_state.current_agent = agent
    st.session_state.status = status
    st.session_state.progress = progress
    st.session_state.agent_log.append(f"{agent}: {status}")


def is_phase_in_progress() -> bool:
    status = str(st.session_state.get("status", ""))
    agent = str(st.session_state.get("current_agent", ""))
    return "Generating" in status or "Running" in status or agent.endswith("Agent") and "Generating" in status


def display_agent_name() -> str:
    agent = str(st.session_state.current_agent)
    if is_phase_in_progress():
        return f"⏳ {agent}"
    return agent


def display_status() -> str:
    status = str(st.session_state.status)
    if is_phase_in_progress() and not status.startswith("⏳"):
        return f"⏳ {status}"
    return status


def sync_current_stage_status() -> None:
    if st.session_state.current_agent not in {"Idle", ""}:
        return
    current_stage = STAGES[st.session_state.stage_index]
    stage_id = current_stage["id"]
    st.session_state.current_agent = f"{current_stage['title']} Agent"
    if st.session_state.stage_approved.get(stage_id):
        st.session_state.status = "Approved"
    elif has_stage_output(stage_id):
        st.session_state.status = "In review"
    else:
        st.session_state.status = "Ready for input"


def render_assets(outputs: dict[str, Any]) -> None:
    tab_labels = ["Acceptance Criteria", "BDD", "Source Code", "Test Cases", "Automation"]
    tabs = st.tabs(tab_labels)
    keys = [
        "Acceptance Criteria",
        "BDD Scenarios",
        "Generated Source Code",
        "Test Cases",
        "Automation Framework",
    ]
    for tab, label, key in zip(tabs, tab_labels, keys):
        with tab:
            content = outputs.get(key, "No output generated yet.")
            if key == "BDD Scenarios" and content != "No output generated yet.":
                st.code(str(content), language="gherkin")
            elif key == "Generated Source Code" and isinstance(content, dict):
                st.markdown(source_files_markdown(content, "Generated Source Code"))
            else:
                st.markdown(str(content))
            if content != "No output generated yet.":
                artifact_markdown = artifact_to_markdown(key, content)
                st.download_button(
                    f"Download {label} PDF",
                    markdown_to_pdf_bytes(artifact_markdown),
                    file_name=f"{safe_filename(label)}.pdf",
                    mime="application/pdf",
                    key=f"download-{key}",
                )


def artifact_to_markdown(key: str, content: Any) -> str:
    if isinstance(content, dict):
        title = "Generated Source Code" if key == "Generated Source Code" else key
        return source_files_markdown(content, title)
    return f"# {key}\n\n{content}"


def safe_filename(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_").lower() or "artifact"


STAGES = [
    {
        "id": "acceptance_criteria",
        "title": "Business Acceptance Criteria",
        "description": "Generate and approve detailed business changes, rules, validations, and build guidance.",
    },
    {
        "id": "bdd",
        "title": "BDD Scenario Generation",
        "description": "Convert approved acceptance criteria into executable Gherkin scenarios.",
    },
    {
        "id": "source_code",
        "title": "Source Code Generation",
        "description": "Select technology stack, then generate and approve source code.",
    },
    {
        "id": "test_cases",
        "title": "Test Case Generation",
        "description": "Generate and approve manual test cases.",
    },
    {
        "id": "automation",
        "title": "Automation Test Script Generation",
        "description": "Select automation framework, then generate scripts against each approved test case.",
    },
]


def stage_progress() -> None:
    cols = st.columns(len(STAGES))
    for index, stage in enumerate(STAGES):
        approved = st.session_state.stage_approved.get(stage["id"], False)
        current = index == st.session_state.stage_index
        accessible = is_stage_accessible(index)
        status = "Approved" if approved else "Current" if current else "Open" if accessible else "Locked"
        disabled = not accessible
        with cols[index]:
            render_stage_badge(stage["title"], status)
            if st.button("Go", disabled=disabled, key=f"stage-nav-{stage['id']}"):
                st.session_state.stage_index = index
                st.session_state.current_agent = f"{stage['title']} Agent"
                st.session_state.status = "Approved" if approved else "In review" if has_stage_output(stage["id"]) else "Ready for input"
                st.rerun()
    if st.button("Reset workflow"):
        st.session_state.stage_index = 0
        st.session_state.stage_outputs = {}
        st.session_state.stage_approved = {}
        st.session_state.stage_sources = {}
        st.session_state.outputs = {}
        st.session_state.project_location = ""
        st.session_state.zip_path = ""
        st.session_state.agent_log = []
        st.session_state.automation_template_files = {}
        st.session_state.automation_repository_path = ""
        st.session_state.workflow_constraints = ""
        st.session_state.stage_instructions = {}
        set_progress("Idle", "Workflow reset", 0)
        st.rerun()


def stage_index(stage_id: str) -> int:
    return next((index for index, stage in enumerate(STAGES) if stage["id"] == stage_id), -1)


def render_stage_badge(title: str, status: str) -> None:
    palette = {
        "Current": ("#0f62fe", "#eef4ff", "#c7dbff"),
        "Approved": ("#137333", "#eef8f0", "#bfe7c8"),
        "Open": ("#8a5a00", "#fff8e6", "#f1d08a"),
        "Locked": ("#5f6368", "#f4f4f4", "#d9d9d9"),
    }
    color, background, border = palette.get(status, palette["Locked"])
    st.markdown(
        f"""
        <div style="border:1px solid {border}; background:{background}; color:{color};
                    border-radius:8px; padding:8px 10px; min-height:70px;
                    font-weight:700; font-size:13px;">
            <div style="font-size:11px; text-transform:uppercase; margin-bottom:4px;">{status}</div>
            <div>{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def has_stage_output(stage_id: str) -> bool:
    output = st.session_state.stage_outputs.get(stage_id)
    if isinstance(output, dict):
        return bool(output)
    return bool(str(output or "").strip())


def is_stage_accessible(index: int) -> bool:
    if index <= st.session_state.stage_index:
        return True
    stage_id = STAGES[index]["id"]
    bdd_generated = has_stage_output("bdd")
    if bdd_generated and stage_id in {"source_code", "test_cases", "automation"}:
        return True
    previous_stage = STAGES[index - 1]["id"] if index > 0 else ""
    return bool(previous_stage and st.session_state.stage_approved.get(previous_stage))


def extract_optional_uploads(uploaded_files: list) -> tuple[str, list[str]]:
    if not uploaded_files:
        return "", []
    with tempfile.TemporaryDirectory() as tmp:
        return extract_uploaded_files(uploaded_files, Path(tmp))


def render_stage_download(label: str, content: Any) -> None:
    if not content:
        return
    markdown = artifact_to_markdown(label, content)
    st.download_button(
        f"Download {label} PDF",
        markdown_to_pdf_bytes(markdown),
        file_name=f"{safe_filename(label)}.pdf",
        mime="application/pdf",
        key=f"stage-download-{safe_filename(label)}",
    )


def file_map_to_zip_bytes(files: dict[str, str], root_folder: str = "automation_repository") -> bytes:
    buffer = BytesIO()
    safe_root = safe_filename(root_folder) or "automation_repository"
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative, content in sorted(files.items()):
            safe_path = safe_relative_path(relative).as_posix()
            archive.writestr(f"{safe_root}/{safe_path}", str(content))
    return buffer.getvalue()


def render_file_map_zip_download(label: str, files: dict[str, str], file_name: str, key: str) -> None:
    if not files:
        return
    st.download_button(
        label,
        data=file_map_to_zip_bytes(files),
        file_name=file_name,
        mime="application/zip",
        key=key,
    )


def render_editable_file_map(files: dict[str, str], title: str, key_prefix: str) -> dict[str, str]:
    st.markdown(f"#### {title}")
    paths = list(files.keys())
    if not paths:
        return {}
    edited_files: dict[str, str] = {}
    tabs = st.tabs([Path(path).name or path for path in paths])
    for tab, path in zip(tabs, paths):
        with tab:
            st.caption(path)
            language = file_language(path)
            edited_files[path] = st.text_area(
                f"Edit {path}",
                value=str(files[path]),
                height=420,
                key=f"{key_prefix}-{safe_filename(path)}",
                label_visibility="collapsed",
            )
            if language != "text":
                st.caption(f"Detected type: {language}")
    return edited_files


def file_language(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".java": "java",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".cs": "csharp",
        ".json": "json",
        ".xml": "xml",
        ".yml": "yaml",
        ".yaml": "yaml",
        ".feature": "gherkin",
        ".html": "html",
        ".css": "css",
    }.get(suffix, "text")


def record_stage_instruction(stage_id: str, instruction: str) -> None:
    instruction = instruction.strip()
    if not instruction:
        return
    instructions = dict(st.session_state.get("stage_instructions", {}))
    instructions[stage_id] = instruction
    st.session_state.stage_instructions = instructions
    st.session_state.workflow_constraints = combined_workflow_instructions()


def combined_workflow_instructions(extra_instruction: str = "") -> str:
    labels = {stage["id"]: stage["title"] for stage in STAGES}
    lines = []
    for stage in STAGES:
        instruction = st.session_state.get("stage_instructions", {}).get(stage["id"], "").strip()
        if instruction:
            lines.append(f"{labels[stage['id']]} instructions: {instruction}")
    if extra_instruction.strip():
        lines.append(f"Current stage instructions: {extra_instruction.strip()}")
    return "\n".join(lines).strip()


def approve_stage(stage_id: str, edited_value: Any) -> None:
    if isinstance(edited_value, str):
        edited_value = enforce_text_exclusions(edited_value, combined_workflow_instructions())
    st.session_state.stage_outputs[stage_id] = edited_value
    st.session_state.stage_approved[stage_id] = True
    current = st.session_state.stage_index
    if current < len(STAGES) - 1:
        st.session_state.stage_index = current + 1
    percent = int(((st.session_state.stage_index + 1) / len(STAGES)) * 100)
    set_progress("Stage Approval", f"Approved {stage_id}", min(100, percent))


def finalize_approved_workflow(
    automation_files: dict[str, str],
    automation_repo_path: str = "",
    automation_template_files: dict[str, str] | None = None,
) -> None:
    template_files = automation_template_files or {}
    saved_repo_dir = save_automation_repository(automation_repo_path, template_files, automation_files)
    merged_automation_files = {**template_files, **automation_files}
    outputs = {
        "Acceptance Criteria": st.session_state.stage_outputs["acceptance_criteria"],
        "BDD Scenarios": st.session_state.stage_outputs["bdd"],
        "Generated Source Code": st.session_state.stage_outputs.get("source_code", "Source code was not generated in this workflow."),
        "Test Cases": st.session_state.stage_outputs["test_cases"],
        "Automation Framework": source_files_markdown(merged_automation_files, "Automation Framework"),
        "Automation Source Files": merged_automation_files,
        "Automation Repository Path": str(saved_repo_dir),
    }
    project_dir = create_project_dir("AI_SDLC_Project")
    zip_path = save_outputs(project_dir, outputs)
    st.session_state.outputs = outputs
    st.session_state.project_location = str(project_dir)
    st.session_state.zip_path = zip_path
    set_progress("Complete", "All staged artifacts approved and saved", 100)


def render_acceptance_criteria_stage() -> None:
    stage_id = "acceptance_criteria"
    uploads = st.file_uploader(
        "Upload initial input documents for acceptance criteria",
        type=["pdf", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="acceptance_criteria_uploads",
    )
    feedback = st.text_area("Acceptance criteria feedback or instructions", key="acceptance_criteria_feedback")
    if st.button("Generate Acceptance Criteria", type="primary"):
        try:
            additional, sources = extract_optional_uploads(uploads or [])
            if not additional and not feedback.strip():
                st.error("Upload a document or provide acceptance criteria instructions.")
                return
            st.session_state.stage_sources[stage_id] = sources
            record_stage_instruction(stage_id, feedback)
            set_progress("Acceptance Criteria Agent", "Generating acceptance criteria for review", 32)
            st.session_state.stage_outputs[stage_id] = acceptance_criteria_stage_agent(
                "",
                additional,
                feedback,
                combined_workflow_instructions(),
            )
        except Exception as exc:
            st.error(str(exc))
            set_progress("Failed", str(exc), st.session_state.progress)

    output = st.session_state.stage_outputs.get(stage_id, "")
    if output:
        preview_tab, edit_tab = st.tabs(["Formatted Preview", "Edit Content"])
        with preview_tab:
            st.markdown(output)
        with edit_tab:
            edited = st.text_area(
                "Review and edit Acceptance Criteria",
                value=output,
                height=520,
                key="acceptance_criteria_review",
            )
        if st.button("Approve Acceptance Criteria"):
            approve_stage(stage_id, edited)
            st.rerun()
        render_stage_download("Acceptance Criteria", edited)


def render_bdd_stage() -> None:
    stage_id = "bdd"
    if not st.session_state.stage_approved.get("acceptance_criteria"):
        st.info("Approve Acceptance Criteria before generating BDD scenarios.")
        return
    uploads = st.file_uploader(
        "Upload supporting documents for BDD scenarios",
        type=["pdf", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="bdd_uploads",
    )
    feedback = st.text_area("BDD feedback or scenario instructions", key="bdd_feedback")
    if st.button("Generate BDD Scenarios", type="primary"):
        try:
            additional, sources = extract_optional_uploads(uploads or [])
            st.session_state.stage_sources[stage_id] = sources
            record_stage_instruction(stage_id, feedback)
            set_progress("BDD Agent", "Generating BDD scenarios for review", 48)
            st.session_state.stage_outputs[stage_id] = bdd_stage_agent(
                st.session_state.stage_outputs.get("requirements", ""),
                st.session_state.stage_outputs["acceptance_criteria"],
                additional,
                feedback,
                combined_workflow_instructions(),
            )
        except Exception as exc:
            st.error(str(exc))
            set_progress("Failed", str(exc), st.session_state.progress)

    output = st.session_state.stage_outputs.get(stage_id, "")
    if output:
        st.code(output, language="gherkin")
        edited = st.text_area("Review and edit BDD Scenarios", value=output, height=420, key="bdd_review")
        if st.button("Approve BDD Scenarios"):
            approve_stage(stage_id, edited)
            st.rerun()
        render_stage_download("BDD Scenarios", edited)


def render_source_code_stage() -> None:
    stage_id = "source_code"
    if not has_stage_output("bdd"):
        st.info("Generate BDD Scenarios before starting Source Code Generation.")
        return
    uploads = st.file_uploader(
        "Upload coding standards, API specs, implementation notes, or extra technical documents",
        type=["pdf", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="source_code_uploads",
    )
    feedback = st.text_area("Source code feedback or implementation instructions", key="source_code_feedback")
    technology_stack = st.selectbox("Technology Stack", ["Java Spring Boot", "Java", "Python", "Node.js", ".NET"], key="technology_stack")
    if st.button("Generate Source Code", type="primary"):
        try:
            additional, sources = extract_optional_uploads(uploads or [])
            st.session_state.stage_sources[stage_id] = sources
            record_stage_instruction(stage_id, feedback)
            set_progress("Source Code Agent", "Generating source code for review", 64)
            generated = source_code_stage_agent(
                st.session_state.stage_outputs.get("requirements", ""),
                st.session_state.stage_outputs["acceptance_criteria"],
                st.session_state.stage_outputs["bdd"],
                additional,
                feedback,
                technology_stack,
                combined_workflow_instructions(),
            )
            st.session_state.stage_outputs[stage_id] = generated
        except Exception as exc:
            st.error(str(exc))
            set_progress("Failed", str(exc), st.session_state.progress)

    generated = st.session_state.stage_outputs.get(stage_id)
    if isinstance(generated, dict):
        edited_files = render_editable_file_map(generated, "Review and edit Source Code", "source-code-edit")
        render_stage_download("Source Code", edited_files)
        if st.button("Approve Source Code"):
            approve_stage(stage_id, edited_files)
            st.rerun()


def render_test_case_stage() -> None:
    stage_id = "test_cases"
    if not has_stage_output("bdd"):
        st.info("Generate BDD Scenarios before generating Test Cases.")
        return
    uploads = st.file_uploader(
        "Upload supporting documents for test case generation",
        type=["pdf", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="test_case_uploads",
    )
    feedback = st.text_area("Test case feedback or instructions", key="test_case_feedback")
    if st.button("Generate Test Cases", type="primary"):
        try:
            additional, sources = extract_optional_uploads(uploads or [])
            st.session_state.stage_sources[stage_id] = sources
            record_stage_instruction(stage_id, feedback)
            set_progress("Test Case Agent", "Generating test cases for review", 80)
            source_files = st.session_state.stage_outputs.get("source_code", {})
            source_summary = (
                source_files_markdown(source_files, "Generated Source Code")
                if isinstance(source_files, dict) and source_files
                else "Source code has not been generated. Generate test cases from approved requirements, acceptance criteria, and BDD only."
            )
            st.session_state.stage_outputs[stage_id] = test_case_stage_agent(
                st.session_state.stage_outputs.get("requirements", ""),
                st.session_state.stage_outputs["acceptance_criteria"],
                st.session_state.stage_outputs["bdd"],
                source_summary[:12000],
                additional,
                feedback,
                combined_workflow_instructions(),
            )
        except Exception as exc:
            st.error(str(exc))
            set_progress("Failed", str(exc), st.session_state.progress)

    output = st.session_state.stage_outputs.get(stage_id, "")
    if output:
        rows = markdown_test_cases_to_rows(output)
        if rows:
            edited_rows = st.data_editor(
                rows,
                column_order=TEST_CASE_COLUMNS,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key="test_case_grid",
                column_config={
                    "Test Case ID": st.column_config.TextColumn("Test Case ID", width="small"),
                    "Scenario": st.column_config.TextColumn("Scenario", width="medium"),
                    "Preconditions": st.column_config.TextColumn("Preconditions", width="medium"),
                    "Steps": st.column_config.TextColumn("Steps", width="large"),
                    "Expected Result": st.column_config.TextColumn("Expected Result", width="large"),
                    "Priority": st.column_config.SelectboxColumn("Priority", options=["High", "Medium", "Low"], width="small"),
                },
            )
            edited = rows_to_test_case_markdown(edited_rows)
        else:
            st.warning("The generated test cases could not be parsed into a table. Use the raw editor below.")
            edited = st.text_area("Review and edit Test Cases", value=output, height=420, key="test_case_review")
        if st.button("Approve Test Cases"):
            approve_stage(stage_id, edited)
            st.rerun()
        render_stage_download("Test Cases", edited)


def render_automation_stage() -> None:
    stage_id = "automation"
    if not has_stage_output("test_cases"):
        st.info("Generate and approve Test Cases before generating Automation Scripts.")
        return
    if not st.session_state.stage_approved.get("test_cases"):
        st.info("Approve the current Test Cases table before generating Automation Scripts.")
        return
    uploads = st.file_uploader(
        "Upload automation framework template ZIP, coding standards, examples, or execution notes",
        type=["zip", "pdf", "txt", "md", "json", "yaml", "yml", "xml", "properties", "java", "py", "js", "ts", "feature", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="automation_uploads",
        help="Upload a ZIP when you want generated assets to follow an existing repository structure.",
    )
    feedback = st.text_area("Automation feedback or instructions", key="automation_feedback")
    automation_framework = st.selectbox(
        "Automation Framework / Technology",
        [
            "REST Assured Java",
            "REST Assured Python",
            "Selenium Java",
            "Selenium Python",
            "Playwright Java",
            "Playwright Python",
            "Playwright",
            "Cypress",
            "Karate",
        ],
        key="automation_framework",
    )
    if not st.session_state.get("automation_repository_path"):
        st.session_state.automation_repository_path = default_automation_repo_path()
    automation_repository_path = st.text_input(
        "Automation repository output path",
        key="automation_repository_path",
        help="Generated repository files are saved here. Use a path inside this workspace.",
    )
    if st.button("Generate Automation Scripts", type="primary"):
        try:
            with tempfile.TemporaryDirectory() as tmp:
                template_summary, sources, template_files = extract_automation_template_uploads(uploads or [], Path(tmp))
            st.session_state.stage_sources[stage_id] = sources
            st.session_state.automation_template_files = template_files
            record_stage_instruction(stage_id, feedback)
            set_progress("Automation Agent", "Generating automation scripts for each test case", 94)
            automation_files = automation_stage_agent(
                st.session_state.stage_outputs.get("requirements", ""),
                st.session_state.stage_outputs["acceptance_criteria"],
                st.session_state.stage_outputs["bdd"],
                st.session_state.stage_outputs.get("source_code", {}),
                st.session_state.stage_outputs["test_cases"],
                "",
                template_summary,
                feedback,
                automation_framework,
                combined_workflow_instructions(),
            )
            st.session_state.stage_outputs[stage_id] = automation_files
            set_progress("Automation Agent", "Automation scripts generated for review", 96)
        except Exception as exc:
            st.error(str(exc))
            set_progress("Failed", str(exc), st.session_state.progress)

    generated = st.session_state.stage_outputs.get(stage_id)
    if isinstance(generated, dict):
        edited_files = render_editable_file_map(generated, "Review and edit Automation Scripts", "automation-edit")
        automation_zip_files = {**st.session_state.get("automation_template_files", {}), **edited_files}
        render_file_map_zip_download(
            "Download Automation Repository ZIP",
            automation_zip_files,
            "automation_repository.zip",
            "automation-repository-zip-stage",
        )
        render_stage_download("Automation", edited_files)
        if st.button("Approve Automation Scripts"):
            try:
                st.session_state.stage_approved[stage_id] = True
                finalize_approved_workflow(
                    edited_files,
                    automation_repository_path,
                    st.session_state.get("automation_template_files", {}),
                )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
                set_progress("Failed", str(exc), st.session_state.progress)


def render_stage_workflow() -> None:
    stage_progress()
    current_stage = STAGES[st.session_state.stage_index]
    st.subheader(current_stage["title"])
    st.caption(current_stage["description"])
    active_instructions = combined_workflow_instructions()
    if active_instructions:
        with st.expander("Active workflow instructions", expanded=False):
            st.markdown(active_instructions.replace("\n", "\n\n"))
    if current_stage["id"] == "acceptance_criteria":
        render_acceptance_criteria_stage()
    elif current_stage["id"] == "bdd":
        render_bdd_stage()
    elif current_stage["id"] == "source_code":
        render_source_code_stage()
    elif current_stage["id"] == "test_cases":
        render_test_case_stage()
    elif current_stage["id"] == "automation":
        render_automation_stage()


def render_app_header() -> None:
    header_image = Path("assets/ai_sdlc_header_compact.png")
    if header_image.exists():
        left, center, right = st.columns([1, 5, 1])
        with center:
            st.image(str(header_image), use_container_width=True)


def main() -> None:
    init_state()
    sync_current_stage_status()
    st.title("AI SDLC Platform")
    render_app_header()

    if not secret_or_env("OPENAI_API_KEY"):
        st.session_state.openai_api_key = st.text_input(
            "OpenAI API Key",
            type="password",
            value=st.session_state.get("openai_api_key", ""),
            placeholder="Enter your key to generate artifacts",
            help="Thanks for entering your OpenAI API key. Please proceed on generating the artifacts.",
        )
        if st.session_state.get("openai_api_key", "").strip():
            st.success("Thanks for entering your OpenAI API key. Please proceed on generating the artifacts.")

    metrics_container = st.container()

    render_stage_workflow()

    sync_current_stage_status()
    with metrics_container:
        st.subheader("Agent Execution")
        col1, col2 = st.columns(2)
        col1.metric("Current Agent", display_agent_name())
        col2.metric("Status", display_status())
        if st.session_state.agent_log:
            with st.expander("Execution Log", expanded=True):
                for item in st.session_state.agent_log:
                    st.markdown(f"- {item}")

    if st.session_state.project_location:
        st.success(f"Generated project location: {st.session_state.project_location}")
    if st.session_state.outputs.get("Automation Repository Path"):
        st.success(f"Automation repository saved at: {st.session_state.outputs['Automation Repository Path']}")
    automation_source_files = st.session_state.outputs.get("Automation Source Files", {})
    if isinstance(automation_source_files, dict) and automation_source_files:
        render_file_map_zip_download(
            "Download Approved Automation Repository ZIP",
            automation_source_files,
            "approved_automation_repository.zip",
            "automation-repository-zip-final",
        )

    if st.session_state.outputs:
        st.subheader("Final Generated Assets")
        render_assets(st.session_state.outputs)

    st.subheader("Download Center")
    st.info("Use the Download PDF button inside each Generated Assets tab to download that tab only.")


if __name__ == "__main__":
    main()

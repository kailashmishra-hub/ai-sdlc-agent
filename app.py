from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from ai_sdlc.config import AppConfig
from ai_sdlc.output_manager import ProjectOutputManager
from ai_sdlc.services.document_extractor import extract_uploaded_files
from ai_sdlc.services.pdf_exporter import markdown_to_pdf_bytes
from ai_sdlc.services.vector_store import VectorStoreService
from ai_sdlc.workflow import run_sdlc_workflow


st.set_page_config(page_title="AI SDLC Platform", page_icon="AI", layout="wide")


def init_state() -> None:
    defaults = {
        "outputs": {},
        "project_location": "",
        "current_agent": "Idle",
        "status": "Waiting for documents",
        "progress": 0,
        "agent_log": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def render_sidebar() -> AppConfig:
    return AppConfig(
        project_name="AI_SDLC_Project",
        technology_stack="Python",
        automation_framework="Playwright",
        output_directory=Path.cwd() / "generated_projects",
        openai_api_key="",
        openai_model="gpt-4o-mini",
        astra_endpoint="",
        astra_token="",
        astra_collection="ai_sdlc_documents",
    )


def open_folder_button(path: str) -> None:
    if st.button("Open Folder", disabled=not path):
        st.info(f"Project folder: {path}")


def run_generation(config: AppConfig, uploaded_files: list) -> None:
    if not config.project_name.strip():
        st.error("Project Name is required.")
        return
    if not uploaded_files:
        st.error("Upload at least one PDF, TXT, or image file.")
        return

    with tempfile.TemporaryDirectory() as tmp:
        temp_dir = Path(tmp)
        st.session_state.agent_log = []
        st.session_state.current_agent = "Document Extraction"
        st.session_state.status = "Extracting uploaded content"
        st.session_state.progress = 10
        st.session_state.agent_log.append("Document Extraction: Extracting uploaded content")
        extraction = extract_uploaded_files(uploaded_files, temp_dir)

        output_manager = ProjectOutputManager(config)
        project_dir = output_manager.create_project_directory()

        st.session_state.current_agent = "Vector DB"
        st.session_state.status = "Storing document chunks in ChromaDB"
        st.session_state.progress = 20
        st.session_state.agent_log.append("Vector DB: Storing document chunks in ChromaDB")
        vector_service = VectorStoreService(project_dir / "vector_db")
        vector_summary = vector_service.store_text(extraction.combined_text, extraction.sources)

        def on_progress(agent: str, status: str, progress: int) -> None:
            st.session_state.current_agent = agent
            st.session_state.status = status
            st.session_state.progress = progress
            st.session_state.agent_log.append(f"{agent}: {status}")

        outputs = run_sdlc_workflow(
            extracted_content=extraction.combined_text,
            config=config,
            on_progress=on_progress,
        )
        outputs["Document Extraction"] = extraction.to_markdown()
        outputs["Vector DB Summary"] = vector_summary

        saved_files = output_manager.save_outputs(outputs)
        framework_files = output_manager.save_generated_framework(outputs)
        final_report = output_manager.save_final_report(outputs, saved_files + framework_files)
        st.session_state.outputs = outputs | {"Final Report": final_report}
        st.session_state.project_location = str(project_dir)
        st.session_state.current_agent = "Complete"
        st.session_state.status = "All artifacts generated"
        st.session_state.progress = 100
        st.session_state.agent_log.append("Complete: All artifacts generated")


def render_generated_assets(outputs: dict) -> None:
    tabs = st.tabs(
        ["Requirements", "User Stories", "Acceptance Criteria", "BDD", "Mapping", "Source Code", "Test Cases", "Automation"]
    )
    tab_keys = [
        "Requirement Specification",
        "User Stories",
        "Acceptance Criteria",
        "BDD Scenarios",
        "Traceability Matrix",
        "Generated Source Code",
        "Test Cases",
        "Automation Framework",
    ]
    for tab, key in zip(tabs, tab_keys):
        with tab:
            content = outputs.get(key, "No output generated yet.")
            if key == "Requirement Specification" and content != "No output generated yet.":
                st.markdown(_format_requirements_for_display(content))
            elif key == "BDD Scenarios" and content != "No output generated yet.":
                st.code(str(content), language="gherkin")
            elif key == "Generated Source Code" and content != "No output generated yet.":
                st.markdown(_source_files_to_markdown(content))
            else:
                st.markdown(content)


def _format_requirements_for_display(content: object) -> str:
    if isinstance(content, dict):
        return _requirements_dict_to_markdown(content)

    text = str(content).strip()
    parsed = _parse_jsonish_requirements(text)
    if parsed:
        return _requirements_dict_to_markdown(parsed)
    return text


def _parse_jsonish_requirements(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned.removeprefix("```json").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```").strip()
    if cleaned.endswith("```"):
        cleaned = cleaned.removesuffix("```").strip()

    if not cleaned.startswith("{"):
        return None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _requirements_dict_to_markdown(requirements: dict) -> str:
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
        value = requirements.get(key)
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


def _source_files_to_markdown(content: object) -> str:
    if not isinstance(content, dict):
        return str(content)

    lines = ["# Generated Source Code"]
    for path, source in content.items():
        language = "java" if str(path).endswith(".java") else "python" if str(path).endswith(".py") else "text"
        lines.append(f"## {path}")
        lines.append(f"```{language}")
        lines.append(str(source).rstrip())
        lines.append("```")
    return "\n\n".join(lines)


def render_download_center(outputs: dict) -> None:
    markdown_bundle = "\n\n---\n\n".join(f"# {key}\n\n{value}" for key, value in outputs.items())
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "Download Markdown",
            markdown_bundle,
            file_name="ai_sdlc_artifacts.md",
            mime="text/markdown",
            disabled=not outputs,
        )
    with col2:
        st.download_button(
            "Download PDF",
            markdown_to_pdf_bytes(markdown_bundle),
            file_name="ai_sdlc_report.pdf",
            mime="application/pdf",
            disabled=not outputs,
        )


def main() -> None:
    init_state()
    config = render_sidebar()

    st.title("AI SDLC Platform")

    st.subheader("Section 1: Document Upload")
    uploaded_files = st.file_uploader(
        "Upload PDF, image, or TXT files",
        type=["pdf", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    st.subheader("Section 2: Agent Execution")
    col1, col2, col3 = st.columns([2, 2, 1])
    col1.metric("Current Agent", st.session_state.current_agent)
    col2.metric("Status", st.session_state.status)
    col3.metric("Progress", f"{st.session_state.progress}%")
    st.progress(st.session_state.progress)
    if st.session_state.agent_log:
        with st.expander("Execution Log", expanded=True):
            for item in st.session_state.agent_log:
                st.markdown(f"- {item}")

    if st.button("Generate SDLC Artifacts", type="primary"):
        run_generation(config, uploaded_files or [])
        st.rerun()

    if st.session_state.project_location:
        st.success(f"Generated project location: {st.session_state.project_location}")
    open_folder_button(st.session_state.project_location)

    st.subheader("Section 3: Generated Assets")
    render_generated_assets(st.session_state.outputs)

    st.subheader("Section 4: Download Center")
    render_download_center(st.session_state.outputs)


if __name__ == "__main__":
    main()

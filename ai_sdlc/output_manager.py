from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ai_sdlc.config import AppConfig


class ProjectOutputManager:
    def __init__(self, config: AppConfig):
        self.config = config
        self.project_dir: Path | None = None

    def create_project_directory(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", self.config.project_name.strip()).strip("_") or "AIProject"
        self.config.output_directory.mkdir(parents=True, exist_ok=True)
        self.project_dir = self.config.output_directory / f"{safe_name}_{timestamp}"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        return self.project_dir

    def save_outputs(self, outputs: dict[str, object]) -> list[Path]:
        project_dir = self._require_project_dir()
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        files = []
        mapping = {
            "Requirement Specification": "requirement_specification.md",
            "User Stories": "user_stories.md",
            "Acceptance Criteria": "acceptance_criteria.md",
            "BDD Scenarios": "bdd_scenarios.md",
            "Test Cases": "test_cases.md",
            "Traceability Matrix": "traceability_matrix.md",
            "Automation Framework": "automation_framework.md",
            "Document Extraction": "document_extraction.md",
            "Vector DB Summary": "vector_db_summary.md",
        }
        for key, filename in mapping.items():
            if key in outputs:
                path = artifacts_dir / filename
                path.write_text(str(outputs[key]), encoding="utf-8")
                files.append(path)
        return files

    def save_generated_framework(self, outputs: dict[str, object]) -> list[Path]:
        project_dir = self._require_project_dir()
        files = []
        for group_name, root in [("Generated Source Code", "source"), ("Automation Source Files", "")]:
            source_files = outputs.get(group_name)
            if not isinstance(source_files, dict):
                continue
            for relative_path, content in source_files.items():
                base = project_dir / root if root else project_dir
                path = base / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(str(content), encoding="utf-8")
                files.append(path)
        return files

    def save_final_report(self, outputs: dict[str, object], files: list[Path]) -> str:
        project_dir = self._require_project_dir()
        report = [
            "# Final AI SDLC Report",
            "",
            f"Project: {self.config.project_name}",
            f"Technology Stack: {self.config.technology_stack}",
            f"Automation Framework: {self.config.automation_framework}",
            f"Project Directory: {project_dir}",
            "",
            "## Generated Files",
            *[f"- {path.relative_to(project_dir)}" for path in files],
            "",
        ]
        for key in [
            "Requirement Specification",
            "User Stories",
            "Acceptance Criteria",
            "BDD Scenarios",
            "Test Cases",
            "Traceability Matrix",
            "Automation Framework",
        ]:
            if key in outputs:
                report.extend([f"## {key}", "", str(outputs[key]), ""])
        report_text = "\n".join(report)
        (project_dir / "Final_Report.md").write_text(report_text, encoding="utf-8")
        return report_text

    def _require_project_dir(self) -> Path:
        if not self.project_dir:
            raise RuntimeError("Project directory has not been created.")
        return self.project_dir

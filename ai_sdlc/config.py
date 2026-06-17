from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    project_name: str
    technology_stack: str
    automation_framework: str
    output_directory: Path
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    astra_endpoint: str = ""
    astra_token: str = ""
    astra_collection: str = "ai_sdlc_documents"

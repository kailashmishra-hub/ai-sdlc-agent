from __future__ import annotations

import json
from typing import Any


def as_markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def fenced_json(data: dict[str, Any]) -> str:
    return "```json\n" + json.dumps(data, indent=2) + "\n```"


def content_hint(text: str, limit: int = 500) -> str:
    clean = " ".join(text.split())
    return clean[:limit] or "Uploaded product requirements"

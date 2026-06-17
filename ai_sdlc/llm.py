from __future__ import annotations

import json
from typing import Any

from ai_sdlc.config import AppConfig


class LLMClient:
    def __init__(self, config: AppConfig):
        self.config = config
        self._chat_model = None
        if config.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI

                self._chat_model = ChatOpenAI(
                    model=config.openai_model,
                    api_key=config.openai_api_key,
                    temperature=0.2,
                )
            except Exception:
                self._chat_model = None

    @property
    def enabled(self) -> bool:
        return self._chat_model is not None

    def invoke_text(self, system: str, user: str) -> str | None:
        if not self._chat_model:
            return None
        try:
            response = self._chat_model.invoke([("system", system), ("user", user)])
            return str(response.content)
        except Exception:
            return None

    def invoke_json(self, system: str, user: str) -> dict[str, Any] | None:
        text = self.invoke_text(system, user)
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

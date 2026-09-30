"""Thin wrapper around the Anthropic API -- the one place an LLM, rather
than Jev or plain code, does open-ended work in this pipeline.
"""

from __future__ import annotations

from anthropic import Anthropic

from report_qa.answer.prompt import SYSTEM_PROMPT


class AnswerLLM:
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def answer(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")

"""Thin wrapper around the Anthropic API -- the one place an LLM, rather
than Jev or plain code, does open-ended work in this pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from anthropic import Anthropic

from report_qa.answer.prompt import SYSTEM_PROMPT


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int


class AnswerLLM:
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self.last_usage: TokenUsage | None = None

    def answer(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        self.last_usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return "".join(block.text for block in response.content if block.type == "text")

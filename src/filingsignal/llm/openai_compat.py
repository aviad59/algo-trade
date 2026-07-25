"""OpenAI-compatible adapter — covers Kimi (Moonshot) and any OpenAI-style
endpoint (incl. GPT). Uses JSON-object mode (the broadly supported path); the
schema is carried by the prompt and enforced by the pydantic backstop in
``structured.py``. No prompt caching or thinking params.
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import Usage
from .base import Capabilities, LLMResult, StopReason

_FINISH_MAP = {
    "stop": StopReason.complete,
    "length": StopReason.max_tokens,
    "content_filter": StopReason.refusal,
}


class OpenAICompatClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url)
        self._client = client
        self.model = model
        # native_schema=False: we rely on json_object mode + prompt + pydantic.
        self.capabilities = Capabilities(native_schema=False, prompt_cache=False, thinking=False)

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: Optional[dict] = None,
        max_tokens: int = 4096,
        effort: Optional[str] = None,
    ) -> LLMResult:
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        choice = resp.choices[0]
        text = choice.message.content or ""
        stop = _FINISH_MAP.get(getattr(choice, "finish_reason", None), StopReason.other)

        u = getattr(resp, "usage", None)
        usage = Usage(
            input_tokens=int(getattr(u, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(u, "completion_tokens", 0) or 0),
        )
        return LLMResult(text=text, stop_reason=stop, usage=usage, raw=resp)

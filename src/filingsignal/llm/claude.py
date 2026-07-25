"""Anthropic (Claude) adapter. Native structured output via ``output_config``,
prompt caching on the system block, adaptive thinking when the model supports it.
Maps Anthropic stop-reasons / usage onto the neutral ``LLMResult``.
"""

from __future__ import annotations

from typing import Any, Optional

from ..models import Usage
from .base import Capabilities, LLMResult, StopReason

# Conservative allow-list: adaptive thinking + output_config.effort exist only on
# newer tiers. Unknown/future ids default to False (no 400s); enable explicitly.
_THINKING_MODELS = ("opus-4-6", "opus-4-7", "opus-4-8", "sonnet-5", "opus-5", "haiku-5")


def _supports_thinking(model: str) -> bool:
    return any(m in model for m in _THINKING_MODELS)


_STOP_MAP = {
    "end_turn": StopReason.complete,
    "stop_sequence": StopReason.complete,
    "tool_use": StopReason.complete,
    "max_tokens": StopReason.max_tokens,
    "refusal": StopReason.refusal,
    "model_context_window_exceeded": StopReason.context_overflow,
}


class ClaudeClient:
    def __init__(
        self,
        *,
        model: str,
        api_key: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
        self._client = client
        self.model = model
        self.capabilities = Capabilities(
            native_schema=True,
            prompt_cache=True,
            thinking=_supports_thinking(model),
        )

    def complete(
        self,
        *,
        system: str,
        user: str,
        schema: Optional[dict] = None,
        max_tokens: int = 4096,
        effort: Optional[str] = None,
    ) -> LLMResult:
        output_config: dict = {}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}

        extras: dict = {}
        if self.capabilities.thinking:
            extras["thinking"] = {"type": "adaptive"}
            if effort:
                output_config["effort"] = effort

        system_block: dict = {"type": "text", "text": system}
        if self.capabilities.prompt_cache:
            system_block["cache_control"] = {"type": "ephemeral"}

        kwargs: dict = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=[system_block],
            messages=[{"role": "user", "content": user}],
            **extras,
        )
        if output_config:
            kwargs["output_config"] = output_config

        with self._client.messages.stream(**kwargs) as stream:
            final = stream.get_final_message()

        text = ""
        for block in getattr(final, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text = block.text
                break

        sr_raw = getattr(final, "stop_reason", None)
        stop = _STOP_MAP.get(sr_raw, StopReason.other)
        # Attach a refusal explanation onto text so structured.py can surface it.
        if stop is StopReason.refusal:
            details = getattr(final, "stop_details", None)
            text = getattr(details, "explanation", "") if details else ""

        u = getattr(final, "usage", None)
        usage = Usage(
            input_tokens=int(getattr(u, "input_tokens", 0) or 0),
            output_tokens=int(getattr(u, "output_tokens", 0) or 0),
            cache_read_tokens=int(getattr(u, "cache_read_input_tokens", 0) or 0),
            cache_write_tokens=int(getattr(u, "cache_creation_input_tokens", 0) or 0),
        )
        return LLMResult(text=text, stop_reason=stop, usage=usage, raw=final)

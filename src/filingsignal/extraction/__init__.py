"""Stage 2 — extraction: filters (pre-LLM), form-specific prompts, Agent #1."""

from .extractor import Extractor
from .filters import FilterDecision, should_extract
from .prompts import FormClass, build_system_prompt, build_user_prompt, form_class

__all__ = [
    "Extractor",
    "FilterDecision",
    "should_extract",
    "FormClass",
    "form_class",
    "build_system_prompt",
    "build_user_prompt",
]

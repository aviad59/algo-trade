import pytest
from pydantic import BaseModel

from filingsignal.llm.base import Capabilities, LLMResult, StopReason
from filingsignal.llm.structured import LLMError, LLMRefusal, complete_structured


class Out(BaseModel):
    material: str
    confidence: float


def test_parses_with_fence_and_prose(fake_llm):
    c = fake_llm('here:\n```json\n{"material":"Copper","confidence":0.9}\n```')
    out, _ = complete_structured(c, system="s", user="u", schema=None, model_cls=Out, max_tokens=50)
    assert out.material == "Copper"


def test_retry_recovers_from_bad_json(fake_llm):
    c = fake_llm(['{not json', '{"material":"Gold","confidence":0.5}'])
    out, _ = complete_structured(c, system="s", user="u", schema=None, model_cls=Out, max_tokens=50, retries=1)
    assert out.material == "Gold"


def test_refusal_raises():
    class Refuse:
        model = "fake"
        capabilities = Capabilities()

        def complete(self, **kw):
            return LLMResult(text="policy", stop_reason=StopReason.refusal)

    with pytest.raises(LLMRefusal):
        complete_structured(Refuse(), system="s", user="u", schema=None, model_cls=Out, max_tokens=50)


def test_gives_up_after_retries(fake_llm):
    c = fake_llm(["nonsense", "still bad"])
    with pytest.raises(LLMError):
        complete_structured(c, system="s", user="u", schema=None, model_cls=Out, max_tokens=50, retries=1)

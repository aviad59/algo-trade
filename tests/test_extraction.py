import json

from filingsignal.extraction import Extractor, form_class, should_extract
from filingsignal.extraction.prompts import FormClass, build_system_prompt


def _payload(effects):
    return json.dumps({"summary": "sum", "extractor_confidence": 0.9, "dated_effects": effects})


def test_form_class_routing():
    assert form_class("8-K") is FormClass.EVENT
    assert form_class("10-Q") is FormClass.INTERIM
    assert form_class("40-F") is FormClass.ANNUAL


def test_event_prompt_injects_items():
    p = build_system_prompt("8-K", ["Copper (id: copper)"], items=["1.01", "8.01"])
    assert "1.01" in p and "8.01" in p


def test_extractor_drops_bad_effects(uni, fake_llm, fetched_8k):
    good = {"material": "copper", "perspective": "producer", "direction": "increase",
            "magnitude": "large", "window_start": "2026-07-01", "window_end": "2026-09-30",
            "rationale": "r", "evidence_quote": "\"q\""}
    bad_material = {**good, "material": "Plutonium"}
    inverted = {**good, "material": "gold", "window_start": "2026-09-30", "window_end": "2026-07-01"}
    empty_quote = {**good, "material": "silver", "evidence_quote": ""}
    client = fake_llm(_payload([good, bad_material, inverted, empty_quote]))
    out = Extractor(client=client, universe=uni).extract(fetched_8k)
    assert len(out.dated_effects) == 1
    assert out.dated_effects[0].material == "Copper"
    assert len(out.extraction_warnings) == 3  # three dropped


def test_filters_item_allowlist_and_keyword_gate(uni, fetched_8k):
    assert should_extract(fetched_8k, uni).keep is True  # 2.02 + copper keyword
    routine = fetched_8k.model_copy(update={"items": ["5.02"], "sections": {"exhibit": "director appointment"}})
    assert should_extract(routine, uni).keep is False
    nomat = fetched_8k.model_copy(update={"items": [], "form": "10-Q",
                                          "sections": {"mda": "vehicle deliveries and margins"}})
    assert should_extract(nomat, uni).keep is False


# --- section-targeting optimization (condense) ---------------------------- #

def test_condense_keeps_guidance_drops_boilerplate():
    from filingsignal.fetcher import condense_section
    guidance = "We expect copper production to increase to 750 million pounds in 2026 and 2027."
    boiler = "The accounting policies described herein conform to GAAP and applicable standards."
    text = "\n\n".join([boiler] * 15 + [guidance] + [boiler] * 15)
    out, changed = condense_section(text, ["copper"], max_chars=len(guidance) + 40)
    assert changed
    assert "750 million pounds" in out           # guidance kept
    assert out.count("GAAP") < text.count("GAAP")  # boilerplate mostly dropped
    assert len(out) <= len(text)


def test_condense_noop_when_within_budget():
    from filingsignal.fetcher import condense_section
    t = "short text about copper guidance for 2026"
    out, changed = condense_section(t, ["copper"], max_chars=1000)
    assert not changed and out == t


def test_condense_disabled_when_maxchars_zero():
    from filingsignal.fetcher import condense_section
    t = "x" * 5000
    out, changed = condense_section(t, [], max_chars=0)
    assert not changed and out == t

import pytest


@pytest.fixture(autouse=True)
def disable_real_llm_calls(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "enable_llm_diagnose", "0")
    monkeypatch.setattr(settings, "enable_llm_ocr_rewrite", "0")
    monkeypatch.setattr(settings, "enable_llm_data_labeling", "0")
    monkeypatch.setattr(settings, "enable_llm_profile_advice", "0")

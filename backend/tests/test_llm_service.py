from app.core.config import settings
from app.services import llm_service


def test_llm_service_without_key_does_not_crash():
    settings.openai_api_key = ""

    assert llm_service.is_llm_enabled() is False
    assert llm_service.get_llm_client() is None
    assert (
        llm_service.safe_generate_text(
            [{"role": "user", "content": "hello"}],
            fallback="fallback",
        )
        == "fallback"
    )


def test_safe_generate_text_masks_api_failures(monkeypatch):
    settings.openai_api_key = "test-key"
    settings.openai_model = "mimo-v2.5"

    def raise_error(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(llm_service, "generate_text", raise_error)

    assert (
        llm_service.safe_generate_text(
            [{"role": "user", "content": "hello"}],
            fallback="rule fallback",
        )
        == "rule fallback"
    )

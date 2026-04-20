import pytest

from claude_core.api.providers import GeminiProviderAdapter, get_provider_adapter


def test_get_provider_adapter_openai():
    adapter = get_provider_adapter("openai")
    assert adapter.name == "openai"
    assert adapter.default_base_url == "https://api.openai.com/v1"


def test_get_provider_adapter_gemini():
    adapter = get_provider_adapter("gemini")
    assert isinstance(adapter, GeminiProviderAdapter)
    assert "generativelanguage.googleapis.com" in adapter.default_base_url


def test_get_provider_adapter_invalid():
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider_adapter("invalid")

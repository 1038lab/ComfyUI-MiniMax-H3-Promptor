"""
ComfyUI-Minimax-H3-Promptor
Model listing helpers for local LLM provider dropdowns.
"""

from .config_manager import get_config_manager
from .provider_lmstudio import LMStudioProvider
from .provider_ollama import OllamaProvider

LOCAL_PROVIDERS = frozenset({"ollama", "lmstudio"})


def list_provider_models(provider_name: str) -> list[str]:
    """Return available model IDs for a local provider, or an empty list."""
    provider_name = provider_name.lower()
    if provider_name not in LOCAL_PROVIDERS:
        return []

    config_manager = get_config_manager()
    provider_config = config_manager.get_provider_config(provider_name)
    if not provider_config:
        return []

    api_base = provider_config.get("api_base", "")
    if provider_name == "ollama":
        return OllamaProvider(api_base=api_base).list_models()
    return LMStudioProvider(api_base=api_base).list_models()

"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""

    content: str = ""
    """The generated text content."""

    model: str = ""
    """The model that generated the response."""

    usage: dict = field(default_factory=dict)
    """Token usage statistics (optional, provider-dependent)."""

    error: str | None = None
    """Error message if the request failed. None means success."""

    @property
    def success(self) -> bool:
        """Whether the request was successful."""
        return self.error is None and bool(self.content)


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    To add a new provider:
    1. Create a new file in py/providers/
    2. Implement this interface
    3. Register the provider name in config.json
    """

    def __init__(self, api_base: str, api_key: str = "", model: str = ""):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            system_prompt: System instructions for the LLM.
            user_message: User's message/query.
            base64_images: List of base64 formatted images for multimodal analysis.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens in response.
            model: Override the default model for this request.

        Returns:
            LLMResponse with generated content or error.
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is reachable and configured.

        Returns:
            True if the provider can accept requests.
        """
        ...

    def get_model(self, override: str | None = None) -> str:
        """Get the model to use, with optional override."""
        return override or self.model

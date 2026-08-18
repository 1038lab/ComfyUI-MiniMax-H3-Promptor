"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

import requests
import time

from .provider_base import LLMProvider, LLMResponse
from .utils import log_debug, log_error, log_warning


# Request timeout in seconds (Ollama can be slow on first load)
REQUEST_TIMEOUT = 300

# Retry config
MAX_RETRIES = 1
RETRY_DELAY = 3.0


class OllamaProvider(LLMProvider):
    """Ollama local inference provider."""

    def __init__(self, api_base: str = "http://localhost:11434", **kwargs):
        # Ollama doesn't use API keys
        super().__init__(api_base=api_base, api_key="", **kwargs)

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat request to Ollama's /api/chat endpoint."""
        model_name = self.get_model(model)
        url = f"{self.api_base}/api/chat"

        user_payload = {"role": "user", "content": ""}
        if base64_images and len(base64_images) > 0:
            if isinstance(base64_images[0], dict):
                text_parts = []
                image_parts = []
                for item in base64_images:
                    if "text" in item:
                        text_parts.append(item["text"])
                    elif "image" in item:
                        image_parts.append(item["image"])
                user_payload["content"] = "\n\n".join(text_parts)
                if image_parts:
                    user_payload["images"] = image_parts
            else:
                user_payload["content"] = user_message
                user_payload["images"] = base64_images
        else:
            user_payload["content"] = user_message
        # Ollama llama3.2-vision and llava models often crash with HTTP 500 if a 'system' role is used.
        # We must fold the system prompt into the user message.
        final_content = f"{system_prompt}\n\n{user_payload['content']}"
        user_payload["content"] = final_content

        payload = {
            "model": model_name,
            "messages": [
                user_payload,
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": max(max_tokens * 2, 8192),
            },
        }

        log_debug(f"Ollama request → {url} | model={model_name} | temp={temperature}")

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                if response.status_code == 404:
                    return LLMResponse(
                        error=f"Model '{model_name}' not found in Ollama. "
                              f"Run: ollama pull {model_name}",
                        model=model_name,
                    )

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        log_warning(
                            f"Ollama server error {response.status_code}, "
                            f"retrying in {RETRY_DELAY}s..."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    return LLMResponse(
                        error=f"Ollama server error (HTTP {response.status_code}): {response.text[:200]}",
                        model=model_name,
                    )

                if not response.ok:
                    return LLMResponse(
                        error=f"Ollama HTTP {response.status_code}: {response.text[:200]}",
                        model=model_name,
                    )

                # Parse Ollama response
                data = response.json()
                content = data.get("message", {}).get("content", "")

                # Build usage info from Ollama's response
                usage = {}
                if "eval_count" in data:
                    usage["completion_tokens"] = data["eval_count"]
                if "prompt_eval_count" in data:
                    usage["prompt_tokens"] = data["prompt_eval_count"]
                if "eval_count" in data and "prompt_eval_count" in data:
                    usage["total_tokens"] = (
                        data["eval_count"] + data["prompt_eval_count"]
                    )

                log_debug(
                    f"Ollama response ← {len(content)} chars | "
                    f"tokens: {usage.get('total_tokens', '?')}"
                )

                return LLMResponse(
                    content=content,
                    model=data.get("model", model_name),
                    usage=usage,
                )

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    log_warning(f"Ollama timed out, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return LLMResponse(
                    error=f"Ollama request timed out after {REQUEST_TIMEOUT}s. "
                          f"The model may still be loading.",
                    model=model_name,
                )

            except requests.exceptions.ConnectionError:
                return LLMResponse(
                    error=f"Cannot connect to Ollama at {self.api_base}. "
                          f"Is Ollama running? Start it with: ollama serve",
                    model=model_name,
                )

            except Exception as e:
                return LLMResponse(
                    error=f"Unexpected Ollama error: {str(e)}",
                    model=model_name,
                )

        return LLMResponse(error="Max retries exceeded.", model=model_name)

    def is_available(self) -> bool:
        """Check if Ollama is running and reachable."""
        try:
            response = requests.get(
                f"{self.api_base}/api/tags",
                timeout=5,
            )
            return response.ok
        except Exception:
            return False

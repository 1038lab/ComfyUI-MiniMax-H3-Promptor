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


# Request timeout in seconds
REQUEST_TIMEOUT = 120

# Retry config
MAX_RETRIES = 1
RETRY_DELAY = 2.0


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible API provider."""

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to an OpenAI-compatible endpoint."""
        model_name = self.get_model(model)
        url = f"{self.api_base}/chat/completions"

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if base64_images:
            user_content = [{"type": "text", "text": user_message}]
            for img_b64 in base64_images:
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
                })
        else:
            user_content = user_message

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        log_debug(f"OpenAI request → {url} | model={model_name} | temp={temperature}")

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                # Handle HTTP errors
                if response.status_code == 401 or response.status_code == 403:
                    return LLMResponse(
                        error=f"Authentication failed (HTTP {response.status_code}). "
                              f"Please check your API key in config.json.",
                        model=model_name,
                    )

                if response.status_code == 429:
                    error_body = response.json().get("error", {})
                    retry_after = error_body.get("message", "Rate limit exceeded")
                    return LLMResponse(
                        error=f"Rate limited: {retry_after}",
                        model=model_name,
                    )

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        log_warning(
                            f"Server error {response.status_code}, "
                            f"retrying in {RETRY_DELAY}s..."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    return LLMResponse(
                        error=f"Server error (HTTP {response.status_code}) after retries.",
                        model=model_name,
                    )

                if not response.ok:
                    return LLMResponse(
                        error=f"HTTP {response.status_code}: {response.text[:200]}",
                        model=model_name,
                    )

                # Parse successful response
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return LLMResponse(
                        error="No choices in API response.",
                        model=model_name,
                    )

                content = choices[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})

                log_debug(
                    f"OpenAI response ← {len(content)} chars | "
                    f"tokens: {usage.get('total_tokens', '?')}"
                )

                return LLMResponse(
                    content=content,
                    model=data.get("model", model_name),
                    usage=usage,
                )

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    log_warning(f"Request timed out, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return LLMResponse(
                    error=f"Request timed out after {REQUEST_TIMEOUT}s.",
                    model=model_name,
                )

            except requests.exceptions.ConnectionError:
                return LLMResponse(
                    error=f"Cannot connect to {self.api_base}. "
                          f"Please check your API base URL.",
                    model=model_name,
                )

            except Exception as e:
                return LLMResponse(
                    error=f"Unexpected error: {str(e)}",
                    model=model_name,
                )

        return LLMResponse(error="Max retries exceeded.", model=model_name)

    def is_available(self) -> bool:
        """Check if the OpenAI endpoint is reachable."""
        try:
            # Attempt a lightweight request (list models)
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.get(
                f"{self.api_base}/models",
                headers=headers,
                timeout=10,
            )
            return response.ok
        except Exception:
            return False

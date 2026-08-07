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

# Anthropic API version
ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(LLMProvider):
    """Anthropic Claude native API provider."""

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a messages request to the Anthropic API."""
        model_name = self.get_model(model)
        url = f"{self.api_base}/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

        # Build user content
        if base64_images and len(base64_images) > 0:
            user_content = []
            if isinstance(base64_images[0], dict):
                for item in base64_images:
                    if "text" in item:
                        user_content.append({"type": "text", "text": item["text"]})
                    elif "image" in item:
                        user_content.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": item["image"],
                            }
                        })
            else:
                for img_b64 in base64_images:
                    user_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64,
                        }
                    })
                user_content.append({"type": "text", "text": user_message})
        else:
            user_content = user_message

        payload = {
            "model": model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_content},
            ],
        }

        log_debug(f"Claude request → {model_name} | temp={temperature}")

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                if response.status_code == 401 or response.status_code == 403:
                    return LLMResponse(
                        error=f"Authentication failed (HTTP {response.status_code}). "
                              f"Please check your Anthropic API key.",
                        model=model_name,
                    )

                if response.status_code == 429:
                    return LLMResponse(
                        error="Claude rate limit exceeded. Please wait and retry.",
                        model=model_name,
                    )

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        log_warning(
                            f"Claude server error {response.status_code}, "
                            f"retrying in {RETRY_DELAY}s..."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    return LLMResponse(
                        error=f"Claude server error (HTTP {response.status_code}) after retries.",
                        model=model_name,
                    )

                if not response.ok:
                    error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                    error_msg = error_data.get("error", {}).get("message", response.text[:200])
                    return LLMResponse(
                        error=f"HTTP {response.status_code}: {error_msg}",
                        model=model_name,
                    )

                # Parse successful response
                data = response.json()
                content_blocks = data.get("content", [])
                content = "".join(
                    block.get("text", "")
                    for block in content_blocks
                    if block.get("type") == "text"
                )

                usage_data = data.get("usage", {})
                usage = {
                    "prompt_tokens": usage_data.get("input_tokens", 0),
                    "completion_tokens": usage_data.get("output_tokens", 0),
                    "total_tokens": (
                        usage_data.get("input_tokens", 0) +
                        usage_data.get("output_tokens", 0)
                    ),
                }

                log_debug(
                    f"Claude response ← {len(content)} chars | "
                    f"tokens: {usage.get('total_tokens', '?')}"
                )

                return LLMResponse(
                    content=content,
                    model=data.get("model", model_name),
                    usage=usage,
                )

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    log_warning(f"Claude request timed out, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return LLMResponse(
                    error=f"Claude request timed out after {REQUEST_TIMEOUT}s.",
                    model=model_name,
                )

            except requests.exceptions.ConnectionError:
                return LLMResponse(
                    error=f"Cannot connect to Anthropic API at {self.api_base}.",
                    model=model_name,
                )

            except Exception as e:
                return LLMResponse(
                    error=f"Unexpected Claude error: {str(e)}",
                    model=model_name,
                )

        return LLMResponse(error="Max retries exceeded.", model=model_name)

    def is_available(self) -> bool:
        """Check if the Claude endpoint is reachable."""
        try:
            # Claude doesn't have a lightweight ping endpoint,
            # so we just check connectivity
            response = requests.get(
                self.api_base.replace("/v1", ""),
                timeout=10,
            )
            return response.status_code < 500
        except Exception:
            return False

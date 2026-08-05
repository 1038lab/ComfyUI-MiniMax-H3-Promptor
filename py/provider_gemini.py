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


class GeminiProvider(LLMProvider):
    """Google Gemini native API provider."""

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a generateContent request to the Gemini API."""
        model_name = self.get_model(model)
        url = f"{self.api_base}/models/{model_name}:generateContent?key={self.api_key}"

        headers = {
            "Content-Type": "application/json",
        }

        # Build user content parts
        parts = [{"text": user_message}]
        if base64_images:
            for img_b64 in base64_images:
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": img_b64,
                    }
                })

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        log_debug(f"Gemini request → {model_name} | temp={temperature}")

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
                              f"Please check your Gemini API key.",
                        model=model_name,
                    )

                if response.status_code == 429:
                    return LLMResponse(
                        error="Gemini rate limit exceeded. Please wait and retry.",
                        model=model_name,
                    )

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        log_warning(
                            f"Gemini server error {response.status_code}, "
                            f"retrying in {RETRY_DELAY}s..."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    return LLMResponse(
                        error=f"Gemini server error (HTTP {response.status_code}) after retries.",
                        model=model_name,
                    )

                if not response.ok:
                    return LLMResponse(
                        error=f"HTTP {response.status_code}: {response.text[:200]}",
                        model=model_name,
                    )

                # Parse successful response
                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    # Check for safety block
                    block_reason = data.get("promptFeedback", {}).get("blockReason", "")
                    if block_reason:
                        return LLMResponse(
                            error=f"Gemini blocked the request: {block_reason}",
                            model=model_name,
                        )
                    return LLMResponse(
                        error="No candidates in Gemini response.",
                        model=model_name,
                    )

                content_parts = candidates[0].get("content", {}).get("parts", [])
                content = "".join(p.get("text", "") for p in content_parts)

                usage_meta = data.get("usageMetadata", {})
                usage = {
                    "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                    "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                    "total_tokens": usage_meta.get("totalTokenCount", 0),
                }

                log_debug(
                    f"Gemini response ← {len(content)} chars | "
                    f"tokens: {usage.get('total_tokens', '?')}"
                )

                return LLMResponse(
                    content=content,
                    model=model_name,
                    usage=usage,
                )

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    log_warning(f"Gemini request timed out, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return LLMResponse(
                    error=f"Gemini request timed out after {REQUEST_TIMEOUT}s.",
                    model=model_name,
                )

            except requests.exceptions.ConnectionError:
                return LLMResponse(
                    error=f"Cannot connect to Gemini API at {self.api_base}.",
                    model=model_name,
                )

            except Exception as e:
                return LLMResponse(
                    error=f"Unexpected Gemini error: {str(e)}",
                    model=model_name,
                )

        return LLMResponse(error="Max retries exceeded.", model=model_name)

    def is_available(self) -> bool:
        """Check if the Gemini endpoint is reachable."""
        try:
            response = requests.get(
                f"{self.api_base}/models?key={self.api_key}",
                timeout=10,
            )
            return response.ok
        except Exception:
            return False

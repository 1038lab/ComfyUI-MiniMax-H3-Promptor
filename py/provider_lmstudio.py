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
from .utils import log_debug, log_warning


# Request timeout in seconds (local models can be slow on first load)
REQUEST_TIMEOUT = 300

# Retry config
MAX_RETRIES = 1
RETRY_DELAY = 3.0


class LMStudioProvider(LLMProvider):
    """
    LM Studio local inference provider.

    LM Studio exposes an OpenAI-compatible API server (default:
    http://localhost:1234/v1). Start it from the LM Studio
    'Developer' tab, then load a model to serve requests.
    """

    def __init__(self, api_base: str = "http://localhost:1234/v1", **kwargs):
        # LM Studio's local server doesn't require an API key
        super().__init__(api_base=api_base, api_key="", **kwargs)

    def _detect_model(self) -> str | None:
        """
        Auto-detect a usable model from the LM Studio server.

        Prefers a model actively loaded in memory (LM Studio's native
        /api/v0/models endpoint reports per-model state). Falls back to
        the first model listed by the OpenAI-compatible /models endpoint.
        """
        # LM Studio native endpoint: same server, without the /v1 suffix
        native_base = self.api_base[:-3] if self.api_base.endswith("/v1") else self.api_base
        try:
            response = requests.get(f"{native_base}/api/v0/models", timeout=10)
            if response.ok:
                models = response.json().get("data", [])
                for m in models:
                    if m.get("state") == "loaded":
                        return m.get("id", "")
                if models:
                    return models[0].get("id", "")
        except Exception:
            pass

        # Fallback: OpenAI-compatible /models
        try:
            response = requests.get(f"{self.api_base}/models", timeout=10)
            if response.ok:
                models = response.json().get("data", [])
                if models:
                    return models[0].get("id", "")
        except Exception:
            pass
        return None

    def list_models(self) -> list[str]:
        """
        List models exposed by the LM Studio server.

        Loaded models are returned first so they appear at the top of
        dropdowns; an empty selection still triggers auto-detect at runtime.
        """
        loaded: list[str] = []
        others: list[str] = []
        native_base = self.api_base[:-3] if self.api_base.endswith("/v1") else self.api_base
        try:
            response = requests.get(f"{native_base}/api/v0/models", timeout=10)
            if response.ok:
                for model in response.json().get("data", []):
                    model_id = model.get("id", "")
                    if not model_id:
                        continue
                    if model.get("state") == "loaded":
                        loaded.append(model_id)
                    else:
                        others.append(model_id)
                if loaded or others:
                    return loaded + others
        except Exception:
            pass

        try:
            response = requests.get(f"{self.api_base}/models", timeout=10)
            if response.ok:
                return [
                    model.get("id", "")
                    for model in response.json().get("data", [])
                    if model.get("id")
                ]
        except Exception:
            pass
        return []

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> LLMResponse:
        """Send a chat completion request to LM Studio's OpenAI-compatible API."""
        model_name = self.get_model(model)

        # No model configured -> auto-pick whatever is loaded in LM Studio
        if not model_name:
            detected = self._detect_model()
            if detected:
                model_name = detected
                log_debug(f"LM Studio auto-detected model: {model_name}")
            else:
                return LLMResponse(
                    error="No model configured and none detected on the LM Studio server. "
                          "Load a model in LM Studio (Developer tab) or set 'model_name' "
                          "on the node / 'default_model' in config.json.",
                    model="",
                )

        url = f"{self.api_base}/chat/completions"

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

        log_debug(f"LM Studio request → {url} | model={model_name} | temp={temperature}")

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=REQUEST_TIMEOUT,
                )

                if response.status_code == 404:
                    return LLMResponse(
                        error=f"Model '{model_name}' not found in LM Studio. "
                              f"Load it in the LM Studio Developer tab (or enable "
                              f"'Just-In-Time Model Loading'), or clear 'model_name' "
                              f"to auto-use the currently loaded model.",
                        model=model_name,
                    )

                if response.status_code >= 500:
                    if attempt < MAX_RETRIES:
                        log_warning(
                            f"LM Studio server error {response.status_code}, "
                            f"retrying in {RETRY_DELAY}s..."
                        )
                        time.sleep(RETRY_DELAY)
                        continue
                    return LLMResponse(
                        error=f"LM Studio server error (HTTP {response.status_code}).",
                        model=model_name,
                    )

                if not response.ok:
                    # LM Studio reports issues (e.g. no model loaded) in an
                    # OpenAI-style JSON error body — surface the message cleanly
                    detail = response.text[:300]
                    try:
                        detail = response.json().get("error", {}).get("message", detail)
                    except Exception:
                        pass
                    return LLMResponse(
                        error=f"LM Studio HTTP {response.status_code}: {detail}",
                        model=model_name,
                    )

                # Parse OpenAI-compatible response
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return LLMResponse(
                        error="No choices in LM Studio response.",
                        model=model_name,
                    )

                content = choices[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})

                log_debug(
                    f"LM Studio response ← {len(content)} chars | "
                    f"tokens: {usage.get('total_tokens', '?')}"
                )

                return LLMResponse(
                    content=content,
                    model=data.get("model", model_name),
                    usage=usage,
                )

            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    log_warning(f"LM Studio timed out, retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                    continue
                return LLMResponse(
                    error=f"LM Studio request timed out after {REQUEST_TIMEOUT}s. "
                          f"The model may still be loading.",
                    model=model_name,
                )

            except requests.exceptions.ConnectionError:
                return LLMResponse(
                    error=f"Cannot connect to LM Studio at {self.api_base}. "
                          f"Open LM Studio → Developer tab → Start Server "
                          f"(default: http://localhost:1234).",
                    model=model_name,
                )

            except Exception as e:
                return LLMResponse(
                    error=f"Unexpected LM Studio error: {str(e)}",
                    model=model_name,
                )

        return LLMResponse(error="Max retries exceeded.", model=model_name)

    def is_available(self) -> bool:
        """Check if the LM Studio server is running and reachable."""
        try:
            response = requests.get(
                f"{self.api_base}/models",
                timeout=5,
            )
            return response.ok
        except Exception:
            return False

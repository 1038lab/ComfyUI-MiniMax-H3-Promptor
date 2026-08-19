"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

import base64
import io
import re
import numpy as np


# ---------------------------------------------------------------------------
# Logging — ANSI colored console output matching ComfyUI-RMBG conventions
# ---------------------------------------------------------------------------

def log_info(msg: str):
    """Log an informational message."""
    print(f"\033[34m[H3-Promptor]\033[0m {msg}")


def log_error(msg: str):
    """Log an error message."""
    print(f"\033[31m[H3-Promptor ERROR]\033[0m {msg}")


def log_debug(msg: str):
    """Log a debug message (dimmed)."""
    print(f"\033[90m[H3-Promptor DEBUG]\033[0m {msg}")


def log_warning(msg: str):
    """Log a warning message."""
    print(f"\033[33m[H3-Promptor WARNING]\033[0m {msg}")


# ---------------------------------------------------------------------------
# Image conversion — ComfyUI tensor ↔ base64 PNG
# ---------------------------------------------------------------------------

def tensor_to_base64(tensor, max_frames: int = 4) -> list[str]:

    from PIL import Image

    # Handle Comfy API v3 VideoFromFile object wrappers
    if hasattr(tensor, "get_components"):
        tensor = tensor.get_components().images

    img_array = tensor.cpu().numpy()
    if img_array.ndim == 3:
        # [H, W, C] -> [1, H, W, C]
        img_array = np.expand_dims(img_array, axis=0)

    batch_size = img_array.shape[0]
    
    # Select frames uniformly if batch exceeds max_frames
    if batch_size > max_frames:
        indices = np.linspace(0, batch_size - 1, max_frames, dtype=int)
    else:
        indices = np.arange(batch_size)

    base64_images = []
    
    for idx in indices:
        frame_array = img_array[idx]
        # Convert from float [0,1] to uint8 [0,255]
        frame_array = np.clip(frame_array * 255.0, 0, 255).astype(np.uint8)

        img_pil = Image.fromarray(frame_array)
        buffered = io.BytesIO()
        img_pil.save(buffered, format="JPEG", quality=85) # Use JPEG for smaller payload
        base64_images.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))

    return base64_images


# ---------------------------------------------------------------------------
# Text sanitization — Clean LLM output artifacts
# ---------------------------------------------------------------------------

def sanitize_llm_output(text: str) -> str:
    if not text:
        return ""

    result = text.strip()

    # 1. Remove complete <think>...</think> blocks from reasoning models
    result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL | re.IGNORECASE).strip()
    
    # 1b. Remove unclosed <think>... if output was cut off or unfinished
    if "<think>" in result.lower() and "</think>" not in result.lower():
        result = re.sub(r"<think>.*", "", result, flags=re.DOTALL | re.IGNORECASE).strip()

    # 2. Remove "Thinking Process:" or "Thought:" reasoning blocks at the start up to [Shot 1] or section headers
    section_marker = re.search(
        r"(?:^|\n)(\[Shot 1\]|subject_definitions:|integrated_multimodal_description:|detailed_description:|For the target video|How the reference)",
        result,
        re.IGNORECASE
    )
    if section_marker and section_marker.start() > 0:
        preamble = result[:section_marker.start()]
        if any(term in preamble.lower() for term in ["thinking", "thought", "analyze", "drafting", "step 1", "step 2", "constraints", "1.", "2.", "*"]):
            result = result[section_marker.start():].strip()

    # 3. Remove markdown code fences
    fence_match = re.search(r"^```(?:text|json|plaintext|plain|markdown)?\s*\n(.*?)\n```\s*$", result, re.DOTALL)
    if fence_match:
        result = fence_match.group(1).strip()
    else:
        result = re.sub(r"^```[\w]*\s*\n", "", result)
        result = re.sub(r"\n```\s*$", "", result)

    # 4. Remove JSON wrapper if output is {"prompt": "..."}
    json_match = re.match(r'^\s*\{\s*"(?:prompt|output|result|text)"\s*:\s*"(.*?)"\s*\}\s*$', result, re.DOTALL)
    if json_match:
        result = json_match.group(1).strip().replace("\\n", "\n").replace('\\"', '"')

    # 5. Remove common LLM preambles
    preambles = [
        r"^Here(?:'s| is) (?:the|your) (?:generated |rewritten |final )?(?:H3 )?prompt:?\s*\n",
        r"^(?:Sure|Okay|Of course)[!,.]?\s*(?:Here(?:'s| is).*?:)?\s*\n",
        r"^Output:?\s*\n",
    ]
    for preamble in preambles:
        result = re.sub(preamble, "", result, flags=re.IGNORECASE)

    return result.strip()


# ---------------------------------------------------------------------------
# LLM Provider Factory
# ---------------------------------------------------------------------------
from .provider_openai import OpenAIProvider
from .provider_ollama import OllamaProvider
from .provider_gemini import GeminiProvider
from .provider_claude import ClaudeProvider

def _create_provider(provider_name: str, config_manager, api_key_override: str = ""):
    """Create an LLM provider instance from config."""
    provider_config = config_manager.get_provider_config(provider_name)
    if not provider_config:
        raise ValueError(f"Provider '{provider_name}' not configured.")

    api_base = provider_config.get("api_base", "")
    api_key = api_key_override or provider_config.get("api_key", "")
    model = provider_config.get("model", "") or provider_config.get("default_model", "")
    provider_type = provider_config.get("type", "openai").lower()

    if provider_type == "ollama":
        return OllamaProvider(api_base=api_base, model=model)
    elif provider_type == "gemini":
        return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
    elif provider_type == "anthropic" or provider_type == "claude":
        return ClaudeProvider(api_base=api_base, api_key=api_key, model=model)
    else:
        return OpenAIProvider(api_base=api_base, api_key=api_key, model=model)

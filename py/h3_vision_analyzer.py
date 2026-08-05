"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

import json
import os
from pathlib import Path

from .config_manager import get_config_manager
from .provider_openai import OpenAIProvider
from .provider_ollama import OllamaProvider
from .provider_gemini import GeminiProvider
from .provider_claude import ClaudeProvider
from .utils import log_info, log_error, tensor_to_base64


PRESETS_FILE = Path(__file__).parent.parent / "vision_prompts.json"

DEFAULT_PRESETS = {
    "image_prompts": {
        "Subject / Identity": "Focus exclusively on describing the main subject's appearance, facial features, and clothing.",
        "Comprehensive": "Analyze the entire image in extreme detail (subjects, environment, lighting, composition, mood).",
        "Action / Emotion": "Analyze only the physical actions, body language, posture, and facial expressions of the subject.",
        "Face & Expression Focus": "Analyze the facial features, gaze, and micro-expressions intimately.",
        "Prop & Object Interaction": "Focus purely on what objects the subject is holding or interacting with, and how they interact.",
        "Lighting & Camera": "Describe only the camera angle/framing (e.g., close-up, wide shot) and the ambient lighting setup.",
        "Cinematic Composition": "Analyze framing techniques, depth of field, foreground/background separation, and lens characteristics (wide, telephoto, macro).",
        "Style & Aesthetics": "Focus solely on the artistic style, color palette, texture, and overall mood.",
        "Color Palette & Texture": "Focus exclusively on the dominating colors, contrast ratios, and visual textures present."
    },
    "video_prompts": {
        "Motion Focus": "Focus strictly on the choreography, speed, and physical movement executed by the subject.",
        "Comprehensive": "Analyze the sequential pacing, camera movement, and subject motion across all provided keyframes.",
        "Camera Tracking": "Focus entirely on tracking how the virtual camera moves (panning, zooming, dollying, tracking).",
        "Temporal Flow": "Analyze the overall pacing, transitions, and scene progression across the extracted frames.",
        "Physics & Momentum": "Analyze the realistic physics, gravity, weight, and momentum of the moving subjects/objects.",
        "Background Dynamics": "Focus exclusively on what is moving in the environment or background, ignoring the main subject."
    }
}

def load_vision_presets():
    """Load vision presets from JSON or create default if missing."""
    if not PRESETS_FILE.exists():
        try:
            with open(PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_PRESETS, f, indent=4, ensure_ascii=False)
            return DEFAULT_PRESETS
        except Exception:
            return DEFAULT_PRESETS
    
    try:
        with open(PRESETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Failed to load vision_prompts.json: {e}")
        return DEFAULT_PRESETS

PRESETS = load_vision_presets()
IMAGE_MODES = list(PRESETS.get("image_prompts", DEFAULT_PRESETS["image_prompts"]).keys())
VIDEO_MODES = list(PRESETS.get("video_prompts", DEFAULT_PRESETS["video_prompts"]).keys())


PROVIDERS = ["openai", "ollama", "gemini", "claude"]


def _create_provider(provider_name: str, config_manager, api_key_override: str = ""):
    provider_config = config_manager.get_provider_config(provider_name)
    if not provider_config:
        raise ValueError(f"Provider '{provider_name}' not configured.")

    api_base = provider_config.get("api_base", "")
    api_key = api_key_override or provider_config.get("api_key", "")
    model = provider_config.get("default_model", "")

    if provider_name == "ollama":
        return OllamaProvider(api_base=api_base, model=model)
    elif provider_name == "gemini":
        return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
    elif provider_name == "claude":
        return ClaudeProvider(api_base=api_base, api_key=api_key, model=model)
    else:
        return OpenAIProvider(api_base=api_base, api_key=api_key, model=model)


class H3_Vision_Analyzer:
    """
    MiniMax H3 Vision Analyzer
    
    Extracts text descriptions and analysis from input references
    using targeted user prompts via JSON preset dropdowns.
    """

    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                "image_ref_1": ("IMAGE", {}),
                "mode_1": (IMAGE_MODES, {"default": IMAGE_MODES[0]}),

                "image_ref_2": ("IMAGE", {}),
                "mode_2": (IMAGE_MODES, {"default": IMAGE_MODES[0]}),

                "image_ref_3": ("IMAGE", {}),
                "mode_3": (IMAGE_MODES, {"default": IMAGE_MODES[0]}),
                
                "image_ref_4": ("IMAGE", {}),
                "mode_4": (IMAGE_MODES, {"default": IMAGE_MODES[0]}),

                "video_ref": ("IMAGE", {"tooltip": "Video batch input."}),
                "mode_video": (VIDEO_MODES, {"default": VIDEO_MODES[0]}),

                "output_language": (["English", "Chinese"], {
                    "default": "English",
                    "tooltip": "Language for the analysis output."
                }),
                "provider": (PROVIDERS, {
                    "default": "openai",
                    "tooltip": "Vision LLM provider to use for analysis.",
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "tooltip": "API key override.",
                }),
                "model_name": ("STRING", {
                    "default": "",
                    "tooltip": "Model override (e.g. gpt-4o, qwen-vl-max).",
                }),
                "temperature": ("FLOAT", {
                    "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05
                }),
                "max_tokens": ("INT", {
                    "default": 2048, "min": 256, "max": 8192, "step": 256
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("vision_context",)
    FUNCTION = "analyze_media"
    CATEGORY = "🧪AILab/🎬 MiniMax H3-Promptor"

    def analyze_media(
        self,
        image_ref_1=None, mode_1: str = IMAGE_MODES[0],
        image_ref_2=None, mode_2: str = IMAGE_MODES[0],
        image_ref_3=None, mode_3: str = IMAGE_MODES[0],
        image_ref_4=None, mode_4: str = IMAGE_MODES[0],
        video_ref=None, mode_video: str = VIDEO_MODES[0],
        output_language: str = "English",
        provider: str = "openai",
        api_key: str = "",
        model_name: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ):
        try:
            base64_images = []
            instructions = []
            media_tags = []
            
            # Helper to fetch active prompt string
            def get_prompt_str(mode: str, is_video=False):
                dict_key = "video_prompts" if is_video else "image_prompts"
                return PRESETS.get(dict_key, {}).get(mode, "Analyze visually.")

            if image_ref_1 is not None:
                media_tags.append("IMG1")
                frames = tensor_to_base64(image_ref_1, max_frames=1)
                base64_images.extend(frames)
                instructions.append(f"Regarding [Image 1]: {get_prompt_str(mode_1)}")
                
            if image_ref_2 is not None:
                media_tags.append("IMG2")
                frames = tensor_to_base64(image_ref_2, max_frames=1)
                base64_images.extend(frames)
                instructions.append(f"Regarding [Image 2]: {get_prompt_str(mode_2)}")
                
            if image_ref_3 is not None:
                media_tags.append("IMG3")
                frames = tensor_to_base64(image_ref_3, max_frames=1)
                base64_images.extend(frames)
                instructions.append(f"Regarding [Image 3]: {get_prompt_str(mode_3)}")
                
            if image_ref_4 is not None:
                media_tags.append("IMG4")
                frames = tensor_to_base64(image_ref_4, max_frames=1)
                base64_images.extend(frames)
                instructions.append(f"Regarding [Image 4]: {get_prompt_str(mode_4)}")
                
            if video_ref is not None:
                media_tags.append("VID")
                frames = tensor_to_base64(video_ref, max_frames=4)
                base64_images.extend(frames)
                instructions.append(f"Regarding [Video] ({len(frames)} extracted keyframes): {get_prompt_str(mode_video, is_video=True)}")

            if not base64_images:
                return ("No visual media provided for analysis.",)

            lang_instruction = ""
            if output_language.lower() == "chinese":
                lang_instruction = " You MUST write your entire analysis in Simplified Chinese (简体中文)."

            system_prompt = (
                "You are an expert film director and visual analyst. "
                "Analyze the provided visual media precisely according to the user's specific instructions for each item. "
                "Output a clean, structured report using the exact Labels the user provided (e.g. 'Image 1:', 'Protagonist:'). "
                "Focus strictly on visual aspects as instructed."
                f"{lang_instruction}"
            )
            
            user_message = "Please analyze the provided visuals based on these instructions:\n\n" + "\n".join(instructions)

            config_manager = get_config_manager()
            llm = _create_provider(provider, config_manager, api_key)
            model_override = model_name if model_name.strip() else None
            
            log_info(f"Analyzer calling {provider} with {len(base64_images)} frames...")
            
            response = llm.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                base64_images=base64_images,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model_override,
            )

            if not response.success:
                log_error(response.error)
                return (f"[Vision Analyzer Error]: {response.error}",)

            # Dump raw to console for inspection
            print(f"\n{'-'*20} RAW ANALYZER OUTPUT {'-'*20}")
            print(response.content)
            print(f"{'-'*60}\n")
            
            # Prepend invisible media signature for Auto mode targeting in Promptor Node
            sig_str = " ".join(media_tags)
            final_output = f"[MEDIA_SIGNATURE: {sig_str}]\n{response.content.strip()}"
            
            return (final_output,)

        except Exception as e:
            log_error(str(e))
            return (f"[Analyzer Exception]: {str(e)}",)


NODE_CLASS_MAPPINGS = {
    "H3_Vision_Analyzer": H3_Vision_Analyzer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_Vision_Analyzer": "MiniMax H3 Vision Analyzer",
}

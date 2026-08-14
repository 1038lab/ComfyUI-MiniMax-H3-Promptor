"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

import json
from pathlib import Path

import comfy.model_management as model_management
from comfy_api.latest import io

from .config_manager import get_config_manager
from .utils import log_info, log_error, tensor_to_base64, _create_provider


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


from .config_manager import get_config_manager

class H3_Vision_Analyzer(io.ComfyNode):
    """
    MiniMax H3 Vision Analyzer
    
    Extracts text descriptions and analysis from input references
    using targeted user prompts via JSON preset dropdowns.
    """

    @classmethod
    def define_schema(cls):
        try:
            _config = get_config_manager().load()
            active_providers = []
            default_uuid = _config.get("defaults", {}).get("vision_provider", "")
            default_choice = ""
            
            for k, v in _config.get("providers", {}).items():
                if v.get("enabled", True) is not False:
                    model_name = v.get("model", "")
                    name = f"{v.get('name', k)} ({model_name})" if model_name else v.get("name", k)
                    active_providers.append(name)
                    if k == default_uuid:
                        default_choice = name
            
            active_providers.sort()
            
            if not default_choice and active_providers:
                default_choice = active_providers[0]
                
            if not active_providers:
                active_providers = ["No Provider Configured"]
                default_choice = active_providers[0]
            
            if default_choice in active_providers:
                active_providers.remove(default_choice)
                active_providers.insert(0, default_choice)
                

        except Exception:
            active_providers = ["Error Loading Providers"]
            default_choice = active_providers[0]

        return io.Schema(
            node_id="H3_Vision_Analyzer",
            display_name="MiniMax H3 Vision Analyzer",
            category="🧪AILab/🎬 MiniMax H3-Promptor",
            inputs=[
                io.Combo.Input("global_image_mode", options=IMAGE_MODES, default="Subject / Identity"),
                io.Combo.Input("global_video_mode", options=VIDEO_MODES, default="Comprehensive"),
                io.String.Input("custom_prompt_override", multiline=True, default="", tooltip="Line-by-line override. Example: <Picture 2>: Overwrite prompt here", optional=True),
                
                io.Autogrow.Input("ref_images", optional=True,
                                  template=io.Autogrow.TemplatePrefix(
                                      input=io.Image.Input("image", tooltip="Reference image"),
                                      prefix="image_", min=0, max=9)),
                io.Autogrow.Input("ref_videos", optional=True,
                                  template=io.Autogrow.TemplatePrefix(
                                      input=getattr(io, "Video", getattr(io, "AnyType", io.Image)).Input("video", tooltip="Reference video"),
                                      prefix="video_", min=0, max=3)),

                io.Combo.Input("output_language", options=["English", "Chinese"], default="English", tooltip="Language for the analysis output.", optional=True),
                io.Combo.Input("provider", options=active_providers, default=default_choice, tooltip="Vision LLM provider to use for analysis.", optional=True),
                io.Float.Input("temperature", default=0.2, min=0.0, max=1.0, step=0.05, optional=True),
                io.Int.Input("max_tokens", default=2048, min=256, max=8192, step=256, optional=True),
            ],
            outputs=[
                io.String.Output("vision_context", display_name="vision_context")
            ],
        )

    @classmethod
    def execute(
        cls,
        global_image_mode: str,
        global_video_mode: str,
        output_language: str = "English",
        provider: str = "",
        custom_prompt_override: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        ref_images: io.Autogrow.Type = None,
        ref_videos: io.Autogrow.Type = None,
    ) -> io.NodeOutput:
        try:
            from .response_parser import ResponseParser
            from .prompt_builder import PromptBuilder
            from .vision_orchestrator import VisionOrchestrator

            # 1. Resolve provider + config
            config_manager = get_config_manager()
            provider_key = config_manager.find_provider_by_display_name(provider)
            provider_config = config_manager.get_provider_config(provider_key)
            llm = _create_provider(provider_key, config_manager)
            batch_vision = provider_config.get("batch_vision", True)

            # VRAM management (Ollama only)
            if provider_key == "ollama":
                log_info("Unloading local Vision model from VRAM...")
                model_management.unload_all_models()
                model_management.soft_empty_cache()

            # 2. Build prompts via PromptBuilder
            prompt_builder = PromptBuilder()
            system_prompt = prompt_builder.build_vision_system_prompt(output_language)
            vibe_system_prompt = prompt_builder.build_vibe_system_prompt()
            overrides = PromptBuilder.parse_overrides(custom_prompt_override)

            # 3. Dispatch all media through orchestrator
            orchestrator = VisionOrchestrator(
                llm=llm,
                prompt_builder=prompt_builder,
                response_parser_cls=ResponseParser,
                system_prompt=system_prompt,
                vibe_system_prompt=vibe_system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                model_override=llm.model,
            )
            final_dict, media_keys = orchestrator.analyze_all(
                ref_images=ref_images,
                ref_videos=ref_videos,
                presets=PRESETS,
                overrides=overrides,
                global_image_mode=global_image_mode,
                global_video_mode=global_video_mode,
                output_language=output_language,
                batch_vision=batch_vision,
                provider_label=provider_key,
            )

            if not final_dict:
                return io.NodeOutput("{}")

            # 4. Serialize + return
            final_dict["_media_keys"] = media_keys
            final_output = json.dumps(final_dict, indent=4, ensure_ascii=False)

            # Console dump for debug
            print(f"\n{'-'*20} RAW ANALYZER OUTPUT {'-'*20}")
            print(final_output)
            print(f"{'-'*60}\n")

            if provider_key == "ollama":
                log_info("Re-clearing VRAM after VLM execution to free space for H3...")
                model_management.soft_empty_cache()

            return io.NodeOutput(final_output)

        except Exception as e:
            log_error(str(e))
            return io.NodeOutput(f"[Analyzer Exception]: {str(e)}")


NODE_CLASS_MAPPINGS = {
    "H3_Vision_Analyzer": H3_Vision_Analyzer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_Vision_Analyzer": "MiniMax H3 Vision Analyzer",
}

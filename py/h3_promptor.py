"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""
import re

try:
    from comfy_api.latest import io
except ImportError:
    class _DummyIO:
        class ComfyNode: pass
        class NodeOutput:
            def __init__(self, *args, **kwargs):
                self.args = args
        class Schema:
            def __init__(self, *args, **kwargs): pass
        class _Field:
            @classmethod
            def Input(cls, *args, **kwargs): return None
            @classmethod
            def Output(cls, *args, **kwargs): return None
        Combo = Image = Video = Audio = String = Float = Int = _Field
    io = _DummyIO()

from .config_manager import get_config_manager
from .task_detector import TASK_TYPE_OPTIONS, TaskDetector
from .prompt_builder import PromptBuilder
from .post_processor import PostProcessor
from .utils import log_info, log_error, _create_provider


class H3_Promptor(io.ComfyNode):

    @classmethod
    def define_schema(cls):
        try:
            _config = get_config_manager().load()
            active_providers = []
            default_uuid = _config.get("defaults", {}).get("promptor_provider", "")
            default_choice = ""
            
            import re
            for k, v in _config.get("providers", {}).items():
                if v.get("enabled", True) is not False:
                    model_name = v.get("model", "").strip()
                    raw_name = v.get("name", k)
                    clean_raw = re.sub(r"\s*\([^)]*\)\s*$", "", raw_name).strip()
                    if model_name:
                        name = f"{clean_raw} ({model_name})"
                    else:
                        name = clean_raw
                    active_providers.append(name)
                    if k == default_uuid:
                        default_choice = name
            
            active_providers.sort()
            
            if not default_choice and active_providers:
                default_choice = active_providers[0]
                
            if not active_providers:
                active_providers = ["No Provider Configured"]
                default_choice = active_providers[0]
                
        except Exception:
            active_providers = ["Error Loading Providers"]
            default_choice = active_providers[0]

        return io.Schema(
            node_id="H3_Promptor",
            display_name="MiniMax H3 Promptor",
            category="🧪AILab/🎬 MiniMax H3-Promptor",
            inputs=[
                io.Combo.Input("task_type", options=TASK_TYPE_OPTIONS, default=TASK_TYPE_OPTIONS[0], tooltip="Task format for MiniMax H3 (Text-to-Video, Image-to-Video, Ref2VA, etc.) or Auto detection based on reference media."),
                io.String.Input("scene_direction", multiline=True, default="", tooltip="Optional director instructions & scene plot. E.g.: Start with <Picture 1> in a slow push-in, transition to <Picture 2> in the rain as the character turns to the camera and says: \"The time has come.\" (Leave empty for full AI creative freedom)"),
                io.Float.Input("duration", default=5.0, min=4.0, max=15.0, step=0.5, tooltip="Target video duration in seconds (valid MiniMax H3 range: 4.0 - 15.0s)."),
                io.String.Input("vision_context", multiline=True, force_input=True, default="", optional=True, tooltip="Connect the vision_context JSON output from the MiniMax H3 Vision node here."),
                io.Combo.Input("reference_images", options=["Auto", "1", "2", "3", "4", "5", "6", "7", "8", "9"], default="Auto", optional=True, tooltip="Number of reference images. 'Auto' synchronizes dynamically with the Vision node (max 9)."),
                io.Combo.Input("reference_videos", options=["Auto", "1", "2", "3"], default="Auto", optional=True, tooltip="Number of reference videos. 'Auto' synchronizes dynamically with the Vision node (max 3)."),
                io.Combo.Input("reference_audios", options=["Auto", "1", "2", "3"], default="Auto", optional=True, tooltip="Number of reference audio tracks. 'Auto' synchronizes dynamically with the Vision node (max 3)."),
                io.Combo.Input("output_language", options=["English", "Chinese"], default="English", optional=True, tooltip="Language for the final structured MiniMax H3 prompt (English or Chinese)."),
                io.Combo.Input("provider", options=active_providers, default=default_choice, optional=True, tooltip="LLM provider used for Director reasoning and prompt synthesis."),
                io.Float.Input("temperature", default=0.7, min=0.0, max=1.0, step=0.05, optional=True, tooltip="Sampling temperature for LLM text generation (0.0 = deterministic/strict, 1.0 = creative)."),
                io.Int.Input("max_tokens", default=4096, min=256, max=8192, step=256, optional=True, tooltip="Maximum token limit for LLM generation response."),
            ],
            outputs=[
                io.String.Output("prompt", display_name="PROMPT", tooltip="Formatted MiniMax H3 structured prompt ready to connect to MiniMax Sampler / Director."),
                io.Float.Output("duration", display_name="DURATION", tooltip="Target video duration in seconds (direct pass-through for downstream Sampler/Audio nodes)."),
                io.Int.Output("length", display_name="LENGTH", tooltip="Frame count at 24 fps, snapped up to the model's 17k+5 grid (124 = ~5s; trained range is ~124-362, longer is untested)"),
            ],
        )

    @classmethod
    def execute(
        cls,
        task_type: str,
        duration: float,
        scene_direction: str = "",
        description: str = "",
        vision_context: str = "",
        reference_images: str = "Auto",
        reference_videos: str = "Auto",
        reference_audios: str = "Auto",
        output_language: str = "English",
        provider: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> io.NodeOutput:
        user_prompt = scene_direction if scene_direction != "" else description
        if not user_prompt:
            user_prompt = kwargs.get("scene_direction", "") or kwargs.get("description", "")
        cleaned_prompt, dur, frames = cls.generate_prompt(
            task_type=task_type,
            description=user_prompt,
            duration=duration,
            vision_context=vision_context,
            reference_images=reference_images,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            output_language=output_language,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return io.NodeOutput(cleaned_prompt, float(dur), int(frames))

    RETURN_TYPES = ("STRING", "FLOAT", "INT")
    RETURN_NAMES = ("prompt", "duration", "length")
    OUTPUT_TOOLTIPS = (
        "Formatted MiniMax H3 structured prompt ready to connect to MiniMax Sampler / Director.",
        "Target video duration in seconds (direct pass-through for downstream Sampler/Audio nodes).",
        "Frame count at 24 fps, snapped up to the model's 17k+5 grid (124 = ~5s; trained range is ~124-362, longer is untested)"
    )

    @classmethod
    def generate_prompt(
        cls,
        task_type: str,
        description: str,
        duration: float,
        vision_context: str = "",
        reference_images: str = "Auto",
        reference_videos: str = "Auto",
        reference_audios: str = "Auto",
        output_language: str = "English",
        provider: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """Generate a MiniMax H3 structured prompt using the two-stage director pipeline."""
        from .pipeline_engine import execute_director_pipeline
        result = execute_director_pipeline(
            task_type=task_type,
            description=description,
            duration=duration,
            vision_context=vision_context,
            reference_images=reference_images,
            reference_videos=reference_videos,
            reference_audios=reference_audios,
            output_language=output_language,
            provider=provider,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return (result["final_prompt"], float(result["duration"]), int(result["length"]))


NODE_CLASS_MAPPINGS = {
    "H3_Promptor": H3_Promptor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_Promptor": "MiniMax H3 Promptor",
}


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


PROVIDERS = ["openai", "ollama", "gemini", "claude"]


class H3_Vision_Analyzer(io.ComfyNode):
    """
    MiniMax H3 Vision Analyzer
    
    Extracts text descriptions and analysis from input references
    using targeted user prompts via JSON preset dropdowns.
    """

    @classmethod
    def define_schema(cls):
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
                io.Combo.Input("provider", options=PROVIDERS, default="openai", tooltip="Vision LLM provider to use for analysis.", optional=True),
                io.String.Input("api_key", default="", tooltip="API key override.", optional=True),
                io.String.Input("model_name", default="", tooltip="Model override (e.g. gpt-4o, qwen-vl-max).", optional=True),
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
        provider: str = "openai",
        api_key: str = "",
        model_name: str = "",
        custom_prompt_override: str = "",
        temperature: float = 0.2,
        max_tokens: int = 2048,
        ref_images: io.Autogrow.Type = None,
        ref_videos: io.Autogrow.Type = None,
    ) -> io.NodeOutput:
        try:
            # Hardcode unload logic to always trigger for Ollama
            if provider == "ollama":
                log_info("Unloading local Vision model from VRAM...")
                model_management.unload_all_models()
                model_management.soft_empty_cache()
            media_keys = []
            final_dict = {}

            # Helper to fetch active prompt string
            def get_prompt_str(mode: str, is_video=False):
                dict_key = "video_prompts" if is_video else "image_prompts"
                return PRESETS.get(dict_key, {}).get(mode, "Analyze visually.")

            # Generate overrides mapping
            overrides = {}
            for line in custom_prompt_override.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k_norm = k.lower()
                    item_idx = ''.join(filter(str.isdigit, k_norm))
                    if not item_idx: continue
                    idx = int(item_idx)
                    
                    if "<" not in k_norm and ("image" in k_norm or "video" in k_norm or "img" in k_norm or "vid" in k_norm):
                        idx += 1
                        
                    if "video" in k_norm or "vid" in k_norm:
                        key = f"<Video {idx}>"
                    else:
                        key = f"<Picture {idx}>"
                    overrides[key] = v.strip()

            config_manager = get_config_manager()
            llm = _create_provider(provider, config_manager, api_key)
            model_override = model_name if model_name.strip() else None

            lang_instruction = ""
            if output_language.lower() == "chinese":
                lang_instruction = " You MUST write your response in Simplified Chinese (简体中文)."
            else:
                lang_instruction = " You MUST write your response in English."

            system_prompt = (
                "You are an expert film director and visual analyst. "
                "Analyze the provided visual media precisely according to the user's instructions.\n"
                "CRITICAL: You MUST output ONLY a valid stringified JSON dictionary mapping the specific media keys to their descriptions. "
                "For example: {\"<Picture 1>\": \"...\", \"<Picture 2>\": \"...\"}. "
                "Do NOT output markdown blocks or extra text outside the JSON."
                f"{lang_instruction}"
            )

            # Provide safety wrapper around ComfyAPI dict/list types
            def _get_iterable(media_input):
                if not media_input:
                    return []
                if isinstance(media_input, dict):
                    return media_input.values()
                if isinstance(media_input, (list, tuple)):
                    return media_input
                return [media_input]

            # 1. Process All Images Together in ONE Standard Payload
            img_list = list(img for img in _get_iterable(ref_images) if img is not None)
            img_index = 1
            
            if img_list:
                interleaved_payload = []
                chunk_keys = []
                instructions = []
                all_frames = []
                
                pos = 1
                for img in img_list:
                    target_key = f"<Picture {img_index}>"
                    media_keys.append(target_key)
                    chunk_keys.append(target_key)
                    frames = tensor_to_base64(img, max_frames=1)
                    active_prompt = overrides.get(target_key, get_prompt_str(global_image_mode))
                    
                    instructions.append(f"Media {pos} is {target_key}: Please analyze based on the instruction -> {active_prompt}")
                    all_frames.extend(frames)
                    
                    img_index += 1
                    pos += 1
                    
                mega_prompt = "Order of attached media:\n" + "\n".join(instructions)
                interleaved_payload.append({"text": mega_prompt})
                for f in all_frames:
                    interleaved_payload.append({"image": f})
                    
                log_info(f"Analyzer calling {provider} for ALL IMAGES ({len(chunk_keys)} items)...")
                response = llm.chat(
                    system_prompt=system_prompt,
                    user_message="",
                    base64_images=interleaved_payload,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model_override,
                )
                
                if response.success:
                    try:
                        clean_content = response.content.strip()
                        if clean_content.startswith("```json"): clean_content = clean_content.replace("```json", "", 1)
                        if clean_content.endswith("```"): clean_content = clean_content[:-3]
                        
                        parsed = json.loads(clean_content.strip())
                        for key in chunk_keys:
                            final_dict[key] = parsed.get(key, "Failed to analyze.")
                    except json.JSONDecodeError:
                        log_error(f"JSON Error in Image Batch.")
                        for key in chunk_keys: final_dict[key] = "LLM failed to return valid JSON."
                else:
                    log_error(f"API Error in Image Batch: {response.error}")
                    for key in chunk_keys: final_dict[key] = f"API Error: {response.error}"

            # 2. Process Videos Logically Separately (1 Video per API call) to prevent Video dropping
            vid_index = 1
            for vid in _get_iterable(ref_videos):
                if vid is not None:
                    target_key = f"<Video {vid_index}>"
                    media_keys.append(target_key)
                    frames = tensor_to_base64(vid, max_frames=4)
                    active_prompt = overrides.get(target_key, get_prompt_str(global_video_mode, is_video=True))
                    
                    interleaved_payload = []
                    mega_prompt = f"{target_key}: Please analyze this sequence of {len(frames)} frames based on the instruction -> {active_prompt}"
                    interleaved_payload.append({"text": mega_prompt})
                    for f in frames:
                        interleaved_payload.append({"image": f})
                    
                    log_info(f"Analyzer calling {provider} for {target_key} ({len(frames)} frames)...")
                    response = llm.chat(
                        system_prompt=system_prompt,
                        user_message="",
                        base64_images=interleaved_payload,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=model_override,
                    )
                    
                    if response.success:
                        try:
                            clean_content = response.content.strip()
                            if clean_content.startswith("```json"): clean_content = clean_content.replace("```json", "", 1)
                            if clean_content.endswith("```"): clean_content = clean_content[:-3]
                            
                            parsed = json.loads(clean_content.strip())
                            final_dict[target_key] = parsed.get(target_key, "Failed to analyze.")
                        except json.JSONDecodeError:
                            log_error(f"JSON Error in Video {vid_index}.")
                            final_dict[target_key] = "LLM failed to return valid JSON."
                    else:
                        log_error(f"API Error in Video {vid_index}: {response.error}")
                        final_dict[target_key] = f"API Error: {response.error}"
                        
                    vid_index += 1

            if not final_dict:
                return ("{}", "T2V (No Media)")

            # 3. Global Vibe Instruction (Text Only Summarization)
            vibe_prompt = overrides.get("Global_Vibe", get_prompt_str(global_image_mode))
            context_str = json.dumps(final_dict, ensure_ascii=False)
            vibe_message = f"Based on the following individual media analyses:\n{context_str}\n\nProvide the final 'Global_Vibe' synthesis using this instruction: {vibe_prompt}"
            
            log_info(f"Analyzer calling {provider} for Global Vibe synthesis...")
            vibe_res = llm.chat(
                system_prompt=system_prompt,
                user_message=vibe_message,
                base64_images=None,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model_override
            )
            
            if vibe_res.success:
                try:
                    clean_content = vibe_res.content.strip()
                    if clean_content.startswith("```json"): clean_content = clean_content.replace("```json", "", 1)
                    if clean_content.endswith("```"): clean_content = clean_content[:-3]
                    parsed = json.loads(clean_content.strip())
                    final_dict["Global_Vibe"] = parsed.get("Global_Vibe", "Failed to synthesize.")
                except json.JSONDecodeError:
                    if "Global_Vibe" in vibe_res.content and "}" not in vibe_res.content:
                        final_dict["Global_Vibe"] = vibe_res.content.replace('"', '').strip()
                    else:
                        final_dict["Global_Vibe"] = "LLM failed to return valid JSON for Global_Vibe."
            else:
                final_dict["Global_Vibe"] = f"API Error: {vibe_res.error}"
                
            # Embed media keys information to guarantee H3_Promptor can count accurately
            final_dict["_media_keys"] = media_keys
            
            final_output = json.dumps(final_dict, indent=4, ensure_ascii=False)
            
            # Dump raw to console for inspection (Restored)
            print(f"\n{'-'*20} RAW ANALYZER OUTPUT {'-'*20}")
            print(final_output)
            print(f"{'-'*60}\n")
            
            if provider == "ollama":
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

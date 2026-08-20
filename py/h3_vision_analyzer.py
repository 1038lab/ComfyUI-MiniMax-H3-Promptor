"""
ComfyUI-Minimax-H3-Promptor V1.3.0
Vision Analyzer Node (V2)

Handles UI media uploads directly (no image/video input ports), outputs parsed vision context,
and passes raw media files to reference output ports.
"""
import os
import json
from pathlib import Path
from PIL import Image
import torch
import numpy as np

import folder_paths
import comfy.model_management as model_management
from comfy_api.latest import io

from .config_manager import get_config_manager
from .utils import log_info, log_error, _create_provider

# Load vision prompts json
curr_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.dirname(curr_dir)
with open(os.path.join(root_dir, 'vision_prompts.json'), 'r', encoding='utf-8') as f:
    PRESETS = json.load(f)

IMAGE_MODES = list(PRESETS.get('image_prompts', {}).keys())
VIDEO_MODES = list(PRESETS.get('video_prompts', {}).keys())
def get_file_path(filename: str, type: str = "input", subfolder: str = "") -> str:
    """Resolve file path using comfyui's folder paths logic."""
    if type == "input":
        base_dir = folder_paths.get_input_directory()
    elif type == "output":
         base_dir = folder_paths.get_output_directory()
    elif type == "temp":
         base_dir = folder_paths.get_temp_directory()
    else:
        # Default fallback
        base_dir = folder_paths.get_input_directory()
    
    if subfolder:
        return os.path.join(base_dir, subfolder, filename)
    return os.path.join(base_dir, filename)

def video_path_to_tensor(video_path: str, max_frames: int = 4) -> torch.Tensor:
    import cv2
    cap = cv2.VideoCapture(video_path)
    frames = []
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames > max_frames:
        indices = np.linspace(0, total_frames - 1, max_frames, dtype=int)
    else:
        indices = np.arange(total_frames)
        
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(frame)
    cap.release()
    
    if len(frames) == 0:
        raise ValueError(f"Failed to read any frames from video: {video_path}")
        
    frames_np = np.stack(frames).astype(np.float32) / 255.0
    return torch.from_numpy(frames_np)

class H3_Vision_Analyzer(io.ComfyNode):
    """
    Minimax H3 Vision Analyzer
    Provides explicit configuration and exact original-ratio Media outputs.
    """
    OUTPUT_IS_LIST = (False, True)
    
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
                
        except Exception:
            active_providers = ["Error Loading Providers"]
            default_choice = active_providers[0]

        return io.Schema(
            node_id="H3_Vision_Analyzer",
            display_name="MiniMax H3 Vision Analyzer", # UI Name replacing older one conceptually
            category="🧪AILab/🎬 MiniMax H3-Promptor",
            inputs=[
                # Top section Configuration
                io.Combo.Input("global_image_mode", options=IMAGE_MODES, default="Subject / Identity"),
                io.Combo.Input("global_video_mode", options=VIDEO_MODES, default="Comprehensive"),
                io.Combo.Input("provider", options=active_providers, default=default_choice, tooltip="Vision LLM provider to use for analysis.", optional=True),
                io.Float.Input("temperature", default=0.2, min=0.0, max=1.0, step=0.05, optional=True),
                io.Int.Input("max_tokens", default=2048, min=256, max=8192, step=256, optional=True),
                io.Combo.Input("output_language", options=["English", "Chinese"], default="English", tooltip="Language for the analysis output.", optional=True),
                
                # Hidden state containing the JSON of what files are uploaded via frontend
                io.String.Input("_media_state", default="", extra_dict={"hidden": True}),
                
                # Custom prompt override containing tags
                io.String.Input("custom_prompt_override", multiline=True, default="", tooltip="Line-by-line override. Example: <Picture 2>: Overwrite prompt here", optional=True),
            ],
            outputs=[
                io.String.Output("vision_context", display_name="vision_context"),
                io.Image.Output("ref_images", display_name="ref_images"),
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
        _media_state: str = "{}"
    ) -> io.NodeOutput:
        try:
            from .response_parser import ResponseParser
            from .prompt_builder import PromptBuilder
            from .vision_orchestrator import VisionOrchestrator
            
            # --- 1. Parse media state ---
            try:
                media_data = json.loads(_media_state if _media_state else "{}")
            except Exception:
                media_data = {"media": []}
            
            media_list = media_data.get("media", [])
            
            parsed_images_for_vlm = []
            parsed_videos_for_vlm = []
            parsed_video_paths = []
            parsed_audios_for_vlm = []
            
            for entry in media_list:
                # [slot_name, {name: "path...", kind: "image"}]
                if len(entry) >= 2:
                    slot_name, data = entry[0], entry[1]
                    file_name = data.get("name", "")
                    kind = data.get("kind", "")
                    
                    if not file_name:
                        continue
                    
                    # Split path
                    parts = file_name.split('/')
                    filename = parts[-1]
                    subfolder = '/'.join(parts[:-1]) if len(parts) > 1 else ""
                    
                    full_path = get_file_path(filename, "input", subfolder)
                    
                    if not os.path.exists(full_path):
                        log_error(f"Media file not found: {full_path}")
                        continue
                        
                    if kind == "image":
                        try:
                            i = Image.open(full_path)
                            from PIL import ImageOps
                            i = ImageOps.exif_transpose(i)
                            pil_img = i.convert("RGB")
                            
                            # Save untouched original tensor for VLM and outputs
                            orig_array = np.array(pil_img).astype(np.float32) / 255.0
                            orig_tensor = torch.from_numpy(orig_array)[None,]
                            parsed_images_for_vlm.append(orig_tensor)
                        except Exception as e:
                            log_error(f"Failed to load image {full_path}: {e}")
                            
                    elif kind == "video":
                        try:
                            video_tensor = video_path_to_tensor(full_path, 4)
                            parsed_videos_for_vlm.append(video_tensor)
                            parsed_video_paths.append(full_path)
                        except Exception as e:
                            log_error(f"Failed to load video {full_path}: {e}")
                            
                    elif kind == "audio":
                        parsed_audios_for_vlm.append(full_path)
            
            # For output port:
            # Bypass `torch.cat()` and output raw list for native ComfyUI List Expansion (no deformation).
            # OUTPUT_IS_LIST = (False, True) requires out_images to always be a list (empty [] when no images loaded).
            out_images = parsed_images_for_vlm
                
            # --- 3. Run LLM Vision Analysis ---
            config_manager = get_config_manager()
            provider_key = config_manager.find_provider_by_display_name(provider)
            provider_config = config_manager.get_provider_config(provider_key)
            llm = _create_provider(provider_key, config_manager)
            
            # Backwards compat mapping
            batch_size = provider_config.get("batch_size")
            if batch_size is None:
                # If they still have boolean legacy value
                if provider_config.get("batch_vision") is False:
                    batch_size = 1
                else:
                    batch_size = 4

            if provider_key == "ollama":
                log_info("Unloading local Vision model from VRAM...")
                model_management.unload_all_models()
                model_management.soft_empty_cache()

            prompt_builder = PromptBuilder()
            system_prompt = prompt_builder.build_vision_system_prompt(output_language)
            vibe_system_prompt = prompt_builder.build_vibe_system_prompt()
            overrides = PromptBuilder.parse_overrides(custom_prompt_override)

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
            
            ref_images_dict = {}
            for i, tensor in enumerate(parsed_images_for_vlm):
                ref_images_dict[f"image_{i}"] = tensor
                
            ref_videos_dict = {}
            for i, path in enumerate(parsed_videos_for_vlm):
                ref_videos_dict[f"video_{i}"] = path
                
            ref_audios_dict = {}
            for i, path in enumerate(parsed_audios_for_vlm):
                ref_audios_dict[f"audio_{i}"] = path
                
            final_dict, media_keys = orchestrator.analyze_all(
                ref_images=ref_images_dict if len(ref_images_dict) > 0 else None,
                ref_videos=ref_videos_dict if len(ref_videos_dict) > 0 else None,
                ref_audios=ref_audios_dict if len(ref_audios_dict) > 0 else None,
                presets=PRESETS,
                overrides=overrides,
                global_image_mode=global_image_mode,
                global_video_mode=global_video_mode,
                output_language=output_language,
                batch_size=batch_size,
                provider_label=provider_key,
            )

            if not final_dict:
                return io.NodeOutput("{}", out_images)

            final_dict["_media_keys"] = media_keys
            final_output = json.dumps(final_dict, indent=4, ensure_ascii=False)

            # Debug
            print(f"\n{'-'*20} RAW ANALYZER OUTPUT {'-'*20}")
            print(final_output)
            print(f"{'-'*60}\n")

            if provider_key == "ollama":
                log_info("Re-clearing VRAM after VLM execution to free space for H3...")
                model_management.soft_empty_cache()

            return io.NodeOutput(
                final_output, 
                out_images
            )

        except Exception as e:
            log_error(str(e))
            return io.NodeOutput(f"[Analyzer Exception]: {str(e)}", [])

NODE_CLASS_MAPPINGS = {
    "H3_Vision_Analyzer": H3_Vision_Analyzer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_Vision_Analyzer": "MiniMax H3 Vision Analyzer"
}

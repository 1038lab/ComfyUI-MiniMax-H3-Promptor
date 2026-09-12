"""
ComfyUI-Minimax-H3-Promptor
Vision Node: MiniMax H3 Vision

Supports both input connectors (Autogrow) and drag/drop uploads.
Features type-scoped drag-and-drop reordering, upstream real preview resolution,
and automated trim of excess unused ports.
"""
import os
import re
import json
from PIL import Image, ImageOps
from typing import Any
import torch
import numpy as np

try:
    import folder_paths
except ImportError:
    folder_paths = None

try:
    import comfy.model_management as model_management
except ImportError:
    model_management = None

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
        class Autogrow:
            Type = Any
            @classmethod
            def Input(cls, *args, **kwargs): return None
            @classmethod
            def TemplatePrefix(cls, *args, **kwargs): return None
    io = _DummyIO()

from .config_manager import get_config_manager
from .utils import log_info, log_error, _create_provider

curr_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.dirname(curr_dir)
with open(os.path.join(root_dir, 'vision_prompts.json'), 'r', encoding='utf-8') as f:
    PRESETS = json.load(f)

IMAGE_MODES = list(PRESETS.get('image_prompts', {}).keys())
VIDEO_MODES = list(PRESETS.get('video_prompts', {}).keys())

def get_file_path(filename: str, type: str = "input", subfolder: str = "") -> str:
    """Resolve file path using comfyui's folder paths logic."""
    base_dir = folder_paths.get_input_directory() if folder_paths else "input"
    if subfolder:
        return os.path.join(base_dir, subfolder, filename)
    return os.path.join(base_dir, filename)

def video_path_to_tensor(video_path: str, max_frames: int = 4) -> Any:
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

class H3_Vision(io.ComfyNode):
    """
    MiniMax H3 Vision Node.
    Supports both input connectors (Autogrow) and drag/drop uploads.
    """
    OUTPUT_IS_LIST = (False, True)
    OUTPUT_NODE = True

    @classmethod
    def define_schema(cls) -> io.Schema:
        try:
            _config = get_config_manager().load()
            active_providers = []
            default_uuid = _config.get("defaults", {}).get("vision_provider", "")
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
            node_id="H3_Vision",
            display_name="MiniMax H3 Vision",
            category="🧪AILab/🎬 MiniMax H3-Promptor",
            is_output_node=True,
            inputs=[
                io.Combo.Input("global_image_mode", options=IMAGE_MODES, default="Subject / Identity", tooltip="Analysis focus mode for reference images (Subject, Clothing, Environment, Action, Full, Raw)."),
                io.Combo.Input("global_video_mode", options=VIDEO_MODES, default="Comprehensive", tooltip="Analysis focus mode for reference videos (Comprehensive, Motion, Audio-Visual Sync, Lighting, Camera, Character)."),
                io.Combo.Input("output_language", options=["English", "Chinese"], default="English", tooltip="Language for the analysis output and subject descriptions.", optional=True),
                io.Combo.Input("provider", options=active_providers, default=default_choice, tooltip="Vision-capable Multimodal LLM provider used to analyze images, videos, and audio.", optional=True),
                io.Float.Input("temperature", default=0.2, min=0.0, max=1.0, step=0.05, tooltip="Sampling temperature for vision analysis reasoning (0.0 = deterministic/strict, 1.0 = creative).", optional=True),
                io.Int.Input("max_tokens", default=2048, min=256, max=8192, step=256, tooltip="Maximum token limit for vision analysis response.", optional=True),
                io.Int.Input("seed", default=0, min=0, max=0xffffffffffffffff, control_after_generate="fixed", tooltip="Random seed for vision analysis (Default: Fixed Value). Click randomize or change seed to re-analyze.", optional=True),
                
                # Autogrow input connectors — pipeline connections from other nodes
                io.Autogrow.Input("ref_images", optional=True,
                                  template=io.Autogrow.TemplatePrefix(
                                      input=io.Image.Input("image", tooltip="Reference image input from pipeline (up to 9 images)"),
                                      prefix="image_", min=0, max=9)),
                io.Autogrow.Input("ref_videos", optional=True,
                                  template=io.Autogrow.TemplatePrefix(
                                      input=io.Video.Input("video", tooltip="Reference video input from pipeline (up to 3 videos)"),
                                      prefix="video_", min=0, max=3)),
                io.Autogrow.Input("ref_audios", optional=True,
                                  template=io.Autogrow.TemplatePrefix(
                                      input=io.Audio.Input("audio", tooltip="Reference audio input from pipeline (up to 3 audios)"),
                                      prefix="audio_", min=0, max=3)),
                
                # Hidden state for drag/drop upload panel & custom order
                io.String.Input("_media_state", default="", extra_dict={"hidden": True}),
                
                io.String.Input("custom_prompt_override", multiline=True, default="", tooltip="Manual prompt override for specific reference tags. E.g.: <Picture 1>: ..., <Video 1>: ...", optional=True),
            ],
            outputs=[
                io.String.Output("vision_context", display_name="VISION_CONTEXT", tooltip="Structured JSON context containing media analysis and reference tags to connect to MiniMax H3 Promptor."),
                io.Image.Output("ref_images_out", display_name="REF_IMAGES", tooltip="Batched reference images passed downstream to MiniMax Sampler."),
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
        seed: int = 0,
        ref_images: io.Autogrow.Type = None,
        ref_videos: io.Autogrow.Type = None,
        ref_audios: io.Autogrow.Type = None,
        _media_state: str = "{}",
        **kwargs
    ) -> io.NodeOutput:
        try:
            # --- 1. Map all available media by unique key (link:* or upload:*) ---
            available_images = {}
            available_videos = {}
            available_audios = {}

            # Collect from Autogrow connectors (supporting dict, list/tuple, and single tensor/path)
            if ref_images is not None:
                if isinstance(ref_images, dict):
                    for key in sorted(ref_images.keys()):
                        if ref_images[key] is not None:
                            k_name = key if key.startswith("image_") else f"image_{key}"
                            available_images[f"link:{k_name}"] = ref_images[key]
                elif isinstance(ref_images, (list, tuple)):
                    for idx, img in enumerate(ref_images):
                        if img is not None:
                            available_images[f"link:image_{idx}"] = img
                else:
                    available_images["link:image_0"] = ref_images

            if ref_videos is not None:
                if isinstance(ref_videos, dict):
                    for key in sorted(ref_videos.keys()):
                        if ref_videos[key] is not None:
                            k_name = key if key.startswith("video_") else f"video_{key}"
                            available_videos[f"link:{k_name}"] = ref_videos[key]
                elif isinstance(ref_videos, (list, tuple)):
                    for idx, vid in enumerate(ref_videos):
                        if vid is not None:
                            available_videos[f"link:video_{idx}"] = vid
                else:
                    available_videos["link:video_0"] = ref_videos

            if ref_audios is not None:
                if isinstance(ref_audios, dict):
                    for key in sorted(ref_audios.keys()):
                        if ref_audios[key] is not None:
                            k_name = key if key.startswith("audio_") else f"audio_{key}"
                            available_audios[f"link:{k_name}"] = ref_audios[key]
                elif isinstance(ref_audios, (list, tuple)):
                    for idx, aud in enumerate(ref_audios):
                        if aud is not None:
                            available_audios[f"link:audio_{idx}"] = aud
                else:
                    available_audios["link:audio_0"] = ref_audios

            for k, v in kwargs.items():
                if v is not None:
                    if k.startswith("image_"):
                        available_images[f"link:{k}"] = v
                    elif k.startswith("video_"):
                        available_videos[f"link:{k}"] = v
                    elif k.startswith("audio_"):
                        available_audios[f"link:{k}"] = v

            # Collect from upload panel (_media_state)
            try:
                media_data = json.loads(_media_state if _media_state else "{}")
            except Exception:
                media_data = {"media": [], "order": [], "linked_state": {}}

            media_list = media_data.get("media", [])
            custom_order = media_data.get("order", [])
            user_reordered = media_data.get("user_reordered", False)
            linked_state = media_data.get("linked_state", {})

            muted_keys = set()
            for entry in media_list:
                if len(entry) >= 2 and isinstance(entry[1], dict) and entry[1].get("muted"):
                    muted_keys.add(f"upload:{entry[0]}")
            for link_key, lstate in linked_state.items():
                if isinstance(lstate, dict) and lstate.get("muted"):
                    muted_keys.add(link_key)

            for entry in media_list:
                if len(entry) >= 2:
                    slot_name, data = entry[0], entry[1]
                    file_name = data.get("name", "")
                    kind = data.get("kind", "")
                    if not file_name:
                        continue

                    parts = file_name.replace('\\', '/').split('/')
                    filename = parts[-1]
                    subfolder = '/'.join(parts[:-1]) if len(parts) > 1 else ""
                    full_path = get_file_path(filename, "input", subfolder)

                    if not os.path.exists(full_path):
                        log_error(f"Media file not found: {full_path}")
                        continue

                    key = f"upload:{slot_name}"
                    if kind == "image":
                        try:
                            i = Image.open(full_path)
                            i = ImageOps.exif_transpose(i)
                            pil_img = i.convert("RGB")
                            orig_array = np.array(pil_img).astype(np.float32) / 255.0
                            orig_tensor = torch.from_numpy(orig_array)[None,] if hasattr(torch, 'from_numpy') else orig_array
                            available_images[key] = orig_tensor
                        except Exception as e:
                            log_error(f"Failed to load image {full_path}: {e}")
                    elif kind == "video":
                        try:
                            video_tensor = video_path_to_tensor(full_path, 4)
                            available_videos[key] = video_tensor
                        except Exception as e:
                            log_error(f"Failed to load video {full_path}: {e}")
                    elif kind == "audio":
                        if key not in muted_keys:
                            available_audios[key] = full_path

            # --- 2. Assemble media lists strictly respecting UI order ---
            def _assemble_ordered_media(available_dict: dict, order_list: list, is_user_reordered: bool, max_count: int) -> list:
                if not available_dict:
                    return []
                def _default_sort_key(k: str):
                    is_link = 0 if k.startswith("link:") else 1
                    num_match = re.search(r'(\d+)', k)
                    num = int(num_match.group(1)) if num_match else 999
                    return (is_link, num, k)

                all_keys = list(available_dict.keys())

                if is_user_reordered and order_list:
                    known_keys = [k for k in order_list if k in available_dict]
                    unknown_keys = [k for k in all_keys if k not in order_list]
                    unknown_keys.sort(key=_default_sort_key)
                    ordered_keys = known_keys + unknown_keys
                else:
                    all_keys.sort(key=_default_sort_key)
                    ordered_keys = all_keys

                result = []
                seen = set()
                for k in ordered_keys:
                    if k in available_dict and k not in seen and len(result) < max_count:
                        seen.add(k)
                        result.append(available_dict[k])
                return result

            parsed_images_for_vlm = _assemble_ordered_media(available_images, custom_order, user_reordered, 9)
            parsed_videos_for_vlm = _assemble_ordered_media(available_videos, custom_order, user_reordered, 3)
            # Filter muted audios before assembling
            active_audios = {k: v for k, v in available_audios.items() if k not in muted_keys}
            parsed_audios_for_vlm = _assemble_ordered_media(active_audios, custom_order, user_reordered, 3)

            out_images = parsed_images_for_vlm
                
            # --- 3. Run LLM Vision Analysis ---
            config_manager = get_config_manager()
            provider_key = config_manager.find_provider_by_display_name(provider)
            provider_config = config_manager.get_provider_config(provider_key)
            
            batch_size = provider_config.get("batch_size")
            if batch_size is None:
                batch_size = 1 if provider_config.get("batch_vision") is False else 4

            ref_images_dict = {f"image_{i}": tensor for i, tensor in enumerate(parsed_images_for_vlm)}
            ref_videos_dict = {f"video_{i}": path for i, path in enumerate(parsed_videos_for_vlm)}
            ref_audios_dict = {f"audio_{i}": path for i, path in enumerate(parsed_audios_for_vlm)}

            try:
                from .pipeline_engine import execute_vision_pipeline
                final_dict, media_keys = execute_vision_pipeline(
                    provider_name_or_key=provider_key,
                    ref_images=ref_images_dict,
                    ref_videos=ref_videos_dict,
                    ref_audios=ref_audios_dict,
                    global_image_mode=global_image_mode,
                    global_video_mode=global_video_mode,
                    output_language=output_language,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    custom_prompt_override=custom_prompt_override,
                    batch_size=batch_size,
                )

                if not final_dict:
                    return io.NodeOutput("{}", out_images)

                final_dict["_media_keys"] = media_keys
                final_output = json.dumps(final_dict, indent=4, ensure_ascii=False)
                return io.NodeOutput(final_output, out_images)
            finally:
                if model_management:
                    model_management.soft_empty_cache()

        except Exception as e:
            log_error(str(e))
            fallback_img = [torch.zeros((1, 64, 64, 3), dtype=torch.float32)] if hasattr(torch, "zeros") else []
            return io.NodeOutput(f"[Analyzer Exception]: {str(e)}", fallback_img)

NODE_CLASS_MAPPINGS = {
    "H3_Vision": H3_Vision,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_Vision": "MiniMax H3 Vision",
}

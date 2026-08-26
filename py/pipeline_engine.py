"""
ComfyUI-Minimax-H3-Promptor
Core Pipeline Engine (Single Source of Truth)

Encapsulates standard end-to-end execution for:
1. Multimodal Vision Analysis (Image/Video/Audio -> structured VISION_CONTEXT)
2. Hollywood Director Promptor (Vision Context + Scene Direction -> 3-Stage MiniMax H3 Prompt)
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from .config_manager import get_config_manager
from .prompt_builder import PromptBuilder
from .post_processor import PostProcessor
from .task_detector import TaskDetector
from .response_parser import ResponseParser
from .vision_orchestrator import VisionOrchestrator
from .provider_local_llm import LocalLLMProvider
from .utils import log_info, log_error, log_warning, _create_provider

logger = logging.getLogger("ComfyUI-Minimax-H3-Promptor")
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def execute_vision_pipeline(
    provider_name_or_key: str,
    ref_images: Optional[Dict[str, Any]] = None,
    ref_videos: Optional[Dict[str, Any]] = None,
    ref_audios: Optional[Dict[str, Any]] = None,
    global_image_mode: str = "Subject / Identity",
    global_video_mode: str = "Comprehensive",
    output_language: str = "English",
    temperature: float = 0.2,
    max_tokens: int = 2048,
    custom_prompt_override: str = "",
    batch_size: Optional[int] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Standard Vision Analysis Pipeline.
    Used by both H3_Vision node and WebUI server.
    """
    config_manager = get_config_manager()
    config = config_manager.load()

    provider_key = config_manager.find_provider_by_display_name(provider_name_or_key)
    if not provider_key:
        provider_key = provider_name_or_key if provider_name_or_key in config.get("providers", {}) else list(config.get("providers", {}).keys())[0]

    llm = _create_provider(provider_key, config_manager)
    prompt_builder = PromptBuilder()

    # Load presets
    presets_path = os.path.join(_ROOT, "vision_prompts.json")
    presets = {}
    if os.path.exists(presets_path):
        with open(presets_path, "r", encoding="utf-8") as f:
            presets = json.load(f)

    system_prompt = prompt_builder.build_vision_system_prompt(output_language)
    vibe_system_prompt = prompt_builder.build_vibe_system_prompt()
    overrides = PromptBuilder.parse_overrides(custom_prompt_override) if custom_prompt_override else {}

    orchestrator = VisionOrchestrator(
        llm=llm,
        prompt_builder=prompt_builder,
        response_parser_cls=ResponseParser,
        system_prompt=system_prompt,
        vibe_system_prompt=vibe_system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        model_override=getattr(llm, "model", ""),
    )

    # Determine batch size: Local VLM defaults to 1 (sequential focus), Cloud API defaults to 4
    is_local = getattr(llm, "type", "") in ["qwenvl", "local_llm"] or isinstance(llm, LocalLLMProvider)
    if batch_size is None:
        batch_size = 1 if is_local else 4

    final_dict, media_keys = orchestrator.analyze_all(
        ref_images=ref_images if ref_images and len(ref_images) > 0 else None,
        ref_videos=ref_videos if ref_videos and len(ref_videos) > 0 else None,
        ref_audios=ref_audios if ref_audios and len(ref_audios) > 0 else None,
        presets=presets,
        overrides=overrides,
        global_image_mode=global_image_mode,
        global_video_mode=global_video_mode,
        output_language=output_language,
        batch_size=batch_size,
        provider_label=provider_key,
    )

    return final_dict, media_keys


def execute_director_pipeline(
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
) -> Dict[str, Any]:
    """
    Standard Two-Stage Hollywood Director Pipeline.
    Used by both H3_Promptor node and WebUI server.
    """
    prompt_builder = PromptBuilder()

    # Parse reference counts
    ui_ref_images = 0 if reference_images == "Auto" else int(reference_images)
    ui_ref_videos = 0 if reference_videos == "Auto" else int(reference_videos)
    ui_ref_audios = 0 if reference_audios == "Auto" else int(reference_audios)

    image_count = ui_ref_images
    has_video = ui_ref_videos > 0
    has_audio = ui_ref_audios > 0

    parsed_vision_dict = None
    available_tags = []
    formatted_context_lines = []

    if vision_context:
        try:
            parsed_vision_dict = json.loads(vision_context) if isinstance(vision_context, str) else vision_context
            media_keys = parsed_vision_dict.get("_media_keys", [k for k in parsed_vision_dict.keys() if k.startswith("<") and k.endswith(">")])
            
            img_count = sum(1 for k in media_keys if k.startswith("<Picture"))
            vid_count = sum(1 for k in media_keys if k.startswith("<Video"))
            aud_count = sum(1 for k in media_keys if k.startswith("<Audio"))

            image_count = max(ui_ref_images, img_count)
            has_video = (ui_ref_videos > 0) or (vid_count > 0)
            has_audio = (ui_ref_audios > 0) or (aud_count > 0)

            for k in media_keys:
                v = parsed_vision_dict.get(k, "").strip()
                if v and "failed to analyze" not in v.lower():
                    formatted_context_lines.append(f"{k}: {v}")
                    available_tags.append(k)
            if has_video and "<Video 1>" not in available_tags:
                available_tags.append("<Video 1>")
            if has_audio and "<Audio 1>" not in available_tags:
                available_tags.append("<Audio 1>")

        except Exception as e:
            log_warning(f"Failed to parse vision_context JSON: {e}. Treating as raw string.")
            formatted_context_lines.append(str(vision_context))

    vision_context_str = "\n".join(formatted_context_lines)

    # 1. Detect Task Type
    detected_type = TaskDetector.detect(
        image_count=image_count,
        has_video=has_video,
        has_audio=has_audio,
        user_override=task_type
    )
    task_desc = TaskDetector.get_task_description(detected_type)

    # 2. Extract Subject Definitions
    subject_defs, valid_tags = prompt_builder.generate_subject_definitions(
        image_count, has_video=has_video, has_audio=has_audio, parsed_vision_dict=parsed_vision_dict
    )

    # 3. Instantiate Provider
    config_manager = get_config_manager()
    config = config_manager.load()
    provider_key = config_manager.find_provider_by_display_name(provider)
    if not provider_key:
        provider_key = provider if provider in config.get("providers", {}) else list(config.get("providers", {}).keys())[0]

    llm = _create_provider(provider_key, config_manager)

    # 4. STAGE 1: Blueprint & Global Vibe Planning
    stage1_sys = prompt_builder.build_blueprint_system_prompt(output_language=output_language)
    stage1_user = prompt_builder.build_blueprint_user_message(
        description=description,
        duration=duration,
        task_type=detected_type,
        vision_context=vision_context_str,
        output_language=output_language,
        image_count=image_count,
        has_video=has_video,
        parsed_vision_dict=parsed_vision_dict
    )

    res_stage1 = llm.chat(
        system_prompt=stage1_sys,
        user_message=stage1_user,
        base64_images=None,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # Frame Length calculation: max(5, round(duration * 24)) aligned to % 17 == 5
    raw_frames = max(5, round(duration * 24.0))
    rem = (raw_frames - 5) % 17
    length_frames = raw_frames if rem == 0 else (raw_frames + (17 - rem))

    if not res_stage1.success:
        err = f"[H3-Promptor Stage 1 Error] {res_stage1.error}"
        log_error(err)
        return {
            "success": False,
            "error": err,
            "final_prompt": err,
            "storyboard": "",
            "blueprint": "",
            "duration": float(duration),
            "length": length_frames,
            "task_type": detected_type,
            "task_desc": task_desc,
            "execution_logs": err,
        }

    blueprint_text = res_stage1.content

    # 5. STAGE 2: Storyboard & Dialogue Generation
    stage2_sys = prompt_builder.build_system_prompt(detected_type, duration=duration, output_language=output_language)
    stage2_user = prompt_builder.build_storyboard_user_message(
        blueprint=blueprint_text,
        description=description,
        duration=duration,
        task_type=detected_type,
        output_language=output_language,
        available_tags=available_tags if available_tags else valid_tags
    )

    res_stage2 = llm.chat(
        system_prompt=stage2_sys,
        user_message=stage2_user,
        base64_images=None,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    if not res_stage2.success:
        err = f"[H3-Promptor Stage 2 Error] {res_stage2.error}"
        log_error(err)
        return {
            "success": False,
            "error": err,
            "final_prompt": err,
            "storyboard": "",
            "blueprint": blueprint_text,
            "duration": float(duration),
            "length": length_frames,
            "task_type": detected_type,
            "task_desc": task_desc,
            "execution_logs": err,
        }

    storyboard_text = res_stage2.content

    # 6. STAGE 3: MiniMax H3 Guardrails & Post-Processing
    alignment_inst = prompt_builder.generate_alignment_instruction(detected_type, duration, image_count)
    cleaned_prompt = PostProcessor.clean(
        storyboard_text,
        detected_type,
        full_task_desc=task_desc,
        subject_defs=subject_defs,
        alignment_inst=alignment_inst,
        duration=duration,
        user_description=description,
        output_language=output_language,
    )

    logs = [
        f"✓ Task Type: {detected_type} ({task_desc})",
        f"✓ Video Duration: {duration}s -> Aligned Frames: {length_frames} (aligned % 17 == 5)",
        f"✓ Subject Definitions Extracted: {len(subject_defs.splitlines()) if subject_defs else 0}",
        f"✓ Provider Used: {getattr(llm, 'model', provider_key)}",
        f"✓ Temperature: {temperature} | Max Tokens: {max_tokens}",
        f"✓ Output Language: {output_language}",
        f"✓ MiniMax H3 Guardrails & PostProcessor Applied Successfully!"
    ]

    return {
        "success": True,
        "final_prompt": cleaned_prompt,
        "storyboard": storyboard_text,
        "blueprint": blueprint_text,
        "duration": float(duration),
        "length": length_frames,
        "task_type": detected_type,
        "task_desc": task_desc,
        "execution_logs": "\n".join(logs),
    }

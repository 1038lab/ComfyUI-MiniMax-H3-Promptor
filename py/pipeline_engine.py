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

    try:
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
    finally:
        if hasattr(llm, "unload"):
            try:
                llm.unload()
            except Exception as unload_err:
                log_warning(f"Failed to unload vision LLM: {unload_err}")


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

    try:
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
    finally:
        if hasattr(llm, "unload"):
            try:
                llm.unload()
            except Exception as unload_err:
                log_warning(f"Failed to unload promptor LLM: {unload_err}")


def execute_refine_section(section_name: str, section_content: str, instruction: str = "", provider_key: str = "", is_retry: bool = False) -> dict:
    """Core synchronous refinement engine for MiniMax H3 prompt sections."""
    import re
    if not section_content:
        return {"status": "error", "message": "section_content is empty."}

    cm = get_config_manager()
    config = cm.load()
    default_provider_key = config.get("defaults", {}).get("promptor_provider", "")
    providers = config.get("providers", {})

    chosen_key = provider_key if (provider_key and provider_key in providers) else default_provider_key
    provider_cfg = providers.get(chosen_key) if chosen_key else None
    if not provider_cfg:
        for k, v in providers.items():
            if v.get("enabled", True) is not False:
                provider_cfg = v
                chosen_key = k
                break

    if not provider_cfg:
        return {"status": "error", "message": "No LLM provider configured. Please set up a provider in settings."}

    provider = _create_provider(chosen_key, cm)

    sec_lower = section_name.lower().strip()
    is_subject = "<subject" in sec_lower or "subject" in sec_lower
    is_shot = "[shot" in sec_lower or "shot" in sec_lower
    is_summary = "summary" in sec_lower
    is_retention = "retention" in sec_lower
    is_detailed_desc = "detailed_description" in sec_lower or "integrated_multimodal_description" in sec_lower
    is_soundscape = "soundscape" in sec_lower or "ambient" in sec_lower
    is_music = "music" in sec_lower or "bgm" in sec_lower or "score" in sec_lower

    if is_subject:
        role = "MiniMax H3 Character & Prop Concept Stylist"
        target_desc = f"the visual subject definition for {section_name}"
        domain_guidelines = (
            "TASK: Refine this entity tag so the person or object has clear, tangible visual definition for video generation.\n"
            "GUIDELINES BY ENTITY TYPE:\n"
            "- For People/Characters: Retain core facial traits/hair, and enrich their attire (clothing style, color, fabric) and worn accessories/hats so the visual design is complete.\n"
            "- For Objects/Props: Detail the material, color, shape, craftsmanship, and physical surface details.\n"
            "EXAMPLE:\n"
            "Input: 'the young woman in <Picture 1>, with young woman with a pale complexion and delicate facial features, gazing softly to the side.'\n"
            "Output: 'the young woman in <Picture 1>, with a pale porcelain complexion, delicate facial features, and dark hair swept over one shoulder, wearing a high-collared crimson silk robe with white fur collar trim and embroidered sleeves, gazing softly to the side.'\n\n"
            "ABSOLUTE PROHIBITIONS (CRITICAL):\n"
            "- NEVER mention camera/photography terms (NO depth of field, bokeh, lens, angles, framing).\n"
            "- NEVER mention lighting setups (NO key light, backlight, rim light, chiaroscuro).\n"
            "- NEVER describe background environment, landscape, or scenery (those belong exclusively in Shot sections).\n"
            "- FORMAT: Output ONLY the descriptive clause starting with 'the [entity] in <Picture N>, with...'. Do NOT output '<Subject N> is' prefix."
        )
        token_limit = 2048
    elif is_shot:
        role = "Hollywood Cinematographer & Film Visual Director"
        target_desc = f"the cinematic action and camera choreography for {section_name}"
        domain_guidelines = (
            "CRITICAL TAG PRESERVATION MANDATE (SUPREME LAW):\n"
            "If the shot begins with or references source tags (e.g. 'Opening on <Video 1>, ...', '<Subject 1>', '<Picture 1>'), you MUST keep them intact! NEVER drop, delete, or rename '<Video 1>' or any reference tag.\n\n"
            "TASK: Elevate this single shot into a masterclass cinematic visual sequence.\n"
            "DIRECTIVES:\n"
            "- Camera Kinematics: Specify lens framing, perspective, and dynamic fluid movements (e.g. push-in, orbital pan, tracking, tilt).\n"
            "- Lighting & Atmosphere: Describe atmospheric god-rays, rim light, shadow contrast, weather, or volumetric haze.\n"
            "- Physical Micro-Actions: Sharpen tangible character reactions, physical kinetics, and pacing.\n"
            "EXAMPLE:\n"
            "Input: 'Opening on <Video 1>, an elderly sage sits cross-legged at the precipice of an ancient cliff, eyes closed, palms resting on his knees. Heavy snowfall drifts through volumetric god-rays. The camera executes a slow push-in.'\n"
            "Output: 'Opening on <Video 1>, an elderly sage sits cross-legged at the sheer precipice of an ancient cliff, eyes closed in deep meditation, palms resting serenely upon his knees. Heavy snowfall drifts in parallax layers through volumetric god-rays piercing bruised clouds. The camera executes a slow, deliberate push-in over 2.8 seconds, shallow depth of field isolating his tranquil expression as a faint plume of breath escapes his lips.'\n\n"
            "CRITICAL FORMAT & INVARIANCE RULES (STRICT & ABSOLUTE):\n"
            "- TIMESTAMPS: If the input shot contains timestamps (e.g. 'At 00:00.000', 'At 00:02.500'), you MUST preserve the timestamp verbatim at the start of the camera movement. NEVER omit, alter, or remove timestamps.\n"
            "- ALIGNMENT DIRECTIVES: If the input starts with a parenthesized reference directive (e.g. '(Begins exactly matching the composition, lighting, and pose of <Picture 1>, then narrating the continuous forward motion)'), PRESERVE it VERBATIM in its parentheses on its own line preceding the timestamp.\n"
            "- Output ONLY the refined shot body (including any alignment clause, timestamp, and camera prose). Do NOT add outer shot number brackets (e.g. '[Shot 1]').\n"
            "- Preserve all reference tokens (<Video 1>, <Picture 1>, <Subject 1>, etc.) exactly."
        )
        token_limit = 2048
    elif is_summary:
        role = "MiniMax H3 Screenplay Narrative Editor"
        target_desc = "the video narrative summary logline"
        domain_guidelines = (
            "TASK: Polish the high-level video logline into a compelling, 1-2 sentence narrative summary.\n"
            "EXAMPLE:\n"
            "Input: '[reference generation] A monk sits on a mountain during winter.'\n"
            "Output: '[reference generation] An ancient sage meditates atop a frozen alpine cliff, confronting the shifting mountain storm in profound spiritual isolation.'\n\n"
            "RULES:\n"
            "- Must preserve '[reference generation]' or '[text generation]' prefix.\n"
            "- Output exactly 1 to 2 concise sentences (approx 20 to 45 words). Single line only. NEVER list individual shots."
        )
        token_limit = 2048
    elif is_retention:
        role = "MiniMax H3 Multimodal Reference Tracking Specialist"
        target_desc = "the reference retention analysis"
        domain_guidelines = (
            "TASK: Standardize the multimodal reference retention statements.\n"
            "EXAMPLE:\n"
            "Input: '<Picture 1>: kept. <Video 1>: mountain kept.'\n"
            "Output: '<Picture 1> (Young Woman): High preservation — delicate facial traits, hair, and crimson robe design maintained.\n<Video 1> (Alpine Mountain): Medium preservation — cliff top geometry and heavy snow atmosphere retained.'\n\n"
            "RULES:\n"
            "- Preserve EVERY reference tag entry (<Subject N>, <Video N>, <Audio N>). Keep the exact same set of tags.\n"
            "- Each item MUST be on its own line: '<Tag> (details): [preservation level] - [reason] maintained.'\n"
            "- Clean list format only."
        )
        token_limit = 2048
    elif is_detailed_desc:
        role = "MiniMax H3 Lead Cinematographer & Multi-Shot Director"
        target_desc = "the full chronological multi-shot sequence in detailed_description"
        domain_guidelines = (
            "TASK: Polish and harmonize the full chronological multi-shot sequence.\n"
            "RULES (CRITICAL & ABSOLUTE):\n"
            "- Preserve EVERY shot header and timestamp EXACTLY as written (e.g. '[Shot 1 — 00:00.000 to 00:02.800]'). NEVER change timestamp numbers, NEVER merge shots, and NEVER add or delete shots.\n"
            "- Elevate camera kinematics, volumetric lighting, and physical continuity across all shots.\n"
            "- Keep each shot as a single, vivid cinematic paragraph."
        )
        token_limit = 4096
    elif is_soundscape:
        role = "MiniMax H3 Foley & Sound Designer"
        target_desc = "the environmental soundscape description"
        domain_guidelines = (
            "TASK: Describe the environmental soundscape and physical diegetic Foley.\n"
            "EXAMPLE:\n"
            "Input: 'Wind blows and snow falls.'\n"
            "Output: 'Subtle whistling alpine wind whipping across sheer rock faces, accompanied by the muffled patter of heavy snowflakes landing on frozen stone and the rustling of coarse wool robes.'\n\n"
            "RULES:\n"
            "- Describe ONLY environmental acoustics and physical Foley sounds (wind, footsteps, cloth rustle, water, weather).\n"
            "- NEVER describe musical instruments, melodic score, or BGM (music belongs strictly in non_diegetic_music).\n"
            "- Output 1 to 2 sentences (single line, approx 20 to 45 words)."
        )
        token_limit = 2048
    elif is_music:
        role = "MiniMax H3 Score Composer & Music Supervisor"
        target_desc = "the musical score description"
        domain_guidelines = (
            "TASK: Describe the non-diegetic musical score and soundtrack.\n"
            "EXAMPLE:\n"
            "Input: 'Sad slow music.'\n"
            "Output: 'A slow-tempo cinematic orchestral score featuring sustained solitary cello lines, ethereal drone pads, and subtle low percussion, creating an atmosphere of ancient solitude.'\n\n"
            "RULES:\n"
            "- Describe ONLY the musical instrumentation, genre, tempo (BPM), and emotional progression.\n"
            "- NEVER describe physical Foley or environment noises (wind, steps, snow belong strictly in overall_soundscape).\n"
            "- Output 1 to 2 sentences (single line, approx 20 to 45 words)."
        )
        token_limit = 2048
    else:
        role = "MiniMax H3 Master Prompt Architect & Film Director"
        target_desc = "the entire MiniMax H3 video prompt"
        domain_guidelines = (
            "TASK: Refine the entire multi-section MiniMax H3 video prompt with professional cinematic quality.\n"
            "ARCHITECTURAL INVARIANTS (STRICT & ABSOLUTE):\n"
            "1. Headlines: Preserve ALL section headlines ('subject_definitions:', 'summary:', 'retention_analysis:', 'detailed_description:', 'overall_soundscape:', 'non_diegetic_music:') exactly on their own lines.\n"
            "2. Subjects: Maintain the exact same set of subjects (<Subject 1>, <Subject 2>, etc.). Describe ONLY their physical appearance and clothing (NO camera, NO lighting in subject tags).\n"
            "3. Shots: Maintain the exact same set of shots and chronological timestamp windows. Elevate camera kinematics, lighting, and action pacing smoothly.\n"
            "4. Audio: Keep soundscape (diegetic noise) and music (soundtrack) strictly separated."
        )
        token_limit = 4096

    user_rev = f"User Revision Goal: {instruction}\n" if instruction else ""

    system_prompt = (
        f"You are an elite {role}.\n"
        f"Your task is to refine and elevate {target_desc}.\n\n"
        "SUPREME LAWS (ABSOLUTE & INVIOLABLE):\n"
        "1. MULTIMODAL TAG INTEGRITY:\n"
        "   Reference tags (<Video N>, <Picture N>, <Subject N>, <Audio N>, (SN), <d>...</d>) are the MULTIMODAL ANCHORS that bind generated video to user media.\n"
        "   - You MUST preserve EVERY reference tag present in the original text EXACTLY as written.\n"
        "   - NEVER delete, rename, skip, or modify any reference tag under any circumstance.\n"
        "2. TIMESTAMPS & TIMELINE INVARIANCE (CRITICAL):\n"
        "   Timestamps (e.g. 'At 00:00.000', 'At 00:01.250') are strict chronological keyframes for video generation.\n"
        "   - You MUST preserve every timestamp present in the original text EXACTLY as written at the start of the camera movement.\n"
        "   - NEVER delete, shift, or omit any timestamp.\n"
        "3. CHARACTER RELATIONSHIPS & ACTION INVARIANCE (CRITICAL):\n"
        "   When multiple tags exist in a scene (e.g. <Picture 1>, <Picture 2>, <Subject 1>, <Subject 2>), their semantic relationship and action causality MUST remain 100% faithful to the original text.\n"
        "   - NEVER swap character roles, identities, or actions (e.g. if <Picture 1> offers an apple to <Picture 2>, NEVER invert it so that <Picture 2> gives it to <Picture 1>).\n"
        "   - Refinement means polishing physical kinetics, lens framing, lighting, and micro-expressions—NEVER fabricating a different storyline or reversing who does what to whom.\n\n"
        f"{domain_guidelines}\n\n"
        "OUTPUT RULE:\n"
        "Output ONLY the refined prompt text. No chit-chat, explanations, or code fences (```)."
    )

    if is_retry:
        user_rev += "Creative Variation: Provide a fresh cinematic variation with dynamic visual details while preserving structural integrity.\n"

    # Detect all mandatory multimodal tags and timestamps from source content to enforce zero-loss invariance
    mandatory_tags = re.findall(r'<(?:Video|Picture|Subject|Audio)\s+\d+>|\(S(?:[1-9]|1\d|20)\)|<d>[\s\S]*?<\/d>|\bAt\s+\d{2}:\d{2}\.\d{3}\b', section_content, flags=re.IGNORECASE)
    unique_tags = list(dict.fromkeys(mandatory_tags))
    if unique_tags:
        tags_str = ", ".join(unique_tags)
        user_rev += f"[MANDATORY REFERENCE TAGS & TIMESTAMPS]\nThe following reference tags and timestamps MUST be preserved verbatim in your refined text: {tags_str}. Never drop, omit, or alter any of these tags or timestamps under any circumstance.\n"

    user_message = f"{user_rev}Content to refine:\n{section_content}"

    try:
        resp = provider.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=token_limit,
            temperature=0.8 if is_retry else 0.7,
        )
    finally:
        if hasattr(provider, "unload"):
            try:
                provider.unload()
            except Exception:
                pass

    if not resp.success:
        return {"status": "error", "message": resp.error or "LLM call failed."}

    refined_text = resp.content.strip()
    if refined_text.startswith("```"):
        refined_text = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", refined_text)
        refined_text = re.sub(r"\n```$", "", refined_text).strip()

    # Clean prefixes and markdown formatting
    if is_subject:
        refined_text = re.sub(r'^(?:<Subject\s+\d+>\s*(?:is\s+|:\s*|-+\s*)?)+', '', refined_text, flags=re.IGNORECASE).strip()
        refined_text = re.sub(r'\s*\n+\s*', ' ', refined_text).strip()
        refined_text = re.sub(r'\*\*|__', '', refined_text).strip()
        # Defensive strip of accidental trailing photography/lighting/scene leaks
        refined_text = re.sub(r',\s*(?:all\s+)?(?:wrapped\s+in|with\s+)?(?:a\s+)?(?:faint\s+|shallow\s+)?(?:bokeh|depth\s+of\s+field|key\s+light|rim\s+light|cinematic\s+lighting|chiaroscuro)[^.]*', '', refined_text, flags=re.IGNORECASE).strip()
        refined_text = re.sub(r'\b(?:bokeh|depth\s+of\s+field|chiaroscuro|key\s+light|rim\s+light)\b', '', refined_text, flags=re.IGNORECASE).strip()

    if is_shot:
        # Strip accidental duplicate shot headers
        refined_text = re.sub(r'^\[Shot\s+\d+[^\]]*\]\s*', '', refined_text, flags=re.IGNORECASE).strip()
        refined_text = re.sub(r'^\*\*[^*]+\*\*:\s*', '', refined_text).strip()
        refined_text = re.sub(r'\*\*|__', '', refined_text).strip()

        # Deterministic Alignment Directive Guard: Preserve parenthesized reference directives (e.g. (Begins...))
        paren_dir_match = re.search(r'(\([^\)]*<Picture\s+\d+>[^\)]*\))', section_content, flags=re.IGNORECASE)
        if paren_dir_match:
            paren_text = paren_dir_match.group(1).strip()
            if paren_text not in refined_text:
                clean_inner = paren_text[1:-1].strip()
                if re.search(re.escape(clean_inner), refined_text):
                    refined_text = re.sub(re.escape(clean_inner) + r'[.,;]?\s*', f"{paren_text}\n", refined_text, count=1)
                else:
                    refined_text = f"{paren_text}\n{refined_text}"

        # Deterministic Timestamp Guard: Ensure 'At 00:XX.XXX' timestamp is never dropped
        time_match = re.search(r'\b(At\s+\d{2}:\d{2}\.\d{3})\b', section_content, flags=re.IGNORECASE)
        if time_match:
            ts_str = time_match.group(1)
            if not re.search(re.escape(ts_str), refined_text, flags=re.IGNORECASE):
                if paren_dir_match and paren_dir_match.group(1) in refined_text:
                    p = paren_dir_match.group(1)
                    refined_text = re.sub(re.escape(p) + r'\s*', f"{p}\n{ts_str} ", refined_text, count=1)
                else:
                    refined_text = f"{ts_str} {refined_text.lstrip()}"
            else:
                if paren_dir_match and paren_dir_match.group(1) in refined_text:
                    p = paren_dir_match.group(1)
                    refined_text = re.sub(re.escape(p) + r'\s*' + re.escape(ts_str), f"{p}\n{ts_str}", refined_text, count=1)

        # Deterministic Tag Guard: Ensure 'Opening on <Video N>' is never dropped
        opening_match = re.search(r'Opening\s+on\s+(<Video\s+\d+>)', section_content, flags=re.IGNORECASE)
        if opening_match:
            v_tag = opening_match.group(1)
            if not re.search(re.escape(v_tag), refined_text, flags=re.IGNORECASE):
                refined_text = re.sub(r'^(?:Opening\s+on\s*,?\s*)+', '', refined_text, flags=re.IGNORECASE).lstrip(', ')
                refined_text = f"Opening on {v_tag}, {refined_text}"

    if is_summary:
        refined_text = re.sub(r'\s*\n+\s*', ' ', refined_text).strip()
        refined_text = re.sub(r'\*\*|__', '', refined_text).strip()
        if section_content.strip().startswith("[reference generation]") and not refined_text.startswith("[reference generation]"):
            refined_text = "[reference generation] " + refined_text
        elif section_content.strip().startswith("[text generation]") and not refined_text.startswith("[text generation]"):
            refined_text = "[text generation] " + refined_text

    if is_retention or is_detailed_desc:
        refined_text = re.sub(r'\*\*|__', '', refined_text).strip()

    # Universal Multimodal Reference Tag Protection Guard
    # Scans for all <Video N>, <Picture N>, <Subject N>, <Audio N> tags and restores any omitted tag
    ref_tags = re.findall(r'<(?:Video|Picture|Subject|Audio)\s+\d+>', section_content, flags=re.IGNORECASE)
    for tag in list(dict.fromkeys(ref_tags)):
        if not re.search(re.escape(tag), refined_text, flags=re.IGNORECASE):
            # Deterministic lossless recovery
            if is_subject and "<picture" in tag.lower():
                if not re.search(r'<Picture\s+\d+>', refined_text, flags=re.IGNORECASE):
                    ent_match = re.search(rf'(the\s+[^,]+?\s+in\s+{re.escape(tag)})', section_content, flags=re.IGNORECASE)
                    if ent_match:
                        refined_text = re.sub(r'^(?:the\s+[^,]+,?\s*with\s+)?', f'{ent_match.group(1)}, with ', refined_text, count=1, flags=re.IGNORECASE)
                    else:
                        refined_text = re.sub(r'^(?:the\s+[^,]+,?\s*with\s+)?', f'the entity in {tag}, with ', refined_text, count=1, flags=re.IGNORECASE)
            elif is_shot or is_detailed_desc:
                if "<video" in tag.lower():
                    if re.search(rf'Opening\s+on\s+{re.escape(tag)}', section_content, flags=re.IGNORECASE):
                        refined_text = f"Opening on {tag}, {refined_text}"
                    else:
                        refined_text = f"{refined_text} (aligned with {tag})"
                elif "<picture" in tag.lower():
                    if re.search(rf'Begins?\s+from\s+[^,.]*?{re.escape(tag)}', section_content, flags=re.IGNORECASE):
                        refined_text = f"Begins from the composition of {tag}, {refined_text}"
                    elif re.search(rf'Concludes?\s+[^,.]*?{re.escape(tag)}', section_content, flags=re.IGNORECASE):
                        refined_text = f"{refined_text.rstrip('.')} while settling seamlessly into {tag}."
                    else:
                        refined_text = f"Featuring {tag}, {refined_text}"
                elif "<subject" in tag.lower():
                    refined_text = f"Focusing on {tag}, {refined_text}"
                elif "<audio" in tag.lower():
                    refined_text = f"{refined_text} (synchronized with {tag})"
            else:
                refined_text = f"{refined_text} (featuring {tag})"

    # Sanitize accidental double brackets like [Shot 1: [00:00.000 -> [Shot 1: 00:00.000
    refined_text = re.sub(r'\[(Shot\s+\d+:\s*)\[', r'[\1', refined_text)

    return {"status": "success", "refined": refined_text}

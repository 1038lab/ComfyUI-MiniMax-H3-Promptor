"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

from .config_manager import get_config_manager
from .task_detector import TASK_TYPE_OPTIONS, TaskDetector
from .prompt_builder import PromptBuilder
from .post_processor import PostProcessor
from .utils import log_info, log_error, _create_provider


from .config_manager import get_config_manager

class H3_Promptor:

    def __init__(self):
        self.prompt_builder = PromptBuilder()

    @classmethod
    def INPUT_TYPES(s):
        try:
            _config = get_config_manager().load()
            active_providers = []
            default_uuid = _config.get("defaults", {}).get("promptor_provider", "")
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

        return {
            "required": {
                "task_type": (TASK_TYPE_OPTIONS, {
                    "default": TASK_TYPE_OPTIONS[0],
                    "tooltip": "Forces the H3 prompt format (Text-to-Video, Image-to-Video, etc.)"
                }),
                "description": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Your main creative description of the scene.",
                }),
                "duration": ("FLOAT", {
                    "default": 5, "min": 4, "max": 15, "step": 0.5,
                    "tooltip": "Vaild duration for Minimax H3 is 4-15 seconds.",
                }),
            },
            "optional": {
                "vision_context": ("STRING", {
                    "multiline": True,
                    "forceInput": True,
                    "default": "",
                    "tooltip": "Connect the output from H3_Vision_Analyzer here.",
                }),
                "reference_images": (["Auto", "1", "2", "3", "4", "5", "6", "7", "8", "9"], {
                    "default": "Auto",
                    "tooltip": "Auto uses Vision Analyzer count. Otherwise manually set how many images are connected to Minimax (max 9).",
                }),
                "reference_videos": (["Auto", "1", "2", "3"], {
                    "default": "Auto",
                    "tooltip": "Auto uses Vision Analyzer count. Otherwise manually set how many videos are connected (max 3).",
                }),
                "reference_audios": (["Auto", "1", "2", "3"], {
                    "default": "Auto",
                    "tooltip": "Auto uses Vision Analyzer count. Otherwise manually set how many audio files are connected (max 3).",
                }),
                "output_language": (["English", "Chinese"], {
                    "default": "English",
                    "tooltip": "The language the Minimax H3 system will receive the prompt in."
                }),
                "provider": (active_providers, {
                    "default": default_choice,
                    "tooltip": "LLM provider to use for text generation.",
                }),
                "temperature": ("FLOAT", {
                    "default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05
                }),
                "max_tokens": ("INT", {
                    "default": 4096, "min": 256, "max": 8192, "step": 256
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "generate_prompt"
    CATEGORY = "🧪AILab/🎬 MiniMax H3-Promptor"

    def generate_prompt(
        self,
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
        try:
            # Parse intelligent Auto media signature if present
            ui_ref_images = 0 if reference_images == "Auto" else int(reference_images)
            ui_ref_videos = 0 if reference_videos == "Auto" else int(reference_videos)
            ui_ref_audios = 0 if reference_audios == "Auto" else int(reference_audios)
            
            image_count = ui_ref_images
            has_video = ui_ref_videos > 0
            has_audio = ui_ref_audios > 0
            
            parsed_vision_dict = None
            available_tags = []
            if vision_context:
                import json
                try:
                    parsed_vision_dict = json.loads(vision_context)
                    media_keys = parsed_vision_dict.get("_media_keys", [])
                    img_count = sum(1 for k in media_keys if k.startswith("<Picture"))
                    vid_count = sum(1 for k in media_keys if k.startswith("<Video"))
                    aud_count = sum(1 for k in media_keys if k.startswith("<Audio"))
                    
                    image_count = max(ui_ref_images, img_count)
                    has_video = (ui_ref_videos > 0) or (vid_count > 0)
                    has_audio = (ui_ref_audios > 0) or (aud_count > 0)
                        
                    formatted_context = []
                    for k in media_keys:
                        v = parsed_vision_dict.get(k, "").strip()
                        if v and "failed to analyze" not in v.lower():
                            formatted_context.append(f"{k}: {v}")
                            available_tags.append(k)
                    if has_video: available_tags.append("<Video 1>")
                    if has_audio: available_tags.append("<Audio 1>")
                    vision_context = "\n".join(formatted_context)
                
                except json.JSONDecodeError:
                    log_error("H3_Promptor: Failed to parse vision_context as JSON. Treating as raw string.")

            # 1. Detect Task Type
            detected_type = TaskDetector.detect(
                image_count=image_count,
                has_video=has_video,
                has_audio=has_audio,
                user_override=task_type
            )
            task_desc = TaskDetector.get_task_description(detected_type)
            
            # 2. Get LLM provider
            config_manager = get_config_manager()
            provider_key = config_manager.find_provider_by_display_name(provider)
            llm = _create_provider(provider_key, config_manager)

            print(f"\n" + "="*80)
            print(f"🎬 [H3-PROMPTOR] STARTING TWO-STAGE DIRECTING PIPELINE")
            print(f"• Task Mode: {detected_type} ({task_desc}) | Target Duration: {duration:0.1f}s | Lang: {output_language}")
            print(f"• Provider: {provider_key} ({llm.model}) | Media: {image_count} Image(s), Video: {has_video}, Audio: {has_audio}")
            print("="*80)

            # ==========================================================
            # STAGE 1: Blueprint & Global Vibe Planning
            # ==========================================================
            print(f"\n{'='*25} [STAGE 1/2] DIRECTING BLUEPRINT & GLOBAL VIBE {'='*25}")
            stage1_sys = self.prompt_builder.build_blueprint_system_prompt(output_language=output_language)
            stage1_user = self.prompt_builder.build_blueprint_user_message(
                description=description,
                duration=duration,
                task_type=detected_type,
                vision_context=vision_context,
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
                max_tokens=1024,
            )

            if not res_stage1.success:
                err = f"[H3-Promptor Stage 1 Error] {res_stage1.error}"
                log_error(err)
                return (err,)

            blueprint_text = res_stage1.content
            print(blueprint_text)
            print("="*80)

            # ==========================================================
            # STAGE 2: Cinematic Storyboard Generation
            # ==========================================================
            print(f"\n{'='*25} [STAGE 2/2] CINEMATIC STORYBOARD & DIALOGUE {'='*25}")
            stage2_sys = self.prompt_builder.build_system_prompt(detected_type, duration=duration, output_language=output_language)
            stage2_user = self.prompt_builder.build_storyboard_user_message(
                blueprint=blueprint_text,
                description=description,
                duration=duration,
                task_type=detected_type,
                output_language=output_language,
                available_tags=available_tags
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
                return (err,)

            print(res_stage2.content)
            print("="*80)

            # ==========================================================
            # STAGE 3: Deterministic Post-Processing & Official Assembly
            # ==========================================================
            subject_defs, valid_tags = self.prompt_builder.generate_subject_definitions(
                image_count, has_video=has_video, has_audio=has_audio, parsed_vision_dict=parsed_vision_dict
            )
            alignment_inst = self.prompt_builder.generate_alignment_instruction(detected_type, duration, image_count)

            cleaned_prompt = PostProcessor.clean(
                res_stage2.content, 
                detected_type, 
                full_task_desc=task_desc,
                subject_defs=subject_defs,
                alignment_inst=alignment_inst,
                duration=duration
            )

            print(f"\n{'#'*25} [FINAL ASSEMBLED MINIMAX PROMPT] {'#'*25}")
            print(cleaned_prompt)
            print("#"*80 + "\n")

            return (cleaned_prompt,)

        except Exception as e:
            error_msg = f"[H3-Promptor Error] {str(e)}"
            log_error(str(e))
            return (error_msg,)

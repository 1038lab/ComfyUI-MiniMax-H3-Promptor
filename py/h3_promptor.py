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
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ):
        """Generate a MiniMax H3 structured prompt."""
        try:
            # Parse intelligent Auto media signature if present
            # Convert UI string values back to integers, treating "Auto" as 0 internally for fallback
            ui_ref_images = 0 if reference_images == "Auto" else int(reference_images)
            ui_ref_videos = 0 if reference_videos == "Auto" else int(reference_videos)
            ui_ref_audios = 0 if reference_audios == "Auto" else int(reference_audios)
            
            image_count = ui_ref_images
            has_video = ui_ref_videos > 0
            has_audio = ui_ref_audios > 0
            
            parsed_vision_dict = None
            if vision_context:
                import json
                try:
                    parsed_vision_dict = json.loads(vision_context)
                    
                    # Update media counts based on Dictionary keys
                    media_keys = parsed_vision_dict.get("_media_keys", [])
                    img_count = sum(1 for k in media_keys if k.startswith("<Picture"))
                    vid_count = sum(1 for k in media_keys if k.startswith("<Video"))
                    aud_count = sum(1 for k in media_keys if k.startswith("<Audio"))
                    
                    # Automatically use the maximum value: allows partial vision analysis (e.g. 3 analyzed) 
                    # while keeping remaining images (e.g. 6 total) as empty visual anchors for the H3 model
                    image_count = max(ui_ref_images, img_count)
                    has_video = (ui_ref_videos > 0) or (vid_count > 0)
                    has_audio = (ui_ref_audios > 0) or (aud_count > 0)
                        
                    # Format vision context back into a readable string for the Prompt LLM context
                    formatted_context = []
                    for k, v in parsed_vision_dict.items():
                        if k != "_media_keys":
                            formatted_context.append(f"{k}: {v}")
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
            
            log_info(f"Task type: {TaskDetector.get_task_description(detected_type)}")

            # 4. Generate system and user prompts
            system_prompt = self.prompt_builder.build_system_prompt(detected_type, duration=duration, output_language=output_language)
            
            user_message = self.prompt_builder.build_user_message(
                description, duration, detected_type, vision_context=vision_context, output_language=output_language,
                image_count=image_count, has_video=has_video
            )

            # 4. Get LLM provider
            config_manager = get_config_manager()
            provider_key = config_manager.find_provider_by_display_name(provider)
            llm = _create_provider(provider_key, config_manager)

            log_info(
                f"Calling {provider_key} | "
                f"model={llm.model} | "
                f"temp={temperature}"
            )

            # NOTE: We NO LONGER send images here (base64_images=None) because it's already in the text context.
            response = llm.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                base64_images=None,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if not response.success:
                error_msg = f"[H3-Promptor Error] {response.error}"
                log_error(response.error)
                return (error_msg,)
                
            # Log raw response to console for user debugging
            print(f"\n{'-'*20} RAW PROMPTOR OUTPUT {'-'*20}")
            print(response.content)
            print(f"{'-'*60}\n")

            # 6. Post-process
            task_desc = TaskDetector.get_task_description(detected_type)
            
            # Dynamically compute subject definitions and alignment strings in Python
            subject_defs = self.prompt_builder.generate_subject_definitions(image_count, has_video, has_audio, parsed_vision_dict=parsed_vision_dict)
            alignment_inst = self.prompt_builder.generate_alignment_instruction(detected_type, duration, image_count)
            
            cleaned_prompt = PostProcessor.clean(
                response.content, 
                detected_type, 
                full_task_desc=task_desc,
                subject_defs=subject_defs,
                alignment_inst=alignment_inst
            )
            log_info(
                f"Prompt generated: {len(cleaned_prompt)} chars | "
                f"model={response.model} | "
                f"tokens={response.usage.get('total_tokens', '?')}"
            )

            return (cleaned_prompt,)

        except Exception as e:
            error_msg = f"[H3-Promptor Error] {str(e)}"
            log_error(str(e))
            return (error_msg,)

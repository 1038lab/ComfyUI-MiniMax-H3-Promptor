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
from .provider_openai import OpenAIProvider
from .provider_ollama import OllamaProvider
from .provider_lmstudio import LMStudioProvider
from .provider_gemini import GeminiProvider
from .provider_claude import ClaudeProvider
from .utils import log_info, log_error


# Provider options
PROVIDERS = ["openai", "ollama", "lmstudio", "gemini", "claude"]


def _create_provider(provider_name: str, config_manager, api_key_override: str = ""):
    """Create an LLM provider instance from config."""
    provider_config = config_manager.get_provider_config(provider_name)
    if not provider_config:
        raise ValueError(f"Provider '{provider_name}' not configured.")

    api_base = provider_config.get("api_base", "")
    api_key = api_key_override or provider_config.get("api_key", "")
    model = provider_config.get("default_model", "")

    if provider_name == "ollama":
        return OllamaProvider(api_base=api_base, model=model)
    elif provider_name == "lmstudio":
        return LMStudioProvider(api_base=api_base, model=model)
    elif provider_name == "gemini":
        return GeminiProvider(api_base=api_base, api_key=api_key, model=model)
    elif provider_name == "claude":
        return ClaudeProvider(api_base=api_base, api_key=api_key, model=model)
    else:
        return OpenAIProvider(api_base=api_base, api_key=api_key, model=model)


class H3_Promptor:
    """
    MiniMax H3 Prompt Generator

    Full-featured text-based prompt generator optimized 
    for fast API calls using pre-computed vision context.
    """

    def __init__(self):
        self.prompt_builder = PromptBuilder()

    @classmethod
    def INPUT_TYPES(s):
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
                "duration": ("INT", {
                    "default": 5, "min": 4, "max": 15, "step": 1,
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
                "output_language": (["English", "Chinese"], {
                    "default": "English",
                    "tooltip": "The language the Minimax H3 system will receive the prompt in."
                }),
                "provider": (PROVIDERS, {
                    "default": "openai",
                    "tooltip": "LLM provider to use for text generation.",
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "tooltip": "API key override.",
                }),
                "model_name": ("STRING", {
                    "default": "",
                    "tooltip": "Model override. For Ollama/LM Studio, a searchable dropdown appears when that provider is selected.",
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
        duration: int,
        vision_context: str = "",
        output_language: str = "English",
        provider: str = "openai",
        api_key: str = "",
        model_name: str = "",
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ):
        """Generate a MiniMax H3 structured prompt."""
        try:
            # Parse intelligent Auto media signature if present
            image_count = 0
            has_video = False
            
            if vision_context and "[MEDIA_SIGNATURE:" in vision_context:
                import re
                match = re.search(r"\[MEDIA_SIGNATURE:\s*(.*?)\]", vision_context)
                if match:
                    tags = match.group(1).split()
                    image_count = sum(1 for t in tags if t.startswith("IMG"))
                    has_video = "VID" in tags
                    
                # Strip the signature so the LLM doesn't see our internal routing tag
                vision_context = re.sub(r"\[MEDIA_SIGNATURE:.*?\]\n", "", vision_context).strip()

            # 1. Detect Task Type
            detected_type = TaskDetector.detect(
                image_count=image_count,
                has_video=has_video,
                user_override=task_type
            )
            
            log_info(f"Task type: {TaskDetector.get_task_description(detected_type)}")

            # 4. Generate system and user prompts
            system_prompt = self.prompt_builder.build_system_prompt(detected_type)
            
            user_message = self.prompt_builder.build_user_message(
                description, duration, detected_type, vision_context=vision_context, output_language=output_language
            )

            # 4. Get LLM provider
            config_manager = get_config_manager()
            llm = _create_provider(provider, config_manager, api_key)

            # 5. Call LLM (with overrides)
            model_override = model_name if model_name.strip() else None
            log_info(
                f"Calling {provider} | "
                f"model={model_override or llm.model} | "
                f"temp={temperature}"
            )

            # NOTE: We NO LONGER send images here (base64_images=None) because it's already in the text context.
            response = llm.chat(
                system_prompt=system_prompt,
                user_message=user_message,
                base64_images=None,
                temperature=temperature,
                max_tokens=max_tokens,
                model=model_override,
            )

            if not response.success:
                error_msg = f"[H3-Promptor Error] {response.error}"
                log_error(response.error)
                return (error_msg, f"Error: {detected_type}")
                
            # Log raw response to console for user debugging
            print(f"\n{'-'*20} RAW PROMPTOR OUTPUT {'-'*20}")
            print(response.content)
            print(f"{'-'*60}\n")

            # 6. Post-process
            task_desc = TaskDetector.get_task_description(detected_type)
            cleaned_prompt = PostProcessor.clean(response.content, detected_type, full_task_desc=task_desc)
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

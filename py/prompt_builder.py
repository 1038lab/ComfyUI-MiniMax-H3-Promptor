"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
"""

from pathlib import Path
from .utils import log_info, log_error, log_debug


# Templates directory
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class PromptBuilder:
    """Build system prompts and user messages for H3 prompt generation."""

    def __init__(self, templates_dir: str | Path | None = None):
        self.templates_dir = Path(templates_dir) if templates_dir else _TEMPLATES_DIR

    def build_system_prompt(
        self,
        task_type: str,
        template_override: str | None = None,
        duration: float = 5.0,
        output_language: str = "English",
    ) -> str:
        """
        Assemble the complete system prompt from template files.
        """
        parts = []

        if output_language.lower() == "chinese":
            parts.append("CRITICAL: You MUST write the ENTIRE OUTPUT PROMPT in Simplified Chinese (简体中文). Ignore any English templates below, they are just structure references.")
        else:
            parts.append("CRITICAL: You MUST write the ENTIRE OUTPUT PROMPT in English.")

        base = self._load_template("system_base.txt")
        if base:
            # Inject budget based on duration and task type complexity
            if task_type in ["Ref2VA", "I2VA", "V2VA", "V2V"]:
                # Reference-heavy modes usually require 350-500 words
                budget = max(350, int(duration * 30))
            else:
                # Base estimation: ~25 words per second
                budget = int(duration * 25)
            
            budget_str = f"Word Budget Constraint: Approximately {budget} English words. Prioritize action over fluff."
            parts.append(f"{base}\n\n{budget_str}")
        else:
            parts.append(self._fallback_base())

        if template_override and template_override != "default":
            task_template = self._load_template(template_override)
            if not task_template:
                task_template = self._load_template(f"{task_type.lower()}.txt")
        else:
            task_template = self._load_template(f"{task_type.lower()}.txt")
        
        if task_template:
            parts.append(task_template)

        return "\n\n".join(parts)

    def generate_alignment_instruction(self, task_type: str, duration: float, image_count: int) -> str:
        """
        Produce mathematically precise alignment strings for FL2VA, I2VA, and L2VA.
        S.SS is floored based on the 17k+5 frame grid to ensure it doesn't fall off the edge.
        """
        # Using the formula from minimax_plan.py
        s = "%.2f" % (int(round(max(0.0, float(duration)) * 10000)) // 100 / 100.0)

        if task_type == "I2VA" and image_count >= 1:
            return "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."

        if task_type == "L2VA" and image_count >= 1:
            return f"For the target video, at {s} seconds into the target video, <Picture 1> is fully referenced."

        if task_type != "FL2VA" or image_count < 2:
            return ""
        
        return (f"How the reference pictures align with the target video — <Picture 1> "
                f"(from [Shot 1]) aligns with the 0.00-second mark of the target video; "
                f"<Picture 2> (from [Shot 2]) aligns with the {s}-second mark of the target video.")

    def generate_subject_definitions(self, image_count: int, has_video: bool, has_audio: bool = False, parsed_vision_dict: dict = None) -> str:
        """
        Programmatically generate exact MiniMax syntax for binding reference tokens.
        """
        lines = []
        if parsed_vision_dict:
            for i in range(image_count):
                key = f"<Picture {i+1}>"
                desc = parsed_vision_dict.get(key, "")
                if desc:
                    lines.append(f"{key} is {desc}")
                else:
                    lines.append(f"{key} acts as a visual anchor.")
            if has_video:
                key = "<Video 1>"
                desc = parsed_vision_dict.get(key, "")
                if desc:
                    lines.append(f"{key} is the reference video: {desc}")
                else:
                    lines.append(f"{key} is the reference video.")
            if has_audio:
                key = "<Audio 1>"
                desc = parsed_vision_dict.get(key, "")
                if desc:
                    lines.append(f"{key} is the reference audio: {desc}")
                else:
                    lines.append(f"{key} is the synchronization and sound reference.")
            return " ".join(lines)
        else:
            if image_count > 0:
                pictures = " and ".join(f"<Picture {i+1}>" for i in range(image_count))
                lines.append(f"<Subject 1> is the primary focus shown in {pictures}.")
                for i in range(image_count):
                    lines.append(f"<Picture {i+1}> acts as a visual anchor.")
            
            if has_video:
                lines.append("<Video 1> is the reference video: follow its motion and camera work exactly.")

            if has_audio:
                lines.append("<Audio 1> is the synchronization and sound reference.")
            
            return " ".join(lines)

    def build_user_message(
        self,
        description: str,
        duration: float,
        task_type: str,
        vision_context: str = "",
        output_language: str = "English",
        image_count: int = 0,
        has_video: bool = False
    ) -> str:
        """
        Construct the main user instruction string dynamically based on the available inputs.
        """
        if output_language.lower() == "chinese":
            msg = f"Task: Generate a MiniMax {task_type} prompt. You MUST write your final response (including the [Shot N] descriptions and audio details) entirely in **Simplified Chinese (简体中文)**.\n\n"
        else:
            msg = f"Task: Generate a MiniMax {task_type} prompt.\n\n"
        
        if vision_context:
            msg += f"--- VISION ANALYSIS ---\nHere is the detailed analysis of the referenced images and videos for this generation:\n{vision_context}\n-----------------------\n\n"
            
        msg += f"Primary Target User Description:\n{description}\n\n"
        
        # Inject exact constraints
        msg += f"Constraint: The video will be {duration} seconds long (approx. {int(duration * 24)} frames). Pace the [Shot N] descriptions accordingly.\n"
        
        # Inject tagging requirements
        available_tags = []
        for i in range(image_count):
            available_tags.append(f"<Picture {i+1}>")
        if has_video:
            available_tags.append("<Video 1>")
            
        if available_tags:
            msg += f"CRITICAL: You have the following media references available: {', '.join(available_tags)}.\n"
            if output_language.lower() == "chinese":
                msg += "You MUST physically insert these exact tags into your [Shot N] sentences to explicitly dictate which subject/motion appears in which shot. For example: `<Picture 1> 走入房间，采用 <Video 1> 的姿态`.\n"
            else:
                msg += "You MUST physically insert these exact tags into your [Shot N] sentences to explicitly dictate which subject/motion appears in which shot. For example: `<Picture 1> enters the room, adopting the posture shown in <Video 1>`.\n"
        
        return msg

    def build_vision_system_prompt(self, output_language: str) -> str:
        """Assemble the system prompt for the vision analyzer."""
        if output_language.lower() == "chinese":
            lang_instruction = "\nCRITICAL: You MUST write your response and translated summaries in Simplified Chinese (简体中文)."
        else:
            lang_instruction = "\nCRITICAL: You MUST write your response in English."

        return (
            "You are an expert film director and visual analyst. "
            "Analyze the provided visual media precisely according to the user's instructions.\n"
            "CRITICAL: You MUST output ONLY a valid stringified JSON dictionary mapping the specific media keys to their descriptions.\n"
            "Output Format Example:\n"
            '{\n  "<Picture 1>": "description here",\n  "<Picture 2>": "description here"\n}\n'
            "Do NOT output markdown blocks, conversational preambles, or any extra text outside the JSON braces."
            f"{lang_instruction}"
        )

    def build_vibe_system_prompt(self) -> str:
        """Assemble the system prompt for the Global Vibe synthesis step."""
        return (
            "You are an expert film director and visual analyst. "
            "Synthesize the provided media analyses precisely according to the instruction.\n"
            "CRITICAL: Output ONLY the requested summary text. Do NOT output markdown, formatting, JSON, or custom tags."
        )

    @staticmethod
    def parse_overrides(custom_prompt_override: str) -> dict:
        """Parse 'key: value' override lines into a dict keyed by <Picture N> / <Video N>."""
        overrides = {}
        for line in custom_prompt_override.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                k_norm = k.lower()
                item_idx = ''.join(filter(str.isdigit, k_norm))
                if not item_idx:
                    continue
                idx = int(item_idx)

                if "<" not in k_norm and ("image" in k_norm or "video" in k_norm or "img" in k_norm or "vid" in k_norm):
                    idx += 1

                if "video" in k_norm or "vid" in k_norm:
                    key = f"<Video {idx}>"
                else:
                    key = f"<Picture {idx}>"
                overrides[key] = v.strip()
        return overrides

    def build_vision_request(self, output_language: str, target_key: str, active_prompt: str, pos: int = 0, is_video: bool = False, num_frames: int = 1) -> str:
        """Construct the prompt sent to the vision analyzer for individual media or sequences."""
        lang_prefix = "【强制指令：必须使用简体中文(Simplified Chinese)输出！！！】\n" if output_language.lower() == "chinese" else ""
        if is_video:
            return f"{target_key}: {lang_prefix}Please analyze this sequence of {num_frames} frames based on the instruction -> {active_prompt}"
        else:
            return f"Media {pos} is {target_key}: {lang_prefix}Please analyze based on the instruction -> {active_prompt}"

    def build_vibe_request(self, output_language: str, final_dict: dict, vibe_prompt_en: str) -> str:
        """Construct the synthesis prompt sent to the vision analyzer for the Global Vibe."""
        import json
        context_str = json.dumps(final_dict, ensure_ascii=False)
        
        if output_language.lower() == "chinese":
            vibe_prompt = f"【极高优先级指令】：请用一段纯文本的简体中文总结总体氛围。必须且只能输出中文，禁止输出英文！\n任务参考（请在总结中体现）：{vibe_prompt_en}"
            return f"Based on the following individual media analyses:\n{context_str}\n\n{vibe_prompt}"
        else:
            return f"Based on the following individual media analyses:\n{context_str}\n\nProvide the final 'Global_Vibe' synthesis using this instruction: {vibe_prompt_en}"

    def get_available_templates(self) -> list[str]:
        templates = ["default"]
        if not self.templates_dir.exists():
            return templates
        for f in sorted(self.templates_dir.glob("*.txt")):
            if f.stem != "system_base":
                templates.append(f.name)
        return templates

    def _load_template(self, filename: str) -> str | None:
        path = self.templates_dir / filename
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except IOError as e:
            return None

    @staticmethod
    def _fallback_base() -> str:
        return "You are a professional MiniMax H3 prompt writer."

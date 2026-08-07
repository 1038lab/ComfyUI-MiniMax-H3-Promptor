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
    ) -> str:
        """
        Assemble the complete system prompt from template files.
        """
        parts = []

        base = self._load_template("system_base.txt")
        if base:
            # Inject budget based on duration (approx 20-30 words per second)
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
        Produce mathematically precise FL2VA alignment strings.
        S.SS is floored based on the 17k+5 frame grid to ensure it doesn't fall off the edge.
        """
        if task_type != "FL2VA" or image_count < 2:
            return ""

        # Using the formula from minimax_plan.py
        s = "%.2f" % (int(round(max(0.0, float(duration)) * 10000)) // 100 / 100.0)
        
        return (f"How the reference pictures align with the target video — <Picture 1> "
                f"(from [Shot 1]) aligns with the 0.00-second mark of the target video; "
                f"<Picture 2> (from [Shot 2]) aligns with the {s}-second mark of the target video.")

    def generate_subject_definitions(self, image_count: int, has_video: bool, parsed_vision_dict: dict = None) -> str:
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
            return " ".join(lines)
        else:
            if image_count > 0:
                pictures = " and ".join(f"<Picture {i+1}>" for i in range(image_count))
                lines.append(f"<Subject 1> is the primary focus shown in {pictures}.")
                for i in range(image_count):
                    lines.append(f"<Picture {i+1}> acts as a visual anchor.")
            
            if has_video:
                lines.append("<Video 1> is the reference video: follow its motion and camera work exactly.")
            
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
            msg += "You MUST physically insert these exact tags into your [Shot N] sentences to explicitly dictate which subject/motion appears in which shot. For example: `<Picture 1> enters the room, adopting the posture shown in <Video 1>`.\n"
        
        if output_language.lower() == "chinese":
            msg += "\n\nCRITICAL LANGUAGE CONSTRAINT:\nYou MUST write the ENTIRE OUTPUT PROMPT in Simplified Chinese (简体中文). Translate all technical film directions into equivalent Chinese terms."
        else:
            msg += "\n\nCRITICAL LANGUAGE CONSTRAINT:\nYou MUST write the ENTIRE OUTPUT PROMPT in English."

        return msg

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

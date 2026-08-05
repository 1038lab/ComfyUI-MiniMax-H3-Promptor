"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
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
    ) -> str:
        """
        Assemble the complete system prompt from template files.

        Composition:
        1. system_base.txt (always loaded — core H3 rules)
        2. Task-specific template (t2v.txt, i2va.txt, etc.)
        3. Optional user-specified template override

        Args:
            task_type: One of T2V, I2VA, FL2VA, Ref2VA.
            template_override: Optional custom template filename.

        Returns:
            Complete system prompt string.
        """
        parts = []

        # 1. Base rules (always included)
        base = self._load_template("system_base.txt")
        if base:
            parts.append(base)
        else:
            log_error("system_base.txt not found! Using minimal fallback.")
            parts.append(self._fallback_base())

        # 2. Task-specific template
        if template_override and template_override != "default":
            task_template = self._load_template(template_override)
            if task_template:
                parts.append(task_template)
            else:
                log_error(f"Template '{template_override}' not found, using default.")
                task_template = self._load_template(f"{task_type.lower()}.txt")
                if task_template:
                    parts.append(task_template)
        else:
            task_template = self._load_template(f"{task_type.lower()}.txt")
            if task_template:
                parts.append(task_template)

        return "\n\n".join(parts)

    def build_user_message(
        self,
        description: str,
        duration: int,
        task_type: str,
        vision_context: str = "",
        output_language: str = "English"
    ) -> str:
        """
        Construct the main user instruction string dynamically based on the available inputs.
        """
        msg = f"Task: Generate a MiniMax {task_type} prompt.\n\n"
        
        if vision_context:
            msg += f"--- VISION ANALYSIS ---\nHere is the detailed analysis of the referenced images and videos for this generation:\n{vision_context}\n-----------------------\n\n"
            
        msg += f"Primary Target User Description:\n{description}\n\n"
        
        msg += f"Constraint: The video will be {duration} seconds long (approx. {duration * 24} frames). Pace the [SCENE] descriptions accordingly.\n"
        
        if output_language.lower() == "chinese":
            msg += "\n\nCRITICAL LANGUAGE CONSTRAINT:\nYou MUST write the ENTIRE OUTPUT PROMPT in Simplified Chinese (简体中文). Translate all technical film directions into equivalent Chinese terms."
        else:
            msg += "\n\nCRITICAL LANGUAGE CONSTRAINT:\nYou MUST write the ENTIRE OUTPUT PROMPT in English."

        return msg

    def get_available_templates(self) -> list[str]:
        """
        List available template files for the dropdown selector.

        Returns:
            List of template filenames (excluding system_base.txt).
        """
        templates = ["default"]

        if not self.templates_dir.exists():
            return templates

        for f in sorted(self.templates_dir.glob("*.txt")):
            if f.stem != "system_base":
                templates.append(f.name)

        return templates

    def _load_template(self, filename: str) -> str | None:
        """Load a template file by name."""
        path = self.templates_dir / filename
        if not path.exists():
            log_debug(f"Template not found: {path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            log_debug(f"Loaded template: {filename} ({len(content)} chars)")
            return content
        except IOError as e:
            log_error(f"Failed to read template {filename}: {e}")
            return None

    @staticmethod
    def _fallback_base() -> str:
        """Minimal fallback if system_base.txt is missing."""
        return (
            "You are a professional MiniMax H3 prompt writer. "
            "Generate structured, cinema-production-grade prompts "
            "following the H3 specification. Use clear section headers "
            "like [REFERENCE USE], [SHOT LIST], [PRODUCTION SOUND], etc. "
            "Output only the raw prompt text with no wrappers."
        )

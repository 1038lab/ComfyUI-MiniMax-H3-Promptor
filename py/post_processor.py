"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""
import re

from .utils import sanitize_llm_output, log_warning


# H3 maximum prompt length (characters)
H3_MAX_CHARS = 7000

# Expected section headers for validation
KNOWN_SECTIONS = [
    "[REFERENCE USE]",
    "[IDENTITY / CONTINUITY LOCKS]",
    "[IDENTITY]",
    "[CONTINUITY]",
    "[SCENE]",
    "[DIALOGUE]",
    "[SCREEN GEOGRAPHY]",
    "[SHOT LIST]",
    "[ACTING]",
    "[LIGHT AND IMAGE]",
    "[CAMERA]",
    "[PRODUCTION SOUND]",
    "[NEGATIVES]",
    "[BOUNDARY FRAMES]",
    "[ACTION]",
    "[CAMERA AND SOUND]",
    "[SOURCE MASTER]",
    "[EDIT]",
    "[PRESERVE]",
    "[TRANSFER]",
    "[SYNC AND MIX]",
    "[SOUND]",
]


class PostProcessor:
    """Clean and validate generated H3 prompts."""

    @staticmethod
    def clean(raw_output: str, task_type: str = "T2V", full_task_desc: str = "") -> str:
        """
        Clean the LLM output and enforce H3 constraints.

        Returns:
            Cleaned prompt string.
        """
        if not raw_output:
            return ""

        # Step 1: Sanitize LLM artifacts
        prompt_text = sanitize_llm_output(raw_output)

        # Fallback to strip any markdown wrappers that might have been missed
        prompt_text = re.sub(r"^```[\w]*\s*\n", "", prompt_text)
        prompt_text = re.sub(r"\n```$", "", prompt_text)
        
        # Step 2: Normalize whitespace
        prompt_text = re.sub(r"\n{3,}", "\n\n", prompt_text)
        prompt_text = "\n".join(line.rstrip() for line in prompt_text.split("\n"))

        # Step 3: Enforce character limit
        if len(prompt_text) > H3_MAX_CHARS:
            log_warning(
                f"Prompt exceeds H3 limit ({len(prompt_text)}/{H3_MAX_CHARS} chars). "
                f"Truncating to fit."
            )
            prompt_text = PostProcessor._truncate_safely(prompt_text, H3_MAX_CHARS)

        # Step 4: Validation warnings
        PostProcessor._validate(prompt_text, task_type)

        return prompt_text.strip()

    @staticmethod
    def _truncate_safely(text: str, max_chars: int) -> str:
        """
        Truncate text to max_chars while preserving complete sentences.
        Tries to cut at the last period before the limit.
        """
        if len(text) <= max_chars:
            return text

        truncated = text[:max_chars]

        # Try to find the last sentence boundary
        last_period = truncated.rfind(".")
        last_newline = truncated.rfind("\n")
        cut_point = max(last_period, last_newline)

        if cut_point > max_chars * 0.7:
            return truncated[:cut_point + 1]

        return truncated

    @staticmethod
    def _validate(prompt: str, task_type: str):
        """
        Run non-blocking validation checks and log warnings.
        Does not modify the prompt.
        """
        # Check for common issues
        if not prompt.strip():
            log_warning("Generated prompt is empty.")
            return

        # Check for section headers
        has_sections = any(
            section in prompt for section in KNOWN_SECTIONS
        )
        if not has_sections and task_type != "T2V":
            log_warning(
                "Prompt does not contain recognized H3 section headers. "
                "Quality may be reduced."
            )

        # Check for forbidden patterns
        if "```" in prompt:
            log_warning(
                "Prompt still contains markdown code fences after sanitization."
            )

        # Check minimum length for non-trivial prompts
        if len(prompt) < 100 and task_type != "T2V":
            log_warning(
                f"Prompt is very short ({len(prompt)} chars). "
                f"H3 typically benefits from detailed prompts."
            )

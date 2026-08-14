"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""


# Valid H3 task types
TASK_TYPES = ["T2V", "I2V", "I2VA", "V2V", "V2VA", "A2V", "FL2VA", "Ref2VA", "L2VA"]

# Full descriptions for UI
TASK_DESCRIPTIONS = {
    "T2V": "Text-to-Video (T2V)",
    "I2V": "Image-to-Video (I2V)",
    "I2VA": "Image-to-Video-Audio (I2VA)",
    "V2V": "Video-to-Video (V2V)",
    "V2VA": "Video-to-Video-Audio (V2VA)",
    "A2V": "Audio-to-Video (A2V)",
    "FL2VA": "First-and-Last-Frame-to-Video (FL2VA)",
    "Ref2VA": "Reference-to-Video-Audio (Ref2VA)",
    "L2VA": "Last-Frame-to-Video-Audio (L2VA)"
}

# User-facing options (includes Auto)
TASK_TYPE_OPTIONS = ["Auto"] + list(TASK_DESCRIPTIONS.values())


class TaskDetector:
    """Detect the appropriate H3 task type from node inputs."""

    @staticmethod
    def detect(
        image_count: int = 0,
        has_video: bool = False,
        has_audio: bool = False,
        user_override: str = "Auto",
    ) -> str:
        """
        Determine the H3 task type based on connected inputs.
        
        Args:
            image_count: Number of images provided (0-4).
            has_video: Whether a video reference is provided.
            has_audio: Whether an audio reference is provided.
            user_override: Explicit user selection from the dropdown.
        """
        # Respect explicit user choice
        if user_override != "Auto":
            # Reverse map the UI description back to the short code (e.g. "Text-to-Video (T2V)" -> "T2V")
            for short_code, desc in TASK_DESCRIPTIONS.items():
                if user_override == desc:
                    return short_code
            # Fallback if somehow short code was passed directly
            if user_override in TASK_TYPES:
                return user_override

        # Auto-detection logic (Audio variants take precedence if has_audio is True)
        if has_video and image_count > 0:
            return "Ref2VA"   # Images + Video (+ Audio optionally) = Omni
        elif image_count >= 3:
            return "Ref2VA"   # 3-4 images = Omni reference
        elif has_video and has_audio:
            return "V2VA"
        elif has_video:
            return "V2V"
        elif image_count == 2:
            return "FL2VA"    # Exactly 2 images = First & Last frame
        elif image_count == 1 and has_audio:
            return "I2VA"
        elif image_count == 1:
            return "I2V"
        elif has_audio:
            return "A2V"
        else:
            return "T2V"      # Text only (no media)

    @staticmethod
    def get_task_description(task_type: str) -> str:
        """Get a human-readable description for a task type."""
        descriptions = {
            "T2V": "Text-to-Video (no references)",
            "I2V": "Image-to-Video (single image)",
            "I2VA": "Image-to-Audio-Video (image + audio reference)",
            "V2V": "Video-to-Video (video reference)",
            "V2VA": "Video-to-Video-Audio (video + audio reference)",
            "A2V": "Audio-to-Video (audio reference)",
            "FL2VA": "First/Last Frame (two boundary images)",
            "Ref2VA": "Omni Reference (multi-modal references)",
            "L2VA": "Last Frame Anchor (end frame constraints)",
        }
        return descriptions.get(task_type, f"Unknown ({task_type})")

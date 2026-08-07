"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
"""
import re

from .utils import sanitize_llm_output, log_warning, log_info

H3_MAX_CHARS = 7000

SOUND_PREFIXES = ("audio:", "sound:", "soundscape:", "sfx:")
MUSIC_PREFIXES = ("music:", "score:", "soundtrack:")

class PostProcessor:
    """Clean, validate, and assemble the final MiniMax H3 Prompt string."""

    @staticmethod
    def split_audio_music(text: str) -> tuple[str, str, str]:
        """Lift Audio and Music lines out of the prompt text."""
        if not text:
            return "", "", ""
        
        kept, sound, music = [], [], []
        current = None
        
        for line in text.splitlines():
            stripped = line.strip()
            low = stripped.lower()
            
            is_sound = False
            for p in SOUND_PREFIXES:
                if low.startswith(p):
                    current = sound
                    stripped = stripped.split(":", 1)[1].strip()
                    is_sound = True
                    break
            
            if is_sound:
                if stripped:
                    current.append(stripped)
                continue
                
            is_music = False
            for p in MUSIC_PREFIXES:
                if low.startswith(p):
                    current = music
                    stripped = stripped.split(":", 1)[1].strip()
                    is_music = True
                    break
            
            if is_music:
                if stripped:
                    current.append(stripped)
                continue

            if current is not None:
                if stripped:
                    current.append(stripped)
                else:
                    current = None
            else:
                kept.append(line)

        return "\n".join(kept).strip(), " ".join(sound).strip(), " ".join(music).strip()

    @staticmethod
    def compile_final_prompt(
        creative_text: str,
        task_type: str,
        subject_definitions: str = "",
        alignment_instructions: str = ""
    ) -> str:
        """
        Assemble the final official MiniMax prompt payload utilizing programmatically built sections.
        """
        # 1. Clean LLM artifacts
        prompt_text = sanitize_llm_output(creative_text)
        prompt_text = re.sub(r"^```[\w]*\s*\n", "", prompt_text)
        prompt_text = re.sub(r"\n```$", "", prompt_text)
        
        # 2. Extract sound and music
        body, soundscape, music = PostProcessor.split_audio_music(prompt_text)

        parts = []

        # 3. Programmatic subject definitions
        if subject_definitions.strip():
            parts.append("subject_definitions: " + subject_definitions.strip())
            
        # 4. Summary & Retention blocks (dynamically compiled in alignment_instructions)
        if alignment_instructions.strip():
            parts.append(alignment_instructions.strip())

        # 5. Core body
        if body.strip():
            header = "detailed_description:\n" if subject_definitions else "integrated_multimodal_description:\n"
            
            # Ensure it always starts with [Shot 1] if not present
            if "[Shot 1]" not in body and "[shot 1]" not in body.lower():
                body = f"[Shot 1] {body.strip()}"
                
            parts.append(header + body.strip())

        # 6. Audio definitions
        if soundscape:
            parts.append("overall_soundscape: " + soundscape)
        if music and music.lower() != "n/a":
            parts.append("non_diegetic_music: " + music)

        final_prompt = "\n\n".join(parts).strip()
        
        return final_prompt

    @staticmethod
    def clean(raw_output: str, task_type: str = "T2V", full_task_desc: str = "", 
              subject_defs: str = "", alignment_inst: str = "") -> str:
        """
        Main entry point for prompt post-processing and compilation.
        """
        if not raw_output:
            return ""

        final_compiled_prompt = PostProcessor.compile_final_prompt(
            raw_output, task_type, subject_defs, alignment_inst
        )

        if len(final_compiled_prompt) > H3_MAX_CHARS:
            log_warning(f"Prompt exceeds H3 limit ({len(final_compiled_prompt)}/{H3_MAX_CHARS} chars).")
            final_compiled_prompt = final_compiled_prompt[:H3_MAX_CHARS]

        return final_compiled_prompt

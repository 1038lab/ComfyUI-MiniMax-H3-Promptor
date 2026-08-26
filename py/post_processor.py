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

BASE_MODES = ("T2V", "I2V", "I2VA", "FL2VA", "L2VA", "A2V")

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
            
            # Check for sound / audio section header
            if low.startswith("overall_soundscape:"):
                current = sound
                val = stripped.split(":", 1)[1].strip()
                if val:
                    sound.append(val)
                continue

            # Check for music section header
            if low.startswith("non_diegetic_music:"):
                current = music
                val = stripped.split(":", 1)[1].strip()
                if val:
                    music.append(val)
                continue

            is_sound = False
            for p in SOUND_PREFIXES:
                if low.startswith(p):
                    current = sound
                    val = stripped.split(":", 1)[1].strip()
                    if val:
                        sound.append(val)
                    is_sound = True
                    break
            
            if is_sound:
                continue
                
            is_music = False
            for p in MUSIC_PREFIXES:
                if low.startswith(p):
                    current = music
                    val = stripped.split(":", 1)[1].strip()
                    if val:
                        music.append(val)
                    is_music = True
                    break
            
            if is_music:
                continue

            if current is not None:
                if stripped:
                    current.append(stripped)
                else:
                    current = None
            else:
                kept.append(line)

        body = "\n".join(kept).strip()
        # Clean stray section headers if model generated them inside body
        body = re.sub(r'^(?:integrated_multimodal_description|detailed_description):\s*\n?', '', body, flags=re.IGNORECASE).strip()

        sound_text = " ".join(sound).strip()
        music_text = " ".join(music).strip()

        return body, sound_text, music_text

    @staticmethod
    def extract_shot_appearances(body: str) -> dict[str, list[str]]:
        """
        Scan [Shot N] blocks to find which tags (<Subject X>, <Picture X>, <Video X>, <Audio X>)
        appear in which specific shots.
        """
        shots = re.split(r'(?=\[Shot\s+\d+)', body, flags=re.IGNORECASE)
        appearances = {}
        for shot in shots:
            shot_match = re.search(r'\[Shot\s+(\d+)', shot, re.IGNORECASE)
            if not shot_match:
                continue
            shot_tag = f"[Shot {shot_match.group(1)}]"
            found_tags = re.findall(r'<(?:Subject|Picture|Video|Audio)\s+\d+>', shot)
            for tag in set(found_tags):
                if tag not in appearances:
                    appearances[tag] = []
                appearances[tag].append(shot_tag)
        return appearances

    @staticmethod
    def construct_ref_blocks(task_type: str, subject_definitions: str, body_text: str, duration: float = 5.0) -> tuple[str, str]:
        """Construct clean summary and dynamic shot-mapped retention_analysis blocks for Full-Reference mode."""
        if not subject_definitions.strip():
            return "", ""

        # Extract declared subjects and media
        declared_subjects = re.findall(r'<Subject\s+\d+>', subject_definitions)
        declared_pictures = re.findall(r'<Picture\s+\d+>', subject_definitions)
        has_video = "<Video 1>" in subject_definitions
        has_audio = "<Audio 1>" in subject_definitions

        # Prefix determination
        if task_type in ["V2V", "V2VA"]:
            prefix = "video editing"
        else:
            prefix = "reference generation"

        summary = f"summary:\n[{prefix}] A {duration:0.1f}-second live-action sequence executing the requested visual narrative across shots using the defined references."

        # Scan shot appearances from narrative body
        appearances = PostProcessor.extract_shot_appearances(body_text)

        retention = ["retention_analysis:"]
        
        # 1. Retention for each declared Subject
        for subj in declared_subjects:
            shot_list = appearances.get(subj, [])
            if not shot_list:
                # Also check corresponding picture index
                s_idx = re.search(r'\d+', subj)
                if s_idx:
                    p_tag = f"<Picture {s_idx.group(0)}>"
                    shot_list = appearances.get(p_tag, [])

            # Extract specific preserved traits from subject_definitions
            trait_match = re.search(rf'{subj}.*?with (.*?)\.', subject_definitions, re.IGNORECASE)
            if trait_match and trait_match.group(1).strip():
                specific_trait = trait_match.group(1).strip() + " maintained."
            else:
                specific_trait = "visual appearance and features maintained."

            if shot_list:
                shots_str = ", ".join(shot_list)
                retention.append(f"{subj} (appears in {shots_str}): fully_preserved - {specific_trait}")
            else:
                retention.append(f"{subj} (appears in target video): fully_preserved - {specific_trait}")

        # 2. Check for standalone Picture references mentioned in body that are not subjects
        for pic in set(declared_pictures):
            p_num_match = re.search(r'\d+', pic)
            p_num = p_num_match.group(0) if p_num_match else ""
            if pic in appearances and not any(f"<Subject {p_num}>" in s for s in declared_subjects):
                shots_str = ", ".join(appearances[pic])
                retention.append(f"{pic}: reference - environment setting and visual tone followed in {shots_str}.")

        # 3. Video & Audio references
        if has_video:
            v_shots = appearances.get("<Video 1>", [])
            if v_shots:
                retention.append(f"<Video 1> (camera and motion): weak_reference - motion timing and camera work followed in {', '.join(v_shots)}.")
            else:
                retention.append("<Video 1> (camera and motion): weak_reference - motion timing and camera work followed.")

        if has_audio:
            retention.append("<Audio 1>: reference - voice timbre and audio synchronization maintained.")

        return summary, "\n".join(retention)

    @staticmethod
    def _strip_filenames(text: str) -> str:
        """Strip raw media filenames that LLMs may inadvertently output."""
        return re.sub(
            r"(?<![\w/\\])[\w .()\-\u4e00-\u9fff]+\.(?:png|jpe?g|webp|bmp|gif|mp4|mov|webm|mkv|avi|mp3|wav|flac|m4a|ogg|aac)(?!\w)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()

    @staticmethod
    def _normalize_subject_shorthand(text: str) -> str:
        """Guarantee that standalone S1-S20 references use official parentheses (S1)."""
        return re.sub(
            r"(?<![A-Za-z0-9_(<（])S([1-9]|1\d|20)(?![A-Za-z0-9_)>）])",
            lambda match: f"(S{match.group(1)})",
            str(text),
            flags=re.IGNORECASE,
        )

    @staticmethod
    def _ensure_fl2va_picture_labels(
        text: str, task_type: str, duration: float = 5.0, output_language: str = "English"
    ) -> str:
        """Guarantee that an FL2VA result retains both official bare picture labels."""
        if str(task_type).upper() != "FL2VA":
            return text
        lowered = str(text).lower()
        if "picture 1" in lowered and "picture 2" in lowered:
            return text
        if str(output_language).lower() in {"中文", "chinese", "zh", "zh-cn"}:
            alignment = (
                f"参考图像与目标视频对齐关系：picture 1 对齐目标视频的 0.00 秒首帧；"
                f"picture 2 对齐目标视频的 {duration:.2f} 秒尾帧。"
            )
        else:
            alignment = (
                "Reference-picture alignment: picture 1 is the target video's exact opening frame at 0.00s; "
                f"picture 2 is its exact ending frame at {duration:.2f}s."
            )
        return f"{alignment}\n\n{text}".strip()

    @staticmethod
    def _extract_explicit_dialogues(prompt: str) -> list[tuple[str, str]]:
        """Extract only dialogue that the user explicitly supplied, preserving exact wording."""
        source = str(prompt or "")
        candidates = []
        speech_marker = r"(?:说|说道|说着|喊|喊道|问|问道|回答|答道|台词|对白|says?|speaks?|shouts?|asks?|replies?)"
        patterns = (
            rf"{speech_marker}[^\n“”‘’\"']{{0,20}}[：:]?\s*[“\"]([^”\"\n]+)[”\"]",
            rf"{speech_marker}[^\n“”‘’\"']{{0,20}}[：:]?\s*[‘']([^’'\n]+)[’']",
            rf"{speech_marker}\s*[：:]\s*([^\n；;]+)",
        )
        for pattern in patterns:
            for match in re.finditer(pattern, source, flags=re.IGNORECASE):
                value = match.group(1).strip().strip("“”‘’\"'").strip()
                existing = {item[0] for item in candidates}
                if not value or value in existing or any(value in item or item in value for item in existing):
                    continue
                language = "Chinese" if re.search(r"[\u3400-\u9fff]", value) else "English"
                candidates.append((value, language))
        return candidates

    @staticmethod
    def _ensure_supplied_dialogues(
        text: str, user_description: str, output_language: str = "English"
    ) -> str:
        """Keep supplied user dialogue formatted as <d>[Language]...</d> inside the main shot narrative."""
        result = str(text)
        dialogues = PostProcessor._extract_explicit_dialogues(user_description)
        if not dialogues:
            return result

        dialogues_to_insert = []
        for index, (dialogue, language) in enumerate(dialogues, start=1):
            tag = f"<d>[{language}]{dialogue}</d>"
            if tag in result:
                continue
            if re.search(rf'<d>[^<]*{re.escape(dialogue)}[^<]*</d>', result, re.IGNORECASE):
                continue
            if dialogue in result:
                for quoted in (f"“{dialogue}”", f"‘{dialogue}’", f'"{dialogue}"', f"'{dialogue}'"):
                    if quoted in result:
                        result = result.replace(quoted, tag, 1)
                        break
                else:
                    result = result.replace(dialogue, tag, 1)
                continue
            dialogues_to_insert.append((index, tag))

        if dialogues_to_insert:
            shot_match = re.search(r'\[Shot\s+1\b[^\]]*\]\s*', result, re.IGNORECASE)
            if shot_match:
                insert_pos = shot_match.end()
            else:
                desc_match = re.search(
                    r'(?:integrated_multimodal_description|detailed_description):\s*\n?', result, re.IGNORECASE
                )
                insert_pos = desc_match.end() if desc_match else 0

            sentences = []
            for order, (index, tag) in enumerate(dialogues_to_insert):
                if str(output_language).lower() in {"中文", "chinese", "zh", "zh-cn"}:
                    action = "说" if order == 0 else "随后继续说"
                    sentences.append(f"画面中的说话者 (S{index}) {action}：{tag}")
                else:
                    action = "says" if order == 0 else "then continues"
                    sentences.append(f"The on-screen speaker (S{index}) {action}: {tag}")

            insertion = " " + " ".join(sentences) + " "
            result = result[:insert_pos] + insertion + result[insert_pos:]

        # Clean up any potential nested <d> tags
        result = re.sub(r'<d>\[(\w+)\]\s*<d>\[\1\](.*?)</d>\s*</d>', r'<d>[\1]\2</d>', result, flags=re.IGNORECASE | re.DOTALL)
        return result

    @staticmethod
    def compile_final_prompt(
        creative_text: str,
        task_type: str,
        subject_definitions: str = "",
        alignment_instructions: str = "",
        duration: float = 5.0,
        user_description: str = "",
        output_language: str = "English",
    ) -> str:
        """
        Assemble the final official MiniMax prompt payload.
        Enforces strict official tags (<Subject N>, <Picture N>, <Video N>, <Audio N>)
        and guarantees clean, deterministic section structuring.
        """
        # 1. Clean LLM artifacts and filenames
        prompt_text = sanitize_llm_output(creative_text)
        prompt_text = PostProcessor._strip_filenames(prompt_text)
        prompt_text = PostProcessor._normalize_subject_shorthand(prompt_text)
        
        # 2. Sanitize any hallucinated tags like <Environment N> or <Setting N> into <Subject N>
        def _fix_tag(match):
            tag_num = match.group(1)
            return f"<Subject {tag_num}>"
        prompt_text = re.sub(r'<(?:Environment|Setting|Location|Scene)\s+(\d+)>', _fix_tag, prompt_text, flags=re.IGNORECASE)

        # 3. Extract body narrative, sound, and music from LLM text
        body, soundscape, music = PostProcessor.split_audio_music(prompt_text)

        # If LLM wrote section headers like detailed_description:, extract only the shot text
        detailed_match = re.search(r'detailed_description:\s*\n?(.*)', body, flags=re.DOTALL | re.IGNORECASE)
        if detailed_match:
            body = detailed_match.group(1).strip()

        # Ensure body starts with [Shot 1]
        if body and not re.search(r'^\s*\[Shot\s+1\b', body, re.IGNORECASE):
            # If body has shots later, grab from first [Shot
            first_shot = re.search(r'\[Shot\s+\d+\b', body, re.IGNORECASE)
            if first_shot:
                body = body[first_shot.start():].strip()
            else:
                body = f"[Shot 1] {body.strip()}"

        # Default fallbacks for soundscape and music if omitted
        if not soundscape:
            soundscape = "Ambient room tone and subtle environmental sound effects matching the scene actions."
        if not music:
            music = "N/A"

        parts = []

        # Branch A: Base Modes (T2V, I2V, I2VA, FL2VA, L2VA, A2V)
        # Official standard: Keyframe alignment line (if any) + integrated_multimodal_description + soundscape + music
        if task_type in BASE_MODES:
            if alignment_instructions.strip():
                parts.append(alignment_instructions.strip())

            parts.append("integrated_multimodal_description:\n" + body.strip())
            parts.append("overall_soundscape:\n" + soundscape)
            parts.append("non_diegetic_music:\n" + music)

        # Branch B: Full-Reference Mode (Ref2VA, V2V, V2VA, multi-image references)
        # Official standard: subject_definitions + summary + retention_analysis + detailed_description + soundscape + music
        else:
            if subject_definitions.strip():
                parts.append("subject_definitions:\n" + subject_definitions.strip())
                
                summary_block, retention_block = PostProcessor.construct_ref_blocks(
                    task_type, subject_definitions, body, duration=duration
                )
                if summary_block:
                    parts.append(summary_block)
                if retention_block:
                    parts.append(retention_block)

            parts.append("detailed_description:\n" + body.strip())
            parts.append("overall_soundscape:\n" + soundscape)
            parts.append("non_diegetic_music:\n" + music)

        final_prompt = "\n\n".join(parts).strip()
        final_prompt = PostProcessor._ensure_fl2va_picture_labels(
            final_prompt, task_type, duration=duration, output_language=output_language
        )
        final_prompt = PostProcessor._ensure_supplied_dialogues(
            final_prompt, user_description=user_description, output_language=output_language
        )
        final_prompt = PostProcessor._normalize_subject_shorthand(final_prompt)
        return final_prompt

    @staticmethod
    def clean(
        raw_output: str,
        task_type: str = "T2V",
        full_task_desc: str = "", 
        subject_defs: str = "",
        alignment_inst: str = "",
        duration: float = 5.0,
        user_description: str = "",
        output_language: str = "English",
    ) -> str:
        """
        Main entry point for prompt post-processing and compilation.
        """
        if not raw_output:
            return ""

        final_compiled_prompt = PostProcessor.compile_final_prompt(
            raw_output,
            task_type,
            subject_defs,
            alignment_inst,
            duration=duration,
            user_description=user_description,
            output_language=output_language,
        )

        if len(final_compiled_prompt) > H3_MAX_CHARS:
            log_warning(f"Prompt exceeds H3 limit ({len(final_compiled_prompt)}/{H3_MAX_CHARS} chars).")
            final_compiled_prompt = final_compiled_prompt[:H3_MAX_CHARS]

        return final_compiled_prompt

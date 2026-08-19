"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
"""

import re
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
            duration_str = f"Video Duration: {duration} seconds. Ensure cut timestamps do not exceed {duration:02.3f}s. Pace the action naturally across the duration."
            parts.append(f"{base}\n\n{duration_str}")
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

        if task_type in ["I2V", "I2VA"] and image_count >= 1:
            return "For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced."

        if task_type == "L2VA" and image_count >= 1:
            return f"How the reference pictures align with the target video — <Picture 1> (from [Shot 1]) aligns with the {s}-second mark of the target video."

        if task_type != "FL2VA" or image_count < 2:
            return ""
        
        return (f"How the reference pictures align with the target video — <Picture 1> "
                f"(from [Shot 1]) aligns with the 0.00-second mark of the target video; "
                f"<Picture 2> (from [Shot 1]) aligns with the {s}-second mark of the target video.")

    @staticmethod
    def _detect_subject_noun(desc: str) -> str:
        """Helper to accurately identify the natural noun/entity category using strict word boundaries."""
        low = desc.lower()

        # 1. Vehicles & Props (Checked first with word boundaries so 'performance' or 'driver' never match 'man')
        vehicle_patterns = [
            (r'\b(sports\s*car|supercar|race\s*car)\b', "sports car"),
            (r'\b(taxi|cab)\b', "taxi"),
            (r'\b(car|automobile|vehicle|sedan|coupe|suv|truck|van)\b', "vehicle"),
            (r'\b(motorcycle|motorbike|bike|bicycle|scooter)\b', "motorcycle"),
            (r'\b(airplane|plane|jet|aircraft|spaceship|shuttle)\b', "aircraft"),
            (r'\b(boat|ship|yacht|vessel)\b', "vessel"),
            (r'\b(robot|mech|cyborg|drone)\b', "robot"),
            (r'\b(armor|suit\s+of\s+armor)\b', "armor"),
        ]
        for pat, noun in vehicle_patterns:
            if re.search(pat, low):
                return noun

        # 2. Animals / Creatures (Word boundaries; negative lookahead prevents 'cat-ear' or 'tiger stripes' matching as animal)
        animal_patterns = [
            (r'\b(black\s+panther)\b', "black panther"),
            (r'\b(panther|leopard|jaguar|cheetah)\b', "panther"),
            (r'\b(tabby\s+cat)\b', "tabby cat"),
            (r'\bcat\b(?!\s*[-_]?\s*(?:ear|tail|eye|print|suit|hat|mask))', "cat"),
            (r'\btiger\b(?!\s*[-_]?\s*(?:stripe|print|pattern))', "tiger"),
            (r'\blion\b(?!\s*[-_]?\s*(?:print|pattern))', "lion"),
            (r'\b(dog|puppy|hound|wolf|fox|bear|dragon|horse|stallion|eagle|hawk|bird|rabbit|deer|creature|beast)\b', None),
        ]
        for pat, noun in animal_patterns:
            m = re.search(pat, low)
            if m:
                return noun if noun else m.group(1)

        # 3. Humanoid / Person (Strict word boundaries)
        person_patterns = [
            (r'\b(woman|girl|female|lady|she|her)\b', "young woman"),
            (r'\b(boy|guy|young\s+man)\b', "young person"),
            (r'\b(man|male|gentleman|he|his)\b', "man"),
            (r'\b(warrior|knight|soldier|fighter|ninja|samurai)\b', "warrior"),
            (r'\b(monk|wizard|mage|priest)\b', "character"),
            (r'\b(person|individual|character|figure|human)\b', "character"),
            (r'\b(hair|bikini|dress|skirt|suit|jacket|shirt|apron|wearing)\b', "young woman" if any(w in low for w in ["she", "her", "bikini", "dress", "skirt"]) else "character"),
        ]
        for pat, noun in person_patterns:
            if re.search(pat, low):
                return noun

        # 4. Environment / Setting
        env_patterns = [
            (r'\b(tunnel|street|alley|corridor|room|hall|forest|mountain|beach|cityscape|landscape|temple|laboratory|station)\b', None)
        ]
        for pat, _ in env_patterns:
            m = re.search(pat, low)
            if m:
                return f"{m.group(1)} environment"

        return "subject"

    def generate_subject_definitions(self, image_count: int, has_video: bool, has_audio: bool = False, parsed_vision_dict: dict = None) -> tuple[str, list[str]]:
        """
        Programmatically generate clean MiniMax subject definitions following official ref-en.txt standard:
        '<Subject N> is the [noun] in <Picture N>, with [key features].'
        """
        lines = []
        valid_tags = []
        if parsed_vision_dict:
            valid_idx = 1
            for i in range(image_count):
                key = f"<Picture {i+1}>"
                desc = parsed_vision_dict.get(key, "").strip()
                if desc and "failed to analyze" not in desc.lower():
                    subj_tag = f"<Subject {valid_idx}>"
                    valid_tags.append(subj_tag)
                    
                    # Detect natural entity noun
                    noun = self._detect_subject_noun(desc)

                    # Clean all boilerplate prefixes
                    cleaned = desc.strip()
                    cleaned = re.sub(
                        r'^(?:the\s+)?(?:main\s+)?(?:subject\s+(?:is|has)|character\s+(?:is|has)|image\s+(?:shows|depicts|presents)|picture\s+(?:shows|depicts|features)|there\s+is|a\s+photo\s+of|a\s+view\s+of|an\s+image\s+of)\s+',
                        '',
                        cleaned,
                        flags=re.IGNORECASE
                    )
                    cleaned = re.sub(r'^(?:a\s+|an\s+|the\s+)', '', cleaned, flags=re.IGNORECASE).strip()
                    
                    # Clean duplicate noun phrases (e.g. "woman with...", "man with...")
                    cleaned = re.sub(r'^(?:woman|man|person|character|girl|boy|individual|subject|animal|vehicle|car)\s+(?:with|wearing|holding|in|having|characterized\s+by)\s+', '', cleaned, flags=re.IGNORECASE).strip()
                    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                    
                    # Extract concise key features
                    clauses = re.split(r'[\.\;\n]', cleaned)
                    traits = clauses[0].strip()
                    if len(traits) < 50 and len(clauses) > 1 and clauses[1].strip():
                        traits += ", " + clauses[1].strip()
                    if len(traits) > 120:
                        traits = traits[:120].rsplit(' ', 1)[0]
                    traits = traits.rstrip(',.')
                    
                    lines.append(f"{subj_tag} is the {noun} in {key}, with {traits}.")
                    valid_idx += 1
            if has_video:
                desc = parsed_vision_dict.get("<Video 1>", "").strip()
                valid_tags.append("<Video 1>")
                if desc and "failed to analyze" not in desc.lower():
                    lines.append(f"<Video 1> is the source video in <Video 1>, with motion and camera rhythm: {desc}.")
                else:
                    lines.append("<Video 1> is the source video for camera movement and temporal structure.")
            if has_audio:
                desc = parsed_vision_dict.get("<Audio 1>", "").strip()
                valid_tags.append("<Audio 1>")
                if desc and "failed to analyze" not in desc.lower():
                    lines.append(f"<Audio 1> is the audio track in <Audio 1>, providing voice timbre and synchronization: {desc}.")
                else:
                    lines.append("<Audio 1> is the reference audio track for voice timbre and synchronization.")
            return "\n".join(lines), valid_tags
        else:
            if image_count > 0:
                for i in range(image_count):
                    subj_tag = f"<Subject {i+1}>"
                    valid_tags.append(subj_tag)
                    lines.append(f"{subj_tag} is the subject in <Picture {i+1}>.")
            if has_video:
                valid_tags.append("<Video 1>")
                lines.append("<Video 1> supplies camera rhythm and motion language only.")
            if has_audio:
                valid_tags.append("<Audio 1>")
                lines.append("<Audio 1> supplies voice identity and audio synchronization.")
            return "\n".join(lines), valid_tags

    def build_user_message(
        self,
        description: str,
        duration: float,
        task_type: str,
        vision_context: str = "",
        output_language: str = "English",
        image_count: int = 0,
        has_video: bool = False,
        parsed_vision_dict: dict = None,
    ) -> str:
        """
        Construct the main user instruction string dynamically with strict duration-based shot budgeting.
        """
        if output_language.lower() == "chinese":
            msg = f"Task: Generate a MiniMax {task_type} prompt. You MUST write your final response (including the [Shot N] descriptions and audio details) entirely in **Simplified Chinese (简体中文)**.\n\n"
        else:
            msg = f"Task: Generate a MiniMax {task_type} prompt in English.\n\n"
        
        if vision_context:
            msg += f"--- PRODUCTION MEDIA REFERENCES (CAST & PROPS) ---\n{vision_context}\n----------------------------------------------------\n\n"
            
        msg += f"USER'S CORE CREATIVE MANDATE (HIGHEST PRIORITY):\n{description}\n-> You MUST direct the scene, cast, and visual action specifically around fulfilling this creative mandate!\n\n"
        
        # Shot budget guidance
        if duration <= 6.0:
            budget_directive = f"Target Video Duration: EXACTLY {duration}s. Shot Budget: 1 to 2 shots max (>=2.5s per shot). Stage multiple references together within the same frame using foreground/midground/background depth composition."
        elif duration <= 10.0:
            budget_directive = f"Target Video Duration: EXACTLY {duration}s. Shot Budget: 2 to 3 shots max (>=3.0s per shot). Build a compact dramatic scene with action-reaction momentum."
        else:
            budget_directive = f"Target Video Duration: EXACTLY {duration}s. Shot Budget: 3 to 4 shots max (>=3.5s per shot). Build a rich cinematic sequence with fluid transitions."

        msg += f"DIRECTING DIRECTIVE:\n- {budget_directive}\n- Never generate timestamps beyond {duration:02.3f} seconds.\n\n"
        
        # Inject available media tags (filtering out failed items)
        available_tags = []
        for i in range(image_count):
            key = f"<Picture {i+1}>"
            if parsed_vision_dict:
                desc = parsed_vision_dict.get(key, "").strip()
                if desc and "failed to analyze" in desc.lower():
                    continue
            available_tags.append(key)
        if has_video:
            available_tags.append("<Video 1>")
            
        if available_tags:
            msg += f"PRODUCTION CAST & ASSETS: Available media references: {', '.join(available_tags)}.\n"
            if output_language.lower() == "chinese":
                msg += "You MUST weave these exact tags naturally into your [Shot N] action sentences to direct the ensemble. For example: `<Picture 1> 与 <Picture 2> 并肩伏击，随后跃上 <Picture 3>`.\n"
            else:
                msg += "You MUST weave these exact tags naturally into your [Shot N] action sentences to direct the ensemble. For example: `<Picture 1> and <Picture 2> sprint alongside <Picture 3>`.\n"
        
        return msg

    def build_blueprint_system_prompt(self, output_language: str = "English") -> str:
        """System prompt for Stage 1: Director's Global Vibe & Timeline Blueprint synthesis."""
        lang_rule = "Simplified Chinese (简体中文)" if output_language.lower() == "chinese" else "English"
        return f"""You are a master Hollywood Director, Showrunner, and Storyboard Planner.
Your task is to analyze production visual assets and the user's creative vision to produce a high-impact 'Director Blueprint & Global Vibe'.

OUTPUT STRUCTURE (Write in {lang_rule}):
1. [Global Vibe & Visual Aesthetic]: 2-3 sentences defining the lighting, color grade, atmosphere, and cinematic world.
2. [Ensemble Cast Roles & Dynamics]: How the available references connect, interact, and serve the user's primary story mandate.
3. [Timeline Beats Plan (Mandatory Full Coverage 00:00.000 to end)]:
   Break the duration into evenly paced shots (e.g. 15s = 4 shots, 5s = 2 shots). For each beat, specify:
   - [Shot N (Start - End)]: Core action, participating references, camera movement, and emotional punchline.
"""

    def build_blueprint_user_message(
        self,
        description: str,
        duration: float,
        task_type: str,
        vision_context: str = "",
        output_language: str = "English",
        image_count: int = 0,
        has_video: bool = False,
        parsed_vision_dict: dict = None,
    ) -> str:
        """Construct user message for Stage 1: Blueprint Synthesis."""
        msg = f"Task: Construct the Director's Blueprint & Global Vibe for a {duration:0.1f}s MiniMax {task_type} sequence.\n\n"
        if vision_context:
            msg += f"--- PRODUCTION VISUAL REFERENCES ---\n{vision_context}\n------------------------------------\n\n"
        msg += f"USER'S SUPREME CREATIVE MANDATE:\n{description}\n\n"
        msg += f"TIMELINE CONSTRAINT: Total duration is EXACTLY {duration:0.1f} seconds. Plan beats that completely cover from 00:00.000 to {duration:02.3f} seconds with zero empty gaps.\n"
        return msg

    def build_storyboard_user_message(
        self,
        blueprint: str,
        description: str,
        duration: float,
        task_type: str,
        output_language: str = "English",
        available_tags: list = None,
    ) -> str:
        """Construct user message for Stage 2: Storyboard Generation using the Stage 1 Blueprint."""
        msg = f"--- APPROVED DIRECTOR BLUEPRINT & GLOBAL VIBE ---\n{blueprint}\n------------------------------------------------\n\n"
        msg += f"USER'S CORE CREATIVE MANDATE:\n{description}\n\n"
        msg += f"DIRECTING TASK: Transform the approved Blueprint above into the final cinematic MiniMax {task_type} storyboard.\n"
        msg += f"CRITICAL RULES:\n"
        msg += f"1. Write timed paragraphs for EVERY shot planned in the blueprint, covering the entire timeline up to {duration:02.3f}s.\n"
        if available_tags:
            msg += f"2. You MUST physically weave these available reference tags: {', '.join(available_tags)} into your action sentences.\n"
        msg += f"3. End strictly with the Audio: and Music: lines.\n"
        return msg

    def build_vision_system_prompt(self, output_language: str = "English") -> str:
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

"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.
"""
import re
import json

class ResponseParser:
    """Dedicated utility class for processing LLM Vision output into clean dictionaries."""

    @staticmethod
    def extract_json_content(content: str) -> dict | None:
        """
        Extract a JSON dictionary from a raw LLM text response.
        Robustly handles preambles, trailing text, and markdown blocks.
        """
        # Strategy 1: Find markdown JSON block
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
                
        # Strategy 2: Find the outermost curly braces { }
        brace_match = re.search(r'\{.*\}', content, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
                
        # Strategy 3: Try parse raw just in case there are no braces or markdown
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
            
        return None

    @staticmethod
    def parse_vision_response(content: str, target_keys: list[str]) -> dict:
        """
        Parse raw response and map it to target keys.
        Handles unstructured text fallbacks and fuzzy key matching (e.g., 'Picture 1' -> '<Picture 1>').
        """
        parsed = ResponseParser.extract_json_content(content)
        return_dict = {}

        if parsed:
            # Check if LLM strictly followed instructions
            all_keys_found = all(k in parsed for k in target_keys)
            
            if all_keys_found:
                return_dict = {k: parsed[k] for k in target_keys}
            else:
                # Fuzzy matching for keys where tags might be stripped (e.g. 'Picture 1' instead of '<Picture 1>')
                for target_key in target_keys:
                    raw_key = target_key.replace("<", "").replace(">", "")
                    if target_key in parsed:
                        return_dict[target_key] = parsed[target_key]
                    elif raw_key in parsed:
                        return_dict[target_key] = parsed[raw_key]
                    else:
                        # Find any key that matches the substring
                        matched = False
                        for pk, pv in parsed.items():
                            if raw_key.lower() in pk.lower():
                                return_dict[target_key] = pv
                                matched = True
                                break
                        if not matched:
                            return_dict[target_key] = "LLM failed to analyze this item."
                            
            # Special case for Global Vibe failing to output exact key but returning dict
            if len(target_keys) == 1 and target_keys[0] == "Global_Vibe":
                if "Global_Vibe" not in parsed:
                    # If it's a dict with one item, assume that's the summary
                    if len(parsed) == 1:
                        val = list(parsed.values())[0]
                        return_dict["Global_Vibe"] = val
                    else:
                        return_dict["Global_Vibe"] = json.dumps(parsed, ensure_ascii=False)        
        else:
            # Fallback handling for pure text responses
            if len(target_keys) == 1:
                # If there's only 1 target key (e.g., <Picture 1> or Global_Vibe), the whole raw text is likely the answer
                return_dict[target_keys[0]] = content.strip()
            else:
                for k in target_keys:
                    return_dict[k] = "LLM failed to return valid JSON."

        return return_dict

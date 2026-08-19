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
        Handles unstructured text fallbacks, single-item dicts, and fuzzy key matching.
        """
        if not content or not content.strip():
            return {k: "LLM returned empty response." for k in target_keys}

        parsed = ResponseParser.extract_json_content(content)
        return_dict = {}

        if parsed and isinstance(parsed, dict):
            # 1. Exact match for all keys
            if all(k in parsed for k in target_keys):
                return {k: str(parsed[k]).strip() for k in target_keys}
            
            # 2. Single target key requested (Sequential image analysis or Global Vibe)
            if len(target_keys) == 1:
                target_key = target_keys[0]
                raw_key = target_key.replace("<", "").replace(">", "").strip()
                
                # Check direct or stripped key match
                if target_key in parsed:
                    return {target_key: str(parsed[target_key]).strip()}
                if raw_key in parsed:
                    return {target_key: str(parsed[raw_key]).strip()}
                
                # Check case-insensitive key substring
                for pk, pv in parsed.items():
                    if raw_key.lower() in pk.lower() or pk.lower() in raw_key.lower():
                        return {target_key: str(pv).strip()}
                
                # Check common generic keys from vision models (e.g. "description", "details", "caption")
                for generic_k in ["description", "desc", "analysis", "caption", "detail", "content", "summary", "result", "text"]:
                    for pk, pv in parsed.items():
                        if generic_k in pk.lower() and str(pv).strip():
                            return {target_key: str(pv).strip()}
                
                # If dict has single value or non-empty string value, take it
                for pv in parsed.values():
                    if isinstance(pv, str) and pv.strip():
                        return {target_key: pv.strip()}
                
                return {target_key: json.dumps(parsed, ensure_ascii=False)}

            # 3. Multi-key matching (Batch mode)
            for target_key in target_keys:
                raw_key = target_key.replace("<", "").replace(">", "").strip()
                matched = False
                
                if target_key in parsed:
                    return_dict[target_key] = str(parsed[target_key]).strip()
                    matched = True
                elif raw_key in parsed:
                    return_dict[target_key] = str(parsed[raw_key]).strip()
                    matched = True
                else:
                    for pk, pv in parsed.items():
                        if raw_key.lower() in pk.lower():
                            return_dict[target_key] = str(pv).strip()
                            matched = True
                            break
                
                if not matched:
                    return_dict[target_key] = "LLM failed to analyze this item."

            return return_dict
        else:
            # Fallback for plain text response (no JSON found)
            if len(target_keys) == 1:
                return {target_keys[0]: content.strip()}
            else:
                for k in target_keys:
                    return_dict[k] = "LLM failed to return valid JSON."

        return return_dict

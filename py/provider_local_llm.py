"""
ComfyUI-Minimax-H3-Promptor
Local LLM Provider bridging to local GGUF engines (ComfyUI-QwenVL / llama-cpp).
Supports both Multimodal VLM (for H3_Vision) and Pure Text LLM (for H3_Promptor).
Follows GPL-3.0 License.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .provider_base import LLMProvider, LLMResponse

logger = logging.getLogger("ComfyUI-Minimax-H3-Promptor")

def log_info(msg: str):
    print(f"[H3-Promptor] {msg}")

def log_warning(msg: str):
    print(f"[H3-Promptor WARNING] {msg}")

def log_error(msg: str):
    print(f"[H3-Promptor ERROR] {msg}")


def normalize_base64_string(b64_str: str) -> str:
    """Strip data URI prefix, remove whitespace, and ensure valid base64 padding."""
    if not isinstance(b64_str, str):
        return ""
    clean = b64_str.strip()
    if "," in clean:
        clean = clean.split(",")[-1].strip()
    # Remove any internal whitespaces / newlines
    clean = "".join(clean.split())
    # Ensure correct padding (=)
    remainder = len(clean) % 4
    if remainder > 0:
        clean += "=" * (4 - remainder)
    return clean


def normalize_inputs(user_message: str, base64_images: Optional[List[Any]]) -> Tuple[str, List[str]]:
    """
    Extracts text prompts and clean base64 image strings from diverse payload formats
    (dict payloads, list of data URIs, raw strings, etc.).
    """
    extracted_text: List[str] = []
    extracted_images: List[str] = []

    if user_message:
        extracted_text.append(user_message)

    if base64_images:
        for item in base64_images:
            if isinstance(item, str):
                b64 = normalize_base64_string(item)
                if b64:
                    extracted_images.append(b64)
            elif isinstance(item, dict):
                # Handle {"text": "..."} or {"image": "..."} or OpenAI image_url dict
                if "text" in item and item["text"]:
                    extracted_text.append(str(item["text"]))
                if "image" in item and item["image"]:
                    b64 = normalize_base64_string(str(item["image"]))
                    if b64:
                        extracted_images.append(b64)
                elif "image_url" in item:
                    val = item["image_url"]
                    url_str = val.get("url", "") if isinstance(val, dict) else str(val)
                    b64 = normalize_base64_string(url_str)
                    if b64:
                        extracted_images.append(b64)

    combined_prompt = "\n\n".join(extracted_text).strip()
    return combined_prompt, extracted_images


class LocalLLMProvider(LLMProvider):
    """
    Local Multimodal / Text LLM Provider.
    Bridges to ComfyUI-QwenVL singleton engine or direct llama-cpp.
    """

    def __init__(
        self,
        model: str = "Huihui-Qwen3.5-4B-abliterated.Q4_K_M.gguf",
        disable_thinking: bool = True,
        unload_after_run: bool = True,
        **kwargs
    ):
        super().__init__(api_base="", api_key="", model=model)
        self.type = "qwenvl"
        self.disable_thinking = disable_thinking
        self.unload_after_run = unload_after_run
        self.extra_kwargs = kwargs
        self._qwenvl_dir: Optional[Path] = None
        self._engine = None

    def _find_qwenvl_custom_node(self) -> Optional[Path]:
        """Locate ComfyUI-QwenVL custom_node directory."""
        if self._qwenvl_dir is not None and self._qwenvl_dir.exists():
            return self._qwenvl_dir

        candidate_names = [
            "ComfyUI-QwenVL",
            "ComfyUI_QwenVL",
            "comfyui-qwenvl",
            "qwenvl",
            "Comfyui-QwenVL",
            "Comfyui_QwenVL"
        ]

        def _is_valid_qwenvl_node(p: Path) -> bool:
            return p.exists() and p.is_dir() and (
                (p / "gguf_models.json").exists() or 
                ((p / "py" / "qwenvl_engine.py").exists() and (p / "__init__.py").exists())
            )

        # 1. Check folder_paths if running within ComfyUI
        try:
            import folder_paths
            if hasattr(folder_paths, "base_path") and isinstance(folder_paths.base_path, (str, Path)):
                base_dir = Path(folder_paths.base_path)
                custom_nodes_dir = base_dir / "custom_nodes"
                for c in candidate_names:
                    p = custom_nodes_dir / c
                    if _is_valid_qwenvl_node(p):
                        self._qwenvl_dir = p
                        return p
        except Exception:
            pass

        # 2. Check sys.modules if ComfyUI-QwenVL is already imported
        try:
            for mod_name, mod in list(sys.modules.items()):
                if not mod or not hasattr(mod, "__file__") or not mod.__file__:
                    continue
                if "qwenvl" in mod_name.lower() and not mod_name.startswith("test_") and "minimax" not in mod_name.lower():
                    mod_dir = Path(mod.__file__).resolve().parent
                    if _is_valid_qwenvl_node(mod_dir):
                        self._qwenvl_dir = mod_dir
                        return mod_dir
        except Exception:
            pass

        # 3. Dynamic search roots based on script location, interpreter location, and drive anchor
        roots = set(Path(__file__).resolve().parents)
        roots.update(Path(sys.executable).resolve().parents)
        anchor = Path(__file__).resolve().anchor
        if anchor:
            roots.add(Path(anchor) / "ComfyUI")
        roots.add(Path("C:/ComfyUI"))

        for parent in roots:
            if not parent.exists():
                continue
            for c in candidate_names:
                for p in [
                    parent / c,
                    parent / "custom_nodes" / c,
                    parent / "ComfyUI" / "custom_nodes" / c,
                    parent / "ComfyUI" / "ComfyUI" / "custom_nodes" / c,
                ]:
                    if _is_valid_qwenvl_node(p):
                        self._qwenvl_dir = p
                        py_dir = p / "py"
                        if py_dir.exists() and str(py_dir) not in sys.path:
                            sys.path.append(str(py_dir))
                        return p

        return None

    def is_available(self) -> bool:
        """Check if ComfyUI-QwenVL custom node is installed and available."""
        return self._find_qwenvl_custom_node() is not None

    def _get_models_dir(self) -> Path:
        """Find the root models directory for ComfyUI."""
        try:
            import folder_paths
            if hasattr(folder_paths, "models_dir") and isinstance(folder_paths.models_dir, (str, Path)):
                p = Path(folder_paths.models_dir)
                if p.exists():
                    return p
        except Exception:
            pass

        # Dynamic search roots
        roots = set(Path(__file__).resolve().parents)
        roots.update(Path(sys.executable).resolve().parents)
        anchor = Path(__file__).resolve().anchor
        if anchor:
            roots.add(Path(anchor) / "ComfyUI")
        roots.add(Path("C:/ComfyUI"))

        for parent in roots:
            if not parent.exists():
                continue
            for cand in [
                parent / "models",
                parent / "ComfyUI" / "models",
                parent / "ComfyUI" / "ComfyUI" / "models",
            ]:
                if cand.exists() and cand.is_dir():
                    return cand

        return Path("models")

    def _load_full_catalog_dict(self) -> Tuple[Dict[str, Any], str]:
        """
        Parses all catalog JSONs from ComfyUI-QwenVL (gguf_models.json, hf_models.json, and custom_models.json).
        Returns: (flattened_models_dict, base_dir)
        """
        flattened: Dict[str, Any] = {}
        base_dir = "LLM/GGUF"
        qwenvl_path = self._find_qwenvl_custom_node()
        if not qwenvl_path:
            return flattened, base_dir

        def _parse_repos(repos: dict, target_dict: dict, seen_names: set, overwrite: bool = False, default_format: str = "gguf"):
            if not isinstance(repos, dict):
                return
            for repo_key, repo in repos.items():
                if not isinstance(repo, dict):
                    continue
                author = repo.get("author") or repo.get("publisher") or ""
                repo_name = repo.get("repo_name") or repo_key
                repo_id = repo.get("repo_id") or (f"{author}/{repo_name}" if author and repo_name else repo_key)
                alt_repo_ids = repo.get("alt_repo_ids") or []
                defaults = repo.get("defaults") or {}
                mmproj_file = repo.get("mmproj_file")
                model_files = repo.get("model_files") or []

                if model_files:
                    for model_file in model_files:
                        fname = Path(model_file).name
                        display = fname
                        if display in seen_names and not overwrite:
                            display = f"{display} ({repo_key})"
                        seen_names.add(display)
                        target_dict[display] = {
                            **defaults,
                            "author": author,
                            "repo_dirname": repo_name,
                            "repo_id": repo_id,
                            "alt_repo_ids": alt_repo_ids,
                            "filename": fname,
                            "mmproj_filename": mmproj_file,
                            "format": "gguf",
                        }
                else:
                    # HuggingFace / Transformers format repo
                    display = repo_key
                    if display in seen_names and not overwrite:
                        display = f"{display} (HF)"
                    seen_names.add(display)
                    target_dict[display] = {
                        **defaults,
                        "author": author,
                        "repo_dirname": repo_name,
                        "repo_id": repo_id,
                        "alt_repo_ids": alt_repo_ids,
                        "filename": repo_id or repo_key,
                        "mmproj_filename": None,
                        "format": "hf",
                    }

        try:
            seen_names = set()
            # 1. GGUF Catalog
            gguf_json = qwenvl_path / "gguf_models.json"
            if gguf_json.exists():
                with open(gguf_json, "r", encoding="utf-8") as f:
                    gdata = json.load(f) or {}
                base_dir = gdata.get("base_dir") or base_dir
                for cat in ["qwenVL_model", "Qwen_model", "models"]:
                    if cat in gdata:
                        _parse_repos(gdata[cat], flattened, seen_names, default_format="gguf")

            # 2. HF / Transformers Catalog
            hf_json = qwenvl_path / "hf_models.json"
            if hf_json.exists():
                with open(hf_json, "r", encoding="utf-8") as f:
                    hdata = json.load(f) or {}
                for cat in ["hf_vl_models", "hf_text_models", "hf_models"]:
                    if cat in hdata:
                        _parse_repos(hdata[cat], flattened, seen_names, default_format="hf")

            # 3. User Custom Models Catalog (highest priority)
            custom_json = qwenvl_path / "custom_models.json"
            if custom_json.exists():
                with open(custom_json, "r", encoding="utf-8") as f:
                    cdata = json.load(f) or {}
                for cat in ["gguf_models", "gguf_vl_models", "gguf_text_models"]:
                    if cat in cdata:
                        _parse_repos(cdata[cat], flattened, seen_names, overwrite=True, default_format="gguf")
                for cat in ["hf_models", "hf_vl_models", "hf_text_models"]:
                    if cat in cdata:
                        _parse_repos(cdata[cat], flattened, seen_names, overwrite=True, default_format="hf")

        except Exception as e:
            logger.debug(f"[H3-Promptor] Catalog load error: {e}")

        return flattened, base_dir

    def _find_model_file_on_disk(self, filename: str, author: str = "", repo_dirname: str = "", format_type: str = "gguf") -> Tuple[bool, Optional[Path], float]:
        """
        Checks whether a specific GGUF or HF Transformers model exists on disk.
        Returns: (downloaded: bool, file_path: Optional[Path], size_mb: float)
        """
        if not filename:
            return False, None, 0.0

        models_root = self._get_models_dir()
        gguf_root = models_root / "LLM" / "GGUF"

        # If it's a GGUF model
        if format_type == "gguf" or filename.lower().endswith(".gguf"):
            fname = Path(filename).name
            # 1. Target author / repo dir
            if author or repo_dirname:
                target = gguf_root / author / repo_dirname / fname
                if target.exists() and target.is_file():
                    size_mb = round(target.stat().st_size / (1024 * 1024), 1)
                    return True, target, size_mb

            # 2. Check standard search locations
            search_dirs = [
                gguf_root,
                models_root / "llm" / "GGUF",
                models_root / "LLM",
                models_root / "llm",
            ]
            for sdir in search_dirs:
                if not sdir.exists():
                    continue
                direct = sdir / fname
                if direct.exists() and direct.is_file():
                    size_mb = round(direct.stat().st_size / (1024 * 1024), 1)
                    return True, direct, size_mb
                try:
                    matches = list(sdir.glob(f"**/{fname}"))
                    if matches and matches[0].is_file():
                        size_mb = round(matches[0].stat().st_size / (1024 * 1024), 1)
                        return True, matches[0], size_mb
                except Exception:
                    pass

        # If it's a HuggingFace / Transformers repo
        else:
            repo_id = filename
            short_name = repo_dirname or repo_id.split("/")[-1]
            hf_dirs = [
                models_root / "LLM" / "transformers" / short_name,
                models_root / "LLM" / "checkpoints" / short_name,
                models_root / "transformers" / short_name,
                models_root / "LLM" / author / short_name if author else None,
                Path.home() / ".cache" / "huggingface" / "hub" / f"models--{repo_id.replace('/', '--')}",
            ]
            for hdir in hf_dirs:
                if hdir and hdir.exists() and hdir.is_dir():
                    try:
                        total_bytes = sum(f.stat().st_size for f in hdir.glob("**/*") if f.is_file())
                        size_mb = round(total_bytes / (1024 * 1024), 1)
                        return True, hdir, size_mb
                    except Exception:
                        return True, hdir, 0.0

        return False, None, 0.0

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Returns full list of available GGUF models (50+ models) with accurate download status.
        Downloaded models are sorted to the top.
        """
        catalog_dict, _ = self._load_full_catalog_dict()
        models = []
        seen_filenames = set()

        # 1. Process all catalog entries
        for key, entry in catalog_dict.items():
            fname = entry.get("filename") or key
            if not fname or ("mmproj" in fname.lower()) or fname in seen_filenames:
                continue
            seen_filenames.add(fname)

            author = entry.get("author", "")
            repo_dirname = entry.get("repo_dirname", "")
            format_type = entry.get("format", "gguf")
            downloaded, fpath, size_mb = self._find_model_file_on_disk(fname, author, repo_dirname, format_type)

            is_vlm = ("vl" in fname.lower()) or ("vision" in fname.lower()) or (entry.get("mmproj_filename") is not None)
            models.append({
                "id": fname,
                "name": fname,
                "format": format_type,
                "type": "vlm" if is_vlm else "llm",
                "downloaded": downloaded,
                "size_mb": size_mb,
                "file_path": str(fpath) if fpath else "",
                "author": author,
                "repo": repo_dirname,
            })

        # 2. Also scan physical disk for any extra .gguf models not in catalog
        models_root = self._get_models_dir()
        gguf_root = models_root / "LLM" / "GGUF"
        if gguf_root.exists():
            for gfile in gguf_root.glob("**/*.gguf"):
                fname = gfile.name
                if ("mmproj" in fname.lower()) or fname in seen_filenames:
                    continue
                seen_filenames.add(fname)
                size_mb = round(gfile.stat().st_size / (1024 * 1024), 1)
                is_vlm = ("vl" in fname.lower()) or ("vision" in fname.lower())
                models.append({
                    "id": fname,
                    "name": fname,
                    "type": "vlm" if is_vlm else "llm",
                    "downloaded": True,
                    "size_mb": size_mb,
                    "file_path": str(gfile),
                    "author": "Local",
                    "repo": "Custom",
                })

        # Sort: downloaded first, then alphabetically
        models.sort(key=lambda m: (not m["downloaded"], m["name"].lower()))
        return models

    def is_available(self) -> bool:
        """Check if local LLM custom node is installed."""
        return self._find_qwenvl_custom_node() is not None

    def _get_engine(self) -> Any:
        """Instantiate singleton QwenVLEngine and ensure catalog is fully populated."""
        if self._engine is not None:
            return self._engine

        qwenvl_path = self._find_qwenvl_custom_node()
        if not qwenvl_path:
            return None

        models_root = self._get_models_dir()

        # Guarantee folder_paths.models_dir is defined for standalone WebUI environment
        import types
        if "folder_paths" not in sys.modules or not getattr(sys.modules["folder_paths"], "models_dir", None):
            fp = sys.modules.get("folder_paths") or types.ModuleType("folder_paths")
            fp.models_dir = str(models_root)
            fp.base_path = str(models_root.parent)
            sys.modules["folder_paths"] = fp
        else:
            try:
                import folder_paths
                if not folder_paths.models_dir or not Path(folder_paths.models_dir).exists():
                    folder_paths.models_dir = str(models_root)
            except Exception:
                pass

        py_dir = qwenvl_path / "py"
        if py_dir.exists() and str(py_dir) not in sys.path:
            sys.path.insert(0, str(py_dir))

        try:
            from qwenvl_engine import QwenVLEngine  # type: ignore
            self._engine = QwenVLEngine.get_instance() if hasattr(QwenVLEngine, "get_instance") else QwenVLEngine()

            # Ensure QwenVLEngine catalog has all categories loaded
            catalog_dict, base_dir = self._load_full_catalog_dict()
            if self._engine and hasattr(self._engine, "catalog"):
                self._engine.catalog = {"base_dir": base_dir, "models": catalog_dict}
                # Prevent reload_catalog from wiping models
                def safe_reload():
                    cat, b_dir = self._load_full_catalog_dict()
                    self._engine.catalog = {"base_dir": b_dir, "models": cat}
                self._engine.reload_catalog = safe_reload

            return self._engine
        except Exception as e:
            logger.debug(f"[H3-Promptor] QwenVLEngine initialization error: {e}")

        return None

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        base64_images: Optional[List[Any]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Execute local LLM / VLM generation.
        Handles text expansion and multimodal vision reasoning with strict input normalization.
        """
        target_model = model or self.model
        qwenvl_path = self._find_qwenvl_custom_node()
        if not qwenvl_path:
            err_msg = (
                "[Local LLM Error] ComfyUI-QwenVL custom node not found. "
                "Please install ComfyUI-QwenVL from ComfyUI Manager to use local GGUF models."
            )
            log_error(err_msg)
            return LLMResponse(content="", model=target_model, error=err_msg)

        # 1. Normalize prompt and images
        clean_user_message, clean_images = normalize_inputs(user_message, base64_images)

        # 2. Check if model is downloaded
        downloaded, fpath, _ = self._find_model_file_on_disk(target_model)
        if not downloaded:
            # Check if target_model is a catalog display key
            catalog_dict, _ = self._load_full_catalog_dict()
            if target_model in catalog_dict:
                entry = catalog_dict[target_model]
                fname = entry.get("filename")
                if fname:
                    downloaded, fpath, _ = self._find_model_file_on_disk(fname, entry.get("author", ""), entry.get("repo_dirname", ""))
                    if downloaded:
                        target_model = fname

        if not downloaded:
            err_msg = (
                f"[Local LLM] Model '{target_model}' is not downloaded yet. "
                f"Please download it via ComfyUI-QwenVL Downloader or place the .gguf file into models/LLM/GGUF/."
            )
            log_error(err_msg)
            return LLMResponse(content="", model=target_model, error=err_msg)

        engine = self._get_engine()
        if engine is None:
            err_msg = "[Local LLM Error] Failed to initialize QwenVLEngine runtime."
            log_error(err_msg)
            return LLMResponse(content="", model=target_model, error=err_msg)

        # Ensure model key exists in engine catalog
        if hasattr(engine, "catalog") and "models" in engine.catalog:
            models_dict = engine.catalog["models"]
            if target_model not in models_dict:
                for k, v in models_dict.items():
                    if isinstance(v, dict) and v.get("filename") == target_model:
                        target_model = k
                        break

        try:
            log_info(f"Local LLM inference → model={target_model} | temp={temperature} | images={len(clean_images)}")
            response_text = ""

            if clean_images and len(clean_images) > 0:
                # Multimodal Vision analysis using standard OpenAI image_url payload format
                llm = engine._load_gguf_model(target_model)
                user_content = [{"type": "text", "text": clean_user_message or "Describe this image in detail."}]
                for b64 in clean_images:
                    user_content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ]
                result = llm.create_chat_completion(
                    messages=messages,
                    max_tokens=int(max_tokens),
                    temperature=float(temperature),
                    stop=["<|im_end|>", "<|im_start|>"]
                )
                choices = result.get("choices") or []
                response_text = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
            else:
                # Pure text prompt expansion
                response_text = engine.run_prompt_enhancement(
                    prompt_text=clean_user_message,
                    system_prompt=system_prompt,
                    model_name=target_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

            # Strip thinking tags if requested
            if getattr(self, "disable_thinking", True) and response_text:
                import re
                response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()

            log_info(f"Local LLM response ← {len(response_text)} chars")
            return LLMResponse(
                content=response_text,
                model=target_model,
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            )

        except Exception as e:
            err_msg = f"[Local LLM Inference Error] {str(e)}"
            log_error(err_msg)
            return LLMResponse(content="", model=target_model, error=err_msg)

    def unload(self) -> None:
        """Release resident GGUF model and free CUDA VRAM."""
        if not getattr(self, "unload_after_run", True):
            log_info("Local LLM unload skipped (unload_after_run is disabled).")
            return

        try:
            engine = self._engine
            if engine is None and self.is_available():
                try:
                    from qwenvl_engine import QwenVLEngine  # type: ignore
                    if hasattr(QwenVLEngine, "_instance") and QwenVLEngine._instance is not None:
                        engine = QwenVLEngine._instance
                except Exception:
                    pass

            if engine is not None:
                if hasattr(engine, "llm") and engine.llm is not None:
                    try:
                        if hasattr(engine.llm, "close"):
                            engine.llm.close()
                    except Exception as e:
                        logger.debug(f"[H3-Promptor] Error closing Llama instance: {e}")
                    engine.llm = None

                if hasattr(engine, "chat_handler") and engine.chat_handler is not None:
                    try:
                        if hasattr(engine.chat_handler, "close"):
                            engine.chat_handler.close()
                        stack = getattr(engine.chat_handler, "_exit_stack", None)
                        if stack is not None and hasattr(stack, "close"):
                            stack.close()
                    except Exception:
                        pass
                    engine.chat_handler = None

                if hasattr(engine, "clear"):
                    try:
                        engine.clear()
                    except Exception:
                        pass

                self._engine = None

            log_info("Local LLM (QwenVL GGUF) unloaded successfully.")
        except Exception as e:
            log_warning(f"Error while unloading Local LLM: {e}")
        finally:
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            try:
                from comfy import model_management
                model_management.soft_empty_cache()
            except Exception:
                pass


# Backward compatibility alias
QwenVLProvider = LocalLLMProvider


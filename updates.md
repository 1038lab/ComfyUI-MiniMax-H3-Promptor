# ComfyUI-Minimax-H3-Promptor Update Log

---

## Release Notes: v1.1.0

### Infinite Dynamic Sockets (ComfyAPI v3 Autogrow)
- **Limitless scaling**: Refactored the `H3_Vision_Analyzer` to completely utilize ComfyUI's native API v3 `Autogrow` inputs. The rigid 4-image limit is gone. Users can now infinitely chain as many `<Picture>` and `<Video>` references as their ComfyUI can handle without cluttering the screen with unused ports.

### Unprecedented Fine-Grained Prompt Overrides
- **Laser-focused Control**: Added a powerful multi-line text widget (`custom_prompt_override`) to the Vision Analyzer. By typing `<Picture 2>: focus entirely on lighting` or `image_3: describe the sword only`, users can surgically override the Vision LLM instructions for specific frames, while allowing all unmentioned media to intelligently fall back to the global analysis modes.

### Invisible VRAM Unloading & Management
- **Seamless Local Hosting**: Optimizing for 16GB VRAM set-ups, the explicit VRAM UI toggle has been replaced with invisible background logic. When selecting local providers like `ollama`, the node automatically wraps execution in `model_management.unload_all_models()` and `soft_empty_cache()`, preventing the user from ever seeing OOM errors when transitioning from LLM analysis to actual H3 video generation.

### Core Prompt Architecture Upgrade & De-Patching (The "Clean Blueprint" Update)
- **Zero-Hallucination Inline Tagging**: We entirely refactored the prompt compilation process. Previously, LLMs were forbidden from using `<Picture X>` tags, leading to severe tag parsing conflicts. Now, the internal pipeline explicitly calculates available visual anchors and seamlessly forces the LLM to embed these tags *directly into the narrative action lines*, perfectly mimicking Official Minimax H3 documentation.
- **Flawless 6-Part Output Integration**: The `H3_Promptor` no longer relies on complex regex fallbacks. It uses a pristine Python string-builder sequence to accurately stack the mandatory 6-part schema (`subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`) exactly as HuggingFace mandates.
- **Audio Routing Fix**: Patched a fatal loop gap where Audio-to-Video and Image-to-Audio pipelines were accidentally being ignored by the detector.
- **Sequential Multi-Modal Processing**: The Vision Analyzer now processes multiple images and videos sequentially (one at a time) rather than in a batch. This wholly prevents API request failures from downstream proxies limiting token structures, and eliminates VLM image-confusion during processing.

### "Auto" Intuitive Media Routing
- **Smart UX Dropdowns**: We abandoned the rigid `0` integer sliders for media counts. The UI now features intelligent Dropdown menus defaulting to `"Auto"`. When disconnected, it stays at 0 (perfect for Text-to-Video). The moment a Vision Analyzer is attached, "Auto" (or any manual number) is effortlessly overridden by the underlying engine for flawless multi-modal stability.

### Millisecond Timestamp Alignment
- **Automated Precision**: For multi-image setups (FL2VA) or time-sensitive inputs, the system now mathematically calculates precise cuts and first/last frame alignments based on your exact video duration.

### Dynamic Word Budget
- **Smarter Length Control**: The prompt builder now calculates an optimal word allowance depending on the target duration of your video. This actively prevents the LLM from over-describing short clips and ensures concise, highly-effective action descriptions.

### Strict Audio/Music Separation
- **Independent Sound Tracks**: All audio-related instructions are now forcefully extracted and formatted into their dedicated environment (Audio) and non-diegetic (Music) parameters, ensuring clean sound generation without mixed directives.

### Official Token Compatibility
- **Full Latent Binding Support**: Replaced legacy `Image1` style tags with the official `<Picture 1>` and `<Video 1>` tokens. This ensures flawless cross-attention injection and perfect compatibility across all ComfyUI MiniMax ecosystem nodes.

### Comprehensive Documentation
- **Official Master Tutorials**: Created `tutorials.md` and `tutorials_zh.md`, replacing heavy backend code documentation with 9 practical, production-ready Workflow Recipes (including Lip-Sync, Anime Style Transfer, Day-to-Night Morph, and more).

# ComfyUI-Minimax-H3-Promptor Update Log

---

## v1.5.0 (2026/09/03)

### ✍️ All-New MiniMax H3 Manual Prompt Composer (`H3_PromptComposer`)
- **Dedicated Manual Prompt Workshop**: Built specifically for manual cinematic scripting, prompt engineering, and quick shot scaffolding without relying on upstream AI generation.
- **8 Standard Task Mode Scaffolds**: Pre-configured official templates for `T2VA` (Text-to-Video), `I2VA` (Image-to-Video), `FL2VA` (First & Last Frame), `Ref2VA` (Omni / Reference), `V2VA` (Video-to-Video), `L2VA` (Long Take), `A2V` (Audio-to-Video), and `Custom/Blank`. Switching modes automatically loads structured starter templates.
- **Multi-Trigger Smart Autocomplete (`@`, `<`, `[` )**: Type `@`, `<`, or `[` anywhere in the editor (or click the top `+Tag` button) to invoke an interactive floating tag menu at the cursor. Quick keyboard navigation (`Up`/`Down`, `Enter`/`Tab`) to insert canonical `<Picture 1-4>`, `[Shot 1-4]`, `<Subject 1-2>`, `<Video 1>`, `<Audio 1>`, and section headers.
- **Section Scaffolding & Clean Spacing**: Inserting major sections automatically includes standard cinematic descriptions with clean empty-line separation, placing the cursor directly on the next line for continuous writing.
- **Typing & Caret Stability**: Completely eradicated caret jumping glitches upon pressing Enter, ensuring fluid and responsive typing.


https://github.com/user-attachments/assets/3ecc233f-dc5b-4045-88e9-b50fd0050dfb


### ✨ MiniMax H3 Prompt Preview & Edit (`H3_PromptEditor`) & AI Refine System
- **Display Name Update**: Formally upgraded to **`MiniMax H3 Prompt Preview & Edit`** with seamless backward compatibility for existing workflows.
- **Centered Floating Refine Modal Viewport**: Upgraded to an elegant centered frosted-glass modal overlay. Freely refine the entire prompt, selected text, individual shots (`[Shot N]`), individual subjects (`<Subject N>`), or specific sections with adaptive height.
- **Safe In-Modal Preview & 3-State Actions (Discard / Retry / Apply)**: Refined text renders with green highlight preview inside the modal. Click `[ Discard ]` to revert the preview in-place without closing, `[ 🔄 Retry ]` to re-roll from the clean original base, or `[ ✓ Apply ]` to commit to the node.
- **1-Click A/B State Toggle & Restore**: After applying, the node toolbar activates a prominent gold `[ ↩ Restore Original ]` button to instantly revert to the original prompt, and toggle between versions for effortless comparison.
- **Structural & Timestamp Freezing**: Isolated shot headers (`[Shot N: MM:SS.mmm]`) and subject prefixes (`<Subject N> is `) to guarantee timestamps and brackets are never corrupted by LLM hallucinations.
- **Target-Aware Directing & Semantic Transposition**: Tailored prompts for cinematographers (shots), concept artists (subjects), and audio designers (soundscapes/music). Transposes environmental instructions into subject attire/lighting, and gracefully falls back to cinematic polish on nonsensical inputs.
- **Lock Protection & Live Sync**: Refined live synchronizations and overwrite protection, ensuring locked nodes preserve manual edits while unlocked nodes cleanly receive newly generated prompts.


https://github.com/user-attachments/assets/df45c7de-6932-460f-8414-f8867c6875fb


---

## v1.4.0 (2026/08/26)

### 🤖 ComfyUI-QwenVL (Local / GGUF) Integration (`qwenvl`)
- **Seamless Local Engine Bridge**: Connects directly to `ComfyUI-QwenVL` (or `llama-cpp`) to run local GGUF models for both multimodal visual analysis in `H3_Vision` and director storyboard reasoning in `H3_Promptor`.
- **Auto-Syncing JSON Catalog**: Directly synchronizes with `ComfyUI-QwenVL`'s `custom_models.json` (auto-maintained by its HuggingFace downloader) and `gguf_models.json`, requiring zero manual JSON editing.
- **Opt-in & Zero Extra Bloat**: Pre-configured as disabled (`enabled: false`) by default in the Provider Settings panel, ensuring pure cloud/API users experience zero overhead.
- **One-Click Connection Testing**: The Settings Panel `/minimax-h3/test_connection` endpoint automatically detects the local engine installation and reports catalog model count.

### 🎬 Scene Direction & Creative Control Refinement (`H3_Promptor`)
- **Renamed `description` to `scene_direction`**: Clearer semantic identity designating user plot instructions as the highest creative mandate.
- **Standard English Production Guidance**: Included an instructive English demonstration tooltip showing reference usage (`<Picture 1>`, `<Picture 2>`), transitions, and dialogue (`says: "..."`) while keeping the default input completely empty for AI creative freedom.
- **Full Backward Compatibility**: Seamlessly accepts both `scene_direction` and legacy `description` inputs from existing saved workflows.

### 🛡️ MiniMax H3 Official Prompt Guardrails (PostProcessor)
- **FL2VA Picture Anchor Guardrail**: Guarantees that First & Last Frame tasks (FL2VA) strictly contain `picture 1` (0.00s opening frame) and `picture 2` (ending frame) alignment declarations. If omitted by the LLM, they are automatically injected in English/Chinese to prevent interpolation failures.
- **Dialogue & Voice Acting Tag Injection (`<d>[Language]...</d>`)**: Automatically extracts user-supplied speech/dialogue from descriptions and guarantees it is formatted as `<d>[Language]...</d>` and embedded into the `[Shot 1]` narrative timeline without duplicate nesting.
- **Subject Shorthand Standardization**: Automatically normalizes standalone `S1`~`S20` mentions to the official MiniMax parenthesized format `(S1)`~`(S20)`.
- **Media Filename Sanitization**: Automatically scrubs hallucinated raw media filenames (e.g. `image.png`, `video.mp4`) from final prompts.

### ⚡ Multi-Platform Thinking Mode Control (Reasoning/Thinking)
- **Thinking Control Toggle (`Disable Thinking (Fast)`)**: Added a dedicated switch in the Settings Panel for OpenAI-compatible, Gemini, and Anthropic providers.
- **SiliconFlow & DeepSeek / Qwen3 / GLM-5**: Injects `"enable_thinking": False` into API request payloads, preventing token budget exhaustion and timeouts.
- **Google Gemini (2.5 / 3.x / Flash)**: Injects `"thinkingConfig": {"thinkingBudget": 0}` to bypass thinking chains and output production-ready prompts instantly.
- **Anthropic Claude**: Preserves native zero-thinking standard mode, allowing full temperature customization.
- **Ollama**: Dynamic UI hides the toggle for Ollama, preventing 400 Bad Request errors while sanitizing `<think>` tags via post-processing.

### 🔌 MiniMax H3 Vision
- **Input Connector Support**: Integrated `H3_Vision` node featuring `io.Autogrow` input connectors for IMAGE, VIDEO, and AUDIO. Pipeline media from other nodes directly into the Vision node while retaining full drag & drop upload functionality.
- **Drag-to-Reorder Media Pipeline**: Freeform card reordering in the Upload Area with strict category partitioning (`All Images -> All Videos -> All Audios`). Drag and drop cards (both connected and uploaded) to reorder `<Picture 1>`, `<Picture 2>`, `<Video 1>`, etc., seamlessly synchronized with backend tensor batching.
- **Live Upstream Media Previews**: Connected inputs automatically display actual image/video thumbnails and clean labels with `🔗 linked` badges.
- **Port Management**: Automatically trims excess unused empty input slots when media capacity is reached (9 images, 3 videos, 3 audios).

### 📐 Promptor Length Output
- **New `length` output (INT)**: `H3_Promptor` node outputs a calculated `length` value using the model-required frame alignment formula: `max(5, round(duration × 24))` aligned to `% 17 == 5`.

---

## v1.3.0 (2026/08/18)
Release Notes: (Hollywood AI Director & Full-Reference Architecture)

### 🎬 Major Highlight: The Two-Stage Hollywood AI Director & Screenwriter Engine
- **Two-Stage Directing Pipeline**: Completely overhauled prompt generation from a rushed one-shot output into a rigorous two-stage film production workflow:
  * **Stage 1: Director Blueprint & Global Vibe**: The LLM first acts as a Hollywood Showrunner, analyzing your reference cast and creative intent to establish the world atmosphere, lighting/color palette, character dynamics, and an evenly paced Timeline Beats Plan (e.g. 4 distinct beats for 15s).
  * **Stage 2: Cinematic Storyboard & Dialogue**: Using the approved blueprint, the LLM crafts timed, cohesive shots covering the entire duration (up to 15.0s) without cutting off early.
- **Official Character Dialogue Syntax (`<d>[Language] "..."</d>`)**: Full support for MiniMax H3's official voice acting format: `<Subject N> (SN) [emotion/action] says: <d>[Language] "Spoken dialogue here"</d>`.
- **User Custom Prompt as Supreme Mandate**: When you provide a custom prompt or scene wish, the director engine prioritizes it as the highest creative mandate, choreographing all uploaded actors, vehicles, and props to execute your exact vision.
- **Ensemble Spatial Staging & Continuity**: Multiple references are composed together across Foreground, Midground, and Background layers with smooth transitions (Match on Action, Eyeline Match, Whip Pan).
- **Physical Shot Budgeting (4s-15s)**: Strict pacing rules prevent video flicker by allocating at least 2.5s-4.0s per shot.

### 🌟 All-New Vision Analyzer V2 & Seamless List Expansion
- **Pure Web DOM Drop-Zone Architecture**: Replaced clunky image/video PyTorch input slots with an intuitive in-node HTML/JS drag-and-drop panel. Drag and drop pictures, videos, and audios directly without wiring noodles.
- **Zero-Deformation Native List Expansion (`OUTPUT_IS_LIST`)**: Passes pristine, 100% original-dimension images directly through a List Iteration pipeline. No more cropping, letterboxing, or stretched faces!
- **Streamlined Pure Perception**: Vision analyzer focuses strictly on objective visual perception (outlines, colors, clothing, OCR text), eliminating redundant text synthesis calls and cutting API token consumption and latency by 50%.

### ⚙️ Fine-Tuning & Pipeline Polish
- **Alphabetical Provider & Model Sorting**: The Provider selection dropdowns across nodes are now automatically sorted alphabetically, and your configured default provider is prioritized at the top.
- **Customizable `Max Batch Images` (Sub-Batch Chunking)**: Configure maximum image batch sizes (e.g. 4 images per request) in the Settings Panel to easily comply with strict upstream API request limits without workflow crashes.
- **Batch Chunk Positional Fallback**: Added robust position-based fallback mapping in `ResponseParser`. Even if an upstream VLM re-numbers images starting from 1 in subsequent chunks, keys are mapped to `<Picture 5>`, `<Picture 6>`, etc., with 100% accuracy.
- **Full Token Budgeting for Multi-Reference Scenes**: Removed internal Stage 1 token bottlenecks, dynamically channeling full `max_tokens` (up to 4096 / 8192) to support reasoning models (`agnes-2.5-flash`, etc.) with internal thinking chains when handling up to 9 references.
- **Word-Boundary Regex Entity Detection**: Uses strict word boundaries `\b` and negative lookahead to eliminate false entity classifications (e.g. "tiger-striped bikini" or "cat-ear headband" are correctly tagged as clothing/accessories on a person, not wild animals; "high-performance" never misclassifies as a man).
- **Dynamic Shot Appearance Mapping**: Automatically scans generated storyboard text to map which subjects actually appear in which shots, building 100% compliant `retention_analysis` metadata.
- **Node Appearance & Theme Customization**: Refined sleek dark-theme palette styling for custom nodes (`appearance.js`).

### 🖥️ ComfyUI Real-Time Console Trace
- **Step-by-Step Terminal Execution**: `H3_Promptor` node outputs the final prompt cleanly while printing beautifully styled, phase-by-phase execution banners (Stage 1 Blueprint, Stage 2 Storyboard, Final Assembly) directly to the ComfyUI terminal console for complete transparency!

---

## Release Notes: v1.2.0 (Settings Hub & Core Architecture Overhaul)

### 🌟 Highlight: Native ComfyUI Settings Integration (API Hub)
- **Centralized API Management**: Completely removed the clunky `api_key` and `model_name` input fields from the Node interfaces. We built a beautiful, native-feeling ComfyUI Settings Panel (under the Gear icon -> MiniMax H3 API Settings) to manage all providers in one place globally.
- **Provider Connection Tester**: Added an inline ping-tester directly in the API Settings Panel. Instantly click "Test" to verify if your Base URL and Key are active, completely eliminating workflow mid-generation crashes due to bad auths.
- **Hot-Reload Node Dropdowns**: Disabling a provider via the toggle switch now takes *instant* effect (just refresh the browser with `F5`). There is no longer any need to explicitly reboot the Python ComfyUI server to update Node dropdowns.
- **Native Toggles**: Upgraded the settings UI to feature standard ComfyUI iOS-style visual toggle switches.
- **Streamlined Custom Node UI**: The Python nodes now only ask you to select a `Provider` from a dynamic dropdown (which syncs automatically to your panel) and retain only `temperature` and `max_tokens` for on-the-fly workflow tuning.

### Dynamic Out-of-the-box Config & Hardware Stability
- **Zero-Config Startup**: The auto-generated `config.json` now ships with 6 industry-standard APIs instantly pre-configured: `OpenAI`, `Anthropic`, `Gemini`, `Ollama`, `LlamaCPP`, and `LMStudio`. New users just drop in their Key and go!
- **Anthropic Native Routing**: Cleaned up internal semantics to identify Claude standard as `Anthropic`.
- **Ollama 500 & LLaVA Fixes**: Added critical pre-flight structural fixes for local vision models (like `llama3.2-vision`). It now intelligently folds `system` prompts into the `user` block and aggressively overrides `num_ctx` to dynamically prevent the notorious Ollama 500 VRAM Overload error.
- **Agnostic Proxy Resilience**: Added explicit proxy error HTML response leaks to the error console so users can pinpoint exactly why an external OpenAI-compatible service returned a 503/500 down state.

### Official MiniMax Syntax & Timeline Accuracy
- **I2VA Frame Anchoring**: Added strict `<Picture 1>` zero-second frame anchoring directly into the visual output, ensuring the AI strictly adheres to the exact starting frame before extrapolating motion.
- **Precise Scene Timestamps**: Upgraded the internal template structure to use strict cut times (`[Shot N] At MM:SS.mmm, ...`) instead of floating time ranges, drastically improving timeline stability across multi-shot sequences.

### Full-Reference Programmatic Injection (Phase 2)
- **Automated Summary Block**: The engine now dynamically scans generation intents and pre-loads the precise HuggingFace structure header (`summary:`) with tags like `[keyframe completion]` or `[audio reference]` based directly on the visual node's internal state.
- **Retention & Preservation Analysis**: The prompt compiler now automatically generates the `retention_analysis` metadata block marking visual assets (`<Picture X>`) as `fully_preserved` and matching audio triggers without LLM hallucination.
- **Dynamic Multimodal Budgeting**: Ref2VA and Omni-tasks are incredibly complex. The word budget bounds have been dramatically uncapped (350-500 words minimum) for tasks involving multi-tag usage to ensure high-fidelity scene orchestration.

### Advanced Audio, Speaker Syncing & L2VA
- **Audio-First Token Injection**: For the first time, when connecting audio directly to the `H3_Promptor`, the prompt compiles a dedicated `<Audio N>` referencing token in the `subject_definitions` mapping. The LLM now perfectly syncs physical actions to sound.
- **Stable Dialogue IDs `(Sx)`**: Embedded conversational logic into the prompt pipeline to enforce tight `(S1)`, `(S2)` character speaker ID mapping and clear voiceover tagging.
- **Introducing L2VA (Last Frame Inference)**: Unlocked the highly requested `Last-Frame-to-Video-Audio (L2VA)` task type. Users can now provide a single ending frame, and the `H3_Promptor` will instruct the LLM to choreograph a dynamic, forward-moving narrative that mathematically converges exactly onto the target pose at the very last second of the generation.

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

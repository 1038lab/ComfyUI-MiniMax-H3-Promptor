# 🎬 ComfyUI MiniMax H3-Promptor

A powerful, node-based automation suite for generating cinema-production-grade prompts explicitly formatted for the **MiniMax H3 Video Generation System**.

This project provides a robust, decoupled architecture separating **multimodal visual analysis** from pure **text-based prompt structuring**, allowing for extreme customizability, precise scene description, and low API operating costs.

![ComfyUI MiniMax H3-Promptor](example_workflows/MiniMax-H3-Promptor.jpg)

## V1.3.0 (2026/08/18) 

### (Hollywood AI Director & Full-Reference Architecture)

*   **🎬 Two-Stage Hollywood AI Director & Screenwriter Engine**: Transforms prompt generation into an authentic film production workflow (Stage 1: Director Blueprint & Global Vibe -> Stage 2: Cinematic Storyboard & Dialogue), generating evenly paced 4-beat timelines covering up to 15.0s.
*   **🗣️ Official MiniMax Dialogue & Voice Acting Syntax**: Native support for `<Subject N> (SN) [emotion] says: <d>[Language] "..."</d>` for vivid character voices and live acting.
*   **👑 Custom Prompt as Supreme Mandate**: User creative wishes are prioritized as the highest directive, orchestrating all uploaded cast, vehicles, and props to execute your vision.
*   **🖼️ All-New Vision Analyzer V2 Drop-Zone Panel**: Native HTML/JS drag-and-drop panel right on the node surface; original images pass through zero-deformation `OUTPUT_IS_LIST` list expansion.
*   **⚙️ Pipeline Polish & Fine-Tuning**: Alphabetical provider sorting with smart default pinning, customizable `Max Batch Images` sub-batching, chunk positional fallback, and regex word-boundary entity recognition.

👉 **[Read the full v1.3.0 Release Notes and Detailed Features here (updates.md)](updates.md#v130-20260818)**


## 🎉 What's New in V1.2.0 (Settings Hub & Core Architecture Overhaul)

*   **Global Native Settings Panel**: Manage all LLM providers (including API Keys and Hot-Reload toggles) seamlessly via the native ComfyUI Gear Icon settings.
*   **L2VA Mode & I2VA Frame Anchoring**: Added strict zero-second first-frame anchoring, and the new reverse L2VA mode to conclude exactly on a target pose.
*   **Full-Reference Script Automation**: Programmatically injects exact schema structural tags (`summary:`, `retention_analysis`) and expands LLM word budgets without hallucination in complex multimodal setups.
*   **Audio-First Token Syncing**: Introduces dedicated `<Audio N>` tracking tags and `(Sx)` conversational ID parsing to align lip movements properly to sound inputs.
<img width="50%" alt="minimax-h3-setting" src="https://github.com/user-attachments/assets/81eda3f3-084c-4ac9-9e99-446afa1009dc" />

👉 **[Read the full v1.2.0 Release Notes and Bug Fixes here (updates.md)](updates.md#v120-20260813)**

---

## 🎉 Previous Updates: V1.1.0 (Refined Architecture)

*   **Zero-Hallucination Inline Tagging**: The Prompt LLM now natively embeds `<Picture X>` references directly inside the narrative action lines, guaranteeing 100% compliance with official MiniMax tag-binding requirements.
*   **Sequential Multi-Modal Processing**: Upgraded the Vision Analyzer to process inputs sequentially. This eliminates Multi-Modal LLM context bleeding and guarantees proxy API limits are never exceeded.
*   **Flawless 6-Part Official Syntax Compliance**: Our structural generation has been de-patched. The Promptor now strictly assembles the mandatory 6-part string array (`subject_definitions`, `summary`, `retention`, etc.) in the exact sequence HuggingFace mandates.
*   **Audio Pipeline Fix**: Completely restored routing logic for Native Audio paths (Audio-to-Video and Image-to-Audio).
*   **Custom Node Theming**: Added native UI coloring support for ComfyUI (`appearance.js`).

---

## 🌟 The V1.0.0 Decoupled Architecture

The pipeline consists of two nodes working in tandem to handle extreme complexity without duplicating LLM vision costs:

### 1. `H3_Vision_Analyzer` 👁️
A highly configurable multimodal analysis engine. This node acts as your virtual Director of Photography, analyzing input imagery and video based on explicit presets.
*   **Infinite Dynamic Scaling**: Upgraded to ComfyAPI v3 `io.Autogrow`. You are no longer limited to 4 images. Connect as many Images and Videos as you want seamlessly.
*   **Targeted Custom Overrides**: Use the `custom_prompt_override` box to type rules like `<Picture 2>: Focus entirely on the background`. It will surgically override the global mode for that exact frame!
*   **Invisible Heavy VRAM Management**: Automatically detects when you are using local models like `Ollama` and safely unloads them behind the scenes to preserve VRAM for the actual H3 video generation.
*   **Multilingual Output**: Choose between English and Chinese for the analysis output language.
*   **Outputs**: Produces a structured JSON-backed `vision_context` that is sent to the Promptor node, completely uncoupling image arrays from the final text pipeline.

#### Vision Analyzer Inputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `ref_images` | IMAGE | Connect one or multiple images; dynamically grows infinitely (`image_X`). |
| `ref_videos` | IMAGE | Connect video tensor sequences; dynamically grows (`video_X`). |
| `global_image_mode` | COMBO | Selects the global fallback analysis logic from `vision_prompts.json` for all images. |
| `global_video_mode` | COMBO | Selects the global fallback analysis logic from `vision_prompts.json` for all videos. |
| `custom_prompt_override`| STRING | A multi-line box to surgically override specific media logic. E.g: `<Picture 2>: focus on the lighting`. |
| `output_language` | COMBO | Language for the analysis output (`English` or `Chinese`). |
| `provider` | COMBO | Synchronizes with Settings. Pick `openai`, `anthropic`, `gemini`, `ollama` etc. |
| `temperature` | FLOAT | Sampling temperature. Default `0.2` for precise factual analysis. |
| `max_tokens` | INT | Maximum response tokens (256-8192). |

### 2. `H3_Promptor` 📝
The core structure engine. It operates at blazing speeds because it takes the user's description and the Vision Analyzer's text report to format the final H3 Prompt—meaning **it does not need to repeatedly analyze heavy images.**
### The "Auto" Multimodal Routing System
The `H3_Promptor` uses a highly intelligent backend algorithm to instantly detect your intended generation mode without manual configuration. When left on **Auto**, the system evaluates the number of images, videos, and audio streams present in the `vision_context` and routes the formatting logic automatically:

| Connected Media | Triggered Mode | Description |
|---|---|---|
| None | **T2V** | Pure Text-to-Video. No physical media anchors are generated. |
| 1 Image | **I2V** | First-Frame conditioning. The provided image acts as the 0.00-second start state. |
| 1 Image + Audio | **I2VA** | Image-to-Video with Audio reference. Perfect for lip-syncing a portrait. |
| 1 Image (Manual) | **L2VA** | Last-Frame Anchor. Select `L2VA` manually in the dropdown to reverse-engineer a video that ends exactly on your image. |
| 2 Images | **FL2VA** | First & Last Frame. Calculates the exact duration boundary to smoothly transition from state A to state B. |
| 3+ Images / Any + Video | **Ref2VA** | Omni-Reference. Uses dynamic high-budget word allowances to construct complex multi-angle or object retention scenes. |
| 1 Video | **V2V** | Video-to-Video editing. Inherits motion properties completely. |
| Audio only | **A2V** | Audio-to-Video. Directs characters to speak or dance exclusively based on the target audio file. |

*(If you wish to force a mode, such as **L2VA** which requires 1 image but acts as the ending frame, simply select it from the dropdown to override the Auto system).*

*   **Language Selection**: Output the final cinematic prompt strictly in **Chinese (简体中文)** or **English**, seamlessly bridging international setups.
*   **Duration Syncing**: Define how long your video is (4-15s), and the LLM will rigorously pace the structural shot-list to match that exact timeframe at 24FPS.

#### Promptor Inputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `task_type` | COMBO | The generation mode (`Auto`, T2V, I2V, FL2VA, etc.). Auto is recommended. |
| `description` | STRING | Your main creative description of the video scene. |
| `duration` | INT | Desired video length (4-15 seconds). |
| `vision_context` | STRING | Connect the output of `H3_Vision_Analyzer` here. Leave unconnected for pure T2V. |
| `output_language` | COMBO | Output the resulting prompt in `English` or `Chinese`. |
| `provider` | COMBO | Synchronizes with Settings. Pick `openai`, `anthropic`, `gemini`, `ollama` etc. |
| `temperature` | FLOAT | Sampling temperature. Default `0.7` for creative writing. |
| `max_tokens` | INT | Maximum response tokens (256-8192). |

---

## 🔌 Supported LLM Providers & Local Model Setup

Both cloud and local offline providers are supported natively. **Ollama** and **LM Studio** are enabled by default for zero-friction local workflows!

| Provider | Type | Default Endpoint | Default Model | Notes / Auth |
|---|---|---|---|---|
| **LM Studio** | Local (`openai`) | `http://localhost:1234/v1` | Loaded Model | Enabled by default; no API key required |
| **Ollama** | Local (`ollama`) | `http://localhost:11434` | `llama3.2` / `llama3.2-vision` | Enabled by default; auto-unloads VRAM |
| **OpenAI** | Cloud (`openai`) | `https://api.openai.com/v1` | `gpt-5` / `gpt-4o` | Requires OpenAI API Key |
| **Gemini** | Cloud (`gemini`) | Google AI Studio | `gemini-2.5-flash` | Requires Google AI API Key |
| **Anthropic** | Cloud (`claude`) | Anthropic API | `claude-3-5-sonnet-latest` | Requires Anthropic API Key |

### 💻 Running Completely Offline / Locally (LM Studio & Ollama)
1. **LM Studio**:
   - Start LM Studio and load any Vision LLM (e.g. Qwen2-VL, MiniCPM-V, Llama-3.2-Vision).
   - Start the local server in LM Studio (default port `1234`).
   - In ComfyUI, simply choose `lmstudio` from the `provider` dropdown on the node.
2. **Ollama**:
   - Run `ollama serve` and pull your model (e.g., `ollama run llama3.2-vision`).
   - Select `ollama` from the `provider` dropdown. (Automatic VRAM clearing is handled internally to save GPU memory for video generation).
3. **Settings Hub**:
   - Click the **Gear Icon** (Settings) in ComfyUI -> **MiniMax H3** to graphically adjust ports, toggle providers on/off, or add custom OpenAI-compatible endpoints (DeepSeek, Groq, OpenRouter, SiliconFlow, llama.cpp).
   - Alternatively, edit `config.json` in the custom node directory.

> All providers support multimodal image & video analysis in `H3_Vision_Analyzer`.


---

## 🌟 Workflow Recipes & Tutorials

Want to learn how to do **Lip-Syncing, Character Interaction, Video Style Transfer**, or **High-End Product Commercials**?

👉 **[Click here to view the Master Workflow Tutorials](tutorials.md)**
👉 **[点击这里查看 8 大经典实战工作流教程 (中文版)](tutorials_zh.md)**

---

## 🚀 Installation & Setup

1. **Clone the Repository**:
   Clone this repo into your `ComfyUI/custom_nodes` folder:
   ```bash
   cd ComfyUI/custom_nodes
   git clone https://github.com/1038lab/Comfyui-Minimax-H3-Promptor.git
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configuration (Native)**:
   Once ComfyUI launches, click the **Gear Icon** (Settings) and navigate to **MiniMax H3**. From there, you can Add Custom Providers, enter API Base URLs, and set Default Models through the graphical interface natively!

---

## 🎨 Modding & Customization

### The `vision_prompts.json` Ecosystem
Upon the first boot of V1.0.0, a `vision_prompts.json` file is generated in the root folder. You can open this JSON file to modify or add completely new analysis strategies:

```json
{
    "image_prompts": {
        "Subject / Identity": "Focus exclusively on describing the main subject's appearance...",
        "Color Palette & Texture": "Focus exclusively on the dominating colors..."
    }
}
```
Add your own custom keys — changes take effect after a ComfyUI restart.

### The System Templates
Want to alter how the backend formats the `[SCENE]` blocks?
Open the `templates/` directory. The `system_base.txt` controls global rules, while the other text files (e.g., `i2v.txt`) control the exact formatting structure based on the mode you selected.

---

##  Credits & Resources

*   Developed by **[1038lab](https://github.com/1038lab)**.
*   **MiniMax H3 Specifications**: Designed specifically to interface with the core structural requirements given by MiniMax.

## License

GPL-3.0

# 🎬 ComfyUI MiniMax H3-Promptor (V1.0.0)

A powerful, node-based automation suite for generating cinema-production-grade prompts explicitly formatted for the **MiniMax H3 Video Generation System**.

This project provides a robust, decoupled architecture separating **multimodal visual analysis** from pure **text-based prompt structuring**, allowing for extreme customizability, precise scene description, and low API operating costs.

---

## 🌟 The V1.0.0 Decoupled Architecture

The pipeline consists of two nodes working in tandem to handle extreme complexity without duplicating LLM vision costs:

### 1. `H3_Vision_Analyzer` 👁️
A highly configurable multimodal analysis engine. This node acts as your virtual Director of Photography, analyzing input imagery and video based on explicit presets.
*   **4 Image Slots + 1 Video Slot**: Analyze up to 4 images and a batch of video keyframes simultaneously.
*   **JSON-Backed Presets**: Every media slot features a dynamic dropdown populated by an auto-generated `vision_prompts.json` file. You can instruct the VLM to analyze *only* the character, *only* the lighting, or the *entire composition*. 
*   **Add Your Own Options**: You can add unlimited new analysis strategies by simply editing the `vision_prompts.json` file in the node directory. The dropdowns update on restart!
*   **Multilingual Output**: Choose between English and Chinese for the analysis output language.
*   **Outputs**: Produces a structured text-based `vision_context` that is sent to the Promptor node, completely uncoupling image arrays from the final text pipeline.

#### Vision Analyzer Inputs
| Parameter | Type | Description |
|-----------|------|-------------|
| `image_ref_1..4` | IMAGE | Image tensors to analyze. |
| `mode_1..4` | COMBO | Selects the specific analysis logic from `vision_prompts.json` for each image. |
| `video_ref` | IMAGE | Video batch tensor. Up to 4 keyframes are extracted and analyzed. |
| `mode_video` | COMBO | Video-specific analysis logic. |
| `output_language` | COMBO | Language for the analysis output (`English` or `Chinese`). |
| `provider` | COMBO | `openai`, `ollama`, `gemini`, or `claude`. |
| `api_key` | STRING | API Key override (leaves `config.json` untouched). |
| `model_name` | STRING | VLM Model override (e.g. `gpt-4o`, `gemini-2.5-flash`). |
| `temperature` | FLOAT | Sampling temperature. Default `0.2` for precise factual analysis. |
| `max_tokens` | INT | Maximum response tokens (256-8192). |

### 2. `H3_Promptor` 📝
The core structure engine. It operates at blazing speeds because it takes the user's description and the Vision Analyzer's text report to format the final H3 Prompt—meaning **it does not need to repeatedly analyze heavy images.**
*   **Intelligent Cross-Node `Auto` Detection**: Even though this node no longer connects to images directly, the `H3_Vision_Analyzer` invisibly stamps a hidden `[MEDIA_SIGNATURE]` encoded with your exact inputs. The `H3_Promptor` silently parses this signature and automatically selects the correct generation mode:

| Vision Inputs | Auto-Detected Mode |
|---|---|
| No media connected | **T2V** — Text-to-Video |
| 1 image | **I2V** — Image-to-Video |
| 2 images | **FL2VA** — First & Last Frame |
| 3-4 images | **Ref2VA** — Omni Reference |
| Video only | **V2V** — Video-to-Video |
| Any images + Video | **Ref2VA** — Omni Reference |

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
| `provider` | COMBO | `openai`, `ollama`, `gemini`, or `claude`. |
| `api_key` | STRING | API Key override. |
| `model_name` | STRING | Model override (e.g. `gpt-4o`, `claude-sonnet-4-20250514`). |
| `temperature` | FLOAT | Sampling temperature. Default `0.7` for creative writing. |
| `max_tokens` | INT | Maximum response tokens (256-8192). |

---

## 🔌 Supported LLM Providers

All 4 providers are implemented as **independent, native API integrations** — no wrappers, no compatibility layers. Each provider file is fully self-contained for easy maintenance.

| Provider | File | API Format | Default Model | Auth Method |
|---|---|---|---|---|
| **OpenAI** | `provider_openai.py` | `/v1/chat/completions` | `gpt-4o` | `Bearer` Token |
| **Ollama** | `provider_ollama.py` | Ollama `/api/chat` | `llama3.1` | None (local) |
| **Gemini** | `provider_gemini.py` | Google `generateContent` | `gemini-2.5-flash` | URL `?key=` param |
| **Claude** | `provider_claude.py` | Anthropic Messages API | `claude-sonnet-4-20250514` | `x-api-key` Header |

> All providers support multimodal (image) inputs for the Vision Analyzer node.

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
3. **Configuration (`config.json`)**:
   On first load, the node will auto-create a `config.json` inside its folder. Open it and fill in your API keys:
   ```json
   {
     "providers": {
       "openai":  { "api_key": "sk-..." },
       "gemini":  { "api_key": "AIza..." },
       "claude":  { "api_key": "sk-ant-..." }
     }
   }
   ```
   > You can also override API keys directly on each node's UI without editing config.json.

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

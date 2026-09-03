"""
ComfyUI-Minimax-H3-Promptor
H3 Prompt Composer node — manually compose, scaffold, and tag MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

try:
    from comfy_api.latest import io
except ImportError:
    class _DummyIO:
        class ComfyNode: pass
        class NodeOutput:
            def __init__(self, *args, **kwargs): self.args = args
        class Schema:
            def __init__(self, *args, **kwargs): pass
        class _Field:
            @classmethod
            def Input(cls, *args, **kwargs): return None
            @classmethod
            def Output(cls, *args, **kwargs): return None
        String = Combo = _Field
    io = _DummyIO()

MODES = [
    "T2VA (Text to Video & Audio)",
    "I2VA (Image to Video & Audio)",
    "FL2VA (First & Last Frame)",
    "Ref2VA (Omni / Reference)",
    "V2VA (Video to Video)",
    "L2VA (Live Action / Extended)",
    "A2V (Audio to Video)",
    "Custom / Blank",
]


class H3_PromptComposer(io.ComfyNode):
    """
    MiniMax H3 Manual Prompt Composer.
    Designed for rapid manual prompt creation with mode-specific template scaffolds,
    real-time syntax highlighting, and an intelligent '@' tag auto-completion popup.
    """
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "🧪AILab/🎬 MiniMax H3-Promptor"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3_PromptComposer",
            display_name="MiniMax H3 Prompt Composer",
            category="🧪AILab/🎬 MiniMax H3-Promptor",
            is_output_node=True,
            inputs=[
                # Mode selector
                io.Combo.Input(
                    "mode",
                    options=MODES,
                    default=MODES[0],
                    tooltip="Select the video generation mode to load standard template scaffolds.",
                ),
                # Internal storage widget: persists edited prompt across workflow save/reload
                io.String.Input(
                    "_composer_prompt",
                    multiline=True,
                    default="",
                    tooltip="Internal storage of composed prompt — do not connect.",
                ),
            ],
            outputs=[
                io.String.Output(
                    "prompt",
                    display_name="PROMPT",
                    tooltip="The composed MiniMax H3 prompt text ready for downstream video generation.",
                ),
            ],
        )

    @classmethod
    def IS_CHANGED(cls, mode: str = MODES[0], _composer_prompt: str = "", **kwargs):
        # Force execution on every run so fresh prompt is always delivered to downstream nodes
        return float("nan")

    @classmethod
    def execute(cls, mode: str = MODES[0], _composer_prompt: str = "", **kwargs) -> dict:
        val = str(_composer_prompt).strip() if _composer_prompt else ""

        return {
            "ui": {
                "prompt": [val],
                "text": [val],
            },
            "result": (val,),
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    OUTPUT_TOOLTIPS = (
        "The composed MiniMax H3 prompt text ready for downstream video generation.",
    )


NODE_CLASS_MAPPINGS = {
    "H3_PromptComposer": H3_PromptComposer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_PromptComposer": "MiniMax H3 Prompt Composer",
}

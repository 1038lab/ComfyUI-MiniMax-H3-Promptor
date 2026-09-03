"""
ComfyUI-Minimax-H3-Promptor
H3 Prompt Editor node — read, highlight, refine, and edit generated prompts.

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
        String = _Field
    io = _DummyIO()


class H3_PromptEditor(io.ComfyNode):
    """
    MiniMax H3 Prompt Preview & Edit.
    Displays the generated prompt with syntax highlighting, allows inline editing,
    one-click AI refinement of individual sections, and lock switch protection.
    """
    OUTPUT_NODE = True
    FUNCTION = "execute"
    CATEGORY = "🧪AILab/🎬 MiniMax H3-Promptor"

    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="H3_PromptEditor",
            display_name="MiniMax H3 Prompt Preview & Edit",
            category="🧪AILab/🎬 MiniMax H3-Promptor",
            is_output_node=True,
            inputs=[
                # Socket input: receives PROMPT from H3_Promptor or upstream nodes
                io.String.Input(
                    "prompt",
                    multiline=True,
                    force_input=True,
                    default="",
                    optional=True,
                    tooltip="Connect the PROMPT output from MiniMax H3 Promptor here.",
                ),
                # Internal storage widget: persists edited prompt across workflow save/reload
                io.String.Input(
                    "_stored_prompt",
                    multiline=True,
                    default="",
                    tooltip="Internal storage — do not connect.",
                ),
            ],
            outputs=[
                io.String.Output(
                    "prompt",
                    display_name="PROMPT",
                    tooltip="The prompt text (original or edited) ready for downstream nodes.",
                ),
            ],
        )

    @classmethod
    def IS_CHANGED(cls, prompt: str = "", _stored_prompt: str = "", **kwargs):
        # Force execution on every run so fresh prompt is always delivered to UI
        return float("nan")

    @classmethod
    def execute(cls, prompt: str = "", _stored_prompt: str = "", **kwargs) -> dict:
        # If prompt arrived via socket, prefer it; otherwise use saved edited prompt
        incoming = str(prompt).strip() if prompt and str(prompt).strip() else ""
        stored = str(_stored_prompt).strip() if _stored_prompt else ""
        value = incoming if incoming else stored

        # Return both standard UI event payload and graph result tuple
        return {
            "ui": {
                "prompt": [value],
                "text": [value],
            },
            "result": (value,)
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    OUTPUT_TOOLTIPS = ("The prompt text (original or edited) ready for downstream nodes.",)


NODE_CLASS_MAPPINGS = {
    "H3_PromptEditor": H3_PromptEditor,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_PromptEditor": "MiniMax H3 Prompt Preview & Edit",
}

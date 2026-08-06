__version__ = "1.0.0"

from .py.h3_promptor import H3_Promptor
from .py.h3_vision_analyzer import H3_Vision_Analyzer

NODE_CLASS_MAPPINGS = {
    "H3_Promptor": H3_Promptor,
    "H3_Vision_Analyzer": H3_Vision_Analyzer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "H3_Promptor": "MiniMax H3 Promptor",
    "H3_Vision_Analyzer": "MiniMax H3 Vision Analyzer",
}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


def _register_routes():
    try:
        from aiohttp import web
        from server import PromptServer

        from .py.model_registry import LOCAL_PROVIDERS, list_provider_models

        @PromptServer.instance.routes.get("/h3_promptor/models")
        async def h3_promptor_models(request):
            provider = request.rel_url.query.get("provider", "").lower()
            if provider not in LOCAL_PROVIDERS:
                return web.json_response({"models": []})
            return web.json_response({"models": list_provider_models(provider)})

    except ImportError:
        pass


_register_routes()

print(
    f"\033[34m[H3-Promptor]\033[0m v\033[93m{__version__}\033[0m | "
    f"\033[93m{len(NODE_CLASS_MAPPINGS)} nodes\033[0m \033[92mLoaded\033[0m"
)

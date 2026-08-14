import json
from server import PromptServer
from aiohttp import web
from .config_manager import get_config_manager

@PromptServer.instance.routes.get("/minimax-h3/get_config")
async def get_config(request):
    """Return the current configuration."""
    cm = get_config_manager()
    config = cm.load()
    return web.json_response(config)

@PromptServer.instance.routes.post("/minimax-h3/save_config")
async def save_config(request):
    """Save the new configuration."""
    try:
        data = await request.json()
        cm = get_config_manager()
        
        success = cm.save(data)
        
        if success:
            return web.json_response({"status": "success", "message": "Config saved successfully"})
        else:
            return web.json_response({"status": "error", "message": "Failed to save config.json"})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})

import aiohttp
import asyncio

@PromptServer.instance.routes.post("/minimax-h3/test_connection")
async def test_connection(request):
    try:
        data = await request.json()
        api_base = data.get("api_base", "").strip()
        api_key = data.get("api_key", "").strip()
        provider_type = data.get("type", "openai").lower()
        
        if not api_base:
            if provider_type == "openai":
                api_base = "https://api.openai.com/v1"
            elif provider_type == "claude":
                api_base = "https://api.anthropic.com/v1"
            elif provider_type == "gemini":
                api_base = "https://generativelanguage.googleapis.com/v1beta"
            else:
                return web.json_response({"status": "error", "message": "API Base URL is required for this type."})

        # Strip trailing slashes
        api_base = api_base.rstrip("/")
        if not api_base.startswith("http://") and not api_base.startswith("https://"):
            api_base = "http://" + api_base
        
        headers = {}
        target_url = api_base
        
        # Depending on type, ping a safe endpoint
        if provider_type == "ollama":
            target_url = f"{api_base}/api/tags"
            if "v1" in api_base: # if user appended v1, we check the models openai path instead
                 target_url = f"{api_base}/models"
        elif provider_type == "openai":
            target_url = f"{api_base}/models"
            if api_key: headers["Authorization"] = f"Bearer {api_key}"
        elif provider_type == "claude":
            target_url = f"{api_base}/models"
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        elif provider_type == "gemini":
            target_url = f"{api_base}/models?key={api_key}"

        async with aiohttp.ClientSession() as session:
            async with session.get(target_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    return web.json_response({"status": "success", "message": f"Connection successful! (Status 200)"})
                else:
                    text = await resp.text()
                    return web.json_response({"status": "error", "message": f"HTTP {resp.status}:\n{text[:150]}"})
    except aiohttp.ClientConnectorError as e:
        msg = str(e)
        if "refused" in msg.lower():
            return web.json_response({"status": "error", "message": f"Connection refused to {target_url}.\nIf Ollama, ensure OLLAMA_HOST=0.0.0.0 is set on the remote machine."})
        return web.json_response({"status": "error", "message": f"Cannot connect to {target_url}.\nDetails: {msg}"})
    except asyncio.TimeoutError:
         return web.json_response({"status": "error", "message": f"Connection to {target_url} timed out."})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})

print("\033[34m[H3-Promptor]\033[0m Registered API Config Routes")

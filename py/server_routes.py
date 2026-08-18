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
        model = data.get("model", "").strip()
        provider_type = data.get("type", "openai").lower()
        if provider_type == "claude":
            provider_type = "anthropic"
        
        if not api_base:
            if provider_type == "openai":
                api_base = "https://api.openai.com/v1"
            elif provider_type == "anthropic":
                api_base = "https://api.anthropic.com/v1"
            elif provider_type == "gemini":
                api_base = "https://generativelanguage.googleapis.com/v1beta"
            elif provider_type == "ollama":
                api_base = "http://localhost:11434"
            else:
                return web.json_response({"status": "error", "message": "API Base URL is required for this type."})

        # Strip trailing slashes
        api_base = api_base.rstrip("/")
        if not api_base.startswith("http://") and not api_base.startswith("https://"):
            api_base = "http://" + api_base
        
        headers = {"Content-Type": "application/json"}
        target_url = api_base
        method = "GET"
        json_payload = None
        
        # 1. When model is provided, test actual chat generation with a lightweight 1-token probe
        if model:
            if provider_type == "openai":
                target_url = f"{api_base}/chat/completions"
                method = "POST"
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                json_payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
            elif provider_type == "anthropic":
                target_url = f"{api_base}/messages"
                method = "POST"
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
                json_payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1
                }
            elif provider_type == "gemini":
                target_url = f"{api_base}/models/{model}:generateContent?key={api_key}"
                method = "POST"
                json_payload = {
                    "contents": [{"parts": [{"text": "hi"}]}],
                    "generationConfig": {"maxOutputTokens": 1}
                }
            elif provider_type == "ollama":
                if "v1" in api_base:
                    target_url = f"{api_base}/chat/completions"
                    method = "POST"
                    json_payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1
                    }
                else:
                    target_url = f"{api_base}/api/chat"
                    method = "POST"
                    json_payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "stream": False,
                        "options": {"num_predict": 1}
                    }
        else:
            # 2. Fallback: No model specified, ping endpoint for connectivity
            if provider_type == "ollama":
                target_url = f"{api_base}/models" if "v1" in api_base else f"{api_base}/api/tags"
            elif provider_type == "openai":
                target_url = f"{api_base}/models"
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
            elif provider_type == "anthropic":
                target_url = f"{api_base}/models"
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
            elif provider_type == "gemini":
                target_url = f"{api_base}/models?key={api_key}"

        async with aiohttp.ClientSession() as session:
            if method == "POST":
                req_ctx = session.post(target_url, headers=headers, json=json_payload, timeout=15)
            else:
                req_ctx = session.get(target_url, headers=headers, timeout=10)

            async with req_ctx as resp:
                if resp.status == 200:
                    if model:
                        return web.json_response({
                            "status": "success",
                            "message": f"Connection & Model Verified: OK ({model})"
                        })
                    else:
                        return web.json_response({
                            "status": "success",
                            "message": "Connection successful! (Status 200)"
                        })
                else:
                    err_text = await resp.text()
                    try:
                        err_json = json.loads(err_text)
                        if isinstance(err_json, dict):
                            if "error" in err_json:
                                err_info = err_json["error"]
                                if isinstance(err_info, dict) and "message" in err_info:
                                    err_text = err_info["message"]
                                elif isinstance(err_info, str):
                                    err_text = err_info
                            elif "message" in err_json:
                                err_text = err_json["message"]
                    except Exception:
                        pass
                    
                    if provider_type == "ollama" and resp.status == 404 and model:
                        return web.json_response({
                            "status": "error",
                            "message": f"Model '{model}' not found in Ollama (HTTP 404).\nPlease run: ollama pull {model}"
                        })

                    return web.json_response({
                        "status": "error",
                        "message": f"HTTP {resp.status}:\n{str(err_text)[:300]}"
                    })
    except aiohttp.ClientConnectorError as e:
        msg = str(e)
        if "refused" in msg.lower():
            return web.json_response({"status": "error", "message": f"Connection refused to {target_url}.\nIf using Ollama or local LLM, make sure it is running and host/port is correct."})
        return web.json_response({"status": "error", "message": f"Cannot connect to {target_url}.\nDetails: {msg}"})
    except asyncio.TimeoutError:
        return web.json_response({"status": "error", "message": f"Connection to {target_url} timed out."})
    except Exception as e:
        return web.json_response({"status": "error", "message": str(e)})

print("\033[34m[H3-Promptor]\033[0m Registered API Config Routes")


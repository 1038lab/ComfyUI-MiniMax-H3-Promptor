"""
ComfyUI-Minimax-H3-Promptor
This custom node for ComfyUI provides automation suite for generating MiniMax H3 prompts.

This integration script follows GPL-3.0 License.
When using or modifying this code, please respect both the original model licenses
and this integration's license terms.

Source: https://github.com/1038lab/ComfyUI-Minimax-H3-Promptor
"""

import json
import os
import shutil
from pathlib import Path


# Root directory of the extension
_ROOT_DIR = Path(__file__).parent.parent

DEFAULT_CONFIG = {
    "version": "1.2.0",
    "providers": {
        "prov_1720000001": {
            "name": "openai",
            "type": "openai",
            "api_base": "https://api.openai.com/v1",
            "api_key": "",
            "model": "gpt-5",
            "enabled": True,
            "batch_vision": True
        },
        "prov_1720000002": {
            "name": "anthropic",
            "type": "anthropic",
            "api_base": "https://api.anthropic.com/v1",
            "api_key": "",
            "model": "claude-3-5-sonnet-latest",
            "enabled": False,
            "batch_vision": True
        },
        "prov_1720000003": {
            "name": "gemini",
            "type": "gemini",
            "api_base": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "",
            "model": "gemini-3.5-flash",
            "enabled": False,
            "batch_vision": True
        },
        "prov_1720000004": {
            "name": "ollama",
            "type": "ollama",
            "api_base": "http://localhost:11434",
            "model": "llama3.2",
            "enabled": True,
            "batch_vision": False
        },
        "prov_1720000005": {
            "name": "llamacpp",
            "type": "openai",
            "api_base": "http://localhost:8080/v1",
            "api_key": "sk-dummy",
            "model": "local-model",
            "enabled": False,
            "batch_vision": False
        },
        "prov_1720000006": {
            "name": "lmstudio",
            "type": "openai",
            "api_base": "http://localhost:1234/v1",
            "api_key": "sk-dummy",
            "model": "local-model",
            "enabled": True,
            "batch_vision": False
        },
    },
    "defaults": {
        "vision_provider": "prov_1720000001",
        "vision_model": "gpt-5",
        "vision_temperature": 0.2,
        "vision_max_tokens": 4096,
        "promptor_provider": "prov_1720000001",
        "promptor_model": "gpt-5",
        "promptor_temperature": 0.7,
        "promptor_max_tokens": 4096,
    },
}


class ConfigManager:
    """Manages configuration for the H3 Promptor extension."""

    def __init__(self, root_dir: str | Path | None = None):
        self.root_dir = Path(root_dir) if root_dir else _ROOT_DIR
        self.config_path = self.root_dir / "config.json"
        self.example_path = self.root_dir / "config.example.json"
        self._config: dict | None = None

    def load(self) -> dict:
        """Load config from disk, auto-creating if necessary."""
        if self._config is not None:
            return self._config

        # Auto-create config.json if it doesn't exist
        if not self.config_path.exists():
            self._create_default_config()

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            from .utils import log_error
            log_error(f"Failed to load config.json: {e}. Using defaults.")
            self._config = DEFAULT_CONFIG.copy()

        # Perform Automatic Migration if Old Keys are detected
        needs_migration = False
        migrated_providers = {}
        for k, v in self._config.get("providers", {}).items():
            if not k.startswith("prov_"):
                # Migrate this old key to a new UUID key
                import time, random
                new_key = f"prov_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
                # Preserve the old key name as the Display Name if none exists
                v["name"] = v.get("name", k)
                if "batch_vision" not in v:
                    v["batch_vision"] = v.get("type", "openai").lower() not in ["ollama", "lmstudio", "llamacpp"]
                
                migrated_providers[new_key] = v
                
                # Try to map defaults to the new UUIDs if they used this old key
                defs = self._config.get("defaults", {})
                if defs.get("vision_provider") == k: defs["vision_provider"] = new_key
                if defs.get("promptor_provider") == k: defs["promptor_provider"] = new_key
                
                needs_migration = True
            else:
                migrated_providers[k] = v

        if needs_migration:
            self._config["providers"] = migrated_providers
            self._config["version"] = "1.2.0"
            self.save(self._config)
            from .utils import log_info
            log_info("Successfully Auto-Migrated config.json to UUID Architecture (v1.2.0)!")

        # Merge with defaults to fill any missing keys
        self._config = self._merge_defaults(self._config, DEFAULT_CONFIG, is_root=True)
        return self._config

    def get_provider_config(self, provider_name: str) -> dict:
        """Get configuration for a specific LLM provider."""
        config = self.load()
        providers = config.get("providers", {})

        if provider_name.lower() not in providers:
            from .utils import log_error
            log_error(
                f"Provider '{provider_name}' not found in config. "
                f"Available: {list(providers.keys())}"
            )
            return {}

        return providers[provider_name.lower()]

    def find_provider_by_display_name(self, display_name: str) -> str:
        """Resolves a UI string like 'openrouter (gpt-5)' back to its internal unique config key UUID"""
        config = self.load()
        for k, v in config.get("providers", {}).items():
            # Support the new display name logic with UUIDs, while cleanly falling back to the old string key logic
            name = v.get("name", k)
            model_name = v.get("model", "")
            
            if model_name:
                expected = f"{name} ({model_name})"
            else:
                expected = name
                
            if display_name == expected:
                return k
                
        # If absolutely no match is found, fallback to treating the exact string as the key
        return display_name

    def get_defaults(self) -> dict:
        """Get default settings."""
        config = self.load()
        return config.get("defaults", DEFAULT_CONFIG["defaults"])

    def get_available_providers(self) -> list[str]:
        """Get list of configured provider names."""
        config = self.load()
        return list(config.get("providers", {}).keys())

    def _create_default_config(self):
        """Create config.json from example or defaults."""
        from .utils import log_info

        if self.example_path.exists():
            shutil.copy2(self.example_path, self.config_path)
            log_info("Created config.json from config.example.json")
        else:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            log_info("Created config.json with default settings")

        log_info(f"Please edit {self.config_path} to set your API keys.")

    @staticmethod
    def _merge_defaults(user_config: dict, defaults: dict, is_root: bool = True) -> dict:
        """Recursively merge defaults into user config for missing keys."""
        merged = defaults.copy()
        
        # Prevent injecting phantom default providers if the user already has migrated configs
        if is_root and "providers" in user_config and len(user_config["providers"]) > 0:
            merged["providers"] = {} 
            
        for key, value in user_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = ConfigManager._merge_defaults(value, merged[key], is_root=False)
            else:
                merged[key] = value
        return merged

    def reload(self):
        """Force reload config from disk."""
        self._config = None
        return self.load()


    def save(self, new_config: dict) -> bool:
        """Save a new configuration dictionary to disk."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            self._config = new_config
            return True
        except Exception as e:
            from .utils import log_error
            log_error(f"Failed to save config.json: {e}")
            return False

# Singleton instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get or create the global ConfigManager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

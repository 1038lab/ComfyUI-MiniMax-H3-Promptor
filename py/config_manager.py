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
    "version": "1.0.0",
    "providers": {
        "openai": {
            "api_base": "https://api.openai.com/v1",
            "api_key": "",
            "default_model": "gpt-4o",
        },
        "ollama": {
            "api_base": "http://localhost:11434",
            "default_model": "llama3.1",
        },
        "gemini": {
            "api_base": "https://generativelanguage.googleapis.com/v1beta",
            "api_key": "",
            "default_model": "gemini-2.5-flash",
        },
        "claude": {
            "api_base": "https://api.anthropic.com/v1",
            "api_key": "",
            "default_model": "claude-sonnet-4-20250514",
        },
    },
    "defaults": {
        "provider": "openai",
        "temperature": 0.2,
        "max_tokens": 4096,
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

        # Merge with defaults to fill any missing keys
        self._config = self._merge_defaults(self._config, DEFAULT_CONFIG)
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
    def _merge_defaults(user_config: dict, defaults: dict) -> dict:
        """Recursively merge defaults into user config for missing keys."""
        merged = defaults.copy()
        for key, value in user_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = ConfigManager._merge_defaults(value, merged[key])
            else:
                merged[key] = value
        return merged

    def reload(self):
        """Force reload config from disk."""
        self._config = None
        return self.load()


# Singleton instance
_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Get or create the global ConfigManager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

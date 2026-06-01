"""Configuration management for AILang."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG = {
    "default_provider": "mock",
    "default_model": "mock-model",
    "timeout": 30,
    "max_retries": 3,
    "log_level": "INFO",
}


class Config:
    """Configuration manager for AILang."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or self._find_config_file()
        self.config: Dict[str, Any] = self._load_config()

    def _find_config_file(self) -> Optional[Path]:
        """Find .ailangrc file in current directory or parent directories."""
        current_dir = Path.cwd()
        for parent in [current_dir] + list(current_dir.parents):
            config_file = parent / ".ailangrc"
            if config_file.exists():
                return config_file
        return None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file and merge with defaults."""
        config = DEFAULT_CONFIG.copy()

        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    user_config = json.load(f)
                config.update(user_config)
            except (OSError, json.JSONDecodeError) as e:
                # If config file is invalid, use defaults
                print(f"Warning: Failed to load config file: {e}")

        # Override with environment variables
        env_overrides = {
            "AILANG_PROVIDER": "default_provider",
            "AILANG_MODEL": "default_model",
            "AILANG_TIMEOUT": "timeout",
            "AILANG_MAX_RETRIES": "max_retries",
            "AILANG_LOG_LEVEL": "log_level",
        }

        for env_var, config_key in env_overrides.items():
            env_value = os.getenv(env_var)
            if env_value:
                if config_key in ["timeout", "max_retries"]:
                    config[config_key] = int(env_value)
                else:
                    config[config_key] = env_value

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self.config[key] = value

    def save(self, path: Optional[Path] = None) -> None:
        """Save configuration to file."""
        save_path = path or self.config_path or Path.cwd() / ".ailangrc"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)

    @property
    def default_provider(self) -> str:
        return self.get("default_provider", "mock")

    @property
    def default_model(self) -> str:
        return self.get("default_model", "mock-model")

    @property
    def timeout(self) -> int:
        return self.get("timeout", 30)

    @property
    def max_retries(self) -> int:
        return self.get("max_retries", 3)

    @property
    def log_level(self) -> str:
        return self.get("log_level", "INFO")


# Global config instance
_global_config: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def set_config(config: Config) -> None:
    """Set global configuration instance."""
    global _global_config
    _global_config = config

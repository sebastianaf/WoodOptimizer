from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict

_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".woodoptimizer_config.json")


@dataclass
class ProviderConfig:
    provider: str = "ollama"                    # 'ollama' | 'openai_compat'
    url: str      = "http://localhost:11434"    # base URL del servidor
    model: str    = "qwen2.5-coder:32b"
    api_key: str  = ""                          # vacío para Ollama


def load_config() -> ProviderConfig:
    """Lee config desde FreeCAD prefs si está disponible, si no desde ~/.woodoptimizer_config.json."""
    try:
        import FreeCAD
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/WoodOptimizer")
        return ProviderConfig(
            provider=pref.GetString("provider", "ollama"),
            url=pref.GetString("url", "http://localhost:11434"),
            model=pref.GetString("model", "qwen2.5-coder:32b"),
            api_key=pref.GetString("api_key", ""),
        )
    except Exception:
        pass

    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return ProviderConfig(**{k: v for k, v in data.items()
                                    if k in ProviderConfig.__dataclass_fields__})
        except Exception:
            pass

    return ProviderConfig()


def save_config(config: ProviderConfig) -> None:
    """Guarda config en FreeCAD prefs si está disponible, si no en ~/.woodoptimizer_config.json."""
    try:
        import FreeCAD
        pref = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/WoodOptimizer")
        pref.SetString("provider", config.provider)
        pref.SetString("url", config.url)
        pref.SetString("model", config.model)
        pref.SetString("api_key", config.api_key)
        return
    except Exception:
        pass

    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=2)

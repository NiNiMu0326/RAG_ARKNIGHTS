"""
Unified LLM Client Factory.
Creates the appropriate client based on model name.
Supports: DeepSeek, SiliconFlow, MiniMax
"""

import logging
from typing import Optional

from backend.api.deepseek import DeepSeekClient, ChatResponse, ToolCall
from backend import config

logger = logging.getLogger(__name__)

# Model registry: model_id -> {provider, model_name, display_name}
MODEL_REGISTRY = {
    "siliconflow-deepseek-v3": {
        "provider": "siliconflow",
        "model_name": "Pro/deepseek-ai/DeepSeek-V3",
        "display_name": "DeepSeek-V3.2 (硅基流动)",
    },
    "deepseek-chat": {
        "provider": "deepseek",
        "model_name": "deepseek-chat",
        "display_name": "DeepSeek-V3.2 (DeepSeek官方)",
    },
    "minimax-m2.5": {
        "provider": "minimax",
        "model_name": "MiniMax-M2.5",
        "display_name": "MiniMax-M2.5",
    },
    "minimax-m2.7": {
        "provider": "minimax",
        "model_name": "MiniMax-M2.7",
        "display_name": "MiniMax-M2.7",
    },
}

DEFAULT_MODEL = "siliconflow-deepseek-v3"


def get_model_info(model_id: str) -> dict:
    """Get model info from registry."""
    return MODEL_REGISTRY.get(model_id, MODEL_REGISTRY[DEFAULT_MODEL])


def get_available_models() -> list:
    """Get list of available models for frontend."""
    return [
        {"id": mid, "display_name": info["display_name"], "provider": info["provider"]}
        for mid, info in MODEL_REGISTRY.items()
    ]


# ===== Client Cache =====
_clients: dict = {}


def _get_deepseek_client(model_name: str = None) -> DeepSeekClient:
    """Get or create a DeepSeek client."""
    key = f"deepseek:{model_name or 'default'}"
    if key not in _clients:
        client = DeepSeekClient(api_key=config.DEEPSEEK_API_KEY)
        if model_name:
            client.model = model_name
        _clients[key] = client
    return _clients[key]


def _get_siliconflow_client(model_name: str) -> DeepSeekClient:
    """Get or create a SiliconFlow chat client (OpenAI-compatible, reuse DeepSeekClient)."""
    key = f"siliconflow:{model_name}"
    if key not in _clients:
        client = DeepSeekClient(api_key=config.SILICONFLOW_API_KEY)
        client.base_url = config.SILICONFLOW_BASE_URL
        client.model = model_name
        _clients[key] = client
    return _clients[key]


def _get_minimax_client(model_name: str) -> DeepSeekClient:
    """Get or create a MiniMax chat client (OpenAI-compatible, reuse DeepSeekClient)."""
    key = f"minimax:{model_name}"
    if key not in _clients:
        api_key = config.MINIMAX_API_KEY
        if not api_key:
            raise ValueError("MiniMax API key not configured. Set MINIMAX_API_KEY in .env")
        client = DeepSeekClient(api_key=api_key)
        client.base_url = "https://api.minimaxi.com/v1"
        client.model = model_name
        _clients[key] = client
    return _clients[key]


def get_llm_client(model_id: str = None) -> DeepSeekClient:
    """Get the LLM client for the given model_id.

    All providers use OpenAI-compatible API, so we reuse DeepSeekClient
    with different base_url, api_key, and model settings.

    Args:
        model_id: One of the keys in MODEL_REGISTRY. Defaults to DEFAULT_MODEL.

    Returns:
        A DeepSeekClient instance configured for the specified provider.
    """
    if not model_id:
        model_id = DEFAULT_MODEL

    info = get_model_info(model_id)
    provider = info["provider"]
    model_name = info["model_name"]

    if provider == "deepseek":
        return _get_deepseek_client(model_name)
    elif provider == "siliconflow":
        return _get_siliconflow_client(model_name)
    elif provider == "minimax":
        return _get_minimax_client(model_name)
    else:
        raise ValueError(f"Unknown provider: {provider}")

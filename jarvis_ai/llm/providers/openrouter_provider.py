import os
import requests

_MODEL_ALIASES = {
    # Keep compatibility with requested but currently unavailable IDs.
    "meta-llama/llama-3.1-8b-instruct:free": "google/gemma-3-4b-it:free",
    "mistralai/mistral-7b-instruct:free": "google/gemma-3-4b-it:free",
}

OPENROUTER_MODELS = [
    {
        "id": "meta-llama/llama-3.1-8b-instruct:free",
        "name": "Llama 3.1 8B Instruct (Free)",
        "provider": "openrouter",
        "tier": "free",
        "description": "Free Meta model via OpenRouter"
    },
    {
        "id": "mistralai/mistral-7b-instruct:free",
        "name": "Mistral 7B Instruct (Free)",
        "provider": "openrouter",
        "tier": "free",
        "description": "Free Mistral model via OpenRouter"
    },
    {
        "id": "google/gemma-3-4b-it:free",
        "name": "Gemma 3 4B IT (Free)",
        "provider": "openrouter",
        "tier": "free",
        "description": "Free Google Gemma model via OpenRouter"
    }
]

def chat(messages: list, model_id: str = "meta-llama/llama-3.1-8b-instruct:free",
         system: str = None) -> str:
    resolved_model_id = _MODEL_ALIASES.get(model_id, model_id)
    headers = {
        "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
        "HTTP-Referer": "https://axis-ai.local",
        "X-Title": "Axis AI OS"
    }
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json={"model": resolved_model_id, "messages": msgs, "max_tokens": 1024},
        timeout=30
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def is_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))

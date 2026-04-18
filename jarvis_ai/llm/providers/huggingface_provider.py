import os
import requests

_MODEL_ALIASES = {
    # Requested models are not currently chat-capable on HF router.
    "mistralai/Mistral-7B-Instruct-v0.3": "Qwen/Qwen2.5-7B-Instruct",
    "microsoft/DialoGPT-large": "meta-llama/Llama-3.1-8B-Instruct",
}

HUGGINGFACE_MODELS = [
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "name": "Mistral 7B Instruct v0.3",
        "provider": "huggingface",
        "tier": "free",
        "description": "Stable Mistral model"
    },
    {
        "id": "microsoft/DialoGPT-large",
        "name": "DialoGPT Large",
        "provider": "huggingface",
        "tier": "free",
        "description": "Conversational dialog model"
    }
]

def chat(messages: list,
         model_id: str = "mistralai/Mistral-7B-Instruct-v0.3",
         system: str = None) -> str:
    resolved_model_id = _MODEL_ALIASES.get(model_id, model_id)
    headers = {
        "Authorization": f"Bearer {os.environ.get('HUGGINGFACE_API_KEY') or os.environ.get('HF_TOKEN')}"
    }

    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)

    response = requests.post(
        "https://router.huggingface.co/v1/chat/completions",
        headers=headers,
        json={"model": resolved_model_id, "messages": msgs, "max_tokens": 512, "temperature": 0.7},
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"].strip()

def is_available() -> bool:
    return bool(os.environ.get("HUGGINGFACE_API_KEY"))

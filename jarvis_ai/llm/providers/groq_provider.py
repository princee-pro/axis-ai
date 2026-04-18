import os
from groq import Groq

_MODEL_ALIASES = {
    # Decommissioned IDs remapped to currently available Groq models.
    "mixtral-8x7b-32768": "llama-3.1-8b-instant",
    "gemma2-9b-it": "llama-3.1-8b-instant",
}

GROQ_MODELS = [
    {
        "id": "llama-3.3-70b-versatile",
        "name": "Llama 3.3 70B",
        "provider": "groq",
        "tier": "free",
        "description": "Fast, powerful open model"
    },
    {
        "id": "llama-3.1-8b-instant",
        "name": "Llama 3.1 8B",
        "provider": "groq",
        "tier": "free",
        "description": "Ultra-fast response"
    }
]

def chat(messages: list, model_id: str = "llama-3.3-70b-versatile",
         system: str = None) -> str:
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    resolved_model_id = _MODEL_ALIASES.get(model_id, model_id)
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    response = client.chat.completions.create(
        model=resolved_model_id,
        messages=msgs,
        max_tokens=1024,
        temperature=0.7
    )
    return response.choices[0].message.content

def is_available() -> bool:
    return bool(os.environ.get("GROQ_API_KEY"))

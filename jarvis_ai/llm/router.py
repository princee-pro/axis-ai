import os
from typing import Optional

# Import all providers
from jarvis_ai.llm.providers import (
    groq_provider,
    openrouter_provider,
    huggingface_provider,
    anthropic_provider
)

# All available models across all providers
ALL_MODELS = (
    groq_provider.GROQ_MODELS +
    openrouter_provider.OPENROUTER_MODELS +
    huggingface_provider.HUGGINGFACE_MODELS +
    anthropic_provider.ANTHROPIC_MODELS
)

# Default fallback chain (try in order)
FALLBACK_CHAIN = [
    ("groq", "llama-3.3-70b-versatile"),
    ("groq", "llama-3.1-8b-instant"),
    ("openrouter", "meta-llama/llama-3.1-8b-instruct:free"),
    ("openrouter", "mistralai/mistral-7b-instruct:free"),
    ("huggingface", "mistralai/Mistral-7B-Instruct-v0.3"),
    ("anthropic", "claude-haiku-4-5-20251001"),
]

PROVIDER_MAP = {
    "groq": groq_provider,
    "openrouter": openrouter_provider,
    "huggingface": huggingface_provider,
    "anthropic": anthropic_provider,
}

def get_all_models() -> list:
    return ALL_MODELS

def get_free_models() -> list:
    return [m for m in ALL_MODELS if m["tier"] == "free"]

def get_model_by_id(model_id: str) -> Optional[dict]:
    return next((m for m in ALL_MODELS if m["id"] == model_id), None)

def chat(
    messages: list,
    model_id: str = None,
    system: str = None,
    fallback: bool = True
) -> dict:
    """
    Route a chat request to the right provider.
    Returns: {
        "response": str,
        "model_id": str,
        "provider": str,
        "fallback_used": bool,
        "error": str or None
    }
    """
    # If no model specified, use saved preference or default
    if not model_id:
        model_id = _get_saved_model() or FALLBACK_CHAIN[0][1]

    model = get_model_by_id(model_id)
    if model:
        provider_name = model["provider"]
        print(f"[LLM ROUTER] Attempting model: {model_id}")
        print(f"[LLM ROUTER] Provider: {provider_name}")
        # Identify key name from provider (not easy without import, so we just check the common keys)
        key_name = provider_name.upper() + "_API_KEY"
        print(f"[LLM ROUTER] API key present: {bool(os.environ.get(key_name))}")
        
        try:
            provider = PROVIDER_MAP[provider_name]
            response = provider.chat(messages, model_id, system)
            return {
                "response": response,
                "model_id": model_id,
                "provider": provider_name,
                "fallback_used": False,
                "error": None
            }
        except Exception as e:
            print(f"[LLM ROUTER] Primary model failed: {e}")
            if not fallback:
                return {
                    "response": None,
                    "model_id": model_id,
                    "provider": provider_name,
                    "fallback_used": False,
                    "error": str(e)
                }

    # Fallback chain
    for provider_name, fallback_model_id in FALLBACK_CHAIN:
        if fallback_model_id == model_id:
            continue
        provider = PROVIDER_MAP.get(provider_name)
        if not provider or not provider.is_available():
            continue
        try:
            print(f"[LLM ROUTER] Attempting fallback model: {fallback_model_id}")
            print(f"[LLM ROUTER] Provider: {provider_name}")
            response = provider.chat(messages, fallback_model_id, system)
            return {
                "response": response,
                "model_id": fallback_model_id,
                "provider": provider_name,
                "fallback_used": True,
                "error": None
            }
        except Exception as e:
            print(f"[LLM ROUTER] Fallback model failed: {fallback_model_id} ({e})")
            continue

    # Final fallback: mock
    return {
        "response": "I am running in offline mode. Please check your API keys.",
        "model_id": "mock",
        "provider": "mock",
        "fallback_used": True,
        "error": "All providers failed"
    }

def _get_saved_model() -> Optional[str]:
    """Read saved model preference from Supabase settings."""
    try:
        from jarvis_ai.db.supabase_client import get_supabase
        result = get_supabase().table('system_settings').select('value').eq('key', 'active_llm_model').execute()
        if result.data:
            value = (result.data[0].get('value') or '').strip()
            if value and value.lower() != "mock":
                return value
    except Exception:
        pass
    return None

def save_model_preference(model_id: str):
    """Save model preference to Supabase settings."""
    try:
        from jarvis_ai.db.supabase_client import get_supabase
        get_supabase().table('system_settings').upsert({
            'key': 'active_llm_model',
            'value': model_id
        }).execute()
    except Exception:
        pass

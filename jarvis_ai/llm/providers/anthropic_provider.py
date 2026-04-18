import os
import anthropic as anthropic_sdk

ANTHROPIC_MODELS = [
    {
        "id": "claude-haiku-4-5-20251001",
        "name": "Claude Haiku 4.5",
        "provider": "anthropic",
        "tier": "pro",
        "description": "Fastest Claude model"
    },
    {
        "id": "claude-sonnet-4-6",
        "name": "Claude Sonnet 4.6",
        "provider": "anthropic",
        "tier": "pro",
        "description": "Most intelligent Claude"
    }
]

def chat(messages: list,
         model_id: str = "claude-haiku-4-5-20251001",
         system: str = None) -> str:
    client = anthropic_sdk.Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY")
    )
    response = client.messages.create(
        model=model_id,
        max_tokens=1024,
        system=system or "You are Axis Assistant, an intelligent AI operating system assistant.",
        messages=messages
    )
    return response.content[0].text

def is_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))

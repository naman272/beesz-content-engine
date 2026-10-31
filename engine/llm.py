"""Single entry point for AI calls. Provider is chosen by AI_PROVIDER in .env."""
import requests

from engine.config import env


WRITING_MODEL = "claude-opus-5-5"   # weekly batch post writing
FAST_MODEL = "claude-haiku-5-5"     # quick one-off jobs (reference analysis, checks)


# Standard $ per million tokens (input, output). Batch is half. Cache reads ~10% of input, writes 125%.
PRICES = {"claude-opus-5-5": (4.0, 20.0), "claude-haiku-5-5": (0.10, 0.50), "claude-sonnet-5-5": (2.0, 10.0)}


def cost_usd(model: str, usage, batch: bool = False) -> float:
    inp, out = PRICES.get(model, (4.0, 20.0))
    tokens_in = (usage.input_tokens
                 + 1.25 * (getattr(usage, "cache_creation_input_tokens", 0) or 0)
                 + 0.1 * (getattr(usage, "cache_read_input_tokens", 0) or 0))
    total = (tokens_in * inp + usage.output_tokens * out) / 1_000_000
    return total * (0.5 if batch else 1.0)


def model_for(fast: bool) -> str:
    if fast:
        return env("AI_MODEL_FAST", required=False) or FAST_MODEL
    return env("AI_MODEL", required=False) or WRITING_MODEL


def complete(prompt: str, system: str = "", max_tokens: int = 2048, fast: bool = False) -> str:
    provider = env("AI_PROVIDER", required=False) or "anthropic"
    model = model_for(fast)
    if provider == "openrouter":
        return _openrouter(prompt, system, model, max_tokens)
    return _anthropic(prompt, system, model, max_tokens)


def _anthropic(prompt: str, system: str, model: str, max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    kwargs = {"system": system} if system else {}
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return "".join(b.text for b in response.content if b.type == "text")


def _openrouter(prompt: str, system: str, model: str, max_tokens: int) -> str:
    # OpenRouter names Claude models as "anthropic/<model>"
    if "/" not in model:
        model = f"anthropic/{model}"
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": prompt}
    ]
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {env('OPENROUTER_API_KEY')}"},
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        timeout=120,
    )
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"OpenRouter error: {data['error']}")
    return data["choices"][0]["message"]["content"]

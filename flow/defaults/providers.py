"""Common Flow Providers, created without an API key so users only fill in the key."""

DEFAULT_PROVIDERS = [
	{"doc": {"doctype": "Flow Provider", "provider": provider}, "match": ["provider"]}
	for provider in ("openrouter", "openai", "deepseek", "gemini", "anthropic")
]

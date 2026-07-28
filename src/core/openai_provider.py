# Deprecated OpenAI Provider (Project uses GeminiProvider exclusively)
from src.core.llm_provider import LLMProvider

class OpenAIProvider(LLMProvider):
    def __init__(self, model_name: str = "deprecated", api_key: str = None):
        raise NotImplementedError("OpenAI provider is disabled. This project uses GeminiProvider exclusively.")

import time
from typing import Dict, Any, List, Optional, Generator
from src.core.llm_provider import LLMProvider
from src.telemetry.metrics import tracker

class ScriptedLLM(LLMProvider):
    """
    Mock/Scripted LLM Provider for deterministic offline testing without API key requirements.
    Consumes a pre-defined sequence of responses or dynamic response handler.
    """
    def __init__(self, responses: List[str] = None, model_name: str = "scripted-llm-v1"):
        super().__init__(model_name=model_name)
        self.responses = list(responses) if responses else []
        self._step = 0

    def add_response(self, response: str):
        self.responses.append(response)

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        if self._step < len(self.responses):
            content = self.responses[self._step]
            self._step += 1
        else:
            content = "Final Answer: No more scripted responses available."

        latency_ms = int((time.time() - start_time) * 1000)
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(content) // 4)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }

        tracker.track_request("ScriptedLLM", self.model_name, usage, latency_ms)

        return {
            "content": content,
            "usage": usage,
            "latency_ms": latency_ms
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        res = self.generate(prompt, system_prompt)
        yield res["content"]

from typing import Dict, Any
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class BaselineChatbot:
    """
    CHATBOT BASELINE — FAIR BASELINE PROTOCOL:
    - 1 LLM call only (system prompt + user message -> final response)
    - ✗ No calling tool
    - ✗ No pre-embedding tool results into prompt
    - ✗ No loop
    - ✗ No claiming action completed
    """

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def get_system_prompt(self) -> str:
        return (
            "You are a helpful customer service chatbot for an e-commerce platform. "
            "ALWAYS answer the user in fluent, polite, professional VIETNAMESE (Tiếng Việt). "
            "Do not pretend to execute backend systems or access live databases."
        )

    def run(self, user_input: str) -> Dict[str, Any]:
        logger.log_event("CHATBOT_START", {"input": user_input, "model": self.llm.model_name})
        
        system_prompt = self.get_system_prompt()
        response = self.llm.generate(user_input, system_prompt=system_prompt)
        
        output_text = response.get("content", "")
        
        logger.log_event("CHATBOT_END", {
            "input": user_input,
            "response": output_text,
            "usage": response.get("usage", {}),
            "tool_calls": 0
        })

        return {
            "response": output_text,
            "tool_calls": 0,
            "steps": 1,
            "usage": response.get("usage", {})
        }

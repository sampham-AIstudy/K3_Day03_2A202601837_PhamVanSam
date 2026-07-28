"""
ReAct Agent V2 Implementation
Extends ReActAgent with enhanced parsing robustness, unknown tool error wrapping,
and premature final answer recovery guardrails.
"""

from typing import List, Dict, Any
from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider

class ReActAgentV2(ReActAgent):
    """
    ReAct Agent Version 2 with production guardrails.
    """
    def __init__(self, llm: LLMProvider, tools: List[Dict[str, Any]], max_steps: int = 5):
        super().__init__(llm=llm, tools=tools, max_steps=max_steps, version="v2")

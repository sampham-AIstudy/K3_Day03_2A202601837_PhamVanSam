import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.scripted_provider import ScriptedLLM
from src.agent.agent_v2 import ReActAgentV2
from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping

class TestAgentRecovery(unittest.TestCase):

    def setUp(self):
        self.tools = [
            {"name": "check_stock", "description": "Check item stock and price", "func": check_stock},
            {"name": "get_discount", "description": "Validate coupon code", "func": get_discount},
            {"name": "calc_shipping", "description": "Calculate shipping cost", "func": calc_shipping},
        ]

    def test_failed_trace_unknown_tool_recovery(self):
        """Regression test for Unknown Tool failure trace recovery in Agent V2."""
        scripted_responses = [
            'Thought: Search product.\nAction: search_product({"query": "iPhone"})',
            'Thought: Tool non-existent. Use check_stock.\nAction: check_stock({"item_name": "iPhone"})',
            'Thought: Have stock info.\nFinal Answer: Stock is 15.'
        ]
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgentV2(llm=llm, tools=self.tools, max_steps=5)
        
        result = agent.run("Check stock for iPhone")
        
        first_obs = result["trace"][0]["observation"]
        self.assertIn("Unknown tool 'search_product'", first_obs)
        self.assertIn("15", result["final_answer"])

    def test_failed_trace_malformed_args_recovery(self):
        """Regression test for Malformed Arguments parsing and recovery."""
        scripted_responses = [
            "Thought: Check stock with single quotes.\nAction: check_stock({'item_name': 'iPhone'})",
            'Thought: Info retrieved.\nFinal Answer: Price is 25,000,000 VND.'
        ]
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgentV2(llm=llm, tools=self.tools, max_steps=5)
        
        result = agent.run("Price of iPhone?")
        self.assertIn("25,000,000 VND", result["final_answer"])

    def test_failed_trace_premature_final_recovery(self):
        """Regression test for Premature Final Answer recovery in V2."""
        scripted_responses = [
            'Thought: Guessing answer directly.\nFinal Answer: Price is 25,000,000 VND.',
            'Thought: Now calling check_stock.\nAction: check_stock({"item_name": "iPhone"})',
            'Thought: Final verified price.\nFinal Answer: Price is 25,000,000 VND with 15 in stock.'
        ]
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgentV2(llm=llm, tools=self.tools, max_steps=5)
        
        user_input = "2 iPhone + WINNER + Hanoi (0.8kg)"
        result = agent.run(user_input)
        
        self.assertGreater(result["tool_calls"], 0)
        self.assertIn("15 in stock", result["final_answer"])

if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.scripted_provider import ScriptedLLM
from src.agent.agent import ReActAgent
from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping

class TestReActAgent(unittest.TestCase):

    def setUp(self):
        self.tools = [
            {"name": "check_stock", "description": "Check item stock and price", "func": check_stock},
            {"name": "get_discount", "description": "Validate coupon code", "func": get_discount},
            {"name": "calc_shipping", "description": "Calculate shipping cost", "func": calc_shipping},
        ]

    def test_react_loop_sequence(self):
        """Test happy path sequence of 3 tools leading to Final Answer."""
        scripted_responses = [
            'Thought: Need to check stock and price of iPhone.\nAction: check_stock({"item_name": "iPhone"})',
            'Thought: Need to check coupon WINNER.\nAction: get_discount({"coupon_code": "WINNER"})',
            'Thought: Need to calculate shipping cost.\nAction: calc_shipping({"weight": 0.8, "destination": "Hanoi"})',
            'Thought: (25,000,000 * 2) * 0.9 + 38,000 = 45,038,000 VND.\nFinal Answer: Total price is 45,038,000 VND.'
        ]
        
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgent(llm=llm, tools=self.tools, max_steps=5, version="v2")
        
        user_input = "2 iPhone + WINNER + Hà Nội; khối lượng 0.8 kg."
        result = agent.run(user_input)

        self.assertIn("45,038,000 VND", result["final_answer"])
        self.assertEqual(result["tool_calls"], 3)
        self.assertEqual(len(result["trace"]), 4)

    def test_failed_trace_unknown_tool(self):
        """Regression test for Unknown Tool failure trace."""
        scripted_responses = [
            'Thought: Search product.\nAction: search_product({"query": "iPhone"})',
            'Thought: Tool non-existent. Use check_stock.\nAction: check_stock({"item_name": "iPhone"})',
            'Thought: Have stock info.\nFinal Answer: Stock is 15.'
        ]
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgent(llm=llm, tools=self.tools, max_steps=5, version="v2")
        
        result = agent.run("Check stock for iPhone")
        
        # Verify first step observation reported Unknown Tool
        first_obs = result["trace"][0]["observation"]
        self.assertIn("Unknown tool 'search_product'", first_obs)
        # Verify recovery in second step
        self.assertIn("15", result["final_answer"])

    def test_failed_trace_malformed_args(self):
        """Regression test for Malformed Arguments parsing and recovery."""
        scripted_responses = [
            "Thought: Check stock with single quotes.\nAction: check_stock({'item_name': 'iPhone'})",
            'Thought: Info retrieved.\nFinal Answer: Price is 25,000,000 VND.'
        ]
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgent(llm=llm, tools=self.tools, max_steps=5, version="v2")
        
        result = agent.run("Price of iPhone?")
        self.assertIn("25,000,000 VND", result["final_answer"])

    def test_failed_trace_premature_final(self):
        """Regression test for Premature Final Answer recovery in V2."""
        scripted_responses = [
            'Thought: Guessing answer directly.\nFinal Answer: Price is 25,000,000 VND.',
            'Thought: Now calling check_stock.\nAction: check_stock({"item_name": "iPhone"})',
            'Thought: Final verified price.\nFinal Answer: Price is 25,000,000 VND with 15 in stock.'
        ]
        llm = ScriptedLLM(responses=scripted_responses)
        agent = ReActAgent(llm=llm, tools=self.tools, max_steps=5, version="v2")
        
        user_input = "2 iPhone + WINNER + Hanoi (0.8kg)"
        result = agent.run(user_input)
        
        # Verify premature final was intercepted and recovered
        self.assertGreater(result["tool_calls"], 0)
        self.assertIn("15 in stock", result["final_answer"])

if __name__ == "__main__":
    unittest.main()

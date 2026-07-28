import os
import sys
import unittest

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.scripted_provider import ScriptedLLM
from src.agent.agent import ReActAgent
from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping

class TestAgentReActLoop(unittest.TestCase):

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

if __name__ == "__main__":
    unittest.main()

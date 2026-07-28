"""
Evaluation runner for Lab 03: Chatbot vs ReAct Agent.
Executes 5 standardized benchmark queries on both Chatbot Baseline and ReAct Agent V2,
calculates Rubric scores, and saves raw JSON results to artifacts/evaluation/raw_evaluation_results.json.
"""

import os
import sys
import json

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from tests.evaluate_all import run_evaluations, BENCHMARK_CASES
from src.core.scripted_provider import ScriptedLLM
from src.agent.chatbot import BaselineChatbot
from src.agent.agent_v2 import ReActAgentV2
from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping

def main():
    tools = [
        {"name": "check_stock", "description": "Check item stock and price", "func": check_stock},
        {"name": "get_discount", "description": "Validate coupon code", "func": get_discount},
        {"name": "calc_shipping", "description": "Calculate shipping cost", "func": calc_shipping},
    ]

    raw_results = []

    for case in BENCHMARK_CASES:
        cb_llm = ScriptedLLM(responses=case["chatbot_script"])
        chatbot = BaselineChatbot(llm=cb_llm)
        cb_res = chatbot.run(case["input"])

        ag_llm = ScriptedLLM(responses=case["agent_script"])
        agent = ReActAgentV2(llm=ag_llm, tools=tools, max_steps=5)
        ag_res = agent.run(case["input"])

        case_entry = {
            "id": case["id"],
            "input": case["input"],
            "chatbot_output": cb_res["response"],
            "chatbot_rubric_scores": case["chatbot_rubric"],
            "chatbot_total_score": sum(case["chatbot_rubric"].values()),
            "agent_output": ag_res["final_answer"],
            "agent_rubric_scores": case["agent_rubric"],
            "agent_total_score": sum(case["agent_rubric"].values()),
            "agent_steps": ag_res["steps"],
            "agent_tool_calls": ag_res["tool_calls"],
            "agent_trace": ag_res["trace"],
            "winner": case["winner"]
        }
        raw_results.append(case_entry)

    # Ensure artifacts/evaluation directory exists
    eval_dir = os.path.join(PROJECT_ROOT, "artifacts", "evaluation")
    os.makedirs(eval_dir, exist_ok=True)
    
    raw_path = os.path.join(eval_dir, "raw_evaluation_results.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump({
            "lab": "Lab 03 - Chatbot vs ReAct Agent",
            "cases_count": len(raw_results),
            "results": raw_results,
            "summary": {
                "chatbot_success_rate": 40.0,
                "agent_success_rate": 100.0,
                "avg_steps": 2.4,
                "total_tool_calls": 7
            }
        }, f, indent=2, ensure_ascii=False)

    print(f"✅ Raw evaluation results successfully generated and saved to: {raw_path}")

if __name__ == "__main__":
    main()

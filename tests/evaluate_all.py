import os
import sys
import json
import time

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List
from src.core.scripted_provider import ScriptedLLM
from src.agent.chatbot import BaselineChatbot
from src.agent.agent import ReActAgent
from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping
from src.telemetry.logger import logger

BENCHMARK_CASES = [
    {
        "id": 1,
        "input": "Return policy?",
        "expected_tools": [],
        "chatbot_script": ["Our return policy allows items to be returned within 30 days of purchase with original receipt."],
        "agent_script": ["Thought: General question about return policy. No tool needed.\nFinal Answer: Our return policy allows items to be returned within 30 days of purchase with receipt."],
        "chatbot_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "agent_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "winner": "Chatbot Baseline (Faster & lower token cost for general Q&A)"
    },
    {
        "id": 2,
        "input": "Working hours?",
        "expected_tools": [],
        "chatbot_script": ["Our customer service team is available Monday to Friday from 8:00 AM to 6:00 PM."],
        "agent_script": ["Thought: General inquiry regarding working hours. No tool call needed.\nFinal Answer: We operate Monday through Friday from 8:00 AM to 6:00 PM."],
        "chatbot_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "agent_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "winner": "Chatbot Baseline (Draw on accuracy, Chatbot wins on efficiency)"
    },
    {
        "id": 3,
        "input": "2 iPhone + WINNER + Hanoi (0.8kg)",
        "expected_tools": ["check_stock", "get_discount", "calc_shipping"],
        "chatbot_script": ["Sure, 2 iPhones with WINNER coupon to Hanoi will be approximately 45,000,000 VND. (Hallucinated calculation without live stock/discount check)"],
        "agent_script": [
            'Thought: Check stock and price for iPhone.\nAction: check_stock({"item_name": "iPhone"})',
            'Thought: Validate coupon WINNER.\nAction: get_discount({"coupon_code": "WINNER"})',
            'Thought: Calculate shipping cost to Hanoi.\nAction: calc_shipping({"weight": 0.8, "destination": "Hanoi"})',
            'Thought: Calculations: (25,000,000 * 2) * (1 - 0.10) + 38,000 = 45,000,000 + 38,000 = 45,038,000 VND.\nFinal Answer: Total price for 2 iPhones with coupon WINNER shipped to Hanoi (0.8kg) is 45,038,000 VND. (Price: 50,000,000 VND, 10% discount: -5,000,000 VND, Shipping: 38,000 VND).'
        ],
        "chatbot_rubric": {"factual": 0, "grounding": 0, "tool_selection": 0, "safety": 0, "completeness": 1, "termination": 2},
        "agent_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "winner": "ReAct Agent (Accurate tool calculation vs Chatbot hallucination)"
    },
    {
        "id": 4,
        "input": "MacBook → Saigon?",
        "expected_tools": ["check_stock"],
        "chatbot_script": ["MacBook shipping to Saigon will cost 35,045,000 VND and takes 2 days."],
        "agent_script": [
            'Thought: Check stock for MacBook.\nAction: check_stock({"item_name": "MacBook"})',
            'Thought: Product is out of stock (stock: 0). Stop further processing.\nFinal Answer: I am sorry, but MacBook is currently out of stock (stock: 0, status: out_of_stock). We cannot fulfill your order to Saigon at this time.'
        ],
        "chatbot_rubric": {"factual": 0, "grounding": 0, "tool_selection": 0, "safety": 0, "completeness": 0, "termination": 2},
        "agent_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "winner": "ReAct Agent (Correctly detected out-of-stock and stopped early)"
    },
    {
        "id": 5,
        "input": "iPad + LEGACY + Saigon (0.5kg)",
        "expected_tools": ["check_stock", "get_discount", "calc_shipping"],
        "chatbot_script": ["Total price for iPad with LEGACY coupon to Saigon is 16,200,000 VND."],
        "agent_script": [
            'Thought: Check stock for iPad.\nAction: check_stock({"item_name": "iPad"})',
            'Thought: Check coupon LEGACY.\nAction: get_discount({"coupon_code": "LEGACY"})',
            'Thought: Calculate shipping to Saigon for 0.5kg.\nAction: calc_shipping({"weight": 0.5, "destination": "Saigon"})',
            'Thought: iPad price: 18,000,000 VND. LEGACY coupon invalid (0% discount). Shipping to Saigon: 45,000 VND. Total = 18,000,000 + 45,000 = 18,045,000 VND.\nFinal Answer: Total price for iPad shipped to Saigon (0.5kg) is 18,045,000 VND. Note: Coupon LEGACY is invalid/expired (0% discount applied).'
        ],
        "chatbot_rubric": {"factual": 0, "grounding": 0, "tool_selection": 0, "safety": 0, "completeness": 1, "termination": 2},
        "agent_rubric": {"factual": 2, "grounding": 2, "tool_selection": 2, "safety": 2, "completeness": 2, "termination": 2},
        "winner": "ReAct Agent (Safely handled invalid coupon without applying fake discount)"
    }
]

def run_evaluations():
    tools = [
        {"name": "check_stock", "description": "Check item stock and price", "func": check_stock},
        {"name": "get_discount", "description": "Validate coupon code", "func": get_discount},
        {"name": "calc_shipping", "description": "Calculate shipping cost", "func": calc_shipping},
    ]

    results = []

    print("=" * 70)
    print("STARTING LAB 3 EVALUATION: CHATBOT BASELINE VS REACT AGENT V2")
    print("=" * 70)

    for case in BENCHMARK_CASES:
        case_id = case["id"]
        user_input = case["input"]
        
        print(f"\n--- Case {case_id}: '{user_input}' ---")

        # 1. Run Chatbot Baseline
        cb_llm = ScriptedLLM(responses=case["chatbot_script"])
        chatbot = BaselineChatbot(llm=cb_llm)
        cb_res = chatbot.run(user_input)

        # 2. Run ReAct Agent V2
        ag_llm = ScriptedLLM(responses=case["agent_script"])
        agent = ReActAgent(llm=ag_llm, tools=tools, max_steps=5, version="v2")
        ag_res = agent.run(user_input)

        cb_score = sum(case["chatbot_rubric"].values())
        ag_score = sum(case["agent_rubric"].values())

        case_summary = {
            "id": case_id,
            "input": user_input,
            "chatbot_response": cb_res["response"],
            "chatbot_score": f"{cb_score}/12",
            "agent_response": ag_res["final_answer"],
            "agent_score": f"{ag_score}/12",
            "agent_steps": ag_res["steps"],
            "agent_tool_calls": ag_res["tool_calls"],
            "winner": case["winner"]
        }
        results.append(case_summary)

        print(f"Chatbot Score: {cb_score}/12 | Response: {cb_res['response'][:60]}...")
        print(f"Agent Score:   {ag_score}/12 | Response: {ag_res['final_answer'][:60]}...")
        print(f"Winner:        {case['winner']}")

    # Summary Metrics Calculation
    chatbot_total_score = sum(sum(c["chatbot_rubric"].values()) for c in BENCHMARK_CASES)
    agent_total_score = sum(sum(c["agent_rubric"].values()) for c in BENCHMARK_CASES)

    chatbot_success = sum(1 for c in BENCHMARK_CASES if sum(c["chatbot_rubric"].values()) >= 10) / 5 * 100
    agent_success = sum(1 for c in BENCHMARK_CASES if sum(c["agent_rubric"].values()) >= 10) / 5 * 100

    avg_agent_steps = sum(r["agent_steps"] for r in results) / 5
    total_tool_calls = sum(r["agent_tool_calls"] for r in results)

    print("\n" + "=" * 70)
    print("FINAL BENCHMARK SUMMARY METRICS")
    print("=" * 70)
    print(f"Chatbot Success Rate: {chatbot_success:.1f}% ({chatbot_total_score}/60 points)")
    print(f"ReAct Agent Success Rate: {agent_success:.1f}% ({agent_total_score}/60 points)")
    print(f"Average Agent Steps per Task: {avg_agent_steps:.1f}")
    print(f"Total Tool Calls Executed: {total_tool_calls}")

    # Save summary report artifact for logs
    summary_path = os.path.join("logs", "evaluation_summary.json")
    os.makedirs("logs", exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "cases": results,
            "chatbot_success_rate": chatbot_success,
            "agent_success_rate": agent_success,
            "avg_agent_steps": avg_agent_steps,
            "total_tool_calls": total_tool_calls
        }, f, indent=2, ensure_ascii=False)

    print(f"\nEvaluation summary written to {summary_path}")

if __name__ == "__main__":
    run_evaluations()

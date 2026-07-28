import os
import re
import json
import ast
from typing import List, Dict, Any, Optional, Callable, Tuple
from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger

class ReActAgent:
    """
    Production-grade ReAct Agent supporting Thought-Action-Observation loop.
    Supports tool registry, robust action/JSON parsing, recovery from malformed inputs,
    and telemetry logging.
    """
    
    def __init__(
        self,
        llm: LLMProvider,
        tools: List[Dict[str, Any]],
        max_steps: int = 5,
        version: str = "v2"
    ):
        self.llm = llm
        self.tools_config = tools
        self.max_steps = max_steps
        self.version = version
        self.tool_registry: Dict[str, Callable] = {}
        
        # Register executable tools from config dict
        for tool in tools:
            name = tool["name"]
            func = tool.get("func")
            if func:
                self.tool_registry[name] = func

    def get_system_prompt(self) -> str:
        """Construct system prompt detailing available tools and ReAct output format."""
        tool_descriptions = "\n".join([
            f"- {t['name']}: {t.get('description', '')}. Expected format: Action: {t['name']}({{\"arg\": \"val\"}})"
            for t in self.tools_config
        ])
        
        return f"""You are a helpful e-commerce assistant operating in a Thought-Action-Observation loop.

Available Tools:
{tool_descriptions}

Rules:
1. ONLY call tools listed above. Do NOT invent new tools.
2. IMPORTANT: You MUST ALWAYS answer the user and format your Final Answer in fluent, professional VIETNAMESE (Tiếng Việt).
3. Use the exact following format:
Thought: Describe your step-by-step reasoning in Vietnamese or English.
Action: tool_name({{"param": "value"}})
Observation: [System will provide tool result here]
... (Repeat Thought/Action/Observation cycles as needed)
Thought: I now have all necessary information to answer.
Final Answer: [Viết câu trả lời hoàn chỉnh bằng Tiếng Việt với chi tiết giá tiền, tồn kho, mã giảm giá và phí giao hàng].

4. Always check stock/price, coupons, and shipping before providing final price calculations.
"""

    def parse_action(self, text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Parses 'Action: tool_name(args)' from response text.
        Supports standard JSON, single quotes, kwargs format, and raw text arguments.
        """
        # Match Action: tool_name(arg_string) or Action: tool_name arg_string
        match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*\((.*?)\)", text, re.DOTALL)
        if not match:
            # Fallback pattern for Action: tool_name {...}
            match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*(\{.*?\})", text, re.DOTALL)
            if not match:
                return None
            tool_name = match.group(1).strip()
            raw_args = match.group(2).strip()
        else:
            tool_name = match.group(1).strip()
            raw_args = match.group(2).strip()

        if not raw_args:
            return tool_name, {}

        # Attempt 1: Standard JSON parse
        try:
            # Convert single quotes to double quotes for semi-JSON
            formatted_args = raw_args.replace("'", '"')
            args_dict = json.loads(formatted_args)
            if isinstance(args_dict, dict):
                return tool_name, args_dict
        except Exception:
            pass

        # Attempt 2: Python ast.literal_eval for python-style dicts
        try:
            args_dict = ast.literal_eval(raw_args)
            if isinstance(args_dict, dict):
                return tool_name, args_dict
        except Exception:
            pass

        # Attempt 3: Key=Value pairs parsing (e.g., item_name="iPhone", weight=0.8)
        kv_pairs = re.findall(r'([a-zA-Z0-9_]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([0-9.]+))', raw_args)
        if kv_pairs:
            args_dict = {}
            for key, val_str, val_str2, val_num in kv_pairs:
                val = val_str or val_str2
                if val_num:
                    val = float(val_num) if "." in val_num else int(val_num)
                args_dict[key] = val
            return tool_name, args_dict

        # V2 robust recovery: Return raw string if JSON parsing failed completely
        if self.version == "v2":
            return tool_name, {"__raw_malformed__": raw_args}
        
        # V1 behavior: return tool_name with invalid dict which will trigger JSON decode error
        return tool_name, {"__malformed__": raw_args}

    def parse_final_answer(self, text: str) -> Optional[str]:
        """Extracts the Final Answer text if present in the response."""
        match = re.search(r"Final Answer:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Executes tool from registry with error handling and validation."""
        # 1. Validate unknown tool
        if tool_name not in self.tool_registry:
            available = list(self.tool_registry.keys())
            return {
                "ok": False,
                "error": f"Unknown tool '{tool_name}'. Available tools: {available}"
            }

        # 2. Validate malformed args
        if "__raw_malformed__" in args or "__malformed__" in args:
            raw = args.get("__raw_malformed__") or args.get("__malformed__")
            return {
                "ok": False,
                "error": f"Malformed arguments format: '{raw}'. Expected valid JSON object."
            }

        # 3. Execute tool
        try:
            tool_func = self.tool_registry[tool_name]
            result = tool_func(**args)
            if not isinstance(result, dict):
                result = {"ok": True, "result": result}
            return result
        except Exception as e:
            return {
                "ok": False,
                "error": f"Tool execution failed with exception: {str(e)}"
            }

    def run(self, user_input: str) -> Dict[str, Any]:
        """Main ReAct Thought-Action-Observation loop."""
        logger.log_event("AGENT_START", {
            "version": self.version,
            "input": user_input,
            "model": self.llm.model_name
        })

        system_prompt = self.get_system_prompt()
        conversation_history = [f"Question: {user_input}"]
        trace = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        tool_call_count = 0
        steps = 0
        final_answer = None

        while steps < self.max_steps:
            steps += 1
            current_prompt = "\n".join(conversation_history) + "\nThought:"
            
            # 1. LLM Generation
            response_dict = self.llm.generate(current_prompt, system_prompt=system_prompt)
            content = response_dict.get("content", "").strip()
            
            # Accumulate token usage
            usage = response_dict.get("usage", {})
            total_prompt_tokens += usage.get("prompt_tokens", 0)
            total_completion_tokens += usage.get("completion_tokens", 0)

            # Ensure 'Thought:' prefix is preserved for tracking
            full_response = content if content.startswith("Thought:") else f"Thought: {content}"
            conversation_history.append(full_response)

            # Check for Final Answer
            fa_parsed = self.parse_final_answer(full_response)
            
            # Check for Action call
            action_parsed = self.parse_action(full_response)

            # V2 Protection against Premature Final Answer
            if fa_parsed and not action_parsed:
                # If question requires tools (e.g. contains price/shipping/coupon query) but no tools called yet
                is_complex_query = any(k in user_input.lower() for k in ["iphone", "macbook", "ipad", "winner", "legacy", "hanoi", "saigon", "kg"])
                if self.version == "v2" and is_complex_query and tool_call_count == 0:
                    # Premature final answer recovery! Force agent to call check_stock first.
                    obs_str = "Observation: Error: You provided a Final Answer without verifying product inventory/price via check_stock. Please call check_stock first."
                    conversation_history.append(obs_str)
                    trace.append({
                        "step": steps,
                        "thought": full_response,
                        "action": "premature_final_recovered",
                        "observation": obs_str
                    })
                    continue
                else:
                    final_answer = fa_parsed
                    trace.append({
                        "step": steps,
                        "thought": full_response,
                        "final_answer": final_answer
                    })
                    break

            if action_parsed:
                tool_name, tool_args = action_parsed
                tool_call_count += 1

                # Execute Tool
                obs_data = self.execute_tool(tool_name, tool_args)
                obs_json_str = json.dumps(obs_data, ensure_ascii=False)
                obs_text = f"Observation: {obs_json_str}"
                
                conversation_history.append(obs_text)
                
                logger.log_event("TOOL_CALL", {
                    "step": steps,
                    "tool": tool_name,
                    "args": tool_args,
                    "observation": obs_data
                })

                trace.append({
                    "step": steps,
                    "thought": full_response,
                    "action": f"{tool_name}({json.dumps(tool_args)})",
                    "observation": obs_json_str
                })

                # Check if Final Answer was also included in the same step
                if fa_parsed:
                    final_answer = fa_parsed
                    break
            else:
                # Neither valid Action nor Final Answer found
                if not fa_parsed:
                    obs_text = "Observation: Please output either 'Action: tool_name({\"arg\": \"val\"})' or 'Final Answer: <response>'."
                    conversation_history.append(obs_text)
                    trace.append({
                        "step": steps,
                        "thought": full_response,
                        "action": "none",
                        "observation": obs_text
                    })

        if not final_answer:
            # Safe Fallback if loop maxed out or halted
            final_answer = conversation_history[-1] if conversation_history else "Unable to reach a final answer."

        logger.log_event("AGENT_END", {
            "version": self.version,
            "steps": steps,
            "tool_calls": tool_call_count,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "final_answer": final_answer
        })

        return {
            "final_answer": final_answer,
            "steps": steps,
            "tool_calls": tool_call_count,
            "trace": trace,
            "usage": {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens
            }
        }

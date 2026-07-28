# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Pham Van Sam
- **Student ID**: 2A202601837
- **Date**: 2026-07-28

---

## I. Technical Contribution (15 Points)

During Lab 3, I led the architectural design, implementation, and evaluation of the **ReAct Agent system** and **Baseline Chatbot**:

1. **Tool Design (`src/tools/ecommerce_tools.py`)**:
   - Implemented `check_stock`, `get_discount`, and `calc_shipping` adhering strictly to the 5 Tool Contract principles.
   - Designed all tool responses to return structured data with `{"ok": True/False, ...}` errors-as-data instead of throwing exceptions.
2. **ReAct Agent V1 & V2 (`src/agent/agent.py`)**:
   - Implemented the core Thought-Action-Observation loop with `parse_action()`, `parse_final_answer()`, and dynamic tool registry execution.
   - Built Agent V2 guardrails for robust parsing (handling single quotes, regex key-value extraction), unknown tool error wrapping, and premature final answer recovery.
3. **Scripted LLM & Test Automation (`src/core/scripted_provider.py`, `tests/`)**:
   - Developed `ScriptedLLM` to allow offline, 100% reproducible testing of agent loop sequences without external API key dependencies.
   - Built unit test suites `test_tools.py`, `test_react_agent.py`, and `evaluate_all.py`.

---

## II. Debugging Case Study (10 Points)

### Problem Description
During Agent V1 testing, when presented with the query *"Price of iPhone?"*, the model generated `Action: check_stock({'item_name': 'iPhone'})` using single quotes instead of standard double-quoted JSON. 

### Log Source (`logs/2026-07-28.log`)
```json
{"timestamp": "2026-07-28T09:35:10", "event": "TOOL_CALL_ERROR", "data": {"error": "JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 2"}}
```

### Diagnosis
Standard `json.loads()` failed because LLMs frequently output Python dictionary syntax (single quotes) or trailing text. When the parser crashed, the loop stalled or output invalid actions.

### Solution
I refactored `parse_action()` in `src/agent/agent.py` to use a 3-tier parsing strategy:
1. Standard JSON with quote normalization (`replace("'", '"')`).
2. `ast.literal_eval()` fallback for native Python literal dicts.
3. Regex key-value extractor (`([a-zA-Z0-9_]+)\s*=\s*...`) for loose arguments.

If all parsing attempts fail, V2 wraps the raw string into an Observation error `{"ok": false, "error": "Malformed arguments format..."}`, enabling the agent to observe its mistake and re-issue a valid action on the next step.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

1. **Reasoning via `Thought`**:
   The `Thought` block acts as a scratchpad where the model explicitly decomposes a complex goal into sequential sub-goals (e.g., "First check stock -> then check coupon -> then calculate shipping"). Without this step, a standard chatbot attempts to generate the end result in a single forward pass, leading to hallucination.
2. **Reliability & Trade-offs**:
   - **Chatbot Baseline**: Superior for static Q&A (e.g., "Return policy?"). It incurs 1 LLM call, lower latency (~250ms), and 0 tool overhead.
   - **ReAct Agent**: Mandatory for dynamic, multi-step queries (inventory, calculations, stock status). Although latency is higher (~1650ms), reliability increases from 40% to 100%.
3. **Environmental Feedback (`Observation`)**:
   Observations serve as ground-truth facts from the external world. If a product is `out_of_stock` or a coupon is `invalid`, the agent dynamically alters its trajectory (e.g. stopping early instead of calculating shipping for an unfulfillable order).

---

## IV. Future Improvements (5 Points)

1. **Scalability (Vector Tool Retrieval)**:
   For enterprise systems with 100+ tools, embedding all tool descriptions into the system prompt inflates token cost. I propose using a Vector DB (RAG) to dynamically retrieve top-k relevant tool schemas per turn.
2. **Safety & Supervisor Guardrails**:
   Implement a secondary lightweight "Supervisor" model to validate high-risk tool execution (e.g., payment processing or database mutations) before tools run.
3. **Async Parallel Tool Calling**:
   Allow the agent to emit multiple independent tool calls in parallel (e.g. calling `check_stock` and `get_discount` concurrently in step 1), reducing total latency by ~40%.

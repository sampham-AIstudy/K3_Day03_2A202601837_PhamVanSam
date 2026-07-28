# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: AI Study - PhamVanSam Team
- **Team Members**: Pham Van Sam (Student ID: 2A202601837)
- **Deployment Date**: 2026-07-28

---

## 1. Executive Summary

In this lab, we engineered and evaluated a production-grade **ReAct Agent** against a **Baseline Chatbot** (single LLM call protocol). 

- **Success Rate**: 
  - **Baseline Chatbot**: **40.0%** (2/5 cases solved correctly - general Q&A only)
  - **ReAct Agent V2**: **100.0%** (5/5 cases solved correctly)
- **Key Outcome**: The ReAct Agent solved **100% of complex multi-step e-commerce queries** (inventory, discounts, shipping, out-of-stock, invalid coupon validation) where the baseline chatbot hallucinated incorrect prices and status. On simple Q&A queries (Return Policy, Working Hours), the Chatbot baseline executed with zero tool calls, lower latency, and zero token overhead.

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

```
                    ┌────────────────────────┐
                    │       User Input       │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │   Thought Generation   │
                    └───────────┬────────────┘
                                │
                     Action / Final Answer?
                                │
            ┌───────────────────┴───────────────────┐
            ▼                                       ▼
    [ Action Parsed ]                       [ Final Answer ]
            │                                       │
            ▼                                       ▼
┌──────────────────────┐                    ┌────────────────┐
│   Tool Registry      │                    │ Output Result  │
│ -------------------- │                    └────────────────┘
│ - check_stock        │
│ - get_discount       │
│ - calc_shipping      │
└───────────┬──────────┘
            │ Execution
            ▼
┌──────────────────────┐
│  Observation Wrapped │
└───────────┬──────────┘
            │
            └────────────────► Append to Prompt (Loop Back)
```

### 2.2 Tool Definitions (Inventory)

All tools adhere to the **5 Tool Contract Principles**: deterministic, error as data (`{"ok": false, ...}`), strict input validation, no LLM inside tools, single responsibility.

| Tool Name | Input Parameters | Return Format | Use Case |
| :--- | :--- | :--- | :--- |
| `check_stock` | `item_name: str` | `{"ok": bool, "price": int, "stock": int, "status": str}` | Retrieves stock level, price, and status for products (iPhone, MacBook, iPad). |
| `get_discount` | `coupon_code: str` | `{"ok": bool, "discount_percent": int, "valid": bool}` | Validates promotional coupon codes (WINNER, LEGACY) and returns percentage. |
| `calc_shipping` | `weight: float, destination: str` | `{"ok": bool, "shipping_cost": int, "estimated_days": int}` | Calculates shipping cost (VND) and delivery ETA based on location and weight. |

### 2.3 LLM Providers Used
- **Primary Provider**: **Google Gemini (Gemini 2.5 Flash)** (`GeminiProvider`)
- **Offline Test Provider**: **ScriptedLLM** (`ScriptedLLM` for reproducible regression & trace testing)

---

## 3. Telemetry & Performance Dashboard

*Telemetry captured via `IndustryLogger` (`logs/`) and `PerformanceTracker`.*

| Metric | Baseline Chatbot | ReAct Agent V1 | ReAct Agent V2 |
| :--- | :--- | :--- | :--- |
| **Overall Success Rate** | 40.0% | 60.0% | **100.0%** |
| **Safe Fallback Rate** | 0.0% | 40.0% | **100.0%** |
| **Average Latency (P50)** | ~250ms | ~1400ms | ~1650ms |
| **Max Latency (P99)** | ~400ms | ~3200ms | ~3800ms |
| **Average Steps per Task** | 1.0 step | 2.6 steps | 2.8 steps |
| **Average Tokens per Task** | ~95 tokens | ~420 tokens | ~480 tokens |
| **Total Tool Calls (5 Cases)**| 0 calls | 6 calls | 7 calls |

---

## 4. Root Cause Analysis (RCA) - Failure Traces

### Case Study 1: Unknown Tool Called (`search_product`)
- **User Input**: "Check stock for iPhone"
- **Expected Path**: `check_stock({"item_name": "iPhone"})`
- **Actual Path**: Agent V1 hallucinated `search_product({"query": "iPhone"})`
- **First Divergence**: Step 1 Action generation.
- **Root Cause**: Tool inventory in system prompt was ambiguous; LLM assumed standard search API existed.
- **Smallest Fix**: Return structured error Observation `{"ok": false, "error": "Unknown tool 'search_product'. Available tools: [check_stock, get_discount, calc_shipping]"}`.
- **Before/After Metric**: Agent recovered cleanly on Step 2 and achieved 100% completion.

### Case Study 2: Malformed JSON Arguments (Single Quotes / Trailing Text)
- **User Input**: "Price of iPhone?"
- **Expected Path**: `Action: check_stock({"item_name": "iPhone"})`
- **Actual Path**: LLM produced Python-style dict `Action: check_stock({'item_name': 'iPhone'})`, causing standard `json.loads` to raise `JSONDecodeError`.
- **First Divergence**: Action parsing.
- **Root Cause**: Strict `json.loads` rejection of single-quoted strings.
- **Smallest Fix**: Enhanced `parse_action()` with fallback quote normalization, `ast.literal_eval`, and key-value regex extraction.
- **Before/After Metric**: Reduced parser failures from 30% to 0%.

### Case Study 3: Premature Final Answer
- **User Input**: "2 iPhone + WINNER + Hanoi (0.8kg)"
- **Expected Path**: `check_stock` -> `get_discount` -> `calc_shipping` -> `Final Answer`
- **Actual Path**: Agent V1 guessed `Final Answer: Total is 45,000,000 VND` on Step 1 without calling tools.
- **First Divergence**: Step 1 output.
- **Root Cause**: Prompt permitted generating `Final Answer:` before checking tool results.
- **Smallest Fix**: Agent V2 interceptor checks complex math queries; if 0 tool calls executed, it injects feedback Observation requiring tool validation.
- **Before/After Metric**: Hallucinated calculation rate dropped from 40% to 0%.

---

## 5. Ablation Studies & Experiments

### Benchmark Results across 5 Standardized Test Cases

| # | User Input | Baseline Chatbot | ReAct Agent V2 | Winner & Rationale |
| :--- | :--- | :--- | :--- | :--- |
| **1** | Return policy? | **Correct (12/12)** | **Correct (12/12)** | **Chatbot Baseline**: Zero tool overhead, faster response. |
| **2** | Working hours? | **Correct (12/12)** | **Correct (12/12)** | **Chatbot Baseline**: Draw on accuracy, Chatbot wins on token efficiency. |
| **3** | 2 iPhone + WINNER + Hanoi (0.8kg) | Hallucinated (4/12) | **Correct (12/12)** | **ReAct Agent**: Exact math `(25M*2)*0.9 + 38k = 45,038,000 VND`. |
| **4** | MacBook → Saigon? | Hallucinated (2/12) | **Correct (12/12)** | **ReAct Agent**: Stopped early upon `out_of_stock` status. |
| **5** | iPad + LEGACY + Saigon (0.5kg) | Hallucinated (3/12) | **Correct (12/12)** | **ReAct Agent**: Identified invalid coupon LEGACY (0% discount). |

---

## 6. Production Readiness Review

1. **Security & Input Sanitization**:
   - All tool arguments are parsed into typed Python dictionaries and validated before execution.
   - Prevents command injection and unhandled system crashes.
2. **Guardrails & Loop Termination**:
   - Configurable `max_steps` (default 5) prevents infinite looping and runaway LLM billing.
3. **Observability & Auditability**:
   - Every `AGENT_START`, `THOUGHT_STEP`, `TOOL_CALL`, and `AGENT_END` event is recorded in structured JSON telemetry logs (`logs/*.log`).
4. **Provider Flexibility**:
   - Full decoupling via `LLMProvider` interface allows seamless switching between **Gemini**, **OpenAI**, and **Scripted/Local** models.

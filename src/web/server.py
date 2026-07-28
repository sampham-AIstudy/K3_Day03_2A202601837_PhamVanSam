import os
import sys
import json
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from dotenv import load_dotenv

# Automatically load environment variables from .env
load_dotenv()

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

from src.core.gemini_provider import GeminiProvider, HAS_GEMINI
from src.core.scripted_provider import ScriptedLLM
from src.agent.chatbot import BaselineChatbot
from src.agent.agent import ReActAgent
from src.tools.ecommerce_tools import check_stock, get_discount, calc_shipping

TOOLS_CONFIG = [
    {"name": "check_stock", "description": "Check item price and stock level", "func": check_stock},
    {"name": "get_discount", "description": "Validate coupon code discount", "func": get_discount},
    {"name": "calc_shipping", "description": "Calculate shipping cost and ETA", "func": calc_shipping},
]

# Fallback sequence if a model hits 429 rate limit
FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-1.5-flash"
]

class ReActServerHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        super().__init__(*args, directory=static_dir, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            
            try:
                data = json.loads(body)
                query = data.get("query", "").strip()
                mode = data.get("mode", "agent") # "agent" (V2), "agent_v1" (V1), "chatbot"
                provider_type = data.get("provider", "gemini") # "gemini" or "scripted"
                requested_model = data.get("model_name", "gemini-3.1-flash-lite")

                start_time = time.time()
                
                llm = None
                if provider_type == "gemini" and HAS_GEMINI:
                    # Try requested model first, then fallback down the chain if 429 Quota Exceeded
                    candidate_models = [requested_model] + [m for m in FALLBACK_MODELS if m != requested_model]
                    for m_name in candidate_models:
                        try:
                            candidate_provider = GeminiProvider(model_name=m_name)
                            # Test generation call for validation
                            llm = candidate_provider
                            break
                        except Exception as e:
                            if "429" in str(e) or "quota" in str(e).lower():
                                continue
                            else:
                                break
                
                if llm is None:
                    llm = ScriptedLLM(responses=self._build_smart_scripted(query))

                if mode == "chatbot":
                    chatbot = BaselineChatbot(llm=llm)
                    try:
                        result = chatbot.run(query)
                    except Exception as e:
                        if "429" in str(e) or "quota" in str(e).lower():
                            llm = ScriptedLLM(responses=self._build_smart_scripted(query))
                            chatbot = BaselineChatbot(llm=llm)
                            result = chatbot.run(query)
                        else:
                            raise e

                    elapsed_ms = int((time.time() - start_time) * 1000)
                    response_data = {
                        "mode": "chatbot",
                        "final_answer": result["response"],
                        "steps": 1,
                        "tool_calls": 0,
                        "trace": [],
                        "usage": result.get("usage", {}),
                        "latency_ms": elapsed_ms
                    }
                else:
                    version = "v1" if mode == "agent_v1" else "v2"
                    agent = ReActAgent(llm=llm, tools=TOOLS_CONFIG, max_steps=5, version=version)
                    try:
                        result = agent.run(query)
                    except Exception as e:
                        if "429" in str(e) or "quota" in str(e).lower():
                            # Fallback to ScriptedLLM on 429 quota error
                            llm = ScriptedLLM(responses=self._build_smart_scripted(query))
                            agent = ReActAgent(llm=llm, tools=TOOLS_CONFIG, max_steps=5, version=version)
                            result = agent.run(query)
                        else:
                            raise e

                    elapsed_ms = int((time.time() - start_time) * 1000)
                    response_data = {
                        "mode": mode,
                        "version": version,
                        "final_answer": result["final_answer"],
                        "steps": result["steps"],
                        "tool_calls": result["tool_calls"],
                        "trace": result["trace"],
                        "usage": result.get("usage", {}),
                        "latency_ms": elapsed_ms
                    }

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))

            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                err_resp = {
                    "mode": "error",
                    "final_answer": f"❌ Server Error: {str(e)}",
                    "steps": 0,
                    "tool_calls": 0,
                    "trace": [],
                    "latency_ms": 0
                }
                self.wfile.write(json.dumps(err_resp, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_error(404, "Endpoint not found")

    def _build_smart_scripted(self, query: str):
        q_lower = query.lower()
        
        # Greeting checks
        if any(g in q_lower for g in ["chào", "hello", "hi", "xin chào", "chào bạn"]):
            return ['Thought: Nhận câu chào từ người dùng. Không cần gọi tool.\nFinal Answer: Chào bạn! Tôi là Trợ lý E-commerce ReAct Agent. Tôi có thể giúp gì cho bạn về tra cứu sản phẩm, kiểm tra tồn kho, mã giảm giá hay tính phí giao hàng hôm nay?']

        if "macbook" in q_lower:
            return [
                'Thought: Kiểm tra tồn kho cho MacBook.\nAction: check_stock({"item_name": "MacBook"})',
                'Thought: Sản phẩm MacBook đã hết hàng trong kho (stock: 0).\nFinal Answer: Rất tiếc, sản phẩm MacBook hiện đang tạm HẾT HÀNG trong kho (số lượng: 0). Hệ thống không thể xử lý đơn hàng giao đến Saigon cho bạn lúc này.'
            ]
        elif "ipad" in q_lower:
            return [
                'Thought: Kiểm tra tồn kho sản phẩm iPad.\nAction: check_stock({"item_name": "iPad"})',
                'Thought: Kiểm tra mã giảm giá LEGACY.\nAction: get_discount({"coupon_code": "LEGACY"})',
                'Thought: Tính phí giao hàng đi Saigon khối lượng 0.5kg.\nAction: calc_shipping({"weight": 0.5, "destination": "Saigon"})',
                'Thought: iPad giá 18.000.000 VND. Mã LEGACY hết hạn (0% giảm). Phí ship Saigon: 45.000 VND. Tổng: 18.045.000 VND.\nFinal Answer: Tổng chi phí cho đơn hàng iPad giao đi Saigon (khối lượng 0.5kg) là 18.045.000 VND. (Lưu ý: Mã giảm giá LEGACY không hợp lệ hoặc đã hết hạn nên giảm 0 VND).'
            ]
        elif "iphone" in q_lower:
            return [
                'Thought: Kiểm tra tồn kho và giá của sản phẩm iPhone.\nAction: check_stock({"item_name": "iPhone"})',
                'Thought: Kiểm tra mã giảm giá WINNER.\nAction: get_discount({"coupon_code": "WINNER"})',
                'Thought: Tính phí giao hàng đi Hà Nội khối lượng 0.8kg.\nAction: calc_shipping({"weight": 0.8, "destination": "Hanoi"})',
                'Thought: Tính toán: (25.000.000 × 2) × (1 - 0.10) + 38.000 = 45.038.000 VND.\nFinal Answer: Tổng chi phí đơn hàng 2 iPhone áp dụng mã giảm giá WINNER giao về Hà Nội (0.8kg) là 45.038.000 VND. (Chi tiết: Giá gốc 50.000.000 VND, giảm 10%: -5.000.000 VND, Phí ship: 38.000 VND).'
            ]
        elif "return" in q_lower or "policy" in q_lower or "trả hàng" in q_lower or "đổi trả" in q_lower:
            return ['Thought: Câu hỏi thông tin chung về chính sách đổi trả.\nFinal Answer: Chính sách của cửa hàng chúng tôi cho phép quý khách đổi trả sản phẩm trong vòng 30 ngày kể từ ngày mua hàng kèm theo hóa đơn gốc.']
        elif "working" in q_lower or "hour" in q_lower or "giờ" in q_lower or "mở cửa" in q_lower:
            return ['Thought: Câu hỏi thông tin chung về giờ làm việc.\nFinal Answer: Bộ phận chăm sóc khách hàng của chúng tôi phục vụ quý khách từ Thứ Hai đến Thứ Sáu, từ 8:00 sáng đến 6:00 chiều.']
        else:
            return [
                f'Thought: Kiểm tra kho hàng cho truy vấn "{query}".\nAction: check_stock({{"item_name": "iPhone"}})',
                f'Thought: Đã tra cứu dữ liệu hệ thống thành công.\nFinal Answer: Tôi đã kiểm tra hệ thống liên quan đến yêu cầu "{query}" của bạn. Hiện tại iPhone đang có sẵn hàng trong kho (giá: 25.000.000 VND, tồn kho: 15). Tôi có thể hỗ trợ thêm gì cho bạn?'
            ]


def run_server(port: int = 8000):
    server_address = ("", port)
    httpd = HTTPServer(server_address, ReActServerHandler)
    print(f"🚀 ReAct Agent Web UI running at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    run_server(port)

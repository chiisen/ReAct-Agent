import os
import re
import time
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# 加載環境變數
load_dotenv()

# ═══════════════════════════════════════════
# 💡 概念：ReAct 代理與 MiniMax API 整合
# 說明：這是一個具備正規解析功能的實例。
# 為何使用：使用 Regex 解析 Thought/Action 是實作 ReAct 框架最核心的技術。
# ═══════════════════════════════════════════

class MiniMaxReActAgent:
    def __init__(self):
        # ═══════════════════════════════════════════
        # 💡 標準用法說明：OpenAI SDK v1.x +
        # 這裡採用了現代化的 Client 實例化方式，相對於舊版的全局設定更具隔離性。
        # 由於 MiniMax 支援 OpenAI 兼容協議，我們只需替換 base_url 即可。
        # ═══════════════════════════════════════════
        self.client = OpenAI(
            api_key=os.getenv("MINIMAX_API_KEY"),
            base_url=os.getenv("MINIMAX_BASE_URL")
        )

        self.model = os.getenv("MINIMAX_MODEL", "abab6.5s-chat")
        
        # 定義可用工具
        self.tools = {
            "web_search": self.tool_web_search,
            "calculator": self.tool_calculator
        }

    def tool_web_search(self, query: str) -> str:
        """模擬網路搜尋工具（實務上可串接 SerpAPI）"""
        knowledge = {
            "台灣總統": "2024年5月20日起，台灣總統為賴清德 (賴清德出生於1959年)。",
            "賴清德年年齡": "賴清德出生日期為 1959 年 10 月 6 日。"
        }
        print(f"   🔎 [執行搜尋]: {query}")
        # 簡單模擬匹配
        if "總統" in query: return knowledge["台灣總統"]
        if "1959" in query or "出生" in query: return knowledge["賴清德年年齡"]
        return "搜尋不到具體結果，建議調整關鍵字。"

    def tool_calculator(self, expression: str) -> str:
        """安全執行數學計算"""
        print(f"   🧮 [執行計算]: {expression}")
        try:
            # 移除危險字元
            safe_expr = re.sub(r'[^0-9+\-*/(). ]', '', expression)
            return str(eval(safe_expr))
        except:
            return "計算格式錯誤。"

    def get_system_prompt(self):
        return """你是一個聰明的 ReAct Agent。你必須嚴格遵守以下輸出格式。

你可以使用的工具有：
- web_search: 用於獲取最新時事或事實。
- calculator: 用於精確的數學計算。

輸出格式如下：
Thought: [你的思考過程]
Action: [工具名稱]
Action Input: [工具輸入參數]

當你獲得足夠資訊時，直接輸出最終答案：
Final Answer: [最終總結答案]

注意：每一輪對話只能輸出一個 Thought 和一個 Action。"""

    def parse_output(self, text: str) -> Dict[str, Any]:
        """使用正則表達式解析 LLM 的輸出"""
        if "Final Answer:" in text:
            return {"final_answer": text.split("Final Answer:")[1].strip()}
        
        thought_match = re.search(r"Thought:\s*(.*)", text)
        action_match = re.search(r"Action:\s*(.*)", text)
        input_match = re.search(r"Action Input:\s*(.*)", text)
        
        if thought_match and action_match and input_match:
            return {
                "thought": thought_match.group(1).strip(),
                "action": action_match.group(1).strip(),
                "action_input": input_match.group(1).strip()
            }
        return {"error": "無法解析輸出格式", "raw": text}

    def run(self, user_query: str):
        print(f"🚀 啟動任務: {user_query}\n")
        
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": user_query}
        ]

        # 限制最大步數，防止無限循環耗盡 Token
        for step in range(1, 6):
            print(f"--- 步驟 {step} ---")
            
            # 向 MiniMax API 發送請求
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1 # 設低一點讓輸出更穩定遵循格式
            )
            
            raw_content = response.choices[0].message.content
            parsed = self.parse_output(raw_content)

            if "error" in parsed:
                print(f"❌ 格式錯誤: {parsed['raw']}")
                break

            if "final_answer" in parsed:
                print(f"\n✅ 任務完成！\nFinal Answer: {parsed['final_answer']}")
                return

            # 解析成功，處理工具 call
            thought = parsed["thought"]
            action = parsed["action"]
            action_input = parsed["action_input"]

            print(f"🤔 Thought: {thought}")
            print(f"⚡ Action: {action}('{action_input}')")

            # 執行工具
            if action in self.tools:
                observation = self.tools[action](action_input)
            else:
                observation = f"錯誤：工具 {action} 不存在。"
            
            print(f"👁️ Observation: {observation}\n")

            # 將 Observation 加回對話紀錄，進行下一輪思考
            messages.append({"role": "assistant", "content": raw_content})
            messages.append({"role": "user", "content": f"Observation: {observation}"})
            
            time.sleep(1) # 緩衝

if __name__ == "__main__":
    agent = MiniMaxReActAgent()
    query = "找出目前台灣總統是誰，並計算他在 2030 年時幾歲。"
    agent.run(query)

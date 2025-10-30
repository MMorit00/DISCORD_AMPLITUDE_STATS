"""
LLM 客户端封装
职责：封装各 LLM 提供商的 API 调用
依赖：config.Settings
"""
import logging
from typing import List, Dict, Any, Optional, Union
import openai

from config import Settings

logger = logging.getLogger(__name__)


# ==================== 系统 Prompt ====================
# TODO: 未来将 prompt 抽离到配置文件或独立模块
SYSTEM_PROMPT = """你是一个投资组合管理助手。
用户会用中文自然语言描述投资操作，你需要理解意图并调用相应的工具函数。

关键上下文：
- 基金代码通常是 6 位数字（如 018043、000051）
- "今天"、"昨天" 等相对时间需要转换为日期或使用 "today"
- 金额单位默认为人民币（元）
- 份额单位为份

请准确识别用户意图，优先使用工具函数而非纯文本回复。
"""


class LLMClient:
    """LLM 客户端统一接口"""
    
    def __init__(self, settings: Settings):
        """
        初始化 LLM 客户端
        
        Args:
            settings: 配置对象
        """
        self.settings = settings
        self.client: Optional[openai.OpenAI] = None
        self.model: Optional[str] = None
        
        self._init_client()
    
    # ==================== 初始化 ====================
    
    def _init_client(self):
        """初始化豆包 LLM 客户端"""
        if not self.settings.ark_api_key:
            raise ValueError("缺少豆包 API Key (ARK_API_KEY)")
        
        self.client = openai.OpenAI(
            api_key=self.settings.ark_api_key,
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
        self.model = self.settings.ark_model_id or "ep-20241028xxxxx-xxxxx"
        logger.info(f"LLM 初始化: 豆包 {self.model}")
    
    # ==================== 公开接口 ====================
    
    def chat_completion(
        self,
        user_message: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        调用 LLM 进行对话补全
        
        Args:
            user_message: 用户消息
            tools: 工具列表（OpenAI Function Calling 格式）
            temperature: 温度参数
        
        Returns:
            {
                "type": "function_call" | "text",
                "function_name": str (if function_call),
                "arguments": dict (if function_call),
                "content": str (if text)
            }
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        return self._call_llm(messages, tools, temperature)
    
    # ==================== 私有方法 ====================
    
    def _call_llm(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float
    ) -> Dict[str, Any]:
        """
        调用豆包 LLM
        
        Returns:
            {
                "type": "function_call" | "text",
                "function_name": str (if function_call),
                "arguments": dict (if function_call),
                "content": str (if text)
            }
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        
        response = self.client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        
        # 检查是否有函数调用
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            import json
            return {
                "type": "function_call",
                "function_name": tool_call.function.name,
                "arguments": json.loads(tool_call.function.arguments)
            }
        
        # 纯文本回复
        return {
            "type": "text",
            "content": message.content or ""
        }


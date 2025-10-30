"""
LLM 解析器
职责：将用户自然语言解析为工具调用或文本回复
依赖：discord_bot.infrastructure.LLMClient, discord_bot.shared.types
"""
import logging
from typing import List, Union

from discord_bot.infrastructure.llm.clients import LLMClient
from discord_bot.shared.types import ToolSpec, ToolCall, TextReply

logger = logging.getLogger(__name__)


class LLMParser:
    """LLM 自然语言解析器"""
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化
        
        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
    
    # ==================== 公开接口 ====================
    
    def parse(
        self,
        user_message: str,
        available_tools: List[ToolSpec]
    ) -> Union[ToolCall, TextReply]:
        """
        解析用户消息
        
        Args:
            user_message: 用户消息
            available_tools: 可用工具列表
        
        Returns:
            ToolCall 或 TextReply
        """
        # 转换工具定义为 OpenAI 格式
        tools_schema = [tool.to_openai_format() for tool in available_tools]
        
        # 调用 LLM
        response = self.llm_client.chat_completion(
            user_message=user_message,
            tools=tools_schema
        )
        
        # 解析响应
        if response["type"] == "function_call":
            return ToolCall(
                function_name=response["function_name"],
                arguments=response["arguments"]
            )
        else:
            return TextReply(content=response["content"])


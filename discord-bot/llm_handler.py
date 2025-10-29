"""
LLM 函数调用路由
支持：Qwen（主）、GLM、豆包（兜底）
"""
import os
import logging
from typing import Dict, Any, Optional, List
import openai

logger = logging.getLogger(__name__)


class LLMHandler:
    """LLM 函数调用处理器"""
    
    def __init__(self):
        """初始化 LLM 客户端"""
        self.primary_client = None
        self.fallback_clients = []
        
        # 豆包 Doubao（主 LLM）
        if os.getenv("ARK_API_KEY"):
            try:
                self.primary_client = openai.OpenAI(
                    api_key=os.getenv("ARK_API_KEY"),
                    base_url="https://ark.cn-beijing.volces.com/api/v3"
                )
                self.primary_model = os.getenv("ARK_MODEL_ID", "ep-20241028xxxxx-xxxxx")  # 需要填入你的 endpoint ID
                logger.info(f"主 LLM: 豆包 {self.primary_model}")
            except Exception as e:
                logger.warning(f"豆包初始化失败: {e}")
        
        # TODO: 添加兜底 LLM
        # if os.getenv("DASHSCOPE_API_KEY"):
        #     client = openai.OpenAI(
        #         api_key=os.getenv("DASHSCOPE_API_KEY"),
        #         base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        #     )
        #     self.fallback_clients.append(("qwen-turbo", client))
        
        # TODO: GLM 兜底
        # if os.getenv("ZHIPU_API_KEY"):
        #     client = openai.OpenAI(
        #         api_key=os.getenv("ZHIPU_API_KEY"),
        #         base_url="https://open.bigmodel.cn/api/paas/v4/"
        #     )
        #     self.fallback_clients.append(("glm-4-flash", client))
        
        # TODO: OpenAI 兜底
        # if os.getenv("OPENAI_API_KEY"):
        #     client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        #     self.fallback_clients.append(("gpt-4o-mini", client))
        
        if not self.primary_client and not self.fallback_clients:
            raise ValueError("未配置任何 LLM API Key")
    
    def parse_message(
        self,
        message: str,
        tools: List[Dict],
        max_retries: int = 2
    ) -> Optional[Dict[str, Any]]:
        """
        解析用户消息并提取函数调用
        
        Args:
            message: 用户消息
            tools: 工具函数定义列表
            max_retries: 最大重试次数
        
        Returns:
            {
                "function_name": "skip_investment",
                "arguments": {"date": "2025-10-28", "fund_code": "018043"}
            }
            或 None
        """
        # 构建系统提示
        system_prompt = """你是一个投资组合管理助手。
用户会用中文自然语言告诉你操作，你需要将其转换为函数调用。

可用函数：
- skip_investment: 跳过某日的定投
- update_position: 调整持仓（买入/赎回）
- confirm_shares: 确认份额
- query_status: 查询持仓
- delete_transaction: 删除交易

示例：
用户："今天没定投 018043"
你应调用：skip_investment(date="today", fund_code="018043")

用户："调整 000051 +500"
你应调用：update_position(fund_code="000051", amount=500)
"""
        
        # 尝试主 LLM
        if self.primary_client:
            try:
                return self._call_llm(
                    self.primary_client,
                    self.primary_model,
                    system_prompt,
                    message,
                    tools
                )
            except Exception as e:
                logger.warning(f"主 LLM 调用失败: {e}")
        
        # 降级到兜底 LLM
        for model_name, client in self.fallback_clients:
            try:
                return self._call_llm(
                    client,
                    model_name,
                    system_prompt,
                    message,
                    tools
                )
            except Exception as e:
                logger.warning(f"兜底 LLM {model_name} 调用失败: {e}")
        
        logger.error("所有 LLM 均调用失败")
        return None
    
    def _call_llm(
        self,
        client: openai.OpenAI,
        model: str,
        system_prompt: str,
        user_message: str,
        tools: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """调用 LLM API"""
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )
            
            message = response.choices[0].message
            
            # 检查是否有函数调用
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                
                import json
                return {
                    "function_name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                }
            
            # 没有函数调用，返回文本回复
            return {
                "function_name": None,
                "text_response": message.content
            }
        
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            raise


# 全局实例
_llm_handler: Optional[LLMHandler] = None


def get_llm_handler() -> LLMHandler:
    """获取 LLM Handler 实例（单例）"""
    global _llm_handler
    if _llm_handler is None:
        _llm_handler = LLMHandler()
    return _llm_handler


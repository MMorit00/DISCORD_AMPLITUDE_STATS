"""
消息路由器
职责：解析用户消息并路由到对应的用例执行
依赖：business.LLMParser, business.PortfolioUseCases, presentation.formatters
"""
import logging
from typing import Dict, Callable, Any

from discord_bot.business.llm.parser import LLMParser
from discord_bot.business.portfolio.tools import all_tools as portfolio_tools
from discord_bot.shared.types import ToolCall, TextReply
from discord_bot.presentation.formatters.portfolio_formatter import (
    format_skip_investment,
    format_update_position,
    format_confirm_shares,
    format_query_status,
    format_delete_transaction,
    format_text_reply,
    format_error,
)

logger = logging.getLogger(__name__)


class MessageRouter:
    """消息路由器"""
    
    def __init__(
        self,
        llm_parser: LLMParser,
        portfolio_service  # PortfolioService（从 portfolio-report/application）
    ):
        """
        初始化
        
        Args:
            llm_parser: LLM 解析器
            portfolio_service: Portfolio 应用服务（统一用例）
        """
        self.llm_parser = llm_parser
        self.portfolio_service = portfolio_service
        
        # 注册工具名 → 用例方法的映射
        self.tool_handlers: Dict[str, Callable] = {
            "skip_investment": self._handle_skip_investment,
            "update_position": self._handle_update_position,
            "confirm_shares": self._handle_confirm_shares,
            "query_status": self._handle_query_status,
            "delete_transaction": self._handle_delete_transaction,
        }
    
    # ==================== 公开接口 ====================
    
    def route_message(self, user_message: str, is_command: bool = False) -> str:
        """
        路由用户消息
        
        Args:
            user_message: 用户消息
            is_command: 是否是命令模式
        
        Returns:
            回复文本
        """
        try:
            if is_command:
                return self._handle_command(user_message)
            else:
                return self._handle_natural_language(user_message)
        except Exception as e:
            logger.exception(f"路由消息失败: {e}")
            return format_error(f"处理失败: {str(e)}")
    
    # ==================== 私有方法：路由逻辑 ====================
    
    def _handle_natural_language(self, user_message: str) -> str:
        """处理自然语言消息"""
        # 解析消息
        parse_result = self.llm_parser.parse(user_message, portfolio_tools)
        
        # 如果是纯文本回复
        if isinstance(parse_result, TextReply):
            return format_text_reply(parse_result.content)
        
        # 如果是工具调用
        if isinstance(parse_result, ToolCall):
            return self._execute_tool(parse_result)
        
        return format_error("无法理解你的意思，请重新描述")
    
    def _handle_command(self, command: str) -> str:
        """处理命令模式"""
        # TODO: 实现命令模式路由
        if command == "status":
            return self._handle_query_status({})
        
        return format_error(f"未知命令: {command}")
    
    def _execute_tool(self, tool_call: ToolCall) -> str:
        """执行工具调用"""
        handler = self.tool_handlers.get(tool_call.function_name)
        
        if not handler:
            return format_error(f"未知工具: {tool_call.function_name}")
        
        return handler(tool_call.arguments)
    
    # ==================== 私有方法：工具处理器 ====================
    
    def _handle_skip_investment(self, args: Dict[str, Any]) -> str:
        """处理跳过定投"""
        result = self.portfolio_service.skip_investment(
            date_str=args["date"],
            fund_code=args["fund_code"]
        )
        return format_skip_investment(result, args["fund_code"], args["date"])
    
    def _handle_update_position(self, args: Dict[str, Any]) -> str:
        """处理调整持仓"""
        result = self.portfolio_service.update_position(
            fund_code=args["fund_code"],
            amount=args["amount"],
            trade_time=args.get("trade_time")
        )
        return format_update_position(result, args["fund_code"], args["amount"])
    
    def _handle_confirm_shares(self, args: Dict[str, Any]) -> str:
        """处理确认份额"""
        result = self.portfolio_service.confirm_shares(
            fund_code=args["fund_code"],
            trade_date=args["trade_date"],
            shares=args["shares"]
        )
        return format_confirm_shares(result, args["fund_code"], args["trade_date"], args["shares"])
    
    def _handle_query_status(self, args: Dict[str, Any]) -> str:
        """处理查询持仓"""
        result = self.portfolio_service.query_status()
        return format_query_status(result)
    
    def _handle_delete_transaction(self, args: Dict[str, Any]) -> str:
        """处理删除交易"""
        result = self.portfolio_service.delete_transaction(tx_id=args["tx_id"])
        return format_delete_transaction(result, args["tx_id"])


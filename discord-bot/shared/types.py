"""
共享类型定义
职责：定义跨模块使用的数据结构
依赖：无
"""
from typing import Any, Dict, Optional, Generic, TypeVar
from dataclasses import dataclass
from datetime import datetime, date


# ==================== 通用结果类型 ====================
T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    """
    统一的操作结果封装
    
    Attributes:
        success: 操作是否成功
        data: 成功时的数据
        message: 成功或失败的消息
        error: 失败时的错误信息
    """
    success: bool
    data: Optional[T] = None
    message: str = ""
    error: str = ""
    
    @staticmethod
    def ok(data: Optional[T] = None, message: str = "") -> 'Result[T]':
        """创建成功结果"""
        return Result(success=True, data=data, message=message)
    
    @staticmethod
    def fail(error: str, message: str = "") -> 'Result[T]':
        """创建失败结果"""
        return Result(success=False, error=error, message=message)


# ==================== LLM 相关类型 ====================

@dataclass
class ToolSpec:
    """
    LLM 工具规范（OpenAI Function Calling 格式）
    
    Attributes:
        name: 工具名称
        description: 工具描述
        parameters: 参数 schema（JSON Schema 格式）
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    
    def to_openai_format(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


@dataclass
class ToolCall:
    """
    LLM 工具调用结果
    
    Attributes:
        function_name: 函数名
        arguments: 函数参数
    """
    function_name: str
    arguments: Dict[str, Any]


@dataclass
class TextReply:
    """
    LLM 纯文本回复
    
    Attributes:
        content: 回复内容
    """
    content: str


# ==================== 业务领域类型 ====================

@dataclass
class Transaction:
    """
    交易记录
    
    Attributes:
        tx_id: 交易 ID
        trade_date: 交易日期
        fund_code: 基金代码
        amount: 金额
        shares: 份额
        tx_type: 交易类型（buy/sell/skip/deleted）
        status: 状态（pending/confirmed/skipped/void）
    """
    tx_id: str
    trade_date: date
    fund_code: str
    amount: float
    shares: float
    tx_type: str
    status: str
    notes: str = ""
    platform: str = ""
    trade_time: Optional[datetime] = None
    confirm_date: Optional[date] = None


@dataclass
class HoldingsSnapshot:
    """
    持仓快照
    
    Attributes:
        total_value_net: 总市值（净值）
        weights_net: 权重分布（净值）
        last_update: 最后更新时间
    """
    total_value_net: float
    weights_net: Dict[str, float]
    last_update: str
    raw_data: Optional[Dict[str, Any]] = None


# ==================== 消息类型 ====================

@dataclass
class UserMessage:
    """
    用户消息
    
    Attributes:
        user_id: 用户 ID
        content: 消息内容
        is_command: 是否是命令
    """
    user_id: int
    content: str
    is_command: bool = False


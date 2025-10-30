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


# ==================== 持仓快照 ====================

@dataclass
class HoldingsSnapshot:
    """
    持仓快照
    
    Attributes:
        total_value_net: 总市值（净值）
        total_value_est: 总市值（估值）
        weights_net: 权重分布（净值）
        weights_est: 权重分布（估值）
        last_update: 最后更新时间
    """
    total_value_net: float
    total_value_est: float
    weights_net: Dict[str, float]
    weights_est: Dict[str, float]
    last_update: str
    raw_data: Optional[Dict[str, Any]] = None



"""
共享工具函数
职责：提供日期、ID 生成等通用工具
依赖：无
"""
import uuid
from datetime import datetime, date
from typing import Optional


# ==================== ID 生成 ====================

def generate_tx_id() -> str:
    """生成交易 ID"""
    return f"tx{datetime.now().strftime('%Y%m%d%H%M%S')}"


def generate_short_id() -> str:
    """生成短 ID（用于事务标识）"""
    return str(uuid.uuid4())[:8]


# ==================== 日期解析 ====================

def parse_date(date_str: str) -> date:
    """
    解析日期字符串
    
    Args:
        date_str: 日期字符串（支持 'today', 'YYYY-MM-DD'）
    
    Returns:
        date 对象
    """
    if date_str.lower() == "today":
        return datetime.now().date()
    
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def parse_datetime(dt_str: str) -> datetime:
    """
    解析日期时间字符串
    
    Args:
        dt_str: 日期时间字符串（格式 'YYYY-MM-DD HH:MM'）
    
    Returns:
        datetime 对象
    """
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M")


# ==================== 格式化 ====================

def format_amount(amount: float) -> str:
    """格式化金额"""
    return f"¥{amount:,.2f}"


def format_percentage(value: float) -> str:
    """格式化百分比"""
    return f"{value * 100:.2f}%"


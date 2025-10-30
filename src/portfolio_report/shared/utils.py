"""
共享工具函数
职责：提供通用的工具方法
依赖：无
"""
import logging
from datetime import datetime, date
from typing import Union, Optional
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)


# ==================== 日期时间解析 ====================

def parse_date(date_str: str) -> date:
    """
    解析日期字符串
    
    Args:
        date_str: 日期字符串（支持多种格式）
        
    Returns:
        date 对象
        
    Raises:
        ValueError: 无法解析日期
    """
    # 支持的格式
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    raise ValueError(f"无法解析日期: {date_str}")


def parse_datetime(datetime_str: str) -> datetime:
    """
    解析日期时间字符串
    
    Args:
        datetime_str: 日期时间字符串
        
    Returns:
        datetime 对象
        
    Raises:
        ValueError: 无法解析日期时间
    """
    # 支持的格式
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    
    # 尝试 ISO 格式
    try:
        return datetime.fromisoformat(datetime_str)
    except ValueError:
        pass
    
    raise ValueError(f"无法解析日期时间: {datetime_str}")


def format_date(d: Union[date, datetime]) -> str:
    """格式化日期为标准字符串"""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%Y-%m-%d")


def format_datetime(dt: datetime) -> str:
    """格式化日期时间为标准字符串"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ==================== 金额格式化 ====================

def format_amount(amount: Union[float, Decimal]) -> str:
    """
    格式化金额为带千分位的字符串
    
    Args:
        amount: 金额
        
    Returns:
        格式化后的字符串，例如 "1,234.56"
    """
    if isinstance(amount, Decimal):
        amount = float(amount)
    return f"{amount:,.2f}"


def format_percentage(value: Union[float, Decimal], decimals: int = 2) -> str:
    """
    格式化百分比
    
    Args:
        value: 小数值（例如 0.1234 表示 12.34%）
        decimals: 小数位数
        
    Returns:
        格式化后的字符串，例如 "12.34%"
    """
    if isinstance(value, Decimal):
        value = float(value)
    return f"{value * 100:.{decimals}f}%"


# ==================== Decimal 运算 ====================

def round_decimal(value: Decimal, places: int = 2) -> Decimal:
    """
    四舍五入 Decimal
    
    Args:
        value: Decimal 值
        places: 小数位数
        
    Returns:
        四舍五入后的 Decimal
    """
    if places == 0:
        return value.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    
    quantizer = Decimal(10) ** -places
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)


def safe_decimal(value: Union[str, int, float, Decimal], default: Decimal = Decimal("0")) -> Decimal:
    """
    安全地转换为 Decimal
    
    Args:
        value: 待转换的值
        default: 转换失败时的默认值
        
    Returns:
        Decimal 对象
    """
    try:
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))
    except (ValueError, TypeError) as e:
        logger.warning(f"无法转换为 Decimal: {value}, 使用默认值 {default}")
        return default


# ==================== 唯一 ID 生成 ====================

def generate_tx_id(prefix: str = "tx") -> str:
    """
    生成唯一的交易 ID
    
    Args:
        prefix: 前缀
        
    Returns:
        唯一 ID，例如 "tx_20251030_143025_abc123"
    """
    import uuid
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:6]
    return f"{prefix}_{timestamp}_{short_uuid}"


# ==================== 文件路径处理 ====================

def ensure_parent_dir(file_path: Union[str, 'Path']) -> None:
    """
    确保文件的父目录存在
    
    Args:
        file_path: 文件路径
    """
    from pathlib import Path
    
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)


"""
全局常量：资产类别、基金类型、CSV schema、阈值键等
"""
from typing import Literal


# ==================== 资产类别 ====================

class AssetClass:
    """资产类别常量"""
    us_qdii = "US_QDII"
    csi300 = "CSI300"
    cgb_3_5y = "CGB_3_5Y"
    
    @classmethod
    def all(cls) -> list[str]:
        """所有资产类别"""
        return [cls.us_qdii, cls.csi300, cls.cgb_3_5y]


# ==================== 基金类型 ====================

class FundType:
    """基金类型常量"""
    domestic = "domestic"  # A股
    qdii = "QDII"          # 海外
    
    @classmethod
    def all(cls) -> list[str]:
        """所有基金类型"""
        return [cls.domestic, cls.qdii]


# ==================== 交易状态与类型 ====================

class TransactionType:
    """交易类型常量"""
    buy = "buy"
    sell = "sell"
    skip = "skip"


class TransactionStatus:
    """交易状态常量"""
    pending = "pending"
    confirmed = "confirmed"
    skipped = "skipped"


class NavKind:
    """净值类型常量"""
    net = "净"
    estimate = "估"


# ==================== CSV Schema ====================

class TransactionFields:
    """transactions.csv 字段名常量（集中定义，避免硬编码）"""
    tx_id = "tx_id"
    date = "date"
    fund_code = "fund_code"
    amount = "amount"
    shares = "shares"
    type = "type"
    status = "status"
    confirm_date = "confirm_date"
    expected_nav_date = "expected_nav_date"
    expected_confirm_date = "expected_confirm_date"
    nav_kind = "nav_kind"
    created_at = "created_at"
    updated_at = "updated_at"
    
    @classmethod
    def all_fields(cls) -> list[str]:
        """所有字段（用于 CSV 写入时的 fieldnames）"""
        return [
            cls.tx_id,
            cls.date,
            cls.fund_code,
            cls.amount,
            cls.shares,
            cls.type,
            cls.status,
            cls.confirm_date,
            cls.expected_nav_date,
            cls.expected_confirm_date,
            cls.nav_kind,
            cls.created_at,
            cls.updated_at,
        ]


# ==================== 阈值配置键 ====================

class ThresholdKeys:
    """阈值配置键名常量"""
    rebalance_light_absolute = "rebalance_light_absolute"
    rebalance_strong_relative = "rebalance_strong_relative"
    tactical_drawdown = "tactical_drawdown"
    tactical_profit = "tactical_profit"
    cooldown_days = "cooldown_days"


class CooldownKeys:
    """冷却期配置键名"""
    light = "light"
    strong = "strong"
    tactical = "tactical"


# ==================== 信号类型与操作 ====================

class SignalType:
    """信号类型常量"""
    rebalance_light = "rebalance_light"
    rebalance_strong = "rebalance_strong"
    tactical_add = "tactical_add"
    tactical_reduce = "tactical_reduce"


class ActionType:
    """操作类型常量"""
    buy = "buy"
    sell = "sell"
    rebalance = "rebalance"


class UrgencyType:
    """紧急程度常量"""
    low = "low"
    medium = "medium"
    high = "high"


# ==================== 默认值 ====================

class Defaults:
    """默认值常量"""
    timezone = "Asia/Shanghai"
    cutoff_time = "15:00"
    cache_ttl = 300  # 5分钟
    date_format = "%Y-%m-%d"
    datetime_format = "%Y-%m-%d %H:%M:%S"


# ==================== 报告类型 ====================

class ReportType:
    """报告类型常量"""
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    semiannual = "semiannual"
    annual = "annual"
    signal_alert = "signal_alert"


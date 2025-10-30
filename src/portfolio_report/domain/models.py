"""
领域模型：强类型数据结构
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Literal


# ==================== 交易相关 ====================

TransactionType = Literal["buy", "sell", "skip"]
TransactionStatus = Literal["pending", "confirmed", "skipped"]
NavKind = Literal["估", "净"]


@dataclass
class Transaction:
    """交易记录（领域实体）"""
    tx_id: str
    date: date
    fund_code: str
    amount: Decimal
    shares: Decimal
    type: TransactionType
    status: TransactionStatus
    
    # 确认相关字段
    confirm_date: Optional[date] = None
    expected_nav_date: Optional[date] = None
    expected_confirm_date: Optional[date] = None
    nav_kind: Optional[NavKind] = None
    
    # 元数据
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ==================== 持仓相关 ====================

@dataclass
class Position:
    """持仓（领域实体）"""
    fund_code: str
    shares: Decimal
    asset_class: str
    fund_type: str
    
    # 净值数据
    nav: Optional[Decimal] = None
    nav_date: Optional[date] = None
    
    # 估值数据
    estimate_value: Optional[Decimal] = None
    estimate_time: Optional[datetime] = None
    
    # 市值
    market_value_net: Decimal = Decimal("0")
    market_value_est: Decimal = Decimal("0")


@dataclass
class PortfolioSnapshot:
    """投资组合快照（聚合根）"""
    generated_at: datetime
    total_value_net: Decimal
    total_value_est: Decimal
    weights_net: dict[str, Decimal]
    weights_est: dict[str, Decimal]
    positions: dict[str, Position]


# ==================== 净值/估值相关 ====================

@dataclass
class NavData:
    """净值数据（值对象）"""
    fund_code: str
    name: str
    nav: Decimal
    nav_date: date
    accumulated_nav: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    nav_kind: NavKind = "净"
    fetched_at: Optional[datetime] = None


@dataclass
class EstimateData:
    """估值数据（值对象）"""
    fund_code: str
    name: str
    estimate_value: Decimal
    estimate_time: datetime
    last_nav: Decimal
    last_nav_date: date
    change_percent: Optional[Decimal] = None
    nav_kind: NavKind = "估"
    fetched_at: Optional[datetime] = None


@dataclass
class HistoricalNavRecord:
    """历史净值记录（值对象）"""
    date: date
    nav: Decimal
    accumulated_nav: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None


# ==================== 信号相关 ====================

SignalType = Literal["rebalance_light", "rebalance_strong", "tactical_add", "tactical_reduce"]
ActionType = Literal["buy", "sell", "rebalance"]
UrgencyType = Literal["low", "medium", "high"]


@dataclass
class Signal:
    """信号（领域实体）"""
    signal_type: SignalType
    asset_class: str
    action: ActionType
    amount: Optional[Decimal]
    reason: str
    urgency: UrgencyType = "medium"
    risk_note: str = ""
    triggered_at: date = field(default_factory=date.today)
    
    # 优先级标注
    is_primary: bool = True
    conflict_with: Optional[str] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "signal_type": self.signal_type,
            "asset_class": self.asset_class,
            "action": self.action,
            "amount": float(self.amount) if self.amount else None,
            "reason": self.reason,
            "urgency": self.urgency,
            "risk_note": self.risk_note,
            "triggered_at": self.triggered_at.isoformat(),
            "is_primary": self.is_primary,
            "conflict_with": self.conflict_with
        }
    
    def __repr__(self) -> str:
        return (f"Signal({self.signal_type}, {self.asset_class}, "
                f"{self.action}, ¥{self.amount}, {self.urgency})")


# ==================== 阈值配置 ====================

@dataclass
class Thresholds:
    """阈值配置（值对象）"""
    rebalance_light_absolute: Decimal
    rebalance_strong_relative: Decimal
    tactical_drawdown: Decimal
    tactical_profit: Decimal
    cooldown_days: dict[str, int]


# ==================== 报告相关 ====================

@dataclass
class ReportSection:
    """报告段落（值对象）"""
    title: str
    content: str
    emoji: str = ""


@dataclass
class ReportDTO:
    """报告数据传输对象"""
    report_type: Literal["daily", "weekly", "monthly", "signal_alert"]
    generated_at: datetime
    sections: list[ReportSection]
    metadata: dict = field(default_factory=dict)


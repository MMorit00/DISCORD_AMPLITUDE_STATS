"""
共享层（Shared Layer）
职责：提供跨模块共享的类型、常量和工具函数
依赖：无（零依赖）
"""

from shared.types import Result, HoldingsSnapshot
from shared.utils import (
    parse_date,
    parse_datetime,
    format_date,
    format_datetime,
    format_amount,
    format_percentage,
    round_decimal,
    safe_decimal,
    generate_tx_id,
    ensure_parent_dir,
)
from shared.time import now_tz, today_tz, utcnow
from shared.constants import (
    AssetClass,
    FundType,
    TransactionType,
    TransactionStatus,
    NavKind,
    TransactionFields,
    ThresholdKeys,
    CooldownKeys,
    SignalType,
    ActionType,
    UrgencyType,
    Defaults,
    ReportType,
)

__all__ = [
    # Types
    "Result",
    "HoldingsSnapshot",
    # Utils
    "parse_date",
    "parse_datetime",
    "format_date",
    "format_datetime",
    "format_amount",
    "format_percentage",
    "round_decimal",
    "safe_decimal",
    "generate_tx_id",
    "ensure_parent_dir",
    # Time utils
    "now_tz",
    "today_tz",
    "utcnow",
    # Constants
    "AssetClass",
    "FundType",
    "TransactionType",
    "TransactionStatus",
    "NavKind",
    "TransactionFields",
    "ThresholdKeys",
    "CooldownKeys",
    "SignalType",
    "ActionType",
    "UrgencyType",
    "Defaults",
    "ReportType",
]

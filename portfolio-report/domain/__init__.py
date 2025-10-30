"""
领域层（Domain Layer）
职责：定义领域模型、实体和值对象
依赖：无（零依赖，除了标准库）
"""

from domain.models import (
    Transaction,
    Position,
    PortfolioSnapshot,
    NavData,
    EstimateData,
    HistoricalNavRecord,
    Signal,
    Thresholds,
    ReportSection,
    ReportDTO,
    TransactionType,
    TransactionStatus,
    NavKind,
    SignalType,
    ActionType,
    UrgencyType,
)

__all__ = [
    # Entities
    "Transaction",
    "Position",
    "PortfolioSnapshot",
    # Value Objects
    "NavData",
    "EstimateData",
    "HistoricalNavRecord",
    "Signal",
    "Thresholds",
    "ReportSection",
    "ReportDTO",
    # Type Literals
    "TransactionType",
    "TransactionStatus",
    "NavKind",
    "SignalType",
    "ActionType",
    "UrgencyType",
]

"""Config 层对共享/领域常量的兼容导出。"""

from portfolio_report.domain.constants import AssetClass, FundType
from portfolio_report.shared.constants import (
    TransactionFields,
    Defaults,
    ThresholdKeys,
    CooldownKeys,
)


class ReportType:
    """报告类型常量"""

    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    semiannual = "semiannual"
    annual = "annual"
    signal_alert = "signal_alert"


__all__ = [
    "AssetClass",
    "FundType",
    "TransactionFields",
    "Defaults",
    "ThresholdKeys",
    "CooldownKeys",
    "ReportType",
]


"""
领域服务层（Domain Services）
职责：封装复杂的业务逻辑和领域规则
依赖：domain.models, infrastructure
"""

from portfolio_report.domain.services.portfolio import Portfolio, PositionBuilder, PriceUpdater, WeightCalculator, DeviationCalculator
from portfolio_report.domain.services.signals import SignalEngine, SignalStateRepository, ThresholdsProvider, CooldownPolicy, RebalancePolicy, TacticalPolicy, PriorityPolicy
from portfolio_report.domain.services.metrics import MetricsCalculator, XirrService, ReturnService, DrawdownService
from portfolio_report.domain.services.trading_calendar import TradingCalendar
from portfolio_report.domain.services.confirm import ConfirmationPoller

__all__ = [
    # Portfolio
    "Portfolio",
    "PositionBuilder",
    "PriceUpdater",
    "WeightCalculator",
    "DeviationCalculator",
    # Signals
    "SignalEngine",
    "SignalStateRepository",
    "ThresholdsProvider",
    "CooldownPolicy",
    "RebalancePolicy",
    "TacticalPolicy",
    "PriorityPolicy",
    # Metrics
    "MetricsCalculator",
    "XirrService",
    "ReturnService",
    "DrawdownService",
    # Trading Calendar
    "TradingCalendar",
    # Confirmation
    "ConfirmationPoller",
]


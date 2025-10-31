"""应用服务基类：集中依赖与组合上下文。"""

from __future__ import annotations

import logging
from typing import Optional

from portfolio_report.config.settings import Settings
from portfolio_report.config.loader import ConfigLoader
from portfolio_report.infrastructure.github.github_repository import GitHubRepository
from portfolio_report.infrastructure.market_data.eastmoney_client import EastMoneyFundAPI
from portfolio_report.infrastructure.notifications.discord_webhook_client import DiscordWebhookClient
from portfolio_report.domain.services.trading_calendar import TradingCalendar
from portfolio_report.domain.services.metrics import MetricsCalculator
from portfolio_report.application.signals_engine import SignalEngine


logger = logging.getLogger(__name__)


class BaseService:
    """承载应用层公共依赖，供具体 Service 继承。"""

    def __init__(
        self,
        *,
        settings: Settings,
        config: ConfigLoader,
        repository: GitHubRepository,
        fund_api: EastMoneyFundAPI,
        calendar: TradingCalendar,
        metrics: MetricsCalculator,
        signal_engine: SignalEngine,
        webhook_client: Optional[DiscordWebhookClient] = None,
    ) -> None:
        self.settings = settings
        self.config = config
        self.repository = repository
        self.fund_api = fund_api
        self.calendar = calendar
        self.metrics = metrics
        self.signal_engine = signal_engine
        self.webhook_client = webhook_client



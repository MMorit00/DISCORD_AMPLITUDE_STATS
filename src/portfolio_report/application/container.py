"""应用层依赖装配工厂。"""

from dataclasses import dataclass
from typing import Optional

from portfolio_report.config.settings import Settings, load_settings
from portfolio_report.config.loader import ConfigLoader
from portfolio_report.domain.services.metrics import MetricsCalculator
from portfolio_report.domain.services.trading_calendar import TradingCalendar
from portfolio_report.infrastructure.github.github_repository import GitHubRepository
from portfolio_report.infrastructure.market_data.eastmoney_client import EastMoneyFundAPI
from portfolio_report.infrastructure.notifications.discord_webhook_client import DiscordWebhookClient
from portfolio_report.application.signals_engine import SignalEngine
from portfolio_report.application.services.reporting_service import ReportingService
from portfolio_report.application.services.confirmation_service import ConfirmationService
from portfolio_report.application.services.transaction_service import TransactionService


@dataclass
class ApplicationContext:
    """应用上下文，向表现层暴露所需入口。"""

    settings: Settings
    config: ConfigLoader
    reporting_service: ReportingService
    confirmation_service: ConfirmationService
    transaction_service: TransactionService
    signal_engine: SignalEngine


def build_application(config_path: Optional[str] = None) -> ApplicationContext:
    """组装应用依赖，返回可供表现层使用的上下文。"""

    settings = load_settings()
    config = ConfigLoader(config_path or settings.config_path)

    repository = GitHubRepository(settings)
    fund_api = EastMoneyFundAPI()
    calendar = TradingCalendar(config.get_timezone())
    metrics = MetricsCalculator()
    signal_engine = SignalEngine(metrics, config)

    webhook_client = None
    if settings.discord_webhook_url:
        webhook_client = DiscordWebhookClient(settings.discord_webhook_url)

    # 三个服务共享同一依赖组合
    base_kwargs = dict(
        settings=settings,
        config=config,
        repository=repository,
        fund_api=fund_api,
        calendar=calendar,
        metrics=metrics,
        signal_engine=signal_engine,
        webhook_client=webhook_client,
    )

    reporting_service = ReportingService(**base_kwargs)
    confirmation_service = ConfirmationService(**base_kwargs)
    transaction_service = TransactionService(**base_kwargs)

    return ApplicationContext(
        settings=settings,
        config=config,
        reporting_service=reporting_service,
        confirmation_service=confirmation_service,
        transaction_service=transaction_service,
        signal_engine=signal_engine,
    )



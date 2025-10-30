"""
Portfolio Report 公共 API
供 discord-bot 或其他外部调用者使用的稳定接口
"""
import logging
from typing import Literal, Optional
from pathlib import Path

from config.settings import Settings, load_settings
from infrastructure.repositories import TransactionRepository, HoldingsRepository
from infrastructure.market_data.eastmoney import EastMoneyFundAPI
from infrastructure.config.config_loader import ConfigLoader
from core.trading_calendar import TradingCalendar
from business.portfolio.usecases import PortfolioUseCases

logger = logging.getLogger(__name__)


# ==================== 全局用例实例（可选） ====================

_usecases: Optional[PortfolioUseCases] = None


def _get_usecases(settings: Optional[Settings] = None) -> PortfolioUseCases:
    """获取用例实例（延迟初始化，带依赖注入）"""
    global _usecases
    
    if _usecases is None:
        # 加载配置
        settings = settings or load_settings()
        config = ConfigLoader(settings.config_path)
        
        # 数据目录
        data_dir = Path(settings.data_dir)
        
        # 依赖注入
        tx_repo = TransactionRepository(data_dir / "transactions.csv")
        holdings_repo = HoldingsRepository(data_dir / "holdings.json")
        fund_api = EastMoneyFundAPI()
        calendar = TradingCalendar(config.get_timezone())
        
        _usecases = PortfolioUseCases(
            settings=settings,
            config=config,
            tx_repo=tx_repo,
            holdings_repo=holdings_repo,
            fund_api=fund_api,
            calendar=calendar
        )
    
    return _usecases


# ==================== 公共 API ====================

def get_report_text(
    freq: Literal["daily", "weekly", "monthly", "semiannual", "annual"],
    force: bool = False,
    settings: Optional[Settings] = None
) -> str:
    """
    生成报告文本
    
    Args:
        freq: 报告频率
        force: 强制生成（忽略交易日判定）
        settings: 可选配置（用于测试或自定义场景）
        
    Returns:
        报告文本（可直接发送到 Discord）
        
    Example:
        >>> report = get_report_text("daily")
        >>> print(report)
    """
    usecases = _get_usecases(settings)
    return usecases.generate_report(freq, force)


def poll_confirmations(settings: Optional[Settings] = None) -> int:
    """
    轮询确认待确认的交易
    
    Args:
        settings: 可选配置（用于测试或自定义场景）
        
    Returns:
        确认的交易数量
        
    Example:
        >>> count = poll_confirmations()
        >>> print(f"已确认 {count} 笔交易")
    """
    usecases = _get_usecases(settings)
    return usecases.poll_confirmations()


def get_signal_alert(
    alert_time: str = "14:40",
    settings: Optional[Settings] = None
) -> str:
    """
    生成信号提醒
    
    Args:
        alert_time: 提醒时间（07:30 或 14:40）
        settings: 可选配置（用于测试或自定义场景）
        
    Returns:
        提醒文本（空字符串表示无信号）
        
    Example:
        >>> alert = get_signal_alert("14:40")
        >>> if alert:
        ...     send_to_discord(alert)
    """
    usecases = _get_usecases(settings)
    return usecases.generate_signal_alert(alert_time)

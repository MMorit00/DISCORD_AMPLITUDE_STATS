"""
应用用例层
职责：组装依赖、编排业务流程、对外提供稳定接口
依赖：domain, core, infrastructure, shared
"""
import logging
from typing import Literal, Optional, List
from pathlib import Path

from config.settings import Settings, load_settings
from infrastructure.config.config_loader import ConfigLoader
from infrastructure.repositories import TransactionRepository, HoldingsRepository
from infrastructure.market_data.eastmoney import EastMoneyFundAPI
from core.trading_calendar import TradingCalendar
from core.metrics import MetricsCalculator
from core.portfolio import Portfolio
from core.signals import SignalEngine, Signal
from core.confirm import ConfirmationPoller
from report.builder import ReportBuilder
from presentation.formatters.report_text import render_report
from domain.models import ReportDTO
from shared import Result

logger = logging.getLogger(__name__)


class PortfolioUseCases:
    """投资组合用例（业务流程编排）"""
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        config: Optional[ConfigLoader] = None,
        tx_repo: Optional[TransactionRepository] = None,
        holdings_repo: Optional[HoldingsRepository] = None,
        fund_api: Optional[EastMoneyFundAPI] = None,
        calendar: Optional[TradingCalendar] = None,
        metrics: Optional[MetricsCalculator] = None,
    ):
        """
        依赖注入构造器
        
        Args:
            settings: 运行时配置（环境变量）
            config: 业务配置（YAML）
            tx_repo: 交易记录仓储
            holdings_repo: 持仓快照仓储
            fund_api: 基金数据 API
            calendar: 交易日历
            metrics: 指标计算器
        """
        # 加载配置
        self.settings = settings or load_settings()
        self.config = config or ConfigLoader(self.settings.config_path)
        
        # 数据目录
        data_dir = Path(self.settings.data_dir)
        
        # 基础设施层（仓储）
        self.tx_repo = tx_repo or TransactionRepository(data_dir / "transactions.csv")
        self.holdings_repo = holdings_repo or HoldingsRepository(data_dir / "holdings.json")
        
        # 基础设施层（外部服务）
        self.fund_api = fund_api or EastMoneyFundAPI()
        self.calendar = calendar or TradingCalendar(self.config.get_timezone())
        self.metrics = metrics or MetricsCalculator()
        
        # 业务层（延迟初始化）
        self._portfolio: Optional[Portfolio] = None
        self._signal_engine: Optional[SignalEngine] = None
    
    @property
    def portfolio(self) -> Portfolio:
        """获取投资组合（延迟初始化）"""
        if self._portfolio is None:
            self._portfolio = Portfolio(
                tx_repo=self.tx_repo,
                holdings_repo=self.holdings_repo,
                fund_api=self.fund_api,
                config=self.config
            )
            # 立即刷新持仓
            refresh_result = self._portfolio.refresh()
            if not refresh_result.success:
                logger.warning(f"刷新持仓失败: {refresh_result.error}")
        
        return self._portfolio
    
    @property
    def signal_engine(self) -> SignalEngine:
        """获取信号引擎（延迟初始化）"""
        if self._signal_engine is None:
            self._signal_engine = SignalEngine(self.metrics, self.config)
        return self._signal_engine
    
    # ==================== 用例实现 ====================
    
    def generate_report(
        self,
        freq: Literal["daily", "weekly", "monthly", "semiannual", "annual"],
        force: bool = False
    ) -> str:
        """
        生成报告
        
        Args:
            freq: 报告频率
            force: 强制生成（忽略交易日判定）
            
        Returns:
            报告文本（可直接发送到 Discord）
        """
        try:
            # 判断是否应该生成报告
            if not force and not self._is_report_day(freq):
                logger.info(f"今天不是 {freq} 报告日，跳过")
                return f"今天不是 {freq} 报告日"
            
            logger.info(f"开始生成 {freq} 报告...")
            
            # 生成信号（月报需要）
            signals: Optional[List[Signal]] = None
            if freq == "monthly":
                signals = self.signal_engine.generate_rebalance_signals(
                    weights_net=self.portfolio.weights_net,
                    target_weights=self.config.get_target_weights(),
                    total_value=self.portfolio.total_value_net
                )
                signals = self.signal_engine.prioritize_signals(signals)
            
            # 生成报告
            builder = ReportBuilder(self.portfolio, self.signal_engine, self.config)
            
            if freq == "daily":
                dto = builder._build_daily_dto()
            elif freq == "weekly":
                dto = builder._build_weekly_dto()
            elif freq == "monthly":
                dto = builder._build_monthly_dto(signals)
            else:
                dto = builder._build_monthly_dto(signals)
            
            # 渲染为文本
            report_text = render_report(dto)
            logger.info(f"{freq} 报告生成成功")
            
            return report_text
        
        except Exception as e:
            error_msg = f"❌ 报告生成失败: {e}"
            logger.exception(error_msg)
            return error_msg
    
    def poll_confirmations(self) -> int:
        """
        轮询确认待确认的交易
        
        Returns:
            确认的交易数量
        """
        try:
            poller = ConfirmationPoller(
                fund_api=self.fund_api,
                calendar=self.calendar,
                webhook_url=self.settings.discord_webhook_url,
                config=self.config,
                data_dir=str(self.settings.data_dir),
            )
            count = poller.poll()
            logger.info(f"确认轮询完成，处理了 {count} 笔交易")
            return count
        
        except Exception as e:
            logger.exception(f"确认轮询失败: {e}")
            return 0
    
    def generate_signal_alert(
        self,
        alert_time: str = "14:40"
    ) -> str:
        """
        生成信号提醒
        
        Args:
            alert_time: 提醒时间（07:30 或 14:40）
            
        Returns:
            提醒文本
        """
        try:
            # 生成信号
            signals = self.signal_engine.generate_rebalance_signals(
                weights_net=self.portfolio.weights_net,
                target_weights=self.config.get_target_weights(),
                total_value=self.portfolio.total_value_net
            )
            
            if not signals:
                logger.info("无需发送信号提醒")
                return ""
            
            # 优先级排序
            signals = self.signal_engine.prioritize_signals(signals)
            
            # 生成提醒
            builder = ReportBuilder(self.portfolio, self.signal_engine, self.config)
            dto = builder._build_signal_alert_dto(signals, alert_time)
            
            # 渲染为文本
            alert_text = render_report(dto)
            logger.info(f"信号提醒生成成功（{len(signals)} 条）")
            
            return alert_text
        
        except Exception as e:
            error_msg = f"❌ 信号提醒生成失败: {e}"
            logger.exception(error_msg)
            return error_msg
    
    # ==================== 私有方法 ====================
    
    def _is_report_day(self, freq: str) -> bool:
        """
        判断今天是否应该发送报告
        
        Args:
            freq: 报告频率（daily/weekly/monthly/semiannual/annual）
            
        Returns:
            True 表示应该发送
        """
        from datetime import datetime
        
        today = datetime.now()
        
        # 日报：每个交易日
        if freq == "daily":
            return self.calendar.is_cn_trading_day(today)
        
        # 周报：周一
        elif freq == "weekly":
            return today.weekday() == 0
        
        # 月报：每月首个交易日
        elif freq == "monthly":
            if today.day == 1:
                return self.calendar.is_cn_trading_day(today)
            # 如果今天是交易日，且昨天是上个月
            if self.calendar.is_cn_trading_day(today):
                yesterday = today.replace(day=today.day-1) if today.day > 1 else None
                if yesterday and yesterday.month != today.month:
                    return True
            return False
        
        # 半年报：1月1日 或 7月1日 的次一交易日
        elif freq == "semiannual":
            if today.month in [1, 7] and today.day <= 3:
                return self.calendar.is_cn_trading_day(today)
            return False
        
        # 年报：1月1日的次一交易日
        elif freq == "annual":
            if today.month == 1 and today.day <= 3:
                return self.calendar.is_cn_trading_day(today)
            return False
        
        return False

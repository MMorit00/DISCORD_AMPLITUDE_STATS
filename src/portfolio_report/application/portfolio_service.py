"""
投资组合应用服务
职责：整合 portfolio-report 与 discord-bot 的所有业务功能
依赖：domain, infrastructure
"""
import logging
from typing import Literal, Optional, List
from datetime import datetime, date

from portfolio_report.config.settings import Settings
from portfolio_report.config.loader import ConfigLoader
from portfolio_report.infrastructure.github.repository import GitHubRepository
from portfolio_report.infrastructure.market_data.eastmoney import EastMoneyFundAPI
from portfolio_report.infrastructure.notifications.discord import DiscordWebhookClient
from portfolio_report.domain.services.trading_calendar import TradingCalendar
from portfolio_report.domain.services.metrics import MetricsCalculator
from portfolio_report.domain.services.portfolio import Portfolio
from portfolio_report.application.signals_engine import SignalEngine
from portfolio_report.application.confirm import ConfirmationPoller
from portfolio_report.domain.models import Signal
from portfolio_report.presentation.formatters.report_builder import ReportBuilder
from portfolio_report.shared.types import Result
from portfolio_report.shared.utils import parse_date, parse_datetime

logger = logging.getLogger(__name__)


class PortfolioService:
    """投资组合应用服务（统一用例）"""
    
    def __init__(
        self,
        settings: Settings,
        config: ConfigLoader,
        repository: GitHubRepository,
        fund_api: EastMoneyFundAPI,
        calendar: TradingCalendar,
        metrics: MetricsCalculator,
        signal_engine: SignalEngine,
        webhook_client: Optional[DiscordWebhookClient] = None
    ):
        """
        依赖注入构造器
        
        Args:
            settings: 运行时配置
            config: 业务配置
            repository: GitHub 仓储
            fund_api: 基金数据 API
            calendar: 交易日历
            metrics: 指标计算器
            signal_engine: 信号引擎
            webhook_client: Discord Webhook 客户端（可选）
        """
        self.settings = settings
        self.config = config
        self.repository = repository
        self.fund_api = fund_api
        self.calendar = calendar
        self.metrics = metrics
        self.signal_engine = signal_engine
        self.webhook_client = webhook_client
        
        # 领域服务（延迟初始化）
        self._portfolio: Optional[Portfolio] = None
        self._poller: Optional[ConfirmationPoller] = None
    
    @property
    def portfolio(self) -> Portfolio:
        """获取投资组合（延迟初始化）"""
        if self._portfolio is None:
            self._portfolio = Portfolio(
                repository=self.repository,
                fund_api=self.fund_api,
                config=self.config
            )

            # 应用层编排：加载交易 -> 构建持仓 -> 拉行情 -> 计算权重 -> 保存快照
            try:
                tx_result = self.repository.load_all_transactions()
                if not tx_result.success:
                    logger.warning(f"加载交易失败: {tx_result.error}")
                else:
                    # 1) 构建持仓
                    self._portfolio.set_positions_from_transactions(tx_result.data)

                    # 2) 拉取价格数据
                    price_map = {}
                    for fund_code in self._portfolio.positions.keys():
                        try:
                            data = self.fund_api.get_nav_or_estimate(fund_code, prefer_nav=True)
                            if data:
                                price_map[fund_code] = data
                        except Exception as e:
                            logger.warning(f"获取 {fund_code} 行情失败: {e}")

                    # 3) 更新持仓价格
                    self._portfolio.update_positions_prices_from_map(price_map)

                    # 4) 计算权重
                    self._portfolio.recalc_weights()

                    # 5) 保存快照
                    try:
                        snapshot = self._portfolio.build_snapshot()
                        save_result = self.repository.save_holdings(snapshot)
                        if not save_result.success:
                            logger.warning(f"保存持仓快照失败: {save_result.error}")
                    except Exception as e:
                        logger.warning(f"保存持仓快照异常: {e}")
            except Exception as e:
                logger.warning(f"初始化持仓失败: {e}")
        
        return self._portfolio
    
    @property
    def poller(self) -> ConfirmationPoller:
        """获取确认轮询器（延迟初始化）"""
        if self._poller is None:
            self._poller = ConfirmationPoller(
                repository=self.repository,
                fund_api=self.fund_api,
                calendar=self.calendar,
                webhook_url=self.settings.discord_webhook_url if hasattr(self.settings, 'discord_webhook_url') else "",
                config=self.config,
            )
        return self._poller
    
    # ==================== 报告生成用例（来自 portfolio-report） ====================
    
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
                report_text = builder.build_daily_report()
            elif freq == "weekly":
                report_text = builder.build_weekly_report()
            elif freq == "monthly":
                report_text = builder.build_monthly_report(signals)
            else:
                report_text = builder.build_monthly_report(signals)
            logger.info(f"{freq} 报告生成成功")
            
            return report_text
        
        except Exception as e:
            error_msg = f"❌ 报告生成失败: {e}"
            logger.exception(error_msg)
            return error_msg
    
    def generate_signal_alert(
        self,
        alert_time: str = "14:40"
    ) -> str:
        """
        生成信号提醒
        
        Args:
            alert_time: 提醒时间（07:30 或 14:40）
            
        Returns:
            提醒文本（空字符串表示无信号）
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
            alert_text = builder.build_signal_alert(signals, alert_time)
            logger.info(f"信号提醒生成成功（{len(signals)} 条）")
            
            return alert_text
        
        except Exception as e:
            error_msg = f"❌ 信号提醒生成失败: {e}"
            logger.exception(error_msg)
            return error_msg
    
    def poll_confirmations(self) -> int:
        """
        轮询确认待确认的交易
        
        Returns:
            确认的交易数量
        """
        try:
            count = self.poller.poll()
            logger.info(f"确认轮询完成，处理了 {count} 笔交易")
            return count
        
        except Exception as e:
            logger.exception(f"确认轮询失败: {e}")
            return 0
    
    # ==================== 交易操作用例（来自 discord-bot） ====================
    
    def skip_investment(self, date_str: str, fund_code: str) -> Result[None]:
        """
        跳过定投
        
        Args:
            date_str: 日期字符串
            fund_code: 基金代码
        
        Returns:
            Result[None]
        """
        try:
            target_date = parse_date(date_str)
            return self.repository.skip_transaction(fund_code, target_date)
        except Exception as e:
            logger.error(f"skip_investment 失败: {e}")
            return Result.fail(error=str(e))
    
    def update_position(
        self,
        fund_code: str,
        amount: float,
        trade_time: Optional[str] = None
    ) -> Result[str]:
        """
        更新持仓
        
        Args:
            fund_code: 基金代码
            amount: 金额（正数买入，负数赎回）
            trade_time: 交易时间（可选）
        
        Returns:
            Result[tx_id]
        """
        try:
            if trade_time:
                trade_dt = parse_datetime(trade_time)
            else:
                trade_dt = datetime.now()
            
            tx_type = "buy" if amount > 0 else "sell"
            
            return self.repository.add_transaction(
                fund_code=fund_code,
                amount=abs(amount),
                trade_time=trade_dt,
                tx_type=tx_type
            )
        except Exception as e:
            logger.error(f"update_position 失败: {e}")
            return Result.fail(error=str(e))
    
    def confirm_shares(
        self,
        fund_code: str,
        trade_date: str,
        shares: float
    ) -> Result[None]:
        """
        确认份额
        
        Args:
            fund_code: 基金代码
            trade_date: 交易日期
            shares: 份额
        
        Returns:
            Result[None]
        """
        try:
            target_date = parse_date(trade_date)
            return self.repository.confirm_shares(fund_code, target_date, shares)
        except Exception as e:
            logger.error(f"confirm_shares 失败: {e}")
            return Result.fail(error=str(e))
    
    def delete_transaction(self, tx_id: str) -> Result[None]:
        """
        删除交易
        
        Args:
            tx_id: 交易 ID
        
        Returns:
            Result[None]
        """
        try:
            return self.repository.delete_transaction(tx_id)
        except Exception as e:
            logger.error(f"delete_transaction 失败: {e}")
            return Result.fail(error=str(e))
    
    def query_status(self) -> Result[dict]:
        """
        查询持仓状态
        
        Returns:
            Result[HoldingsSnapshot]
        """
        try:
            return self.repository.read_holdings()
        except Exception as e:
            logger.error(f"query_status 失败: {e}")
            return Result.fail(error=str(e))
    
    # ==================== 私有方法 ====================
    
    def _is_report_day(self, freq: str) -> bool:
        """
        判断今天是否应该发送报告
        
        Args:
            freq: 报告频率（daily/weekly/monthly/semiannual/annual）
            
        Returns:
            True 表示应该发送
        """
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


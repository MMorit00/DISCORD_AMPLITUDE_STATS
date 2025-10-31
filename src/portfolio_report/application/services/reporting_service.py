"""报告相关用例服务。"""

from __future__ import annotations

import logging
from typing import Literal, Optional, List
from datetime import datetime

from decimal import Decimal

from portfolio_report.application.services.base_service import BaseService
from portfolio_report.application.report_builder import ReportBuilder
from portfolio_report.domain.models import Signal
from portfolio_report.domain.services.portfolio import Portfolio


logger = logging.getLogger(__name__)


class ReportingService(BaseService):
    """报告生成与提醒服务。"""

    # ---- 组合 Portfolio（延迟） ----
    _portfolio: Optional[Portfolio] = None

    @property
    def portfolio(self) -> Portfolio:
        if self._portfolio is None:
            self._portfolio = Portfolio(
                funds_config=self.config.get("funds", {}),
                fund_types=self.config.get("fund_types", {}),
                target_weights=self.config.get_target_weights(),
            )

            try:
                tx_result = self.repository.load_all_transactions()
                if tx_result.success and tx_result.data:
                    self._portfolio.set_positions_from_transactions(tx_result.data)

                    price_map = {}
                    for fund_code in self._portfolio.positions.keys():
                        try:
                            data = self.fund_api.get_nav_or_estimate(fund_code, prefer_nav=True)
                            if data:
                                price_map[fund_code] = data
                        except Exception as e:
                            logger.warning(f"获取 {fund_code} 行情失败: {e}")

                    self._portfolio.update_positions_prices_from_map(price_map)
                    self._portfolio.recalc_weights()

                    try:
                        snapshot = self._portfolio.build_snapshot()
                        _ = self.repository.save_holdings(snapshot)
                    except Exception as e:
                        logger.warning(f"保存持仓快照异常: {e}")
            except Exception as e:
                logger.warning(f"初始化持仓失败: {e}")

        return self._portfolio

    # ---- 用例：生成报告 ----
    def generate_report(
        self,
        freq: Literal["daily", "weekly", "monthly", "semiannual", "annual"],
        force: bool = False,
    ) -> str:
        try:
            if not force and not self._is_report_day(freq):
                logger.info(f"今天不是 {freq} 报告日，跳过")
                return f"今天不是 {freq} 报告日"

            logger.info(f"开始生成 {freq} 报告...")

            signals: Optional[List[Signal]] = None
            if freq == "monthly":
                signals = self.signal_engine.generate_rebalance_signals(
                    weights_net=self.portfolio.weights_net,
                    target_weights=self.config.get_target_weights(),
                    total_value=self.portfolio.total_value_net,
                )
                signals = self.signal_engine.prioritize_signals(signals)

            builder = ReportBuilder(self.portfolio, self.signal_engine, self.config)
            if freq == "daily":
                return builder.build_daily_report()
            if freq == "weekly":
                return builder.build_weekly_report()
            return builder.build_monthly_report(signals)

        except Exception as e:
            error_msg = f"❌ 报告生成失败: {e}"
            logger.exception(error_msg)
            return error_msg

    # ---- 用例：信号提醒 ----
    def generate_signal_alert(self, alert_time: str = "14:40") -> str:
        try:
            signals = self.signal_engine.generate_rebalance_signals(
                weights_net=self.portfolio.weights_net,
                target_weights=self.config.get_target_weights(),
                total_value=self.portfolio.total_value_net,
            )
            if not signals:
                logger.info("无需发送信号提醒")
                return ""
            signals = self.signal_engine.prioritize_signals(signals)
            builder = ReportBuilder(self.portfolio, self.signal_engine, self.config)
            return builder.build_signal_alert(signals, alert_time)
        except Exception as e:
            error_msg = f"❌ 信号提醒生成失败: {e}"
            logger.exception(error_msg)
            return error_msg

    # ---- 辅助：发送 ----
    def send_report(self, report_text: str) -> bool:
        if not self.webhook_client:
            logger.warning("未配置 webhook 客户端，跳过发送")
            return False
        try:
            self.webhook_client.send(report_text)
            logger.info("✅ 报告发送成功")
            return True
        except Exception as exc:
            logger.error(f"发送报告失败: {exc}")
            return False

    # ---- 私有：是否报告日 ----
    def _is_report_day(self, freq: str) -> bool:
        today = datetime.now()
        if freq == "daily":
            return self.calendar.is_cn_trading_day(today)
        if freq == "weekly":
            return today.weekday() == 0
        if freq == "monthly":
            if today.day == 1:
                return self.calendar.is_cn_trading_day(today)
            if self.calendar.is_cn_trading_day(today):
                from datetime import timedelta
                yesterday = today - timedelta(days=1)
                return yesterday.month != today.month
            return False
        if freq == "semiannual":
            if today.month in [1, 7] and today.day <= 3:
                return self.calendar.is_cn_trading_day(today)
            return False
        if freq == "annual":
            if today.month == 1 and today.day <= 3:
                return self.calendar.is_cn_trading_day(today)
            return False
        return False



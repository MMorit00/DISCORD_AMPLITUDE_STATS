"""
确认轮询器（Application 层）：使用 GitHubRepository/ EastMoney/ TradingCalendar 编排确认流程
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Optional

from portfolio_report.config.loader import ConfigLoader
from portfolio_report.shared.constants import TransactionFields, Defaults
from portfolio_report.infrastructure.github.github_repository import GitHubRepository
from portfolio_report.infrastructure.market_data.eastmoney_client import EastMoneyFundAPI
from portfolio_report.infrastructure.notifications.discord_webhook_client import DiscordWebhookClient
from portfolio_report.domain.services.trading_calendar import TradingCalendar


logger = logging.getLogger(__name__)


class ConfirmationPoller:
    """确认轮询器（应用层编排）"""

    def __init__(
        self,
        repository: GitHubRepository,
        fund_api: EastMoneyFundAPI,
        calendar: TradingCalendar,
        webhook_url: str = "",
        config: Optional[ConfigLoader] = None,
    ):
        self.repository = repository
        self.fund_api = fund_api
        self.calendar = calendar
        self.webhook_url = webhook_url
        self.config = config or ConfigLoader()

    def _load_pending_transactions(self, today: date) -> List[Dict[str, str]]:
        """从 GitHub 加载待确认交易（预计确认日 <= today）"""
        result = self.repository.load_all_transactions()
        if not result.success or not result.data:
            return []
        pending: List[Dict[str, str]] = []
        for row in result.data:
            status = row.get(TransactionFields.status, "")
            expected_confirm_str = row.get(TransactionFields.expected_confirm_date, "")
            if status == "pending" and expected_confirm_str:
                try:
                    expected_date = datetime.strptime(expected_confirm_str, Defaults.date_format).date()
                    if expected_date <= today:
                        pending.append(row)
                except Exception:
                    continue
        return pending

    def _check_nav_confirmed(self, fund_code: str, expected_nav_date: str) -> Optional[Dict[str, str]]:
        """判断净值是否已公布（nav_date >= 预计净值日）"""
        nav_data = self.fund_api.get_latest_nav(fund_code)
        if not nav_data:
            return None
        if nav_data.get("nav_date") >= expected_nav_date:
            return nav_data
        return None

    def poll(self) -> int:
        """执行确认轮询，返回确认笔数"""
        today = date.today()
        pending_txs = self._load_pending_transactions(today)
        if not pending_txs:
            logger.info("无待确认交易")
            return 0

        confirmed_count = 0
        notifications: List[str] = []

        for tx in pending_txs:
            tx_id = tx.get(TransactionFields.tx_id)
            fund_code = tx.get(TransactionFields.fund_code)
            amount = tx.get(TransactionFields.amount)
            expected_nav_date = tx.get(TransactionFields.expected_nav_date)

            nav_data = self._check_nav_confirmed(fund_code, expected_nav_date)
            if not nav_data:
                continue

            # 计算份额（若未填写）
            shares = tx.get(TransactionFields.shares) or "0"
            if not shares or float(shares) == 0:
                try:
                    nav_value = float(nav_data["nav"]) if nav_data.get("nav") else 0.0
                    shares = str(float(amount) / nav_value) if nav_value > 0 else "0"
                except Exception:
                    shares = "0"

            # 使用仓储更新确认（以交易日为 confirm_date）
            try:
                trade_date_str = tx.get(TransactionFields.date)
                trade_dt = datetime.strptime(trade_date_str, Defaults.date_format).date()
                result = self.repository.confirm_shares(fund_code, trade_dt, float(shares))
                if result.success:
                    confirmed_count += 1
                    fund_name = self.config.get_fund_name(fund_code)
                    notifications.append(
                        f"✅ {fund_name} ({fund_code})\n"
                        f"   金额: ¥{amount}, 份额: {float(shares):.2f}\n"
                        f"   净值: {nav_data['nav']} ({nav_data['nav_date']})"
                    )
                else:
                    logger.warning(f"更新交易失败: {tx_id}, {result.error}")
            except Exception as e:
                logger.warning(f"确认交易异常: {tx_id}, {e}")

        # 发送通知
        if notifications and self.webhook_url:
            try:
                message = (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 份额确认通知 ({confirmed_count}笔)\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n" +
                    "\n\n".join(notifications) +
                    "\n\n━━━━━━━━━━━━━━━━━━━━"
                )
                DiscordWebhookClient(self.webhook_url).send(message)
            except Exception as e:
                logger.error(f"发送确认通知失败: {e}")

        return confirmed_count



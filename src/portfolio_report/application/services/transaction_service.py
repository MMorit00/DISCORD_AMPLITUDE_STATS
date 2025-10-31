"""交易与状态相关用例服务。"""

import logging
from typing import Optional
from datetime import datetime

from portfolio_report.application.services.base_service import BaseService
from portfolio_report.shared.types import Result
from portfolio_report.shared.utils import parse_date, parse_datetime


logger = logging.getLogger(__name__)


class TransactionService(BaseService):
    """交易增删改查与状态查询。"""

    def skip_investment(self, date_str: str, fund_code: str) -> Result[None]:
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
        trade_time: Optional[str] = None,
    ) -> Result[str]:
        try:
            trade_dt = parse_datetime(trade_time) if trade_time else datetime.now()
            tx_type = "buy" if amount > 0 else "sell"
            return self.repository.add_transaction(
                fund_code=fund_code,
                amount=abs(amount),
                trade_time=trade_dt,
                tx_type=tx_type,
            )
        except Exception as e:
            logger.error(f"update_position 失败: {e}")
            return Result.fail(error=str(e))

    def confirm_shares(
        self,
        fund_code: str,
        trade_date: str,
        shares: float,
    ) -> Result[None]:
        try:
            target_date = parse_date(trade_date)
            return self.repository.confirm_shares(fund_code, target_date, shares)
        except Exception as e:
            logger.error(f"confirm_shares 失败: {e}")
            return Result.fail(error=str(e))

    def delete_transaction(self, tx_id: str) -> Result[None]:
        try:
            return self.repository.delete_transaction(tx_id)
        except Exception as e:
            logger.error(f"delete_transaction 失败: {e}")
            return Result.fail(error=str(e))

    def query_status(self) -> Result[dict]:
        try:
            return self.repository.read_holdings()
        except Exception as e:
            logger.error(f"query_status 失败: {e}")
            return Result.fail(error=str(e))



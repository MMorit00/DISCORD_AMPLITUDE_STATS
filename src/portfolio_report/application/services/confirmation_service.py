"""确认轮询用例服务。"""

import logging
from typing import Optional

from portfolio_report.application.services.base_service import BaseService
from portfolio_report.application.confirm import ConfirmationPoller


logger = logging.getLogger(__name__)


class ConfirmationService(BaseService):
    """份额确认轮询服务。"""

    _poller: Optional[ConfirmationPoller] = None

    @property
    def poller(self) -> ConfirmationPoller:
        if self._poller is None:
            self._poller = ConfirmationPoller(
                repository=self.repository,
                fund_api=self.fund_api,
                calendar=self.calendar,
                webhook_url=self.settings.discord_webhook_url if hasattr(self.settings, 'discord_webhook_url') else "",
                config=self.config,
            )
        return self._poller

    def poll_confirmations(self) -> int:
        try:
            count = self.poller.poll()
            logger.info(f"确认轮询完成，处理了 {count} 笔交易")
            return count
        except Exception as e:
            logger.exception(f"确认轮询失败: {e}")
            return 0



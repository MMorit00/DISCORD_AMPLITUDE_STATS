"""
确认轮询器
定时检查基金净值/份额确认情况并自动回填
"""
import csv
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, TypedDict, Callable
from pathlib import Path

from utils.config_loader import ConfigLoader
from utils.discord_webhook import DiscordWebhookClient, get_webhook_url
from sources.eastmoney import get_fund_api
from core.trading_calendar import get_calendar

logger = logging.getLogger(__name__)


# ==================
# Types & Constants
# ==================

class NavData(TypedDict, total=False):
    """基金净值数据模型（最小字段集）"""
    nav: str
    nav_date: str

DATE_FMT = "%Y-%m-%d"


# ==================
# Repositories（状态/数据源）
# ==================

class TransactionsRepository:
    """交易记录仓储：负责 CSV 的读取/写回"""
    
    def __init__(self, transactions_file: Path):
        self.transactions_file = transactions_file
    
    def load_pending(self, today: date) -> List[Dict[str, str]]:
        """读取待确认交易（预计确认日 <= today）"""
        if not self.transactions_file.exists():
            return []
        
        pending: List[Dict[str, str]] = []
        with open(self.transactions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("status", "")
                expected_confirm_str = row.get("expected_confirm_date", "")
                if status == "pending" and expected_confirm_str:
                    try:
                        expected_date = datetime.strptime(expected_confirm_str, DATE_FMT).date()
                        if expected_date <= today:
                            pending.append(row)
                    except:
                        pass
        return pending
    
    def update_confirmation(self, tx_id: str, nav: str, nav_date: str, shares: str) -> bool:
        """根据 tx_id 更新确认字段并写回 CSV"""
        rows: List[Dict[str, str]] = []
        updated = False
        
        with open(self.transactions_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row.get("tx_id") == tx_id:
                    row["status"] = "confirmed"
                    row["confirm_date"] = nav_date
                    row["nav_kind"] = "净"
                    if shares:
                        row["shares"] = shares
                    updated = True
                rows.append(row)
        
        if not updated:
            return False
        
        with open(self.transactions_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        return True


# ==================
# Services（领域服务）
# ==================

class ConfirmationService:
    """确认检查服务：判断净值是否已公布"""
    
    def __init__(self, fund_api):
        self.fund_api = fund_api
    
    def check(self, fund_code: str, expected_nav_date: str) -> Optional[NavData]:
        nav_data: Optional[Dict] = self.fund_api.get_latest_nav(fund_code)
        if not nav_data:
            return None
        if nav_data.get("nav_date") >= expected_nav_date:
            return nav_data  # type: ignore[return-value]
        return None


class NotificationService:
    """通知服务：负责组装文案并发送到 Discord"""
    
    def __init__(self, webhook_url_getter: Callable[[], str] = get_webhook_url):
        self.webhook_url_getter = webhook_url_getter
    
    def send_confirmation_summary(self, confirmed_count: int, notifications: List[str]) -> None:
        if not notifications:
            return
        webhook_url = self.webhook_url_getter()
        message = (
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 份额确认通知 ({confirmed_count}笔)\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n" +
            "\n\n".join(notifications) +
            "\n\n━━━━━━━━━━━━━━━━━━━━"
        )
        DiscordWebhookClient(webhook_url).send(message)


# ==================
# Facade（编排层）
# ==================

class ConfirmationPoller:
    """确认轮询器"""
    
    def __init__(self, config: Optional[ConfigLoader] = None, data_dir: Optional[str] = None):
        self.config = config or ConfigLoader()
        
        if data_dir is None:
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
        
        self.data_dir = Path(data_dir)
        self.transactions_file = self.data_dir / "transactions.csv"
        
        # 依赖
        self.fund_api = get_fund_api()
        self.calendar = get_calendar()
        
        # 组装仓储与服务
        self.tx_repo = TransactionsRepository(self.transactions_file)
        self.confirm_service = ConfirmationService(self.fund_api)
        self.notifier = NotificationService()
    
    def load_pending_transactions(self) -> List[Dict[str, str]]:
        """加载待确认的交易（委托 TransactionsRepository）"""
        today = date.today()
        pending = self.tx_repo.load_pending(today)
        logger.info(f"找到 {len(pending)} 条待确认交易")
        return pending
    
    def check_confirmation(self, fund_code: str, expected_nav_date: str) -> Optional[Dict]:
        """检查净值是否已公布（委托 ConfirmationService）"""
        nav_data = self.confirm_service.check(fund_code, expected_nav_date)
        if nav_data:
            logger.info(f"{fund_code} 净值已公布: {nav_data['nav']} ({nav_data['nav_date']})")
        else:
            logger.debug(f"{fund_code} 净值尚未更新或无数据")
        return nav_data
    
    def update_confirmation(self, tx_id: str, nav: str, nav_date: str, shares: str) -> bool:
        """更新交易确认信息（委托 TransactionsRepository）"""
        ok = self.tx_repo.update_confirmation(tx_id, nav, nav_date, shares)
        if ok:
            logger.info(f"更新交易 {tx_id}: 确认日={nav_date}, 份额={shares}")
        else:
            logger.warning(f"未找到交易 {tx_id}")
        return ok
    
    def poll(self) -> int:
        """
        执行轮询
        
        Returns:
            确认的交易数量
        """
        pending_txs = self.load_pending_transactions()
        
        if not pending_txs:
            logger.info("无待确认交易")
            return 0
        
        confirmed_count = 0
        notifications = []
        
        for tx in pending_txs:
            tx_id = tx.get("tx_id")
            fund_code = tx.get("fund_code")
            expected_nav_date = tx.get("expected_nav_date")
            amount = tx.get("amount")
            
            # 检查确认
            nav_data = self.check_confirmation(fund_code, expected_nav_date)
            
            if nav_data:
                # 计算份额（如果尚未填写）
                shares = tx.get("shares")
                if not shares or shares == "0":
                    nav_value = float(nav_data['nav'])
                    shares = str(float(amount) / nav_value)
                
                # 更新确认
                if self.update_confirmation(
                    tx_id,
                    nav_data['nav'],
                    nav_data['nav_date'],
                    shares
                ):
                    confirmed_count += 1
                    
                    # 准备通知
                    fund_name = self.config.get_fund_name(fund_code)
                    notifications.append(
                        f"✅ {fund_name} ({fund_code})\n"
                        f"   金额: ¥{amount}, 份额: {float(shares):.2f}\n"
                        f"   净值: {nav_data['nav']} ({nav_data['nav_date']})"
                    )
        
        # 发送通知（委托 NotificationService）
        if notifications:
            try:
                self.notifier.send_confirmation_summary(confirmed_count, notifications)
                logger.info(f"已发送确认通知：{confirmed_count} 笔")
            except Exception as e:
                logger.error(f"发送确认通知失败: {e}")
        
        return confirmed_count


def main():
    """主函数（供 Actions 调用）"""
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    
    try:
        poller = ConfirmationPoller()
        count = poller.poll()
        
        logger.info(f"确认轮询完成，处理了 {count} 笔交易")
        sys.exit(0)
    
    except Exception as e:
        logger.exception(f"确认轮询失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()



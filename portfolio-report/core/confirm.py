"""
确认轮询器
定时检查基金净值/份额确认情况并自动回填
"""
import csv
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from pathlib import Path

from utils.config_loader import ConfigLoader
from utils.discord import post_to_discord, get_webhook_url
from sources.eastmoney import get_fund_api
from core.trading_calendar import get_calendar

logger = logging.getLogger(__name__)


class ConfirmationPoller:
    """确认轮询器"""
    
    def __init__(self, config: Optional[ConfigLoader] = None, data_dir: Optional[str] = None):
        self.config = config or ConfigLoader()
        
        if data_dir is None:
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
        
        self.data_dir = Path(data_dir)
        self.transactions_file = self.data_dir / "transactions.csv"
        
        self.fund_api = get_fund_api()
        self.calendar = get_calendar()
    
    def load_pending_transactions(self) -> List[Dict[str, str]]:
        """加载待确认的交易"""
        if not self.transactions_file.exists():
            return []
        
        pending = []
        today = date.today()
        
        try:
            with open(self.transactions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    status = row.get("status", "")
                    expected_confirm_str = row.get("expected_confirm_date", "")
                    
                    # 只处理 pending 状态且预计确认日 <= 今天的记录
                    if status == "pending" and expected_confirm_str:
                        try:
                            expected_date = datetime.strptime(expected_confirm_str, "%Y-%m-%d").date()
                            if expected_date <= today:
                                pending.append(row)
                        except:
                            pass
            
            logger.info(f"找到 {len(pending)} 条待确认交易")
            return pending
        
        except Exception as e:
            logger.error(f"加载待确认交易失败: {e}")
            return []
    
    def check_confirmation(self, fund_code: str, expected_nav_date: str) -> Optional[Dict]:
        """
        检查净值是否已公布
        
        Args:
            fund_code: 基金代码
            expected_nav_date: 预计净值日
        
        Returns:
            净值数据或 None
        """
        try:
            nav_data = self.fund_api.get_latest_nav(fund_code)
            
            if not nav_data:
                return None
            
            # 检查净值日期是否匹配
            if nav_data.get("nav_date") >= expected_nav_date:
                logger.info(f"{fund_code} 净值已公布: {nav_data['nav']} ({nav_data['nav_date']})")
                return nav_data
            
            logger.debug(f"{fund_code} 净值尚未更新: {nav_data.get('nav_date')} < {expected_nav_date}")
            return None
        
        except Exception as e:
            logger.error(f"检查 {fund_code} 确认失败: {e}")
            return None
    
    def update_confirmation(self, tx_id: str, nav: str, nav_date: str, shares: str) -> bool:
        """
        更新交易确认信息
        
        Args:
            tx_id: 交易ID
            nav: 净值
            nav_date: 净值日期
            shares: 确认份额
        
        Returns:
            是否更新成功
        """
        try:
            # 读取所有交易
            rows = []
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
                        logger.info(f"更新交易 {tx_id}: 确认日={nav_date}, 份额={shares}")
                    
                    rows.append(row)
            
            if not updated:
                logger.warning(f"未找到交易 {tx_id}")
                return False
            
            # 写回文件
            with open(self.transactions_file, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            
            logger.info(f"交易确认已更新: {tx_id}")
            return True
        
        except Exception as e:
            logger.error(f"更新确认失败: {e}")
            return False
    
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
        
        # 发送通知
        if notifications:
            try:
                webhook_url = get_webhook_url()
                message = (
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 份额确认通知 ({confirmed_count}笔)\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n" +
                    "\n\n".join(notifications) +
                    "\n\n━━━━━━━━━━━━━━━━━━━━"
                )
                post_to_discord(webhook_url, message)
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


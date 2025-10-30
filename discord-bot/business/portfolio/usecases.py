"""
Portfolio 用例实现
职责：实现投资组合相关的业务逻辑
依赖：infrastructure.GitHubRepository, shared.types, shared.utils
"""
import logging
from datetime import datetime
from typing import Optional

from infrastructure import GitHubRepository
from shared import Result, HoldingsSnapshot, parse_date, parse_datetime

logger = logging.getLogger(__name__)


class PortfolioUseCases:
    """投资组合用例"""
    
    def __init__(self, repository: GitHubRepository):
        """
        初始化
        
        Args:
            repository: GitHub 仓储
        """
        self.repository = repository
    
    # ==================== 用例实现 ====================
    
    def skip_investment(self, date: str, fund_code: str) -> Result[None]:
        """
        跳过定投
        
        Args:
            date: 日期字符串
            fund_code: 基金代码
        
        Returns:
            Result[None]
        """
        try:
            target_date = parse_date(date)
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
    
    def query_status(self) -> Result[HoldingsSnapshot]:
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


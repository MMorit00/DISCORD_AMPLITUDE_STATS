"""
交易记录仓储
职责：负责读写 transactions.csv
依赖：shared, domain
"""
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import date

from shared import Result, parse_date, generate_tx_id, ensure_parent_dir
from config.constants import TransactionFields, TransactionStatus, TransactionType

logger = logging.getLogger(__name__)


class TransactionRepository:
    """交易记录仓储：负责读取和写入 transactions.csv"""
    
    def __init__(self, transactions_file: Path):
        """
        初始化
        
        Args:
            transactions_file: transactions.csv 文件路径
        """
        self.transactions_file = Path(transactions_file)
        ensure_parent_dir(self.transactions_file)
    
    def load_all(self) -> Result[List[Dict[str, str]]]:
        """
        加载所有交易记录
        
        Returns:
            Result[List[Dict[str, str]]]
        """
        if not self.transactions_file.exists():
            logger.warning(f"交易记录文件不存在: {self.transactions_file}")
            return Result.ok(data=[], message="交易记录文件不存在")
        
        try:
            transactions = []
            with open(self.transactions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    transactions.append(row)
            
            logger.info(f"加载了 {len(transactions)} 条交易记录")
            return Result.ok(data=transactions)
        
        except Exception as e:
            logger.error(f"加载交易记录失败: {e}")
            return Result.fail(error=str(e))
    
    def load_by_fund(self, fund_code: str) -> Result[List[Dict[str, str]]]:
        """
        按基金代码加载交易记录
        
        Args:
            fund_code: 基金代码
            
        Returns:
            Result[List[Dict[str, str]]]
        """
        result = self.load_all()
        if not result.success:
            return result
        
        transactions = [
            tx for tx in result.data
            if tx.get(TransactionFields.fund_code) == fund_code
        ]
        
        return Result.ok(data=transactions)
    
    def load_by_status(self, status: str) -> Result[List[Dict[str, str]]]:
        """
        按状态加载交易记录
        
        Args:
            status: 状态（pending/confirmed/skipped）
            
        Returns:
            Result[List[Dict[str, str]]]
        """
        result = self.load_all()
        if not result.success:
            return result
        
        transactions = [
            tx for tx in result.data
            if tx.get(TransactionFields.status) == status
        ]
        
        return Result.ok(data=transactions)
    
    def find_by_id(self, tx_id: str) -> Result[Optional[Dict[str, str]]]:
        """
        按 ID 查找交易
        
        Args:
            tx_id: 交易 ID
            
        Returns:
            Result[Optional[Dict[str, str]]]
        """
        result = self.load_all()
        if not result.success:
            return result
        
        for tx in result.data:
            if tx.get(TransactionFields.tx_id) == tx_id:
                return Result.ok(data=tx)
        
        return Result.ok(data=None, message="未找到交易记录")
    
    def save_all(self, transactions: List[Dict[str, str]]) -> Result[None]:
        """
        保存所有交易记录
        
        Args:
            transactions: 交易记录列表
            
        Returns:
            Result[None]
        """
        try:
            ensure_parent_dir(self.transactions_file)
            
            with open(self.transactions_file, 'w', encoding='utf-8', newline='') as f:
                if not transactions:
                    # 写入空文件的表头
                    fieldnames = TransactionFields.all_fields()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                else:
                    # 使用第一条记录的键作为字段名
                    fieldnames = list(transactions[0].keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(transactions)
            
            logger.info(f"保存了 {len(transactions)} 条交易记录")
            return Result.ok()
        
        except Exception as e:
            logger.error(f"保存交易记录失败: {e}")
            return Result.fail(error=str(e))
    
    def add(self, transaction: Dict[str, str]) -> Result[str]:
        """
        添加交易记录
        
        Args:
            transaction: 交易记录
            
        Returns:
            Result[tx_id]
        """
        try:
            result = self.load_all()
            if not result.success:
                return Result.fail(error=result.error)
            
            transactions = result.data
            
            # 生成 tx_id（如果没有）
            if not transaction.get(TransactionFields.tx_id):
                transaction[TransactionFields.tx_id] = generate_tx_id()
            
            tx_id = transaction[TransactionFields.tx_id]
            
            # 检查是否已存在
            if any(tx.get(TransactionFields.tx_id) == tx_id for tx in transactions):
                return Result.fail(error=f"交易 ID 已存在: {tx_id}")
            
            transactions.append(transaction)
            
            save_result = self.save_all(transactions)
            if not save_result.success:
                return Result.fail(error=save_result.error)
            
            return Result.ok(data=tx_id, message=f"已添加交易: {tx_id}")
        
        except Exception as e:
            logger.error(f"添加交易失败: {e}")
            return Result.fail(error=str(e))
    
    def update(self, tx_id: str, updates: Dict[str, str]) -> Result[None]:
        """
        更新交易记录
        
        Args:
            tx_id: 交易 ID
            updates: 要更新的字段
            
        Returns:
            Result[None]
        """
        try:
            result = self.load_all()
            if not result.success:
                return Result.fail(error=result.error)
            
            transactions = result.data
            found = False
            
            for tx in transactions:
                if tx.get(TransactionFields.tx_id) == tx_id:
                    tx.update(updates)
                    found = True
                    break
            
            if not found:
                return Result.fail(error=f"未找到交易: {tx_id}")
            
            save_result = self.save_all(transactions)
            if not save_result.success:
                return Result.fail(error=save_result.error)
            
            return Result.ok(message=f"已更新交易: {tx_id}")
        
        except Exception as e:
            logger.error(f"更新交易失败: {e}")
            return Result.fail(error=str(e))
    
    def delete(self, tx_id: str) -> Result[None]:
        """
        删除交易记录（软删除，标记为 skipped）
        
        Args:
            tx_id: 交易 ID
            
        Returns:
            Result[None]
        """
        return self.update(tx_id, {
            TransactionFields.status: TransactionStatus.skipped,
            TransactionFields.type: TransactionType.skip
        })


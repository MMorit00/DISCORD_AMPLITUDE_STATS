"""
GitHub 数据仓储
职责：封装 GitHub API 与 CSV 文件操作，提供语义化的数据访问接口
依赖：config.Settings, shared.types
"""
import json
import logging
import base64
from datetime import datetime, date
from typing import Optional, Dict, Any

from github import Github, GithubException

from shared.types import Result, Transaction, HoldingsSnapshot
from shared.utils import generate_short_id
from config.settings import Settings

logger = logging.getLogger(__name__)


class GitHubRepository:
    """GitHub 数据仓储实现"""
    
    def __init__(self, settings: Settings):
        """
        初始化
        
        Args:
            settings: 配置对象
        """
        self.settings = settings
        self.github = Github(settings.github_token)
        self.repo = self.github.get_repo(settings.github_repo)
        self.data_path = settings.github_data_path
        
        logger.info(f"GitHub 仓储初始化: {settings.github_repo}")
    
    # ==================== 私有方法：文件读写 ====================
    
    def _read_file(self, file_path: str) -> tuple[str, str]:
        """
        读取文件内容和 SHA
        
        Returns:
            (content, sha)
        """
        try:
            file_content = self.repo.get_contents(file_path)
            content = base64.b64decode(file_content.content).decode('utf-8')
            sha = file_content.sha
            return content, sha
        
        except GithubException as e:
            if e.status == 404:
                logger.warning(f"文件不存在: {file_path}")
                return "", ""
            raise
    
    def _write_file(
        self,
        file_path: str,
        content: str,
        message: str,
        sha: Optional[str] = None
    ) -> Result[str]:
        """
        写入文件（幂等）
        
        Args:
            file_path: 文件路径
            content: 文件内容
            message: Commit 消息
            sha: 文件 SHA（用于并发控制）
        
        Returns:
            Result[commit_sha]
        """
        try:
            tx_id = generate_short_id()
            full_message = f"{message} [tx:{tx_id}]"
            
            if sha:
                result = self.repo.update_file(
                    path=file_path,
                    message=full_message,
                    content=content,
                    sha=sha
                )
            else:
                result = self.repo.create_file(
                    path=file_path,
                    message=full_message,
                    content=content
                )
            
            logger.info(f"GitHub 写入成功: {file_path}, tx={tx_id}")
            return Result.ok(data=result['commit'].sha, message=f"提交成功: {tx_id}")
        
        except GithubException as e:
            if e.status == 409:
                logger.warning(f"并发冲突: {file_path}, 重试...")
                _, new_sha = self._read_file(file_path)
                if new_sha:
                    return self._write_file(file_path, content, message, new_sha)
            
            logger.error(f"GitHub 写入失败: {e}")
            return Result.fail(error=str(e))
    
    # ==================== 公开接口：交易操作 ====================
    
    def skip_transaction(self, fund_code: str, target_date: date) -> Result[None]:
        """
        跳过定投（软删除）
        
        Args:
            fund_code: 基金代码
            target_date: 目标日期
        
        Returns:
            Result[None]
        """
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return Result.fail(error="交易文件不存在")
            
            lines = content.strip().split('\n')
            header = lines[0]
            rows = []
            found = False
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                values = line.split(',')
                row_date = values[1] if len(values) > 1 else ""
                row_code = values[2] if len(values) > 2 else ""
                
                if row_date == target_date.strftime("%Y-%m-%d") and row_code == fund_code:
                    values[5] = "skip"
                    values[15] = "skipped"
                    found = True
                    logger.info(f"标记为跳过: {fund_code} {target_date}")
                
                rows.append(','.join(values))
            
            if not found:
                return Result.fail(error=f"未找到 {fund_code} {target_date} 的交易记录")
            
            new_content = header + '\n' + '\n'.join(rows) + '\n'
            
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] skip_investment {fund_code} {target_date}",
                sha
            )
            
            return Result.ok(message=result.message) if result.success else result
        
        except Exception as e:
            logger.error(f"skip_transaction 失败: {e}")
            return Result.fail(error=str(e))
    
    def add_transaction(
        self,
        fund_code: str,
        amount: float,
        trade_time: datetime,
        tx_type: str = "buy"
    ) -> Result[str]:
        """
        添加交易记录
        
        Args:
            fund_code: 基金代码
            amount: 金额
            trade_time: 交易时间
            tx_type: 交易类型（buy/sell）
        
        Returns:
            Result[tx_id]
        """
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return Result.fail(error="交易文件不存在")
            
            tx_id = f"tx{datetime.now().strftime('%Y%m%d%H%M%S')}"
            trade_date = trade_time.strftime("%Y-%m-%d")
            
            new_row = [
                tx_id,
                trade_date,
                fund_code,
                str(amount),
                "0",
                tx_type,
                "手动添加",
                "alipay",
                trade_time.strftime("%Y-%m-%d %H:%M:%S"),
                "pre15",
                trade_date,
                "domestic",
                trade_date,
                trade_date,
                "",
                "pending",
                "估",
                "0.0",
                "false"
            ]
            
            new_content = content.strip() + '\n' + ','.join(new_row) + '\n'
            
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] add_transaction {fund_code} {tx_type} {amount}",
                sha
            )
            
            return Result.ok(data=tx_id, message=result.message) if result.success else Result.fail(error=result.error)
        
        except Exception as e:
            logger.error(f"add_transaction 失败: {e}")
            return Result.fail(error=str(e))
    
    def confirm_shares(
        self,
        fund_code: str,
        trade_date: date,
        shares: float
    ) -> Result[None]:
        """
        确认交易份额
        
        Args:
            fund_code: 基金代码
            trade_date: 交易日期
            shares: 份额
        
        Returns:
            Result[None]
        """
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return Result.fail(error="交易文件不存在")
            
            lines = content.strip().split('\n')
            header = lines[0]
            rows = []
            found = False
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                values = line.split(',')
                row_date = values[1] if len(values) > 1 else ""
                row_code = values[2] if len(values) > 2 else ""
                
                if row_date == trade_date.strftime("%Y-%m-%d") and row_code == fund_code:
                    values[4] = str(shares)
                    values[14] = trade_date.strftime("%Y-%m-%d")
                    values[15] = "confirmed"
                    values[16] = "净"
                    found = True
                    logger.info(f"确认份额: {fund_code} {trade_date} {shares}")
                
                rows.append(','.join(values))
            
            if not found:
                return Result.fail(error=f"未找到 {fund_code} {trade_date} 的交易记录")
            
            new_content = header + '\n' + '\n'.join(rows) + '\n'
            
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] confirm_shares {fund_code} {trade_date} {shares}",
                sha
            )
            
            return Result.ok(message=result.message) if result.success else result
        
        except Exception as e:
            logger.error(f"confirm_shares 失败: {e}")
            return Result.fail(error=str(e))
    
    def delete_transaction(self, tx_id: str) -> Result[None]:
        """
        删除交易（软删除）
        
        Args:
            tx_id: 交易 ID
        
        Returns:
            Result[None]
        """
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return Result.fail(error="交易文件不存在")
            
            lines = content.strip().split('\n')
            header = lines[0]
            rows = []
            found = False
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                values = line.split(',')
                row_tx_id = values[0] if len(values) > 0 else ""
                
                if row_tx_id == tx_id:
                    values[5] = "deleted"
                    values[15] = "void"
                    found = True
                    logger.info(f"软删除交易: {tx_id}")
                
                rows.append(','.join(values))
            
            if not found:
                return Result.fail(error=f"未找到交易 {tx_id}")
            
            new_content = header + '\n' + '\n'.join(rows) + '\n'
            
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] delete_transaction {tx_id}",
                sha
            )
            
            return Result.ok(message=result.message) if result.success else result
        
        except Exception as e:
            logger.error(f"delete_transaction 失败: {e}")
            return Result.fail(error=str(e))
    
    # ==================== 公开接口：查询操作 ====================
    
    def read_holdings(self) -> Result[HoldingsSnapshot]:
        """
        读取持仓快照
        
        Returns:
            Result[HoldingsSnapshot]
        """
        try:
            file_path = f"{self.data_path}/holdings.json"
            content, _ = self._read_file(file_path)
            
            if not content:
                return Result.fail(error="持仓文件不存在")
            
            data = json.loads(content)
            
            snapshot = HoldingsSnapshot(
                total_value_net=data.get('total_value_net', 0),
                weights_net=data.get('weights_net', {}),
                last_update=data.get('last_update', ''),
                raw_data=data
            )
            
            return Result.ok(data=snapshot)
        
        except Exception as e:
            logger.error(f"read_holdings 失败: {e}")
            return Result.fail(error=str(e))


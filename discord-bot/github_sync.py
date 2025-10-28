"""
GitHub 幂等写入模块
支持：If-Match 并发控制、事务 ID 幂等、软删除
"""
import os
import csv
import json
import logging
import uuid
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from pathlib import Path
import base64

from github import Github, GithubException

logger = logging.getLogger(__name__)


class GitHubSync:
    """GitHub 数据同步器"""
    
    def __init__(
        self,
        repo_name: Optional[str] = None,
        token: Optional[str] = None,
        data_path: str = "portfolio-report/data"
    ):
        """
        初始化
        
        Args:
            repo_name: 仓库名（如 username/repo）
            token: GitHub Personal Access Token
            data_path: 数据文件路径前缀
        """
        self.repo_name = repo_name or os.getenv("GITHUB_REPO")
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.data_path = data_path
        
        if not self.repo_name or not self.token:
            raise ValueError("缺少 GITHUB_REPO 或 GITHUB_TOKEN 环境变量")
        
        self.github = Github(self.token)
        self.repo = self.github.get_repo(self.repo_name)
        
        logger.info(f"GitHub 同步器初始化: {self.repo_name}")
    
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
    ) -> Dict[str, Any]:
        """
        写入文件（幂等）
        
        Args:
            file_path: 文件路径
            content: 文件内容
            message: Commit 消息
            sha: 文件 SHA（用于 If-Match）
        
        Returns:
            操作结果
        """
        try:
            # 生成事务 ID（幂等性）
            tx_id = str(uuid.uuid4())[:8]
            full_message = f"{message} [tx:{tx_id}]"
            
            if sha:
                # 更新现有文件（带 If-Match）
                result = self.repo.update_file(
                    path=file_path,
                    message=full_message,
                    content=content,
                    sha=sha
                )
            else:
                # 创建新文件
                result = self.repo.create_file(
                    path=file_path,
                    message=full_message,
                    content=content
                )
            
            logger.info(f"GitHub 写入成功: {file_path}, tx={tx_id}")
            
            return {
                "success": True,
                "commit_sha": result['commit'].sha,
                "tx_id": tx_id
            }
        
        except GithubException as e:
            if e.status == 409:  # Conflict
                logger.warning(f"并发冲突: {file_path}, 重试...")
                # 重新读取并重试
                _, new_sha = self._read_file(file_path)
                if new_sha:
                    return self._write_file(file_path, content, message, new_sha)
            
            logger.error(f"GitHub 写入失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def skip_transaction(self, fund_code: str, target_date: date) -> Dict[str, Any]:
        """
        跳过定投（软删除）
        
        Args:
            fund_code: 基金代码
            target_date: 目标日期
        
        Returns:
            操作结果
        """
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return {"success": False, "error": "交易文件不存在"}
            
            # 解析 CSV
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
                
                # 匹配目标记录
                if row_date == target_date.strftime("%Y-%m-%d") and row_code == fund_code:
                    # 软删除：修改 type 为 skip
                    values[5] = "skip"  # type 字段
                    values[15] = "skipped"  # status 字段
                    found = True
                    logger.info(f"标记为跳过: {fund_code} {target_date}")
                
                rows.append(','.join(values))
            
            if not found:
                return {
                    "success": False,
                    "error": f"未找到 {fund_code} {target_date} 的交易记录"
                }
            
            # 重新组装 CSV
            new_content = header + '\n' + '\n'.join(rows) + '\n'
            
            # 写入
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] skip_investment {fund_code} {target_date}",
                sha
            )
            
            return result
        
        except Exception as e:
            logger.error(f"skip_transaction 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def add_transaction(
        self,
        fund_code: str,
        amount: float,
        trade_time: datetime,
        tx_type: str = "buy"
    ) -> Dict[str, Any]:
        """
        添加交易记录
        
        Args:
            fund_code: 基金代码
            amount: 金额
            trade_time: 交易时间
            tx_type: 交易类型（buy/sell）
        
        Returns:
            操作结果
        """
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return {"success": False, "error": "交易文件不存在"}
            
            # 生成新记录
            tx_id = f"tx{datetime.now().strftime('%Y%m%d%H%M%S')}"
            trade_date = trade_time.strftime("%Y-%m-%d")
            
            # TODO: 调用 TradingCalendar 计算 cutoff_flag, expected_confirm_date 等
            # 简化版：先填基础字段
            new_row = [
                tx_id,
                trade_date,
                fund_code,
                str(amount),
                "0",  # shares (待确认)
                tx_type,
                "手动添加",  # notes
                "alipay",  # platform
                trade_time.strftime("%Y-%m-%d %H:%M:%S"),  # trade_time_local
                "pre15",  # cutoff_flag (TODO: 实际计算)
                trade_date,  # trade_day_cn
                "domestic",  # fund_type (TODO: 从配置读取)
                trade_date,  # expected_nav_date
                trade_date,  # expected_confirm_date
                "",  # confirm_date
                "pending",  # status
                "估",  # nav_kind
                "0.0",  # front_load_fee_rate
                "false"  # redemption_penalty_flag
            ]
            
            # 添加到文件
            new_content = content.strip() + '\n' + ','.join(new_row) + '\n'
            
            # 写入
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] update_position {fund_code} {tx_type} {amount}",
                sha
            )
            
            return result
        
        except Exception as e:
            logger.error(f"add_transaction 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def confirm_transaction(
        self,
        fund_code: str,
        trade_date: date,
        shares: float
    ) -> Dict[str, Any]:
        """确认交易份额"""
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return {"success": False, "error": "交易文件不存在"}
            
            # 解析并更新
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
                    values[4] = str(shares)  # shares
                    values[14] = trade_date.strftime("%Y-%m-%d")  # confirm_date
                    values[15] = "confirmed"  # status
                    values[16] = "净"  # nav_kind
                    found = True
                    logger.info(f"确认份额: {fund_code} {trade_date} {shares}")
                
                rows.append(','.join(values))
            
            if not found:
                return {
                    "success": False,
                    "error": f"未找到 {fund_code} {trade_date} 的交易记录"
                }
            
            new_content = header + '\n' + '\n'.join(rows) + '\n'
            
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] confirm_shares {fund_code} {trade_date} {shares}",
                sha
            )
            
            return result
        
        except Exception as e:
            logger.error(f"confirm_transaction 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_transaction(self, tx_id: str) -> Dict[str, Any]:
        """删除交易（软删除）"""
        try:
            file_path = f"{self.data_path}/transactions.csv"
            content, sha = self._read_file(file_path)
            
            if not content:
                return {"success": False, "error": "交易文件不存在"}
            
            # 解析并标记删除
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
                    # 软删除
                    values[5] = "deleted"  # type
                    values[15] = "void"  # status
                    found = True
                    logger.info(f"软删除交易: {tx_id}")
                
                rows.append(','.join(values))
            
            if not found:
                return {
                    "success": False,
                    "error": f"未找到交易 {tx_id}"
                }
            
            new_content = header + '\n' + '\n'.join(rows) + '\n'
            
            result = self._write_file(
                file_path,
                new_content,
                f"[bot] delete_transaction {tx_id}",
                sha
            )
            
            return result
        
        except Exception as e:
            logger.error(f"delete_transaction 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def read_holdings(self) -> Optional[Dict[str, Any]]:
        """读取持仓快照"""
        try:
            file_path = f"{self.data_path}/holdings.json"
            content, _ = self._read_file(file_path)
            
            if content:
                return json.loads(content)
            
            return None
        
        except Exception as e:
            logger.error(f"读取持仓失败: {e}")
            return None


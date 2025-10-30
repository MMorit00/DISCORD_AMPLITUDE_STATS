"""
持仓快照仓储
职责：负责读写 holdings.json
依赖：shared
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from shared import Result, ensure_parent_dir

logger = logging.getLogger(__name__)


class HoldingsRepository:
    """持仓快照仓储：负责读取和写入 holdings.json"""
    
    def __init__(self, holdings_file: Path):
        """
        初始化
        
        Args:
            holdings_file: holdings.json 文件路径
        """
        self.holdings_file = Path(holdings_file)
        ensure_parent_dir(self.holdings_file)
    
    def load(self) -> Result[Optional[Dict[str, Any]]]:
        """
        加载持仓快照
        
        Returns:
            Result[Optional[Dict[str, Any]]]
        """
        if not self.holdings_file.exists():
            logger.info(f"持仓快照文件不存在: {self.holdings_file}")
            return Result.ok(data=None, message="持仓快照文件不存在")
        
        try:
            with open(self.holdings_file, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
            
            logger.info(f"加载持仓快照: {self.holdings_file}")
            return Result.ok(data=snapshot)
        
        except Exception as e:
            logger.error(f"加载持仓快照失败: {e}")
            return Result.fail(error=str(e))
    
    def save(self, snapshot: Dict[str, Any]) -> Result[None]:
        """
        保存持仓快照
        
        Args:
            snapshot: 持仓快照数据
            
        Returns:
            Result[None]
        """
        try:
            ensure_parent_dir(self.holdings_file)
            
            with open(self.holdings_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
            logger.info(f"保存持仓快照: {self.holdings_file}")
            return Result.ok()
        
        except Exception as e:
            logger.error(f"保存持仓快照失败: {e}")
            return Result.fail(error=str(e))
    
    def exists(self) -> bool:
        """
        检查持仓快照文件是否存在
        
        Returns:
            bool
        """
        return self.holdings_file.exists()


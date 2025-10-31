"""
信号状态仓储（Infrastructure）：负责 state.json 的读写
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any


logger = logging.getLogger(__name__)


class SignalStateRepository:
    """信号状态仓储（负责 state.json 的读写）
    
    职责：
    - 加载状态文件 -> Dict
    - 保存状态 Dict -> 文件
    - 初始化空状态结构
    """
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
    
    def load(self) -> Dict[str, Any]:
        """加载状态文件，不存在或失败则返回默认空结构"""
        if not self.state_file.exists():
            return self._default_state()
        
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载状态文件失败: {e}")
            return self._default_state()
    
    def save(self, state: Dict[str, Any]) -> None:
        """保存状态到文件"""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"保存信号状态: {self.state_file}")
        except Exception as e:
            logger.error(f"保存状态文件失败: {e}")
    
    def _default_state(self) -> Dict[str, Any]:
        """默认空状态结构"""
        return {
            "last_signals": {},
            "signal_history": [],
            "last_rebalance": None,
            "cooldown_tracker": {}
        }



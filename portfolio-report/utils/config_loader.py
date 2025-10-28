"""
配置文件加载工具
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            # 默认路径：相对于当前文件的 ../config/config.yaml
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "config" / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self):
        """加载配置文件"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在：{self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        logger.info(f"已加载配置文件：{self.config_path}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_target_weights(self) -> Dict[str, float]:
        """获取目标权重"""
        return self.get('target_weights', {})
    
    def get_funds_by_asset(self, asset: str) -> list:
        """获取指定资产类别的基金列表"""
        funds = self.get('funds', {})
        return funds.get(asset, [])
    
    def get_fund_name(self, fund_code: str) -> str:
        """获取基金名称"""
        names = self.get('fund_names', {})
        return names.get(fund_code, fund_code)
    
    def get_fund_type(self, fund_code: str) -> str:
        """获取基金类型（domestic/QDII）"""
        types = self.get('fund_types', {})
        return types.get(fund_code, 'domestic')
    
    def get_thresholds(self) -> Dict[str, Any]:
        """获取阈值配置"""
        return self.get('thresholds', {})
    
    def get_timezone(self) -> str:
        """获取时区"""
        return self.get('timezone', 'Asia/Shanghai')
    
    def get_llm_routing(self, purpose: str) -> Dict[str, Any]:
        """
        获取 LLM 路由配置
        
        Args:
            purpose: 'parse' 或 'write'
        """
        routing = self.get('llm_routing', {})
        return routing.get(purpose, {})
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config


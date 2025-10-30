"""
配置文件加载工具

分层职责：
- 路径解析：确定最终配置文件路径
- 文件读取：读取原始文本内容
- 内容解析：将文本解析为 Python 字典
- 配置构建：对解析结果做必要的结构整理（如需要）

说明：不额外考虑错误处理，仅聚焦层次清晰与注释简洁。
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器

    职责：负责加载 YAML 配置并提供点号路径访问与领域便捷方法。
    使用优先级：入参路径 > 环境变量 PORTFOLIO_CONFIG > 默认相对路径。
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        # 路径解析层
        self.config_path: Path = self._resolve_config_path(config_path)
        # 配置存储
        self._config: Dict[str, Any] = {}
        # 加载流程（读取 -> 解析 -> 构建）
        self._load()
    
    # ==================
    # 分层私有方法
    # ==================

    def _resolve_config_path(self, config_path: Optional[Union[str, Path]]) -> Path:
        """路径解析：入参 > 环境变量 > 默认路径。"""
        if config_path:
            return Path(config_path)
        env_path = os.getenv("PORTFOLIO_CONFIG")
        if env_path:
            return Path(env_path)
        base_dir = Path(__file__).parent.parent.parent
        return base_dir / "config" / "config.yaml"

    def _read_text(self, path: Path) -> str:
        """文件读取：读取原始文本。"""
        return path.read_text(encoding="utf-8")

    def _parse_yaml(self, text: str) -> Dict[str, Any]:
        """内容解析：YAML 文本 -> 字典。"""
        data = yaml.safe_load(text)
        return data or {}

    def _build_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """配置构建：如需对解析后的结构做轻量整理，可在此扩展。"""
        return data

    def _load(self) -> None:
        """加载流程：读取 -> 解析 -> 构建 -> 存储。"""
        raw_text = self._read_text(self.config_path)
        parsed = self._parse_yaml(raw_text)
        self._config = self._build_config(parsed)
        logger.info(f"已加载配置文件：{self.config_path}")

    def reload(self) -> None:
        """重新加载配置。"""
        self._load()
    




# 以下是配置项的便捷方法
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项（点号路径）。

        行为：一旦中间层或最终值为 None，返回 default。
        例：get("a.b.c", default={})
        """
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
    
    def get_funds_by_asset(self, asset: str) -> List[str]:
        """获取指定资产类别的基金列表"""
        funds = self.get('funds', {})
        return list(funds.get(asset, []))
    
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
    


    # ==================
    # 便捷方法
    # ==================
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config


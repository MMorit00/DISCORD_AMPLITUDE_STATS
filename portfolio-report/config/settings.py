"""
配置管理模块
职责：集中加载环境变量与运行时配置
对齐 discord-bot 的配置模式，使用 dataclass + 环境变量
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


@dataclass
class Settings:
    """应用配置（不使用单例，支持测试注入）"""
    
    # ==================== 运行时配置 ====================
    log_level: str = "INFO"
    timezone: str = "Asia/Shanghai"
    
    # ==================== 数据路径 ====================
    data_dir: Path = Path(__file__).parent.parent / "data"
    config_path: Optional[Path] = None
    
    # ==================== Discord 配置 ====================
    discord_webhook_url: str = ""
    
    # ==================== HTTP 代理 ====================
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    
    @staticmethod
    def from_env() -> "Settings":
        """从环境变量加载配置"""
        # 基础配置
        log_level = os.getenv("LOG_LEVEL", "INFO")
        timezone = os.getenv("TZ", "Asia/Shanghai")
        
        # 数据路径
        data_dir_str = os.getenv("DATA_DIR")
        if data_dir_str:
            data_dir = Path(data_dir_str)
        else:
            data_dir = Path(__file__).parent.parent / "data"
        
        config_path_str = os.getenv("PORTFOLIO_CONFIG")
        config_path = Path(config_path_str) if config_path_str else None
        
        # Discord
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        
        # 代理
        http_proxy = os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("HTTPS_PROXY")
        
        return Settings(
            log_level=log_level,
            timezone=timezone,
            data_dir=data_dir,
            config_path=config_path,
            discord_webhook_url=discord_webhook_url,
            http_proxy=http_proxy,
            https_proxy=https_proxy,
        )
    
    @property
    def proxy(self) -> Optional[str]:
        """获取代理配置"""
        return self.https_proxy or self.http_proxy


def load_settings() -> Settings:
    """加载配置（提供函数式接口，不强制单例）"""
    return Settings.from_env()


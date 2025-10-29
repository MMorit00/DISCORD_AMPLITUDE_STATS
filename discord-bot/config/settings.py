"""
配置管理模块
职责：集中加载环境变量与运行时配置
依赖：仅依赖 os、dotenv
"""
import os
from typing import List, Optional
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """应用配置"""
    
    # ==================== Discord 配置 ====================
    discord_token: str
    allowed_user_ids: List[int]
    
    # ==================== GitHub 配置 ====================
    github_token: str
    github_repo: str
    github_data_path: str = "portfolio-report/data"
    
    # ==================== LLM 配置 ====================
    ark_api_key: Optional[str] = None
    ark_model_id: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    zhipu_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    # ==================== 运行时配置 ====================
    log_level: str = "INFO"
    timezone: str = "Asia/Shanghai"
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    
    def __init__(self):
        """从环境变量加载配置"""
        # Discord
        self.discord_token = self._require("DISCORD_TOKEN")
        user_ids_str = self._require("ALLOWED_USER_IDS")
        self.allowed_user_ids = [
            int(uid.strip()) 
            for uid in user_ids_str.split(",") 
            if uid.strip()
        ]
        
        # GitHub
        self.github_token = self._require("GITHUB_TOKEN")
        self.github_repo = self._require("GITHUB_REPO")
        self.github_data_path = os.getenv("GITHUB_DATA_PATH", self.github_data_path)
        
        # LLM (至少需要一个)
        self.ark_api_key = os.getenv("ARK_API_KEY")
        self.ark_model_id = os.getenv("ARK_MODEL_ID")
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.zhipu_api_key = os.getenv("ZHIPU_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not any([
            self.ark_api_key,
            self.dashscope_api_key,
            self.zhipu_api_key,
            self.openai_api_key
        ]):
            raise ValueError("至少需要配置一个 LLM API Key")
        
        # 运行时
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.timezone = os.getenv("TZ", self.timezone)
        self.http_proxy = os.getenv("HTTP_PROXY")
        self.https_proxy = os.getenv("HTTPS_PROXY")
    
    def _require(self, key: str) -> str:
        """读取必需的环境变量"""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"缺少必需的环境变量: {key}")
        return value
    
    @property
    def proxy(self) -> Optional[str]:
        """获取代理配置"""
        return self.https_proxy or self.http_proxy


# ==================== 全局配置实例 ====================
settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置单例"""
    global settings
    if settings is None:
        settings = Settings()
    return settings


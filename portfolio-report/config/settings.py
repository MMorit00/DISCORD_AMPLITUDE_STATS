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

# 加载多层 .env 文件（根目录优先，随后 discord_bot 覆盖）
def _load_env_chain():
    base_dir = Path(__file__).parents[2]  # amplitude-discord-report/
    candidates = [
        base_dir / ".env",
        base_dir / "discord_bot" / ".env",
        base_dir / "discord-bot" / ".env",  # 兼容旧目录名
    ]
    for env_file in candidates:
        if env_file.exists():
            # 允许后加载的文件覆盖之前的值，保证更具体的环境优先生效
            load_dotenv(dotenv_path=env_file, override=True)

_load_env_chain()


@dataclass
class Settings:
    """应用配置（统一 portfolio-report 与 discord-bot）"""
    
    # ==================== 运行时配置 ====================
    log_level: str = "INFO"
    timezone: str = "Asia/Shanghai"
    
    # ==================== 数据路径 ====================
    data_dir: Path = Path(__file__).parent.parent / "data"
    config_path: Optional[Path] = None
    
    # ==================== Discord 配置 ====================
    discord_token: Optional[str] = None
    discord_webhook_url: str = ""
    allowed_user_ids: list[int] = None
    
    # ==================== GitHub 配置 ====================
    github_token: str = ""
    github_repo: str = ""
    github_data_path: str = "portfolio-report/data"
    
    # ==================== LLM 配置 ====================
    ark_api_key: Optional[str] = None
    ark_model_id: Optional[str] = None
    dashscope_api_key: Optional[str] = None
    zhipu_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    
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
        discord_token = os.getenv("DISCORD_TOKEN")
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        allowed_user_ids_str = os.getenv("ALLOWED_USER_IDS", "")
        allowed_user_ids = [
            int(uid.strip()) 
            for uid in allowed_user_ids_str.split(",") 
            if uid.strip()
        ] if allowed_user_ids_str else []
        
        # GitHub
        github_token = os.getenv("GITHUB_TOKEN", "")
        github_repo = os.getenv("GITHUB_REPO", "")
        github_data_path = os.getenv("GITHUB_DATA_PATH", "portfolio-report/data")
        
        # LLM
        ark_api_key = os.getenv("ARK_API_KEY")
        ark_model_id = os.getenv("ARK_MODEL_ID")
        dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        zhipu_api_key = os.getenv("ZHIPU_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # 代理
        http_proxy = os.getenv("HTTP_PROXY")
        https_proxy = os.getenv("HTTPS_PROXY")
        
        return Settings(
            log_level=log_level,
            timezone=timezone,
            data_dir=data_dir,
            config_path=config_path,
            discord_token=discord_token,
            discord_webhook_url=discord_webhook_url,
            allowed_user_ids=allowed_user_ids,
            github_token=github_token,
            github_repo=github_repo,
            github_data_path=github_data_path,
            ark_api_key=ark_api_key,
            ark_model_id=ark_model_id,
            dashscope_api_key=dashscope_api_key,
            zhipu_api_key=zhipu_api_key,
            openai_api_key=openai_api_key,
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


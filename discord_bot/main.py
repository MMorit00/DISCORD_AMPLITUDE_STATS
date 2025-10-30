"""
主入口
职责：依赖注入与应用启动
运行方式：python -m discord_bot.main（推荐）
"""
import sys
from pathlib import Path

# 路径设置
_current_dir = Path(__file__).parent
_portfolio_report_dir = _current_dir.parent / "portfolio-report"

import os
import logging

# ==================== 导入 portfolio-report 模块 ====================
# 将 portfolio-report 添加到路径（供其内部导入使用）
sys.path.insert(0, str(_portfolio_report_dir))

from config.settings import load_settings
from infrastructure.github.repository import GitHubRepository
from infrastructure.market_data.eastmoney import EastMoneyFundAPI
from infrastructure.config.config_loader import ConfigLoader
from domain.services.trading_calendar import TradingCalendar
from domain.services.metrics import MetricsCalculator
from domain.services.signals import SignalEngine
from application.portfolio_service import PortfolioService

# ==================== 导入 discord_bot 模块 ====================
from discord_bot.infrastructure.llm.clients import LLMClient
from discord_bot.business.llm.parser import LLMParser
from discord_bot.presentation.message_router import MessageRouter
from discord_bot.presentation.discord.bot_adapter import DiscordBotAdapter


def setup_logging(log_level: str):
    """配置日志"""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main():
    """主函数：组装依赖并启动"""
    try:
        # 加载配置（使用统一的 Settings）
        settings = load_settings()
        setup_logging(settings.log_level)
        
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("Portfolio Discord Bot 启动")
        logger.info("=" * 50)
        
        # ==================== 依赖注入 ====================
        
        logger.info("初始化基础设施层...")
        
        # 配置
        config = ConfigLoader(settings.config_path)
        
        # GitHub 仓储
        github_repo = GitHubRepository(settings)
        
        # 外部服务
        fund_api = EastMoneyFundAPI()
        calendar = TradingCalendar(config.get_timezone())
        metrics = MetricsCalculator()
        signal_engine = SignalEngine(metrics, config)
        
        # LLM 客户端
        llm_client = LLMClient(settings)
        
        # ==================== 应用层 ====================
        
        logger.info("初始化应用服务...")
        
        # Portfolio 应用服务（复用 portfolio-report 的）
        portfolio_service = PortfolioService(
            settings=settings,
            config=config,
            repository=github_repo,
            fund_api=fund_api,
            calendar=calendar,
            metrics=metrics,
            signal_engine=signal_engine,
            webhook_client=None  # Bot 不需要 Webhook
        )
        
        # LLM 解析器
        llm_parser = LLMParser(llm_client)
        
        # ==================== 表现层 ====================
        
        logger.info("初始化表现层...")
        
        # 消息路由器（使用 PortfolioService）
        message_router = MessageRouter(llm_parser, portfolio_service)
        
        # Discord Bot 适配器
        discord_bot = DiscordBotAdapter(settings, message_router)
        
        # ==================== 启动应用 ====================
        
        logger.info("=" * 50)
        logger.info("所有组件初始化完成，启动 Discord Bot")
        logger.info("=" * 50)
        
        discord_bot.run()
    
    except ValueError as e:
        # 配置错误
        print(f"❌ 配置错误: {e}", file=sys.stderr)
        sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n👋 Bot 已停止")
        sys.exit(0)
    
    except Exception as e:
        print(f"❌ 启动失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


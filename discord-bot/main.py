"""
主入口
职责：依赖注入与应用启动
"""
import os
import sys
import logging

from config import get_settings
from infrastructure import GitHubRepository, LLMClient
from business import LLMParser, PortfolioUseCases
from presentation import MessageRouter, DiscordBotAdapter


def setup_logging(log_level: str):
    """配置日志"""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main():
    """主函数：组装依赖并启动"""
    try:
        # 加载配置
        settings = get_settings()
        setup_logging(settings.log_level)
        
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("Portfolio Discord Bot 启动")
        logger.info("=" * 50)
        
        # ==================== 依赖注入 ====================
        
        # 基础设施层
        logger.info("初始化基础设施层...")
        github_repository = GitHubRepository(settings)
        llm_client = LLMClient(settings)
        
        # 业务层
        logger.info("初始化业务层...")
        llm_parser = LLMParser(llm_client)
        portfolio_usecases = PortfolioUseCases(github_repository)
        
        # 表现层
        logger.info("初始化表现层...")
        message_router = MessageRouter(llm_parser, portfolio_usecases)
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


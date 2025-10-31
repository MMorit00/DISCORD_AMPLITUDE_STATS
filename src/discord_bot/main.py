"""
主入口
职责：依赖注入与应用启动
运行方式：python -m discord_bot.main（推荐）
"""
import sys
import logging

from portfolio_report.application.container import build_application

# ==================== 导入 discord_bot 模块 ====================
from discord_bot.infrastructure.llm.clients import LLMClient
from discord_bot.business.llm.parser import LLMParser
from discord_bot.presentation.message_router import MessageRouter
from discord_bot.presentation.bot_adapter import DiscordBotAdapter


def setup_logging(log_level: str):
    """配置日志"""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main():
    """主函数：组装依赖并启动"""
    try:
        # 复用 portfolio_report 的装配工厂
        context = build_application()
        settings = context.settings
        setup_logging(settings.log_level)
        
        logger = logging.getLogger(__name__)
        logger.info("=" * 50)
        logger.info("Portfolio Discord Bot 启动")
        logger.info("=" * 50)
        
        # ==================== 依赖注入 ====================
        
        # LLM 客户端
        llm_client = LLMClient(settings)
        
        transaction_service = context.transaction_service
        
        # LLM 解析器
        llm_parser = LLMParser(llm_client)
        
        # ==================== 表现层 ====================
        
        logger.info("初始化表现层...")
        
        # 消息路由器（使用 TransactionService）
        message_router = MessageRouter(llm_parser, transaction_service)
        
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


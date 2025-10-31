#!/usr/bin/env python3
"""
Portfolio Report CLI
投资组合报告生成器

Usage:
    python main.py --freq daily
    python main.py --freq weekly
    python main.py --freq monthly
"""
import sys
import logging
import argparse

from portfolio_report.config.settings import load_settings
from portfolio_report.infrastructure.github.repository import GitHubRepository
from portfolio_report.infrastructure.market_data.eastmoney import EastMoneyFundAPI
from portfolio_report.config.loader import ConfigLoader
from portfolio_report.infrastructure.notifications.discord import DiscordWebhookClient
from portfolio_report.domain.services.trading_calendar import TradingCalendar
from portfolio_report.domain.services.metrics import MetricsCalculator
from portfolio_report.application.signals_engine import SignalEngine
from portfolio_report.application.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)


def setup_logging(log_level: str):
    """配置日志"""
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def main():
    """主函数：依赖注入 + 执行用例"""
    parser = argparse.ArgumentParser(description="投资组合报告生成器")
    parser.add_argument(
        "--freq",
        type=str,
        required=True,
        choices=["daily", "weekly", "monthly", "semiannual", "annual"],
        help="报告频率"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制发送（忽略交易日判定）"
    )
    
    args = parser.parse_args()
    
    try:
        # ==================== 加载配置 ====================
        settings = load_settings()
        setup_logging(settings.log_level)
        
        logger.info("=" * 60)
        logger.info(f"Portfolio Report - {args.freq.upper()} 报告")
        logger.info("=" * 60)
        
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
        
        # Discord Webhook（可选）
        webhook_client = None
        if settings.discord_webhook_url:
            webhook_client = DiscordWebhookClient(settings.discord_webhook_url)
        
        # ==================== 应用层 ====================
        
        logger.info("初始化应用服务...")
        
        service = PortfolioService(
            settings=settings,
            config=config,
            repository=github_repo,
            fund_api=fund_api,
            calendar=calendar,
            metrics=metrics,
            signal_engine=signal_engine,
            webhook_client=webhook_client
        )
        
        # ==================== 执行用例 ====================
        
        logger.info(f"开始生成 {args.freq} 报告...")
        
        report = service.generate_report(args.freq, args.force)
        
        # ==================== 发送报告 ====================
        
        if settings.discord_webhook_url:
            logger.info("发送到 Discord...")
            discord_client = DiscordWebhookClient(settings.discord_webhook_url)
            discord_client.send(report)
            logger.info("✅ 报告发送成功")
        else:
            logger.warning("未配置 DISCORD_WEBHOOK_URL，跳过发送")
            print("\n" + "=" * 60)
            print(report)
            print("=" * 60)
        
        logger.info("=" * 60)
        logger.info("任务完成")
        logger.info("=" * 60)
    
    except Exception as e:
        error_msg = f"❌ 报告生成失败: {e}"
        logger.exception(error_msg)
        
        # 尝试发送错误通知
        try:
            settings = load_settings()
            if settings.discord_webhook_url:
                DiscordWebhookClient(settings.discord_webhook_url).send(error_msg)
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()

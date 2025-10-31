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

from portfolio_report.application.container import build_application

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
    
    context = None

    try:
        # ==================== 加载应用 ====================
        context = build_application()
        settings = context.settings
        setup_logging(settings.log_level)
        
        logger.info("=" * 60)
        logger.info(f"Portfolio Report - {args.freq.upper()} 报告")
        logger.info("=" * 60)
        
        service = context.reporting_service
        
        # ==================== 执行用例 ====================
        
        logger.info(f"开始生成 {args.freq} 报告...")
        
        report = service.generate_report(args.freq, args.force)
        
        # ==================== 发送报告 ====================
        
        if settings.discord_webhook_url:
            logger.info("发送到 Discord...")
            service.send_report(report)
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
        if context and context.settings.discord_webhook_url:
            try:
                context.reporting_service.send_report(error_msg)
            except Exception:
                pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Portfolio Report CLI
投资组合报告生成器

Usage:
    python main.py --freq daily
    python main.py --freq weekly
    python main.py --freq monthly
"""
import os
import sys
import logging
import argparse
from datetime import datetime, date
from pathlib import Path

# 添加 portfolio-report 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import ConfigLoader
from utils.discord import post_to_discord, get_webhook_url
from core.portfolio import Portfolio
from core.signals import SignalEngine
from core.trading_calendar import get_calendar
from report.builder import ReportBuilder

# 日志配置
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


def is_report_day(freq: str, calendar) -> bool:
    """
    判断今天是否应该发送报告
    
    Args:
        freq: 报告频率（daily/weekly/monthly/semiannual/annual）
        calendar: 交易日历实例
    
    Returns:
        True 表示应该发送
    """
    today = datetime.now()
    
    # 日报：每个交易日
    if freq == "daily":
        return calendar.is_cn_trading_day(today)
    
    # 周报：周一
    elif freq == "weekly":
        return today.weekday() == 0  # Monday
    
    # 月报：每月首个交易日
    elif freq == "monthly":
        if today.day == 1:
            return calendar.is_cn_trading_day(today)
        # 如果今天是交易日，且昨天是上个月
        if calendar.is_cn_trading_day(today):
            yesterday = today.replace(day=today.day-1) if today.day > 1 else None
            if yesterday and yesterday.month != today.month:
                return True
        return False
    
    # 半年报：1月1日 或 7月1日 的次一交易日
    elif freq == "semiannual":
        if today.month in [1, 7] and today.day <= 3:
            return calendar.is_cn_trading_day(today)
        return False
    
    # 年报：1月1日的次一交易日
    elif freq == "annual":
        if today.month == 1 and today.day <= 3:
            return calendar.is_cn_trading_day(today)
        return False
    
    return False


def main():
    """主函数"""
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
        # 初始化
        config = ConfigLoader()
        calendar = get_calendar(config.get_timezone())
        
        # 判断是否应该发送
        if not args.force and not is_report_day(args.freq, calendar):
            logger.info(f"今天不是 {args.freq} 报告日，跳过")
            return
        
        logger.info(f"开始生成 {args.freq} 报告...")
        
        # 刷新持仓数据
        portfolio = Portfolio(config)
        portfolio.refresh()
        
        # 生成信号
        signal_engine = SignalEngine(config)
        signals = signal_engine.generate_rebalance_signals(
            weights_net=portfolio.weights_net,
            target_weights=config.get_target_weights(),
            total_value=portfolio.total_value_net
        )
        
        # 优先级排序
        signals = signal_engine.prioritize_signals(signals)
        
        # 生成报告
        builder = ReportBuilder(portfolio, signal_engine, config)
        
        if args.freq == "daily":
            report = builder.build_daily_report()
        elif args.freq == "weekly":
            report = builder.build_weekly_report()
        elif args.freq == "monthly":
            report = builder.build_monthly_report(signals)
        else:
            # TODO: 实现半年报和年报
            report = builder.build_monthly_report(signals)
        
        # 发送到 Discord
        webhook_url = get_webhook_url()
        post_to_discord(webhook_url, report)
        
        logger.info(f"{args.freq} 报告发送成功")
    
    except Exception as e:
        error_msg = f"❌ 报告生成失败: {e}"
        logger.exception(error_msg)
        
        # 尝试发送错误通知
        try:
            webhook_url = get_webhook_url()
            post_to_discord(webhook_url, error_msg)
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()


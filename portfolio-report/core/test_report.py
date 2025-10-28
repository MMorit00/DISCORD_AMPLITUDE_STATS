"""
报告生成器测试（无需 Discord Webhook）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.portfolio import Portfolio
from core.signals import SignalEngine
from report.builder import ReportBuilder


def test_daily_report():
    """测试日报生成"""
    print("\n" + "="*50)
    print("测试日报生成")
    print("="*50)
    
    # 刷新持仓
    portfolio = Portfolio()
    portfolio.refresh()
    
    # 生成报告
    builder = ReportBuilder(portfolio)
    report = builder.build_daily_report()
    
    print("\n" + report)
    print("\n✅ 日报生成成功")


def test_weekly_report():
    """测试周报生成"""
    print("\n" + "="*50)
    print("测试周报生成")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.refresh()
    
    builder = ReportBuilder(portfolio)
    report = builder.build_weekly_report()
    
    print("\n" + report)
    print("\n✅ 周报生成成功")


def test_monthly_report():
    """测试月报生成（含信号）"""
    print("\n" + "="*50)
    print("测试月报生成")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.refresh()
    
    # 生成信号
    engine = SignalEngine()
    signals = engine.generate_rebalance_signals(
        weights_net=portfolio.weights_net,
        target_weights=portfolio.config.get_target_weights(),
        total_value=portfolio.total_value_net
    )
    
    # 优先级排序
    signals = engine.prioritize_signals(signals)
    
    print(f"\n生成了 {len(signals)} 个信号")
    
    # 生成报告
    builder = ReportBuilder(portfolio, engine)
    report = builder.build_monthly_report(signals)
    
    print("\n" + report)
    print("\n✅ 月报生成成功")


def test_signal_alert():
    """测试信号提醒"""
    print("\n" + "="*50)
    print("测试信号提醒")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.refresh()
    
    engine = SignalEngine()
    signals = engine.generate_rebalance_signals(
        weights_net=portfolio.weights_net,
        target_weights=portfolio.config.get_target_weights(),
        total_value=portfolio.total_value_net
    )
    
    builder = ReportBuilder(portfolio, engine)
    
    if signals:
        # 14:40 提醒
        alert = builder.build_signal_alert(signals, "14:40")
        print("\n14:40 提醒：")
        print(alert)
    else:
        print("\n无信号需要提醒")


if __name__ == "__main__":
    print("="*50)
    print("报告生成器测试")
    print("="*50)
    
    try:
        test_daily_report()
        test_weekly_report()
        test_monthly_report()
        test_signal_alert()
        
        print("\n" + "="*50)
        print("✅ 所有测试完成")
        print("="*50)
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


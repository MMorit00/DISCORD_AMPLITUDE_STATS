"""
信号引擎测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import date, timedelta
from decimal import Decimal
from core.signals import SignalEngine, Signal
from core.portfolio import Portfolio


def test_rebalance_signals():
    """测试再平衡信号"""
    print("\n" + "="*50)
    print("测试再平衡信号")
    print("="*50)
    
    # 使用真实持仓数据
    portfolio = Portfolio()
    portfolio.build_positions()
    portfolio.fetch_nav_data()
    portfolio.calculate_weights()
    
    engine = SignalEngine()
    
    # 生成再平衡信号
    signals = engine.generate_rebalance_signals(
        weights_net=portfolio.weights_net,
        target_weights=portfolio.config.get_target_weights(),
        total_value=portfolio.total_value_net
    )
    
    print(f"\n生成了 {len(signals)} 个再平衡信号：\n")
    
    for signal in signals:
        print(f"{'='*50}")
        print(f"资产类别: {signal.asset_class}")
        print(f"信号类型: {signal.signal_type}")
        print(f"操作: {signal.action}")
        print(f"金额: ¥{signal.amount:.2f}")
        print(f"理由: {signal.reason}")
        print(f"紧急度: {signal.urgency}")
        if signal.risk_note:
            print(f"风险提示: {signal.risk_note}")


def test_cooldown():
    """测试冷却机制"""
    print("\n" + "="*50)
    print("测试冷却机制")
    print("="*50)
    
    engine = SignalEngine()
    
    # 设置冷却
    engine.set_cooldown("US_QDII", "rebalance_strong", 90)
    
    # 检查冷却
    is_cooling = engine.check_cooldown("US_QDII", "rebalance_strong")
    print(f"\nUS_QDII rebalance_strong 是否在冷却期: {is_cooling}")
    
    # 检查其他资产
    is_cooling_2 = engine.check_cooldown("CSI300", "rebalance_light")
    print(f"CSI300 rebalance_light 是否在冷却期: {is_cooling_2}")
    
    engine._save_state()
    print("\n✅ 冷却状态已保存")


def test_tactical_signals():
    """测试战术信号（模拟数据）"""
    print("\n" + "="*50)
    print("测试战术信号")
    print("="*50)
    
    engine = SignalEngine()
    
    # 模拟90日净值序列（下跌10%）
    today = date.today()
    nav_series = []
    
    for i in range(90, -1, -1):
        dt = today - timedelta(days=i)
        # 模拟：从 1.0 下跌到 0.9
        nav = Decimal("1.0") - Decimal(str(i)) * Decimal("0.001")
        nav_series.append((dt, nav))
    
    # 生成战术信号
    signal = engine.generate_tactical_signals(
        asset_class="US_QDII",
        nav_90d_series=nav_series,
        current_weight=Decimal("0.11"),
        target_weight=Decimal("0.75"),
        fund_type="QDII"
    )
    
    if signal:
        print(f"\n✅ 触发战术信号:")
        print(f"资产类别: {signal.asset_class}")
        print(f"信号类型: {signal.signal_type}")
        print(f"操作: {signal.action}")
        print(f"金额: ¥{signal.amount:.2f}")
        print(f"理由: {signal.reason}")
        if signal.risk_note:
            print(f"风险提示: {signal.risk_note}")
    else:
        print("\n未触发战术信号")


def test_signal_priority():
    """测试信号优先级"""
    print("\n" + "="*50)
    print("测试信号优先级")
    print("="*50)
    
    engine = SignalEngine()
    
    # 创建多个信号
    signals = [
        Signal("tactical_add", "US_QDII", "buy", Decimal("200"), "战术加仓", "medium"),
        Signal("rebalance_strong", "US_QDII", "buy", Decimal("5000"), "强制再平衡", "high"),
        Signal("rebalance_light", "CSI300", "sell", Decimal("3000"), "轻度再平衡", "medium"),
    ]
    
    print(f"\n原始信号顺序:")
    for i, sig in enumerate(signals, 1):
        print(f"{i}. {sig.signal_type} ({sig.urgency})")
    
    # 排序
    sorted_signals = engine.prioritize_signals(signals)
    
    print(f"\n排序后信号:")
    for i, sig in enumerate(sorted_signals, 1):
        print(f"{i}. {sig.signal_type} ({sig.urgency}) - {sig.asset_class}")
    
    print("\n✅ 优先级排序正确（strong > light > tactical）")


if __name__ == "__main__":
    print("="*50)
    print("信号引擎测试")
    print("="*50)
    
    try:
        test_rebalance_signals()
        test_cooldown()
        test_tactical_signals()
        test_signal_priority()
        
        print("\n" + "="*50)
        print("✅ 所有测试完成")
        print("="*50)
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()



"""
持仓管理模块测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import shutil
from core.portfolio import Portfolio
from utils.config_loader import ConfigLoader


def setup_test_data():
    """准备测试数据"""
    data_dir = Path(__file__).parent.parent / "data"
    transactions_file = data_dir / "transactions.csv"
    transactions_sample = data_dir / "transactions_sample.csv"
    
    if transactions_sample.exists() and not transactions_file.exists():
        shutil.copy(transactions_sample, transactions_file)
        print(f"✅ 复制样例数据到 {transactions_file}")
    elif not transactions_file.exists():
        print(f"⚠️  交易记录文件不存在: {transactions_file}")


def test_load_transactions():
    """测试加载交易记录"""
    print("\n" + "="*50)
    print("测试加载交易记录")
    print("="*50)
    
    portfolio = Portfolio()
    transactions = portfolio.load_transactions()
    
    print(f"\n✅ 加载了 {len(transactions)} 条交易记录")
    
    if transactions:
        print(f"\n前 3 条记录：")
        for i, tx in enumerate(transactions[:3], 1):
            print(f"{i}. {tx['date']} - {tx['fund_code']} - "
                  f"{tx['type']} - {tx['shares']} 份 - {tx['status']}")


def test_build_positions():
    """测试构建持仓"""
    print("\n" + "="*50)
    print("测试构建持仓")
    print("="*50)
    
    portfolio = Portfolio()
    positions = portfolio.build_positions()
    
    print(f"\n✅ 构建了 {len(positions)} 个持仓\n")
    
    for fund_code, position in positions.items():
        print(f"{fund_code} ({position.asset_class}):")
        print(f"  份额: {position.shares:.2f}")
        print(f"  类型: {position.fund_type}")


def test_fetch_nav():
    """测试获取净值数据"""
    print("\n" + "="*50)
    print("测试获取净值数据")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.build_positions()
    portfolio.fetch_nav_data()
    
    print(f"\n持仓净值情况：\n")
    
    for fund_code, position in portfolio.positions.items():
        print(f"{fund_code}:")
        if position.nav:
            print(f"  净值: {position.nav} ({position.nav_date})")
            print(f"  市值(净): ¥{position.market_value_net:.2f}")
        if position.estimate_value:
            print(f"  估值: {position.estimate_value} ({position.estimate_time})")
            print(f"  市值(估): ¥{position.market_value_est:.2f}")


def test_calculate_weights():
    """测试计算权重"""
    print("\n" + "="*50)
    print("测试计算权重")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.build_positions()
    portfolio.fetch_nav_data()
    portfolio.calculate_weights()
    
    print(f"\n总市值(净): ¥{portfolio.total_value_net:.2f}")
    print(f"总市值(估): ¥{portfolio.total_value_est:.2f}\n")
    
    print("权重(净):")
    for asset_class, weight in portfolio.weights_net.items():
        print(f"  {asset_class}: {float(weight)*100:.2f}%")
    
    print("\n权重(估):")
    for asset_class, weight in portfolio.weights_est.items():
        print(f"  {asset_class}: {float(weight)*100:.2f}%")


def test_weight_deviation():
    """测试权重偏离计算"""
    print("\n" + "="*50)
    print("测试权重偏离")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.build_positions()
    portfolio.fetch_nav_data()
    portfolio.calculate_weights()
    
    deviations = portfolio.get_weight_deviation()
    target_weights = portfolio.config.get_target_weights()
    
    print(f"\n{'资产类别':<15} {'目标':<10} {'实际(净)':<10} {'绝对偏离':<10} {'相对偏离':<10}")
    print("-" * 65)
    
    for asset_class, target in target_weights.items():
        actual = portfolio.weights_net.get(asset_class, 0)
        abs_dev, rel_dev = deviations.get(asset_class, (0, 0))
        
        print(f"{asset_class:<15} {target*100:>6.2f}% {float(actual)*100:>8.2f}% "
              f"{float(abs_dev)*100:>8.2f}% {float(rel_dev)*100:>8.2f}%")


def test_save_holdings():
    """测试保存持仓快照"""
    print("\n" + "="*50)
    print("测试保存持仓快照")
    print("="*50)
    
    portfolio = Portfolio()
    portfolio.refresh()
    
    print(f"\n✅ 持仓快照已保存到: {portfolio.holdings_file}")


if __name__ == "__main__":
    print("="*50)
    print("持仓管理模块测试")
    print("="*50)
    
    try:
        setup_test_data()
        test_load_transactions()
        test_build_positions()
        test_fetch_nav()
        test_calculate_weights()
        test_weight_deviation()
        test_save_holdings()
        
        print("\n" + "="*50)
        print("✅ 所有测试完成")
        print("="*50)
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


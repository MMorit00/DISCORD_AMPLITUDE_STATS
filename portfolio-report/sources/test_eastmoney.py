"""
东方财富数据源测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sources.eastmoney import get_fund_api


def test_realtime_estimate():
    """测试实时估值获取"""
    print("\n" + "="*50)
    print("测试实时估值获取")
    print("="*50)
    
    api = get_fund_api()
    
    # 测试A股基金
    fund_code = "000051"
    print(f"\n获取 {fund_code} 实时估值...")
    estimate = api.get_realtime_estimate(fund_code)
    
    if estimate:
        print(f"✅ 基金名称: {estimate['name']}")
        print(f"✅ 估算净值: {estimate['estimate_value']}")
        print(f"✅ 估值时间: {estimate['estimate_time']}")
        print(f"✅ 涨跌幅: {estimate['change_percent']}%")
        print(f"✅ 昨日净值: {estimate['last_nav']} ({estimate['last_nav_date']})")
        print(f"✅ 标识: {estimate['nav_kind']}")
    else:
        print("❌ 获取失败")


def test_latest_nav():
    """测试最新净值获取"""
    print("\n" + "="*50)
    print("测试最新净值获取")
    print("="*50)
    
    api = get_fund_api()
    
    # 测试QDII基金
    fund_code = "018043"
    print(f"\n获取 {fund_code} 最新净值...")
    nav = api.get_latest_nav(fund_code)
    
    if nav:
        print(f"✅ 基金名称: {nav['name']}")
        print(f"✅ 单位净值: {nav['nav']}")
        print(f"✅ 净值日期: {nav['nav_date']}")
        print(f"✅ 累计净值: {nav['accumulated_nav']}")
        print(f"✅ 涨跌幅: {nav['change_percent']}%")
        print(f"✅ 标识: {nav['nav_kind']}")
    else:
        print("❌ 获取失败")


def test_smart_fetch():
    """测试智能获取（净值/估值）"""
    print("\n" + "="*50)
    print("测试智能获取")
    print("="*50)
    
    api = get_fund_api()
    
    funds = ["000051", "018043", "019305"]
    
    for fund_code in funds:
        print(f"\n获取 {fund_code}...")
        data = api.get_nav_or_estimate(fund_code)
        
        if data:
            print(f"✅ {data['name']}")
            
            if data['nav_kind'] == '估':
                print(f"   估算净值: {data['estimate_value']} ({data['estimate_time']})")
                print(f"   涨跌幅: {data['change_percent']}%")
            else:
                print(f"   单位净值: {data['nav']} ({data['nav_date']})")
                print(f"   涨跌幅: {data['change_percent']}%")
            
            print(f"   数据类型: {data['nav_kind']}")
        else:
            print(f"❌ 获取失败")


def test_historical_nav():
    """测试历史净值获取"""
    print("\n" + "="*50)
    print("测试历史净值获取")
    print("="*50)
    
    api = get_fund_api()
    
    fund_code = "000051"
    print(f"\n获取 {fund_code} 最近10天净值...")
    history = api.get_historical_nav(fund_code, limit=10)
    
    if history:
        print(f"✅ 获取到 {len(history)} 条数据\n")
        
        print(f"{'日期':<12} {'净值':<10} {'涨跌幅':<10}")
        print("-" * 40)
        
        for item in history[:5]:  # 只显示前5条
            print(f"{item['date']:<12} {item['nav']:<10} {item['change_percent']:>8}%")
        
        if len(history) > 5:
            print("...")
    else:
        print("❌ 获取失败")


def test_cache():
    """测试缓存功能"""
    print("\n" + "="*50)
    print("测试缓存功能")
    print("="*50)
    
    api = get_fund_api(cache_ttl=60)
    
    fund_code = "000051"
    
    print(f"\n第一次获取 {fund_code}...")
    import time
    start = time.time()
    data1 = api.get_latest_nav(fund_code)
    time1 = time.time() - start
    print(f"耗时: {time1:.3f}s")
    
    print(f"\n第二次获取 {fund_code}（应使用缓存）...")
    start = time.time()
    data2 = api.get_latest_nav(fund_code)
    time2 = time.time() - start
    print(f"耗时: {time2:.3f}s")
    
    if time2 < time1 * 0.1:  # 缓存应该快很多
        print(f"✅ 缓存生效（快了 {time1/time2:.1f} 倍）")
    else:
        print("⚠️  缓存可能未生效")


if __name__ == "__main__":
    print("="*50)
    print("东方财富数据源测试")
    print("="*50)
    
    try:
        test_latest_nav()
        test_realtime_estimate()
        test_smart_fetch()
        test_historical_nav()
        test_cache()
        
        print("\n" + "="*50)
        print("✅ 所有测试完成")
        print("="*50)
    
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


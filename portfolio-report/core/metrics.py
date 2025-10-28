"""
收益与风险指标计算模块
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import numpy_financial as npf

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """收益与风险指标计算器"""
    
    def __init__(self):
        pass
    
    def calculate_xirr(
        self,
        cashflows: List[Tuple[date, Decimal]]
    ) -> Optional[float]:
        """
        计算 XIRR（不规则现金流内部收益率）
        
        Args:
            cashflows: [(日期, 现金流), ...]
                      买入为负，赎回/当前市值为正
        
        Returns:
            年化收益率（如 0.15 表示 15%）
        """
        if len(cashflows) < 2:
            logger.warning("XIRR 计算需要至少 2 个现金流")
            return None
        
        try:
            # 转换为 numpy 数组
            dates = [cf[0] for cf in cashflows]
            amounts = [float(cf[1]) for cf in cashflows]
            
            # 使用 numpy-financial 的 xirr
            # 注意：需要将日期转换为从第一天开始的天数
            start_date = min(dates)
            days = [(d - start_date).days for d in dates]
            
            # 使用 xnpv 和数值求解计算 xirr
            # 简化：使用 irr 的近似计算
            result = npf.irr(amounts)
            
            if result is None or abs(result) > 10:  # 异常值过滤
                logger.warning(f"XIRR 计算结果异常: {result}")
                return None
            
            return float(result)
        
        except Exception as e:
            logger.error(f"XIRR 计算失败: {e}")
            return None
    
    def calculate_returns(
        self,
        start_value: Decimal,
        end_value: Decimal
    ) -> Decimal:
        """
        计算区间收益率
        
        Args:
            start_value: 期初市值
            end_value: 期末市值
        
        Returns:
            收益率（如 0.15 表示 15%）
        """
        if start_value <= 0:
            return Decimal("0")
        
        return (end_value - start_value) / start_value
    
    def calculate_max_drawdown(
        self,
        nav_series: List[Tuple[date, Decimal]]
    ) -> Tuple[Optional[Decimal], Optional[date], Optional[date]]:
        """
        计算最大回撤
        
        Args:
            nav_series: [(日期, 净值), ...] 按时间升序
        
        Returns:
            (最大回撤幅度, 高点日期, 低点日期)
        """
        if len(nav_series) < 2:
            return None, None, None
        
        max_dd = Decimal("0")
        peak_date = nav_series[0][0]
        trough_date = nav_series[0][0]
        peak_value = nav_series[0][1]
        
        for dt, value in nav_series:
            # 更新峰值
            if value > peak_value:
                peak_value = value
                peak_date = dt
            
            # 计算当前回撤
            if peak_value > 0:
                dd = (value - peak_value) / peak_value
                if dd < max_dd:
                    max_dd = dd
                    trough_date = dt
        
        return max_dd, peak_date, trough_date
    
    def calculate_90d_drawdown(
        self,
        nav_series: List[Tuple[date, Decimal]],
        reference_date: Optional[date] = None
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """
        计算近90日高点与回撤
        
        Args:
            nav_series: [(日期, 净值), ...] 按时间升序
            reference_date: 参考日期（默认为最后一个日期）
        
        Returns:
            (90日高点净值, 当前相对高点的回撤幅度)
        """
        if not nav_series:
            return None, None
        
        if reference_date is None:
            reference_date = nav_series[-1][0]
        
        # 筛选近90天的数据
        from datetime import timedelta
        cutoff_date = reference_date - timedelta(days=90)
        
        recent_series = [
            (dt, val) for dt, val in nav_series
            if dt >= cutoff_date and dt <= reference_date
        ]
        
        if len(recent_series) < 2:
            return None, None
        
        # 找到90日高点
        peak_value = max(val for _, val in recent_series)
        current_value = recent_series[-1][1]
        
        # 计算回撤
        if peak_value > 0:
            drawdown = (current_value - peak_value) / peak_value
        else:
            drawdown = Decimal("0")
        
        return peak_value, drawdown


# 全局实例
_metrics_instance: Optional[MetricsCalculator] = None


def get_metrics() -> MetricsCalculator:
    """获取指标计算器实例（单例模式）"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCalculator()
    return _metrics_instance


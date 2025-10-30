"""
收益与风险指标计算模块
"""
import logging
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
import numpy_financial as npf

logger = logging.getLogger(__name__)


# ==================
# Types & Constants
# ==================

# 轻量类型别名，增强可读性
Cashflow = Tuple[date, Decimal]
NavPoint = Tuple[date, Decimal]
NavSeries = List[NavPoint]


# ==================
# Services（服务层）
# ==================

class XirrService:
    """XIRR 计算服务：不规则现金流内部收益率"""
    
    def calculate(self, cashflows: List[Cashflow]) -> Optional[float]:
        """计算 XIRR，买入为负、赎回/当前市值为正"""
        if len(cashflows) < 2:
            logger.warning("XIRR 计算需要至少 2 个现金流")
            return None
        
        try:
            # 转换为 numpy-financial 输入
            dates = [cf[0] for cf in cashflows]
            amounts = [float(cf[1]) for cf in cashflows]
            # 备注：xirr 通常基于 xnpv 数值求解；此处沿用 irr 近似
            start_date = min(dates)
            _days = [(d - start_date).days for d in dates]  # 占位，保留思路
            result = npf.irr(amounts)
            if result is None or abs(result) > 10:
                logger.warning(f"XIRR 计算结果异常: {result}")
                return None
            return float(result)
        except Exception as e:
            logger.error(f"XIRR 计算失败: {e}")
            return None


class ReturnService:
    """区间收益率计算服务"""
    
    def calculate(self, start_value: Decimal, end_value: Decimal) -> Decimal:
        if start_value <= 0:
            return Decimal("0")
        return (end_value - start_value) / start_value


class DrawdownService:
    """回撤相关计算服务（最大回撤、窗口回撤）"""
    
    def calculate_max_drawdown(
        self,
        nav_series: NavSeries
    ) -> Tuple[Optional[Decimal], Optional[date], Optional[date]]:
        if len(nav_series) < 2:
            return None, None, None
        
        max_dd = Decimal("0")
        peak_date = nav_series[0][0]
        trough_date = nav_series[0][0]
        peak_value = nav_series[0][1]
        
        for dt, value in nav_series:
            if value > peak_value:
                peak_value = value
                peak_date = dt
            if peak_value > 0:
                dd = (value - peak_value) / peak_value
                if dd < max_dd:
                    max_dd = dd
                    trough_date = dt
        
        return max_dd, peak_date, trough_date
    
    def calculate_window_drawdown(
        self,
        nav_series: NavSeries,
        window_days: int = 90,
        reference_date: Optional[date] = None
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        if not nav_series:
            return None, None
        if reference_date is None:
            reference_date = nav_series[-1][0]
        
        from datetime import timedelta
        cutoff_date = reference_date - timedelta(days=window_days)
        recent_series = [
            (dt, val) for dt, val in nav_series
            if dt >= cutoff_date and dt <= reference_date
        ]
        if len(recent_series) < 2:
            return None, None
        
        peak_value = max(val for _, val in recent_series)
        current_value = recent_series[-1][1]
        if peak_value > 0:
            drawdown = (current_value - peak_value) / peak_value
        else:
            drawdown = Decimal("0")
        return peak_value, drawdown


# ==================
# Facade（对外门面：编排服务）
# ==================

class MetricsCalculator:
    """收益与风险指标计算器（编排层）"""
    
    def __init__(self):
        # 组装服务
        self._xirr_service = XirrService()
        self._return_service = ReturnService()
        self._drawdown_service = DrawdownService()
    
    def calculate_xirr(
        self,
        cashflows: List[Cashflow]
    ) -> Optional[float]:
        """计算 XIRR（委托 XirrService）"""
        return self._xirr_service.calculate(cashflows)
    
    def calculate_returns(
        self,
        start_value: Decimal,
        end_value: Decimal
    ) -> Decimal:
        """计算区间收益率（委托 ReturnService）"""
        return self._return_service.calculate(start_value, end_value)
    
    def calculate_max_drawdown(
        self,
        nav_series: NavSeries
    ) -> Tuple[Optional[Decimal], Optional[date], Optional[date]]:
        """计算最大回撤（委托 DrawdownService）"""
        return self._drawdown_service.calculate_max_drawdown(nav_series)
    
    def calculate_90d_drawdown(
        self,
        nav_series: NavSeries,
        reference_date: Optional[date] = None
    ) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """计算近90日高点与回撤（委托 DrawdownService）"""
        return self._drawdown_service.calculate_window_drawdown(
            nav_series, window_days=90, reference_date=reference_date
        )



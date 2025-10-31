"""
交易日与确认日推演模块

## 股市游戏规则（支付宝/基金交易口径）

### 1. 未知价原则（15:00 Cutoff）
- **15:00 前提交**：按当日收盘净值（T 日）成交
- **15:00 后提交**：按次日收盘净值（T+1 日）成交
- 提交时不知道成交价，故称"未知价"

### 2. 交易日判定
- **中国交易日（A股）**：
  - 周一至周五（工作日）
  - 排除法定节假日（元旦、春节、清明、劳动节、端午、中秋、国庆）
  - 包含调休工作日（如春节/国庆前后调休）
  - 依赖 `chinese_calendar` 库自动处理
  
- **美国交易日（纳斯达克/纽交所）**：
  - 周一至周五
  - 排除联邦假日（元旦、总统日、阵亡将士日、独立日、劳动节、感恩节、圣诞节等）
  - 当前为简化版假日表，生产环境建议接入完整市场日历

### 3. 确认日推演（T+N 规则）
- **A股基金（domestic）**：
  - T 日 15:00 前：按 T 日净值成交
  - T+1 日：份额确认（可查询）
  - 净值公告时间：通常 T 日晚 21:00-23:00
  
- **QDII 基金（投资美股）**：
  - T 日 15:00 前提交 → T+1 日计算净值 → T+2 日确认份额
  - 需考虑中美两边市场同时开市
  - 遇美股节假日顺延（如感恩节、圣诞节）
  - 净值公告时间：通常 T+1 日上午 10:00-12:00

### 4. 特殊情况（TODO 待处理）
- **临时休市**：台风/暴雨等极端天气、重大事件
- **提前收盘**：年末最后一个交易日可能 14:00 提前收盘
- **QDII 特殊市场**：
  - 港股通/沪深港通有独立休市安排
  - 欧洲/日本 QDII 需单独处理时差与假日
  - 基金公司公告延迟情况

### 5. 时区约定
- 所有时间均使用 `Asia/Shanghai`（UTC+8）
- cutoff 判定在本地时区进行
- 跨时区 QDII 基金，净值计算以基金公司公告为准
"""

import os
import logging
from datetime import datetime, time, timedelta, date
from typing import Optional, Tuple, TypedDict, Literal
from dateutil import tz
import chinese_calendar as cc

from portfolio_report.domain.constants import FundType

logger = logging.getLogger(__name__)


# ==================
# Types & Constants
# ==================

class CutoffResult(TypedDict):
    """cutoff 判定结果：
    - cutoff_flag: "pre15" / "post15"
    - trade_day_cn: T 日（中国交易日，date）
    """
    cutoff_flag: Literal["pre15", "post15"]
    trade_day_cn: date


class ConfirmDates(TypedDict):
    """确认日期推演结果：
    - expected_nav_date: 预计净值日（date）
    - expected_confirm_date: 预计确认日（date）
    """
    expected_nav_date: date
    expected_confirm_date: date


DEFAULT_CUTOFF_TIME = time(15, 0)  # 15:00 分界线（常量）


# ==================
# Providers（市场日历提供者）
# ==================

class CNCalendarProvider:
    """中国交易日历提供者：基于 chinese_calendar 库"""

    def is_trading_day(self, dt: datetime) -> bool:
        """判断是否为中国交易日"""
        return cc.is_workday(dt)

    def next_trading_day(self, dt: datetime, *, skip_current: bool = False) -> datetime:
        """获取下一个中国交易日"""
        if not skip_current and self.is_trading_day(dt):
            return dt
        current = dt + timedelta(days=1)
        for _ in range(30):
            if self.is_trading_day(current):
                return current
            current += timedelta(days=1)
        logger.warning(f"未找到 {dt} 之后 30 天内的中国交易日")
        return current


class USCalendarProvider:
    """美国交易日历提供者：简化假日表（可替换为完整实现）"""

    def is_trading_day(self, dt: datetime) -> bool:
        """判断是否为美国交易日"""
        if dt.weekday() >= 5:
            return False
        us_holidays = self._get_us_holidays(dt.year)
        return dt.date() not in us_holidays

    def next_trading_day(self, dt: datetime, *, skip_current: bool = False) -> datetime:
        """获取下一个美国交易日"""
        if not skip_current and self.is_trading_day(dt):
            return dt
        current = dt + timedelta(days=1)
        for _ in range(30):
            if self.is_trading_day(current):
                return current
            current += timedelta(days=1)
        logger.warning(f"未找到 {dt} 之后 30 天内的美国交易日")
        return current

    def _get_us_holidays(self, year: int) -> set:
        """获取美国主要市场假日（简化版）"""
        holidays = set()
        holidays.add(date(year, 1, 1))
        holidays.add(self._nth_weekday(year, 1, 0, 3))
        holidays.add(self._nth_weekday(year, 2, 0, 3))
        holidays.add(self._last_weekday(year, 5, 0))
        holidays.add(date(year, 7, 4))
        holidays.add(self._nth_weekday(year, 9, 0, 1))
        holidays.add(self._nth_weekday(year, 11, 3, 4))
        holidays.add(date(year, 12, 25))
        return holidays

    def _nth_weekday(self, year: int, month: int, weekday: int, n: int) -> date:
        """获取某月第 n 个星期几（0=周一）"""
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()
        if weekday >= first_weekday:
            first_target = first_day + timedelta(days=(weekday - first_weekday))
        else:
            first_target = first_day + timedelta(days=(7 - first_weekday + weekday))
        return first_target + timedelta(weeks=(n - 1))

    def _last_weekday(self, year: int, month: int, weekday: int) -> date:
        """获取某月最后一个星期几"""
        from calendar import monthrange
        last_day = date(year, month, monthrange(year, month)[1])
        last_weekday = last_day.weekday()
        if weekday <= last_weekday:
            return last_day - timedelta(days=(last_weekday - weekday))
        else:
            return last_day - timedelta(days=(7 - weekday + last_weekday))


# ==================
# Policies（策略层）
# ==================

class CutoffPolicy:
    """15:00 Cutoff 策略"""

    def __init__(self, cn_calendar: CNCalendarProvider, timezone, cutoff_time: time):
        self.cn_calendar = cn_calendar
        self.timezone = timezone
        self.cutoff_time = cutoff_time

    def check(self, trade_time: datetime) -> CutoffResult:
        """判断交易时间是否在 15:00 cutoff 之前"""
        local_time = trade_time.astimezone(self.timezone)
        if local_time.time() < self.cutoff_time:
            cutoff_flag = "pre15"
            trade_day_cn = local_time.date()
        else:
            cutoff_flag = "post15"
            next_day = local_time + timedelta(days=1)
            trade_day_cn = self.cn_calendar.next_trading_day(next_day).date()

        # 确保 trade_day_cn 是交易日
        if not self.cn_calendar.is_trading_day(datetime.combine(trade_day_cn, time(9, 0))):
            trade_day_cn = self.cn_calendar.next_trading_day(
                datetime.combine(trade_day_cn, time(9, 0))
            ).date()

        return {"cutoff_flag": cutoff_flag, "trade_day_cn": trade_day_cn}


class ConfirmAlignmentPolicy:
    """确认日对齐策略（A股 T+1、QDII T+2）"""

    def __init__(self, cn_calendar: CNCalendarProvider, us_calendar: USCalendarProvider):
        self.cn_calendar = cn_calendar
        self.us_calendar = us_calendar

    def calculate(self, trade_day_cn: date, fund_type: str) -> ConfirmDates:
        """计算预计净值日和确认日"""
        trade_dt = datetime.combine(trade_day_cn, time(9, 0))

        if fund_type == FundType.domestic:
            expected_nav_date = trade_day_cn
            expected_confirm_date = self.cn_calendar.next_trading_day(
                trade_dt + timedelta(days=1)
            ).date()
        elif fund_type == FundType.qdii:
            expected_nav_date = self.cn_calendar.next_trading_day(
                trade_dt + timedelta(days=1)
            ).date()
            confirm_dt = trade_dt + timedelta(days=2)
            expected_confirm_date = self._align_qdii_confirm_date(confirm_dt).date()
        else:
            logger.warning(f"未知基金类型：{fund_type}，使用 {FundType.domestic} 规则")
            expected_nav_date = trade_day_cn
            expected_confirm_date = self.cn_calendar.next_trading_day(
                trade_dt + timedelta(days=1)
            ).date()

        return {
            "expected_nav_date": expected_nav_date,
            "expected_confirm_date": expected_confirm_date,
        }

    def _align_qdii_confirm_date(self, dt: datetime) -> datetime:
        """QDII 确认日对齐：需要中国和美国都开市"""
        current = dt
        for _ in range(10):
            if self.cn_calendar.is_trading_day(current) and self.us_calendar.is_trading_day(current):
                return current
            current += timedelta(days=1)
        logger.warning(f"未找到 {dt} 附近中美都开市的日期，使用中国交易日")
        return self.cn_calendar.next_trading_day(dt)


# ==================
# Service（编排服务层）
# ==================

class TradingCalendar:
    """交易日历服务（编排层）：组合 Provider 与 Policy，对外提供统一接口"""
    
    def __init__(self, timezone_str: str = "Asia/Shanghai"):
        self.timezone = tz.gettz(timezone_str)
        self.cutoff_time = DEFAULT_CUTOFF_TIME
        
        # 组装依赖
        self.cn_calendar = CNCalendarProvider()
        self.us_calendar = USCalendarProvider()
        self.cutoff_policy = CutoffPolicy(self.cn_calendar, self.timezone, self.cutoff_time)
        self.confirm_policy = ConfirmAlignmentPolicy(self.cn_calendar, self.us_calendar)
    
    # ---- 对外 API：委托 Provider/Policy ----
    
    def is_cn_trading_day(self, date: datetime) -> bool:
        """判断是否为中国交易日（委托 CNCalendarProvider）"""
        return self.cn_calendar.is_trading_day(date)
    
    def is_us_trading_day(self, date: datetime) -> bool:
        """判断是否为美国交易日（委托 USCalendarProvider）"""
        return self.us_calendar.is_trading_day(date)
    
    def next_cn_trading_day(self, date: datetime, skip_current: bool = False) -> datetime:
        """获取下一个中国交易日（委托 CNCalendarProvider）"""
        return self.cn_calendar.next_trading_day(date, skip_current=skip_current)
    
    def next_us_trading_day(self, date: datetime, skip_current: bool = False) -> datetime:
        """获取下一个美国交易日（委托 USCalendarProvider）"""
        return self.us_calendar.next_trading_day(date, skip_current=skip_current)
    
    def check_cutoff(self, trade_time: datetime) -> Tuple[str, datetime]:
        """判断交易时间是否在 15:00 cutoff 之前（委托 CutoffPolicy）"""
        result = self.cutoff_policy.check(trade_time)
        return result["cutoff_flag"], result["trade_day_cn"]
    
    def calculate_confirm_date(
        self,
        trade_day_cn: datetime.date,
        fund_type: str
    ) -> Tuple[datetime.date, datetime.date]:
        """计算预计净值日和确认日（委托 ConfirmAlignmentPolicy）"""
        result = self.confirm_policy.calculate(trade_day_cn, fund_type)
        return result["expected_nav_date"], result["expected_confirm_date"]
    
    # ---- 辅助格式化 ----
    def format_date_with_nav_kind(
        self,
        date: datetime.date,
        expected_nav_date: datetime.date,
        nav_kind: str = "估"
    ) -> str:
        """
        格式化日期并标注估/净
        
        Args:
            date: 当前日期
            expected_nav_date: 预计净值日
            nav_kind: 当前净值类型（"估" 或 "净"）
        
        Returns:
            格式化字符串，如 "2025-10-28 (估)" 或 "2025-10-28"
        """
        date_str = date.strftime("%Y-%m-%d")
        
        if nav_kind == "估":
            return f"{date_str} (估)"
        else:
            return date_str


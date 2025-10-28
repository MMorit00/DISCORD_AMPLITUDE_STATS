"""
交易日与确认日推演模块
支持：中国/美国交易日判定、15:00 cutoff、QDII T+N 确认推演
"""

import os
import logging
from datetime import datetime, time, timedelta
from typing import Optional, Tuple
from dateutil import tz
import chinese_calendar as cc

logger = logging.getLogger(__name__)


class TradingCalendar:
    """交易日历管理器"""
    
    def __init__(self, timezone_str: str = "Asia/Shanghai"):
        self.timezone = tz.gettz(timezone_str)
        self.cutoff_time = time(15, 0)  # 15:00 分界线
    
    def is_cn_trading_day(self, date: datetime) -> bool:
        """
        判断是否为中国交易日（A股）
        
        使用 chinesecalendar 库，自动处理：
        - 周末（非交易日）
        - 法定节假日（非交易日）
        - 调休工作日（是交易日）
        
        TODO: 考虑特殊情况
        - 台风/暴雨等极端天气临时休市
        - 重大事件临时休市
        - 年末最后一个交易日提前收盘
        
        Args:
            date: 日期（datetime 对象）
        
        Returns:
            True 表示交易日，False 表示非交易日
        """
        return cc.is_workday(date)
    
    def is_us_trading_day(self, date: datetime) -> bool:
        """
        判断是否为美国交易日（纳斯达克/纽交所）
        
        简化规则（实际应维护完整日历）：
        - 周一至周五
        - 排除美国主要假日（元旦、独立日、感恩节、圣诞节等）
        
        Args:
            date: 日期（datetime 对象）
        
        Returns:
            True 表示交易日，False 表示非交易日
        """
        # 周末
        if date.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # 美国主要假日（简化版，实际应更完整）
        us_holidays = self._get_us_holidays(date.year)
        date_only = date.date()
        
        return date_only not in us_holidays
    
    def _get_us_holidays(self, year: int) -> set:
        """
        获取美国主要市场假日（简化版）
        
        TODO: 补充完整的美股市场假日
        - Good Friday（耶稣受难日，Easter前周五，需复杂计算）
        - Juneteenth（6月19日，2021年起）
        - 如节假日落在周末，需调整到周一/周五
        - 部分假日提前休市（如感恩节后、圣诞前夕）
        
        生产环境建议：
        1. 使用 pandas_market_calendars 库
        2. 或维护完整的 US_market_holidays.csv
        3. 或接入第三方交易日历 API
        """
        from datetime import date
        
        holidays = set()
        
        # 元旦（New Year's Day）
        holidays.add(date(year, 1, 1))
        
        # 马丁·路德·金日（1月第三个周一）
        holidays.add(self._nth_weekday(year, 1, 0, 3))
        
        # 总统日（2月第三个周一）
        holidays.add(self._nth_weekday(year, 2, 0, 3))
        
        # TODO: 耶稣受难日（Good Friday，Easter 前周五）
        # 需要实现 Easter 日期计算算法（Computus）
        # 或使用 dateutil.easter 模块
        
        # TODO: Juneteenth（6月19日，2021年起新增联邦假日）
        # if year >= 2021:
        #     holidays.add(date(year, 6, 19))
        
        # 阵亡将士纪念日（5月最后一个周一）
        holidays.add(self._last_weekday(year, 5, 0))
        
        # 独立日（Independence Day）
        holidays.add(date(year, 7, 4))
        
        # 劳动节（9月第一个周一）
        holidays.add(self._nth_weekday(year, 9, 0, 1))
        
        # 感恩节（11月第四个周四）
        holidays.add(self._nth_weekday(year, 11, 3, 4))
        
        # 圣诞节（Christmas）
        holidays.add(date(year, 12, 25))
        
        return holidays
    
    def _nth_weekday(self, year: int, month: int, weekday: int, n: int):
        """获取某月第 n 个星期几（0=周一）"""
        from datetime import date
        first_day = date(year, month, 1)
        first_weekday = first_day.weekday()
        
        # 计算第一个目标星期几的日期
        if weekday >= first_weekday:
            first_target = first_day + timedelta(days=(weekday - first_weekday))
        else:
            first_target = first_day + timedelta(days=(7 - first_weekday + weekday))
        
        # 第 n 个目标星期几
        return first_target + timedelta(weeks=(n - 1))
    
    def _last_weekday(self, year: int, month: int, weekday: int):
        """获取某月最后一个星期几"""
        from datetime import date
        from calendar import monthrange
        
        last_day = date(year, month, monthrange(year, month)[1])
        last_weekday = last_day.weekday()
        
        if weekday <= last_weekday:
            return last_day - timedelta(days=(last_weekday - weekday))
        else:
            return last_day - timedelta(days=(7 - weekday + last_weekday))
    
    def next_cn_trading_day(self, date: datetime, skip_current: bool = False) -> datetime:
        """
        获取下一个中国交易日
        
        Args:
            date: 起始日期
            skip_current: 是否跳过当前日期（即使当前是交易日）
        
        Returns:
            下一个交易日
        """
        if not skip_current and self.is_cn_trading_day(date):
            return date
        
        current = date + timedelta(days=1)
        max_attempts = 30  # 防止无限循环
        
        for _ in range(max_attempts):
            if self.is_cn_trading_day(current):
                return current
            current += timedelta(days=1)
        
        logger.warning(f"未找到 {date} 之后 {max_attempts} 天内的中国交易日")
        return current
    
    def next_us_trading_day(self, date: datetime, skip_current: bool = False) -> datetime:
        """
        获取下一个美国交易日
        
        Args:
            date: 起始日期
            skip_current: 是否跳过当前日期
        
        Returns:
            下一个交易日
        """
        if not skip_current and self.is_us_trading_day(date):
            return date
        
        current = date + timedelta(days=1)
        max_attempts = 30
        
        for _ in range(max_attempts):
            if self.is_us_trading_day(current):
                return current
            current += timedelta(days=1)
        
        logger.warning(f"未找到 {date} 之后 {max_attempts} 天内的美国交易日")
        return current
    
    def check_cutoff(self, trade_time: datetime) -> Tuple[str, datetime]:
        """
        判断交易时间是否在 15:00 cutoff 之前
        
        Args:
            trade_time: 交易时间（带时区）
        
        Returns:
            (cutoff_flag, trade_day_cn)
            - cutoff_flag: "pre15" 或 "post15"
            - trade_day_cn: T 日（中国交易日）
        """
        # 转换到本地时区
        local_time = trade_time.astimezone(self.timezone)
        
        # 判断是否在 15:00 之前
        if local_time.time() < self.cutoff_time:
            # 15:00 前：算当日 T
            cutoff_flag = "pre15"
            trade_day_cn = local_time.date()
        else:
            # 15:00 后：算下一交易日 T
            cutoff_flag = "post15"
            next_day = local_time + timedelta(days=1)
            trade_day_cn = self.next_cn_trading_day(next_day).date()
        
        # 确保 trade_day_cn 是交易日
        if not self.is_cn_trading_day(datetime.combine(trade_day_cn, time(9, 0))):
            trade_day_cn = self.next_cn_trading_day(
                datetime.combine(trade_day_cn, time(9, 0))
            ).date()
        
        return cutoff_flag, trade_day_cn
    
    def calculate_confirm_date(
        self,
        trade_day_cn: datetime.date,
        fund_type: str
    ) -> Tuple[datetime.date, datetime.date]:
        """
        计算预计净值日和确认日
        
        Args:
            trade_day_cn: T 日（中国交易日）
            fund_type: "domestic" 或 "QDII"
        
        Returns:
            (expected_nav_date, expected_confirm_date)
        """
        trade_dt = datetime.combine(trade_day_cn, time(9, 0))
        
        if fund_type == "domestic":
            # A股基金：T 日净值，T+1 确认
            expected_nav_date = trade_day_cn
            expected_confirm_date = self.next_cn_trading_day(
                trade_dt + timedelta(days=1)
            ).date()
        
        elif fund_type == "QDII":
            # QDII：T+1 计算净值，T+2 确认（需考虑美股休市）
            expected_nav_date = self.next_cn_trading_day(
                trade_dt + timedelta(days=1)
            ).date()
            
            # T+2 确认日：需要中国和美国都是交易日
            confirm_dt = trade_dt + timedelta(days=2)
            expected_confirm_date = self._align_qdii_confirm_date(confirm_dt).date()
        
        else:
            logger.warning(f"未知基金类型：{fund_type}，使用 domestic 规则")
            expected_nav_date = trade_day_cn
            expected_confirm_date = self.next_cn_trading_day(
                trade_dt + timedelta(days=1)
            ).date()
        
        return expected_nav_date, expected_confirm_date
    
    def _align_qdii_confirm_date(self, date: datetime) -> datetime:
        """
        QDII 确认日对齐：需要中国和美国都开市
        
        TODO: 完善对齐逻辑
        - 考虑港股通/沪深港通的特殊情况
        - QDII 投资欧洲/日本市场的需单独处理
        - 考虑基金公司公告延迟的情况
        
        Args:
            date: 初步确认日
        
        Returns:
            对齐后的确认日（两边都开市）
        """
        current = date
        max_attempts = 10
        
        for _ in range(max_attempts):
            if self.is_cn_trading_day(current) and self.is_us_trading_day(current):
                return current
            current += timedelta(days=1)
        
        # 兜底：至少返回中国交易日
        logger.warning(f"未找到 {date} 附近中美都开市的日期，使用中国交易日")
        return self.next_cn_trading_day(date)
    
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


# 全局实例（可选，方便调用）
_calendar_instance: Optional[TradingCalendar] = None


def get_calendar(timezone_str: str = "Asia/Shanghai") -> TradingCalendar:
    """获取交易日历实例（单例模式）"""
    global _calendar_instance
    if _calendar_instance is None:
        _calendar_instance = TradingCalendar(timezone_str)
    return _calendar_instance


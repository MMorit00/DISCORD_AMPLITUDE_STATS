"""
时间工具模块
简单的时区工具函数
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo


def now_tz(timezone: str = "Asia/Shanghai") -> datetime:
    """获取指定时区的当前时间"""
    return datetime.now(ZoneInfo(timezone))


def today_tz(timezone: str = "Asia/Shanghai") -> date:
    """获取指定时区的当前日期"""
    return now_tz(timezone).date()


def utcnow() -> datetime:
    """获取 UTC 当前时间"""
    return datetime.now(ZoneInfo("UTC"))


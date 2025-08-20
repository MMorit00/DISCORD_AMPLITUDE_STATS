import os
import io
import sys
import json
import gzip
import math
import zipfile
import logging
import datetime as dt
from typing import Dict, Tuple, Set, Optional
import requests
from dateutil import tz

# 配置日志
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

AMPLITUDE_API_KEY = os.getenv("AMPLITUDE_API_KEY")
AMPLITUDE_SECRET_KEY = os.getenv("AMPLITUDE_SECRET_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
TIMEZONE = os.getenv("AMPLITUDE_TIMEZONE", "UTC")

if not (AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY and DISCORD_WEBHOOK_URL):
    logging.error("缺少必要环境变量：AMPLITUDE_API_KEY / AMPLITUDE_SECRET_KEY / DISCORD_WEBHOOK_URL")
    sys.exit(1)

def week_range(tz_name: str = "UTC") -> Tuple[dt.datetime, dt.datetime, dt.datetime, dt.datetime]:
    """
    返回两个完整周的起止时间（上一周、上上周），均为周一 00:00 到下周一 00:00 的半开区间
    """
    tzinfo = tz.gettz(tz_name)
    now = dt.datetime.now(tzinfo)
    weekday = now.weekday()  # Monday=0
    this_monday = (now - dt.timedelta(days=weekday)).replace(hour=0, minute=0, second=0, microsecond=0)
    last_monday = this_monday - dt.timedelta(days=7)
    prev_monday = this_monday - dt.timedelta(days=14)
    return prev_monday, last_monday, last_monday, this_monday

def amplitude_export(start: dt.datetime, end: dt.datetime) -> bytes:
    """
    调用 Amplitude Export API，返回 zip 二进制数据
    文档：/api/2/export?start=YYYYMMDDT00&end=YYYYMMDDT00 （UTC 小时粒度）
    """
    start_utc = start.astimezone(tz.UTC)
    end_utc = end.astimezone(tz.UTC)
    fmt = "%Y%m%dT%H"
    url = "https://amplitude.com/api/2/export"
    auth = (AMPLITUDE_API_KEY, AMPLITUDE_SECRET_KEY)
    params = {"start": start_utc.strftime(fmt), "end": end_utc.strftime(fmt)}

    logging.info(f"请求 Amplitude Export: {params}")
    with requests.get(url, params=params, auth=auth, stream=True, timeout=600) as r:
        r.raise_for_status()
        return r.content  # zip 内容

def parse_events_from_zip(zip_bytes: bytes):
    """
    解析 zip 内的 .json.gz 文件，每行一个事件 JSON
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if not name.endswith(".json.gz"):
                continue
            with zf.open(name) as gz_file:
                with gzip.GzipFile(fileobj=io.BufferedReader(gz_file)) as jf:
                    for line in jf:
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except Exception as e:
                            logging.warning(f"解析行失败: {e}")

def aggregate_week(events_iter) -> Dict[str, int]:
    """
    指标：
    - 周活跃用户：基于 user_id（优先），否则 device_id 去重
    - 事件数：总数
    """
    users: Set[str] = set()
    event_count = 0
    for ev in events_iter:
        event_count += 1
        uid = ev.get("user_id") or ev.get("device_id")
        if uid:
            users.add(str(uid))
    return {"活跃用户": len(users), "事件数": event_count}

def calculate_growth(curr: Dict[str, int], prev: Dict[str, int]) -> Dict[str, Optional[float]]:
    def rate(c, p):
        if not p:
            return None
        return (c - p) / p * 100.0
    return {
        "活跃用户增长率": rate(curr.get("活跃用户", 0), prev.get("活跃用户", 0)),
        "事件数增长率": rate(curr.get("事件数", 0), prev.get("事件数", 0)),
    }

def fmt_pct(v: Optional[float]) -> str:
    if v is None or (isinstance(v, float) and (v != v)):  # NaN
        return "N/A"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"

def build_message(prev_week_label: str, prev_stats: Dict[str, int],
                  last_week_label: str, last_stats: Dict[str, int],
                  growth: Dict[str, Optional[float]]) -> str:
    lines = []
    lines.append("Amplitude 周统计数据")
    lines.append("")
    lines.append(f"{prev_week_label}：")
    lines.append(f"- 活跃用户：{prev_stats['活跃用户']}")
    lines.append(f"- 事件数：{prev_stats['事件数']}")
    lines.append("")
    lines.append(f"{last_week_label}：")
    lines.append(f"- 活跃用户：{last_stats['活跃用户']}")
    lines.append(f"- 事件数：{last_stats['事件数']}")
    lines.append("")
    lines.append("周环比：")
    lines.append(f"- 活跃用户：{fmt_pct(growth['活跃用户增长率'])}")
    lines.append(f"- 事件数：{fmt_pct(growth['事件数增长率'])}")
    return "\n".join(lines)

def post_to_discord(webhook_url: str, content: str):
    r = requests.post(webhook_url, json={"content": content}, timeout=30)
    try:
        r.raise_for_status()
        logging.info("已发送到 Discord")
    except Exception:
        logging.error("发送到 Discord 失败：%s %s", r.status_code, r.text)
        raise

def main():
    tzinfo = tz.gettz(TIMEZONE)
    prev_start, prev_end, last_start, last_end = week_range(tz_name=TIMEZONE)

    def label(s: dt.datetime, e: dt.datetime):
        # 展示为业务时区的周一到周日
        s_local = s.astimezone(tzinfo)
        e_local = (e - dt.timedelta(seconds=1)).astimezone(tzinfo)
        return f"{s_local.strftime('%Y-%m-%d')} ~ {e_local.strftime('%Y-%m-%d')}"

    prev_label = label(prev_start, prev_end)
    last_label = label(last_start, last_end)

    logging.info(f"下载上上周数据：{prev_label}")
    prev_zip = amplitude_export(prev_start, prev_end)
    prev_stats = aggregate_week(parse_events_from_zip(prev_zip))

    logging.info(f"下载上周数据：{last_label}")
    last_zip = amplitude_export(last_start, last_end)
    last_stats = aggregate_week(parse_events_from_zip(last_zip))

    growth = calculate_growth(last_stats, prev_stats)
    message = build_message(prev_label, prev_stats, last_label, last_stats, growth)

    logging.info("发送文本到 Discord")
    post_to_discord(DISCORD_WEBHOOK_URL, message)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err = f"Amplitude 周报任务失败：{e}"
        logging.exception(err)
        try:
            if DISCORD_WEBHOOK_URL:
                post_to_discord(DISCORD_WEBHOOK_URL, err)
        finally:
            sys.exit(1)

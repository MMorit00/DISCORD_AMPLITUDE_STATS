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

# 日志
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
)

# 环境变量
AMPLITUDE_API_KEY = os.getenv("AMPLITUDE_API_KEY")
AMPLITUDE_SECRET_KEY = os.getenv("AMPLITUDE_SECRET_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
TIMEZONE = os.getenv("AMPLITUDE_TIMEZONE", "UTC")
# 触发模式：SCHEDULED（定时触发，查上周数据）或 MANUAL（手动触发，查今日数据）
TRIGGER_MODE = os.getenv("TRIGGER_MODE", "MANUAL").upper()
# 区域（可选）：US 或 EU。若设置了 AMPLITUDE_BASE_URL，则忽略本项
AMPLITUDE_REGION = os.getenv("AMPLITUDE_REGION", "").strip().upper()
# 固定使用 https://analytics.amplitude.com
# 注意：此域名可能不是正确的 Export API 端点，如遇 403 错误，脚本会自动尝试切换到正确的域名
AMPLITUDE_BASE_URL = os.getenv("AMPLITUDE_BASE_URL") or "https://analytics.amplitude.com"

def _normalize_base_url(u: str) -> str:
    if not u:
        return "https://amplitude.com"
    u = u.strip()
    if u.endswith("/"):
        u = u[:-1]
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u

def _alternate_base_url(u: str) -> str:
    """
    返回另一区域的基础域名（US <-> EU）
    """
    if "eu.amplitude.com" in u:
        return "https://amplitude.com"
    return "https://analytics.eu.amplitude.com"

AMPLITUDE_BASE_URL = _normalize_base_url(AMPLITUDE_BASE_URL)

if not (AMPLITUDE_API_KEY and AMPLITUDE_SECRET_KEY and DISCORD_WEBHOOK_URL):
    logging.error("缺少必要环境变量：AMPLITUDE_API_KEY / AMPLITUDE_SECRET_KEY / DISCORD_WEBHOOK_URL")
    sys.exit(1)

def get_time_range(tz_name: str = "UTC", mode: str = "MANUAL") -> Tuple[dt.datetime, dt.datetime, str]:
    """
    根据触发模式返回时间范围
    SCHEDULED: 返回上周数据（上周一00:00到上周日23:59）
    MANUAL: 返回今日数据（今日00:00到现在）
    """
    tzinfo = tz.gettz(tz_name)
    now = dt.datetime.now(tzinfo)
    
    if mode == "SCHEDULED":
        # 定时触发：查上周数据（上周一到上周日）
        weekday = now.weekday()  # Monday=0
        this_monday = (now - dt.timedelta(days=weekday)).replace(hour=0, minute=0, second=0, microsecond=0)
        last_monday = this_monday - dt.timedelta(days=7)
        last_sunday = this_monday - dt.timedelta(seconds=1)
        
        return last_monday, last_sunday, "上周"
    else:
        # 手动触发：查今日数据
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start, now, "今日"

def amplitude_export(start: dt.datetime, end: dt.datetime) -> bytes:
    """
    调用 Amplitude Export API，返回 zip 二进制数据
    文档：{BASE}/api/2/export?start=YYYYMMDDTHH&end=YYYYMMDDTHH（UTC 小时粒度，end 为开区间）
    - 某些租户/时间段可能返回 404，表示无可导出归档；此时按“天”拆分重试并合并。
    - 若凭据/区域不匹配，可能返回 401/403 或 HTML 登录页；此时自动切换另一区域重试一次。
    """
    start_utc = start.astimezone(tz.UTC)
    end_utc = end.astimezone(tz.UTC)
    fmt = "%Y%m%dT%H"

    auth = (AMPLITUDE_API_KEY, AMPLITUDE_SECRET_KEY)
    params = {"start": start_utc.strftime(fmt), "end": end_utc.strftime(fmt)}
    headers = {"Accept": "application/zip"}

    def _request_with_base(base_url: str):
        url = f"{base_url}/api/2/export"
        logging.info(f"请求 Amplitude Export: {url} params={params}")
        r0 = requests.get(url, params=params, auth=auth, headers=headers, stream=True, timeout=600, allow_redirects=False)
        return url, r0

    # 第一次以配置区域请求
    base_used = AMPLITUDE_BASE_URL
    url, r = _request_with_base(base_used)

    # 如遇 401/403 或被重定向至登录（3xx）或返回 HTML（疑似登录页），尝试另一区域
    ct = r.headers.get("Content-Type", "").lower()
    if r.status_code in (401, 403) or (300 <= r.status_code < 400) or (r.status_code == 200 and "text/html" in ct):
        alt_base = _normalize_base_url(_alternate_base_url(base_used))
        logging.warning("Export 返回异常状态 %s（或疑似登录页），尝试切换区域：%s -> %s", r.status_code, base_used, alt_base)
        base_used = alt_base
        url, r = _request_with_base(base_used)
        if 200 <= r.status_code < 300:
            logging.warning("切换区域后成功。建议将 AMPLITUDE_BASE_URL 固定为：%s（或设置 AMPLITUDE_REGION 对应 US/EU）", base_used)

    if r.status_code == 404:
        # 分天重试并合并 zip 内容
        logging.warning("Export 返回 404，尝试按天分段重试")
        buf = io.BytesIO()
        wrote_any = False
        with zipfile.ZipFile(buf, "w") as combined_zip:
            cur = start_utc
            while cur < end_utc:
                day_start = cur
                day_end = min(cur + dt.timedelta(days=1), end_utc)
                day_params = {"start": day_start.strftime(fmt), "end": day_end.strftime(fmt)}
                logging.info(f"按天重试：{day_params}")
                day_url = f"{base_used}/api/2/export"
                dr = requests.get(day_url, params=day_params, auth=auth, headers=headers, stream=True, timeout=600)
                if dr.status_code == 404:
                    logging.info(f"该日无归档：{day_params}")
                    cur = day_end
                    continue
                dr.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(dr.content)) as dz:
                    for name in dz.namelist():
                        combined_zip.writestr(name, dz.read(name))
                        wrote_any = True
                cur = day_end
        if not wrote_any:
            raise FileNotFoundError("该时间段没有可导出的 Amplitude 数据（多次 404）。请确认数据中心域名与时间区间。")
        return buf.getvalue()

    # 非 404 的错误直接抛出，便于上层捕获并发到 Discord
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
    - 周活跃用户：优先 user_id，否则 device_id 去重
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
    lines.append("Amplitude 日统计数据")
    lines.append("")
    lines.append(f"{prev_week_label}：")
    lines.append(f"- 活跃用户：{prev_stats['活跃用户']}")
    lines.append(f"- 事件数：{prev_stats['事件数']}")
    lines.append("")
    lines.append(f"{last_week_label}：")
    lines.append(f"- 活跃用户：{last_stats['活跃用户']}")
    lines.append(f"- 事件数：{last_stats['事件数']}")
    lines.append("")
    lines.append("日环比：")
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
    
    # 根据触发模式获取时间范围
    start_time, end_time, period_label = get_time_range(tz_name=TIMEZONE, mode=TRIGGER_MODE)

    def format_time_range(s: dt.datetime, e: dt.datetime):
        s_local = s.astimezone(tzinfo)
        e_local = e.astimezone(tzinfo)
        if s_local.date() == e_local.date():
            return f"{s_local.strftime('%Y-%m-%d')} ({s_local.strftime('%H:%M')} - {e_local.strftime('%H:%M')})"
        return f"{s_local.strftime('%Y-%m-%d %H:%M')} ~ {e_local.strftime('%Y-%m-%d %H:%M')}"

    time_range_str = format_time_range(start_time, end_time)
    
    logging.info(f"触发模式：{TRIGGER_MODE}")
    logging.info(f"下载{period_label}数据：{time_range_str}")
    
    data_zip = amplitude_export(start_time, end_time)
    stats = aggregate_week(parse_events_from_zip(data_zip))

    # 构建报告消息
    lines = []
    if TRIGGER_MODE == "SCHEDULED":
        lines.append("Amplitude 上周统计数据")
    else:
        lines.append("Amplitude 今日统计数据")
    lines.append("")
    lines.append(f"{period_label} ({time_range_str})：")
    lines.append(f"- 活跃用户：{stats['活跃用户']}")
    lines.append(f"- 事件数：{stats['事件数']}")
    message = "\n".join(lines)

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

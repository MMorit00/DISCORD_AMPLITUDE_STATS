"""
东方财富（天天基金）数据源
抓取基金净值、估值、历史数据
"""
import os
import json
import logging
import time
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List, Any
from pathlib import Path
import requests
from dateutil import tz

logger = logging.getLogger(__name__)


class EastMoneyFundAPI:
    """东方财富基金数据 API"""
    
    # API 端点
    BASE_URL = "https://fundgz.1234567.com.cn"
    FUND_DETAIL_URL = "https://fund.eastmoney.com"
    
    def __init__(self, cache_dir: Optional[str] = None, cache_ttl: int = 300):
        """
        初始化
        
        Args:
            cache_dir: 缓存目录（默认为 portfolio-report/data/cache）
            cache_ttl: 缓存有效期（秒，默认 5 分钟）
        """
        if cache_dir is None:
            # 默认缓存目录
            base_dir = Path(__file__).parent.parent
            cache_dir = base_dir / "data" / "cache"
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://fund.eastmoney.com/"
        })
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"
    
    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """读取缓存"""
        cache_path = self._get_cache_path(key)
        
        if not cache_path.exists():
            return None
        
        try:
            # 检查缓存是否过期
            mtime = cache_path.stat().st_mtime
            age = time.time() - mtime
            
            if age > self.cache_ttl:
                logger.debug(f"缓存已过期: {key} (age={age:.1f}s)")
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.debug(f"命中缓存: {key}")
            return data
        
        except Exception as e:
            logger.warning(f"读取缓存失败: {key}, {e}")
            return None
    
    def _write_cache(self, key: str, data: Dict[str, Any]):
        """写入缓存"""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"写入缓存: {key}")
        
        except Exception as e:
            logger.warning(f"写入缓存失败: {key}, {e}")
    
    def get_realtime_estimate(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """
        获取基金实时估值（盘中）
        
        API: https://fundgz.1234567.com.cn/js/{fund_code}.js
        
        Args:
            fund_code: 基金代码
        
        Returns:
            {
                "fund_code": "018043",
                "name": "天弘纳斯达克100(QDII)A",
                "estimate_value": "1.2345",      # 估算净值
                "estimate_time": "2025-10-28 14:30",  # 估值时间
                "last_nav": "1.2300",            # 上一交易日净值
                "last_nav_date": "2025-10-27",  # 净值日期
                "change_percent": "0.37",        # 估算涨跌幅 %
                "nav_kind": "估"
            }
        """
        cache_key = f"estimate_{fund_code}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        # 尝试读取缓存
        cached = self._read_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 请求估值接口
            url = f"{self.BASE_URL}/js/{fund_code}.js"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # 解析响应（JSONP 格式）
            # 格式：jsonpgz({"fundcode":"018043","name":"...","gszzl":"0.37",...});
            text = response.text.strip()
            
            if not text.startswith("jsonpgz("):
                logger.warning(f"估值接口返回格式异常: {fund_code}")
                return None
            
            # 提取 JSON
            json_str = text[8:-2]  # 去掉 "jsonpgz(" 和 ");"
            data = json.loads(json_str)
            
            # 格式化返回数据
            result = {
                "fund_code": data.get("fundcode"),
                "name": data.get("name"),
                "estimate_value": data.get("gsz"),       # 估算净值
                "estimate_time": data.get("gztime"),     # 估值时间
                "last_nav": data.get("dwjz"),            # 昨日净值
                "last_nav_date": data.get("jzrq"),       # 净值日期
                "change_percent": data.get("gszzl"),     # 涨跌幅
                "nav_kind": "估",
                "fetched_at": datetime.now(tz=tz.gettz("Asia/Shanghai")).isoformat()
            }
            
            # 写入缓存
            self._write_cache(cache_key, result)
            
            logger.info(f"获取估值成功: {fund_code} {data.get('name')} "
                       f"{result['estimate_value']} ({result['change_percent']}%)")
            
            return result
        
        except requests.RequestException as e:
            logger.error(f"获取估值失败: {fund_code}, 网络错误: {e}")
            return None
        
        except Exception as e:
            logger.error(f"获取估值失败: {fund_code}, {e}")
            return None
    
    def get_latest_nav(self, fund_code: str) -> Optional[Dict[str, Any]]:
        """
        获取基金最新净值（已公布）
        
        通过抓取基金详情页获取最新净值
        
        Args:
            fund_code: 基金代码
        
        Returns:
            {
                "fund_code": "018043",
                "name": "天弘纳斯达克100(QDII)A",
                "nav": "1.2300",                 # 单位净值
                "nav_date": "2025-10-27",        # 净值日期
                "accumulated_nav": "1.2300",     # 累计净值
                "change_percent": "0.12",        # 日涨跌幅 %
                "nav_kind": "净"
            }
        """
        cache_key = f"nav_{fund_code}_{datetime.now().strftime('%Y%m%d')}"
        
        # 尝试读取缓存（净值缓存时间较长）
        cached = self._read_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 方式 1：使用天天基金的净值查询接口
            url = f"https://api.fund.eastmoney.com/f10/lsjz"
            params = {
                "fundCode": fund_code,
                "pageIndex": 1,
                "pageSize": 1,
                "startDate": "",
                "endDate": "",
                "_": int(time.time() * 1000)
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("ErrCode") != 0:
                logger.warning(f"净值接口返回错误: {fund_code}, {data.get('ErrMsg')}")
                return None
            
            # 解析净值数据
            ls_data = data.get("Data", {}).get("LSJZList", [])
            if not ls_data:
                logger.warning(f"未找到净值数据: {fund_code}")
                return None
            
            latest = ls_data[0]
            
            result = {
                "fund_code": fund_code,
                "name": data.get("Data", {}).get("FundName", ""),
                "nav": latest.get("DWJZ"),                    # 单位净值
                "nav_date": latest.get("FSRQ"),               # 净值日期
                "accumulated_nav": latest.get("LJJZ"),        # 累计净值
                "change_percent": latest.get("JZZZL"),        # 涨跌幅
                "nav_kind": "净",
                "fetched_at": datetime.now(tz=tz.gettz("Asia/Shanghai")).isoformat()
            }
            
            # 写入缓存
            self._write_cache(cache_key, result)
            
            logger.info(f"获取净值成功: {fund_code} {result['name']} "
                       f"{result['nav']} ({result['nav_date']})")
            
            return result
        
        except requests.RequestException as e:
            logger.error(f"获取净值失败: {fund_code}, 网络错误: {e}")
            return None
        
        except Exception as e:
            logger.error(f"获取净值失败: {fund_code}, {e}")
            return None
    
    def get_nav_or_estimate(self, fund_code: str, prefer_nav: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取净值或估值（智能选择）
        
        策略：
        1. 优先尝试获取最新净值
        2. 如果净值不是今天的，且当前在交易时段，则返回估值
        3. 否则返回净值
        
        Args:
            fund_code: 基金代码
            prefer_nav: 是否优先净值（默认 True）
        
        Returns:
            净值或估值数据，包含 nav_kind 字段标识
        """
        nav_data = self.get_latest_nav(fund_code)
        estimate_data = None
        
        # 判断净值是否为今天
        today = date.today()
        nav_is_today = False
        
        if nav_data and nav_data.get("nav_date"):
            try:
                nav_date = datetime.strptime(nav_data["nav_date"], "%Y-%m-%d").date()
                nav_is_today = (nav_date == today)
            except:
                pass
        
        # 如果净值是今天的，直接返回
        if nav_is_today and nav_data:
            return nav_data
        
        # 否则，尝试获取估值
        current_time = datetime.now(tz=tz.gettz("Asia/Shanghai")).time()
        trading_start = datetime.strptime("09:30", "%H:%M").time()
        trading_end = datetime.strptime("15:00", "%H:%M").time()
        
        # 交易时段内，获取估值
        if trading_start <= current_time <= trading_end:
            estimate_data = self.get_realtime_estimate(fund_code)
        
        # 返回策略
        if prefer_nav and nav_data:
            return nav_data
        elif estimate_data:
            return estimate_data
        else:
            return nav_data
    
    def get_historical_nav(
        self,
        fund_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 90
    ) -> List[Dict[str, Any]]:
        """
        获取历史净值序列
        
        Args:
            fund_code: 基金代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 最大返回条数
        
        Returns:
            [{
                "date": "2025-10-27",
                "nav": "1.2300",
                "accumulated_nav": "1.2300",
                "change_percent": "0.12"
            }, ...]
        """
        try:
            url = "https://api.fund.eastmoney.com/f10/lsjz"
            
            params = {
                "fundCode": fund_code,
                "pageIndex": 1,
                "pageSize": limit,
                "startDate": start_date.strftime("%Y-%m-%d") if start_date else "",
                "endDate": end_date.strftime("%Y-%m-%d") if end_date else "",
                "_": int(time.time() * 1000)
            }
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("ErrCode") != 0:
                logger.warning(f"历史净值接口返回错误: {fund_code}, {data.get('ErrMsg')}")
                return []
            
            ls_data = data.get("Data", {}).get("LSJZList", [])
            
            result = []
            for item in ls_data:
                result.append({
                    "date": item.get("FSRQ"),
                    "nav": item.get("DWJZ"),
                    "accumulated_nav": item.get("LJJZ"),
                    "change_percent": item.get("JZZZL")
                })
            
            logger.info(f"获取历史净值成功: {fund_code}, {len(result)} 条")
            return result
        
        except Exception as e:
            logger.error(f"获取历史净值失败: {fund_code}, {e}")
            return []


# 全局实例
_api_instance: Optional[EastMoneyFundAPI] = None


def get_fund_api(cache_dir: Optional[str] = None, cache_ttl: int = 300) -> EastMoneyFundAPI:
    """获取 API 实例（单例模式）"""
    global _api_instance
    if _api_instance is None:
        _api_instance = EastMoneyFundAPI(cache_dir, cache_ttl)
    return _api_instance



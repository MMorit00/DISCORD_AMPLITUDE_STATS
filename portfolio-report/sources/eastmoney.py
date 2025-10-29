"""
东方财富（天天基金）数据源
抓取基金净值、估值、历史数据
"""
import os
import json
import logging
import time
from datetime import datetime, timedelta, date, time as time_type
from typing import Optional, Dict, List, Any, TypedDict
from pathlib import Path
import requests
from dateutil import tz

logger = logging.getLogger(__name__)


# ==================
# Types & Constants
# ==================

class EstimateData(TypedDict, total=False):
    """实时估值数据模型（盘中行情）"""
    fund_code: str
    name: str
    estimate_value: str      # 估算净值（类比股票现价）
    estimate_time: str       # 估值时间
    last_nav: str            # 上一交易日净值（类比昨收价）
    last_nav_date: str       # 净值日期
    change_percent: str      # 估算涨跌幅 %
    nav_kind: str            # "估"
    fetched_at: str


class NavData(TypedDict, total=False):
    """最新净值数据模型（已公布净值）"""
    fund_code: str
    name: str
    nav: str                 # 单位净值（类比股票收盘价）
    nav_date: str            # 净值日期
    accumulated_nav: str     # 累计净值
    change_percent: str      # 日涨跌幅 %
    nav_kind: str            # "净"
    fetched_at: str


class HistoricalNavRecord(TypedDict, total=False):
    """历史净值记录（类比K线数据点）"""
    date: str
    nav: str
    accumulated_nav: str
    change_percent: str


# API 端点常量
api_base_url = "https://fundgz.1234567.com.cn"
api_fund_detail_url = "https://fund.eastmoney.com"
api_nav_query_url = "https://api.fund.eastmoney.com/f10/lsjz"

# 交易时段常量（A股交易时间）
trading_start_time = "09:30"
trading_end_time = "15:00"

# 默认缓存配置
default_cache_ttl = 300  # 5分钟


# ==================
# Repositories（缓存管理）
# ==================

class CacheRepository:
    """缓存仓储：负责本地缓存的读写与过期判断"""
    
    def __init__(self, cache_dir: Path, cache_ttl: int = default_cache_ttl):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = cache_ttl
    
    def _get_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"
    
    def read(self, key: str) -> Optional[Dict[str, Any]]:
        """读取缓存（自动检查过期）"""
        cache_path = self._get_path(key)
        if not cache_path.exists():
            return None
        
        # 检查过期
        mtime = cache_path.stat().st_mtime
        age = time.time() - mtime
        if age > self.cache_ttl:
            logger.debug(f"缓存已过期: {key} (age={age:.1f}s)")
            return None
        
        with open(cache_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.debug(f"命中缓存: {key}")
        return data
    
    def write(self, key: str, data: Dict[str, Any]) -> None:
        """写入缓存"""
        cache_path = self._get_path(key)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"写入缓存: {key}")


# ==================
# Services（业务服务）
# ==================

class HttpService:
    """HTTP 请求服务：统一管理 session/headers"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://fund.eastmoney.com/"
        })
    
    def get(self, url: str, params: Optional[Dict] = None, timeout: int = 10) -> requests.Response:
        """发起 GET 请求"""
        return self.session.get(url, params=params, timeout=timeout)
    
    def get_json(self, url: str, params: Optional[Dict] = None, timeout: int = 10) -> Dict:
        """发起 GET 请求并解析 JSON"""
        response = self.get(url, params, timeout)
        response.raise_for_status()
        return response.json()


class ParserService:
    """数据解析服务：JSONP/JSON 格式化与结构映射"""
    
    @staticmethod
    def parse_jsonp(text: str, prefix: str = "jsonpgz") -> Optional[Dict]:
        """解析 JSONP 格式（去掉回调函数包装）"""
        text = text.strip()
        if not text.startswith(f"{prefix}("):
            return None
        json_str = text[len(prefix)+1:-2]  # 去掉 "jsonpgz(" 和 ");"
        return json.loads(json_str)
    
    @staticmethod
    def parse_estimate_response(data: Dict) -> EstimateData:
        """解析估值接口返回的原始数据为 EstimateData"""
        return EstimateData(
            fund_code=data.get("fundcode"),
            name=data.get("name"),
            estimate_value=data.get("gsz"),
            estimate_time=data.get("gztime"),
            last_nav=data.get("dwjz"),
            last_nav_date=data.get("jzrq"),
            change_percent=data.get("gszzl"),
            nav_kind="估",
            fetched_at=datetime.now(tz=tz.gettz("Asia/Shanghai")).isoformat()
        )
    
    @staticmethod
    def parse_nav_response(data: Dict, fund_code: str) -> Optional[NavData]:
        """解析净值接口返回的原始数据为 NavData"""
        ls_data = data.get("Data", {}).get("LSJZList", [])
        if not ls_data:
            return None
        latest = ls_data[0]
        return NavData(
            fund_code=fund_code,
            name=data.get("Data", {}).get("FundName", ""),
            nav=latest.get("DWJZ"),
            nav_date=latest.get("FSRQ"),
            accumulated_nav=latest.get("LJJZ"),
            change_percent=latest.get("JZZZL"),
            nav_kind="净",
            fetched_at=datetime.now(tz=tz.gettz("Asia/Shanghai")).isoformat()
        )


class TradingTimeService:
    """交易时段判断服务"""
    
    @staticmethod
    def is_trading_hours() -> bool:
        """判断当前是否在交易时段（09:30-15:00）"""
        current_time = datetime.now(tz=tz.gettz("Asia/Shanghai")).time()
        start = datetime.strptime(trading_start_time, "%H:%M").time()
        end = datetime.strptime(trading_end_time, "%H:%M").time()
        return start <= current_time <= end
    
    @staticmethod
    def is_nav_today(nav_date_str: str) -> bool:
        """判断净值日期是否为今天"""
        try:
            nav_date = datetime.strptime(nav_date_str, "%Y-%m-%d").date()
            return nav_date == date.today()
        except:
            return False


# ==================
# Strategies（策略层）
# ==================

class NavEstimateStrategy:
    """净值/估值智能选择策略（类比：优先成交价 vs 实时报价）"""
    
    def __init__(self, trading_time_service: TradingTimeService):
        self.trading_time_service = trading_time_service
    
    def choose(
        self,
        nav_data: Optional[NavData],
        estimate_data: Optional[EstimateData],
        prefer_nav: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        智能选择净值或估值
        
        策略：
        1. 如果净值是今天的 → 直接返回净值（类比：已有收盘价就用收盘价）
        2. 如果净值不是今天的 且 当前在交易时段 → 返回估值（类比：盘中用实时价）
        3. 否则根据 prefer_nav 决定
        """
        # 检查净值是否为今天
        if nav_data and nav_data.get("nav_date"):
            if self.trading_time_service.is_nav_today(nav_data["nav_date"]):
                return nav_data
        
        # 如果在交易时段，优先估值
        if self.trading_time_service.is_trading_hours() and estimate_data:
            return estimate_data
        
        # 默认策略
        if prefer_nav and nav_data:
            return nav_data
        elif estimate_data:
            return estimate_data
        else:
            return nav_data


# ==================
# Facade（对外 API 门面）
# ==================

class EastMoneyFundAPI:
    """东方财富基金数据 API（编排层）
    
    职责：
    - 组装仓储/服务/策略依赖
    - 提供对外统一接口（估值/净值/历史数据）
    """
    
    # API 端点（兼容旧代码，保留类属性）
    BASE_URL = api_base_url
    FUND_DETAIL_URL = api_fund_detail_url
    
    def __init__(self, cache_dir: Optional[str] = None, cache_ttl: int = default_cache_ttl):
        """初始化 API 实例"""
        if cache_dir is None:
            base_dir = Path(__file__).parent.parent
            cache_dir = base_dir / "data" / "cache"
        
        # 组装仓储
        self.cache_repo = CacheRepository(Path(cache_dir), cache_ttl)
        
        # 组装服务
        self.http_service = HttpService()
        self.parser_service = ParserService()
        self.trading_time_service = TradingTimeService()
        
        # 组装策略
        self.nav_estimate_strategy = NavEstimateStrategy(self.trading_time_service)
    
    def get_realtime_estimate(self, fund_code: str) -> Optional[EstimateData]:
        """获取基金实时估值（盘中行情）"""
        cache_key = f"estimate_{fund_code}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        # 尝试从缓存读取
        cached = self.cache_repo.read(cache_key)
        if cached:
            return cached  # type: ignore[return-value]
        
        # 请求估值接口
        url = f"{api_base_url}/js/{fund_code}.js"
        response = self.http_service.get(url, timeout=10)
        response.raise_for_status()
        
        # 解析 JSONP
        data = self.parser_service.parse_jsonp(response.text)
        if not data:
            logger.warning(f"估值接口返回格式异常: {fund_code}")
            return None
        
        # 格式化为 EstimateData
        result = self.parser_service.parse_estimate_response(data)
        
        # 写入缓存
        self.cache_repo.write(cache_key, result)  # type: ignore[arg-type]
        
        logger.info(f"获取估值成功: {fund_code} {result.get('name')} "
                   f"{result.get('estimate_value')} ({result.get('change_percent')}%)")
        
        return result
    
    def get_latest_nav(self, fund_code: str) -> Optional[NavData]:
        """获取基金最新净值（已公布的收盘价）"""
        cache_key = f"nav_{fund_code}_{datetime.now().strftime('%Y%m%d')}"
        
        # 尝试从缓存读取
        cached = self.cache_repo.read(cache_key)
        if cached:
            return cached  # type: ignore[return-value]
        
        # 请求净值接口
        params = {
            "fundCode": fund_code,
            "pageIndex": 1,
            "pageSize": 1,
            "startDate": "",
            "endDate": "",
            "_": int(time.time() * 1000)
        }
        
        data = self.http_service.get_json(api_nav_query_url, params, timeout=10)
        
        if data.get("ErrCode") != 0:
            logger.warning(f"净值接口返回错误: {fund_code}, {data.get('ErrMsg')}")
            return None
        
        # 解析为 NavData
        result = self.parser_service.parse_nav_response(data, fund_code)
        if not result:
            logger.warning(f"未找到净值数据: {fund_code}")
            return None
        
        # 写入缓存
        self.cache_repo.write(cache_key, result)  # type: ignore[arg-type]
        
        logger.info(f"获取净值成功: {fund_code} {result.get('name')} "
                   f"{result.get('nav')} ({result.get('nav_date')})")
        
        return result
    
    def get_nav_or_estimate(self, fund_code: str, prefer_nav: bool = True) -> Optional[Dict[str, Any]]:
        """获取净值或估值（智能选择，委托 NavEstimateStrategy）"""
        nav_data = self.get_latest_nav(fund_code)
        estimate_data = None
        
        # 如果在交易时段，尝试获取估值
        if self.trading_time_service.is_trading_hours():
            estimate_data = self.get_realtime_estimate(fund_code)
        
        # 委托策略选择
        return self.nav_estimate_strategy.choose(nav_data, estimate_data, prefer_nav)
    
    def get_historical_nav(
        self,
        fund_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 90
    ) -> List[HistoricalNavRecord]:
        """获取历史净值序列（类比K线数据）"""
        params = {
            "fundCode": fund_code,
            "pageIndex": 1,
            "pageSize": limit,
            "startDate": start_date.strftime("%Y-%m-%d") if start_date else "",
            "endDate": end_date.strftime("%Y-%m-%d") if end_date else "",
            "_": int(time.time() * 1000)
        }
        
        data = self.http_service.get_json(api_nav_query_url, params, timeout=15)
        
        if data.get("ErrCode") != 0:
            logger.warning(f"历史净值接口返回错误: {fund_code}, {data.get('ErrMsg')}")
            return []
        
        ls_data = data.get("Data", {}).get("LSJZList", [])
        
        result: List[HistoricalNavRecord] = []
        for item in ls_data:
            result.append(HistoricalNavRecord(
                date=item.get("FSRQ"),
                nav=item.get("DWJZ"),
                accumulated_nav=item.get("LJJZ"),
                change_percent=item.get("JZZZL")
            ))
        
        logger.info(f"获取历史净值成功: {fund_code}, {len(result)} 条")
        return result


# 全局实例
_api_instance: Optional[EastMoneyFundAPI] = None


def get_fund_api(cache_dir: Optional[str] = None, cache_ttl: int = 300) -> EastMoneyFundAPI:
    """获取 API 实例（单例模式）"""
    global _api_instance
    if _api_instance is None:
        _api_instance = EastMoneyFundAPI(cache_dir, cache_ttl)
    return _api_instance



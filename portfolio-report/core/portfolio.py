"""
持仓管理与计算模块
支持：估/净并行计算、权重分析、收益计算
"""
import csv
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any, TypedDict, Literal
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from utils.config_loader import ConfigLoader
from sources.eastmoney import get_fund_api
from core.trading_calendar import get_calendar

logger = logging.getLogger(__name__)


# ==================
# Types & Constants
# ==================

class TransactionRow(TypedDict, total=False):
    """交易记录行（CSV）
    仅定义当前用到的字段，后续可按需补充。
    """
    tx_id: str
    date: str
    fund_code: str
    amount: str
    shares: str
    type: Literal["buy", "sell", "skip"]
    status: Literal["pending", "confirmed", "skipped"]


# 交易类型常量
TX_BUY = "buy"
TX_SELL = "sell"
TX_SKIP = "skip"

# 交易状态常量
STATUS_CONFIRMED = "confirmed"


# ==================
# Repositories（仓储层：IO 操作）
# ==================

class TransactionRepository:
    """交易记录仓储：负责读取 transactions.csv"""

    def __init__(self, transactions_file: Path):
        self.transactions_file = transactions_file

    def load_all(self) -> List[Dict[str, str]]:
        """加载所有交易记录"""
        if not self.transactions_file.exists():
            logger.warning(f"交易记录文件不存在: {self.transactions_file}")
            return []

        transactions = []
        try:
            with open(self.transactions_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    transactions.append(row)
            logger.info(f"加载了 {len(transactions)} 条交易记录")
            return transactions
        except Exception as e:
            logger.error(f"加载交易记录失败: {e}")
            return []


class HoldingsRepository:
    """持仓快照仓储：负责写入 holdings.json"""

    def __init__(self, holdings_file: Path):
        self.holdings_file = holdings_file

    def save(self, snapshot: Dict[str, Any]) -> None:
        """保存持仓快照"""
        try:
            with open(self.holdings_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            logger.info(f"保存持仓快照: {self.holdings_file}")
        except Exception as e:
            logger.error(f"保存持仓快照失败: {e}")


# ==================
# Entities（领域实体）
# ==================

class Position:
    """单个持仓"""
    
    def __init__(
        self,
        fund_code: str,
        shares: Decimal,
        asset_class: str,
        fund_type: str = "domestic"
    ):
        self.fund_code = fund_code
        self.shares = shares
        self.asset_class = asset_class  # US_QDII, CSI300, CGB_3_5Y
        self.fund_type = fund_type      # domestic, QDII
        
        # 净值数据
        self.nav: Optional[Decimal] = None
        self.nav_date: Optional[date] = None
        
        # 估值数据
        self.estimate_value: Optional[Decimal] = None
        self.estimate_time: Optional[datetime] = None
        
        # 市值
        self.market_value_net: Decimal = Decimal("0")
        self.market_value_est: Decimal = Decimal("0")
    
    def update_nav(self, nav: str, nav_date: str):
        """更新净值"""
        self.nav = Decimal(str(nav))
        self.nav_date = datetime.strptime(nav_date, "%Y-%m-%d").date()
        self.market_value_net = self.shares * self.nav
    
    def update_estimate(self, estimate: str, estimate_time: str):
        """更新估值"""
        self.estimate_value = Decimal(str(estimate))
        self.estimate_time = datetime.strptime(estimate_time, "%Y-%m-%d %H:%M")
        self.market_value_est = self.shares * self.estimate_value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "fund_code": self.fund_code,
            "shares": float(self.shares),
            "asset_class": self.asset_class,
            "fund_type": self.fund_type,
            "nav": float(self.nav) if self.nav else None,
            "nav_date": self.nav_date.isoformat() if self.nav_date else None,
            "estimate_value": float(self.estimate_value) if self.estimate_value else None,
            "estimate_time": self.estimate_time.isoformat() if self.estimate_time else None,
            "market_value_net": float(self.market_value_net),
            "market_value_est": float(self.market_value_est)
        }


# ==================
# Services（服务层：纯业务逻辑）
# ==================

class PositionBuilder:
    """持仓构建服务：从交易记录构建持仓"""

    def __init__(self, config: ConfigLoader):
        self.config = config

    def build_positions(self, transactions: List[Dict[str, str]]) -> Dict[str, Position]:
        """从交易记录构建持仓"""
        shares_by_fund: Dict[str, Decimal] = {}

        for tx in transactions:
            fund_code = tx.get("fund_code")
            shares_str = tx.get("shares", "0")
            tx_type = tx.get("type", TX_BUY)
            status = tx.get("status", STATUS_CONFIRMED)

            # 只统计已确认的交易
            if status != STATUS_CONFIRMED:
                continue

            # 跳过标记为 skipped 的记录
            if tx_type == TX_SKIP:
                continue

            try:
                shares = Decimal(str(shares_str))
                if tx_type == TX_BUY:
                    shares_by_fund[fund_code] = shares_by_fund.get(fund_code, Decimal("0")) + shares
                elif tx_type == TX_SELL:
                    shares_by_fund[fund_code] = shares_by_fund.get(fund_code, Decimal("0")) - shares
            except (ValueError, TypeError) as e:
                logger.warning(f"无效的份额数据: {fund_code}, {shares_str}, {e}")
                continue

        # 创建持仓对象
        positions = {}
        for fund_code, shares in shares_by_fund.items():
            if shares <= 0:
                continue
            asset_class = self._get_asset_class(fund_code)
            fund_type = self.config.get_fund_type(fund_code)
            position = Position(fund_code, shares, asset_class, fund_type)
            positions[fund_code] = position

        logger.info(f"构建了 {len(positions)} 个持仓")
        return positions

    def _get_asset_class(self, fund_code: str) -> str:
        """获取基金的资产类别"""
        funds_config = self.config.get('funds', {})
        for asset_class, codes in funds_config.items():
            if fund_code in codes:
                return asset_class
        logger.warning(f"未找到基金 {fund_code} 的资产类别配置")
        return "Unknown"


class PriceUpdater:
    """价格更新服务：为持仓更新净值/估值"""

    def update_positions_prices(self, positions: Dict[str, Position], fund_api, prefer_estimate: bool = False):
        """获取所有持仓的净值/估值数据"""
        for fund_code, position in positions.items():
            try:
                data = fund_api.get_nav_or_estimate(fund_code, prefer_nav=not prefer_estimate)
                if not data:
                    logger.warning(f"未获取到 {fund_code} 的数据")
                    continue

                # 更新净值
                if data.get('nav_kind') == '净':
                    position.update_nav(data['nav'], data['nav_date'])
                    logger.info(f"{fund_code} 净值: {data['nav']} ({data['nav_date']})")
                # 更新估值
                elif data.get('nav_kind') == '估':
                    position.update_estimate(data['estimate_value'], data['estimate_time'])
                    if data.get('last_nav') and data.get('last_nav_date'):
                        position.update_nav(data['last_nav'], data['last_nav_date'])
                    logger.info(f"{fund_code} 估值: {data['estimate_value']} ({data['estimate_time']})")
            except Exception as e:
                logger.error(f"获取 {fund_code} 数据失败: {e}")


class WeightCalculator:
    """权重计算服务：计算总市值与权重分布"""

    def calc_totals_and_weights(self, positions: Dict[str, Position]) -> Tuple[Decimal, Decimal, Dict[str, Decimal], Dict[str, Decimal]]:
        """计算总市值与权重（估/净并行）"""
        total_value_net = sum(pos.market_value_net for pos in positions.values())
        total_value_est = sum(pos.market_value_est for pos in positions.values())

        # 按资产类别汇总
        class_value_net: Dict[str, Decimal] = {}
        class_value_est: Dict[str, Decimal] = {}

        for position in positions.values():
            asset_class = position.asset_class
            class_value_net[asset_class] = class_value_net.get(asset_class, Decimal("0")) + position.market_value_net
            class_value_est[asset_class] = class_value_est.get(asset_class, Decimal("0")) + position.market_value_est

        # 计算权重
        weights_net: Dict[str, Decimal] = {}
        weights_est: Dict[str, Decimal] = {}

        if total_value_net > 0:
            for asset_class, value in class_value_net.items():
                weights_net[asset_class] = value / total_value_net

        if total_value_est > 0:
            for asset_class, value in class_value_est.items():
                weights_est[asset_class] = value / total_value_est

        logger.info(f"总市值(净): {total_value_net:.2f}")
        logger.info(f"总市值(估): {total_value_est:.2f}")
        logger.info(f"权重(净): {self._format_weights(weights_net)}")
        logger.info(f"权重(估): {self._format_weights(weights_est)}")

        return total_value_net, total_value_est, weights_net, weights_est

    def _format_weights(self, weights: Dict[str, Decimal]) -> str:
        """格式化权重输出"""
        return ", ".join(f"{k}: {float(v)*100:.2f}%" for k, v in weights.items())


class DeviationCalculator:
    """偏离计算服务：计算权重偏离"""

    def __init__(self, config: ConfigLoader):
        self.config = config

    def calc_weight_deviation(self, weights_net: Dict[str, Decimal]) -> Dict[str, Tuple[Decimal, Decimal]]:
        """计算权重偏离"""
        target_weights = self.config.get_target_weights()
        deviations = {}

        for asset_class, target in target_weights.items():
            target_decimal = Decimal(str(target))
            actual_net = weights_net.get(asset_class, Decimal("0"))

            # 绝对偏离
            abs_dev = abs(actual_net - target_decimal)

            # 相对偏离
            if target_decimal > 0:
                rel_dev = abs(actual_net / target_decimal - Decimal("1"))
            else:
                rel_dev = Decimal("0")

            deviations[asset_class] = (abs_dev, rel_dev)

        return deviations


# ==================
# Facade（对外门面：编排服务）
# ==================

class Portfolio:
    """投资组合"""
    
    def __init__(self, config: Optional[ConfigLoader] = None, data_dir: Optional[str] = None):
        """
        初始化
        
        Args:
            config: 配置加载器
            data_dir: 数据目录（默认为 portfolio-report/data）
        """
        self.config = config or ConfigLoader()
        
        if data_dir is None:
            base_dir = Path(__file__).parent.parent
            data_dir = base_dir / "data"
        
        self.data_dir = Path(data_dir)
        transactions_file = self.data_dir / "transactions.csv"
        holdings_file = self.data_dir / "holdings.json"
        
        # 仓储层
        self.transaction_repo = TransactionRepository(transactions_file)
        self.holdings_repo = HoldingsRepository(holdings_file)
        
        # 服务层
        self.position_builder = PositionBuilder(self.config)
        self.price_updater = PriceUpdater()
        self.weight_calculator = WeightCalculator()
        self.deviation_calculator = DeviationCalculator(self.config)
        
        # 持仓字典 {fund_code: Position}
        self.positions: Dict[str, Position] = {}
        
        # 汇总数据
        self.total_value_net = Decimal("0")
        self.total_value_est = Decimal("0")
        self.weights_net: Dict[str, Decimal] = {}
        self.weights_est: Dict[str, Decimal] = {}
        
        # API 实例
        self.fund_api = get_fund_api()
        self.calendar = get_calendar()
    
    # ---- 对外公开 API ----
    
    def get_weight_deviation(self) -> Dict[str, Tuple[Decimal, Decimal]]:
        """计算权重偏离（委托 DeviationCalculator）"""
        return self.deviation_calculator.calc_weight_deviation(self.weights_net)
    
    def refresh(self, prefer_estimate: bool = False):
        """刷新持仓数据（完整流程）"""
        logger.info("开始刷新持仓数据...")
        self._build_positions()
        self._fetch_nav_data(prefer_estimate)
        self._calculate_weights()
        self._save_holdings()
        logger.info("持仓数据刷新完成")
    
    # ---- 内部流程方法（私有） ----
    
    def _load_transactions(self) -> List[Dict[str, str]]:
        """加载交易记录（委托 TransactionRepository）"""
        return self.transaction_repo.load_all()
    
    def _build_positions(self) -> Dict[str, Position]:
        """构建持仓（委托 PositionBuilder）"""
        transactions = self._load_transactions()
        self.positions = self.position_builder.build_positions(transactions)
        return self.positions
    
    def _fetch_nav_data(self, prefer_estimate: bool = False):
        """获取所有持仓的净值/估值数据（委托 PriceUpdater）"""
        self.price_updater.update_positions_prices(self.positions, self.fund_api, prefer_estimate)
    
    def _calculate_weights(self):
        """计算权重（委托 WeightCalculator）"""
        result = self.weight_calculator.calc_totals_and_weights(self.positions)
        self.total_value_net, self.total_value_est, self.weights_net, self.weights_est = result
    
    def _save_holdings(self):
        """保存持仓快照（委托 HoldingsRepository）"""
        snapshot = {
            "generated_at": datetime.now().isoformat(),
            "total_value_net": float(self.total_value_net),
            "total_value_est": float(self.total_value_est),
            "weights_net": {k: float(v) for k, v in self.weights_net.items()},
            "weights_est": {k: float(v) for k, v in self.weights_est.items()},
            "positions": {
                code: pos.to_dict() for code, pos in self.positions.items()
            }
        }
        self.holdings_repo.save(snapshot)


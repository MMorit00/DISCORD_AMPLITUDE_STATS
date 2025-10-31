"""
持仓管理核心模块
职责：持仓计算、权重分析、领域服务
依赖：domain, infrastructure, shared
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from pathlib import Path

from portfolio_report.domain.models import Position
from portfolio_report.config.loader import ConfigLoader
from portfolio_report.config.constants import TransactionFields
from portfolio_report.shared.types import Result

logger = logging.getLogger(__name__)


# ==================
# Domain Services（领域服务）
# ==================

class PositionBuilder:
    """持仓构建服务：从交易记录构建持仓"""

    def __init__(self, config: ConfigLoader):
        self.config = config

    def build_positions(self, transactions: List[Dict[str, str]]) -> Dict[str, Position]:
        """
        从交易记录构建持仓
        
        Args:
            transactions: 交易记录列表
            
        Returns:
            Dict[fund_code, Position]
        """
        shares_by_fund: Dict[str, Decimal] = {}

        for tx in transactions:
            fund_code = tx.get(TransactionFields.fund_code)
            shares_str = tx.get(TransactionFields.shares, "0")
            tx_type = tx.get(TransactionFields.type, "buy")
            status = tx.get(TransactionFields.status, "confirmed")

            # 只统计已确认的交易
            if status != "confirmed":
                continue

            # 跳过标记为 skipped 的记录
            if tx_type == "skip":
                continue

            try:
                shares = Decimal(str(shares_str))
                if tx_type == "buy":
                    shares_by_fund[fund_code] = shares_by_fund.get(fund_code, Decimal("0")) + shares
                elif tx_type == "sell":
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
            
            position = Position(
                fund_code=fund_code,
                shares=shares,
                asset_class=asset_class,
                fund_type=fund_type
            )
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

    def update_positions_prices(
        self,
        positions: Dict[str, Position],
        fund_api,
        prefer_estimate: bool = False
    ):
        """
        获取所有持仓的净值/估值数据
        
        Args:
            positions: 持仓字典
            fund_api: 基金 API
            prefer_estimate: 是否优先使用估值
        """
        for fund_code, position in positions.items():
            try:
                data = fund_api.get_nav_or_estimate(fund_code, prefer_nav=not prefer_estimate)
                if not data:
                    logger.warning(f"未获取到 {fund_code} 的数据")
                    continue

                # 更新净值或估值
                self._update_position_data(position, data)
                
            except Exception as e:
                logger.error(f"获取 {fund_code} 数据失败: {e}")

    def _update_position_data(self, position: Position, data: Dict):
        """更新持仓数据"""
        nav_kind = data.get('nav_kind')
        
        if nav_kind == '净':
            # 更新净值
            position.nav = Decimal(str(data['nav']))
            position.nav_date = datetime.strptime(data['nav_date'], "%Y-%m-%d").date()
            position.market_value_net = position.shares * position.nav
            logger.info(f"{position.fund_code} 净值: {data['nav']} ({data['nav_date']})")
            
        elif nav_kind == '估':
            # 更新估值
            position.estimate_value = Decimal(str(data['estimate_value']))
            position.estimate_time = datetime.strptime(data['estimate_time'], "%Y-%m-%d %H:%M")
            position.market_value_est = position.shares * position.estimate_value
            
            # 同时更新上一交易日净值
            if data.get('last_nav') and data.get('last_nav_date'):
                position.nav = Decimal(str(data['last_nav']))
                position.nav_date = datetime.strptime(data['last_nav_date'], "%Y-%m-%d").date()
                position.market_value_net = position.shares * position.nav
            
            logger.info(f"{position.fund_code} 估值: {data['estimate_value']} ({data['estimate_time']})")


class WeightCalculator:
    """权重计算服务：计算总市值与权重分布"""

    def calc_totals_and_weights(
        self,
        positions: Dict[str, Position]
    ) -> Tuple[Decimal, Decimal, Dict[str, Decimal], Dict[str, Decimal]]:
        """
        计算总市值与权重（估/净并行）
        
        Args:
            positions: 持仓字典
            
        Returns:
            (total_value_net, total_value_est, weights_net, weights_est)
        """
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
        """
        计算权重偏离
        
        Args:
            weights_net: 当前权重（净值口径）
            
        Returns:
            Dict[asset_class, (abs_deviation, rel_deviation)]
        """
        target_weights = self.config.get_target_weights()
        deviations = {}

        for asset_class, target in target_weights.items():
            target_decimal = Decimal(str(target))
            actual_net = weights_net.get(asset_class, Decimal("0"))

            # 绝对偏离
            abs_dev = abs(actual_net - target_decimal)

            # 相对偏离
            if target_decimal > 0:
                rel_dev = (actual_net - target_decimal) / target_decimal
            else:
                rel_dev = Decimal("0")

            deviations[asset_class] = (abs_dev, rel_dev)

        return deviations


# ==================
# Aggregate Root（聚合根）
# ==================

class Portfolio:
    """
    投资组合聚合根
    职责：编排领域服务，维护持仓状态
    """
    
    def __init__(
        self,
        repository,  # GitHubRepository 或其他仓储实现（不再在领域层使用）
        fund_api,
        config: ConfigLoader
    ):
        """
        初始化（依赖注入）
        
        Args:
            repository: 统一仓储（提供 load_all_transactions/save_holdings/load_holdings）
            fund_api: 基金 API
            config: 配置加载器
        """
        self.repository = repository
        self.fund_api = fund_api
        self.config = config
        
        # 领域服务
        self.position_builder = PositionBuilder(config)
        self.price_updater = PriceUpdater()
        self.weight_calculator = WeightCalculator()
        self.deviation_calculator = DeviationCalculator(config)
        
        # 持仓状态
        self.positions: Dict[str, Position] = {}
        self.total_value_net = Decimal("0")
        self.total_value_est = Decimal("0")
        self.weights_net: Dict[str, Decimal] = {}
        self.weights_est: Dict[str, Decimal] = {}
    
    # ==================== 公开 API ====================
    
    def set_positions_from_transactions(self, transactions: List[Dict[str, str]]) -> None:
        """从交易记录构建并设置持仓（纯计算）"""
        self.positions = self.position_builder.build_positions(transactions)

    def update_positions_prices_from_map(self, price_data_by_fund: Dict[str, Dict], prefer_estimate: bool = False) -> None:
        """使用外部提供的价格数据更新持仓（纯计算，不做 I/O）"""
        for fund_code, position in self.positions.items():
            data = price_data_by_fund.get(fund_code)
            if not data:
                logger.warning(f"未提供 {fund_code} 的价格数据")
                continue
            try:
                self.price_updater._update_position_data(position, data)
            except Exception as e:
                logger.error(f"更新 {fund_code} 价格失败: {e}")

    def recalc_weights(self) -> None:
        """重新计算总市值与权重（纯计算）"""
        result = self.weight_calculator.calc_totals_and_weights(self.positions)
        self.total_value_net, self.total_value_est, self.weights_net, self.weights_est = result
    
    def get_weight_deviation(self) -> Dict[str, Tuple[Decimal, Decimal]]:
        """
        计算权重偏离
        
        Returns:
            Dict[asset_class, (abs_deviation, rel_deviation)]
        """
        return self.deviation_calculator.calc_weight_deviation(self.weights_net)
    
    # ==================== 快照构建 ====================
    
    def build_snapshot(self) -> Dict:
        """构建持仓快照（纯计算，不执行持久化）"""
        snapshot = {
            "generated_at": datetime.now().isoformat(),
            "total_value_net": float(self.total_value_net),
            "total_value_est": float(self.total_value_est),
            "weights_net": {k: float(v) for k, v in self.weights_net.items()},
            "weights_est": {k: float(v) for k, v in self.weights_est.items()},
            "positions": {
                code: self._position_to_dict(pos)
                for code, pos in self.positions.items()
            }
        }
        return snapshot
    
    def _position_to_dict(self, position: Position) -> Dict:
        """将 Position 转换为字典"""
        return {
            "fund_code": position.fund_code,
            "shares": float(position.shares),
            "asset_class": position.asset_class,
            "fund_type": position.fund_type,
            "nav": float(position.nav) if position.nav else None,
            "nav_date": position.nav_date.isoformat() if position.nav_date else None,
            "estimate_value": float(position.estimate_value) if position.estimate_value else None,
            "estimate_time": position.estimate_time.isoformat() if position.estimate_time else None,
            "market_value_net": float(position.market_value_net),
            "market_value_est": float(position.market_value_est)
        }

"""
持仓管理与计算模块
支持：估/净并行计算、权重分析、收益计算
"""
import csv
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

from utils.config_loader import ConfigLoader
from sources.eastmoney import get_fund_api
from core.trading_calendar import get_calendar

logger = logging.getLogger(__name__)


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
        self.transactions_file = self.data_dir / "transactions.csv"
        self.holdings_file = self.data_dir / "holdings.json"
        
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
    
    def load_transactions(self) -> List[Dict[str, str]]:
        """
        加载交易记录
        
        Returns:
            交易记录列表
        """
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
    
    def build_positions(self) -> Dict[str, Position]:
        """
        构建持仓
        
        从交易记录计算当前持有份额
        
        Returns:
            持仓字典 {fund_code: Position}
        """
        transactions = self.load_transactions()
        
        # 按基金代码聚合份额
        shares_by_fund: Dict[str, Decimal] = {}
        
        for tx in transactions:
            fund_code = tx.get("fund_code")
            shares_str = tx.get("shares", "0")
            tx_type = tx.get("type", "buy")
            status = tx.get("status", "confirmed")
            
            # 只统计已确认的交易
            if status not in ["confirmed"]:
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
                continue  # 跳过已清仓的基金
            
            # 获取资产类别
            asset_class = self._get_asset_class(fund_code)
            fund_type = self.config.get_fund_type(fund_code)
            
            position = Position(fund_code, shares, asset_class, fund_type)
            positions[fund_code] = position
        
        self.positions = positions
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
    
    def fetch_nav_data(self, prefer_estimate: bool = False):
        """
        获取所有持仓的净值/估值数据
        
        Args:
            prefer_estimate: 是否优先使用估值（默认优先净值）
        """
        for fund_code, position in self.positions.items():
            try:
                # 智能获取净值或估值
                data = self.fund_api.get_nav_or_estimate(
                    fund_code,
                    prefer_nav=not prefer_estimate
                )
                
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
                    # 同时更新昨日净值
                    if data.get('last_nav') and data.get('last_nav_date'):
                        position.update_nav(data['last_nav'], data['last_nav_date'])
                    logger.info(f"{fund_code} 估值: {data['estimate_value']} ({data['estimate_time']})")
            
            except Exception as e:
                logger.error(f"获取 {fund_code} 数据失败: {e}")
    
    def calculate_weights(self):
        """计算权重（估/净并行）"""
        # 计算总市值
        self.total_value_net = sum(
            pos.market_value_net for pos in self.positions.values()
        )
        self.total_value_est = sum(
            pos.market_value_est for pos in self.positions.values()
        )
        
        # 按资产类别汇总
        class_value_net: Dict[str, Decimal] = {}
        class_value_est: Dict[str, Decimal] = {}
        
        for position in self.positions.values():
            asset_class = position.asset_class
            
            class_value_net[asset_class] = (
                class_value_net.get(asset_class, Decimal("0")) + position.market_value_net
            )
            class_value_est[asset_class] = (
                class_value_est.get(asset_class, Decimal("0")) + position.market_value_est
            )
        
        # 计算权重
        self.weights_net = {}
        self.weights_est = {}
        
        if self.total_value_net > 0:
            for asset_class, value in class_value_net.items():
                self.weights_net[asset_class] = value / self.total_value_net
        
        if self.total_value_est > 0:
            for asset_class, value in class_value_est.items():
                self.weights_est[asset_class] = value / self.total_value_est
        
        logger.info(f"总市值(净): {self.total_value_net:.2f}")
        logger.info(f"总市值(估): {self.total_value_est:.2f}")
        logger.info(f"权重(净): {self._format_weights(self.weights_net)}")
        logger.info(f"权重(估): {self._format_weights(self.weights_est)}")
    
    def _format_weights(self, weights: Dict[str, Decimal]) -> str:
        """格式化权重输出"""
        return ", ".join(
            f"{k}: {float(v)*100:.2f}%" for k, v in weights.items()
        )
    
    def get_weight_deviation(self) -> Dict[str, Tuple[Decimal, Decimal]]:
        """
        计算权重偏离
        
        Returns:
            {
                asset_class: (absolute_deviation, relative_deviation)
            }
        """
        target_weights = self.config.get_target_weights()
        deviations = {}
        
        for asset_class, target in target_weights.items():
            target_decimal = Decimal(str(target))
            actual_net = self.weights_net.get(asset_class, Decimal("0"))
            
            # 绝对偏离
            abs_dev = abs(actual_net - target_decimal)
            
            # 相对偏离
            if target_decimal > 0:
                rel_dev = abs(actual_net / target_decimal - Decimal("1"))
            else:
                rel_dev = Decimal("0")
            
            deviations[asset_class] = (abs_dev, rel_dev)
        
        return deviations
    
    def save_holdings(self):
        """保存持仓快照"""
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_value_net": float(self.total_value_net),
            "total_value_est": float(self.total_value_est),
            "weights_net": {k: float(v) for k, v in self.weights_net.items()},
            "weights_est": {k: float(v) for k, v in self.weights_est.items()},
            "positions": {
                code: pos.to_dict() for code, pos in self.positions.items()
            }
        }
        
        try:
            with open(self.holdings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"保存持仓快照: {self.holdings_file}")
        
        except Exception as e:
            logger.error(f"保存持仓快照失败: {e}")
    
    def refresh(self, prefer_estimate: bool = False):
        """
        刷新持仓数据（完整流程）
        
        Args:
            prefer_estimate: 是否优先使用估值
        """
        logger.info("开始刷新持仓数据...")
        
        # 1. 构建持仓
        self.build_positions()
        
        # 2. 获取净值/估值
        self.fetch_nav_data(prefer_estimate)
        
        # 3. 计算权重
        self.calculate_weights()
        
        # 4. 保存快照
        self.save_holdings()
        
        logger.info("持仓数据刷新完成")

